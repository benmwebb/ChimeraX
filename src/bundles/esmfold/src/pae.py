# vim: set expandtab shiftwidth=4 softtabstop=4:

# === UCSF ChimeraX Copyright ===
# Copyright 2016 Regents of the University of California.
# All rights reserved.  This software provided pursuant to a
# license agreement containing restrictions on its disclosure,
# duplication and use.  For details see:
# http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
# This notice must be embedded in or attached to all copies,
# including partial copies, of the software or any revisions
# or derivations thereof.
# === UCSF ChimeraX Copyright ===

esmfold_pae_url = 'https://api.esmatlas.com/fetchConfidencePrediction/'

def esmfold_pae(session, structure = None, file = None, mgnify_id = None,
                palette = None, range = None, plot = None, divider_lines = None,
                color_domains = False, connect_max_pae = 5, cluster = 0.5, min_size = 10,
                version = None):
    '''Load ESM Metagenomics Atlas predicted aligned error file and show plot or color domains.'''

    if mgnify_id:
        pae_url = esmfold_pae_url + mgnify_id
        file_name = mgnify_id + '.json'
        from chimerax.core.fetch import fetch_file
        file = fetch_file(session, pae_url, 'ESM Metagenomics Atlas PAE %s' % mgnify_id,
                          file_name, 'ESMFold', error_status = False)
        
    if file:
        from chimerax.alphafold.pae import AlphaFoldPAE
        pae = AlphaFoldPAE(file, structure)
        pae._plddt_palette = 'esmfold'
        if structure:
            if not pae.reduce_matrix_to_residues_in_structure():
                from chimerax.core.errors import UserError
                raise UserError('Number of residues in structure "%s" is %d which does not match PAE matrix size %d.'
                                % (str(structure), structure.num_residues, pae.matrix_size) +
                                '\n\nThis can happen if residues were deleted from the ESMFold model or if the PAE data was applied to a structure that was not the one predicted by ESMFold.  Use the full-length ESMFold model to show predicted aligned error.')
            structure.esmfold_pae = pae
    elif structure is None:
        from chimerax.core.errors import UserError
        raise UserError('No structure or PAE file specified.')
    else:
        pae = getattr(structure, 'esmfold_pae', None)
        if pae is None:
            from chimerax.core.errors import UserError
            raise UserError('No predicted aligned error (PAE) data opened for structure #%s'
                            % structure.id_string)

    if plot is None:
        plot = not color_domains	# Plot by default if not coloring domains.
        
    if plot:
        from chimerax.core.colors import colormap_with_range
        colormap = colormap_with_range(palette, range, default_colormap_name = 'pae',
                                       full_range = (0,30))
        p = getattr(structure, '_esmfold_pae_plot', None)
        if p is None or p.closed():
            dividers = True if divider_lines is None else divider_lines
            from chimerax.alphafold.pae import AlphaFoldPAEPlot
            p = AlphaFoldPAEPlot(session, 'ESMFold Predicted Aligned Error', pae,
                                 colormap=colormap, divider_lines=dividers)
            if structure:
                structure._esmfold_pae_plot = p
        else:
            p.display(True)
            if palette is not None or range is not None:
                p.set_colormap(colormap)
            if divider_lines is not None:
                p.show_chain_dividers(divider_lines)

    pae.set_default_domain_clustering(connect_max_pae, cluster)
    if color_domains:
        if structure is None:
            from chimerax.core.errors import UserError
            raise UserError('Must specify structure to color domains.')
        pae.color_domains(connect_max_pae, cluster, min_size)

# -----------------------------------------------------------------------------
#
def register_esmfold_pae_command(logger):
    from chimerax.core.commands import CmdDesc, register, OpenFileNameArg, ColormapArg, ColormapRangeArg, BoolArg, FloatArg, IntArg
    from chimerax.atomic import AtomicStructureArg, UniProtIdArg
    desc = CmdDesc(
        optional = [('structure', AtomicStructureArg)],
        keyword = [('file', OpenFileNameArg),
                   ('uniprot_id', UniProtIdArg),
                   ('palette', ColormapArg),
                   ('range', ColormapRangeArg),
                   ('plot', BoolArg),
                   ('divider_lines', BoolArg),
                   ('color_domains', BoolArg),
                   ('connect_max_pae', FloatArg),
                   ('cluster', FloatArg),
                   ('min_size', IntArg),
                   ('version', IntArg)],
        synopsis = 'Show ESMFold predicted aligned error'
    )
    
    register('esmfold pae', desc, esmfold_pae, logger=logger)

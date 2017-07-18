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

def model(session, targets, combined_templates=False, custom_script=None,
    dist_restraints_path=None, executable_location=None, fast=False, het_preserve=False,
    hydrogens=False, license_key=None, num_models=5, temp_path=None, thorough_opt=False,
    water_preserve=False):
    """
    Generate comparitive models for the target sequences.

    Arguments:
    session
        current session
    targets
        list of (alignment, sequence) tuples.  Each sequence will be modelled.
    combined_templates
        If True, all associated chains are used as templates to generate a single set of
        models for the target sequence.  If False, each associated chain is used to
        generate a separate set of models of the target sequence.  The latter is useful
        for modelling multimers from a single alignment.
    custom_script
        If provided, the location of a custom Modeller script to use instead of the
        one we would otherwise generate.
    dist_restraints_path
        If provided, the path to a file containing additional distance restraints
    executable_location
        If provided, the path to the locally installed Modeller executable.  If not
        provided, use the web service.
    fast
        Whether to use fast but crude generation of models
    het_preserve
        Whether to preserve HET atoms in generated models
    hydrogens
        Whether to generate models with hydrogen atoms
    license_key
        Modeller license key.  If not provided, try to use settings to find one.
    num_models
        Number of models to generate for each template sequence
    temp_path
        If provided, folder to use for temporary files
    thorough_opt
        Whether to perform thorough optimization
    water_preserve
        Whether to preserve water in generated models
    """

    template_info = []
    for alignment, orig_target in targets:
        if not alignment.associations:
            raise ValueError("Alignment %s has no associatied chains to use as templates."
                % alignment.ident)
        # Copy the target sequence, changing name to conform to Modeller limitations
        from .common import modeller_copy
        target = modeller_copy(orig_target)
        if combined_templates:
            target_templates = []
            template_info.append((target, target_templates))
        for aseq, chain in alignment.associations.items():
            if not combined_templates:
                target_templates = []
                template_info.append((target, target_templates))
            target_templates.append((regularized_seq(aseq, chain), chain))

def regularized_seq(aseq, chain):
    mmap = aseq.match_maps[chain]
    from .common import modeller_copy
    rseq = modeller_copy(aseq)
    rseq.descript = "structure:" + chain_save_name(chain)
    for ungapped in range(len(aseq.ungapped())):
        gapped = aseq.ungapped_to_gapped(ungapped)
        if i not in mmap:
            rseq.characters[gapped] = '-'
        else:
           #TODO

def chain_save_name(chain):
    return chain.structure.name.replace(':', '_').replace(' ', '_') \
        + "_" + chain.structure.id_string() + '/' + chain.chain_id.replace(' ', '_')

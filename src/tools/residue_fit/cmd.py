# vim: set expandtab ts=4 sw=4:

def resfit(session, atoms, map = None, motion_frames = 50, pause_frames = 50, movie_framerate = 25):
    '''Display fit of each residue in a density map.

    Parameters
    ----------
    atoms : Atoms
      Atoms from one chain or part of a chain.
    map : Volume
      Density map to show near each residue.
    '''

    from chimerax.core.commands import AnnotationError
    if map is None:
        raise AnnotationError('Require "map" option: resfit #1 map #2')

    cids = atoms.unique_chain_ids
    if len(cids) != 1:
        raise AnnotationError('Atoms must belong to one chain, got %d chains %s'
                              % (len(cids), ', '.join(cids)))

    res = atoms.unique_residues
    bbres = residues_with_backbone(res)
    if len(bbres) == 0:
        raise AnnotationError('None of %d specified residues have backbone atoms "N", "CA" and "C"' % len(res))
    
    bundle_info = session.toolshed.find_bundle('residue_fit')
    from . import gui
    gui.ResidueFit(session, bundle_info, bbres, map,
                   motion_frames = motion_frames, pause_frames = pause_frames,
                   movie_framerate = movie_framerate)
    

def residues_with_backbone(residues):
    rb = []
    for i,r in enumerate(residues):
        anames = r.atoms.names
        if 'N' in anames and 'CA' in anames and 'C' in anames:
            rb.append(i)
    return residues.filter(rb)

def register_resfit_command():
    from chimerax.core.commands import CmdDesc, register, AtomsArg, IntArg
    from chimerax.core.map import MapArg
    desc = CmdDesc(required = [('atoms', AtomsArg)],
                   keyword = [('map', MapArg),
                              ('motion_frames', IntArg),
                              ('pause_frames', IntArg),
                              ('movie_framerate', IntArg)],
                   synopsis = 'Display slider to show fit of each residue in density map')
    register('resfit', desc, resfit)

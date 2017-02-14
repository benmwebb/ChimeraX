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

def style(session, objects=None, atom_style=None, atom_radius=None, stick_radius=None, ball_scale=None, dashes=None):
    '''Set the atom and bond display styles and sizes.

    Parameters
    ----------
    atoms : Atoms or None
        Change the style of these atoms. If not specified then all atoms are changed.
    atom_style : "sphere", "ball" or "stick"
        Controls how atoms and bonds are depicted.
    atom_radius : float or "default"
      New radius value for atoms.
    stick_radius : float
      New radius value for bonds shown in stick style.
    ball_scale : float
      Multiplier times atom radius for determining atom size in ball style (default 0.3).
    dashes : int
      Number of dashes shown for pseudobonds.
    '''
    from ..atomic import all_atoms, Atom
    atoms = all_atoms(session) if objects is None else objects.atoms

    what = []
    if atom_style is not None:
        s = {
            'sphere': Atom.SPHERE_STYLE,
            'ball': Atom.BALL_STYLE,
            'stick': Atom.STICK_STYLE,
        }[atom_style.lower()]
        atoms.draw_modes = s
        what.append('%d atom styles' % len(atoms))

    if atom_radius is not None:
        if atom_radius == 'default':
            atoms.radii = atoms.default_radii
        else:
            atoms.radii = atom_radius
        what.append('%d atom radii' % len(a))

    if stick_radius is not None:
        b = atoms.inter_bonds
        b.radii = stick_radius
        what.append('%d bond radii' % len(b))

    if ball_scale is not None:
        mols = atoms.unique_structures
        for s in mols:
            s.ball_scale = ball_scale
        what.append('%d ball scales' % len(mols))

    if what:
        msg = 'Changed %s' % ', '.join(what)
        log = session.logger
        log.status(msg)
        log.info(msg)

    if dashes is not None:
        for pbg in pseudobond_groups(objects, session):
            pbg.dashes = dashes

def pseudobond_groups(objects, session):
    from ..atomic import PseudobondGroup, all_atoms

    # Explicitly specified global pseudobond groups
    models = session.models.list() if objects is None else objects.models
    pbgs = set(m for m in models if isinstance(m, PseudobondGroup))

    atoms = all_atoms(session) if objects is None else objects.atoms

    # Intra-molecular pseudobond groups with bonds between specified atoms.
    for m in atoms.unique_structures:
        molpbgs = [pbg for pbg in m.pbg_map.values()
                   if pbg.pseudobonds.between_atoms(atoms).any()]
        pbgs.update(molpbgs)

    # Global pseudobond groups with bonds between specified atoms
    gpbgs = [pbg for pbg in session.models.list(type = PseudobondGroup)
             if pbg.pseudobonds.between_atoms(atoms).any()]
    pbgs.update(gpbgs)

    return pbgs


def register_command(session):
    from . import register, CmdDesc, ObjectsArg, EmptyArg, EnumOf, Or, IntArg, FloatArg
    desc = CmdDesc(required = [('objects', Or(ObjectsArg, EmptyArg)),
                               ('atom_style', Or(EnumOf(('sphere', 'ball', 'stick')), EmptyArg))],
                   keyword = [('atom_radius', Or(EnumOf(['default']), FloatArg)),
                              ('stick_radius', FloatArg),
                              ('ball_scale', FloatArg),
                              ('dashes', IntArg)],
                   synopsis='change atom and bond depiction')
    register('style', desc, style, logger=session.logger)

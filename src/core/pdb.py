# vim: set expandtab shiftwidth=4 softtabstop=4:
"""
pdb: PDB format support
=======================

Read Protein DataBank (PDB) files.
"""

from . import structure
from .cli import UserError

_builtin_open = open


def open_pdb(session, filename, *args, **kw):

    name = kw['name'] if 'name' in kw else None
    if hasattr(filename, 'read'):
        # it's really a fetched stream
        input = filename
    else:
        input = _builtin_open(filename, 'rb')
        if name is None:
            name = filename

    from . import pdbio
    mol_blob = pdbio.read_pdb_file(input)
    if input != filename:
        input.close()

    model = structure.StructureModel(name)
    model.mol_blob = mol_blob
    model.make_drawing()

    # TODO: is this a lightweight operation?
    atom_blob, bond_list = model.mol_blob.atoms_bonds
    num_atoms = len(atom_blob.coords)
    num_bonds = len(bond_list)

    return [model], ("Opened PDB data containing %d atoms and %d bonds"
                     % (num_atoms, num_bonds))


def fetch_pdb(session, pdb_id):
    if len(pdb_id) != 4:
        raise UserError("PDB identifiers are 4 characters long")
    import os
    # TODO: use our own cache
    # check in local cache
    filename = "~/Downloads/Chimera/PDB/%s.pdb" % pdb_id.upper()
    filename = os.path.expanduser(filename)
    if os.path.exists(filename):
        return _builtin_open(filename, 'rb')
    # check on local system -- TODO: configure location
    lower = pdb_id.lower()
    subdir = lower[1:3]
    filename = "/databases/mol/pdb/%s/pdb%s.ent" % (subdir, lower)
    if os.path.exists(filename):
        return _builtin_open(filename, 'rb')
    from urllib.request import URLError, Request, urlopen
    url = "http://www.rcsb.org/pdb/files/%s.pdb" % pdb_id.upper()
    # TODO: save in local cache
    from . import utils
    request = Request(url, headers={
        "User-Agent": utils.html_user_agent(session.app_dirs),
    })
    try:
        return urlopen(request)
    except URLError as e:
        raise UserError(str(e))


def register():
    from . import io
    io.register_format(
        "PDB", structure.CATEGORY, (".pdb", ".pdb1", ".ent", ".pqr"), ("pdb",),
        mime=("chemical/x-pdb", "chemical/x-spdbv"),
        reference="http://wwpdb.org/docs.html#format",
        open_func=open_pdb, fetch_func=fetch_pdb)

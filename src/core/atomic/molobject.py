# vim: set expandtab shiftwidth=4 softtabstop=4:
from numpy import uint8, int32, float64, float32, bool as npy_bool
from .molc import string, cptr, pyobject, c_property, set_c_pointer, c_function, ctype_type_to_numpy, pointer
import ctypes
size_t = ctype_type_to_numpy[ctypes.c_size_t]   # numpy dtype for size_t

# -------------------------------------------------------------------------------
# These routines convert C++ pointers to Python objects and are used for defining
# the object properties.
#
def _atoms(p):
    from .molarray import Atoms
    return Atoms(p)
def _atom_pair(p):
    return (object_map(p[0],Atom), object_map(p[1],Atom))
def _atom_or_none(p):
    return object_map(p, Atom) if p else None
def _bonds(p):
    from .molarray import Bonds
    return Bonds(p)
def _element(p):
    return object_map(p, Element)
def _pseudobonds(p):
    from .molarray import Pseudobonds
    return Pseudobonds(p)
def _residue(p):
    return object_map(p, Residue)
def _residues(p):
    from .molarray import Residues
    return Residues(p)
def _non_null_residues(p):
    from .molarray import Residues
    return Residues(p[p!=0])
def _residues_or_nones(p):
    return [Residue(rptr) if rptr else None for rptr in p]
def _chains(p):
    from .molarray import Chains
    return Chains(p)
def _atomic_structure(p):
    if p == 0: return None
    return object_map(p, AtomicStructureData)
def _pseudobond_group_map(pbgc_map):
    from .pbgroup import PseudobondGroup
    pbg_map = dict((name, object_map(pbg,PseudobondGroup)) for name, pbg in pbgc_map.items())
    return pbg_map

# -----------------------------------------------------------------------------
#
class Atom:
    '''
    An atom includes physical and graphical properties such as an element name,
    coordinates in space, and color and radius for rendering.

    To create an Atom use the :class:`.AtomicStructure` new_atom() method.
    '''

    SPHERE_STYLE, BALL_STYLE, STICK_STYLE = range(3)

    HIDE_RIBBON = 0x1
    BBE_MIN, BBE_RIBBON, BBE_MAX = range(3)

    bfactor = c_property('atom_bfactor', float32, doc = "B-factor, floating point value.")
    bonds = c_property('atom_bonds', cptr, "num_bonds", astype=_bonds, read_only=True,
        doc="Bonds connected to this atom as an array of :py:class:`Bonds` objects. Read only.")
    chain_id = c_property('atom_chain_id', string, read_only = True,
        doc = "Protein Data Bank chain identifier. Limited to 4 characters. Read only string.")
    color = c_property('atom_color', uint8, 4, doc="Color RGBA length 4 numpy uint8 array.")
    coord = c_property('atom_coord', float64, 3,
        doc="Coordinates as a numpy length 3 array, 64-bit float values.")
    display = c_property('atom_display', npy_bool,
        doc="Whether to display the atom. Boolean value.")
    draw_mode = c_property('atom_draw_mode', uint8,
        doc="Controls how the atom is depicted.\n\n|  Possible values:\n"
        "SPHERE_STYLE\n"
        "    Use full atom radius\n"
        "BALL_STYLE\n"
        "    Use reduced atom radius, but larger than bond radius\n"
        "STICK_STYLE\n"
        "    Match bond radius")
    element = c_property('atom_element', cptr, astype = _element, read_only = True,
        doc =  ":class:`Element` corresponding to the chemical element for the atom.")
    element_name = c_property('atom_element_name', string, read_only = True,
        doc = "Chemical element name. Read only.")
    element_number = c_property('atom_element_number', uint8, read_only = True,
        doc = "Chemical element number. Read only.")
    hide = c_property('atom_hide', int32,
        doc="Whether atom is hidden (overrides display).  Integer bitmask."
        "\n\n|  Possible values:\n"
        "HIDE_RIBBON\n"
        "    Hide mask for backbone atoms in ribbon.")
    in_chain = c_property('atom_in_chain', npy_bool, read_only = True,
        doc = "Whether this atom belongs to a polymer. Read only.")
    name = c_property('atom_name', string, doc = "Atom name. Maximum length 4 characters.")
    neighbors = c_property('atom_neighbors', cptr, "num_bonds", astype=_atoms, read_only=True,
        doc=":class:`.Atom`\\ s connnected to this atom directly by one bond. Read only.")
    num_bonds = c_property("atom_num_bonds", size_t, read_only=True,
        doc="Number of bonds connected to this atom. Read only.")
    radius = c_property('atom_radius', float32, doc="Radius of atom.")
    residue = c_property('atom_residue', cptr, astype = _residue, read_only = True,
        doc = ":class:`Residue` the atom belongs to.")
    selected = c_property('atom_selected', npy_bool, doc="Whether the atom is selected.")
    structure = c_property('atom_structure', cptr, astype=_atomic_structure, read_only=True,
        doc=":class:`.AtomicStructure` the atom belongs to")
    structure_category = c_property('atom_structure_category', string, read_only=True,
        doc = "Whether atom is ligand, ion, etc.")
    visible = c_property('atom_visible', npy_bool, read_only=True,
        doc="Whether atom is displayed and not hidden.")

    def __init__(self, c_pointer):
        set_c_pointer(self, c_pointer)

    def connects_to(self, atom):
        '''Whether this atom is directly bonded to a specified atom.'''
        f = c_function('atom_connects_to', args = (ctypes.c_void_p, ctypes.c_void_p),
               ret = ctypes.c_bool)
        c = f(self._c_pointer, atom._c_pointer)
        return c

    def is_backbone(self, bb_extent):
        '''Whether this Atom is considered backbone, given the 'extent' criteria.

        |  Possible 'extent' values are:
        BBE_MIN
            Only the atoms needed to connect the residue chain (and their hydrogens)
        BBE_MAX
            All non-sidechain atoms
        BBE_RIBBON
            The backbone atoms that a ribbon depiction hides
        '''
        f = c_function('atom_is_backbone', args = (ctypes.c_void_p, ctypes.c_int),
                ret = ctypes.c_bool)
        return f(self._c_pointer, bb_type)

    @property
    def scene_coord(self):
        '''
        Atom center coordinates in the global scene coordinate system.
        This accounts for the :class:`Drawing` positions for the hierarchy
        of models this atom belongs to.
        '''
        return self.structure.scene_position * self.coord

# -----------------------------------------------------------------------------
#
class Bond:
    '''
    Bond connecting two atoms.

    To create a Bond use the :class:`.AtomicStructure` new_bond() method.
    '''
    def __init__(self, bond_pointer):
        set_c_pointer(self, bond_pointer)

    atoms = c_property('bond_atoms', cptr, 2, astype = _atom_pair, read_only = True)
    '''Two-tuple of :py:class:`Atom` objects that are the bond end points.'''
    color = c_property('bond_color', uint8, 4)
    '''Color RGBA length 4 numpy uint8 array.'''
    display = c_property('bond_display', npy_bool)
    '''
    Whether to display the bond if both atoms are shown.
    Can be overriden by the hide attribute.
    '''
    halfbond = c_property('bond_halfbond', npy_bool)
    '''
    Whether to color the each half of the bond nearest an end atom to match that atom
    color, or use a single color and the bond color attribute.  Boolean value.
    '''
    radius = c_property('bond_radius', float32)
    '''Displayed cylinder radius for the bond.'''
    HIDE_RIBBON = 0x1
    '''Hide mask for backbone bonds in ribbon.'''
    hide = c_property('bond_hide', int32)
    '''Whether bond is hidden (overrides display).  Integer bitmask.'''
    shown = c_property('bond_shown', npy_bool, read_only = True)
    '''Whether bond is visible and both atoms are shown and at least one is not Sphere style. Read only.'''
    structure = c_property('bond_structure', cptr, astype = _atomic_structure, read_only = True)
    ''':class:`.AtomicStructure` the bond belongs to.'''
    visible = c_property('bond_visible', npy_bool, read_only = True)
    '''Whether bond is display and not hidden. Read only.'''

    def other_atom(self, atom):
        '''Return the :class:`Atom` at the other end of this bond opposite
        the specified atom.'''
        a1,a2 = self.atoms
        return a2 if atom is a1 else a1

# -----------------------------------------------------------------------------
#
class Pseudobond:
    '''
    A Pseudobond is a graphical line between atoms for example depicting a distance
    or a gap in an amino acid chain, often shown as a dotted or dashed line.
    Pseudobonds can join atoms belonging to different :class:`.AtomicStructure`\\ s
    which is not possible with a :class:`Bond`\\ .

    To create a Pseudobond use the :class:`PseudobondGroup` new_pseudobond() method.
    '''
    def __init__(self, pbond_pointer):
        set_c_pointer(self, pbond_pointer)

    atoms = c_property('pseudobond_atoms', cptr, 2, astype = _atom_pair, read_only = True)
    '''Two-tuple of :py:class:`Atom` objects that are the bond end points.'''
    color = c_property('pseudobond_color', uint8, 4)
    '''Color RGBA length 4 numpy uint8 array.'''
    display = c_property('pseudobond_display', npy_bool)
    '''
    Whether to display the bond if both atoms are shown.
    Can be overriden by the hide attribute.
    '''
    halfbond = c_property('pseudobond_halfbond', npy_bool)
    '''
    Whether to color the each half of the bond nearest an end atom to match that atom
    color, or use a single color and the bond color attribute.  Boolean value.
    '''
    radius = c_property('pseudobond_radius', float32)
    '''Displayed cylinder radius for the bond.'''
    shown = c_property('pseudobond_shown', npy_bool, read_only = True)
    '''Whether bond is visible and both atoms are shown. Read only.'''

    @property
    def length(self):
        '''Distance between centers of two bond end point atoms.'''
        a1, a2 = self.atoms
        v = a1.scene_coord - a2.scene_coord
        from math import sqrt
        return sqrt((v*v).sum())

# -----------------------------------------------------------------------------
#
class PseudobondGroupData:
    '''
    A group of pseudobonds typically used for one purpose such as display
    of distances or missing segments.  The category attribute names the group,
    for example "distances" or "missing segments".

    This base class of :class:`.PseudobondGroup` represents the C++ data while
    the derived class handles rendering the pseudobonds.

    To create a PseudobondGroup use the :class:`PseudobondManager` get_group() method.
    '''

    def __init__(self, pbg_pointer):
        set_c_pointer(self, pbg_pointer)

    category = c_property('pseudobond_group_category', string, read_only = True)
    '''Name of the pseudobond group.  Read only string.'''
    num_pseudobonds = c_property('pseudobond_group_num_pseudobonds', size_t, read_only = True)
    '''Number of pseudobonds in group. Read only.'''
    structure = c_property('pseudobond_group_structure', cptr, astype = _atomic_structure,
        read_only = True)
    '''Structure pseudobond group is owned by.  *Bad* things will happen if called
    on a group that isn't owned (i.e. managed by the global pseudobond manager
    rather than by a structure's pseudobond manager'''
    pseudobonds = c_property('pseudobond_group_pseudobonds', cptr, 'num_pseudobonds',
                             astype = _pseudobonds, read_only = True)
    '''Group pseudobonds as a :class:`.Pseudobonds` collection. Read only.'''

    def new_pseudobond(self, atom1, atom2):
        '''Create a new pseudobond between the specified :class:`Atom` objects.'''
        f = c_function('pseudobond_group_new_pseudobond',
                       args = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p),
                       ret = ctypes.c_void_p)
        pb = f(self._c_pointer, atom1._c_pointer, atom2._c_pointer)
        return object_map(pb, Pseudobond)

    # Graphics changed flags used by rendering code.  Private.
    _gc_color = c_property('pseudobond_group_gc_color', npy_bool)
    _gc_select = c_property('pseudobond_group_gc_select', npy_bool)
    _gc_shape = c_property('pseudobond_group_gc_shape', npy_bool)


# -----------------------------------------------------------------------------
#
from ..state import State
class PseudobondManager(State):
    '''Per-session singleton pseudobond manager keeps track of all
    :class:`.PseudobondGroupData` objects.'''

    def __init__(self, session):
        self.session = session
        f = c_function('pseudobond_create_global_manager', args = (ctypes.c_void_p,),
            ret = ctypes.c_void_p)
        set_c_pointer(self, f(session.change_tracker._c_pointer))
        self.session.triggers.add_handler("begin save session",
            lambda *args: self._ses_call("save_setup"))
        self.session.triggers.add_handler("end save session",
            lambda *args: self._ses_call("save_teardown"))
        self.session.triggers.add_handler("begin restore session",
            lambda *args: self._ses_call("restore_setup"))
        self.session.triggers.add_handler("end restore session",
            lambda *args: self._ses_call("restore_teardown"))

    def get_group(self, category, create = True):
        '''Get an existing :class:`.PseudobondGroup` or create a new one given a category name.'''
        f = c_function('pseudobond_global_manager_get_group',
                       args = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int),
                       ret = ctypes.c_void_p)
        pbg = f(self._c_pointer, category.encode('utf-8'), create)
        if not pbg:
            return None
        from .pbgroup import PseudobondGroup
        return object_map(pbg,
            lambda ptr, ses=self.session: PseudobondGroup(ptr, session=ses))

    def delete_group(self, pbg):
        f = c_function('pseudobond_global_manager_delete_group',
                       args = (ctypes.c_void_p, ctypes.c_void_p), ret = None)
        f(self._c_pointer, pbg._c_pointer)

    def take_snapshot(self, session, flags):
        '''Gather session info; return version number'''
        f = c_function('pseudobond_global_manager_session_info',
                    args = (ctypes.c_void_p, ctypes.py_object), ret = ctypes.c_int)
        retvals = []
        version = f(self._c_pointer, retvals)
        # remember the structure->int mapping the pseudobonds used...
        f = c_function('pseudobond_global_manager_session_save_structure_mapping',
                       args = (ctypes.c_void_p,), ret = ctypes.py_object)
        ptr_map = f(self._c_pointer)
        # mapping is ptr->int, change to int->obj
        obj_map = {}
        for ptr, ses_id in ptr_map.items():
            # shouldn't be _creating_ any objects, so pass None as the type
            obj_map[ses_id] = object_map(ptr, None)
        return version, (retvals, obj_map)

    def reset_state(self, session):
        f = c_function('pseudobond_global_manager_clear', args = (ctypes.c_void_p,))
        f(self._c_pointer)

    @classmethod
    def restore_snapshot_new(cls, session, bundle_info, version, data):
        return session.pb_manager

    def restore_snapshot_init(self, session, tool_info, version, data):
        mgr_data, structure_mapping = data
        # restore the int->structure mapping the pseudobonds use...
        ptr_mapping = {}
        for ses_id, structure in structure_mapping.items():
            ptr_mapping[ses_id] = structure._c_pointer.value
        f = c_function('pseudobond_global_manager_session_restore_structure_mapping',
                       args = (ctypes.c_void_p, ctypes.py_object))
        f(self._c_pointer, ptr_mapping)
        ints, floats, misc = mgr_data
        f = c_function('pseudobond_global_manager_session_restore',
                args = (ctypes.c_void_p, ctypes.c_int,
                        ctypes.py_object, ctypes.py_object, ctypes.py_object))
        f(self._c_pointer, version, ints, floats, misc)

    def _ses_call(self, func_qual):
        f = c_function('pseudobond_global_manager_session_' + func_qual, args=(ctypes.c_void_p,))
        f(self._c_pointer)


# -----------------------------------------------------------------------------
#
class Residue:
    '''
    A group of atoms such as an amino acid or nucleic acid. Every atom in
    an :class:`.AtomicStructure` belongs to a residue, including solvent and ions.

    To create a Residue use the :class:`.AtomicStructure` new_residue() method.
    '''

    def __init__(self, residue_pointer):
        set_c_pointer(self, residue_pointer)

    atoms = c_property('residue_atoms', cptr, 'num_atoms', astype = _atoms, read_only = True)
    ''':class:`.Atoms` collection containing all atoms of the residue.'''
    chain_id = c_property('residue_chain_id', string, read_only = True)
    '''Protein Data Bank chain identifier. Limited to 4 characters. Read only string.'''
    PT_NONE = 0
    '''Residue polymer type = none.'''
    PT_AMINO = 1
    '''Residue polymer type = amino acid.'''
    PT_NUCLEIC = 2
    '''Residue polymer type = nucleotide.'''
    polymer_type = c_property('residue_polymer_type', int32, read_only = True)
    '''Polymer type of residue. Integer value.'''
    is_helix = c_property('residue_is_helix', npy_bool)
    '''Whether this residue belongs to a protein alpha helix. Boolean value.'''
    is_sheet = c_property('residue_is_sheet', npy_bool)
    '''Whether this residue belongs to a protein beta sheet. Boolean value.'''
    ss_id = c_property('residue_ss_id', int32)
    '''Secondary structure id number. Integer value.'''
    ribbon_display = c_property('residue_ribbon_display', npy_bool)
    '''Whether to display the residue as a ribbon/pipe/plank. Boolean value.'''
    ribbon_hide_backbone = c_property('residue_ribbon_hide_backbone', npy_bool)
    '''Whether a ribbon automatically hides the residue backbone atoms. Boolean value.'''
    ribbon_color = c_property('residue_ribbon_color', uint8, 4)
    '''Ribbon color RGBA length 4 numpy uint8 array.'''
    ribbon_style = c_property('residue_ribbon_style', int32)
    '''Whether the residue is displayed as a ribbon or a pipe/plank. Integer value.'''
    RIBBON = 0
    '''Ribbon style = ribbon.'''
    PIPE = 1
    '''Ribbon style = pipe/plank.'''
    ribbon_adjust = c_property('residue_ribbon_adjust', float32)
    '''Smoothness adjustment factor (no adjustment = 0 <= factor <= 1 = idealized).'''
    name = c_property('residue_name', string, read_only = True)
    '''Residue name. Maximum length 4 characters. Read only.'''
    num_atoms = c_property('residue_num_atoms', size_t, read_only = True)
    '''Number of atoms belonging to the residue. Read only.'''
    number = c_property('residue_number', int32, read_only = True)
    '''Integer sequence position number as defined in the input data file. Read only.'''
    principal_atom = c_property('residue_principal_atom', cptr, astype = _atom_or_none, read_only=True)
    '''The 'chain trace' :class:`.Atom`\\ , if any.

    Normally returns the C4' from a nucleic acid since that is always present,
    but in the case of a P-only trace it returns the P.'''
    str = c_property('residue_str', string, read_only = True)
    '''
    String including residue's name, sequence position, and chain ID in a readable
    form. Read only.
    '''
    structure = c_property('residue_structure', cptr, astype = _atomic_structure, read_only = True)
    ''':class:`.AtomicStructure` that this residue belongs too. Read only.'''

    # TODO: Currently no C++ method to get Chain

    def add_atom(self, atom):
        '''Add the specified :class:`.Atom` to this residue.
        An atom can only belong to one residue, and all atoms
        must belong to a residue.'''
        f = c_function('residue_add_atom', args = (ctypes.c_void_p, ctypes.c_void_p))
        f(self._c_pointer, atom._c_pointer)

# -----------------------------------------------------------------------------
#
class Sequence:
    '''
    A polymeric sequence.  Offers string-like interface.
    '''

    def __init__(self, seq_pointer):
        set_c_pointer(self, seq_pointer)

# -----------------------------------------------------------------------------
#
class Chain(Sequence):
    '''
    A single polymer chain such as a protein, DNA or RNA strand.
    A chain has a sequence associated with it.  A chain may have breaks.
    Chain objects are not always equivalent to Protein Databank chains.

    TODO: C++ sequence object is currently not available in Python.
    '''
    def __init__(self, chain_pointer):
        super().__init__(chain_pointer)

    chain_id = c_property('chain_chain_id', string, read_only = True)
    '''Chain identifier. Limited to 4 characters. Read only string.'''
    structure = c_property('chain_structure', cptr, astype = _atomic_structure, read_only = True)
    ''':class:`.AtomicStructure` that this chain belongs too. Read only.'''
    existing_residues = c_property('chain_residues', cptr, 'num_residues', astype = _non_null_residues, read_only = True)
    ''':class:`.Residues` collection containing the residues of this chain with existing structure, in order. Read only.'''
    num_existing_residues = c_property('chain_num_existing_residues', size_t, read_only = True)
    '''Number of residues in this chain with existing structure. Read only.'''

    residues = c_property('chain_residues', cptr, 'num_residues', astype = _residues_or_nones, read_only = True)
    '''List containing the residues of this chain in order. Residues with no structure will be None. Read only.'''
    num_residues = c_property('chain_num_residues', size_t, read_only = True)
    '''Number of residues belonging to this chain, including those without structure. Read only.'''

# -----------------------------------------------------------------------------
#
class AtomicStructureData:
    '''
    This is a base class of :class:`.AtomicStructure`.
    This base class manages the atomic data while the
    derived class handles the graphical 3-dimensional rendering using OpenGL.
    '''
    def __init__(self, mol_pointer=None, logger=None, restore_data=None):
        if mol_pointer is None:
            # Create a new atomic structure
            mol_pointer = c_function('structure_new', args = (ctypes.py_object,), ret = ctypes.c_void_p)(logger)
        set_c_pointer(self, mol_pointer)

        if restore_data:
            '''Restore from session info'''
            self._ses_call("restore_setup")
            session, version, data = restore_data
            ints, floats, misc = data
            f = c_function('structure_session_restore',
                    args = (ctypes.c_void_p, ctypes.c_int,
                            ctypes.py_object, ctypes.py_object, ctypes.py_object))
            f(self._c_pointer, version, ints, floats, misc)
            session.triggers.add_handler("end restore session", self._ses_restore_teardown)

    def delete(self):
        '''Deletes the C++ data for this atomic structure.'''
        c_function('structure_delete', args = (ctypes.c_void_p,))(self._c_pointer)

    atoms = c_property('structure_atoms', cptr, 'num_atoms', astype = _atoms, read_only = True)
    ''':class:`.Atoms` collection containing all atoms of the structure.'''
    bonds = c_property('structure_bonds', cptr, 'num_bonds', astype = _bonds, read_only = True)
    ''':class:`.Bonds` collection containing all bonds of the structure.'''
    chains = c_property('structure_chains', cptr, 'num_chains', astype = _chains, read_only = True)
    ''':class:`.Chains` collection containing all chains of the structure.'''
    name = c_property('structure_name', string)
    '''Structure name, a string.'''
    num_atoms = c_property('structure_num_atoms', size_t, read_only = True)
    '''Number of atoms in structure. Read only.'''
    num_bonds = c_property('structure_num_bonds', size_t, read_only = True)
    '''Number of bonds in structure. Read only.'''
    num_coord_sets = c_property('structure_num_coord_sets', size_t, read_only = True)
    '''Number of coordinate sets in structure. Read only.'''
    num_chains = c_property('structure_num_chains', size_t, read_only = True)
    '''Number of chains structure. Read only.'''
    num_residues = c_property('structure_num_residues', size_t, read_only = True)
    '''Number of residues structure. Read only.'''
    residues = c_property('structure_residues', cptr, 'num_residues', astype = _residues, read_only = True)
    ''':class:`.Residues` collection containing the residues of this structure. Read only.'''
    pbg_map = c_property('structure_pbg_map', pyobject, astype = _pseudobond_group_map, read_only = True)
    '''Dictionary mapping name to :class:`.PseudobondGroup` for pseudobond groups
    belonging to this structure. Read only.'''
    metadata = c_property('metadata', pyobject, read_only = True)
    '''Dictionary with metadata. Read only.'''
    ribbon_tether_scale = c_property('structure_ribbon_tether_scale', float32)
    '''Ribbon tether thickness scale factor (1.0 = match displayed atom radius, 0=invisible).'''
    ribbon_tether_shape = c_property('structure_ribbon_tether_shape', int32)
    '''Ribbon tether shape. Integer value.'''
    ribbon_show_spine = c_property('structure_ribbon_show_spine', npy_bool)
    '''Display ribbon spine. Boolean.'''
    ribbon_display_count = c_property('structure_ribbon_display_count', int32, read_only = True)
    '''Return number of residues with ribbon display set. Integer.'''
    TETHER_CONE = 0
    TETHER_REVERSE_CONE = 1
    TETHER_CYLINDER = 2
    ribbon_tether_sides = c_property('structure_ribbon_tether_sides', int32)
    '''Number of sides for ribbon tether. Integer value.'''
    ribbon_tether_opacity = c_property('structure_ribbon_tether_opacity', float32)
    '''Ribbon tether opacity scale factor (relative to the atom).'''

    def _copy(self):
        f = c_function('structure_copy', args = (ctypes.c_void_p,), ret = ctypes.c_void_p)
        p = f(self._c_pointer)
        return p
        
    def new_atom(self, atom_name, element_name):
        '''Create a new :class:`.Atom` object. It must be added to a :class:`.Residue` object
        belonging to this structure before being used.'''
        f = c_function('structure_new_atom',
                       args = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p),
                       ret = ctypes.c_void_p)
        ap = f(self._c_pointer, atom_name.encode('utf-8'), element_name.encode('utf-8'))
        return object_map(ap, Atom)

    def new_bond(self, atom1, atom2):
        '''Create a new :class:`.Bond` joining two :class:`Atom` objects.'''
        f = c_function('structure_new_bond',
                       args = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p),
                       ret = ctypes.c_void_p)
        bp = f(self._c_pointer, atom1._c_pointer, atom2._c_pointer)
        return object_map(bp, Bond)

    def new_residue(self, residue_name, chain_id, pos):
        '''Create a new :class:`.Residue`.'''
        f = c_function('structure_new_residue',
                       args = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int),
                       ret = ctypes.c_void_p)
        rp = f(self._c_pointer, residue_name.encode('utf-8'), chain_id.encode('utf-8'), pos)
        return object_map(rp, Residue)

    def polymers(self, consider_missing_structure = True, consider_chains_ids = True):
        '''Return a tuple of :class:`.Residues` objects each containing residues for one polymer.
        Arguments control whether a single polymer can span missing residues or differing chain identifiers.'''
        f = c_function('structure_polymers',
                       args = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int),
                       ret = ctypes.py_object)
        resarrays = f(self._c_pointer, consider_missing_structure, consider_chains_ids)
        from .molarray import Residues
        return tuple(Residues(ra) for ra in resarrays)

    def pseudobond_group(self, name, create_type = "normal"):
        '''Get or create a :class:`.PseudobondGroup` belonging to this structure.'''
        if create_type is None:
            create_arg = 0
        elif create_type == "normal":
            create_arg = 1
        else:  # per-coordset
            create_arg = 2
        f = c_function('structure_pseudobond_group',
                       args = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int),
                       ret = ctypes.c_void_p)
        pbg = f(self._c_pointer, name.encode('utf-8'), create_arg)
        from .pbgroup import PseudobondGroup
        return object_map(pbg, PseudobondGroup)

    def restore_snapshot_init(self, session, tool_info, version, data):
        AtomicStructureData.__init__(self, logger=session.logger,
            restore_data=(session, version, data))

    def session_atom_to_id(self, ptr):
        '''Map Atom pointer to session ID'''
        f = c_function('structure_session_atom_to_id',
                    args = (ctypes.c_void_p, ctypes.c_void_p), ret = size_t)
        return f(self._c_pointer, ptr)

    def session_residue_to_id(self, ptr):
        '''Map Residue pointer to session ID'''
        f = c_function('structure_session_residue_to_id',
                    args = (ctypes.c_void_p, ctypes.c_void_p), ret = size_t)
        return f(self._c_pointer, ptr)

    def session_id_to_atom(self, i):
        '''Map sessionID to Atom pointer'''
        f = c_function('structure_session_id_to_atom',
                    args = (ctypes.c_void_p, ctypes.c_size_t), ret = ctypes.c_void_p)
        return f(self._c_pointer, i)

    def set_color(self, rgba):
        '''Set color of atoms, bonds, and residues'''
        f = c_function('set_structure_color',
                    args = (ctypes.c_void_p, ctypes.c_void_p))
        return f(self._c_pointer, pointer(rgba))

    def take_snapshot(self, session, flags):
        '''Gather session info; return version number'''
        f = c_function('structure_session_info',
                    args = (ctypes.c_void_p, ctypes.py_object, ctypes.py_object,
                        ctypes.py_object),
                    ret = ctypes.c_int)
        ints = []
        floats = []
        misc = []
        return f(self._c_pointer, ints, floats, misc), (ints, floats, misc)

    def _ses_call(self, func_qual):
        f = c_function('structure_session_' + func_qual, args=(ctypes.c_void_p,))
        f(self._c_pointer)

    def _ses_restore_teardown(self, *args):
        self._ses_call("restore_teardown")
        from ..triggerset import DEREGISTER
        return DEREGISTER

    def _start_change_tracking(self, change_tracker):
        f = c_function('structure_start_change_tracking',
                args = (ctypes.c_void_p, ctypes.c_void_p))
        f(self._c_pointer, change_tracker._c_pointer)

    # Graphics changed flags used by rendering code.  Private.
    _gc_color = c_property('structure_gc_color', npy_bool)
    _gc_select = c_property('structure_gc_select', npy_bool)
    _gc_shape = c_property('structure_gc_shape', npy_bool)
    _gc_ribbon = c_property('structure_gc_ribbon', npy_bool)

# -----------------------------------------------------------------------------
#
class ChangeTracker:
    '''Per-session singleton change tracker keeps track of all
    atomic data changes'''

    def __init__(self):
        f = c_function('change_tracker_create', args = (), ret = ctypes.c_void_p)
        set_c_pointer(self, f())

    def add_modified(self, modded, reason):
        f = c_function('change_tracker_add_modified',
            args = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_char_p))
        from .molarray import Collection
        if isinstance(modded, Collection):
            class_num = self._class_to_int(modded.object_class)
            for ptr in modded.pointers:
                f(self._c_pointer, class_num, ptr, reason.encode('utf-8'))
        else:
            f(self._c_pointer, self._class_to_int(modded.__class__), modded._c_pointer,
                reason.encode('utf-8'))
    @property
    def changed(self):
        f = c_function('change_tracker_changed', args = (ctypes.c_void_p,), ret = npy_bool)
        return f(self._c_pointer)

    @property
    def changes(self):
        f = c_function('change_tracker_changes', args = (ctypes.c_void_p,),
            ret = ctypes.py_object)
        data = f(self._c_pointer)
        class Changes:
            def __init__(self, created, modified, reasons, total_deleted):
                self.created = created
                self.modified = modified
                self.reasons = reasons
                self.total_deleted = total_deleted
        final_changes = {}
        for k, v in data.items():
            created_ptrs, mod_ptrs, reasons, tot_del = v
            temp_ns = {}
            # can't effectively use locals() as the third argument for some
            # obscure Python 3 reason
            exec("from .molarray import {}s as collection".format(k), globals(), temp_ns)
            collection = temp_ns['collection']
            fc_key = k[:-4] if k.endswith("Data") else k
            final_changes[fc_key] = Changes(collection(created_ptrs),
                collection(mod_ptrs), reasons, tot_del)
        return final_changes

    def clear(self):
        f = c_function('change_tracker_clear', args = (ctypes.c_void_p,))
        f(self._c_pointer)

    def _class_to_int(self, klass):
        # has to tightly coordinate wih change_track_add_modified
        if klass.__name__ == "Atom":
            return 0
        if klass.__name__ == "Bond":
            return 1
        if klass.__name__ == "Pseudobond":
            return 2
        if klass.__name__ == "Residue":
            return 3
        if klass.__name__ == "Chain":
            return 4
        if klass.__name__ == "AtomicStructure":
            return 5
        if klass.__name__ == "PseudobondGroup":
            return 6
        raise AssertionError("Unknown class for change tracking")

# -----------------------------------------------------------------------------
#
class Element:
    '''A chemical element having a name, number, mass, and other physical properties.'''
    def __init__(self, element_pointer):
        set_c_pointer(self, element_pointer)

    name = c_property('element_name', string, read_only = True)
    '''Element name, for example C for carbon. Read only.'''
    number = c_property('element_number', uint8, read_only = True)
    '''Element atomic number, for example 6 for carbon. Read only.'''
    mass = c_property('element_mass', float32, read_only = True)
    '''Element atomic mass,
    taken from http://en.wikipedia.org/wiki/List_of_elements_by_atomic_weight.
    Read only.'''
    is_alkali_metal = c_property('element_is_alkali_metal', npy_bool, read_only = True)
    '''Is atom an alkali metal. Read only.'''
    is_halogen = c_property('element_is_halogen', npy_bool, read_only = True)
    '''Is atom a halogen. Read only.'''
    is_metal = c_property('element_is_metal', npy_bool, read_only = True)
    '''Is atom a metal. Read only.'''
    is_noble_gas = c_property('element_is_noble_gas', npy_bool, read_only = True)
    '''Is atom a noble_gas. Read only.'''
    valence = c_property('element_valence', uint8, read_only = True)
    '''Element valence number, for example 7 for chlorine. Read only.'''

    def get_element(name_or_number):
        '''Get the Element that corresponds to an atomic name or number'''
        if type(name_or_number) == type(1):
            f = c_function('element_number_get_element', args = (ctypes.c_int,), ret = ctypes.c_void_p)
        elif type(name_or_number) == type(""):
            f = c_function('element_name_get_element', args = (ctypes.c_char_p,), ret = ctypes.c_void_p)
        else:
            raise ValueError("'get_element' arg must be string or int")
        return _element(f(name_or_number))

# -----------------------------------------------------------------------------
#
from collections import namedtuple
ExtrudeValue = namedtuple("ExtrudeValue", ["vertices", "normals",
                                           "triangles", "colors",
                                           "front_band", "back_band"])

class RibbonXSection:
    '''
    A cross section that can extrude ribbons when given the
    required control points, tangents, normals and colors.
    '''
    def __init__(self, coords, coords2=None,
                 normals=None, normals2=None, faceted=False):
        f = c_function('rxsection_new',
                       args = (ctypes.py_object,        # coords
                               ctypes.py_object,        # coords2
                               ctypes.py_object,        # normals
                               ctypes.py_object,        # normals2
                               ctypes.c_bool),          # faceted
                               ret = ctypes.c_void_p)   # pointer to C++ instance
        xs_pointer = f(coords, coords2, normals, normals2, faceted)
        set_c_pointer(self, xs_pointer)

    def delete(self):
        '''Deletes the C++ data for this atomic structure.'''
        c_function('rxsection_delete', args = (ctypes.c_void_p,))(self._c_pointer)

    def extrude(self, centers, tangents, normals, color,
                cap_front, cap_back, offset):
        '''Return the points, normals and triangles for a ribbon.'''
        f = c_function('rxsection_extrude',
                       args = (ctypes.c_void_p,     # self
                               ctypes.py_object,    # centers
                               ctypes.py_object,    # tangents
                               ctypes.py_object,    # normals
                               ctypes.py_object,    # color
                               ctypes.c_bool,       # cap_front
                               ctypes.c_bool,       # cap_back
                               ctypes.c_int),       # offset
                       ret = ctypes.py_object)      # tuple
        t = f(self._c_pointer, centers, tangents, normals, color,
              cap_front, cap_back, offset)
        if t is not None:
            t = ExtrudeValue(*t)
        return t

    def blend(self, back_band, front_band):
        '''Return the triangles blending front and back halves of ribbon.'''
        f = c_function('rxsection_blend',
                       args = (ctypes.c_void_p,     # self
                               ctypes.py_object,    # back_band
                               ctypes.py_object),    # front_band
                       ret = ctypes.py_object)      # tuple
        t = f(self._c_pointer, back_band, front_band)
        return t


# -----------------------------------------------------------------------------
#
_object_map = {}	# Map C++ pointer to Python object
def object_map(p, object_type):
    global _object_map
    o = _object_map.get(p, None)
    if o is None:
        _object_map[p] = o = object_type(p)
    return o

def add_to_object_map(object):
    _object_map[object._c_pointer.value] = object

def register_object_map_deletion_handler(omap):
    # When a C++ object such as an Atom is deleted the pointer is removed
    # from the object map if it exists and the Python object has its _c_pointer
    # attribute deleted.
    f = c_function('object_map_deletion_handler', args = [ctypes.c_void_p], ret = ctypes.c_void_p)
    p = ctypes.c_void_p(id(omap))
    global _omd_handler
    _omd_handler = Object_Map_Deletion_Handler(f(p))

_omd_handler = None
class Object_Map_Deletion_Handler:
    def __init__(self, h):
        self.h = h
        self.delete_handler = c_function('delete_object_map_deletion_handler', args = [ctypes.c_void_p])
    def __del__(self):
        # Make sure object map deletion handler is removed before Python exits
        # so later C++ deletes don't cause segfault on exit.
        self.delete_handler(self.h)

register_object_map_deletion_handler(_object_map)

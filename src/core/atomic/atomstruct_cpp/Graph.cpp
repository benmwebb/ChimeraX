// vi: set expandtab ts=4 sw=4:
#include <algorithm>
#include <set>

#include <logger/logger.h>
#include <pysupport/convert.h>
#include <pythonarray.h>

#include "Atom.h"
#include "Bond.h"
#include "CoordSet.h"
#include "destruct.h"
#include "Graph.h"
#include "PBGroup.h"
#include "Pseudobond.h"
#include "Residue.h"

namespace atomstruct {

const char*  Graph::PBG_METAL_COORDINATION = "metal coordination bonds";
const char*  Graph::PBG_MISSING_STRUCTURE = "missing structure";
const char*  Graph::PBG_HYDROGEN_BONDS = "hydrogen bonds";

Graph::Graph(PyObject* logger):
    _active_coord_set(NULL), _chains(nullptr),
    _change_tracker(DiscardingChangeTracker::discarding_change_tracker()),
    _idatm_valid(false), _logger(logger), _name("unknown AtomicStructure/Graph"),
    _pb_mgr(this), _polymers_computed(false), _recompute_rings(true),
    _structure_cats_dirty(true),
    asterisks_translated(false), is_traj(false),
    lower_case_chains(false), pdb_version(0)
{
    change_tracker()->add_created(this);
}

Graph::~Graph() {
    // assign to variable so that it lives to end of destructor
    auto du = DestructionUser(this);
    change_tracker()->add_deleted(this);
    for (auto b: _bonds)
        delete b;
    for (auto a: _atoms)
        delete a;
    if (_chains != nullptr) {
        for (auto ch: *_chains)
            ch->clear_residues();
        // don't delete the actual chains -- they may be being
        // used as Sequences and the Python layer will delete 
        // them (as sequences) as appropriate
        delete _chains;
    }
    for (auto r: _residues)
        delete r;
    for (auto cs: _coord_sets)
        delete cs;
}

std::map<Residue *, char>
Graph::best_alt_locs() const
{
    // check the common case of all blank alt locs first...
    bool all_blank = true;
    const Atoms& as = atoms();
    for (auto ai = as.begin(); ai != as.end(); ++ai) {
        if (!(*ai)->_alt_loc_map.empty()) {
            all_blank = false;
            break;
        }
    }
    std::map<Residue *, char> best_locs;
    if (all_blank) {
        return best_locs;
    }

    // go through the residues and collate a group of residues with
    //   related alt locs
    // use the alt loc with the highest average occupancy; if tied,
    //  the lowest bfactors; if tied, first alphabetically
    std::set<Residue *> seen;
    for (auto ri = _residues.begin(); ri != _residues.end(); ++ri) {
        Residue *r = *ri;
        if (seen.find(r) != seen.end())
            continue;
        seen.insert(r);
        std::set<Residue *> res_group;
        std::set<char> alt_loc_set;
        for (auto ai = r->_atoms.begin(); ai != r->_atoms.end(); ++ai) {
            Atom *a = *ai;
            alt_loc_set = a->alt_locs();
            if (!alt_loc_set.empty())
                break;
        }
        // if residue has no altlocs, skip it
        if (alt_loc_set.empty())
            continue;
        // for this residue and neighbors linked through alt loc,
        // collate occupancy/bfactor info
        res_group.insert(r);
        std::vector<Residue *> todo;
        todo.push_back(r);
        std::map<char, int> occurances;
        std::map<char, float> occupancies, bfactors;
        while (!todo.empty()) {
            Residue *cr = todo.back();
            todo.pop_back();
            for (auto ai = cr->_atoms.begin(); ai != cr->_atoms.end(); ++ai) {
                Atom *a = *ai;
                bool check_neighbors = true;
                for (auto alsi = alt_loc_set.begin(); alsi != alt_loc_set.end();
                ++alsi) {
                    char alt_loc = *alsi;
                    if (!a->has_alt_loc(alt_loc)) {
                        check_neighbors = false;
                        break;
                    }
                    occurances[alt_loc] += 1;
                    Atom::_Alt_loc_info info = a->_alt_loc_map[alt_loc];
                    occupancies[alt_loc] += info.occupancy;
                    bfactors[alt_loc] += info.bfactor;
                }
                if (check_neighbors) {
                    for (auto nb: a->neighbors()) {
                        Residue *nr = nb->residue();
                        if (nr != cr && nb->alt_locs() == alt_loc_set
                        && seen.find(nr) == seen.end()) {
                            seen.insert(nr);
                            todo.push_back(nr);
                            res_group.insert(nr);
                        }
                    }
                }
            }
        }
        // go through the occupancy/bfactor info and decide on
        // the best alt loc
        char best_loc = '\0';
        std::vector<char> alphabetic_alt_locs(alt_loc_set.begin(),
            alt_loc_set.end());
        std::sort(alphabetic_alt_locs.begin(), alphabetic_alt_locs.end());
        float best_occupancies = 0.0, best_bfactors = 0.0;
        for (auto ali = alphabetic_alt_locs.begin();
        ali != alphabetic_alt_locs.end(); ++ali) {
            char al = *ali;
            bool is_best = best_loc == '\0';
            float occ = occupancies[al] / occurances[al];
            if (!is_best) {
                if (occ > best_occupancies)
                    is_best = true;
                else if (occ < best_occupancies)
                    continue;
            }
            float bf = bfactors[al] / occurances[al];
            if (!is_best) {
                if (bf < best_bfactors)
                    is_best = true;
                else if (bf < best_bfactors)
                    continue;
            }
            if (is_best) {
                best_loc = al;
                best_occupancies = occ;
                best_bfactors = bf;
            }
        }
        // note the best alt loc for these residues in the map
        for (auto rgi = res_group.begin(); rgi != res_group.end(); ++rgi) {
            best_locs[*rgi] = best_loc;
        }
    }

    return best_locs;
}

void
Graph::bonded_groups(std::vector<std::vector<Atom*>>* groups,
    bool consider_missing_structure) const
{
    // find connected atomic structures, considering missing-structure pseudobonds
    std::map<Atom*, std::vector<Atom*>> pb_connections;
    if (consider_missing_structure) {
        auto pbg = const_cast<Graph*>(this)->_pb_mgr.get_group(PBG_MISSING_STRUCTURE,
            AS_PBManager::GRP_NONE);
        if (pbg != nullptr) {
            for (auto& pb: pbg->pseudobonds()) {
                auto a1 = pb->atoms()[0];
                auto a2 = pb->atoms()[1];
                pb_connections[a1].push_back(a2);
                pb_connections[a2].push_back(a1);
            }
        }
    }
    std::set<Atom*> seen;
    for (auto a: atoms()) {
        if (seen.find(a) != seen.end())
            continue;
        groups->emplace_back();
        std::vector<Atom*>& bonded = groups->back();
        std::set<Atom*> pending;
        pending.insert(a);
        while (pending.size() > 0) {
            Atom* pa = *(pending.begin());
            pending.erase(pa);
            if (seen.find(pa) != seen.end())
                continue;
            seen.insert(pa);
            bonded.push_back(pa);
            if (pb_connections.find(pa) != pb_connections.end()) {
                for (auto conn: pb_connections[pa]) {
                    pending.insert(conn);
                }
            }
            for (auto nb: pa->neighbors())
                pending.insert(nb);
        }
    }
}

void Graph::_copy(Graph* g) const
{
    g->set_name(name());

    for (auto h = metadata.begin() ; h != metadata.end() ; ++h)
        g->metadata[h->first] = h->second;
    g->pdb_version = pdb_version;

    std::map<Residue*, Residue*> rmap;
    for (auto ri = residues().begin() ; ri != residues().end() ; ++ri) {
        Residue* r = *ri;
        Residue* cr = g->new_residue(r->name(), r->chain_id(), r->position(), r->insertion_code());
        cr->set_ribbon_display(r->ribbon_display());
        cr->set_ribbon_color(r->ribbon_color());
        cr->set_is_helix(r->is_helix());
        cr->set_is_sheet(r->is_sheet());
        cr->set_is_het(r->is_het());
        rmap[r] = cr;
    }

    std::map<Atom*, Atom*> amap;
    for (auto ai = atoms().begin() ; ai != atoms().end() ; ++ai) {
        Atom* a = *ai;
        Atom* ca = g->new_atom(a->name(), a->element());
        Residue *cr = rmap[a->residue()];
        cr->add_atom(ca);	// Must set residue before setting alt locs
        std::set<char> alocs = a->alt_locs();
        if (alocs.empty()) {
            ca->set_coord(a->coord());
            ca->set_bfactor(a->bfactor());
            ca->set_occupancy(a->occupancy());
        } else {
            char aloc = a->alt_loc();	// Remember original alt loc.
            for (auto ali = alocs.begin() ; ali != alocs.end() ; ++ali) {
                char al = *ali;
                a->set_alt_loc(al);
                ca->set_alt_loc(al, true);
                ca->set_coord(a->coord());
                ca->set_bfactor(a->bfactor());
                ca->set_occupancy(a->occupancy());
            }
            a->set_alt_loc(aloc);	// Restore original alt loc.
            ca->set_alt_loc(aloc);
        }
        ca->set_draw_mode(a->draw_mode());
        ca->set_radius(a->radius());
        ca->set_color(a->color());
        ca->set_display(a->display());
        amap[a] = ca;
    }

    for (auto bi = bonds().begin() ; bi != bonds().end() ; ++bi) {
        Bond* b = *bi;
        const Bond::Atoms& a = b->atoms();
        Bond* cb = g->new_bond(amap[a[0]], amap[a[1]]);
        cb->set_display(b->display());
        cb->set_color(b->color());
        cb->set_halfbond(b->halfbond());
        cb->set_radius(b->radius());
    }
}

Graph*
Graph::copy() const
{
    Graph* g = new Graph(_logger);
    _copy(g);
    return g;
}

void
Graph::_delete_atom(Atom* a)
{
    auto db = DestructionBatcher(this);
    if (a->element().number() == 1)
        --_num_hyds;
    for (auto b: a->bonds())
        b->other_atom(a)->remove_bond(b);
    typename Atoms::iterator i = std::find_if(_atoms.begin(), _atoms.end(),
        [&a](Atom* ua) { return ua == a; });
    _atoms.erase(i);
    set_gc_shape();
    delete a;
}

void
Graph::delete_atom(Atom* a)
{
    if (a->structure() != this) {
        logger::error(_logger, "Atom ", a->residue()->str(), " ", a->name(),
            " does not belong to the structure that it's being deleted from.");
        throw std::invalid_argument("delete_atom called for Atom not in AtomicStructure/Graph");
    }
    if (atoms().size() == 1) {
        delete this;
        return;
    }
    auto r = a->residue();
    if (r->atoms().size() == 1) {
        _delete_residue(r, std::find(_residues.begin(), _residues.end(), r));
        return;
    }
    _delete_atom(a);
}

void
Graph::_delete_atoms(const std::set<Atom*>& atoms)
{
    if (atoms.size() == _atoms.size()) {
        delete this;
        return;
    }
    std::map<Residue*, std::vector<Atom*>> res_del_atoms;
    for (auto a: atoms) {
        res_del_atoms[a->residue()].push_back(a);
    }
    std::set<Residue*> res_removals;
    for (auto& r_atoms: res_del_atoms) {
        auto r = r_atoms.first;
        auto& dels = r_atoms.second;
        if (dels.size() == r->atoms().size()) {
            res_removals.insert(r);
        } else {
            for (auto a: dels)
                r->remove_atom(a);
        }
    }
    if (res_removals.size() > 0) {
        // remove_if apparently doesn't guarantee that the _back_ of
        // the vector is all the removed items -- there could be second
        // copies of the retained values in there, so do the delete as
        // part of the lambda rather than in a separate pass through
        // the end of the vector
        auto new_end = std::remove_if(_residues.begin(), _residues.end(),
            [&res_removals](Residue* r) {
                bool rm = res_removals.find(r) != res_removals.end();
                if (rm) delete r; return rm;
            });
        _residues.erase(new_end, _residues.end());
    }
    // remove_if doesn't swap the removed items into the end of the vector,
    // so can't just go through the tail of the vector and delete things,
    // need to delete them as part of the lambda
    auto new_a_end = std::remove_if(_atoms.begin(), _atoms.end(),
        [&atoms](Atom* a) { 
            bool rm = atoms.find(a) != atoms.end();
            if (rm) delete a; return rm;
        });
    _atoms.erase(new_a_end, _atoms.end());

    for (auto a: _atoms) {
        std::vector<Bond*> removals;
        for (auto b: a->bonds()) {
            if (atoms.find(b->other_atom(a)) != atoms.end())
                removals.push_back(b);
        }
        for (auto b: removals)
            a->remove_bond(b);
    }

    auto new_b_end = std::remove_if(_bonds.begin(), _bonds.end(),
        [&atoms](Bond* b) {
            bool rm = atoms.find(b->atoms()[0]) != atoms.end()
            || atoms.find(b->atoms()[1]) != atoms.end();
            if (rm) delete b; return rm;
        });
    _bonds.erase(new_b_end, _bonds.end());
    set_gc_shape();
}

void
Graph::delete_atoms(const std::vector<Atom*>& atoms)
{
    auto db = DestructionBatcher(this);
    // construct set first to ensure uniqueness before tests...
    auto del_atoms_set = std::set<Atom*>(atoms.begin(), atoms.end());
    _delete_atoms(del_atoms_set);
}

void
Graph::delete_bond(Bond *b)
{
    typename Bonds::iterator i = std::find_if(_bonds.begin(), _bonds.end(),
        [&b](Bond* ub) { return ub == b; });
    if (i == _bonds.end())
        throw std::invalid_argument("delete_bond called for Bond not in Graph");
    auto db = DestructionBatcher(this);
    for (auto a: b->atoms())
        a->remove_bond(b);
    _bonds.erase(i);
    set_gc_shape();
    _structure_cats_dirty = true;
    delete b;
}

void
Graph::_delete_residue(Residue* r, const Graph::Residues::iterator& ri)
{
    auto db = DestructionBatcher(r);
    if (r->chain() != nullptr) {
        r->chain()->remove_residue(r);
        set_gc_ribbon();
    }
    for (auto a: r->atoms()) {
        _delete_atom(a);
    }
    _residues.erase(ri);
    delete r;
}

void
Graph::delete_residue(Residue* r)
{
    auto ri = std::find(_residues.begin(), _residues.end(), r);
    if (ri == _residues.end()) {
        logger::error(_logger, "Residue ", r->str(),
            " does not belong to the structure that it's being deleted from.");
        return;
    }
    if (residues().size() == 1) {
        delete this;
        return;
    }
    _delete_residue(r, ri);
}

CoordSet *
Graph::find_coord_set(int id) const
{
    for (auto csi = _coord_sets.begin(); csi != _coord_sets.end(); ++csi) {
        if ((*csi)->id() == id)
            return *csi;
    }

    return nullptr;
}

Residue *
Graph::find_residue(const ChainID &chain_id, int pos, char insert) const
{
    for (auto ri = _residues.begin(); ri != _residues.end(); ++ri) {
        Residue *r = *ri;
        if (r->position() == pos && r->chain_id() == chain_id
        && r->insertion_code() == insert)
            return r;
    }
    return nullptr;
}

Residue *
Graph::find_residue(const ChainID& chain_id, int pos, char insert, ResName& name) const
{
    for (auto ri = _residues.begin(); ri != _residues.end(); ++ri) {
        Residue *r = *ri;
        if (r->position() == pos && r->name() == name && r->chain_id() == chain_id
        && r->insertion_code() == insert)
            return r;
    }
    return nullptr;
}

void
Graph::make_chains() const
{
    // since Graphs don't have sequences, they don't have chains
    if (_chains != nullptr) {
        for (auto c: *_chains)
            delete c;
        delete _chains;
    }

    _chains = new Chains();
}

Atom *
Graph::new_atom(const char* name, const Element& e)
{
    Atom *a = new Atom(this, name, e);
    add_atom(a);
    if (e.number() == 1)
        ++_num_hyds;
    return a;
}

Bond *
Graph::new_bond(Atom *a1, Atom *a2)
{
    Bond *b = new Bond(this, a1, a2);
    b->finish_construction(); // virtual calls work now
    add_bond(b);
    return b;
}

CoordSet *
Graph::new_coord_set()
{
    if (_coord_sets.empty())
        return new_coord_set(0);
    return new_coord_set(_coord_sets.back()->id());
}

static void
_coord_set_insert(Graph::CoordSets &coord_sets, CoordSet* cs, int index)
{
    if (coord_sets.empty() || coord_sets.back()->id() < index) {
        coord_sets.emplace_back(cs);
        return;
    }
    for (auto csi = coord_sets.begin(); csi != coord_sets.end(); ++csi) {
        if (index < (*csi)->id()) {
            coord_sets.insert(csi, cs);
            return;
        } else if (index == (*csi)->id()) {
            delete *csi;
            coord_sets.insert(csi, cs);
            return;
        }
    }
    std::logic_error("CoordSet insertion logic error");
}

CoordSet*
Graph::new_coord_set(int index)
{
    if (!_coord_sets.empty())
        return new_coord_set(index, _coord_sets.back()->coords().size());
    CoordSet* cs = new CoordSet(this, index);
    _coord_set_insert(_coord_sets, cs, index);
    return cs;
}

CoordSet*
Graph::new_coord_set(int index, int size)
{
    CoordSet* cs = new CoordSet(this, index, size);
    _coord_set_insert(_coord_sets, cs, index);
    return cs;
}

Residue*
Graph::new_residue(const ResName& name, const ChainID& chain,
    int pos, char insert, Residue *neighbor, bool after)
{
    if (neighbor == nullptr) {
        _residues.emplace_back(new Residue(this, name, chain, pos, insert));
        return _residues.back();
    }
    auto ri = std::find_if(_residues.begin(), _residues.end(),
                [&neighbor](Residue* vr) { return vr == neighbor; });
    if (ri == _residues.end())
        throw std::out_of_range("Waypoint residue not in residue list");
    if (after)
        ++ri;
    Residue *r = new Residue(this, name, chain, pos, insert);
    _residues.insert(ri, r);
    return r;
}

const Graph::Rings&
Graph::rings(bool cross_residues, unsigned int all_size_threshold,
    std::set<const Residue *>* ignore) const
{
    if (_rings_cached(cross_residues, all_size_threshold, ignore)) {
        return _rings;
    }

    _recompute_rings = false;
    _rings_last_cross_residues = cross_residues;
    _rings_last_all_size_threshold = all_size_threshold;
    _rings_last_ignore = ignore;

    _calculate_rings(cross_residues, all_size_threshold, ignore);

    // clear out ring lists in individual atoms and bonds
    for (auto a: atoms()) {
        a->_rings.clear();
    }
    for (auto b: bonds()) {
        b->_rings.clear();
    }

    // set individual atom/bond ring lists
    for (auto& r: _rings) {
        for (auto a: r.atoms()) {
            a->_rings.push_back(&r);
        }
        for (auto b: r.bonds()) {
            b->_rings.push_back(&r);
        }
    }
    return _rings;
}

bool
Graph::_rings_cached(bool cross_residues, unsigned int all_size_threshold,
    std::set<const Residue *>* ignore) const
{
    return !_recompute_rings && cross_residues == _rings_last_cross_residues
        && all_size_threshold == _rings_last_all_size_threshold
        && ignore == _rings_last_ignore;
}

int
Graph::session_info(PyObject* ints, PyObject* floats, PyObject* misc) const
{
    // The passed-in args need to be empty lists.  This routine will add one object to each
    // list for each of these classes:
    //    AtomicStructure/Graph
    //    Atom
    //    Bond (needs Atoms)
    //    CoordSet (needs Atoms)
    //    PseudobondManager (needs Atoms and CoordSets)
    //    Residue
    //    Chain
    // For the numeric types, the objects will be numpy arrays: one-dimensional for
    // AtomicStructure attributes and two-dimensional for the others.  Except for
    // PseudobondManager; that will be a list of numpy arrays, one per group.  For the misc,
    // The objects will be Python lists, or lists of lists (same scheme as for the arrays),
    // though there may be exceptions (e.g. altloc info).
    //
    // Just let rings get recomputed instead of saving them.  Don't have to set up and
    // tear down a bond map that way (rings are the only thing that needs bond references).

    if (!PyList_Check(ints) || PyList_Size(ints) != 0)
        throw std::invalid_argument("AtomicStructure::session_info: first arg is not an"
            " empty list");
    if (!PyList_Check(floats) || PyList_Size(floats) != 0)
        throw std::invalid_argument("AtomicStructure::session_info: second arg is not an"
            " empty list");
    if (!PyList_Check(misc) || PyList_Size(misc) != 0)
        throw std::invalid_argument("AtomicStructure::session_info: third arg is not an"
            " empty list");

    using pysupport::cchar_to_pystring;
    using pysupport::cvec_of_char_to_pylist;
    using pysupport::cmap_of_chars_to_pydict;

    // AtomicStructure attrs
    int* int_array;
    PyObject* npy_array = python_int_array(SESSION_NUM_INTS(), &int_array);
    *int_array++ = _idatm_valid;
    int x = std::find(_coord_sets.begin(), _coord_sets.end(), _active_coord_set)
        - _coord_sets.begin();
    *int_array++ = x; // can be == size if active coord set is null
    *int_array++ = asterisks_translated;
    *int_array++ = _display;
    *int_array++ = is_traj;
    *int_array++ = lower_case_chains;
    *int_array++ = pdb_version;
    *int_array++ = _ribbon_display_count;
    // pb manager version number remembered later
    if (PyList_Append(ints, npy_array) < 0)
        throw std::runtime_error("Couldn't append to int list");

    float* float_array;
    npy_array = python_float_array(SESSION_NUM_FLOATS(), &float_array);
    *float_array++ = _ball_scale;
    // if you add floats, change the allocation above
    if (PyList_Append(floats, npy_array) < 0)
        throw std::runtime_error("Couldn't append to floats list");

    PyObject* attr_list = PyList_New(SESSION_NUM_MISC());
    if (attr_list == nullptr)
        throw std::runtime_error("Cannot create Python list for misc info");
    if (PyList_Append(misc, attr_list) < 0)
        throw std::runtime_error("Couldn't append to misc list");
    // input_seq_info
    PyList_SET_ITEM(attr_list, 0, cmap_of_chars_to_pydict(_input_seq_info,
        "residue chain ID", "residue name"));
    // name
    PyList_SET_ITEM(attr_list, 1, cchar_to_pystring(_name, "structure name"));
    // input_seq_source
    PyList_SET_ITEM(attr_list, 2, cchar_to_pystring(input_seq_source, "seq info source"));
    // metadata
    PyList_SET_ITEM(attr_list, 3, cmap_of_chars_to_pydict(metadata,
        "metadata key", "metadata value"));

    // atoms
    // We need to remember names and elements ourself for constructing the atoms.
    // Make a list of num_atom+1 items, the first of which will be the list of
    //   names and the remainder of which will be empty lists which will be handed
    //   off individually to the atoms.
    int num_atoms = atoms().size();
    int num_ints = num_atoms; // list of elements
    int num_floats = 0;
    PyObject* atoms_misc = PyList_New(num_atoms+1);
    if (atoms_misc == nullptr)
        throw std::runtime_error("Cannot create Python list for atom misc info");
    if (PyList_Append(misc, atoms_misc) < 0)
        throw std::runtime_error("Couldn't append atom misc list to misc list");
    PyObject* atom_names = PyList_New(num_atoms);
    if (atom_names == nullptr)
        throw std::runtime_error("Cannot create Python list for atom names");
    PyList_SET_ITEM(atoms_misc, 0, atom_names);
    int i = 0;
    for (auto a: atoms()) {
        num_ints += a->session_num_ints();
        num_floats += a->session_num_floats();

        // remember name
        PyList_SET_ITEM(atom_names, i++, cchar_to_pystring(a->name(), "atom name"));
    }
    int* atom_ints;
    PyObject* atom_npy_ints = python_int_array(num_ints, &atom_ints);
    for (auto a: atoms()) {
        *atom_ints++ = a->element().number();
    }
    if (PyList_Append(ints, atom_npy_ints) < 0)
        throw std::runtime_error("Couldn't append atom ints to int list");
    float* atom_floats;
    PyObject* atom_npy_floats = python_float_array(num_floats, &atom_floats);
    if (PyList_Append(floats, atom_npy_floats) < 0)
        throw std::runtime_error("Couldn't append atom floats to float list");
    i = 1;
    for (auto a: atoms()) {
        PyObject* empty_list = PyList_New(0);
        if (empty_list == nullptr)
            throw std::runtime_error("Cannot create Python list for individual atom misc info");
        PyList_SET_ITEM(atoms_misc, i++, empty_list);
        a->session_save(&atom_ints, &atom_floats, empty_list);
    }

    // bonds
    // We need to remember atom indices ourself for constructing the bonds.
    int num_bonds = bonds().size();
    num_ints = 1 + 2 * num_bonds; // to hold the # of bonds, and atom indices
    num_floats = 0;
    num_ints += num_bonds * Bond::session_num_ints();
    num_floats += num_bonds * Bond::session_num_floats();
    PyObject* bonds_misc = PyList_New(0);
    if (bonds_misc == nullptr)
        throw std::runtime_error("Cannot create Python list for bond misc info");
    if (PyList_Append(misc, bonds_misc) < 0)
        throw std::runtime_error("Couldn't append bond misc list to misc list");
    int* bond_ints;
    PyObject* bond_npy_ints = python_int_array(num_ints, &bond_ints);
    *bond_ints++ = num_bonds;
    for (auto b: bonds()) {
        *bond_ints++ = (*session_save_atoms)[b->atoms()[0]];
        *bond_ints++ = (*session_save_atoms)[b->atoms()[1]];
    }
    if (PyList_Append(ints, bond_npy_ints) < 0)
        throw std::runtime_error("Couldn't append bond ints to int list");
    float* bond_floats;
    PyObject* bond_npy_floats = python_float_array(num_floats, &bond_floats);
    if (PyList_Append(floats, bond_npy_floats) < 0)
        throw std::runtime_error("Couldn't append bond floats to float list");
    for (auto b: bonds()) {
        b->session_save(&bond_ints, &bond_floats);
    }

    // coord sets
    int num_cs = coord_sets().size();
    num_ints = 1 + num_cs; // to note the total # of coord sets, and coord set IDs
    num_floats = 0;
    for (auto cs: _coord_sets) {
        num_ints += cs->session_num_ints();
        num_floats += cs->session_num_floats();
    }
    PyObject* cs_misc = PyList_New(0);
    if (cs_misc == nullptr)
        throw std::runtime_error("Cannot create Python list for coord set misc info");
    if (PyList_Append(misc, cs_misc) < 0)
        throw std::runtime_error("Couldn't append coord set misc list to misc list");
    int* cs_ints;
    PyObject* cs_npy_ints = python_int_array(num_ints, &cs_ints);
    *cs_ints++ = num_cs;
    for (auto cs: coord_sets()) {
        *cs_ints++ = cs->id();
    }
    if (PyList_Append(ints, cs_npy_ints) < 0)
        throw std::runtime_error("Couldn't append coord set ints to int list");
    float* cs_floats;
    PyObject* cs_npy_floats = python_float_array(num_floats, &cs_floats);
    if (PyList_Append(floats, cs_npy_floats) < 0)
        throw std::runtime_error("Couldn't append coord set floats to float list");
    for (auto cs: coord_sets()) {
        cs->session_save(&cs_ints, &cs_floats);
    }

    // PseudobondManager groups;
    // main version number needs to go up when manager's
    // version number goes up, so check it
    PyObject* pb_ints;
    PyObject* pb_floats;
    PyObject* pb_misc;
    *int_array = _pb_mgr.session_info(&pb_ints, &pb_floats, &pb_misc);
    if (*int_array++ != 1) {
        throw std::runtime_error("Unexpected version number from pseudobond manager");
    }
    if (PyList_Append(ints, pb_ints) < 0)
        throw std::runtime_error("Couldn't append pseudobond ints to int list");
    if (PyList_Append(floats, pb_floats) < 0)
        throw std::runtime_error("Couldn't append pseudobond floats to float list");
    if (PyList_Append(misc, pb_misc) < 0)
        throw std::runtime_error("Couldn't append pseudobond misc info to misc list");

    // residues
    int num_residues = residues().size();
    num_ints = 2 * num_residues; // to note position and insertion code for constructor
    num_floats = 0;
    for (auto res: _residues) {
        num_ints += res->session_num_ints();
        num_floats += res->session_num_floats();
    }
    PyObject* res_misc = PyList_New(2);
    if (res_misc == nullptr)
        throw std::runtime_error("Cannot create Python list for residue misc info");
    if (PyList_Append(misc, res_misc) < 0)
        throw std::runtime_error("Couldn't append residue misc list to misc list");
    int* res_ints;
    PyObject* res_npy_ints = python_int_array(num_ints, &res_ints);
    if (PyList_Append(ints, res_npy_ints) < 0)
        throw std::runtime_error("Couldn't append residue ints to int list");
    float* res_floats;
    PyObject* res_npy_floats = python_float_array(num_floats, &res_floats);
    if (PyList_Append(floats, res_npy_floats) < 0)
        throw std::runtime_error("Couldn't append residue floats to float list");
    PyObject* py_res_names = PyList_New(num_residues);
    if (py_res_names == nullptr)
        throw std::runtime_error("Cannot create Python list for residue names");
    PyList_SET_ITEM(res_misc, 0, py_res_names);
    PyObject* py_chain_ids = PyList_New(num_residues);
    if (py_chain_ids == nullptr)
        throw std::runtime_error("Cannot create Python list for chain IDs");
    PyList_SET_ITEM(res_misc, 1, py_chain_ids);
    i = 0;
    for (auto res: residues()) {
        // remember res name and chain ID
        PyList_SET_ITEM(py_res_names, i, cchar_to_pystring(res->name(), "residue name"));
        PyList_SET_ITEM(py_chain_ids, i++, cchar_to_pystring(res->chain_id(), "residue chain ID"));
        *res_ints++ = res->position();
        *res_ints++ = res->insertion_code();
        res->session_save(&res_ints, &res_floats);
    }

    // chains
    int num_chains = _chains == nullptr ? -1 : _chains->size();
    num_ints = 1; // for storing num_chains, since len(chain_ids) can't show nullptr
    num_floats = 0;
    if (_chains != nullptr) {
        for (auto ch: *_chains) {
            num_ints += ch->session_num_ints();
            num_floats += ch->session_num_floats();
        }
    }
    // allocate for list of chain IDs
    PyObject* chain_misc = PyList_New(1);
    if (chain_misc == nullptr)
        throw std::runtime_error("Cannot create Python list for chain misc info");
    if (PyList_Append(misc, chain_misc) < 0)
        throw std::runtime_error("Couldn't append chain misc list to misc list");
    PyObject* chain_ids = PyList_New(num_chains);
    if (chain_ids == nullptr)
        throw std::runtime_error("Cannot create Python list for chain IDs");
    PyList_SET_ITEM(chain_misc, 0, chain_ids);
    i = 0;
    if (_chains != nullptr) {
        for (auto ch: *_chains) {
            num_ints += ch->session_num_ints();
            num_floats += ch->session_num_floats();

            // remember chain ID
            PyList_SET_ITEM(chain_ids, i++, cchar_to_pystring(ch->chain_id(), "chain chain ID"));
        }
    }
    int* chain_ints;
    PyObject* chain_npy_ints = python_int_array(num_ints, &chain_ints);
    if (PyList_Append(ints, chain_npy_ints) < 0)
        throw std::runtime_error("Couldn't append chain ints to int list");
    float* chain_floats;
    PyObject* chain_npy_floats = python_float_array(num_floats, &chain_floats);
    if (PyList_Append(floats, chain_npy_floats) < 0)
        throw std::runtime_error("Couldn't append chain floats to float list");
    *chain_ints++ = num_chains;
    if (_chains != nullptr) {
        for (auto ch: *_chains) {
            ch->session_save(&chain_ints, &chain_floats);
        }
    }

    return CURRENT_SESSION_VERSION;  // version number
}

void
Graph::session_restore(int version, PyObject* ints, PyObject* floats, PyObject* misc)
{
    // restore the stuff saved by session_info()

    if (version > CURRENT_SESSION_VERSION)
        throw std::invalid_argument("Don't know how to restore new session data; update your"
            " version of ChimeraX");

    if (!PyList_Check(ints) || PyList_Size(ints) != 7)
        throw std::invalid_argument("AtomicStructure::session_restore: first arg is not a"
            " 7-element list");
    if (!PyList_Check(floats) || PyList_Size(floats) != 7)
        throw std::invalid_argument("AtomicStructure::session_restore: second arg is not a"
            " 7-element list");
    if (!PyList_Check(misc) || PyList_Size(misc) != 7)
        throw std::invalid_argument("AtomicStructure::session_restore: third arg is not a"
            " 7-element list");

    using pysupport::pylist_of_string_to_cvec;
    using pysupport::pystring_to_cchar;

    // AtomicStructure ints
    PyObject* item = PyList_GET_ITEM(ints, 0);
    auto iarray = Numeric_Array();
    if (!array_from_python(item, 1, Numeric_Array::Int, &iarray, false))
        throw std::invalid_argument("AtomicStructure int data is not a one-dimensional"
            " numpy int array");
    if (iarray.size() != SESSION_NUM_INTS(version))
        throw std::invalid_argument("AtomicStructure int array wrong size");
    int* int_array = static_cast<int*>(iarray.values());
    _idatm_valid = *int_array++;
    int active_cs = *int_array++; // have to wait until CoordSets restored to set
    asterisks_translated = *int_array++;
    _display = *int_array++;
    is_traj = *int_array++;
    lower_case_chains = *int_array++;
    pdb_version = *int_array++;
    _ribbon_display_count = *int_array++;
    auto pb_manager_version = *int_array++;
    // if more added, change the array dimension check above

    // AtomicStructure floats
    item = PyList_GET_ITEM(floats, 0);
    auto farray = Numeric_Array();
    if (!array_from_python(item, 1, Numeric_Array::Float, &farray, false))
        throw std::invalid_argument("AtomicStructure float data is not a one-dimensional"
            " numpy float array");
    if (farray.size() != SESSION_NUM_FLOATS(version))
        throw std::invalid_argument("AtomicStructure float array wrong size");
    float* float_array = static_cast<float*>(farray.values());
    _ball_scale = *float_array++;
    // if more added, change the array dimension check above

    // AtomicStructure misc info
    item = PyList_GET_ITEM(misc, 0);
    if (!PyList_Check(item) || PyList_GET_SIZE(item) != SESSION_NUM_MISC(version))
        throw std::invalid_argument("AtomicStructure misc data is not list or is wrong size");
    // input_seq_info
    PyObject* map = PyList_GET_ITEM(item, 0);
    if (!PyDict_Check(map))
        throw std::invalid_argument("input seq info is not a dict!");
    Py_ssize_t index = 0;
    PyObject* py_chain_id;
    PyObject* py_residues;
    _input_seq_info.clear();
    while (PyDict_Next(map, &index, &py_chain_id, &py_residues)) {
        ChainID chain_id = pystring_to_cchar(py_chain_id, "input seq chain ID");
        auto& res_names = _input_seq_info[chain_id];
        pylist_of_string_to_cvec(py_residues, res_names, "chain residue name");
    }
    // name
    _name = pystring_to_cchar(PyList_GET_ITEM(item, 1), "structure name");
    // input_seq_source
    input_seq_source = pystring_to_cchar(PyList_GET_ITEM(item, 2), "structure input seq source");
    // metadata
    map = PyList_GET_ITEM(item, 3);
    if (!PyDict_Check(map))
        throw std::invalid_argument("structure metadata is not a dict!");
    index = 0;
    PyObject* py_hdr_type;
    PyObject* py_headers;
    _input_seq_info.clear();
    while (PyDict_Next(map, &index, &py_hdr_type, &py_headers)) {
        auto hdr_type = pystring_to_cchar(py_hdr_type, "structure metadata key");
        auto& headers = metadata[hdr_type];
        pylist_of_string_to_cvec(py_headers, headers, "structure metadata");
    }

    // atoms
    PyObject* atoms_misc = PyList_GET_ITEM(misc, 1);
    if (!PyList_Check(atoms_misc))
        throw std::invalid_argument("atom misc info is not a list");
    if (PyList_GET_SIZE(atoms_misc) < 1)
        throw std::invalid_argument("atom names missing");
    std::vector<AtomName> atom_names;
    pylist_of_string_to_cvec(PyList_GET_ITEM(atoms_misc, 0), atom_names, "atom name");
    if ((decltype(atom_names)::size_type)(PyList_GET_SIZE(atoms_misc)) != atom_names.size() + 1)
        throw std::invalid_argument("bad atom misc info");
    PyObject* atom_ints = PyList_GET_ITEM(ints, 1);
    iarray = Numeric_Array();
    if (!array_from_python(atom_ints, 1, Numeric_Array::Int, &iarray, false))
        throw std::invalid_argument("Atom int data is not a one-dimensional"
            " numpy int array");
    int_array = static_cast<int*>(iarray.values());
    auto element_ints = int_array;
    int_array += atom_names.size();
    PyObject* atom_floats = PyList_GET_ITEM(floats, 1);
    farray = Numeric_Array();
    if (!array_from_python(atom_floats, 1, Numeric_Array::Float, &farray, false))
        throw std::invalid_argument("Atom float data is not a one-dimensional"
            " numpy float array");
    float_array = static_cast<float*>(farray.values());
    int i = 1; // atom names are in slot zero
    for (auto aname: atom_names) {
        auto a = new_atom(aname, Element::get_element(*element_ints++));
        a->session_restore(version, &int_array, &float_array, PyList_GET_ITEM(atoms_misc, i++));
    }

    // bonds
    PyObject* bond_ints = PyList_GET_ITEM(ints, 2);
    iarray = Numeric_Array();
    if (!array_from_python(bond_ints, 1, Numeric_Array::Int, &iarray, false))
        throw std::invalid_argument("Bond int data is not a one-dimensional"
            " numpy int array");
    int_array = static_cast<int*>(iarray.values());
    auto num_bonds = *int_array++;
    auto bond_index_ints = int_array;
    int_array += 2 * num_bonds;
    PyObject* bond_floats = PyList_GET_ITEM(floats, 2);
    farray = Numeric_Array();
    if (!array_from_python(bond_floats, 1, Numeric_Array::Float, &farray, false))
        throw std::invalid_argument("Bond float data is not a one-dimensional"
            " numpy float array");
    float_array = static_cast<float*>(farray.values());
    for (i = 0; i < num_bonds; ++i) {
        Atom *a1 = atoms()[*bond_index_ints++];
        Atom *a2 = atoms()[*bond_index_ints++];
        auto b = new_bond(a1, a2);
        b->session_restore(version, &int_array, &float_array);
    }

    // coord sets
    PyObject* cs_ints = PyList_GET_ITEM(ints, 3);
    iarray = Numeric_Array();
    if (!array_from_python(cs_ints, 1, Numeric_Array::Int, &iarray, false))
        throw std::invalid_argument("Coord set int data is not a one-dimensional"
            " numpy int array");
    int_array = static_cast<int*>(iarray.values());
    auto num_cs = *int_array++;
    auto cs_id_ints = int_array;
    int_array += num_cs;
    PyObject* cs_floats = PyList_GET_ITEM(floats, 3);
    farray = Numeric_Array();
    if (!array_from_python(cs_floats, 1, Numeric_Array::Float, &farray, false))
        throw std::invalid_argument("Coord set float data is not a one-dimensional"
            " numpy float array");
    float_array = static_cast<float*>(farray.values());
    for (i = 0; i < num_cs; ++i) {
        auto cs = new_coord_set(*cs_id_ints++, atom_names.size());
        cs->session_restore(version, &int_array, &float_array);
    }
    // can now resolve the active coord set
    if ((CoordSets::size_type)active_cs < _coord_sets.size())
        _active_coord_set = _coord_sets[active_cs];
    else
        _active_coord_set = nullptr;

    // PseudobondManager groups;
    PyObject* pb_ints = PyList_GET_ITEM(ints, 4);
    iarray = Numeric_Array();
    if (!array_from_python(pb_ints, 1, Numeric_Array::Int, &iarray, false))
        throw std::invalid_argument("Pseudobond int data is not a one-dimensional"
            " numpy int array");
    int_array = static_cast<int*>(iarray.values());
    PyObject* pb_floats = PyList_GET_ITEM(floats, 4);
    farray = Numeric_Array();
    if (!array_from_python(pb_floats, 1, Numeric_Array::Float, &farray, false))
        throw std::invalid_argument("Pseudobond float data is not a one-dimensional"
            " numpy float array");
    float_array = static_cast<float*>(farray.values());
    _pb_mgr.session_restore(pb_manager_version, &int_array, &float_array, PyList_GET_ITEM(misc, 4));

    // residues
    PyObject* res_misc = PyList_GET_ITEM(misc, 5);
    if (!PyList_Check(res_misc) or PyList_GET_SIZE(res_misc) != 2)
        throw std::invalid_argument("residue misc info is not a two-item list");
    std::vector<ResName> res_names;
    pylist_of_string_to_cvec(PyList_GET_ITEM(res_misc, 0), res_names, "residue name");
    std::vector<ChainID> res_chain_ids;
    pylist_of_string_to_cvec(PyList_GET_ITEM(res_misc, 1), res_chain_ids, "chain ID");
    PyObject* py_res_ints = PyList_GET_ITEM(ints, 5);
    iarray = Numeric_Array();
    if (!array_from_python(py_res_ints, 1, Numeric_Array::Int, &iarray, false))
        throw std::invalid_argument("Residue int data is not a one-dimensional numpy int array");
    auto res_ints = static_cast<int*>(iarray.values());
    PyObject* py_res_floats = PyList_GET_ITEM(floats, 5);
    farray = Numeric_Array();
    if (!array_from_python(py_res_floats, 1, Numeric_Array::Float, &farray, false))
        throw std::invalid_argument("Residue float data is not a one-dimensional"
            " numpy float array");
    auto res_floats = static_cast<float*>(farray.values());
    for (decltype(res_names)::size_type i = 0; i < res_names.size(); ++i) {
        auto& res_name = res_names[i];
        auto& chain_id = res_chain_ids[i];
        auto pos = *res_ints++;
        auto insert = *res_ints++;
        auto r = new_residue(res_name, chain_id, pos, insert);
        r->session_restore(version, &res_ints, &res_floats);
    }

    // chains
    PyObject* chain_misc = PyList_GET_ITEM(misc, 6);
    if (!PyList_Check(chain_misc) or PyList_GET_SIZE(chain_misc) != 1)
        throw std::invalid_argument("chain misc info is not a one-item list");
    std::vector<ChainID> chain_chain_ids;
    pylist_of_string_to_cvec(PyList_GET_ITEM(chain_misc, 0), chain_chain_ids, "chain ID");
    PyObject* py_chain_ints = PyList_GET_ITEM(ints, 6);
    iarray = Numeric_Array();
    if (!array_from_python(py_chain_ints, 1, Numeric_Array::Int, &iarray, false))
        throw std::invalid_argument("Chain int data is not a one-dimensional numpy int array");
    auto chain_ints = static_cast<int*>(iarray.values());
    PyObject* py_chain_floats = PyList_GET_ITEM(floats, 6);
    farray = Numeric_Array();
    if (!array_from_python(py_chain_floats, 1, Numeric_Array::Float, &farray, false))
        throw std::invalid_argument("Chain float data is not a one-dimensional"
            " numpy float array");
    auto chain_floats = static_cast<float*>(farray.values());
    auto num_chains = *chain_ints++;
    if (num_chains < 0) {
        _chains = nullptr;
    } else {
        _chains = new Chains();
        for (auto chain_id: chain_chain_ids) {
            auto chain = _new_chain(chain_id);
            chain->session_restore(version, &chain_ints, &chain_floats);
        }
    }
}

void
Graph::session_save_setup() const
{
    size_t index = 0;

    session_save_atoms = new std::unordered_map<const Atom*, size_t>;
    for (auto a: atoms()) {
        (*session_save_atoms)[a] = index++;
    }

    index = 0;
    session_save_bonds = new std::unordered_map<const Bond*, size_t>;
    for (auto b: bonds()) {
        (*session_save_bonds)[b] = index++;
    }

    index = 0;
    session_save_chains = new std::unordered_map<const Chain*, size_t>;
    for (auto c: chains()) {
        (*session_save_chains)[c] = index++;
    }

    index = 0;
    session_save_crdsets = new std::unordered_map<const CoordSet*, size_t>;
    for (auto cs: coord_sets()) {
        (*session_save_crdsets)[cs] = index++;
    }

    index = 0;
    session_save_residues = new std::unordered_map<const Residue*, size_t>;
    for (auto r: residues()) {
        (*session_save_residues)[r] = index++;
    }

    _pb_mgr.session_save_setup();
}

void
Graph::session_save_teardown() const
{
    delete session_save_atoms;
    delete session_save_bonds;
    delete session_save_chains;
    delete session_save_crdsets;
    delete session_save_residues;

    _pb_mgr.session_save_teardown();
}

void
Graph::set_active_coord_set(CoordSet *cs)
{
    CoordSet *new_active;
    if (cs == nullptr) {
        if (_coord_sets.empty())
            return;
        new_active = _coord_sets.front();
    } else {
        CoordSets::iterator csi = std::find_if(_coord_sets.begin(), _coord_sets.end(),
                [&cs](CoordSet* vcs) { return vcs == cs; });
        if (csi == _coord_sets.end())
            throw std::out_of_range("Requested active coord set not in coord sets");
        new_active = cs;
    }
    if (_active_coord_set != new_active) {
        _active_coord_set = new_active;
        set_gc_shape();
        change_tracker()->add_modified(this, ChangeTracker::REASON_ACTIVE_COORD_SET);
    }
}

void
Graph::set_color(const Rgba& rgba)
{
    for (auto a: _atoms)
        a->set_color(rgba);
    for (auto b: _bonds)
        b->set_color(rgba);
    for (auto r: _residues)
        r->set_ribbon_color(rgba);
}

void
Graph::use_best_alt_locs()
{
    std::map<Residue *, char> alt_loc_map = best_alt_locs();
    for (auto almi = alt_loc_map.begin(); almi != alt_loc_map.end(); ++almi) {
        (*almi).first->set_alt_loc((*almi).second);
    }
}

} //  namespace atomstruct

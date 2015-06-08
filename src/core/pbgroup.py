from .molecule import CPseudoBondGroup
from .models import Model
class PseudoBondGroup(CPseudoBondGroup, Model):
    """Pseudobond group model"""

    def __init__(self, name, view):

        CPseudoBondGroup.__init__(self, name)
        Model.__init__(self, name)
        self._pbond_drawing = None

        self.update_graphics()

        self._view = view
        view.add_shape_changed_callback(self.update_graphics)

    def delete(self):
        self._view.remove_shape_changed_callback(self.update_graphics)
        self._view = None
        Model.delete(self)
        self._pbond_drawing = None
        CPseudoBondGroup.delete(self)

    def update_graphics(self):

        pbonds = self.pseudobonds
        d = self._pbond_drawing
        if len(pbonds) == 0:
            if d:
                d.delete()
                self._pbond_drawing = None
            return

        from . import structure
        if d is None:
            self._pbond_drawing = d = self.new_drawing('pbonds')
            va, na, ta = structure.pseudobond_geometry()
            d.vertices = va
            d.normals = na
            d.triangles = ta

        bond_atoms = pbonds.atoms
        radii = pbonds.radii
        bond_colors = pbonds.colors
        half_bond_coloring = pbonds.halfbonds
        to_pbg = self.scene_position.inverse()
        axyz0, axyz1 = to_pbg*bond_atoms[0].scene_coords, to_pbg*bond_atoms[1].scene_coords
        d.positions = structure.bond_cylinder_placements(axyz0, axyz1, radii, half_bond_coloring)
        d.display_positions = self.shown_bond_cylinders(bond_atoms, half_bond_coloring)
        d.colors = self.bond_colors(bond_atoms, bond_colors, half_bond_coloring)

    def bond_colors(self, bond_atoms, bond_colors, half_bond_coloring):
        if half_bond_coloring.any():
            bc0,bc1 = bond_atoms[0].colors, bond_atoms[1].colors
            from numpy import concatenate
            c = concatenate((bc0,bc1))
        else:
            c = bond_colors
        return c

    def shown_bond_cylinders(self, bond_atoms, half_bond_coloring):
        sb = bond_atoms[0].displays & bond_atoms[1].displays  # Show bond if both atoms shown
        if half_bond_coloring.any():
            sb2 = numpy.concatenate((sb,sb))
            return sb2
        return sb

    def take_snapshot(self, phase, session, flags):
        if phase != self.SAVE_PHASE:
            return
        data = {}
        return [self.STRUCTURE_STATE_VERSION, data]

    def restore_snapshot(self, phase, session, version, data):
        if version != self.STRUCTURE_STATE_VERSION or len(data) > 0:
            raise RestoreError("Unexpected version or data")

    def reset_state(self):
        pass

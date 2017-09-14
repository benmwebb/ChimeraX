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

from chimerax.core.toolshed import BundleAPI

class _gltfBundle(BundleAPI):

    @staticmethod
    def get_class(class_name):
        # 'get_class' is called by session code to get class saved in a session
        if class_name == 'gltfModel':
            from . import gltf
            return gltf.gltfModel
        return None

    @staticmethod
    def open_file(session, stream, file_name):
        # 'open_file' is called by session code to open a file
        # returns (list of models, status message)
        from . import gltf
        return gltf.read_gltf(session, stream, file_name)

    @staticmethod
    def save_file(session, path, models=None, center=None, size=None,
                  short_vertex_indices=False, float_colors=False):
        # 'save_file' is called by session code to save a file
        from . import gltf
        return gltf.write_gltf(session, path, models, center=center, size=size,
                               short_vertex_indices=short_vertex_indices,
                               float_colors=float_colors)

bundle_api = _gltfBundle()

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

class _DunbrackLibBundleAPI(BundleAPI):

    @staticmethod
    def run_provider(session, name, mgr, **kw):
        from .lib import DunbrackRotamerLibrary
        return DunbrackRotamerLibrary(name, session.rotamers.ui_name(name))


bundle_api = _DunbrackLibBundleAPI()

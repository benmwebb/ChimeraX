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

class _UniprotBundleAPI(BundleAPI):

    @staticmethod
    def fetch_from_database(session, identifier, ignore_cache=False, **kw):
        # 'fetch_from_database' is called to fetch data with give identifier
        from .fetch_uniprot import fetch_uniprot
        return fetch_uniprot(session, identifier, ignore_cache=ignore_cache)

bundle_api = _UniprotBundleAPI()
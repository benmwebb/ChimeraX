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

class PresetsManager:
    """Manager for presets"""

    def __init__(self, session):
        self._alignments = {}
        self.session = session
        self._presets = {}
        from chimerax.core.triggerset import TriggerSet
        self.triggers = TriggerSet()
        self.triggers.add_trigger("presets changed")

    @property
    def presets_by_category(self):
        return {cat:[name for name in info.keys()] for cat,info in self._presets.items()}

    def preset_function(self, category, preset_name):
        return self._presets[category][preset_name]

    def remove_presets(self, category, preset_names):
        for name in preset_names:
            del self._presets[category][name]
        self.triggers.activate_trigger("presets changed", self)

    def add_presets(self, category, preset_info):
        """'preset_info' should be a dictionary of preset-name -> callback-function/command-string"""
        self._presets.setdefault(category, {}).update({
            name: lambda p=preset: self.execute(p)
            for name, preset in preset_info
        })
        self.triggers.activate_trigger("presets changed", self)

    def add_provider(self, bundle_info, name,
                     order=None, category="General", **kw):
        from chimerax.core.utils import CustomSortString
        if order is None:
            cname = name
        else:
            cname = CustomSortString(name, sort_val=int(order))
        def cb(name=name, mgr=self, bi=bundle_info):
            bi.run_provider(self.session, name, self)
        try:
            self._presets[category][cname] = cb
        except KeyError:
            self._presets[category] = {cname:cb}

    def end_providers(self):
        self.triggers.activate_trigger("presets changed", self)

    def execute(self, preset):
        if callable(preset):
            preset()
            self.session.logger.info("Preset implemented in Python; no expansion to individual ChimeraX"
                " commands available.")
        else:
            from chimerax.core.commands import run
            run(self.session, preset, log=False)
            self.session.logger.info(
                "Preset expands to these ChimeraX commands: <i>%s</i>" % preset, is_html=True)

# vim: set expandtab ts=4 sw=4:

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

# -----------------------------------------------------------------------------
# Panel for erasing parts of map in sphere with map eraser mouse mode.
#
from chimerax.core.tools import ToolInstance
class VolumeMenu(ToolInstance):

    def __init__(self, session, tool_name):
        
        self._shown = False

        ToolInstance.__init__(self, session, tool_name)
        
    @classmethod
    def get_singleton(self, session, create=True):
        from chimerax.core import tools
        return tools.get_singleton(session, VolumeMenu, 'Volume Menu', create=create)

    @property
    def shown(self):
        return self._shown

    def display(self, show):
        if show:
            self.show()
        else:
            self.hide()
            
    def show(self):
        if self._shown:
            return
        self._shown = True
        global settings
        settings.show_volume_menu = True
        for tool in self._volume_tools():
            tool_name = 'Hide Volume Menu' if tool.name == 'Show Volume Menu' else tool.name
            def callback(ses = self.session, tool_name=tool_name, vmenu = self):
                if tool_name == 'Hide Volume Menu':
                    vmenu.hide()
                else:
                    from chimerax.core.commands import run, quote_if_necessary
                    run(ses, "toolshed show %s" % quote_if_necessary(tool_name))
            self.session.ui.main_window.add_menu_entry(['Volume'], tool_name, callback)

    def hide(self):
        if not self._shown:
            return
        self._shown = False
        global settings
        settings.show_volume_menu = False
        self.session.ui.main_window.remove_menu(['Volume'])

    def toggle(self):
        if self.shown:
            self.hide()
        else:
            self.show()

    def _volume_tools(self):
        tools = []
        ses = self.session
        for bi in ses.toolshed.bundle_info(ses.logger):
            for tool in bi.tools:
                if 'Volume Data' in tool.categories:
                    tools.append(tool)
        tools.sort(key = lambda t: t.name)
        return tools


from chimerax.core.settings import Settings
class _VolumeMenuSettings(Settings):
    AUTO_SAVE = {
        'show_volume_menu': False,
    }

settings = None	# Set by bundle initialization code _VolumeMenuAPI.initialize().
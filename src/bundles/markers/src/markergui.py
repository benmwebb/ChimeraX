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
# User interface for building cages.
#
from chimerax.core.tools import ToolInstance

# ------------------------------------------------------------------------------
#
class MarkerModeSettings(ToolInstance):

    def __init__(self, session, tool_name):
        ToolInstance.__init__(self, session, tool_name)

        self.display_name = 'Markers'

        from chimerax.core.ui.gui import MainToolWindow
        tw = MainToolWindow(self)
        self.tool_window = tw
        parent = tw.ui_area
        
        from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMenu, QSizePolicy

        playout = QVBoxLayout(parent)
        playout.setContentsMargins(0,0,0,0)
        playout.setSpacing(0)
        parent.setLayout(playout)

        f = QFrame(parent)
        f.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        playout.addWidget(f)
        layout = QVBoxLayout(f)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        f.setLayout(layout)
        
        mf = QFrame(f)
#        mf.setStyleSheet('background-color: green')

        mf.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout.addWidget(mf)
        self.mode_menu_names = mnames = {
            'surface': 'Place marker on surface',
            'surface center': 'Place marker at center of connected surface',
            'link': 'Link consecutively clicked markers'}
        mode_order = ('surface', 'surface center', 'link')
        mm_layout = QHBoxLayout(mf)
        mm_layout.setContentsMargins(0,0,0,0)
        mm_layout.setSpacing(5)
        mf.setLayout(mm_layout)
        ml = QLabel(' Mouse mode', mf)
        mm_layout.addWidget(ml)
        self.mode_button = mb = QPushButton(mf)
        mm = QMenu()
        for m in mode_order:
            mm.addAction(mnames[m], lambda mode=m, self=self: self.mode_change_cb(mode))
        mb.setMenu(mm)
        mm_layout.addWidget(mb)
        mm_layout.addStretch(1)    # Extra space at end
        self.update_settings()
        
        tw.manage(placement="side")

    def update_settings(self):
        from .markers import marker_settings
        mode = marker_settings(self.session, 'placement_mode')
        self.mode_button.setText(self.mode_menu_names[mode])
        
    def show(self):
        self.tool_window.shown = True

    def hide(self):
        self.tool_window.shown = False

    def mode_change_cb(self, mode):
        self.mode_button.setText(self.mode_menu_names[mode])

        from .markers import marker_settings
        s = marker_settings(self.session)
        s['placement_mode'] = mode

        
def marker_panel(session, tool_name):
  cb = getattr(session, '_markers_gui', None)
  if cb is None:
    session._markers_gui = cb = MarkerModeSettings(session, tool_name)
  return cb

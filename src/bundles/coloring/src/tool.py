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

from chimerax.core.tools import ToolInstance


class ColoringTool(ToolInstance):

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        from chimerax.ui import MainToolWindow
        self.tool_window = tw = MainToolWindow(self)
        parent = tw.ui_area
        #TODO
        from PyQt5.QtWidgets import QVBoxLayout, QDialogButtonBox
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        parent.setLayout(layout)
        self.gui = gui_class(self.session, has_apply_button=True)
        layout.addWidget(self.gui)

        from PyQt5.QtWidgets import QDialogButtonBox as qbbox
        bbox = qbbox(qbbox.Ok | qbbox.Apply | qbbox.Close | qbbox.Help)
        bbox.accepted.connect(self.run_command)
        bbox.button(qbbox.Apply).clicked.connect(self.run_command)
        bbox.accepted.connect(self.delete) # slots executed in the order they are connected
        bbox.rejected.connect(self.delete)
        if self.help:
            from chimerax.core.commands import run
            bbox.helpRequested.connect(lambda run=run, ses=self.session: run(ses, "help " + self.help))
        else:
            bbox.button(qbbox.Help).setEnabled(False)
        layout.addWidget(bbox)

        tw.manage(placement=None)

    def delete(self):
        self.gui.destroy()
        super().delete()

    def run_command(self):
        from chimerax.core.commands import run
        run(self.session, " ".join(self.gui.get_command()))
        self.session.logger.status("You can hide/close %s with the Model Panel" % self.gui.prox_words,
            secondary=True, color="blue", blank_after=15)

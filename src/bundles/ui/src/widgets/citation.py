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

""" Citation:  show citation for literature reference"""

import os
from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel, QToolButton, QAction
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import Qt

class Citation(QFrame):

    def __init__(self, session, cite, prefix=None, suffix=None, url=None, pubmed_id=None, image=True):
        """
            'cite' is the citation text
            'prefix'/'suffix' is text to precede/follow the citation
            'url' is the link to the publication data base.
            'pubmed_id' is the PubMed ID, which can be supplied in lieu of 'url'
                if appropriate
            'image' is the path to the image file of publication data base logo icon.
             the default is the PubMed icon.
        """
        QFrame.__init__(self)
        self.setFrameStyle(self.Panel | self.Raised)

        self.session = session

        layout = QGridLayout()
        self.setLayout(layout)

        if prefix is not None:
            layout.addWidget(QLabel(prefix), 0, 0, Qt.AlignRight)

        cite_label = QLabel(cite)
        cite_label.setFont(QFont("Times", 12))
        layout.addWidget(cite_label, 1, 0, Qt.AlignLeft)

        if url is None:
            if pubmed_id:
                url = 'https://www.ncbi.nlm.nih.gov/pubmed/' + str(pubmed_id)
        if url is not None:
            self.url = url
            if image is True:
                image_path = os.path.join(os.path.dirname(__file__), "icons", "Default_PubMed.png")
            else:
                image_path = image
            if image_path:
                action = QAction(QIcon(image_path), "Abstract")
            else:
                action = QAction("Abstract")
            action.triggered.connect(self._open_url)
            button = QToolButton()
            button.setDefaultAction(action)
            button.setAutoRaise(True)
            layout.addWidget(button, 1, 1, Qt.AlignLeft | Qt.AlignBottom)
        if suffix is not None:
            layout.addWidget(QLabel(suffix), 2, 0, Qt.AlignLeft)

    def _open_url(self):
        from chimerax.help_viewer import show_url
        show_url(self.session, self.url)
        return
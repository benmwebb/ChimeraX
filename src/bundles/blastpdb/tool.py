# vim: set expandtab shiftwidth=4 softtabstop=4:

# ToolUI classes may also override
#   "delete" - called to clean up before instance is deleted
#
from chimerax.core.tools import ToolInstance

_EmptyPage = "<h2>Please select a chain and press <b>BLAST</b></h2>"
_InProgressPage = "<h2>BLAST search in progress&hellip;</h2>"


class ToolUI(ToolInstance):

    SESSION_ENDURING = False
    CUSTOM_SCHEME = "blastpdb"
    REF_ID_URL = "https://www.ncbi.nlm.nih.gov/gquery/?term=%s"

    def __init__(self, session, tool_name, blast_results=None, atomspec=None):
        # Standard template stuff
        ToolInstance.__init__(self, session, tool_name)
        self.display_name = "Blast PDB"
        from chimerax.core.ui.gui import MainToolWindow
        self.tool_window = MainToolWindow(self)
        self.tool_window.manage(placement="side")
        parent = self.tool_window.ui_area

        # UI consists of a chain selector and search button on top
        # and HTML widget below for displaying results.
        # Layout all the widgets
        from PyQt5.QtWidgets import QGridLayout, QLabel, QComboBox, QPushButton
        from chimerax.core.ui.widgets import HtmlView
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel("Chain:")
        layout.addWidget(label, 0, 0)
        self.chain_combobox = QComboBox()
        layout.addWidget(self.chain_combobox, 0, 1)
        button = QPushButton("BLAST")
        button.clicked.connect(self._blast_cb)
        layout.addWidget(button, 0, 2)
        self.results_view = HtmlView(parent, size_hint=(575, 300),
                                     interceptor=self._navigate,
                                     schemes=[self.CUSTOM_SCHEME])
        layout.addWidget(self.results_view, 1, 0, 1, 3)
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 10)
        layout.setColumnStretch(2, 0)
        layout.setRowStretch(0, 0)
        layout.setRowStretch(1, 10)
        parent.setLayout(layout)

        # Register for model addition/removal so we can update chain list
        from chimerax.core.models import ADD_MODELS, REMOVE_MODELS
        t = session.triggers
        self._add_handler = t.add_handler(ADD_MODELS, self._update_chains)
        self._remove_handler = t.add_handler(REMOVE_MODELS, self._update_chains)

        # Set widget values and go
        self._update_chains()
        self._update_blast_results(blast_results, atomspec)

    def _blast_cb(self, _):
        from .job import BlastPDBJob
        n = self.chain_combobox.currentIndex()
        if n < 0:
            return
        chain = self.chain_combobox.itemData(n)
        BlastPDBJob(self.session, chain.characters, chain.atomspec(),
                    finish_callback=self._blast_job_finished)
        self.results_view.setHtml(_InProgressPage)

    def _update_chains(self, trigger=None, trigger_data=None):
        from chimerax.core.atomic import AtomicStructure
        all_chains = []
        for m in self.session.models.list(type=AtomicStructure):
            all_chains.extend(m.chains)
        all_chains.sort(key=str)
        self.chain_combobox.clear()
        for chain in all_chains:
            self.chain_combobox.addItem(str(chain), userData=chain)

    def _blast_job_finished(self, blast_results, job):
        self._update_blast_results(blast_results, job.atomspec)

    def _update_blast_results(self, blast_results, atomspec):
        # blast_results is either None or a blastp_parser.Parser
        self.ref_atomspec = atomspec
        if atomspec:
            from chimerax.core.commands import AtomSpecArg
            arg = AtomSpecArg.parse(atomspec, self.session)[0]
            s = arg.evaluate(self.session)
            chains = s.atoms.residues.unique_chains
            if len(chains) == 1:
                n = self.chain_combobox.findData(chains[0])
                self.chain_combobox.setCurrentIndex(n)
        if blast_results is None:
            self.results_view.setHtml(_EmptyPage)
        else:
            html = ["<h2>BlastPDB ",
                    "<small>(an <a href=\"http://www.rbvi.ucsf.edu\">RBVI</a> "
                    "web service)</small> Results</h2>",
                    "<table><tr>"
                    "<th>Name</th>"
                    "<th>E&#8209;Value</th>"
                    "<th>Score</th>"
                    "<th>Description</th>"
                    "</tr>"]
            for m in blast_results.matches[1:]:
                if m.pdb:
                    name = "<a href=\"%s:%s\">%s</a>" % (self.CUSTOM_SCHEME,
                                                         m.pdb, m.pdb)
                else:
                    import re
                    match = re.search(r"\|ref\|([^|]+)\|", m.name)
                    if match is None:
                        name = m.name
                    else:
                        ref_id = match.group(1)
                        ref_url = self.REF_ID_URL % ref_id
                        name = "<a href=\"%s\">%s</a>" % (ref_url, ref_id)
                html.append("<tr><td>%s</td><td>%s</td>"
                            "<td>%s</td><td>%s</td></tr>" %
                            (name, "%.1e" % m.evalue,
                             str(m.score), m.description))
            html.append("</table>")
            self.results_view.setHtml('\n'.join(html))

    def _navigate(self, info):
        # "info" is an instance of QWebEngineUrlRequestInfo
        url = info.requestUrl()
        scheme = url.scheme()
        if scheme == self.CUSTOM_SCHEME:
            # self._load_pdb(url.path())
            self.session.ui.thread_safe(self._load_pdb, url.path())
        # For now, we only intercept our custom scheme.  All other
        # requests are processed normally.

    def _load_pdb(self, code):
        from chimerax.core.commands import run
        parts = code.split("_", 1)
        if len(parts) == 1:
            pdb_id = parts[0]
            chain_id = None
        else:
            pdb_id, chain_id = parts
        models = run(self.session, "open pdb:%s" % pdb_id)[0]
        if not self.ref_atomspec:
            run(self.session, "select clear")
        for m in models:
            if chain_id:
                spec = m.atomspec() + '/' + chain_id
            else:
                spec = m.atomspec()
            if self.ref_atomspec:
                run(self.session, "matchmaker %s to %s" % (spec,
                                                           self.ref_atomspec))
            else:
                run(self.session, "select add %s" % spec)

    def delete(self):
        t = self.session.triggers
        t.remove_handler(self._add_handler)
        t.remove_handler(self._remove_handler)

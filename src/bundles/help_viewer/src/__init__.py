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

from chimerax.core import toolshed
_new_bundle_handler = None

help_url_paths = []     # help directories in URL path form


def _update_cache(trigger_name=None, bundle_info=None):
    global help_url_paths

    import os
    from chimerax import app_dirs
    cached_index = os.path.join(app_dirs.user_cache_dir, 'docs', 'user', 'index.html')
    try:
        os.remove(cached_index)
    except OSError:
        pass

    def cvt_path(path):
        from urllib.request import pathname2url
        help_path = pathname2url(path)
        if help_path.startswith('///'):
            help_path = help_path[2:]
        if not help_path.endswith('/'):
            help_path += '/'
        return help_path

    help_directories = toolshed.get_help_directories()
    help_url_paths = [cvt_path(hd) for hd in help_directories]


class _MyAPI(toolshed.BundleAPI):

    @staticmethod
    def initialize(session, bundle_info):
        global _new_bundle_handler
        ts = toolshed.get_toolshed()
        _new_bundle_handler = ts.triggers.add_handler(
            toolshed.TOOLSHED_BUNDLE_INSTALLED, _update_cache)
        # ? = ts.triggers.add_handler(
        #    toolshed.TOOLSHED_BUNDLE_UNINSTALLED, _update_cache)
        _update_cache()

    @staticmethod
    def finish(session, bundle_info):
        global _new_bundle_handler
        ts = toolshed.get_toolshed()
        if _new_bundle_handler is not None:
            ts.triggers.remove_handler(_new_bundle_handler)
            _new_bundle_handler = None

    @staticmethod
    def register_command(command_name, logger):
        # 'register_command' is lazily called when command is referenced
        from . import cmd
        from chimerax.core.commands import register
        register(command_name, cmd.help_desc, cmd.help, logger=logger)

    @staticmethod
    def open_file(session, path, file_name, new_tab=False):
        # 'open_file' is called by session code to open a file
        import os
        base, ext = os.path.splitext(path)
        ext, *fragment = ext.split('#')
        if not fragment:
            fragment = ''
        else:
            fragment = fragment[0]
            path = path[:-(len(fragment) + 1)]
        path = os.path.abspath(path)
        from urllib.parse import urlunparse
        from urllib.request import pathname2url
        url = urlunparse(('file', '', pathname2url(path), '', '', fragment))
        show_url(session, url, new_tab=new_tab)
        return [], "Opened %s" % file_name

    @staticmethod
    def get_class(class_name):
        # 'get_class' is called by session code to get class saved in a session
        if class_name == 'HelpUI':
            from . import tool
            return tool.HelpUI
        return None

    @staticmethod
    def run_provider(session, name, mgr, **kw):
        from chimerax.open import OpenerInfo
        class HelpViewerOpenerInfo(OpenerInfo):
            def open(self, session, path, file_name, **kw):
                import os
                base, ext = os.path.splitext(path)
                ext, *fragment = ext.split('#')
                if not fragment:
                    fragment = ''
                else:
                    fragment = fragment[0]
                    path = path[:-(len(fragment) + 1)]
                path = os.path.abspath(path)
                from urllib.parse import urlunparse
                from urllib.request import pathname2url
                url = urlunparse(('file', '', pathname2url(path), '', '', fragment))
                show_url(session, url, new_tab=False)
                return [], "Opened %s" % file_name
        return HelpViewerOpenerInfo()


def show_url(session, url, *, new_tab=False, html=None):
    if session.ui.is_gui:
        from .tool import HelpUI
        help_viewer = HelpUI.get_viewer(session)
        help_viewer.show(url, new_tab=new_tab, html=html)
    else:
        import webbrowser
        if new_tab:
            webbrowser.open_new_tab(url)
        else:
            webbrowser.open(url)


bundle_api = _MyAPI()

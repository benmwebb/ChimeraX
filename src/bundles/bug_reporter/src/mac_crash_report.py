# -----------------------------------------------------------------------------
# Check Mac crash log to see if ChimeraX crashed since the last time it was
# started.  If so display the ChimeraX bug report dialog with crash log info
# filled in.
#
def check_for_crash_on_mac(session):

    import sys
    if sys.platform != 'darwin':
        return  # Only check for crashes on Mac OS.

    # Get time of last check for crash logs.
    from .settings import BugReporterSettings
    settings = BugReporterSettings(session, 'Bug Reporter')
    last = settings.last_crash_check
    from time import time
    settings.last_crash_check = time()
    if last is None:
        return          # No previous crash check time available.

    report = recent_chimera_crash(last)
    if report is None:
        return

    # Show Chimera bug reporting dialog.
    from chimerax.bug_reporter import show_bug_reporter
    br = show_bug_reporter(session)
    br.set_description('<p><font color=red>Last time you used ChimeraX it crashed.</font><br>'
                       'Please describe steps that led to the crash here.</p>'
                       '<pre>\n%s\n</pre>' % report)

# -----------------------------------------------------------------------------
#
def recent_chimera_crash(time):

    # Check if Mac Python crash log exists and was modified since last
    # time Chimera was started.
    dir = crash_logs_directory()
    if dir is None:
        return None

    log = recent_crash(time, dir, 'ChimeraX')
    return log

# -----------------------------------------------------------------------------
# On Mac OS 10.6 and later uses ~/Library/Logs/DiagnosticReports for crash logs.
#
def crash_logs_directory():

    from os.path import expanduser, isdir
    logd = expanduser('~/Library/Logs/DiagnosticReports')
    if isdir(logd):
        return logd
    return None

# -----------------------------------------------------------------------------
#
def recent_crash(time, dir, file_prefix):

    from os import listdir
    filenames = listdir(dir)

    from os.path import getmtime, join
    pypaths = [join(dir,f) for f in filenames if f.startswith(file_prefix)]
    tpaths = [(getmtime(p), p) for p in pypaths]
    if len(tpaths) == 0:
        return None

    tpaths.sort()
    t, p = tpaths[-1]
    if t < time:
        return None     # No file more recent than time.

    f = open(p, 'r')
    log = f.read()
    f.close()

    return log

# -----------------------------------------------------------------------------
#
def register_mac_crash_checker(session):
    import sys
    if sys.platform != 'darwin':
        return
    
    # Delay crash check until ChimeraX fully started.
    def crash_check(tname, data):
        check_for_crash_on_mac(session)
        from chimerax.core import triggerset
        return triggerset.DEREGISTER
    
    session.triggers.add_handler('new frame', crash_check)

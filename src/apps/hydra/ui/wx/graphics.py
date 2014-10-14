# vim: set expandtab ts=4 sw=4:

import wx
from ...graphics import View

class GraphicsWindow(View, wx.Panel):
    """
    The graphics window that displays the three-dimensional models.

    Routines that involve the window toolkit or event processing are
    handled by this class while routines that depend only on OpenGL
    are in the View base class.
    """

    def __init__(self, session, parent=None):
        self.session = session
        wx.Panel.__init__(self, parent)
        self.opengl_context = None
        self.opengl_canvas = OpenGLCanvas(self)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.opengl_canvas, 1, wx.EXPAND)
        self.SetSizerAndFit(sizer)

        View.__init__(self, session, self.GetClientSize())

        self.set_stereo_eye_separation()

        self.timer = None
        self.redraw_interval = 16  #milliseconds
        #TODO: maybe redraw interval should be 10 msec to reduce
        # frame drops at 60 frames/sec

        from . import mousemodes
        self.mouse_modes = mousemodes.Mouse_Modes(self)

        self.Bind(wx.EVT_CHAR, self.OnChar)

    def OnChar(self, event):
        from sys import stderr
        print("key", file=stderr)
        log = self.session.log
        log.log_message("key event: {}".format(str(event)))
        log.show()
        event.Skip()

    def create_opengl_context(self):
        from wx.glcanvas import GLContext
        return GLContext(self.opengl_canvas)

    def make_opengl_context_current(self):
        if self.opengl_context is None:
            self.opengl_context = self.create_opengl_context()
            self.start_update_timer()
        self.opengl_canvas.SetCurrent(self.opengl_context)

    def redraw_timer_callback(self, evt):
        if True:
            if not self.redraw():
                self.mouse_modes.mouse_pause_tracking()

    def set_stereo_eye_separation(self, eye_spacing_millimeters=61.0):
        screen = wx.ScreenDC()
        ssize = screen.GetSizeMM()[0]
        psize = screen.GetSize()[0]
        self.camera.eye_separation_pixels = psize * eye_spacing_millimeters \
            / ssize

    def start_update_timer(self):
        if self.timer is None:
            self.timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.redraw_timer_callback, self.timer)
            self.timer.Start(self.redraw_interval)

    def swap_opengl_buffers(self):
        self.opengl_canvas.SwapBuffers()

from wx import glcanvas
class OpenGLCanvas(glcanvas.GLCanvas):

    def __init__(self, parent):
        self.graphics_window = parent
        attribs = [ glcanvas.WX_GL_RGBA, glcanvas.WX_GL_DOUBLEBUFFER,
            glcanvas.WX_GL_OPENGL_PROFILE, glcanvas.WX_GL_OPENGL_PROFILE_3_2CORE
            ]
        gl_supported = glcanvas.GLCanvas.IsDisplaySupported
        if not gl_supported(attribs):
            raise AssertionError("Required OpenGL capabilities RGBA and/or"
                " double buffering and/or OpenGL 3 not supported")
        for depth in range(32, 0, -8):
            test_attribs = attribs + [glcanvas.WX_GL_DEPTH_SIZE, depth]
            if gl_supported(test_attribs):
                attribs = test_attribs
                print("Using {}-bit OpenGL depth buffer".format(depth))
                break
        else:
            raise AssertionError("Required OpenGL depth buffer capability"
                " not supported")
        test_attribs = attribs + [glcanvas.WX_GL_STEREO]
        if gl_supported(test_attribs):
            attribs = test_attribs
        else:
            print("Stereo mode is not supported by OpenGL driver")
        glcanvas.GLCanvas.__init__(self, parent, -1, attribList=attribs)

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_PAINT, self.OnPaint)

    def OnPaint(self, evt):
        #dc = wx.PaintDC(self)
        #self.OnDraw()
        self.graphics_window.draw_graphics()

    def OnSize(self, evt):
        wx.CallAfter(self.set_viewport)
        evt.Skip()

    def set_viewport(self):
        self.graphics_window.window_size = w, h = self.GetClientSize()
        if self.graphics_window.opengl_context is not None:
            from ... import graphics
            fb = graphics.default_framebuffer()
            fb.width, fb.height = w, h
            fb.viewport = (0, 0, w, h)

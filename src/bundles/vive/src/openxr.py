
class XR:
    '''
    Encapsulate all OpenXR API calls.

    Copied most of the OpenXR setup code from xr_examples/gl_example.py in
        https://github.com/cmbruns/pyopenxr_examples
    '''
    def __init__(self):
        self.field_of_view = [None, None]		# Field of view for each eye, radians
        self.eye_pose = [None, None]			# Last eye camera pose
        self._debug = True
        
        self._instance = None				# Connection to OpenXR runtime
        self._system_id = None				# Headset hardware
        self._session = None				# Connection to headset
        self._session_state = None
        self._projection_layer = None
        self._swapchains = []				# Render textures
        self._framebuffers = []				# Framebuffers for left and right eyes
        self.render_size = (1000,1000)
        self._ready_to_render = False

        self._frame_started = False
        self._frame_count = 0

        self._action_set = None
        self._event_queue = []

    def start_session(self):
        self._instance = self._create_instance()	# Connect to OpenXR runtime
        self._system_id = self._create_system()		# Choose headset
        self._session = self._create_session()		# Connect to headset
        self._projection_layer = self._create_projection_layer()
        self.render_size = self._recommended_render_size()
        self._frame_started = False
        self._frame_count = 0
        self._action_set = self._create_action_set()	# Manage hand controller input
        
    def _create_instance(self):
        '''Establish connection to OpenXR runtime.'''
        import xr
        requested_extensions = [xr.KHR_OPENGL_ENABLE_EXTENSION_NAME]
        if self._debug:
            requested_extensions.append(xr.EXT_DEBUG_UTILS_EXTENSION_NAME)

        app_info = xr.ApplicationInfo("chimerax", 0, "pyopenxr", 0, xr.XR_CURRENT_API_VERSION)
        iinfo = xr.InstanceCreateInfo(application_info = app_info,
                                      enabled_extension_names = requested_extensions)
        if self._debug:
            dumci = xr.DebugUtilsMessengerCreateInfoEXT()
            dumci.message_severities = (xr.DEBUG_UTILS_MESSAGE_SEVERITY_VERBOSE_BIT_EXT
                                        | xr.DEBUG_UTILS_MESSAGE_SEVERITY_INFO_BIT_EXT
                                        | xr.DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT
                                        | xr.DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT)
            dumci.message_types = (xr.DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT
                                   | xr.DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT
                                   | xr.DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT
                                   | xr.DEBUG_UTILS_MESSAGE_TYPE_CONFORMANCE_BIT_EXT)
            dumci.user_data = None  # TODO
            self._debug_cb = xr.PFN_xrDebugUtilsMessengerCallbackEXT(self._debug_callback)
            dumci.user_callback = self._debug_cb
            import ctypes
            iinfo.next = ctypes.cast(ctypes.pointer(dumci), ctypes.c_void_p)  # TODO: yuck

        instance = xr.create_instance(iinfo)

        return instance

    def runtime_name(self):
        import xr
        return xr.get_instance_properties(instance=self._instance).runtime_name.decode('utf-8')
    
    def _create_system(self):
        '''Find headset.'''
        import xr
        get_info = xr.SystemGetInfo(xr.FormFactor.HEAD_MOUNTED_DISPLAY)
        system_id = xr.get_system(self._instance, get_info)
        return system_id

    def system_name(self):
        import xr
        return xr.get_system_properties(instance=self._instance, system_id=self._system_id).system_name.decode('utf-8')

    def _recommended_render_size(self):
        '''Width and height of single eye framebuffer.'''
        import xr
        view_configs = xr.enumerate_view_configurations(self._instance, self._system_id)
        assert view_configs[0] == xr.ViewConfigurationType.PRIMARY_STEREO.value
        view_config_views = xr.enumerate_view_configuration_views(
            self._instance, self._system_id, xr.ViewConfigurationType.PRIMARY_STEREO)
        assert len(view_config_views) == 2
        view0 = view_config_views[0]
        return (view0.recommended_image_rect_width, view0.recommended_image_rect_height)

    def _create_session(self):
        '''
        Connect to headset.
        This requires the OpenGL context to be current because it passes the graphics
        context as an argument when creating the session.
        '''
        self._get_graphics_requirements()
        import xr
        gb = xr.GraphicsBindingOpenGLWin32KHR()
        from OpenGL import WGL
        gb.h_dc = WGL.wglGetCurrentDC()
        gb.h_glrc = WGL.wglGetCurrentContext()
        debug ('WGL dc', gb.h_dc, 'WGL context', gb.h_glrc)
        self._graphics_binding = gb
        import ctypes
        pp = ctypes.cast(ctypes.pointer(gb), ctypes.c_void_p)
        sesinfo = xr.SessionCreateInfo(0, self._system_id, next=pp)
        session = xr.create_session(self._instance, sesinfo)
        space = xr.create_reference_space(session,
                                          xr.ReferenceSpaceCreateInfo(xr.ReferenceSpaceType.STAGE))
        self._scene_space = space
        return session

    def _get_graphics_requirements(self):
        # Have to call this before xrCreateSession() otherwise OpenXR generates an error.
        # TODO: pythonic wrapper
        import ctypes, xr
        pxrGetOpenGLGraphicsRequirementsKHR = ctypes.cast(
            xr.get_instance_proc_addr(
                self._instance,
                "xrGetOpenGLGraphicsRequirementsKHR",
            ),
            xr.PFN_xrGetOpenGLGraphicsRequirementsKHR
        )
        graphics_requirements = xr.GraphicsRequirementsOpenGLKHR()
        result = pxrGetOpenGLGraphicsRequirementsKHR(
            self._instance, self._system_id,
            ctypes.byref(graphics_requirements))  # TODO: pythonic wrapper
        result = xr.exception.check_result(xr.Result(result))
        if result.is_exception():
            raise result

        min_ver = graphics_requirements.min_api_version_supported
        max_ver = graphics_requirements.max_api_version_supported
        debug (f'OpenXR requires OpenGL minimum version {min_ver >> 48}.{(min_ver >> 32) & 0xffff}, maximum version {max_ver >> 48}.{(max_ver >> 32) & 0xffff}')

    def _create_projection_layer(self):
        '''Set projection mode'''
        import xr
        pl_views = (xr.CompositionLayerProjectionView * 2)(
            xr.CompositionLayerProjectionView(), xr.CompositionLayerProjectionView())
        self._projection_layer_views = pl_views
        projection_layer = xr.CompositionLayerProjection(space = self._scene_space,
                                                         views = pl_views)
        return projection_layer

    def _create_swapchains(self):
        '''Make render textures'''
        from OpenGL import GL
        # Only the SRGB format gives colors similar to screen.
        # All other formats openxr treats as linear intensity, appears bright.
        color_formats = [GL.GL_SRGB8_ALPHA8]
        color_formats.append(GL.GL_RGBA16F)  # Works on SteamVR with Vive Pro (881A)
        # Supported openxr color formats on Oculus Quest 2. 8058, 881B, 8C3A, 8C43
        color_formats.extend([GL.GL_RGBA8, GL.GL_RGB16F, GL.GL_R11F_G11F_B10F, GL.GL_SRGB8_ALPHA8])
        import xr
        swapchain_formats = xr.enumerate_swapchain_formats(self._session)
        for color_format in color_formats:
            if color_format in swapchain_formats:
                break
        if color_format not in swapchain_formats:
            format_nums = ['%0X' % fmt for fmt in swapchain_formats]
            raise ValueError(f'Color format {color_format} not in supported formats {format_nums}')
        w,h = self.render_size
        scinfo = xr.SwapchainCreateInfo(
            usage_flags = (xr.SwapchainUsageFlags.SAMPLED_BIT |
                           xr.SwapchainUsageFlags.COLOR_ATTACHMENT_BIT),
            #usage_flags = xr.SWAPCHAIN_USAGE_TRANSFER_DST_BIT,
            format = color_format,
            sample_count = 1,
            array_size = 1,
            face_count = 1,
            mip_count = 1,
            width = w,
            height = h)
        
        swapchains = [xr.create_swapchain(self._session, scinfo),	# Left and right eye
                      xr.create_swapchain(self._session, scinfo)]

        # Keep the buffer alive by moving it into the list of buffers.
        self._swapchain_image_buffer = [
            xr.enumerate_swapchain_images(swapchain=swapchain,
                                          element_type=xr.SwapchainImageOpenGLKHR)
            for swapchain in swapchains]

        for sc, plv in zip(swapchains, self._projection_layer_views):
            plv.sub_image.swapchain = sc
            plv.sub_image.image_rect.offset[:] = (0,0)
            plv.sub_image.image_rect.extent[:] = (w, h)

        return swapchains

    def _create_framebuffers(self, opengl_context):
        if len(self._swapchains) == 0:
            self._swapchains = self._create_swapchains()
        w,h = self.render_size
        from chimerax.graphics.opengl import Texture, Framebuffer
        framebuffers = []
        for sc, eye in zip(self._swapchains, ('left','right')):
            import xr
            images = xr.enumerate_swapchain_images(sc, xr.SwapchainImageOpenGLKHR)
            tex_id = images[0].image
            t = Texture()
            t.id = tex_id
            t.size = (w,h)
            fb = Framebuffer(f'VR {eye} eye', opengl_context,
                             width=w, height=h, color_texture = t, alpha = True)
            framebuffers.append(fb)
        return framebuffers

    def _delete_framebuffers(self):
        for fb in self._framebuffers:
            fb.delete(make_current = True)
        self._framebuffers.clear()

    def set_opengl_render_target(self, render, eye):
        if not self._frame_started:
            return
        if len(self._framebuffers) == 0:
            self._framebuffers = self._create_framebuffers(render.opengl_context)
        ei = 0 if eye == 'left' else 1
        swapchain = self._swapchains[ei]
        import xr
        swapchain_index = xr.acquire_swapchain_image(swapchain=swapchain,
                                                     acquire_info=xr.SwapchainImageAcquireInfo())
        xr.wait_swapchain_image(swapchain=swapchain,
                                wait_info=xr.SwapchainImageWaitInfo(xr.INFINITE_DURATION))
        render.push_framebuffer(self._framebuffers[ei])
        images = xr.enumerate_swapchain_images(swapchain, xr.SwapchainImageOpenGLKHR)
        tex_id = images[swapchain_index].image
        from chimerax.graphics.opengl import GL
        GL.glFramebufferTexture(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, tex_id, 0)
        # The swap chains consist of 3 images, probably to pipeline the rendering,
        # so each frame the next image is used.
        debug('render target', eye, 'texture', tex_id)

        '''
        miplevel = 0
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex_id)
        w = GL.glGetTexLevelParameteriv(GL.GL_TEXTURE_2D, miplevel, GL.GL_TEXTURE_WIDTH)
        h = GL.glGetTexLevelParameteriv(GL.GL_TEXTURE_2D, miplevel, GL.GL_TEXTURE_HEIGHT)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        debug('texture size', w, h)
        '''

        '''
        fbo_status = GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)
        if fbo_status != GL.GL_FRAMEBUFFER_COMPLETE:
            error('Framebuffer is not complete', fbo_status)
            """
    36054 GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT is generated when:

    Not all framebuffer attachment points are framebuffer attachment complete. This means that at least one attachment point with a renderbuffer or texture attached has its attached object no longer in existence or has an attached image with a width or height of zero, or the color attachment point has a non-color-renderable image attached, or the depth attachment point has a non-depth-renderable image attached, or the stencil attachment point has a non-stencil-renderable image attached.
            """
            GL.glFramebufferTexture(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, 0, 0)
            fbo_status = GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)
            if fbo_status == GL.GL_FRAMEBUFFER_COMPLETE:
                debug('After removing framebuffer color attachment it is complete')
            else:
                error('After removing framebuffer color attachment still is not complete', fbo_status)
        '''
        
    def release_opengl_render_target(self, render, eye):
        if not self._frame_started:
            return
        # The gl_example.py code unbinds the color texture from the framebuffer
        # after rendering.  Maybe this is needed so that xr.end_frame() can use the
        # color texture.  Not sure.
#        from chimerax.graphics.opengl import GL
#        GL.glFramebufferTexture(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, 0, 0)
        render.pop_framebuffer()
#        from chimerax.graphics.opengl import GL        
#        GL.glFinish()
        ei = 0 if eye == 'left' else 1
        swapchain = self._swapchains[ei]
        import xr
        xr.release_swapchain_image(swapchain, xr.SwapchainImageReleaseInfo())

    def start_frame(self):
        self._frame_started = False
        if not self._ready_to_render:
            return False
        self._poll_xr_events()
        if self._start_xr_frame():
            debug ('started xr frame')
            if self._update_xr_views() and self._frame_state.should_render:
                self._frame_count += 1
                debug ('frame should render')
                self._frame_started = True
                return True
            else:
                self._end_xr_frame()
        return False

    def end_frame(self):
        if self._frame_started:
            self._frame_started = False
            self._end_xr_frame()
        debug('ended xr frame')

    def _poll_xr_events(self):
        import xr
        while True:
            try:
                event_buffer = xr.poll_event(self._instance)
                event_type = xr.StructureType(event_buffer.type)
                if event_type == xr.StructureType.EVENT_DATA_SESSION_STATE_CHANGED:
                    self._on_session_state_changed(event_buffer)
                else:
                    debug('Got event', event_type)
            except xr.EventUnavailable:
                break

    def _on_session_state_changed(self, session_state_changed_event):
        import xr
        # TODO: it would be nice to avoid this horrible cast...
        import ctypes
        event = ctypes.cast(
            ctypes.byref(session_state_changed_event),
            ctypes.POINTER(xr.EventDataSessionStateChanged)).contents
        # TODO: enum property
        self._session_state = state = xr.SessionState(event.state)
        debug('Session state', state)
        if state == xr.SessionState.READY:
            sbinfo = xr.SessionBeginInfo(xr.ViewConfigurationType.PRIMARY_STEREO)
            xr.begin_session(self._session, sbinfo)
            self._ready_to_render = True
        elif state == xr.SessionState.STOPPING:
            xr.end_session(self._session)
            self._ready_to_render = False
            # After this it will transition to the IDLE state and from there
            # it will either go back to READY or EXITING.
            # No calls should be made to wait_frame, begin_frame, end_frame until ready.
        elif state == xr.SessionState.EXITING:
            self.shutdown()
            
    def _start_xr_frame(self):
        import xr
        if self._session_state in [
            xr.SessionState.READY,
            xr.SessionState.FOCUSED,
            xr.SessionState.SYNCHRONIZED,
            xr.SessionState.VISIBLE,
        ]:
            try:
                self._frame_state = xr.wait_frame(self._session,
                                                  frame_wait_info=xr.FrameWaitInfo())
                xr.begin_frame(self._session, xr.FrameBeginInfo())
                return True
            except xr.ResultException:
                error ('xr.wait_frame() or xr.begin_frame() failed')
                return False
                
        return False

    def _end_xr_frame(self):
#        from chimerax.graphics.opengl import GL        
#        GL.glFinish()

        layers = []
        if self._frame_state.should_render:
            for eye_index in range(2):
                layer_view = self._projection_layer_views[eye_index]
                eye_view = self._eye_view_states[eye_index]
                layer_view.fov = eye_view.fov
                layer_view.pose = eye_view.pose
            import ctypes
            layers = [ctypes.byref(self._projection_layer)]

        self._projection_layer.views = self._projection_layer_views

        import xr
        frame_end_info = xr.FrameEndInfo(
            display_time = self._frame_state.predicted_display_time,
            environment_blend_mode = xr.EnvironmentBlendMode.OPAQUE,
            layers = layers)
        xr.end_frame(self._session, frame_end_info)

    def _update_xr_views(self):
        import xr
        vs, evs = xr.locate_views(self._session,
                                  xr.ViewLocateInfo(
                                      view_configuration_type=xr.ViewConfigurationType.PRIMARY_STEREO,
                                      display_time=self._frame_state.predicted_display_time,
                                      space=self._projection_layer.space))
        vsf = vs.view_state_flags
        if (vsf & xr.VIEW_STATE_POSITION_VALID_BIT == 0
            or vsf & xr.VIEW_STATE_ORIENTATION_VALID_BIT == 0):
            return False  # There are no valid tracking poses for the views.
    
        self._eye_view_states = evs
        for eye_index, view_state in enumerate(evs):
            self.field_of_view[eye_index] = view_state.fov
            self.eye_pose[eye_index] = self._xr_pose_to_place(view_state.pose)

        return True
    
    def _xr_pose_to_place(self, xr_pose):
        from chimerax.geometry import quaternion_rotation
        x,y,z,w = xr_pose.orientation
        q = (w,x,y,z)
        return quaternion_rotation(q, xr_pose.position)

    def _create_action_set(self):
        import xr
        # Create an action set.
        action_set_info = xr.ActionSetCreateInfo(
            action_set_name="gameplay",
            localized_action_set_name="Gameplay",
            priority=0,
        )
        action_set = xr.create_action_set(self._instance, action_set_info)

        self._hand_path = {'left': self._xr_path("/user/hand/left"),
                           'right': self._xr_path("/user/hand/right")}

        self._actions = self._create_button_actions(action_set)
        
        pose_bindings = self._create_hand_pose_actions(action_set)
        khr_bindings = self._suggested_bindings([
            ('/user/hand/left/input/select/click', 'trigger'),
            ('/user/hand/right/input/select/click', 'trigger'),
            ('/user/hand/left/input/menu/click', 'menu'),
            ('/user/hand/right/input/menu/click', 'menu'),
        ])
        self._suggest_bindings(pose_bindings + khr_bindings,
                               "/interaction_profiles/khr/simple_controller")

        vive_bindings = self._suggested_bindings([
            ('/user/hand/left/input/trigger/click','trigger'),
            ('/user/hand/right/input/trigger/click','trigger'),
            ('/user/hand/left/input/squeeze/click', 'grip'),
            ('/user/hand/right/input/squeeze/click', 'grip'),
            ('/user/hand/left/input/menu/click', 'menu'),
            ('/user/hand/right/input/menu/click', 'menu'),
            ('/user/hand/left/input/trackpad/click', 'trackpad'),
            ('/user/hand/right/input/trackpad/click', 'trackpad'),
        ])
        self._suggest_bindings(pose_bindings + vive_bindings,
                               "/interaction_profiles/htc/vive_controller")

        oculus_bindings = self._suggested_bindings([
            ('/user/hand/left/input/trigger/value', 'trigger_value'),
            ('/user/hand/right/input/trigger/value', 'trigger_value'),
            ('/user/hand/left/input/squeeze/value', 'grip_value'),
            ('/user/hand/right/input/squeeze/value', 'grip_value'),
            ('/user/hand/left/input/thumbstick', 'thumbstick'),
            ('/user/hand/right/input/thumbstick', 'thumbstick'),
            ('/user/hand/left/input/x/click', 'A'),
            ('/user/hand/right/input/a/click', 'A'),
            ('/user/hand/left/input/y/click', 'menu'),
            ('/user/hand/right/input/b/click', 'menu'),
        ])
        self._suggest_bindings(pose_bindings + oculus_bindings,
                               "/interaction_profiles/oculus/touch_controller")

        from ctypes import pointer
        xr.attach_session_action_sets(
            session=self._session,
            attach_info=xr.SessionActionSetsAttachInfo(
                count_action_sets=1,
                action_sets=pointer(action_set),
            ),
        )
        return action_set

    def _create_hand_pose_actions(self, action_set):
        # Get the XrPath for the left and right hands.
        import xr

        # Create an input action getting the left and right hand poses.
        self._hand_pose_action = xr.create_action(
            action_set=action_set,
            create_info=xr.ActionCreateInfo(
                action_type=xr.ActionType.POSE_INPUT,
                action_name="hand_pose",
                localized_action_name="Hand Pose",
                count_subaction_paths=2,
                subaction_paths=[self._hand_path['left'], self._hand_path['right']],
            ),
        )

        # Suggest bindings
        bindings = [
            xr.ActionSuggestedBinding(self._hand_pose_action,
                                      self._xr_path("/user/hand/left/input/aim/pose")),
            xr.ActionSuggestedBinding(self._hand_pose_action,
                                      self._xr_path("/user/hand/right/input/aim/pose"))
        ]

        # Create action space
        left_action_space_info = xr.ActionSpaceCreateInfo(
            action=self._hand_pose_action,
            subaction_path=self._hand_path['left'],
        )
        assert left_action_space_info.pose_in_action_space.orientation.w == 1
        right_action_space_info = xr.ActionSpaceCreateInfo(
            action=self._hand_pose_action,
            subaction_path=self._hand_path['right'],
        )
        assert right_action_space_info.pose_in_action_space.orientation.w == 1
        self._hand_space = {
            'left' : xr.create_action_space(session=self._session,
                                            create_info=left_action_space_info),
            'right': xr.create_action_space(session=self._session,
                                            create_info=right_action_space_info)
        }

        return bindings

    def _xr_path(self, path):
        import xr
        return xr.string_to_path(self._instance, path)
    
    def _create_button_actions(self, action_set):
        actions = {}
        import xr
        both_hands = ['left', 'right']
        from xr import ActionType as t
        for button, hands, type in (
                ('trigger', both_hands, t.BOOLEAN_INPUT),
                ('trigger_value', both_hands, t.FLOAT_INPUT),
                ('grip', both_hands, t.BOOLEAN_INPUT),
                ('grip_value', both_hands, t.FLOAT_INPUT),
                ('menu', both_hands, t.BOOLEAN_INPUT),
                ('trackpad', both_hands, t.BOOLEAN_INPUT),
                ('A', both_hands, t.BOOLEAN_INPUT),
                ('thumbstick', both_hands, t.VECTOR2F_INPUT),
        ):
            action = xr.create_action(
                action_set=action_set,
                create_info=xr.ActionCreateInfo(
                    action_type=type,
                    action_name=button.lower(),
                    localized_action_name=button,
                    count_subaction_paths=len(hands),
                    subaction_paths=[self._hand_path[side] for side in hands],
                ),
            )
            actions[button] = Action(action, button, hands, type, self._hand_path)
        
        return actions

    def _suggested_bindings(self, path_to_action_names):
        bindings = []
        import xr
        for path, action_name in path_to_action_names:
            ca = self._actions[action_name]
            bindings.append(xr.ActionSuggestedBinding(ca.action, self._xr_path(path)))
        return bindings
    
    def _suggest_bindings(self, bindings, profile_path):
        import xr
        xr.suggest_interaction_profile_bindings(
            instance=self._instance,
            suggested_bindings=xr.InteractionProfileSuggestedBinding(
                interaction_profile=xr.string_to_path(self._instance, profile_path),
                count_suggested_bindings=len(bindings),
                suggested_bindings=(xr.ActionSuggestedBinding * len(bindings))(*bindings),
            ),
        )

    def _button_events(self):
        if not self._sync_actions():
            return []
        
        events = []
        for a in self._actions.values():
            events.extend(a.events(self._session))
                
        return events

    def _sync_actions(self):
        import xr
        if self._session_state != xr.SessionState.FOCUSED:
            return False
        active_action_set = xr.ActiveActionSet(self._action_set, xr.NULL_PATH)
        from ctypes import pointer
        xr.sync_actions(
            self._session,
            xr.ActionsSyncInfo(
                count_active_action_sets=1,
                active_action_sets=pointer(active_action_set)
            ),
        )
        return True

    def device_active(self, device_name):
        import xr
        if self._session_state != xr.SessionState.FOCUSED:
            return False

        pose_state = xr.get_action_state_pose(
            session=self._session,
            get_info=xr.ActionStateGetInfo(
                action=self._hand_pose_action,
                subaction_path=self._hand_path[device_name],
            ),
        )

        return pose_state.is_active

    def device_position(self, device_name):
        if not self.device_active(device_name):
            return None

        import xr
        space_location = xr.locate_space(
            space=self._hand_space[device_name],
            base_space=self._scene_space,
            time=self._frame_state.predicted_display_time,
        )
        loc_flags = space_location.location_flags
        if (loc_flags & xr.SPACE_LOCATION_POSITION_VALID_BIT == 0
            or loc_flags & xr.SPACE_LOCATION_ORIENTATION_VALID_BIT == 0):
            return None

        return self._xr_pose_to_place(space_location.pose)

    def _debug_callback(self, severity, _type, data, _user_data):
        d = data.contents
        # TODO structure properties to return unicode strings
        sev = self._debug_severity_string(severity)
        fname = d.function_name.decode()
        msg = d.message.decode()
        debug( f"{sev}: {fname}: {msg}")
        return True

    def _debug_severity_string(self, severity_flags):
        if severity_flags & 0x0001:
            return 'Verbose'
        if severity_flags & 0x0010:
            return 'Info'
        if severity_flags & 0x0100:
            return 'Warning'
        if severity_flags & 0x1000:
            return 'Error'
        return 'Critical'
        
    def shutdown(self):
        import xr
        for hs in self._hand_space.values():
            xr.destroy_space(hs)
        self._hand_space.clear()

        if self._action_set is not None:
            xr.destroy_action_set(self._action_set)
            self._action_set = None
        
        self._delete_framebuffers()

        # Delete projection layer, swapchains, session, system and instance.
        for swapchain in self._swapchains:
            xr.destroy_swapchain(swapchain)
        self._swapchains = []
#        self._projection_layer.destroy()  # Destroy method is missing
        self._projection_layer = None
        xr.destroy_space(self._scene_space)
        self._scene_space = None
        xr.destroy_session(self._session)
        self._session = None
        xr.destroy_instance(self._instance)
        self._instance = None


    def hmd_pose(self):
        # head to room coordinates.  None if not available
        e0, e1 = self.eye_pose
        shift = 0.5 * (e1.origin() - e0.origin())
        from chimerax.geometry import translation
        return translation(shift) * e0
    def eye_to_head_transform(self, eye):
        pass
    def projection_matrix(self, eye, z_near, z_far):
        pass
    def submit(self, eye, texture):
        # eye = 'left' or 'right'
        pass
    def hand_controllers(self):
        # Return list of (device_id, 'left' or 'right')
        return []
    def controller_left_or_right(self, device_index):
        # Return 'left' or 'right'
        return 'right'
    def controller_model_name(self, device_name):
        # 'vr_controller_vive_1_5' for vive pro
        # 'oculus_cv1_controller_right', 'oculus_cv1_controller_left'
        # 'oculus_rifts_controller_right', 'oculus_rifts_controller_left'
        return 'unknown'
    def controller_state(self, device_name):
        return None
    def device_type(self, device_index):
        # Returns 'controller', 'tracker', 'hmd', or 'unknown'
        return 'unknown'
    def find_tracker(self):
        # Return device id for connected "tracker" device or None
        return None
    TrackedDeviceActivated = 0
    TrackedDeviceDeactivated = 1
    ButtonTouchEvent = 4
    ButtonUntouchEvent = 5
    def poll_next_event(self):
        self._poll_xr_events()	# Update self._session_state to detect headset has lost focus
        q = self._event_queue
        q.extend(self._button_events())
        if len(q) == 0:
            return None
        e = q[0]
        del q[0]
        return e

class Action:
    def __init__(self, action, button, sides, type, hand_paths):
        self.action = action
        self.button = button
        self.sides = sides
        self.type = type	# xr.ActionType.BOOLEAN_INPUT or FLOAT_INPUT or VECTOR2F_INPUT
        self._hand_path = hand_paths

        self._float_press = 0.7
        self._float_release = 0.3
        self._float_state = {'left':0, 'right':0}

        self._xy_minimum = 0.1		# Minimum thumbstick value to generate an event
        
    def events(self, session):
        import xr
        if self.type == xr.ActionType.BOOLEAN_INPUT:
            return self._bool_events(session)
        elif self.type == xr.ActionType.FLOAT_INPUT:
            return self._float_events(session)
        elif self.type == xr.ActionType.VECTOR2F_INPUT:
            return self._xy_events(session)

    def _bool_events(self, session):
        events = []
        import xr
        for side in self.sides:
            b_state = xr.get_action_state_boolean(
                session=session,
                get_info=xr.ActionStateGetInfo(action = self.action,
                                               subaction_path=self._hand_path[side]))
            if b_state.is_active and b_state.changed_since_last_sync:
                state = ButtonEvent.BUTTON_PRESSED if b_state.current_state else ButtonEvent.BUTTON_RELEASED
                events.append(ButtonEvent(ButtonEvent.BUTTON_ID[self.button], state, side))
        return events

    def _float_events(self, session):
        events = []
        import xr
        for side in self.sides:
            f_state = xr.get_action_state_float(
                session=session,
                get_info=xr.ActionStateGetInfo(action = self.action,
                                               subaction_path=self._hand_path[side]))
            if f_state.is_active and f_state.changed_since_last_sync:
                value = f_state.current_state
                if value > self._float_press:
                    if self._float_state[side] < self._float_press:
                        events.append(ButtonEvent(ButtonEvent.BUTTON_ID[self.button],
                                                  ButtonEvent.BUTTON_PRESSED, side))
                elif value < self._float_release:
                    if self._float_state[side] > self._float_release:
                        events.append(ButtonEvent(ButtonEvent.BUTTON_ID[self.button],
                                                  ButtonEvent.BUTTON_RELEASED, side))
                self._float_state[side] = value
        return events

    def _xy_events(self, session):
        events = []
        import xr
        for side in self.sides:
            xy_state = xr.get_action_state_vector2f(
                session=session,
                get_info=xr.ActionStateGetInfo(action = self.action,
                                               subaction_path=self._hand_path[side]))
            if xy_state.is_active and xy_state.changed_since_last_sync:
                value = xy_state.current_state
                if abs(value.x) >= self._xy_minimum or abs(value.y) >= self._xy_minimum:
                    events.append(XYEvent(ButtonEvent.BUTTON_ID[self.button], (value.x,value.y), side))
        return events
    
class ButtonEvent:
    BUTTON_PRESSED = 'pressed'
    BUTTON_RELEASED = 'released'
    BUTTON_ID = {'menu':1, 'grip':2, 'grip_value':2, 'trigger': 33, 'trigger_value':33,
                 'trackpad':32, 'thumbstick':32, 'A':7}  # SteamVR ids
    def __init__(self, button, state, device_name):
        self.button = button
        self.state = state	# BUTTON_PRESSED or BUTTON_RELEASED
        self.device_name = device_name
    
class XYEvent:
    def __init__(self, button, xy, device_name):
        self.button = button
        self.xy = xy
        self.device_name = device_name

def error(*args):
    print(*args)
    
def debug(*args):
    pass
#    print(*args)

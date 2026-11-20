import bpy
import math
import time
import threading
from collections import deque
from .renderer import CursorRenderer

class CursorState:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CursorState, cls).__new__(cls)
            cls._instance._init_state()
        return cls._instance

    def _init_state(self):
        self.lock = threading.Lock()
        
        # Window-level position (Retina scale points/pixels)
        self.win_x = 800.0
        self.win_y = 600.0
        
        # Kinematic trajectory state
        self.start_x = 800.0
        self.start_y = 600.0
        self.target_x = 800.0
        self.target_y = 600.0
        self.motion_start_time = 0.0
        self.motion_duration = 0.35
        self.is_moving = False
        
        # Interaction modes: 'NORMAL', 'HOVER', 'CLICK', 'DRAGGING'
        self.interaction_mode = 'NORMAL'
        self.hover_active = False
        self.drag_active = False
        
        # Seamless Waypoint Queue
        self.waypoint_queue = deque()
        self.current_callback = None
        self.current_click_on_arrive = False
        
        # Visual FX (Click ripples)
        self.ripples = []
        
        # Status
        self.status = "IDLE"  # IDLE, RUNNING, PAUSED, STOPPED
        self.action = "Ready"
        self.step_index = 0
        self.total_steps = 0
        
        # Telemetry & Performance Tracking
        self.frame_times = deque(maxlen=60)
        self.last_frame_time = time.perf_counter()
        self.avg_fps = 60.0
        self.frame_jitter_ms = 0.0
        self.dispatch_latency_ms = 0.0
        self.dropped_frames = 0
        
        # Handlers and active state
        self.handlers = {}
        self.timer_handle = None
        self.is_active = False
        self.last_area_ptr = None
        
        self.stop_requested = False
        self.pause_requested = False

state = CursorState()

def _find_area_at(win_x, win_y):
    """Finds the Blender screen area containing the window coordinate."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.x <= win_x <= area.x + area.width and area.y <= win_y <= area.y + area.height:
                return area
    return None

def update_timer():
    """60 FPS high-precision kinematic update timer."""
    now = time.perf_counter()
    
    with state.lock:
        if not state.is_active:
            return None

        # Frame timing & jitter analysis
        dt = now - state.last_frame_time
        state.last_frame_time = now
        state.frame_times.append(dt)
        if len(state.frame_times) >= 10:
            avg_dt = sum(state.frame_times) / len(state.frame_times)
            state.avg_fps = 1.0 / avg_dt if avg_dt > 0 else 60.0
            state.frame_jitter_ms = max(abs(f - avg_dt) for f in state.frame_times) * 1000.0

        needs_redraw = False
        cur_x = state.win_x
        cur_y = state.win_y

        # Trajectory Interpolation
        if state.is_moving and not state.pause_requested:
            elapsed = now - state.motion_start_time
            dur = max(0.001, state.motion_duration)
            tau = min(1.0, max(0.0, elapsed / dur))

            # Minimum-Jerk Quintic Polynomial Easing: s(t) = 10t^3 - 15t^4 + 6t^5
            s = tau * tau * tau * (10.0 - 15.0 * tau + 6.0 * tau * tau)

            state.win_x = state.start_x + (state.target_x - state.start_x) * s
            state.win_y = state.start_y + (state.target_y - state.start_y) * s
            needs_redraw = True

            # Arrived at destination
            if tau >= 1.0:
                state.win_x = state.target_x
                state.win_y = state.target_y
                state.is_moving = False

                if state.current_click_on_arrive:
                    state.ripples.append({
                        "win_x": state.win_x,
                        "win_y": state.win_y,
                        "start_time": now,
                        "duration": 0.15
                    })
                    state.current_click_on_arrive = False

                cb = state.current_callback
                state.current_callback = None
                if cb:
                    try:
                        cb()
                    except Exception as e:
                        print(f"[Air Cursor] Callback error: {e}")

                # Next waypoint
                if state.waypoint_queue:
                    next_wp = state.waypoint_queue.popleft()
                    _start_motion_segment(
                        next_wp["target_x"],
                        next_wp["target_y"],
                        next_wp.get("duration"),
                        next_wp.get("click", False),
                        next_wp.get("hover", False),
                        next_wp.get("drag", False),
                        next_wp.get("action", ""),
                        next_wp.get("callback")
                    )

        # Update Ripples
        active_ripples = []
        for rip in state.ripples:
            if now - rip["start_time"] < rip.get("duration", 0.15):
                active_ripples.append(rip)
                needs_redraw = True
        state.ripples = active_ripples

        cur_x = state.win_x
        cur_y = state.win_y

    # Targeted Redraw Optimization
    if needs_redraw:
        cur_area = _find_area_at(cur_x, cur_y)
        prev_area = state.last_area_ptr

        if cur_area:
            cur_area.tag_redraw()
        if prev_area and prev_area != cur_area:
            prev_area.tag_redraw()

        state.last_area_ptr = cur_area

    return 0.016  # ~60 FPS

def _start_motion_segment(target_x, target_y, duration=None, click=False, hover=False, drag=False, action="", callback=None):
    now = time.perf_counter()
    dist = math.hypot(target_x - state.win_x, target_y - state.win_y)
    
    if duration is None:
        duration = min(0.48, max(0.18, 0.14 + 0.010 * math.sqrt(dist)))

    state.start_x = state.win_x
    state.start_y = state.win_y
    state.target_x = float(target_x)
    state.target_y = float(target_y)
    state.motion_start_time = now
    state.motion_duration = float(duration)
    state.is_moving = True
    state.hover_active = hover
    state.drag_active = drag
    state.current_click_on_arrive = click
    state.current_callback = callback
    if action:
        state.action = action

def move_cursor_to_win(win_x, win_y, action_text="", duration=None, click=False, hover=False, drag=False, callback=None):
    """Queues or starts smooth kinematic cursor movement."""
    with state.lock:
        if not state.is_active:
            start_operator()

        dispatch_time = time.perf_counter()
        if not state.is_moving:
            _start_motion_segment(win_x, win_y, duration, click, hover, drag, action_text, callback)
            state.dispatch_latency_ms = (time.perf_counter() - dispatch_time) * 1000.0
        else:
            state.waypoint_queue.append({
                "target_x": float(win_x),
                "target_y": float(win_y),
                "duration": duration,
                "click": click,
                "hover": hover,
                "drag": drag,
                "action": action_text,
                "callback": callback
            })

def click_target_win(win_x, win_y, action_text="", callback=None):
    """Glides to target, fires a 150ms tip ripple, and executes callback."""
    move_cursor_to_win(win_x, win_y, action_text=action_text, click=True, callback=callback)

def teleport_cursor_win(win_x, win_y, action_text=""):
    """Instantly sets position without animation (used for resets)."""
    with state.lock:
        state.win_x = float(win_x)
        state.win_y = float(win_y)
        state.target_x = float(win_x)
        state.target_y = float(win_y)
        state.is_moving = False
        state.waypoint_queue.clear()
        if action_text:
            state.action = action_text

    area = _find_area_at(win_x, win_y)
    if area:
        area.tag_redraw()

def register_draw_handlers():
    spaces_and_regions = [
        (bpy.types.SpaceView3D, 'WINDOW'),
        (bpy.types.SpaceView3D, 'UI'),
        (bpy.types.SpaceView3D, 'HEADER'),
        (bpy.types.SpaceOutliner, 'WINDOW'),
        (bpy.types.SpaceOutliner, 'HEADER'),
        (bpy.types.SpaceProperties, 'WINDOW'),
        (bpy.types.SpaceProperties, 'NAVIGATION_BAR'),
        (bpy.types.SpaceProperties, 'HEADER')
    ]
    for space_cls, reg_type in spaces_and_regions:
        key = (space_cls.__name__, reg_type)
        if key not in state.handlers:
            cb = (lambda s=space_cls.__name__, r=reg_type: CursorRenderer.draw_callback_for_region(s, r, state))
            try:
                h = space_cls.draw_handler_add(cb, (), reg_type, 'POST_PIXEL')
                state.handlers[key] = (space_cls, h, reg_type)
            except Exception:
                pass

def unregister_draw_handlers():
    for key, (space_cls, h, reg_type) in list(state.handlers.items()):
        try:
            space_cls.draw_handler_remove(h, reg_type)
        except Exception:
            pass
    state.handlers.clear()

def start_operator():
    with state.lock:
        state.is_active = True
        state.status = "RUNNING"
        state.stop_requested = False
        state.pause_requested = False
        state.last_frame_time = time.perf_counter()

    register_draw_handlers()

    if state.timer_handle is None:
        if not bpy.app.timers.is_registered(update_timer):
            bpy.app.timers.register(update_timer, first_interval=0.016, persistent=True)
            state.timer_handle = update_timer

    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            a.tag_redraw()

    return {"status": "started"}

def pause_operator():
    with state.lock:
        state.pause_requested = True
        state.status = "PAUSED"
    return {"status": "paused"}

def resume_operator():
    with state.lock:
        state.pause_requested = False
        state.status = "RUNNING"
        state.motion_start_time = time.perf_counter()
    return {"status": "resumed"}

def emergency_stop():
    with state.lock:
        state.stop_requested = True
        state.pause_requested = False
        state.status = "STOPPED"
        state.is_active = False
        state.waypoint_queue.clear()
        state.ripples.clear()

    unregister_draw_handlers()

    if state.timer_handle is not None:
        try:
            if bpy.app.timers.is_registered(update_timer):
                bpy.app.timers.unregister(update_timer)
        except Exception:
            pass
        state.timer_handle = None

    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            a.tag_redraw()

    return {"status": "stopped"}

def get_telemetry():
    with state.lock:
        return {
            "status": state.status,
            "win_x": round(state.win_x, 1),
            "win_y": round(state.win_y, 1),
            "ai_x": round(state.win_x, 1),
            "ai_y": round(state.win_y, 1),
            "target_win_x": round(state.target_x, 1),
            "target_win_y": round(state.target_y, 1),
            "target_x": round(state.target_x, 1),
            "target_y": round(state.target_y, 1),
            "is_moving": state.is_moving,
            "queue_depth": len(state.waypoint_queue),
            "interaction_mode": state.interaction_mode,
            "avg_fps": round(state.avg_fps, 1),
            "frame_jitter_ms": round(state.frame_jitter_ms, 2),
            "dispatch_latency_ms": round(state.dispatch_latency_ms, 3),
            "action": state.action,
            "step_index": state.step_index,
            "total_steps": state.total_steps,
            "is_active": state.is_active
        }

# Sidebar Panel
class VIEW3D_PT_AirCursor(bpy.types.Panel):
    bl_label = "Air Cursor"
    bl_idname = "VIEW3D_PT_air_cursor"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AI Cursor"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        tel = get_telemetry()

        box = col.box()
        b_row = box.row()
        b_row.label(text=f"Status: {tel['status']}", icon='PLAY' if tel['status'] == 'RUNNING' else 'PAUSE')
        box.label(text=f"FPS: {tel['avg_fps']} | Jitter: {tel['frame_jitter_ms']}ms")
        box.label(text=f"Latency: {tel['dispatch_latency_ms']}ms")

        col.separator()
        row = col.row(align=True)
        row.operator("aircursor.start", text="Start", icon='PLAY')
        row.operator("aircursor.pause", text="Pause", icon='PAUSE')
        row.operator("aircursor.resume", text="Resume", icon='FORWARD')
        col.separator()
        col.operator("aircursor.emergency_stop", text="Emergency Stop", icon='CANCEL')

class AIRCURSOR_OT_Start(bpy.types.Operator):
    bl_idname = "aircursor.start"
    bl_label = "Start Air Cursor"
    def execute(self, context):
        start_operator()
        return {'FINISHED'}

class AIRCURSOR_OT_Pause(bpy.types.Operator):
    bl_idname = "aircursor.pause"
    bl_label = "Pause Air Cursor"
    def execute(self, context):
        pause_operator()
        return {'FINISHED'}

class AIRCURSOR_OT_Resume(bpy.types.Operator):
    bl_idname = "aircursor.resume"
    bl_label = "Resume Air Cursor"
    def execute(self, context):
        resume_operator()
        return {'FINISHED'}

class AIRCURSOR_OT_EmergencyStop(bpy.types.Operator):
    bl_idname = "aircursor.emergency_stop"
    bl_label = "Emergency Stop"
    def execute(self, context):
        emergency_stop()
        return {'FINISHED'}

classes = (
    VIEW3D_PT_AirCursor,
    AIRCURSOR_OT_Start,
    AIRCURSOR_OT_Pause,
    AIRCURSOR_OT_Resume,
    AIRCURSOR_OT_EmergencyStop
)

def register():
    for c in classes:
        try:
            bpy.utils.register_class(c)
        except Exception:
            pass

def unregister():
    for c in reversed(classes):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass
    emergency_stop()

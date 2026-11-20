try:
    import bpy
    BPY_AVAILABLE = True
except ImportError:
    bpy = None
    BPY_AVAILABLE = False
import math
import time
import threading
from collections import deque
from typing import Any, Callable, Optional, Union, Tuple, List

from .kinematics import minimum_jerk_poly, calculate_adaptive_duration
from .renderer import CursorRenderer
from .pipeline import Action, ActionQueue, resolve_target
from .server import CommandServer

class CursorState:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CursorState, cls).__new__(cls)
            cls._instance._init_state()
        return cls._instance

    def _init_state(self):
        # Re-entrant lock prevents deadlocks when callbacks query telemetry or schedule actions
        self.lock = threading.RLock()
        
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
        
        # Interaction modes
        self.interaction_mode = 'NORMAL'  # NORMAL, HOVER, CLICK, DRAGGING
        self.hover_active = False
        self.drag_active = False
        
        # Action pipeline & Queue
        self.action_queue = ActionQueue()
        self.current_action: Optional[Action] = None
        
        # Visual FX (Click ripples)
        self.ripples = []
        
        # Configuration
        self.config = {
            "cursor_scale": 1.0,
            "accent_color": (0.0, 0.88, 1.0, 0.65),
            "speed_multiplier": 1.0,
            "show_shadow": True,
            "show_ripples": True,
            "show_glow": True,
            "ripple_duration": 0.15,
            "server_port": 9880,
            "enable_server": True
        }
        
        # Status & Telemetry
        self.status = "IDLE"  # IDLE, RUNNING, PAUSED, STOPPED
        self.action = "Ready"
        self.completed_actions_count = 0
        
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
        
        # Socket Command Server
        self.server: Optional[CommandServer] = None

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
    action_to_execute = None
    needs_redraw = False
    
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

        cur_x = state.win_x
        cur_y = state.win_y

        # Trajectory Interpolation
        if state.is_moving and not state.pause_requested:
            elapsed = now - state.motion_start_time
            dur = max(0.001, state.motion_duration)
            tau = min(1.0, max(0.0, elapsed / dur))

            # Minimum-Jerk Quintic Polynomial Easing: s(t) = 10t^3 - 15t^4 + 6t^5
            s = minimum_jerk_poly(tau)
            state.win_x = state.start_x + (state.target_x - state.start_x) * s
            state.win_y = state.start_y + (state.target_y - state.start_y) * s
            needs_redraw = True

            # Arrived at destination
            if tau >= 1.0:
                state.win_x = state.target_x
                state.win_y = state.target_y
                state.is_moving = False

                curr = state.current_action
                state.current_action = None

                if curr is not None:
                    if curr.click and state.config.get("show_ripples", True):
                        state.ripples.append({
                            "win_x": state.win_x,
                            "win_y": state.win_y,
                            "start_time": now,
                            "duration": state.config.get("ripple_duration", 0.15)
                        })
                    action_to_execute = curr

        # If idle and actions are queued, begin next action immediately
        if not state.is_moving and not state.pause_requested:
            next_action = state.action_queue.pop_next()
            if next_action is not None:
                _start_action(next_action)
                needs_redraw = True

        # Update Ripples
        active_ripples = []
        for rip in state.ripples:
            if now - rip["start_time"] < rip.get("duration", 0.15):
                active_ripples.append(rip)
                needs_redraw = True
        state.ripples = active_ripples

        cur_x = state.win_x
        cur_y = state.win_y

    # Execute arrival action OUTSIDE the lock to ensure re-entrancy and non-blocking timers
    if action_to_execute is not None:
        try:
            action_to_execute.execute()
        except Exception as e:
            print(f"[Air Cursor] Action execution error: {e}")
        with state.lock:
            state.completed_actions_count += 1
            # Check if queue has next action to start immediately with zero delay
            if not state.is_moving and not state.pause_requested:
                next_action = state.action_queue.pop_next()
                if next_action is not None:
                    _start_action(next_action)
                    needs_redraw = True

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

def _start_action(action: Action):
    """Initializes motion towards an action's target coordinates."""
    now = time.perf_counter()
    target_x = float(action.resolved_x)
    target_y = float(action.resolved_y)
    
    speed_mult = state.config.get("speed_multiplier", 1.0)
    dur = action.duration
    if dur is None:
        dur = calculate_adaptive_duration(state.win_x, state.win_y, target_x, target_y, speed_multiplier=speed_mult)

    state.start_x = state.win_x
    state.start_y = state.win_y
    state.target_x = target_x
    state.target_y = target_y
    state.motion_start_time = now
    state.motion_duration = float(dur)
    state.is_moving = True
    state.hover_active = action.hover
    state.drag_active = action.drag
    state.action = action.action_text
    state.current_action = action
    action.status = "MOVING"

# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def enqueue_action(target: Any,
                   action_type: str = "MOVE",
                   duration: Optional[float] = None,
                   action_text: str = "",
                   hover: bool = False,
                   drag: bool = False,
                   operator_func: Optional[Callable[[], Any]] = None,
                   on_complete: Optional[Callable[[Action], None]] = None) -> Action:
    """
    Enqueues a synchronized action in the Air Cursor pipeline.
    The operator_func executes on Blender's main thread ONLY after the cursor arrives at the target.
    """
    act = Action(
        target=target,
        action_type=action_type,
        duration=duration,
        action_text=action_text,
        hover=hover,
        drag=drag,
        operator_func=operator_func,
        on_complete=on_complete
    )
    with state.lock:
        if not state.is_active:
            start_operator()
        t_disp = time.perf_counter()
        state.action_queue.enqueue(act)
        state.dispatch_latency_ms = (time.perf_counter() - t_disp) * 1000.0
    return act

def dispatch_action_sequence(actions: List[Action]):
    """Enqueues a sequence of actions executed continuously without pauses."""
    with state.lock:
        if not state.is_active:
            start_operator()
        for act in actions:
            state.action_queue.enqueue(act)

def move_cursor_to_win(win_x: float, win_y: float, action_text: str = "",
                       duration: Optional[float] = None, click: bool = False,
                       hover: bool = False, drag: bool = False,
                       callback: Optional[Callable[[], Any]] = None) -> Action:
    """Queues smooth kinematic cursor movement to window coordinates."""
    act_type = "CLICK" if click else "MOVE"
    return enqueue_action(
        target=(win_x, win_y),
        action_type=act_type,
        duration=duration,
        action_text=action_text,
        hover=hover,
        drag=drag,
        operator_func=callback
    )

def click_target_win(win_x: float, win_y: float, action_text: str = "",
                     callback: Optional[Callable[[], Any]] = None) -> Action:
    """Glides to target, fires a 150ms tip ripple, and executes callback on arrival."""
    return move_cursor_to_win(win_x, win_y, action_text=action_text, click=True, callback=callback)

def teleport_cursor_win(win_x: float, win_y: float, action_text: str = ""):
    """Instantly sets position without animation (used for test resets)."""
    with state.lock:
        state.win_x = float(win_x)
        state.win_y = float(win_y)
        state.target_x = float(win_x)
        state.target_y = float(win_y)
        state.is_moving = False
        state.action_queue.clear()
        state.current_action = None
        if action_text:
            state.action = action_text

    area = _find_area_at(win_x, win_y)
    if area:
        area.tag_redraw()

def get_telemetry() -> dict:
    """Returns real-time performance and status metrics."""
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
            "queue_depth": state.action_queue.size(),
            "interaction_mode": state.interaction_mode,
            "avg_fps": round(state.avg_fps, 1),
            "frame_jitter_ms": round(state.frame_jitter_ms, 2),
            "dispatch_latency_ms": round(state.dispatch_latency_ms, 3),
            "action": state.action,
            "completed_actions": state.completed_actions_count,
            "is_active": state.is_active
        }

def _server_dispatch_handler(payload: dict) -> dict:
    """Handles JSON commands arriving over the built-in CommandServer."""
    cmd = payload.get("cmd", payload.get("type", "")).lower()
    
    if cmd in ("action", "enqueue"):
        target = payload.get("target")
        act_type = payload.get("action_type", "MOVE")
        dur = payload.get("duration")
        text = payload.get("action_text", "")
        code_to_exec = payload.get("code")
        
        op_fn = None
        if code_to_exec:
            def runner():
                ns = {"bpy": bpy, "air_cursor": state}
                exec(code_to_exec, ns)
            op_fn = runner

        act = enqueue_action(target=target, action_type=act_type, duration=dur, action_text=text, operator_func=op_fn)
        return {"status": "ok", "action_id": act.action_id}

    elif cmd == "move":
        x, y = resolve_target(payload.get("target", (payload.get("x", 800), payload.get("y", 600))))
        dur = payload.get("duration")
        move_cursor_to_win(x, y, action_text=payload.get("action_text", ""), duration=dur)
        return {"status": "ok", "x": x, "y": y}

    elif cmd == "click":
        x, y = resolve_target(payload.get("target", (payload.get("x", 800), payload.get("y", 600))))
        click_target_win(x, y, action_text=payload.get("action_text", ""))
        return {"status": "ok", "x": x, "y": y}

    elif cmd == "teleport":
        x, y = resolve_target(payload.get("target", (payload.get("x", 800), payload.get("y", 600))))
        teleport_cursor_win(x, y, action_text=payload.get("action_text", ""))
        return {"status": "ok", "x": x, "y": y}

    elif cmd == "telemetry":
        return {"status": "ok", "telemetry": get_telemetry()}

    elif cmd == "pause":
        return pause_operator()

    elif cmd == "resume":
        return resume_operator()

    elif cmd == "start":
        return start_operator()

    elif cmd == "stop":
        return emergency_stop()

    elif cmd == "execute_code":
        code_str = payload.get("params", {}).get("code", "") or payload.get("code", "")
        ns = {"bpy": bpy}
        exec(code_str, ns)
        return {"status": "success", "result": {"executed": True}}

    return {"status": "error", "message": f"Unknown command: {cmd}"}

# --------------------------------------------------------------------------
# Lifecycle Management
# --------------------------------------------------------------------------

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

    # Start built-in socket command server if enabled
    if state.config.get("enable_server", True) and state.server is None:
        port = state.config.get("server_port", 9880)
        state.server = CommandServer(port=port)
        state.server.start(_server_dispatch_handler)

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
        state.action_queue.clear()
        state.current_action = None
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

def shutdown_server():
    """Stops the socket command server when unregistering the add-on."""
    if state.server is not None:
        try:
            state.server.stop()
        except Exception:
            pass
        state.server = None

# --------------------------------------------------------------------------
# UI Sidebar Panel & Operators
# --------------------------------------------------------------------------

if BPY_AVAILABLE:
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
            box.label(text=f"Queue: {tel['queue_depth']} actions")

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
else:
    classes = ()

def register():
    if not BPY_AVAILABLE:
        return
    for c in classes:
        try:
            bpy.utils.register_class(c)
        except Exception:
            pass

def unregister():
    if not BPY_AVAILABLE:
        return
    emergency_stop()
    shutdown_server()
    for c in reversed(classes):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass

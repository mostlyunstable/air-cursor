"""
Air Cursor: Unified Action-to-Cursor Pipeline & Dynamic Target Resolver.
Guarantees continuous synchronization between cursor animation and Blender operation dispatch.
"""

import time
import threading
from collections import deque
from typing import Any, Callable, Optional, Union, Tuple

try:
    import bpy
    BPY_AVAILABLE = True
except ImportError:
    bpy = None
    BPY_AVAILABLE = False

class Action:
    """Represents a synchronized unit of work in the Air Cursor pipeline."""
    def __init__(self,
                 target: Any,
                 action_type: str = "MOVE",
                 duration: Optional[float] = None,
                 action_text: str = "",
                 hover: bool = False,
                 drag: bool = False,
                 operator_func: Optional[Callable[[], Any]] = None,
                 on_complete: Optional[Callable[['Action'], None]] = None):
        self.action_id = f"act_{time.time_ns()}"
        self.target = target
        self.action_type = action_type.upper()  # MOVE, CLICK, HOVER, DRAG
        self.duration = duration
        self.action_text = action_text or f"{self.action_type} -> {target}"
        self.hover = hover or (self.action_type == "HOVER")
        self.drag = drag or (self.action_type == "DRAG")
        self.click = (self.action_type == "CLICK")
        self.operator_func = operator_func
        self.on_complete = on_complete
        
        # Lifecycle state
        self.resolved_x: float = 0.0
        self.resolved_y: float = 0.0
        self.status = "PENDING"  # PENDING, MOVING, EXECUTING, COMPLETED, FAILED
        self.result: Any = None
        self.error: Optional[str] = None
        self.created_at = time.perf_counter()
        self.completed_at: Optional[float] = None

    def execute(self) -> Any:
        """Executes the associated Blender operation on the main thread."""
        self.status = "EXECUTING"
        if self.operator_func is not None:
            try:
                self.result = self.operator_func()
                self.status = "COMPLETED"
            except Exception as e:
                self.error = str(e)
                self.status = "FAILED"
                print(f"[Air Cursor] Action {self.action_id} error: {e}")
        else:
            self.status = "COMPLETED"
        
        self.completed_at = time.perf_counter()
        if self.on_complete is not None:
            try:
                self.on_complete(self)
            except Exception as e:
                print(f"[Air Cursor] on_complete callback error: {e}")
        return self.result

def resolve_target(target: Any) -> Tuple[float, float]:
    """
    Dynamically resolves a target specification into Blender window coordinates (x, y).
    
    Supported formats:
    - (x, y) or [x, y]: Explicit coordinates
    - {"x": ..., "y": ...}: Dict coordinates
    - "VIEW_3D": Center of the 3D Viewport
    - "OUTLINER": Center of the Outliner editor
    - "PROPERTIES": Center of the Properties editor
    - ("AREA", "VIEW_3D", "UI"): Center of N-panel in 3D Viewport
    - ("AREA", "VIEW_3D", "HEADER"): Center of 3D Viewport header
    - ("AREA", "PROPERTIES", "NAVIGATION_BAR"): Tab column of Properties
    """
    # 1. Explicit tuple / list coordinates
    if isinstance(target, (tuple, list)) and len(target) == 2 and isinstance(target[0], (int, float)):
        return (float(target[0]), float(target[1]))
    
    # 2. Dict with x, y
    if isinstance(target, dict) and "x" in target and "y" in target:
        return (float(target["x"]), float(target["y"]))

    # 3. Dynamic Blender Area / Region resolution
    if BPY_AVAILABLE and hasattr(bpy, "context") and hasattr(bpy.context, "window_manager"):
        wm = getattr(bpy.context, "window_manager", None)
        if wm and wm.windows:
            window = wm.windows[0]
            screen = getattr(window, "screen", None)
            if screen and hasattr(screen, "areas"):
                # Handle ("AREA", area_type, [region_type])
                area_type = None
                region_type = None
                if isinstance(target, str):
                    area_type = target.upper()
                elif isinstance(target, (tuple, list)):
                    if len(target) >= 2 and target[0] == "AREA":
                        area_type = target[1].upper()
                        if len(target) >= 3:
                            region_type = target[2].upper()

                if area_type:
                    for area in screen.areas:
                        if area.type == area_type:
                            if region_type:
                                for reg in area.regions:
                                    if reg.type == region_type:
                                        return (
                                            float(reg.x + reg.width / 2.0),
                                            float(reg.y + reg.height / 2.0)
                                        )
                            # Default to area center
                            return (
                                float(area.x + area.width / 2.0),
                                float(area.y + area.height / 2.0)
                            )

    # Fallback default if resolution fails
    if isinstance(target, (tuple, list)) and len(target) == 2:
        return (float(target[0]), float(target[1]))
    
    # Sensible window center fallback
    return (800.0, 600.0)

class ActionQueue:
    """Thread-safe queue managing pending actions."""
    def __init__(self):
        self._lock = threading.RLock()
        self._queue = deque()

    def enqueue(self, action: Action):
        with self._lock:
            # Resolve target coordinates upon enqueue
            rx, ry = resolve_target(action.target)
            action.resolved_x = rx
            action.resolved_y = ry
            self._queue.append(action)

    def pop_next(self) -> Optional[Action]:
        with self._lock:
            if self._queue:
                return self._queue.popleft()
            return None

    dequeue = pop_next

    def peek(self) -> Optional[Action]:
        with self._lock:
            if self._queue:
                return self._queue[0]
            return None

    def clear(self):
        with self._lock:
            self._queue.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._queue) == 0

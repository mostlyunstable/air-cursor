"""
Air Cursor: Autonomous Dual-Cursor System for Blender.
Provides an independent AI pointer with minimum-jerk kinematics and 100% human input isolation.
"""

bl_info = {
    "name": "Air Cursor",
    "author": "Mayank Kumar",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > AI Cursor",
    "description": "Autonomous AI cursor operating inside Blender with minimum-jerk kinematics and human input isolation",
    "category": "3D View",
}

from .core import (
    register as register_core,
    unregister as unregister_core,
    start_operator,
    pause_operator,
    resume_operator,
    emergency_stop,
    move_cursor_to_win,
    click_target_win,
    teleport_cursor_win,
    get_telemetry,
    state
)

def register():
    register_core()

def unregister():
    unregister_core()

if __name__ == "__main__":
    register()

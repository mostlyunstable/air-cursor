"""
Air Cursor: Autonomous Dual-Cursor System for Blender.
Provides an independent AI pointer with minimum-jerk kinematics and human input isolation.
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

try:
    import bpy
    BPY_AVAILABLE = True
except ImportError:
    bpy = None
    BPY_AVAILABLE = False

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
    enqueue_action,
    dispatch_action_sequence,
    get_telemetry,
    state
)
from .pipeline import Action, ActionQueue, resolve_target
from .kinematics import minimum_jerk_poly, calculate_adaptive_duration

if BPY_AVAILABLE:
    class AirCursorPreferences(bpy.types.AddonPreferences):
        bl_idname = __package__ or "air_cursor"

        cursor_scale: bpy.props.FloatProperty(
            name="Cursor Scale",
            description="Scaling factor for AI cursor rendering",
            default=1.0,
            min=0.5,
            max=3.0,
            update=lambda s, c: state.config.update({"cursor_scale": s.cursor_scale})
        )

        accent_color: bpy.props.FloatVectorProperty(
            name="Accent Color",
            subtype='COLOR',
            size=4,
            default=(0.0, 0.88, 1.0, 0.65),
            description="Color tint and opacity for cursor border glow and ripples",
            update=lambda s, c: state.config.update({"accent_color": tuple(s.accent_color)})
        )

        speed_multiplier: bpy.props.FloatProperty(
            name="Speed Multiplier",
            description="Kinematic duration multiplier (lower is faster)",
            default=1.0,
            min=0.2,
            max=5.0,
            update=lambda s, c: state.config.update({"speed_multiplier": s.speed_multiplier})
        )

        show_shadow: bpy.props.BoolProperty(
            name="Render Shadow",
            default=True,
            update=lambda s, c: state.config.update({"show_shadow": s.show_shadow})
        )

        show_ripples: bpy.props.BoolProperty(
            name="Click Ripples",
            default=True,
            update=lambda s, c: state.config.update({"show_ripples": s.show_ripples})
        )

        show_glow: bpy.props.BoolProperty(
            name="Hover Glow",
            default=True,
            update=lambda s, c: state.config.update({"show_glow": s.show_glow})
        )

        server_port: bpy.props.IntProperty(
            name="Server Port",
            description="TCP socket port for external agent communication",
            default=9880,
            min=1024,
            max=65535,
            update=lambda s, c: state.config.update({"server_port": s.server_port})
        )

        def draw(self, context):
            layout = self.layout
            col = layout.column(align=False)
            col.prop(self, "cursor_scale")
            col.prop(self, "accent_color")
            col.prop(self, "speed_multiplier")
            col.separator()
            row = col.row()
            row.prop(self, "show_shadow")
            row.prop(self, "show_ripples")
            row.prop(self, "show_glow")
            col.separator()
            col.prop(self, "server_port")

def register():
    if not BPY_AVAILABLE:
        return
    try:
        bpy.utils.register_class(AirCursorPreferences)
    except Exception:
        pass
    register_core()

def unregister():
    if not BPY_AVAILABLE:
        return
    unregister_core()
    try:
        bpy.utils.unregister_class(AirCursorPreferences)
    except Exception:
        pass

__all__ = [
    "register",
    "unregister",
    "start_operator",
    "pause_operator",
    "resume_operator",
    "emergency_stop",
    "move_cursor_to_win",
    "click_target_win",
    "teleport_cursor_win",
    "enqueue_action",
    "dispatch_action_sequence",
    "resolve_target",
    "get_telemetry",
    "state",
    "Action",
    "ActionQueue",
    "minimum_jerk_poly",
    "calculate_adaptive_duration"
]

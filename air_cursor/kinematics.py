"""
Air Cursor: Mathematical Kinematics Engine.
Implements biological minimum-jerk polynomial easing and adaptive trajectory scaling.
Pure Python module with zero external dependencies (unit-testable outside Blender).
"""

import math

def minimum_jerk_poly(tau: float) -> float:
    """
    Computes normalized displacement s(tau) for normalized time tau in [0, 1].
    Polynomial: s(t) = 10t^3 - 15t^4 + 6t^5
    Boundary conditions:
        s(0) = 0, s(1) = 1
        s'(0) = 0, s'(1) = 0 (zero endpoint velocity)
        s''(0) = 0, s''(1) = 0 (zero endpoint acceleration)
    """
    t = min(1.0, max(0.0, float(tau)))
    return t * t * t * (10.0 - 15.0 * t + 6.0 * t * t)

def minimum_jerk_velocity(tau: float, duration: float) -> float:
    """
    Computes instantaneous velocity ds/dt at normalized time tau.
    s'(t) = (30t^2 - 60t^3 + 30t^4) / duration
    Peak velocity occurs at tau = 0.5: s'(0.5) = 1.875 / duration
    """
    if duration <= 0:
        return 0.0
    t = min(1.0, max(0.0, float(tau)))
    return (30.0 * t * t - 60.0 * t * t * t + 30.0 * t * t * t * t) / duration

def interpolate_position(start_x: float, start_y: float,
                         target_x: float, target_y: float,
                         tau: float) -> tuple[float, float]:
    """Interpolates 2D coordinates along the minimum-jerk trajectory."""
    s = minimum_jerk_poly(tau)
    cur_x = start_x + (target_x - start_x) * s
    cur_y = start_y + (target_y - start_y) * s
    return (cur_x, cur_y)

def calculate_adaptive_duration(start_x: float, start_y: float,
                                target_x: float, target_y: float,
                                speed_multiplier: float = 1.0,
                                min_duration: float = 0.18,
                                max_duration: float = 0.48) -> float:
    """
    Calculates natural human-like duration scaling with Euclidean distance.
    Formula: T = clamp(min_dur, max_dur, 0.14 + 0.010 * sqrt(distance)) / speed_multiplier
    Short micro-moves (50px): ~0.18s
    Long cross-editor moves (2000px): ~0.48s
    """
    dist = math.hypot(target_x - start_x, target_y - start_y)
    base_duration = min(max_duration, max(min_duration, 0.14 + 0.010 * math.sqrt(dist)))
    mult = max(0.1, float(speed_multiplier))
    return base_duration / mult

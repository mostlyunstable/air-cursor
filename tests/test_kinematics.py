"""
Unit tests for Air Cursor minimum-jerk kinematics engine.
Runs standalone without any bpy dependencies.
"""

import unittest
import math
import sys
import os

# Add parent directory to path so air_cursor can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from air_cursor.kinematics import minimum_jerk_poly, minimum_jerk_velocity, calculate_adaptive_duration


class TestKinematics(unittest.TestCase):

    def test_boundary_values(self):
        """Boundary values of normalized polynomial must be exact."""
        self.assertAlmostEqual(minimum_jerk_poly(0.0), 0.0, places=6)
        self.assertAlmostEqual(minimum_jerk_poly(1.0), 1.0, places=6)
        self.assertAlmostEqual(minimum_jerk_poly(0.5), 0.5, places=6)

    def test_clamping(self):
        """Values outside [0, 1] must be clamped."""
        self.assertAlmostEqual(minimum_jerk_poly(-0.5), 0.0, places=6)
        self.assertAlmostEqual(minimum_jerk_poly(1.5), 1.0, places=6)

    def test_monotonicity(self):
        """Polynomial curve must be strictly monotonically non-decreasing."""
        steps = 100
        prev = 0.0
        for i in range(1, steps + 1):
            tau = i / float(steps)
            curr = minimum_jerk_poly(tau)
            self.assertGreaterEqual(curr, prev)
            prev = curr

    def test_zero_boundary_velocity(self):
        """Velocity at boundary conditions (tau=0 and tau=1) must be zero."""
        v_start = minimum_jerk_velocity(0.0, 1.0)
        v_end = minimum_jerk_velocity(1.0, 1.0)
        self.assertAlmostEqual(v_start, 0.0, places=6)
        self.assertAlmostEqual(v_end, 0.0, places=6)

    def test_peak_velocity(self):
        """Peak velocity occurs at tau = 0.5 and equals 1.875 / duration."""
        dur = 0.4
        v_mid = minimum_jerk_velocity(0.5, dur)
        expected_v = 1.875 / dur
        self.assertAlmostEqual(v_mid, expected_v, places=4)

    def test_adaptive_duration_scaling(self):
        """Duration increases logarithmically with distance and scales with multiplier."""
        # Zero distance
        d0 = calculate_adaptive_duration(100, 100, 100, 100, min_duration=0.15)
        self.assertAlmostEqual(d0, 0.15, places=4)

        # 500 px movement
        d500 = calculate_adaptive_duration(0, 0, 300, 400) # hypot is 500
        self.assertGreater(d500, 0.15)
        self.assertLessEqual(d500, 0.65)

        # Speed multiplier scaling: 2.0x speed cuts duration in half; 0.5x speed doubles duration
        d_fast = calculate_adaptive_duration(0, 0, 300, 400, speed_multiplier=2.0)
        self.assertAlmostEqual(d_fast, d500 / 2.0, places=4)

        d_slow = calculate_adaptive_duration(0, 0, 300, 400, speed_multiplier=0.5)
        self.assertAlmostEqual(d_slow, d500 / 0.5, places=4)


if __name__ == '__main__':
    unittest.main()

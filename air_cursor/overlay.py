"""
Air Cursor: macOS Cocoa Click-Through Floating Overlay Window.
Renders an independent floating AI pointer above Blender on macOS without stealing or intercepting human input events.
"""

import sys
import os
import math
import time
import threading

try:
    import AppKit
    from AppKit import (
        NSApplication, NSWindow, NSView, NSColor, NSRect, NSPoint, NSSize,
        NSWindowStyleMaskBorderless, NSBackingStoreBuffered, NSBezierPath,
        NSTimer, NSRunLoop, NSDefaultRunLoopMode, NSStatusWindowLevel
    )
    COCOA_AVAILABLE = True
except ImportError:
    COCOA_AVAILABLE = False

class OverlayState:
    def __init__(self):
        self.lock = threading.Lock()
        self.ai_x = 400.0
        self.ai_y = 300.0
        self.target_x = 400.0
        self.target_y = 300.0
        self.action_text = "Idle"
        self.ripples = []
        self.running = True

state = OverlayState()

if COCOA_AVAILABLE:
    class CursorOverlayView(NSView):
        def drawRect_(self, rect):
            with state.lock:
                ai_x = state.ai_x
                ai_y = state.ai_y
                ripples = list(state.ripples)

            frame_h = self.frame().size.height
            cocoa_y = frame_h - ai_y

            # 1. Click Ripples
            for rip in ripples:
                r = rip["radius"]
                a = rip["alpha"]
                r_path = NSBezierPath.bezierPathWithOvalInRect_(
                    NSRect(NSPoint(rip["x"] - r, frame_h - rip["y"] - r), NSSize(r * 2, r * 2))
                )
                NSColor.colorWithCalibratedRed_green_blue_alpha_(0.0, 0.9, 1.0, a).setStroke()
                r_path.setLineWidth_(1.5)
                r_path.stroke()

            # 2. Cyan Pointer Arrow
            cursor_path = NSBezierPath.bezierPath()
            cursor_path.moveToPoint_(NSPoint(ai_x, cocoa_y))
            cursor_path.lineToPoint_(NSPoint(ai_x + 14.0, cocoa_y - 14.0))
            cursor_path.lineToPoint_(NSPoint(ai_x + 6.0, cocoa_y - 14.0))
            cursor_path.lineToPoint_(NSPoint(ai_x + 10.0, cocoa_y - 22.0))
            cursor_path.lineToPoint_(NSPoint(ai_x + 7.0, cocoa_y - 23.5))
            cursor_path.lineToPoint_(NSPoint(ai_x + 3.0, cocoa_y - 15.5))
            cursor_path.lineToPoint_(NSPoint(ai_x, cocoa_y - 18.0))
            cursor_path.closePath()

            # Shadow
            sh_path = NSBezierPath.bezierPath()
            sh_path.moveToPoint_(NSPoint(ai_x + 1.5, cocoa_y - 2.0))
            sh_path.lineToPoint_(NSPoint(ai_x + 15.5, cocoa_y - 16.0))
            sh_path.lineToPoint_(NSPoint(ai_x + 7.5, cocoa_y - 16.0))
            sh_path.lineToPoint_(NSPoint(ai_x + 11.5, cocoa_y - 24.0))
            sh_path.lineToPoint_(NSPoint(ai_x + 8.5, cocoa_y - 25.5))
            sh_path.lineToPoint_(NSPoint(ai_x + 4.5, cocoa_y - 17.5))
            sh_path.lineToPoint_(NSPoint(ai_x + 1.5, cocoa_y - 20.0))
            sh_path.closePath()
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.0, 0.0, 0.0, 0.3).setFill()
            sh_path.fill()

            # White fill & dark border
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.98, 0.99, 1.0, 1.0).setFill()
            cursor_path.fill()
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.10, 0.14, 0.20, 0.90).setStroke()
            cursor_path.setLineWidth_(1.4)
            cursor_path.stroke()

            # Cyan spine accent
            spine_path = NSBezierPath.bezierPath()
            spine_path.moveToPoint_(NSPoint(ai_x, cocoa_y))
            spine_path.lineToPoint_(NSPoint(ai_x + 6.0, cocoa_y - 14.0))
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.0, 0.88, 1.0, 0.8).setStroke()
            spine_path.setLineWidth_(1.2)
            spine_path.stroke()

    def create_overlay_window(screen_w=1920, screen_h=1080):
        app = NSApplication.sharedApplication()
        rect = NSRect(NSPoint(0, 0), NSSize(screen_w, screen_h))
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect,
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False
        )
        win.setLevel_(NSStatusWindowLevel + 10)
        win.setOpaque_(False)
        win.setBackgroundColor_(NSColor.clearColor())
        win.setIgnoresMouseEvents_(True)
        win.setHasShadow_(False)

        view = CursorOverlayView.alloc().initWithFrame_(rect)
        win.setContentView_(view)
        win.makeKeyAndOrderFront_(None)
        return app, win, view

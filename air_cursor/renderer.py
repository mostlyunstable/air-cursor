try:
    import bpy
    import gpu
    from gpu_extras.batch import batch_for_shader
except ImportError:
    bpy = None
    gpu = None
    batch_for_shader = None
import math
import time

class CursorRenderer:
    """Multi-region GPU shader renderer for Air Cursor pointer."""

    ARROW_VERTS = [
        (0.0, 0.0),       # v0: Tip
        (0.0, -18.0),     # v1: Left bottom corner
        (4.5, -14.0),     # v2: Left inner notch
        (8.0, -22.5),     # v3: Tail bottom-left
        (11.0, -21.2),    # v4: Tail bottom-right
        (7.5, -12.5),     # v5: Tail upper-right notch
        (13.5, -12.5)     # v6: Right wing tip
    ]

    ARROW_TRIS = [
        (0, 1, 2),
        (0, 2, 6),
        (2, 5, 6),
        (2, 3, 5),
        (3, 4, 5)
    ]

    @classmethod
    def draw_callback_for_region(cls, space_name, reg_type, state):
        with state.lock:
            if not state.is_active:
                return
            wx = state.win_x
            wy = state.win_y
            hover = state.hover_active
            drag = state.drag_active
            ripples = list(state.ripples)
            cfg = dict(state.config)
            now = time.perf_counter()

        context = bpy.context
        region = getattr(context, 'region', None)
        area = getattr(context, 'area', None)
        if not region or not area:
            return

        reg_x = region.x
        reg_y = region.y
        reg_w = region.width
        reg_h = region.height

        in_region = (reg_x <= wx <= reg_x + reg_w) and (reg_y <= wy <= reg_y + reg_h)

        # Region-local cursor tip
        cx = wx - reg_x
        cy = wy - reg_y

        scale = cfg.get("cursor_scale", 1.0)
        accent_color = cfg.get("accent_color", (0.0, 0.88, 1.0, 0.65))
        show_shadow = cfg.get("show_shadow", True)
        show_ripples = cfg.get("show_ripples", True)
        show_glow = cfg.get("show_glow", True)

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')

        # 1. Click Ripples (150ms expanding ring at tip)
        if show_ripples:
            for rip in ripples:
                rwx = rip["win_x"]
                rwy = rip["win_y"]
                if (reg_x <= rwx <= reg_x + reg_w) and (reg_y <= rwy <= reg_y + reg_h):
                    rcx = rwx - reg_x
                    rcy = rwy - reg_y
                    elapsed = now - rip["start_time"]
                    dur = rip.get("duration", cfg.get("ripple_duration", 0.15))
                    progress = min(1.0, max(0.0, elapsed / dur))
                    
                    r = (2.0 + progress * 12.0) * scale
                    alpha = (1.0 - progress) * 0.85
                    
                    segments = 24
                    ring_coords = []
                    for i in range(segments + 1):
                        ang = i * (2.0 * math.pi / segments)
                        ring_coords.append((rcx + r * math.cos(ang), rcy + r * math.sin(ang)))
                    
                    gpu.state.line_width_set(1.5)
                    batch_rip = batch_for_shader(shader, 'LINE_STRIP', {'pos': ring_coords})
                    shader.bind()
                    shader.uniform_float('color', (accent_color[0], accent_color[1], accent_color[2], alpha))
                    batch_rip.draw(shader)

        # If pointer tip is not in this region, stop here
        if not in_region:
            gpu.state.blend_set('NONE')
            return

        # Defer to higher z-order subregions (UI N-panel, HEADER, etc.)
        if reg_type == 'WINDOW':
            for sub_r in area.regions:
                if sub_r.type != 'WINDOW' and (sub_r.x <= wx <= sub_r.x + sub_r.width) and (sub_r.y <= wy <= sub_r.y + sub_r.height):
                    gpu.state.blend_set('NONE')
                    return

        # 2. Subtle Glow (Tip aura)
        if show_glow:
            glow_radius = (10.0 if hover else 7.0) * scale
            glow_alpha = 0.28 if hover else 0.15
            glow_segments = 16
            glow_tris = []
            for i in range(glow_segments):
                a1 = i * (2.0 * math.pi / glow_segments)
                a2 = (i + 1) * (2.0 * math.pi / glow_segments)
                glow_tris.extend([
                    (cx, cy),
                    (cx + glow_radius * math.cos(a1), cy + glow_radius * math.sin(a1)),
                    (cx + glow_radius * math.cos(a2), cy + glow_radius * math.sin(a2))
                ])
            batch_glow = batch_for_shader(shader, 'TRIS', {'pos': glow_tris})
            shader.bind()
            shader.uniform_float('color', (accent_color[0], accent_color[1], accent_color[2], glow_alpha))
            batch_glow.draw(shader)

        scaled_verts = [(px * scale, py * scale) for (px, py) in cls.ARROW_VERTS]

        # 3. Natural Drop Shadow (+1.5, -2.0 offset)
        if show_shadow:
            sh_off_x = 1.5 * scale
            sh_off_y = -2.0 * scale
            sh_coords = [(cx + px + sh_off_x, cy + py + sh_off_y) for (px, py) in scaled_verts]
            sh_tris = []
            for t in cls.ARROW_TRIS:
                sh_tris.extend([sh_coords[t[0]], sh_coords[t[1]], sh_coords[t[2]]])
            
            batch_sh = batch_for_shader(shader, 'TRIS', {'pos': sh_tris})
            shader.bind()
            shader.uniform_float('color', (0.0, 0.0, 0.0, 0.28))
            batch_sh.draw(shader)

        # 4. Clean White Arrow Body
        arrow_coords = [(cx + px, cy + py) for (px, py) in scaled_verts]
        arrow_tri_coords = []
        for t in cls.ARROW_TRIS:
            arrow_tri_coords.extend([arrow_coords[t[0]], arrow_coords[t[1]], arrow_coords[t[2]]])

        batch_body = batch_for_shader(shader, 'TRIS', {'pos': arrow_tri_coords})
        shader.bind()
        shader.uniform_float('color', (0.98, 0.99, 1.0, 1.0))
        batch_body.draw(shader)

        # 5. Crisp Dark Charcoal Outline
        outline_pts = arrow_coords + [arrow_coords[0]]
        batch_out = batch_for_shader(shader, 'LINE_STRIP', {'pos': outline_pts})
        gpu.state.line_width_set(max(1.0, 1.4 * scale))
        shader.bind()
        shader.uniform_float('color', (0.10, 0.14, 0.20, 0.90))
        batch_out.draw(shader)

        # 6. Electric Spine Accent (Line from notch v2 to v5)
        spine_pts = [arrow_coords[0], arrow_coords[2], arrow_coords[5]]
        batch_spine = batch_for_shader(shader, 'LINE_STRIP', {'pos': spine_pts})
        gpu.state.line_width_set(max(1.0, 1.2 * scale))
        shader.bind()
        shader.uniform_float('color', (accent_color[0], accent_color[1], accent_color[2], 0.65))
        batch_spine.draw(shader)

        # 7. Drag Indicator (Small grip dot when drag_active)
        if drag:
            dot_cx = cx + 18.0 * scale
            dot_cy = cy - 8.0 * scale
            dot_r = 3.0 * scale
            dot_pts = []
            for i in range(12):
                a1 = i * (2.0 * math.pi / 12)
                a2 = (i + 1) * (2.0 * math.pi / 12)
                dot_pts.extend([
                    (dot_cx, dot_cy),
                    (dot_cx + dot_r * math.cos(a1), dot_cy + dot_r * math.sin(a1)),
                    (dot_cx + dot_r * math.cos(a2), dot_cy + dot_r * math.sin(a2))
                ])
            batch_dot = batch_for_shader(shader, 'TRIS', {'pos': dot_pts})
            shader.bind()
            shader.uniform_float('color', (accent_color[0], accent_color[1], accent_color[2], 0.90))
            batch_dot.draw(shader)

        gpu.state.blend_set('NONE')

# Air Cursor: Technical Architecture & Kinematics

Air Cursor provides an autonomous desktop AI pointer designed to operate inside Blender with native desktop fluidity and strict input isolation.

---

## 1. Input Isolation Architecture

Traditional automation tools often seize or warp the operating system's hardware mouse cursor (`CGWarpMouseCursorPosition`), preventing the user from using their computer during automated runs.

Air Cursor solves this through Blender-internal rendering and dispatch:
- **No System-Wide Pointer Hijacking**: The OS hardware pointer is never moved or polled destructively. The user can type, browse, or code on other displays and applications simultaneously.
- **GPU `POST_PIXEL` Render Layer**: The AI pointer is drawn directly inside Blender's viewport framebuffer using `gpu.shader` and `gpu_extras.batch`.
- **Window Coordinate Mapping**: Cursor positions are defined in window-space coordinates and translated into region-local coordinates per editor space.

```
+-------------------------------------------------------------+
| macOS Desktop                                               |
|                                                             |
|   [Human OS Cursor] -> Native Finder / Browser / Editor     |
|   (Uninterrupted, 0.00 px deflection)                       |
|                                                             |
|   +-------------------------------------------------------+ |
|   | Blender Application Window                            | |
|   |                                                       | |
|   |   [Air Cursor (AI)] -> GPU POST_PIXEL Shader Overlay  | |
|   |   - 3D Viewport                                       | |
|   |   - Outliner Hierarchy                                | |
|   |   - Properties Panels                                 | |
|   +-------------------------------------------------------+ |
+-------------------------------------------------------------+
```

---

## 2. Mathematical Kinematics Engine

Air Cursor implements human motor control principles using a quintic minimum-jerk polynomial trajectory. Jerk is the time derivative of acceleration ($\frac{d^3x}{dt^3}$); minimizing total jerk across the movement produces a natural bell-shaped velocity curve with zero initial and terminal velocity.

### Closed-Form Polynomial
For normalized time $\tau \in [0, 1]$ where $\tau = \frac{t - t_{\text{start}}}{T}$:

$$s(\tau) = 10\tau^3 - 15\tau^4 + 6\tau^5$$

Boundary conditions satisfied:
- $s(0) = 0, \quad s(1) = 1$
- $s'(0) = 0, \quad s'(1) = 0$ (Zero velocity at endpoints)
- $s''(0) = 0, \quad s''(1) = 0$ (Zero acceleration at endpoints)

### Dynamic Duration Scaling
To prevent long cross-screen movements from creeping or micro-movements from snapping abruptly, duration $T$ scales dynamically based on Euclidean distance:

$$T(dist) = \text{clamp}\left(0.18, 0.48, 0.14 + 0.010 \sqrt{dist}\right)$$

- Micro-moves ($50\text{px}$): $\sim 0.18\text{ s}$
- Cross-editor transitions ($2000\text{px}$): $\sim 0.48\text{ s}$

---

## 3. Targeted Redraw Optimization

In Blender, calling `area.tag_redraw()` across all screen areas every frame causes Cycles viewport rendering to constantly invalidate its progressive sampling buffer, leading to UI frame drops.

Air Cursor resolves this via **Targeted Area Invalidation**:
1. Locates the specific screen area containing $(x, y)$ via `_find_area_at(x, y)`.
2. Only tags `tag_redraw()` on the active area containing the cursor.
3. When transitioning across area boundaries (e.g. from 3D Viewport into Outliner), invalidates both the previous and current area for a single frame.
4. When the cursor is stationary and no ripples are active, redraw is skipped entirely (0% idle GPU overhead).

---

## 4. Multi-Region GPU Rendering

Blender's UI layout comprises multiple space types (`SpaceView3D`, `SpaceOutliner`, `SpaceProperties`) and subregions (`WINDOW`, `UI`, `HEADER`, `NAVIGATION_BAR`).

To ensure the cursor remains visible on top of N-panel buttons and headers:
- Handlers are registered on both `WINDOW` and higher z-order subregions (`UI`, `HEADER`, `NAVIGATION_BAR`).
- When Blender draws `WINDOW`, it checks if $(x, y)$ falls inside a subregion; if so, it skips drawing to let the subregion draw the cursor on top of UI widgets.
- Prevents double-drawing while guaranteeing the cursor is never occluded by sidebar controls.

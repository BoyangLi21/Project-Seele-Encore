"""Offline preview of the A.T. Field effect (client/fx/AtFieldEffects.java).

python at_field_preview.py --out <dir> [--fps 30]

Evaluates the same layers per pixel (field fill, standing rings lit by passing
wavefronts, wavefront tint + core, contact flash) for a scripted strike
sequence and writes PNG frames: front view and an oblique view, over a day
and a dusk sky.  Keep the constants in step with the Java class.
"""

import argparse
import os

import numpy as np
from PIL import Image, ImageDraw

HOLD, FRONTS, FRONT_GAP, FRONT_TRAVEL, RINGS = 1.7, 4, 0.07, 0.8, 11
NORMALS = np.array([[np.cos(k * np.pi / 4), np.sin(k * np.pi / 4)] for k in range(4)])


def octa(x, y):
    """Flat-side distance of an octagon whose flat sides face 0/45/90/135 degrees."""
    return np.max(np.abs(x[..., None] * NORMALS[:, 0] + y[..., None] * NORMALS[:, 1]), axis=-1)


def profile(t):
    t = np.abs(t)
    skirt = np.exp(-t * t * 5.0) * (1.0 - t ** 4)
    core = np.exp(-t * t * 70.0)
    return np.where(t <= 1.0, np.maximum(skirt * 0.55, core), 0.0)


def ease_out(x, p):
    return 1.0 - (1.0 - np.clip(x, 0.0, 1.0)) ** p


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def front_radius(R, prog):
    return R * (0.04 + 1.12 * ease_out(prog, 1.8))


def render(frame, px, py, valid, pulses, now, R=1.0):
    """Fill and orange tint alpha-blended over the frame, white-hot cores added."""
    first, last = pulses[0][2], pulses[-1][2]
    presence = ease_out((now - first) / 0.06, 2.0) * (1.0 - smoothstep((now - last - 0.25) / (HOLD - 0.25)))
    if presence <= 0.002:
        return frame
    v = valid[..., None]

    def tint(alpha_map, col):
        nonlocal frame
        a = np.clip(alpha_map, 0, 1)[..., None] * v
        frame = frame * (1 - a) + np.asarray(col) * a

    glow = np.zeros_like(frame)

    def add(alpha_map, col):
        nonlocal glow
        glow = glow + np.clip(alpha_map, 0, 1)[..., None] * np.array(col) * v

    flash = max([p[3] * np.exp(-(now - p[2]) * 7.0) for p in pulses if now >= p[2]] + [0.0])
    d0 = octa(px, py)
    fr = R * 1.04
    alpha = presence * (0.15 + 0.22 * flash)
    u = np.clip(d0 / fr, 0, 1)[..., None]
    centre, rim = np.array((1.0, 0.68, 0.24)), np.array((1.0, 0.38, 0.05))
    tint(np.where(d0 <= fr, alpha * (1.5 + (0.75 - 1.5) * d0 / fr), 0.0).clip(0, 0.7), centre * (1 - u) + rim * u)
    flicker = 0.95
    rings = []
    for ring in range(RINGS):
        rr = R * (0.1 + 0.9 * ring / (RINGS - 1))
        lit = 0.0
        for (a, b, start, inten) in pulses:
            for f in range(FRONTS):
                t = now - start - f * FRONT_GAP
                if t <= 0 or t >= FRONT_TRAVEL:
                    continue
                g = (rr - front_radius(R, t / FRONT_TRAVEL)) / (R * 0.075)
                lit += inten * np.exp(-g * g) * (1 - 0.2 * f)
        rings.append((rr, min(lit, 1.0), 1.35 if ring == RINGS - 1 else 1.0))
    fronts = []
    for (a, b, start, inten) in pulses:
        age = now - start
        if age < 0:
            continue
        d = octa(px - a, py - b)
        for f in range(FRONTS):
            t = age - f * FRONT_GAP
            if t <= 0 or t >= FRONT_TRAVEL:
                continue
            prog = t / FRONT_TRAVEL
            front = front_radius(R, prog)
            beyond = 1 - smoothstep((front / R - 0.9) / 0.3)
            bright = inten * flicker * presence * (1 - 0.18 * f) * beyond * (1 - prog) ** 1.4 * min(prog / 0.04, 1)
            fronts.append((d, front, R * (0.008 + 0.022 * (1 - prog)), bright))
        fl = inten * np.exp(-age * 9.0) * presence
        disk = R * (0.08 + 0.16 * ease_out(age / 0.2, 2.0))
        fronts.append((d, None, disk, fl))
    for core in (False, True):
        for rr, lit, edge in rings:
            if core:
                w = R * 0.006
                add(presence * flicker * (0.10 + 0.9 * lit) * edge * profile((d0 - rr) / w), (1.0, 0.82, 0.55))
            else:
                w = R * (0.02 + 0.012 * lit)
                tint(presence * flicker * (0.24 + 0.55 * lit) * edge * profile((d0 - rr) / w), (1.0, 0.46, 0.08))
        if core:
            add(presence * flicker * 0.55 * profile((d0 - R * 0.995) / (R * 0.01)), (1.0, 0.88, 0.62))
        else:
            tint(presence * flicker * 0.42 * profile((d0 - R * 0.9925) / (R * 0.0375)), (1.0, 0.44, 0.07))
        for d, front, w, bright in fronts:
            if front is None:
                if bright <= 0.01:
                    continue
                if core:
                    add(bright * profile(d / w), (1.0, 0.94, 0.8))
                else:
                    tint(bright * 0.75 * profile(d / (w * 2.2)), (1.0, 0.5, 0.1))
            elif core:
                add(bright * profile((d - front) / w), (1.0, 0.9, 0.68))
            else:
                tint(bright * 0.75 * profile((d - front) / (w * 4)), (1.0, 0.42, 0.06))
    return np.clip(frame + glow, 0, 1)


def sky(h, w, top, bottom):
    t = np.linspace(0, 1, h)[:, None, None]
    return np.broadcast_to(np.array(top) * (1 - t) + np.array(bottom) * t, (h, w, 3)).copy()


def front_coords(h, w, extent):
    ys, xs = np.mgrid[0:h, 0:w]
    s = 2 * extent / h
    return (xs - w / 2) * s, (h / 2 - ys) * s, np.ones((h, w), bool)


def oblique_coords(h, w, yaw, dist, fov):
    """Pinhole camera orbiting the plane (z = 0) by yaw about its vertical axis."""
    ys, xs = np.mgrid[0:h, 0:w]
    f = (h / 2) / np.tan(np.radians(fov) / 2)
    dx, dy, dz = (xs - w / 2) / f, (h / 2 - ys) / f, -np.ones_like(xs, float)
    c, s = np.cos(yaw), np.sin(yaw)
    rx, rz = c * dx + s * dz, -s * dx + c * dz
    cam = np.array([dist * np.sin(yaw), 0.15 * dist, dist * np.cos(yaw)])
    ry = dy - 0.15
    t = -cam[2] / np.where(np.abs(rz) < 1e-9, -1e-9, rz)
    px, py = cam[0] + t * rx, cam[1] + t * ry
    return px, py, t > 0


SCRIPT = [
    # (time s, a, b, intensity, label)
    (0.20, 0.00, 0.00, 1.0, "single punch"),
    (2.00, -0.10, 0.06, 0.8, "rifle burst"),
    (2.25, 0.08, -0.04, 0.8, None),
    (2.50, 0.02, 0.12, 0.8, None),
    (2.75, -0.05, -0.08, 0.8, None),
    (3.00, 0.11, 0.03, 0.8, None),
    (5.20, 0.00, 0.00, 1.4, "heavy blow"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seconds", type=float, default=7.0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    H, W = 360, 480
    views = [front_coords(H, W, 1.35), oblique_coords(H, W, np.radians(55), 3.1, 50)]
    backgrounds = [sky(H, W, (0.36, 0.55, 0.80), (0.75, 0.84, 0.92)), sky(H, W, (0.07, 0.08, 0.16), (0.42, 0.24, 0.20))]
    groups = []
    for i, (t, x, y, inten, label) in enumerate(SCRIPT):
        if i == 0 or SCRIPT[i][0] - SCRIPT[i - 1][0] > 0.9:
            groups.append([])
        groups[-1].append((x, y, t, inten))
    for k in range(int(a.seconds * a.fps)):
        now = k / a.fps
        tiles = []
        for bg in backgrounds:
            row = []
            for (px, py, valid) in views:
                frame = bg.copy()
                for g in groups:
                    live = [p for p in g if p[2] <= now]
                    if not live:
                        continue
                    frame = render(frame, px, py, valid, live, now)
                row.append(frame)
            tiles.append(np.concatenate(row, axis=1))
        img = Image.fromarray((np.concatenate(tiles, axis=0) * 255).astype(np.uint8))
        draw = ImageDraw.Draw(img)
        label = next((s[4] for s in reversed(SCRIPT) if s[4] and s[0] <= now + 0.2), "")
        draw.text((8, 6), f"{now:4.2f}s  {label}", fill=(255, 255, 255))
        img.save(os.path.join(a.out, f"f_{k:04d}.png"))
    print("frames", int(a.seconds * a.fps))


if __name__ == "__main__":
    main()

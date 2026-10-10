#!/usr/bin/env python3
"""Generate Hemo's own blood textures (no third-party art).

Full-screen overlays are 1024x512 and get stretched over the whole screen, so
they are deliberately ASYMMETRIC: every layer favours different corners/edges.
Crit-number splats are 128x128. Output: RGBA PNG, colour = dark blood, shape
in alpha. Re-run to re-roll (seeded, so results are reproducible).
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
W, H = 1024, 512
rng = np.random.default_rng(20261004)
random.seed(20261004)


def fbm(w, h, octaves=5, base=4, persistence=0.55):
    """Fractal value noise in 0..1."""
    total = np.zeros((h, w), dtype=np.float32)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        cells = base * (2 ** o)
        grid = rng.random((max(2, cells * h // w), cells)).astype(np.float32)
        img = Image.fromarray((grid * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        total += np.asarray(img, dtype=np.float32) / 255.0 * amp
        norm += amp
        amp *= persistence
    return total / norm


def smoothstep(edge0, edge1, x):
    t = np.clip((x - edge0) / (edge1 - edge0), 0, 1)
    return t * t * (3 - 2 * t)


def colorize(alpha, shade=None):
    """Dark blood colour with some tonal variation; alpha carries the shape."""
    h, w = alpha.shape
    var = fbm(w, h, 4, 6) if shade is None else shade
    r = 0.26 + 0.30 * var
    g = 0.015 + 0.035 * var
    b = 0.02 + 0.035 * var
    rgb = np.stack([r, g, b], axis=-1)
    rgba = np.concatenate([rgb, alpha[..., None]], axis=-1)
    return Image.fromarray((np.clip(rgba, 0, 1) * 255).astype(np.uint8), "RGBA")


def save(img, name):
    path = os.path.join(OUT, name)
    img.save(path, optimize=True)
    print(f"{name}: {img.size} {os.path.getsize(path) // 1024} KB")


yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
nx, ny = xx / W, yy / H


def edge_distance(weights):
    """Normalised distance to the nearest edge, each edge scaled by a weight
    (higher weight = blood reaches further in from that edge)."""
    wl, wr, wt, wb = weights
    return np.minimum.reduce([
        nx / wl, (1 - nx) / wr, ny / wt, (1 - ny) / wb])


# 1) Edge vignette: heavy bottom-left and top-right, thin elsewhere.
def make_edge():
    noise = fbm(W, H, 6, 5)
    d = edge_distance((0.30, 0.16, 0.22, 0.34))
    # push extra blood into two opposite corners
    corner_a = np.hypot(nx - 0.0, (ny - 1.0) * 1.6)
    corner_b = np.hypot((nx - 1.0) * 0.9, (ny - 0.0) * 1.5)
    d = d - 0.30 * np.exp(-corner_a * 3.2) - 0.22 * np.exp(-corner_b * 3.6)
    alpha = 1.0 - smoothstep(0.08, 0.62, d + (noise - 0.5) * 0.7)
    alpha = np.clip(alpha, 0, 1) ** 1.8 * 0.9
    # fine grain so the edge looks wet and uneven, not airbrushed
    alpha *= 0.85 + 0.15 * fbm(W, H, 3, 24)
    return colorize(np.clip(alpha, 0, 1))


# 2) Splatter + drips helpers.
def splatter(draw, cx, cy, spread, count, rmin, rmax, bias=(0, 0)):
    for _ in range(count):
        ang = random.uniform(0, math.tau)
        dist = abs(random.gauss(0, spread))
        x = cx + math.cos(ang) * dist + bias[0] * dist * 0.5
        y = cy + math.sin(ang) * dist + bias[1] * dist * 0.5
        r = max(1.2, random.uniform(rmin, rmax) * 0.6 * math.exp(-dist / (spread * 1.3)))
        sx, sy = r * random.uniform(0.7, 1.5), r * random.uniform(0.7, 1.5)
        draw.ellipse([x - sx, y - sy, x + sx, y + sy], fill=255)


def drip(draw, x, y, length, width):
    """A vertical run with a fat rounded tip; narrows slightly upward."""
    steps = int(length)
    for i in range(steps):
        t = i / max(1, steps)
        w = width * (0.55 + 0.45 * t)
        wob = math.sin(i * 0.15 + x) * 0.8
        draw.ellipse([x + wob - w, y + i - w, x + wob + w, y + i + w], fill=255)
    tip = width * 1.45
    draw.ellipse([x - tip, y + length - tip, x + tip, y + length + tip], fill=255)


def warp(a, strength=26):
    """Displace pixels by smooth noise so round shapes turn organic."""
    dx = (fbm(W, H, 4, 6) - 0.5) * 2 * strength
    dy = (fbm(W, H, 4, 6) - 0.5) * 2 * strength
    xi = np.clip((xx + dx).astype(np.int32), 0, W - 1)
    yi = np.clip((yy + dy).astype(np.int32), 0, H - 1)
    return a[yi, xi]


def finish_mask(mask_img, noise_amp=0.35):
    mask = mask_img.filter(ImageFilter.GaussianBlur(5.0))
    a = np.asarray(mask, dtype=np.float32) / 255.0
    a = warp(a, 30)
    a = smoothstep(0.30, 0.58, a + (fbm(W, H, 6, 14) - 0.5) * noise_amp)
    return a


def make_left():
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    splatter(d, -20, H * 0.62, 190, 520, 3, 34, bias=(1, 0))
    splatter(d, 60, H * 0.12, 120, 220, 2, 22, bias=(1, -0.2))
    # asymmetric drips from the upper-left
    for _ in range(11):
        x = random.uniform(10, W * 0.42)
        y = random.uniform(-10, H * 0.14)
        drip(d, x, y, random.uniform(40, 210) * (1.2 - x / (W * 0.6)), random.uniform(3, 8))
    # a few stray flecks
    for _ in range(70):
        x, y = random.uniform(0, W * 0.5), random.uniform(0, H)
        r = random.uniform(1.2, 4)
        d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    return colorize(finish_mask(mask))


def make_right():
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    splatter(d, W + 30, H * 0.30, 230, 460, 3, 38, bias=(-1, 0))
    splatter(d, W * 0.72, H + 30, 170, 340, 2, 30, bias=(0, -1))
    # drips climbing down from the top-right, shorter and fewer than the left
    for _ in range(6):
        x = random.uniform(W * 0.62, W - 8)
        drip(d, x, random.uniform(-10, 10), random.uniform(30, 140), random.uniform(3, 7))
    for _ in range(60):
        x, y = random.uniform(W * 0.45, W), random.uniform(0, H)
        r = random.uniform(1.2, 4)
        d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    return colorize(finish_mask(mask, 0.4))


def make_veins():
    """Branching veins creeping in from two corners, thin and dark."""
    layer = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(layer)

    def branch(x, y, ang, length, width, depth):
        if depth == 0 or length < 8 or width < 0.6:
            return
        pts = [(x, y)]
        for _ in range(int(length / 6)):
            ang += random.gauss(0, 0.22)
            x += math.cos(ang) * 6
            y += math.sin(ang) * 6
            pts.append((x, y))
            if random.random() < 0.07 and depth > 1:
                branch(x, y, ang + random.choice((-1, 1)) * random.uniform(0.5, 1.1),
                       length * 0.55, width * 0.62, depth - 1)
        d.line(pts, fill=255, width=max(1, int(round(width))), joint="curve")

    for _ in range(7):  # bottom-left cluster
        branch(random.uniform(-10, 40), random.uniform(H * 0.55, H),
               random.uniform(-0.5, 0.5), random.uniform(150, 300), random.uniform(3.2, 5), 4)
    for _ in range(5):  # top-right, sparser
        branch(random.uniform(W - 50, W + 10), random.uniform(0, H * 0.45),
               math.pi + random.uniform(-0.5, 0.5), random.uniform(120, 240), random.uniform(2.8, 4.2), 4)
    mask = layer.filter(ImageFilter.GaussianBlur(1.1))
    a = np.asarray(mask, dtype=np.float32) / 255.0
    edge_fade = 1.0 - smoothstep(0.04, 0.34, np.minimum.reduce([nx, 1 - nx, ny * 1.4, (1 - ny) * 1.4]))
    a = np.clip(a * 1.25, 0, 1) * (0.55 + 0.45 * fbm(W, H, 3, 10)) * edge_fade
    # veins are darker than the splatter
    img = colorize(a, shade=np.zeros_like(a))
    arr = np.asarray(img).astype(np.float32)
    arr[..., 0] *= 0.82
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def make_splat(seed, size=128):
    r = random.Random(seed)
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    c = size / 2
    d.ellipse([c - 26, c - 22, c + 26, c + 22], fill=255)
    for _ in range(46):  # radiating droplets
        ang = r.uniform(0, math.tau)
        dist = r.uniform(18, 56)
        rad = r.uniform(1.5, 7) * (1.3 - dist / 70)
        x, y = c + math.cos(ang) * dist, c + math.sin(ang) * dist
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=255)
    for _ in range(9):  # streaks
        ang = r.uniform(0, math.tau)
        for t in np.linspace(14, r.uniform(42, 62), 20):
            rad = max(0.8, 5 * (1 - t / 64))
            x, y = c + math.cos(ang) * t, c + math.sin(ang) * t
            d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    a = np.asarray(mask, dtype=np.float32) / 255.0
    a = smoothstep(0.35, 0.65, a)
    shade = np.asarray(Image.fromarray((np.random.default_rng(seed).random((size, size)) * 255)
                                       .astype(np.uint8)).filter(ImageFilter.GaussianBlur(4)),
                       dtype=np.float32) / 255.0
    return colorize(a, shade=shade)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    save(make_edge(), "blood_edge.png")
    save(make_left(), "blood_left.png")
    save(make_right(), "blood_right.png")
    save(make_veins(), "blood_veins.png")
    for i in (1, 2, 3):
        save(make_splat(i), f"splat_{i}.png")

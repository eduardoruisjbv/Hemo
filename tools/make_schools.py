#!/usr/bin/env python3
"""Generate Hemo's per-school crit textures (own art, no third-party assets).

For every magic school: fx_<school>.png (1024x512 full-screen layer, heavy on
the LEFT so a mirrored copy covers the right) and sp_<school>_1/2.png (128x128
sprites that sit behind the crit number). Colours are baked in. Physical keeps
the blood textures from make_blood.py.
Usage: python3 make_schools.py <output dir>
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import make_blood as mb

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
W, H = mb.W, mb.H
random.seed(77)
rng = np.random.default_rng(77)
fbm, smoothstep, warp = mb.fbm, mb.smoothstep, mb.warp
nx, ny = mb.nx, mb.ny

PALETTES = {
    "fire":   [(0.30, 0.02, 0.00), (0.85, 0.22, 0.02), (1.00, 0.62, 0.10), (1.00, 0.95, 0.60)],
    "frost":  [(0.20, 0.45, 0.78), (0.50, 0.78, 1.00), (0.85, 0.96, 1.00), (1.00, 1.00, 1.00)],
    "shadow": [(0.04, 0.00, 0.08), (0.20, 0.04, 0.34), (0.42, 0.14, 0.66), (0.62, 0.35, 0.90)],
    "arcane": [(0.35, 0.08, 0.55), (0.78, 0.28, 1.00), (1.00, 0.70, 1.00), (1.00, 1.00, 1.00)],
    "nature": [(0.04, 0.18, 0.02), (0.22, 0.55, 0.08), (0.55, 0.88, 0.18), (0.85, 1.00, 0.45)],
    "holy":   [(0.75, 0.50, 0.12), (1.00, 0.82, 0.38), (1.00, 0.95, 0.72), (1.00, 1.00, 0.95)],
    "chaos":  [(0.22, 0.00, 0.30), (0.70, 0.04, 0.62), (0.95, 0.30, 0.90), (0.35, 1.00, 0.25)],
}


def ramp(palette, t):
    """Map 0..1 values to RGB through palette stops (piecewise linear)."""
    t = np.clip(t, 0, 1) * (len(palette) - 1)
    i = np.minimum(t.astype(np.int32), len(palette) - 2)
    f = (t - i)[..., None]
    pal = np.array(palette, dtype=np.float32)
    return pal[i] * (1 - f) + pal[i + 1] * f


def compose(alpha, heat, palette):
    """alpha = shape, heat = 0..1 position along the palette."""
    rgb = ramp(palette, heat)
    rgba = np.concatenate([rgb, np.clip(alpha, 0, 1)[..., None]], axis=-1)
    return Image.fromarray((np.clip(rgba, 0, 1) * 255).astype(np.uint8), "RGBA")


def aniso(w, h, cols, rows, octaves=4):
    """Noise stretched along one axis (many cells one way, few the other)."""
    total = np.zeros((h, w), dtype=np.float32)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        g = rng.random((max(2, rows * 2 ** o), max(2, cols * 2 ** o))).astype(np.float32)
        img = Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        total += np.asarray(img, dtype=np.float32) / 255.0 * amp
        norm += amp
        amp *= 0.5
    return total / norm


def edge_weight(left=1.0, right=0.35, top=0.5, bottom=0.8):
    """Per-pixel 0..1 'how close to the favoured edges' (asymmetric)."""
    left, right, top, bottom = (max(v, 1e-3) for v in (left, right, top, bottom))
    return np.maximum.reduce([
        np.clip(1 - nx / (0.34 * left), 0, 1), np.clip(1 - (1 - nx) / (0.34 * right), 0, 1),
        np.clip(1 - ny / (0.45 * top), 0, 1), np.clip(1 - (1 - ny) / (0.45 * bottom), 0, 1)])


def glow_lines(lines, widths, blur=5, boost=1.6):
    """Draw polylines then add a blurred halo; returns 0..1 mask (core=1)."""
    layer = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(layer)
    for pts, w in zip(lines, widths):
        d.line(pts, fill=255, width=w, joint="curve")
    core = np.asarray(layer, dtype=np.float32) / 255.0
    halo = np.asarray(layer.filter(ImageFilter.GaussianBlur(blur)), dtype=np.float32) / 255.0
    return np.clip(core + halo * boost * 0.5, 0, 1), core


def jagged(p0, p1, rough=0.22, depth=6):
    pts = [p0, p1]
    for _ in range(depth):
        nxt = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            nxt += [(mx + random.gauss(0, rough * length * 0.5), my + random.gauss(0, rough * length * 0.5)), b]
        pts = nxt
    return pts


def sparks(count, bias_left=True):
    layer = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(layer)
    for _ in range(count):
        x = abs(random.gauss(0, W * 0.28)) if bias_left else random.uniform(0, W)
        y = random.uniform(0, H)
        r = random.uniform(1.0, 3.2)
        d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    return np.asarray(layer.filter(ImageFilter.GaussianBlur(0.8)), dtype=np.float32) / 255.0


# ---- full-screen layers ---------------------------------------------------

def fx_fire():
    flames = aniso(W, H, 18, 3, 4)                      # tall narrow tongues
    height = 1 - ny                                      # grows from the bottom edge
    field = smoothstep(0.30, 0.95, flames * 1.25 + 0.55 * height - 0.55 + 0.35 * edge_weight(1.2, 0.2, 0.0, 1.0))
    field = warp(field, 22)
    left = aniso(W, H, 3, 12, 4)                         # flames also lick in from the left
    field *= smoothstep(0.0, 0.5, ny - 0.38)              # keep tongues near the bottom edge
    field = np.maximum(field, smoothstep(0.35, 0.8, left + 0.9 * np.clip(1 - nx / 0.28, 0, 1) - 0.55))
    heat = np.clip((field ** 1.1) * 0.78 + (fbm(W, H, 4, 9) - 0.5) * 0.2, 0, 1)
    emb = sparks(90)
    alpha = np.clip(field * 0.95 + emb, 0, 1)
    return compose(alpha, np.maximum(heat, emb), PALETTES["fire"])


def fx_frost():
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    for _ in range(34):                                  # shards growing in from the edges
        side = random.random()
        if side < 0.55:     # left
            bx, by, ang = 0, random.uniform(0, H), random.uniform(-0.5, 0.5)
        elif side < 0.8:    # bottom
            bx, by, ang = random.uniform(0, W * 0.8), H, -math.pi / 2 + random.uniform(-0.45, 0.45)
        else:               # top right
            bx, by, ang = random.uniform(W * 0.6, W), 0, math.pi / 2 + random.uniform(-0.4, 0.4)
        length = random.uniform(70, 260) * (1.3 if bx < W * 0.3 else 0.8)
        half = random.uniform(8, 22)
        tip = (bx + math.cos(ang) * length, by + math.sin(ang) * length)
        nxv, nyv = -math.sin(ang), math.cos(ang)
        d.polygon([(bx + nxv * half, by + nyv * half), tip, (bx - nxv * half, by - nyv * half)], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    shards = np.asarray(mask, dtype=np.float32) / 255.0
    frost = smoothstep(0.35, 0.85, fbm(W, H, 5, 7) * 0.8 + 0.7 * edge_weight(1.2, 0.5, 0.7, 0.9) - 0.35)
    veins = Image.new("L", (W, H), 0)
    dv = ImageDraw.Draw(veins)
    for _ in range(26):
        x, y = random.uniform(0, W * 0.45), random.uniform(0, H)
        ang = random.uniform(-0.6, 0.6)
        for _ in range(random.randint(8, 22)):
            nxp, nyp = x + math.cos(ang) * 9, y + math.sin(ang) * 9
            dv.line([(x, y), (nxp, nyp)], fill=255, width=2)
            if random.random() < 0.3:
                bx = ang + random.choice((-1, 1)) * 0.9
                dv.line([(nxp, nyp), (nxp + math.cos(bx) * 24, nyp + math.sin(bx) * 24)], fill=255, width=1)
            x, y, ang = nxp, nyp, ang + random.gauss(0, 0.2)
    ice = np.asarray(veins.filter(ImageFilter.GaussianBlur(0.8)), dtype=np.float32) / 255.0
    alpha = np.clip(shards * 0.75 + frost * 0.55 + ice * 0.9, 0, 1)
    heat = np.clip(0.25 + shards * 0.45 + ice * 0.6 + frost * 0.3, 0, 1)
    return compose(alpha, heat, PALETTES["frost"])


def fx_shadow():
    smoke = fbm(W, H, 6, 4)
    w = warp(smoke, 70)
    field = smoothstep(0.42, 0.78, w * 0.9 + 0.75 * edge_weight(1.2, 0.45, 0.8, 1.0) - 0.30)
    wisps = fbm(W, H, 5, 9)
    field = np.clip(field * (0.6 + 0.7 * wisps), 0, 1)
    tendrils = Image.new("L", (W, H), 0)
    dt = ImageDraw.Draw(tendrils)
    for _ in range(9):
        x, y = random.uniform(-10, 30), random.uniform(0, H)
        ang = random.uniform(-0.7, 0.7)
        pts = [(x, y)]
        for _ in range(60):
            ang += random.gauss(0, 0.16)
            x += math.cos(ang) * 8
            y += math.sin(ang) * 8
            pts.append((x, y))
        dt.line(pts, fill=255, width=random.randint(5, 11), joint="curve")
    tend = np.asarray(tendrils.filter(ImageFilter.GaussianBlur(3)), dtype=np.float32) / 255.0
    tend *= 0.8 * (1 - smoothstep(0.1, 0.5, nx))
    alpha = np.clip(field * 0.95 + tend, 0, 1)
    heat = np.clip(0.15 + field * 0.5 + wisps * 0.3, 0, 1)
    return compose(alpha, heat, PALETTES["shadow"])


def fx_arcane():
    lines, widths = [], []
    for _ in range(11):                                  # arcs crawling in from the left and bottom
        if random.random() < 0.7:
            p0 = (0, random.uniform(0, H))
            p1 = (random.uniform(W * 0.25, W * 0.6), random.uniform(0, H))
        else:
            p0 = (random.uniform(0, W * 0.7), H)
            p1 = (p0[0] + random.uniform(-120, 200), random.uniform(H * 0.4, H * 0.8))
        lines.append(jagged(p0, p1))
        widths.append(random.randint(2, 4))
    halo, core = glow_lines(lines, widths, blur=7, boost=2.2)
    aura = smoothstep(0.2, 0.9, 0.9 * edge_weight(1.2, 0.4, 0.6, 0.9) + (fbm(W, H, 4, 6) - 0.5) * 0.5) * 0.5
    stars = sparks(70)
    alpha = np.clip(halo * 0.95 + aura + stars, 0, 1)
    heat = np.clip(0.2 + core * 0.9 + stars + aura * 0.2, 0, 1)
    return compose(alpha, heat, PALETTES["arcane"])


def fx_nature():
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    mb.splatter(d, -10, H * 0.55, 330, 760, 3, 36, bias=(1, 0))
    for _ in range(10):
        mb.drip(d, random.uniform(10, W * 0.42), random.uniform(-10, H * 0.12),
                random.uniform(40, 190), random.uniform(3, 8))
    blob = mb.finish_mask(mask)
    vines = Image.new("L", (W, H), 0)
    dv = ImageDraw.Draw(vines)
    for _ in range(8):
        x, y = random.uniform(-10, 40), random.uniform(H * 0.1, H)
        ang = random.uniform(-0.6, 0.4)
        pts = [(x, y)]
        for _ in range(random.randint(30, 60)):
            ang += random.gauss(0, 0.2)
            x += math.cos(ang) * 6
            y += math.sin(ang) * 6
            pts.append((x, y))
            if random.random() < 0.1:  # a leaf
                dv.ellipse([x - 9, y - 4, x + 9, y + 4], fill=255)
        dv.line(pts, fill=255, width=4, joint="curve")
    vine = np.asarray(vines.filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float32) / 255.0
    vine *= 1 - smoothstep(0.05, 0.45, nx)
    alpha = np.clip(blob * 0.9 + vine * 0.85, 0, 1)
    heat = np.clip(0.2 + (fbm(W, H, 4, 8) - 0.3) * 0.9 * blob + vine * 0.5, 0, 1)
    return compose(alpha, heat, PALETTES["nature"])


def fx_holy():
    ang = np.arctan2(ny * H, nx * W + 1e-3)             # fan of rays from the top-left corner
    rays = (np.sin(ang * 22 + fbm(W, H, 3, 5) * 6) * 0.5 + 0.5) ** 3
    falloff = np.exp(-np.hypot(nx, ny * 1.6) * 2.4)
    corner = np.exp(-np.hypot(nx * 1.2, ny * 2.0) * 3.2)
    alpha = np.clip(rays * falloff * 1.7 + corner * 0.95, 0, 1)
    alpha *= 0.85 + 0.15 * fbm(W, H, 4, 10)
    stars = sparks(60)
    alpha = np.clip(alpha + stars * 0.9, 0, 1)
    heat = np.clip(0.3 + corner * 0.6 + rays * falloff * 0.4 + stars, 0, 1)
    return compose(alpha, heat, PALETTES["holy"])


def fx_chaos():
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    for _ in range(18):                                  # dark angular shards from the left / bottom
        if random.random() < 0.65:
            bx, by, ang = 0, random.uniform(0, H), random.uniform(-0.7, 0.7)
        else:
            bx, by, ang = random.uniform(0, W * 0.7), H, -math.pi / 2 + random.uniform(-0.6, 0.6)
        length = random.uniform(120, 340)
        half = random.uniform(16, 44)
        tip = (bx + math.cos(ang) * length, by + math.sin(ang) * length)
        nxv, nyv = -math.sin(ang), math.cos(ang)
        mid = (bx + math.cos(ang) * length * 0.5 + nxv * half * 0.4, by + math.sin(ang) * length * 0.5 + nyv * half * 0.4)
        d.polygon([(bx + nxv * half, by + nyv * half), mid, tip, (bx - nxv * half, by - nyv * half)], fill=255)
    shards = np.asarray(mask.filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float32) / 255.0
    edge = np.asarray(mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(1.6)), dtype=np.float32) / 255.0
    lines = [jagged((random.uniform(0, W * 0.3), random.uniform(0, H)),
                    (random.uniform(W * 0.3, W * 0.7), random.uniform(0, H)), 0.28) for _ in range(7)]
    halo, core = glow_lines(lines, [3] * 7, blur=6, boost=2.0)
    aura = smoothstep(0.25, 0.9, 0.8 * edge_weight(1.2, 0.4, 0.6, 0.9) + (fbm(W, H, 4, 6) - 0.5) * 0.5) * 0.35
    alpha = np.clip(shards * 0.85 + edge * 1.2 + halo * 0.9 + aura, 0, 1)
    heat = np.clip(0.02 + shards * 0.08 + halo * 0.5 + np.clip(edge * 3, 0, 1) * 0.95, 0, 1)
    return compose(alpha, heat, PALETTES["chaos"])



# ---- painterly crest style (frost / nature / chaos) ------------------------
# A thick brush-stroked mass hugging the bottom edge, climbing toward the
# LEFT: ragged top edge, horizontal strokes, bright crest fading to a dark
# base, dark haze above and loose flecks. (Mirrored copies climb on the right.)

PAINT = {
    "frost":  dict(palette=[(0.02, 0.05, 0.14), (0.10, 0.28, 0.55), (0.45, 0.72, 0.95), (0.96, 0.99, 1.00)],
                   base=0.66, slope=0.30, haze=0.40, clouds=0.9, ragged=0.22),
    "nature": dict(palette=[(0.02, 0.07, 0.01), (0.10, 0.34, 0.05), (0.38, 0.80, 0.16), (0.80, 1.00, 0.45)],
                   base=0.64, slope=0.30, haze=0.35, clouds=0.35, ragged=0.28),
    "chaos":  dict(palette=[(0.03, 0.00, 0.07), (0.30, 0.02, 0.40), (0.78, 0.12, 0.74), (0.55, 1.00, 0.35)],
                   base=0.66, slope=0.30, haze=0.45, clouds=0.5, ragged=0.26),
}


def painterly(school):
    cfg = PAINT[school]
    # crest profile: high on the left, lower to the right, with slow waves
    wave = fbm(W, H, 4, 5)[H // 2, :]
    top = cfg["base"] - cfg["slope"] * (1 - nx) ** 1.3 + (wave[None, :] - 0.5) * 0.16
    edge_noise = fbm(W, H, 5, 9)                          # blobby, brushy edge (not spiky)
    fine = fbm(W, H, 6, 22)
    dist = ny - top + (edge_noise - 0.5) * cfg["ragged"] + (fine - 0.5) * 0.045
    body = smoothstep(-0.015, 0.07, dist)               # opaque mass below the crest
    haze = np.exp(-np.maximum(0.0, -dist) * 11) * cfg["haze"] * (1 - body)  # soft dark smoke above
    # tonal structure: bright near the crest, dark deep inside, streaked
    depth = np.clip(dist / 0.45, 0, 1)
    streak = aniso(W, H, 5, 42, 4)                       # long HORIZONTAL brush marks
    heat = np.clip(0.95 - depth * 1.15 + (streak - 0.5) * 0.85 + (fbm(W, H, 4, 8) - 0.5) * 0.2, 0, 1)
    # a few lit "clouds" riding the crest (frost especially)
    cloud = smoothstep(0.55, 0.85, aniso(W, H, 6, 20, 5) + (1 - depth) * 0.25) * cfg["clouds"]
    heat = np.clip(heat + cloud * 0.5 * (1 - depth), 0, 1)
    # loose flecks above the crest
    layer = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(layer)
    for _ in range(140):
        x = random.uniform(0, W)
        t_y = float(top[0, int(min(W - 1, x))]) * H
        y = t_y - abs(random.gauss(0, 40)) - 4
        r = random.uniform(0.9, 3.0)
        d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    flecks = np.asarray(layer.filter(ImageFilter.GaussianBlur(0.7)), dtype=np.float32) / 255.0
    flecks *= smoothstep(0.1, 0.7, 1 - nx + 0.3)         # more flecks on the heavy (left) side
    alpha = np.clip(body * 0.97 + haze + flecks, 0, 1)
    heat = np.maximum(heat * np.clip(body + haze, 0, 1), flecks)
    heat = np.where(body > 0.02, heat, np.maximum(haze * 0.25, flecks))
    return compose(alpha, heat, cfg["palette"])

# ---- 128x128 sprites ------------------------------------------------------

def sprite(school, seed, spikes, ragged, size=128):
    r = random.Random(seed)
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    c = size / 2
    pts = []
    for i in range(spikes * 2):
        ang = math.tau * i / (spikes * 2) + r.uniform(-0.08, 0.08)
        rad = (58 if i % 2 == 0 else 22) * (1 + r.uniform(-ragged, ragged))
        pts.append((c + math.cos(ang) * rad, c + math.sin(ang) * rad))
    d.polygon(pts, fill=255)
    d.ellipse([c - 24, c - 24, c + 24, c + 24], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1.3))
    a = np.asarray(mask, dtype=np.float32) / 255.0
    a = smoothstep(0.3, 0.65, a)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    dist = np.hypot(xx - c, yy - c) / 60
    noise = np.asarray(Image.fromarray((np.random.default_rng(seed).random((size, size)) * 255).astype(np.uint8))
                       .filter(ImageFilter.GaussianBlur(5)), dtype=np.float32) / 255.0
    heat = np.clip(1.0 - dist * 0.9 + (noise - 0.5) * 0.4, 0, 1)
    return compose(a * 0.95, heat, PALETTES[school])


SPRITES = {  # school: ((spikes, ragged) for sprite 1, sprite 2)
    "fire": ((9, 0.35), (7, 0.45)), "frost": ((6, 0.05), (8, 0.12)),
    "shadow": ((10, 0.5), (8, 0.55)), "arcane": ((12, 0.2), (8, 0.15)),
    "nature": ((7, 0.4), (9, 0.4)), "holy": ((12, 0.08), (16, 0.1)),
    "chaos": ((5, 0.4), (7, 0.35)),
}

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    mb.OUT = OUT
    makers = {"fire": fx_fire, "frost": lambda: painterly("frost"), "shadow": fx_shadow,
              "arcane": fx_arcane, "nature": lambda: painterly("nature"), "holy": fx_holy,
              "chaos": lambda: painterly("chaos")}
    only = sys.argv[2:]  # optional: regenerate just these schools
    for index, (school, make) in enumerate(makers.items()):
        if only and school not in only:
            continue
        mb.save(make(), f"fx_{school}.png")
        for i, (spikes, ragged) in enumerate(SPRITES[school], 1):
            mb.save(sprite(school, 1000 * (index + 1) + i, spikes, ragged), f"sp_{school}_{i}.png")

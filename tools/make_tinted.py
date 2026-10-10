#!/usr/bin/env python3
"""Hemo: blood as the single texture, tinted per damage school.

Reads the original blood textures in <dir> (made by make_blood.py) and writes:
  blood_left_t / blood_right_t / splat_1_t..3_t   grey-shaded copies that take
      any colour through SetVertexColor (multiply), so one blood serves every
      school. The red originals stay for Physical.
  fx_skulls.png / sp_skull_1..2.png               Shadow's black smoke with
      skulls (death-knight look), drawn here, no third-party art.
Usage: python3 make_tinted.py <Textures dir>
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

DIR = sys.argv[1] if len(sys.argv) > 1 else "."
W, H = 1024, 512
rng = np.random.default_rng(666)
random.seed(666)


def load(name):
    return np.asarray(Image.open(os.path.join(DIR, name)).convert("RGBA"), dtype=np.float32) / 255.0


def save(arr, name):
    img = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), "RGBA")
    path = os.path.join(DIR, name)
    img.save(path, optimize=True)
    print(f"{name}: {img.size} {os.path.getsize(path) // 1024} KB")


def tintable(src, dst):
    """Keep the shape (alpha) and the shading, drop the red: a grey that a
    vertex colour turns into any hue without losing the blood's depth."""
    im = load(src)
    alpha, red = im[..., 3], im[..., 0]
    solid = alpha > 0.03
    lo, hi = np.percentile(red[solid], 2), np.percentile(red[solid], 98)
    shade = np.clip((red - lo) / (hi - lo + 1e-6), 0, 1)
    grey = 0.40 + 0.50 * shade
    out = np.stack([grey, grey, grey, alpha], axis=-1)
    save(out, dst)


def fbm(w, h, octaves=5, base=4, persistence=0.55):
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


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# Skulls -------------------------------------------------------------------

def skull_masks(size=256):
    """(body, sockets) masks. The body is a skull silhouette with eye sockets,
    nose and teeth cut out; sockets are just the eye holes (they get a cold
    glow). Drawn at 4x and shrunk so the edges are smooth."""
    s = size * 4
    body = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(body)
    eyes = Image.new("L", (s, s), 0)
    de = ImageDraw.Draw(eyes)
    cx = s / 2
    d.ellipse([cx - 0.36 * s, 0.07 * s, cx + 0.36 * s, 0.66 * s], fill=255)
    d.rounded_rectangle([cx - 0.25 * s, 0.50 * s, cx + 0.25 * s, 0.80 * s], radius=0.09 * s, fill=255)
    d.rounded_rectangle([cx - 0.21 * s, 0.76 * s, cx + 0.21 * s, 0.93 * s], radius=0.05 * s, fill=255)
    for sign in (-1, 1):
        ex = cx + sign * 0.15 * s
        box = [ex - 0.105 * s, 0.34 * s, ex + 0.105 * s, 0.56 * s]
        d.ellipse(box, fill=0)
        de.ellipse([box[0] + 0.02 * s, box[1] + 0.03 * s, box[2] - 0.02 * s, box[3] - 0.03 * s], fill=255)
    d.polygon([(cx, 0.55 * s), (cx - 0.045 * s, 0.68 * s), (cx + 0.045 * s, 0.68 * s)], fill=0)
    d.rectangle([cx - 0.21 * s, 0.775 * s, cx + 0.21 * s, 0.795 * s], fill=0)
    for i in range(-3, 4):
        x = cx + i * 0.058 * s
        d.rectangle([x - 0.005 * s, 0.70 * s, x + 0.005 * s, 0.775 * s], fill=0)
        d.rectangle([x - 0.005 * s, 0.795 * s, x + 0.005 * s, 0.90 * s], fill=0)
    shrink = lambda im: np.asarray(im.resize((size, size), Image.LANCZOS), dtype=np.float32) / 255.0
    return shrink(body), shrink(eyes)


SKULL, EYES = skull_masks()


def paste_skull(canvas, cx, cy, size, angle, strength):
    """Add a rotated, scaled skull: canvas[...,0] = bone, canvas[...,1] = eye glow."""
    for channel, source in ((0, SKULL), (1, EYES)):
        mask = Image.fromarray((source * 255).astype(np.uint8)).resize((size, size), Image.LANCZOS)
        mask = mask.rotate(angle, resample=Image.BICUBIC, expand=True)
        m = np.asarray(mask, dtype=np.float32) / 255.0
        h, w = m.shape
        x0, y0 = int(cx - w / 2), int(cy - h / 2)
        xs, ys = max(0, x0), max(0, y0)
        xe, ye = min(canvas.shape[1], x0 + w), min(canvas.shape[0], y0 + h)
        if xe <= xs or ye <= ys:
            continue
        sub = m[ys - y0:ye - y0, xs - x0:xe - x0] * strength
        region = canvas[ys:ye, xs:xe]
        region[..., channel] = np.maximum(region[..., channel], sub)


def blur(a, radius):
    return np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius)),
                      dtype=np.float32) / 255.0


def smoke_alpha(w, h):
    """Wispy black smoke, thick on the left edge and corners, streaked upward."""
    n = fbm(w, h, 5, 4)
    streak = fbm(w, h, 4, 2)
    streak = np.asarray(Image.fromarray((streak * 255).astype(np.uint8)).resize((w // 6, h)).resize((w, h), Image.BICUBIC),
                        dtype=np.float32) / 255.0
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    edge = np.clip(1.0 - xx / (w * 0.85), 0, 1) ** 0.8
    vert = 0.45 + 0.55 * np.abs(yy / h - 0.5) * 2
    density = edge * (0.6 + 0.4 * vert) + (n - 0.5) * 0.5 + (streak - 0.5) * 0.35
    return smoothstep(0.16, 0.58, density)


def decay(mask, w, h, amount=0.55):
    """Eat the skull away with noise so it looks ghostly and weathered."""
    holes = fbm(w, h, 5, 10)
    return mask * smoothstep(0.34, 0.60, holes + (0.5 - amount) * 0.3)


def compose(smoke, bone, eyes, smoke_strength=0.95):
    glow_bone = blur(bone, 7)
    glow_eyes = blur(eyes, 5)
    alpha = np.clip(smoke * smoke_strength + glow_bone * 0.30 + glow_eyes * 1.1, 0, 1)
    alpha = np.maximum(alpha, bone * 0.80)
    black = np.array([0.02, 0.016, 0.035], dtype=np.float32)
    ash = np.array([0.42, 0.47, 0.58], dtype=np.float32)
    eyeglow = np.array([0.30, 0.85, 1.00], dtype=np.float32)
    rgb = black[None, None, :] + (ash - black)[None, None, :] * bone[..., None]
    rgb = rgb * (1 - glow_eyes[..., None] * 0.9) + eyeglow[None, None, :] * (glow_eyes[..., None] * 0.9)
    return np.concatenate([rgb, alpha[..., None]], axis=-1)


def make_skull_layer():
    smoke = smoke_alpha(W, H)
    canvas = np.zeros((H, W, 2), dtype=np.float32)
    skulls = [(130, 150, 120, 12, 0.60), (95, 400, 100, 18, 0.50), (270, 290, 135, -10, 0.45),
              (340, 70, 80, -20, 0.38), (450, 420, 70, 10, 0.32)]
    for cx, cy, size, angle, strength in skulls:
        paste_skull(canvas, cx, cy, size, angle, strength)
    bone = blur(decay(canvas[..., 0], W, H), 1.6)
    # Eye glow sits where the body is cut out, so test against a widened body.
    near_bone = blur(canvas[..., 0], 8) > 0.12
    eyes = np.clip(blur(canvas[..., 1] * near_bone, 1.5) * 1.8, 0, 1)
    save(compose(smoke, bone, eyes), "fx_skulls.png")


def make_skull_sprite(index, angle):
    size = 128
    canvas = np.zeros((size, size, 2), dtype=np.float32)
    paste_skull(canvas, size / 2, size / 2 + 2, 84, angle, 0.62)
    bone = blur(canvas[..., 0], 0.8)
    eyes = np.clip(blur(canvas[..., 1], 1.2) * 1.8, 0, 1)
    ring = blur(bone, 9)
    out = compose(ring * 0.9, bone, eyes, 1.0)
    save(out, f"sp_skull_{index}.png")


if __name__ == "__main__":
    tintable("blood_left.png", "blood_left_t.png")
    tintable("blood_right.png", "blood_right_t.png")
    for i in (1, 2, 3):
        tintable(f"splat_{i}.png", f"splat_{i}_t.png")
    make_skull_layer()
    make_skull_sprite(1, -8)
    make_skull_sprite(2, 12)

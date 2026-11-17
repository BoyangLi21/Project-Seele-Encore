"""Original resource pack SEELE_GreenGrassSide.zip: grass-block sides green all the way down (from R63r, owner-approved).

On hillsides the grass block's side shows dirt with a thin tinted fringe, read as brown stripes.
This pack replaces minecraft:block/grass_block_side_overlay with an opaque greyscale grass texture,
so the biome tint colours the whole side. The SEELE terrain pack is 128 px with LabPBR maps, so the
pack also brings a 128 px albedo, a near-flat normal map and a grass specular map (subsurface on);
otherwise that pack's fringe-shaped maps would still shade the side under the shader.

Everything is procedural: seeded, tileable value noise, brightness matched to the terrain pack's
grass top (mean 128, spread 25). No texture is copied or downloaded.

  python tools/gen_green_grass_side.py <out.zip> [preview.png]
"""
import io
import json
import sys
import zipfile

import numpy as np
from PIL import Image

SIZE = 128
SEED = 0x5EE1E6
BLOCK = 'assets/minecraft/textures/block/'
STAMP = (2026, 11, 15, 0, 0, 0)


def tile_noise(rng, cells_x, cells_y):
    """Value noise that wraps at the texture edge, so stacked and neighbouring blocks tile."""
    lattice = rng.random((cells_y, cells_x))
    u = np.arange(SIZE) * cells_x / SIZE
    v = np.arange(SIZE) * cells_y / SIZE
    i0, j0 = np.floor(u).astype(int), np.floor(v).astype(int)
    fu, fv = u - i0, v - j0
    fu, fv = fu * fu * (3 - 2 * fu), fv * fv * (3 - 2 * fv)
    i1, j1 = (i0 + 1) % cells_x, (j0 + 1) % cells_y
    i0, j0 = i0 % cells_x, j0 % cells_y
    a = lattice[np.ix_(j0, i0)]; b = lattice[np.ix_(j0, i1)]
    c = lattice[np.ix_(j1, i0)]; d = lattice[np.ix_(j1, i1)]
    top = a + (b - a) * fu[None, :]
    bottom = c + (d - c) * fu[None, :]
    return top + (bottom - top) * fv[:, None]


def textures():
    # The 4-cell layer is kept low: one large blotch repeating on every block reads as a pattern on a hillside.
    rng = np.random.default_rng(SEED)
    field = sum(amp * (tile_noise(rng, cells, cells) - 0.5)
                for amp, cells in ((0.15, 4), (0.22, 8), (0.20, 16), (0.14, 32), (0.10, 64)))
    # Blades on a vertical face: narrow, taller-than-wide streaks.
    field = field + 0.16 * (tile_noise(rng, 64, 8) - 0.5) + 0.05 * rng.standard_normal((SIZE, SIZE))
    grey = 128 + 25 * (field - field.mean()) / field.std()
    grey = np.clip(np.round(grey), 40, 230).astype(np.uint8)
    albedo = np.dstack([grey, grey, grey, np.full_like(grey, 255)])

    height = grey.astype(np.float64) / 255
    gx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) / 2
    gy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) / 2
    strength = 1.6
    nx, ny = -gx * strength, -gy * strength
    nz = 1 / np.sqrt(1 + nx * nx + ny * ny)
    nx, ny = nx * nz, ny * nz
    # LabPBR 1.3 normal: RG = tangent normal, B = ambient occlusion (255 none), A = height (255 top).
    normal = np.dstack([np.clip(np.round(128 + 127 * nx), 0, 255), np.clip(np.round(128 + 127 * ny), 0, 255),
                        np.full(grey.shape, 255), np.full(grey.shape, 255)]).astype(np.uint8)
    # LabPBR 1.3 specular: R = smoothness, G = F0 (dielectric), B = subsurface (65-255), A = 255 no emission.
    rough = np.clip(np.round(34 + 10 * (tile_noise(rng, 16, 16) - 0.5)), 0, 255)
    specular = np.dstack([rough, np.full(grey.shape, 10), np.full(grey.shape, 150), np.full(grey.shape, 255)]).astype(np.uint8)
    icon = (albedo[::2, ::2, :3].astype(np.float64) * np.array([0.47, 0.74, 0.32])).astype(np.uint8)
    return albedo, normal, specular, icon


def png(array, mode):
    out = io.BytesIO()
    Image.fromarray(array, mode).save(out, 'PNG', optimize=False)
    return out.getvalue()


def build(target, preview=None):
    albedo, normal, specular, icon = textures()
    files = {
        'pack.mcmeta': json.dumps({'pack': {'pack_format': 15, 'description': 'SEELE 原创：山坡草方块侧面全绿（程序生成）'}},
                                  ensure_ascii=False, indent=2).encode('utf8'),
        'pack.png': png(icon, 'RGB'),
        BLOCK + 'grass_block_side_overlay.png': png(albedo, 'RGBA'),
        BLOCK + 'grass_block_side_overlay_n.png': png(normal, 'RGBA'),
        BLOCK + 'grass_block_side_overlay_s.png': png(specular, 'RGBA'),
        'LICENSE.txt': ('原创素材：tools/gen_green_grass_side.py 程序生成（固定种子的可平铺噪声），'
                        '随 Project SEELE 按 MIT 许可发布。不含 Mojang 或任何其他资源包的贴图。\n').encode('utf8'),
    }
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[name])
    if preview:
        # Side faces as the game would tint them with the world's grass colour (#7B8F53, 8097875).
        tint = np.array([0x7B, 0x8F, 0x53]) / 255
        green = (albedo[..., :3] * tint).astype(np.uint8)
        Image.fromarray(np.tile(green, (2, 3, 1)), 'RGB').resize((SIZE * 6, SIZE * 4), Image.NEAREST).save(preview)


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)

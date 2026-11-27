"""Original Blockbench passenger ship for MTR 4. The berth length bounds the model to 19 metres.

Visual reference: Odakyu Hakone's Queen Ashinoko (gold hull, wood salon and viewing deck).
The model, texture atlas, deck surfaces and operable boarding gates are authored here.
"""

from collections import defaultdict
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL
import json
import math
import numpy as np
from PIL import Image

SHIP = "projectseele_ashi_excursion"
PALETTE = {
    "keel": (40, 49, 56),
    "hull": (175, 109, 44),
    "gold": (238, 188, 92),
    "cream": (227, 210, 171),
    "teak": (137, 88, 56),
    "walnut": (68, 43, 39),
    "brass": (204, 151, 75),
    "red": (129, 53, 53),
    "iron": (55, 64, 68),
    "white": (239, 229, 208),
    "velvet": (46, 91, 90),
    "rope": (128, 103, 78),
    "black": (29, 35, 42),
    "light": (255, 222, 150),
    "green": (40, 166, 107),
    "signal": (224, 67, 51),
}


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), "utf8")


def material_layout(elements, materials):
    # MTR 4.0.5 decodes native cuboid box UV and integer uv_offset. Pack each wood,
    # metal, fabric or light into a swatch large enough for its biggest unfolded box.
    footprints = {m: [4, 4] for m in PALETTE}
    for element, material in zip(elements, materials):
        dx, dy, dz = np.maximum(
            1, np.rint(np.array(element["to"]) - element["from"]).astype(int)
        )
        limits = footprints[material]
        limits[0] = max(limits[0], int(2 * (dx + dz) + 6))
        limits[1] = max(limits[1], int(dy + dz + 6))
    layout = {}
    x = y = row = 0
    for material in sorted(footprints, key=lambda m: -footprints[m][1]):
        width, height = footprints[material]
        if x + width > 1024:
            x = 0
            y += row
            row = 0
        layout[material] = (x, y, width, height)
        x += width
        row = max(row, height)
    return layout, 2 ** max(1, (y + row - 1).bit_length())


def atlas(path, layout, height):
    size = 32
    image = np.zeros((height, 1024, 3), dtype=np.uint8)
    rng = np.random.default_rng(753)
    for i, (name, rgb) in enumerate(PALETTE.items()):
        y, x = np.mgrid[:size, :size]
        grain = rng.normal(0, 2, (size, size))
        if name in ("teak", "walnut", "hull"):
            grain += np.sin(x * 0.44 + np.sin(y * 0.13) * 0.55) * 2 - (x % 8 == 0) * 10
            grain -= ((y + ((x // 8) % 2) * 16) % 32 == 0) * 8
        elif name in ("gold", "brass"):
            grain += np.sin(x * 0.14 + y * 0.05) * 5
        piece = np.clip(
            np.array(rgb)[None, None, :] + grain[:, :, None], 0, 255
        ).astype("uint8")
        sx, sy, width, h = layout[name]
        image[sy : sy + h, sx : sx + width] = np.tile(
            piece, (math.ceil(h / size), math.ceil(width / size), 1)
        )[:h, :width]
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image).save(path)


def model(root):
    elements, materials, groups = [], [], defaultdict(list)

    def uid(key):
        return str(uuid5(NAMESPACE_URL, SHIP + "/" + key))

    def box(name, start, end, material, group="main", rotation=None, pivot=None):
        ident = uid(f"{group}/{len(elements)}/{name}")
        v = lambda a: [round(float(n) * 16, 4) for n in a]
        data = dict(
            name=name,
            type="cube",
            uuid=ident,
            box_uv=True,
            autouv=0,
            origin=v(pivot or (0, 0, 0)),
        )
        data["from"], data["to"] = v(start), v(end)
        if rotation:
            data["rotation"] = [round(k, 4) for k in rotation]
        elements.append(data)
        materials.append(material)
        groups[group].append(ident)

    def floor(x, y, z, X, Z):
        box("walkable deck", (x, y, z), (X, y, Z), "teak", "floors")

    def beam(label, a, b, radius, colour):
        dx, dy, dz = np.array(b) - np.array(a)
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        # Rotate a rod whose local axis is +Z, about its start.
        pitch = -math.degrees(math.asin(dy / length))
        yaw = math.degrees(math.atan2(dx, dz))
        x, y, z = a
        box(
            label,
            (x - radius, y - radius, z),
            (x + radius, y + radius, z + length),
            colour,
            rotation=(pitch, yaw, 0),
            pivot=(x, y, z),
        )

    # Fair the bow and transom across thirty-eight half-metre stations. Each strake has
    # its own waterline, flare and sheer. There is an open perimeter promenade.
    stations = [
        (-9.5, 0.07),
        (-8.8, 0.77),
        (-7.8, 1.65),
        (-6.3, 2.43),
        (-4.5, 2.9),
        (-2.8, 3.05),
        (3.8, 3.05),
        (6.5, 2.9),
        (8.1, 2.45),
        (9.0, 1.86),
        (9.4, 1.4),
    ]

    def breadth(z):
        return float(np.interp(z, *zip(*stations)))

    for z in np.arange(-9.5, 9.4, 0.5):
        end = min(z + 0.5, 9.4)
        mid = (z + end) / 2
        radius = breadth(mid)
        for y0, y1, fac, mat in [
            (-1.18, -0.76, 0.56, "keel"),
            (-0.76, -0.4, 0.76, "keel"),
            (-0.4, -0.26, 0.89, "red"),
            (-0.26, 0.21, 0.95, "hull"),
            (0.21, 0.34, 1, "gold"),
            (0.34, 0.72, 1, "hull"),
            (0.72, 0.79, 1.015, "brass"),
            (0.79, 0.86, 1, "teak"),
        ]:
            box(
                "swept hull strake",
                (-radius * fac, y0, z),
                (radius * fac, y1, end),
                mat,
            )
        floor(-radius, 0.86, z, radius, end)
    # Glazed salon uses open windows so that a seated or standing player can see the lake.
    # Leave opposing midship gates and the starboard aft stairwell free of furniture.
    for side in (-1, 1):
        x = side * 2.55
        for za, zb in [(-5.75, -1.19), (1.19, 5.25)]:
            box("salon sill", (x - 0.08, 0.86, za), (x + 0.08, 1.55, zb), "walnut")
            box(
                "brass picture rail",
                (x - 0.095, 1.50, za),
                (x + 0.095, 1.58, zb),
                "brass",
            )
            box("clerestory", (x - 0.08, 2.93, za), (x + 0.08, 3.18, zb), "cream")
            for z in np.arange(za, zb + 0.3, 1.05):
                box(
                    "varnished mullion",
                    (x - 0.075, 1.54, z),
                    (x + 0.075, 2.96, min(z + 0.11, zb + 0.16)),
                    "teak",
                )
        # Sliding gates have independent paired panels and an MTR doorway box on each side.
        for direction in (-1, 1):
            z0, z1 = (-1.14, -0.015) if direction < 0 else (0.015, 1.14)
            group = f"gate_{side}_{direction}"
            for yy in (1.08, 1.33, 1.62):
                box(
                    "brass gate bars",
                    (side * 2.99 - 0.035, yy, z0),
                    (side * 2.99 + 0.035, yy + 0.045, z1),
                    "brass",
                    group,
                )
            for zz in (z0, z1 - 0.055):
                box(
                    "gate stile",
                    (side * 2.99 - 0.04, 0.86, zz),
                    (side * 2.99 + 0.04, 1.69, zz + 0.055),
                    "walnut",
                    group,
                )
        xa, xb = sorted((side * 2.78, side * 4.76))
        box(
            "embarkation threshold",
            (xa, 0.86, -1.14),
            (xb, 0.86, 1.14),
            "cream",
            f"doorway_{side}",
        )
        for za, zb in [(-8.4, -1.17), (1.17, 8.9)]:
            zz = np.linspace(za, zb, math.ceil(zb - za) + 1)
            for a, b in zip(zz, zz[1:]):
                ax, bx = side * (breadth(a) - 0.08), side * (breadth(b) - 0.08)
                for yy in (1.14, 1.63):
                    beam("promenade rail", (ax, yy, a), (bx, yy, b), 0.041, "brass")
                box(
                    "rail post",
                    (ax - 0.045, 0.84, a - 0.045),
                    (ax + 0.045, 1.7, a + 0.045),
                    "cream",
                )
    for z in (-5.7, 5.19):
        for x in (-2.5, -1.72, -0.99, 0.99, 1.72, 2.5):
            box(
                "end wall carving",
                (x - 0.07, 0.86, z),
                (x + 0.07, 3.13, z + 0.14),
                "teak",
            )
        for x, X in ((-2.55, -0.98), (0.98, 2.55)):
            box("salon end panelling", (x, 0.86, z), (X, 1.55, z + 0.14), "walnut")
    for side in (-1, 1):
        for z in (-4.65, -2.8, 2.05, 3.9):
            x = side * 1.76
            box(
                "banquette base",
                (x - 0.44, 0.86, z),
                (x + 0.44, 1.16, z + 0.68),
                "walnut",
            )
            box(
                "upholstered cushion",
                (x - 0.45, 1.16, z),
                (x + 0.45, 1.26, z + 0.68),
                "velvet" if z < 0 else "red",
            )
            box(
                "backrest",
                (x - 0.44, 1.24, z + 0.56),
                (x + 0.44, 1.74, z + 0.71),
                "velvet" if z < 0 else "red",
            )
    for x, X, z, Z in [(-2.7, 2.7, -5.95, 3.45), (-2.7, 1.30, 3.45, 5.72)]:
        box("salon overhead", (x, 3.10, z), (X, 3.23, Z), "cream")
        box("upper promenade", (x, 3.23, z), (X, 3.31, Z), "teak")
        floor(x, 3.31, z, X, Z)
    for k in range(8):
        z = 7.84 - k * 0.48
        y = 0.86 + (k + 1) * (0.30625)
        box("after companionway", (1.32, 0.86, z - 0.47), (2.52, y, z + 0.012), "teak")
        floor(1.32, y, z - 0.47, 2.52, z + 0.012)
    box("upper stair landing", (1.32, 3.10, 3.40), (2.52, 3.31, 4.03), "teak")
    floor(1.32, 3.31, 3.40, 2.52, 4.03)
    for side in (-1, 1):
        x = side * 2.63
        for yy in (3.69, 4.18):
            beam(
                "upper brass rail",
                (x, yy, -5.88),
                (x, yy, 5.66 if side < 0 else 3.42),
                0.045,
                "brass",
            )
        for z in np.arange(-5.8, 5.65 if side < 0 else 3.41, 1):
            box("standard", (x - 0.045, 3.31, z), (x + 0.045, 4.23, z + 0.09), "cream")
    for z in (-5.86, 5.66):
        for yy in (3.69, 4.18):
            beam(
                "end rail",
                (-2.63, yy, z),
                (2.63 if z < 0 else 1.28, yy, z),
                0.043,
                "brass",
            )
    # Wheelhouse and forward golden prow give the vessel a recognisable profile at range.
    for x in (-1.5, 1.5):
        box(
            "wheelhouse side", (x - 0.07, 3.31, -4.83), (x + 0.07, 4.05, -2.58), "cream"
        )
        for z in (-4.85, -3.76, -2.64):
            box(
                "bridge window jamb",
                (x - 0.075, 4.05, z),
                (x + 0.075, 5.12, z + 0.1),
                "teak",
            )
    for x in (-1.48, -0.51, 0.51, 1.48):
        box(
            "windshield frame", (x - 0.07, 4.05, -4.86), (x + 0.07, 5.12, -4.74), "teak"
        )
    box("chart table", (-1.51, 3.31, -4.86), (1.51, 4.07, -4.6), "cream")
    box("bridge roof", (-1.68, 5.10, -5.03), (1.68, 5.29, -2.4), "cream")
    for side, col in ((-1, "signal"), (1, "green")):
        box(
            "running light",
            (side * 1.62 - 0.06, 5.28, -4.48),
            (side * 1.62 + 0.06, 5.48, -4.31),
            col,
        )
    for z, top in [(-6.75, 8.4), (2.5, 9.4)]:
        bottom = 0.86 if z < 0 else 3.31
        box(
            "lower spar", (-0.14, bottom, z - 0.14), (0.14, top - 1, z + 0.14), "walnut"
        )
        box(
            "topmast",
            (-0.078, top - 1, z - 0.078),
            (0.078, top + 0.38, z + 0.078),
            "teak",
        )
        for h, width in ((top - 0.9, 1.65), (top - 2.15, 2.04)):
            beam("yardarm", (-width, h, z), (width, h, z), 0.066, "teak")
        for side in (-1, 1):
            beam(
                "shroud",
                (side * (2 if z < 0 else 2.45), 1.72 if z < 0 else 4.18, z + 0.75),
                (0, top - 0.55, z),
                0.023,
                "rope",
            )
        box("pennant", (0, top - 0.38, z - 0.04), (0.035, top + 0.23, z + 0.95), "red")
    beam("forestay", (0, 8.15, -6.75), (0, 1.47, -9.4), 0.025, "rope")
    beam("main stay", (0, 8.18, -6.75), (0, 9.22, 2.5), 0.025, "rope")
    beam("after stay", (0, 9.22, 2.5), (0, 1.55, 9.1), 0.025, "rope")
    layout, texture_height = material_layout(elements, materials)
    for e, mat in zip(elements, materials):
        x, y, *_ = layout[mat]
        e["uv_offset"] = [x + 2, y + 2]
    outliner = [
        dict(
            name=name,
            uuid=uid(name),
            origin=[0, 0, 0],
            children=children,
            visibility=True,
            export=True,
        )
        for name, children in groups.items()
    ]
    data = dict(
        meta={
            "format_version": "4.10",
            "model_format": "modded_entity",
            "box_uv": True,
        },
        name=SHIP,
        model_identifier=SHIP,
        resolution=dict(width=1024, height=texture_height),
        elements=elements,
        outliner=outliner,
        textures=[],
    )
    assets = root / "assets/projectseele"
    save(assets / "models/vehicle/ashi.bbmodel", data)
    atlas(assets / "textures/vehicle/ashi.png", layout, texture_height)
    parts = [
        dict(names=["main"], positionDefinitions=["main"], renderStage="EXTERIOR"),
        dict(names=["floors"], positionDefinitions=["main"], type="FLOOR"),
        dict(
            names=["doorway_-1", "doorway_1"],
            positionDefinitions=["main"],
            type="DOORWAY",
        ),
    ]
    for side in (-1, 1):
        for direction in (-1, 1):
            parts.append(
                dict(
                    names=[f"gate_{side}_{direction}"],
                    positionDefinitions=["main"],
                    renderStage="EXTERIOR",
                    doorZMultiplier=-direction * 18,
                    doorAnimationType="BOUNCY_1",
                )
            )
    save(assets / "properties/vehicle/ashi.json", dict(parts=parts, modelYOffset=0.5))
    descriptor = dict(
        id=SHIP,
        name="芦之湖観光船 | Ashinoko Excursion",
        color="CC9943",
        transportMode="BOAT",
        length=19,
        width=6.1,
        bogie1Position=-5,
        bogie2Position=5,
        models=[
            dict(
                modelResource="projectseele:models/vehicle/ashi.bbmodel",
                textureResource="projectseele:textures/vehicle/ashi.png",
                modelPropertiesResource="projectseele:properties/vehicle/ashi.json",
                positionDefinitionsResource="mtr:properties/definition/boat_1.json",
            )
        ],
    )
    save(
        root / "assets/mtr/mtr_custom_resources.json",
        dict(vehicles=[descriptor], signs=[], rails=[], objects=[], lifts=[]),
    )
    save(
        root / "pack.mcmeta",
        dict(pack=dict(pack_format=15, description="Hakone lake excursion vessel")),
    )
    return data


if __name__ == "__main__":
    model(
        Path(__file__).resolve().parents[1]
        / "src/main/resources/resourcepacks/ashi_ship"
    )

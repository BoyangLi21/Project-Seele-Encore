"""Original cuboid satellite handsets and pixel atlases; no external artwork or fonts."""
from pathlib import Path
import json
import math
import random
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src/main/resources/assets/projectseele"
OUT = ROOT / ".Codex/phone-model-r54"
OUT.mkdir(parents=True, exist_ok=True)
GLYPHS = {
    "0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"], "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"], "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"], "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"], "9": ["111", "101", "111", "001", "111"],
    "A": ["010", "101", "111", "101", "101"], "B": ["110", "101", "110", "101", "110"],
    "C": ["111", "100", "100", "100", "111"], "D": ["110", "101", "101", "101", "110"],
    "E": ["111", "100", "110", "100", "111"], "F": ["111", "100", "110", "100", "100"],
    "G": ["111", "100", "101", "101", "111"], "H": ["101", "101", "111", "101", "101"],
    "I": ["111", "010", "010", "010", "111"], "L": ["100", "100", "100", "100", "111"],
    "M": ["10001", "11011", "10101", "10001", "10001"],
    "N": ["1001", "1101", "1011", "1001", "1001"], "O": ["111", "101", "101", "101", "111"],
    "P": ["110", "101", "110", "100", "100"], "R": ["110", "101", "110", "101", "101"],
    "S": ["111", "100", "111", "001", "111"], "T": ["111", "010", "010", "010", "010"],
    "U": ["101", "101", "101", "101", "111"], "V": ["101", "101", "101", "101", "010"],
    "X": ["101", "101", "010", "101", "101"], "Y": ["101", "101", "010", "010", "010"],
    "-": ["000", "000", "111", "000", "000"], "+": ["000", "010", "111", "010", "000"],
    "#": ["101", "111", "101", "111", "101"], "*": ["000", "101", "010", "101", "000"],
    " ": ["00"] * 5, "/": ["001", "001", "010", "100", "100"],
}


def rgb(color):
    return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))


def text(draw, at, value, color, scale=1):
    x, y = at
    for ch in value:
        glyph = GLYPHS[ch]
        for row, bits in enumerate(glyph):
            for col, bit in enumerate(bits):
                if bit == "1":
                    draw.rectangle((x+col*scale, y+row*scale, x+(col+1)*scale-1, y+(row+1)*scale-1), fill=color)
        x += (len(glyph[0])+1)*scale


THEMES = {
    "satellite_phone": dict(body="282D33", back="20252A", rim="5B6269", dark="10171C", keybase="1B2127", key="454E56", accent="C76D4B", metal="A1A9AB", screen="A8B49A", ink="2D4138", brand="NERV", line="FIELD 01"),
    "un_satellite_phone": dict(body="CED6D8", back="A7B4BA", rim="5D7888", dark="1A2C37", keybase="233D4B", key="4B6573", accent="5C9DB4", metal="D7DFE0", screen="A3C5C7", ink="2C4D58", brand="UN", line="FIELD 02"),
}


def atlas(name, theme):
    image = Image.new("RGB", (128, 128), rgb(theme["dark"]))
    draw = ImageDraw.Draw(image)
    rng = random.Random(54)
    colors = ["body", "back", "rim", "dark", "keybase", "key", "accent", "metal"]
    for n, slot in enumerate(colors):
        color = rgb(theme[slot])
        for y in range(16):
            for x in range(16):
                grain = rng.choice([-2, -1, 0, 0, 0, 1, 2])
                image.putpixel((n*16+x, y), tuple(max(0, min(255, c+grain)) for c in color))
    lcd, ink = rgb(theme["screen"]), rgb(theme["ink"])
    draw.rectangle((0, 24, 63, 55), fill=lcd)
    for y in range(27, 54, 2):
        for x in range(2, 62, 2):
            image.putpixel((x, y), tuple(max(0, c-7) for c in lcd))
    draw.line((1, 25, 62, 25), fill=tuple(min(255, c+17) for c in lcd))
    text(draw, (5, 29), "SATCOM", ink)
    text(draw, (5, 40), "CH --", ink)
    text(draw, (38, 47), theme["brand"], ink)
    draw.rectangle((53, 29, 59, 33), outline=ink)
    draw.rectangle((60, 30, 60, 32), fill=ink)
    draw.line((5, 50, 26, 50), fill=ink)
    draw.rectangle((64, 24, 111, 31), fill=rgb(theme["dark"]))
    for x in range(67, 109, 4):
        draw.line((x, 26, x, 29), fill=rgb(theme["rim"]))
    draw.rectangle((64, 36, 111, 43), fill=rgb(theme["body"]))
    text(draw, (67, 38), theme["brand"], rgb(theme["accent"]))
    draw.rectangle((64, 48, 111, 63), fill=rgb(theme["dark"]))
    text(draw, (67, 51), theme["line"], rgb(theme["metal"]))
    text(draw, (67, 58), "SAT / 90", rgb(theme["rim"]))
    for i, ch in enumerate("123456789*0#"):
        xx, yy = (i % 3)*12, 64+(i//3)*12
        draw.rectangle((xx, yy, xx+11, yy+11), fill=rgb(theme["key"]))
        draw.line((xx+1, yy+1, xx+10, yy+1), fill=rgb(theme["rim"]))
        text(draw, (xx+4, yy+3), ch, rgb("E4EBE6"))
    for yy, label, color in [(64, "MENU", theme["key"]), (80, "CALL", theme["accent"])]:
        draw.rectangle((48, yy, 71, yy+11), fill=rgb(color))
        text(draw, (51, yy+3), label, rgb("F0EEE6"))
    draw.rectangle((80, 72, 111, 95), fill=rgb(theme["back"]))
    for yy in range(76, 93, 4):
        draw.line((85, yy, 106, yy), fill=rgb(theme["dark"]))
    draw.rectangle((80, 104, 95, 119), fill=rgb(theme["accent"]))
    for yy in (107, 111, 115):
        draw.line((83, yy, 92, yy), fill=rgb(theme["rim"]))
    draw.rectangle((104, 104, 111, 111), fill=rgb(theme["rim"]))
    draw.line((106, 108, 109, 108), fill=rgb(theme["dark"]))
    path = ASSETS / "textures/item" / f"{name}_r54.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return image


def uv(rect):
    return [round(n/8, 5) for n in rect]


def make_model(name):
    elements = []
    swatches = {n: uv((i*16+2, 2, i*16+14, 14)) for i, n in enumerate(["body", "back", "rim", "dark", "keybase", "key", "accent", "metal"])}

    def box(label, a, b, surface="body", front=None, back=None):
        faces = {side: {"uv": swatches[surface], "texture": "#atlas"} for side in ["north", "south", "east", "west", "up", "down"]}
        if front is not None:
            faces["north"] = {"uv": uv(front), "texture": "#atlas"}
        if back is not None:
            faces["south"] = {"uv": uv(back), "texture": "#atlas"}
        elements.append({"name": label, "from": a, "to": b, "faces": faces})
        return elements[-1]

    # Non-overlapping stepped perimeter bands keep the corner silhouette softened.
    bands = [(5.15, 10.85, 1.2, 1.55), (4.8, 11.2, 1.55, 1.9), (4.6, 11.4, 1.9, 11.9), (4.8, 11.2, 11.9, 12.25), (5.15, 10.85, 12.25, 12.6)]
    for i, (left, right, low, high) in enumerate(bands):
        box(f"front_shell_{i}", [left, low, 6.78], [right, high, 7.97])
        box(f"rear_shell_{i}", [left, low, 8.03], [right, high, 9.18], "back")
        box(f"rubber_seal_{i}", [left+.04, low, 7.97], [right-.04, high, 8.03], "dark")
    box("front_face_recess", [4.97, 1.95, 6.58], [11.03, 11.97, 6.79], "body")
    box("speaker_mount", [5.75, 11.33, 6.44], [10.25, 11.96, 6.59], "dark", front=(64, 24, 112, 32))
    box("identity_plate", [5.55, 10.79, 6.49], [10.45, 11.23, 6.59], "body", front=(64, 36, 112, 44))
    box("screen_well", [5.26, 7.58, 6.48], [10.74, 10.57, 6.59], "dark")
    box("screen_rim_left", [5.2, 7.52, 6.28], [5.5, 10.63, 6.59], "rim")
    box("screen_rim_right", [10.5, 7.52, 6.28], [10.8, 10.63, 6.59], "rim")
    box("screen_rim_top", [5.5, 10.31, 6.28], [10.5, 10.63, 6.59], "rim")
    box("screen_rim_bottom", [5.5, 7.52, 6.28], [10.5, 7.84, 6.59], "rim")
    box("recessed_dot_matrix_lcd", [5.5, 7.84, 6.38], [10.5, 10.31, 6.48], "dark", front=(0, 24, 64, 56))
    box("keypad_recess", [5.1, 1.65, 6.47], [10.9, 6.33, 6.59], "keybase")
    for i, ch in enumerate("123456789*0#"):
        xx, yy = 9.9-(i % 3)*1.9, 5.75-(i//3)*1.12
        box(f"key_{i}_foot", [xx-.76, yy-.46, 6.33], [xx+.76, yy+.46, 6.5], "keybase")
        ux, uy = (i % 3)*12, 64+(i//3)*12
        box(f"key_{i}_cap", [xx-.65, yy-.35, 6.18], [xx+.65, yy+.35, 6.34], "key", front=(ux, uy+1, ux+12, uy+10))
    for left, tile, surface, label in [(8.15, 64, "key", "menu"), (5.35, 80, "accent", "call")]:
        box(f"{label}_foot", [left, 6.62, 6.35], [left+2.5, 7.28, 6.59], "keybase")
        box(f"{label}_cap", [left+.12, 6.73, 6.18], [left+2.38, 7.17, 6.36], surface, front=(48, tile, 72, tile+12))
    box("ptt_housing", [4.32, 8.17, 7.12], [4.62, 10.35, 8.68], "dark")
    ptt = box("ptt_switch", [4.12, 8.43, 7.31], [4.34, 10.09, 8.49], "accent")
    ptt["faces"]["west"] = {"uv": uv((80, 104, 96, 120)), "texture": "#atlas"}
    for yy in [8.48, 9.7]:
        box("volume_switch", [11.38, yy, 7.35], [11.64, yy+.85, 8.3], "rim")
    box("antenna_socket", [5.24, 12.28, 7.17], [6.78, 12.95, 8.71], "dark")
    box("antenna_collar", [5.38, 12.87, 7.31], [6.64, 13.2, 8.57], "rim")
    box("short_antenna", [5.56, 13.13, 7.49], [6.46, 15.36, 8.39], "dark")
    box("antenna_tip", [5.66, 15.36, 7.59], [6.36, 15.64, 8.29], "dark")
    for yy in [13.45, 14.05]:
        box("antenna_grip_ring", [5.5, yy, 7.43], [6.52, yy+.12, 8.45], "back")
    box("rear_battery_cover", [5.12, 2.0, 9.17], [10.88, 9.98, 9.31], "back", back=(80, 72, 112, 96))
    box("rear_serial_plate", [5.7, 10.45, 9.17], [10.3, 11.95, 9.27], "dark", back=(64, 48, 112, 64))
    box("battery_latch", [7.1, 1.66, 9.17], [8.9, 2.05, 9.42], "rim")
    for xx, yy in [(5.13, 2.02), (10.87, 2.02), (5.13, 11.93), (10.87, 11.93)]:
        box("recessed_fastener", [xx-.12, yy-.12, 6.48], [xx+.12, yy+.12, 6.59], "metal", front=(104, 104, 112, 112))
    display = {
        "gui": {"rotation": [8, 155, 0], "translation": [0, -.15, 0], "scale": [.95]*3},
        "firstperson_righthand": {"rotation": [8, 165, -6], "translation": [0, 1.5, 0], "scale": [.68]*3},
        "firstperson_lefthand": {"rotation": [8, 165, -6], "translation": [0, 1.5, 0], "scale": [.68]*3},
        "thirdperson_righthand": {"rotation": [0, 180, 0], "translation": [0, 1.4, 0], "scale": [.48]*3},
        "thirdperson_lefthand": {"rotation": [0, 180, 0], "translation": [0, 1.4, 0], "scale": [.48]*3},
        "fixed": {"rotation": [0, 180, 0], "translation": [0, 0, 0], "scale": [.85]*3},
        "ground": {"rotation": [0, 0, 90], "translation": [0, 1, 0], "scale": [.35]*3},
    }
    model = {"credit": "Project SEELE original industrial handset, procedural pixel atlas", "parent": "minecraft:block/block", "ambientocclusion": True, "gui_light": "front", "textures": {"particle": f"projectseele:item/{name}_r54", "atlas": f"projectseele:item/{name}_r54"}, "elements": elements, "display": display}
    (ASSETS / "models/item" / f"{name}.json").write_text(json.dumps(model, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return model


def preview(model, atlas_image, path):
    # Orthographic source-model preview, not a game screenshot.
    import numpy as np
    angle = math.radians(155)
    tilt = math.radians(8)
    ry = np.array([[math.cos(angle), 0, math.sin(angle)], [0, 1, 0], [-math.sin(angle), 0, math.cos(angle)]])
    rx = np.array([[1, 0, 0], [0, math.cos(tilt), -math.sin(tilt)], [0, math.sin(tilt), math.cos(tilt)]])
    rotation = rx @ ry
    pixels = np.empty((600, 420, 3), dtype=np.uint8)
    pixels[:] = [25, 30, 36]
    depth = np.full((600, 420), -np.inf)
    face_indices = {"north": [1, 0, 3, 2], "south": [4, 5, 6, 7], "east": [5, 1, 2, 6], "west": [0, 4, 7, 3], "up": [3, 7, 6, 2], "down": [0, 1, 5, 4]}
    faces = []
    for part in model["elements"]:
        a, b = part["from"], part["to"]
        vertices = np.array([[a[0], a[1], a[2]], [b[0], a[1], a[2]], [b[0], b[1], a[2]], [a[0], b[1], a[2]], [a[0], a[1], b[2]], [b[0], a[1], b[2]], [b[0], b[1], b[2]], [a[0], b[1], b[2]]])
        transformed = (vertices-np.array([8, 8, 8])) @ rotation.T
        for direction, inds in face_indices.items():
            points = transformed[inds]
            normal = np.cross(points[1]-points[0], points[2]-points[1])
            if normal[2] <= 0:
                continue
            rect = part["faces"][direction]["uv"]
            color = atlas_image.getpixel((int((rect[0]+rect[2])*4), int((rect[1]+rect[3])*4)))
            shade = {"north": 1, "south": .85, "up": 1.1, "down": .6, "east": .8, "west": .75}[direction]
            faces.append((points[:, 2].mean(), points, rect, tuple(min(255, int(c*shade)) for c in color), direction))
    for _, points, rect, color, direction in faces:
        # Native north UV: top-left is (+X,+Y,-Z), facing the viewer.
        if direction == "north":
            points = points[[3, 2, 1, 0]]
        polygon = np.array([(210+p[0]*32, 310-p[1]*32) for p in points])
        lo = np.maximum([0, 0], np.floor(polygon.min(axis=0)).astype(int))
        hi = np.minimum([420, 600], np.ceil(polygon.max(axis=0)).astype(int))
        if np.any(hi <= lo):
            continue
        inv = np.linalg.inv(np.column_stack((polygon[1]-polygon[0], polygon[3]-polygon[0])))
        yy, xx = np.mgrid[lo[1]:hi[1], lo[0]:hi[0]]
        samples = np.stack((xx+.5-polygon[0, 0], yy+.5-polygon[0, 1]), axis=-1) @ inv.T
        u, v = samples[..., 0], samples[..., 1]
        z = points[0, 2]+u*(points[1, 2]-points[0, 2])+v*(points[3, 2]-points[0, 2])
        old_depth = depth[lo[1]:hi[1], lo[0]:hi[0]]
        valid = (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1) & (z > old_depth)
        target = pixels[lo[1]:hi[1], lo[0]:hi[0]]
        if direction == "north":
            source = np.asarray(atlas_image.crop(tuple(round(n*8) for n in rect)))
            tx = np.clip((u*source.shape[1]).astype(int), 0, source.shape[1]-1)
            ty = np.clip((v*source.shape[0]).astype(int), 0, source.shape[0]-1)
            target[valid] = source[ty[valid], tx[valid]]
        else:
            target[valid] = color
        old_depth[valid] = z[valid]
    Image.fromarray(pixels).save(path)


report = []
for name, theme in THEMES.items():
    image = atlas(name, theme)
    model = make_model(name)
    for element in model["elements"]:
        assert all(element["from"][i] < element["to"][i] for i in range(3))
        assert all(0 <= n <= 16 for face in element["faces"].values() for n in face["uv"])
    assert all(value.startswith("projectseele:item/") for value in model["textures"].values())
    bounds = [[min(e["from"][i] for e in model["elements"]), max(e["to"][i] for e in model["elements"])] for i in range(3)]
    report.append({"item": name, "elements": len(model["elements"]), "bounds": bounds, "texture": [128, 128], "front_face": "north", "gui_rotation_y": 155, "hand_rotation_y": 165})
    preview(model, image, OUT / f"{name}_source_preview.png")
(OUT / "dimensions.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))

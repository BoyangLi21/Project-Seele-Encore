"""Maintain the park entrance, the retired upper science walkway and the R753 terminal finish."""

from dogma_recommission import AIR
from dogma_surface_command import X, Z, GROUND, cladding, interiors, elevator, skin
import numpy as np


def clear_entrance(b):
    # First floor faces west. Keep a clear view under the entrance canopy, including
    # the curve in the public approach. Cut the crowns along with their parent trunks.
    line = [(167, 369), (184, 374), (201, 380), (209, 388), (215, 395), (222, 395)]
    opening = {(x, z) for x in range(203, 225) for z in range(383, 408)}
    for (x, z), (xx, zz) in zip(line, line[1:]):
        n = max(abs(xx - x), abs(zz - z))
        for step in range(n + 1):
            a = round(x + (xx - x) * step / n)
            c = round(z + (zz - z) * step / n)
            opening.update(
                (a + i, c + j)
                for i in range(-5, 6)
                for j in range(-5, 6)
                if i * i + j * j <= 28
            )

    def wooded(s):
        return "_leaves[" in s or "_log[" in s or s.startswith("minecraft:vine[")

    crowns = set()
    for x, z in opening:
        if any("_log[" in b.get(x, y, z) for y in range(-480, -440)):
            crowns.update(
                (x + i, z + j)
                for i in range(-5, 6)
                for j in range(-5, 6)
                if i * i + j * j <= 29
            )
    count = 0
    for x, z in opening | crowns:
        for y in range(-480, -425):
            if wooded(b.get(x, y, z)):
                b.put(x, y, z, AIR)
                count += 1
    return count


def remove_east_jamb(b, previous):
    # Only the old building's east tip is inside the R753 restoration rectangle.
    count = 0
    for x in range(169, 174):
        for z in range(342, 366):
            for y in range(-470, -405):
                old = previous.get(x, y, z)
                now = b.get(x, y, z)
                if now != old and old is not None:
                    b.put(x, y, z, old)
                    count += 1
    return count


def remove_upper_walk(b):
    # Both decks cross U1/U2. The live lower passage dips under the rails around Z475.
    # Remove the upper flight from landing to landing. Shared roofs stay at Y=-462.
    for z in range(403, 547):
        for x in range(192, 201):
            top = -451
            bottom = -461 if 409 <= z <= 540 else -466
            for y in range(bottom, top + 1):
                state = b.get(x, y, z)
                if state != AIR and not any(
                    k in state for k in ("_leaves", "_log", "grass", "dirt")
                ):
                    b.put(x, y, z, AIR)
            if z < 409:
                b.put(x, -467, z, "smooth_stone")
            if z >= 541:
                b.put(x, -467, z, "smooth_stone")
    # This short enclosed stair returns exclusively from the lower corridor to the
    # retired deck. Its east wall is freestanding, two blocks west of the next building.
    for x in range(201, 212):
        for z in range(525, 543):
            for y in range(-468, -451):
                s = b.get(x, y, z)
                if s.startswith(
                    (
                        "projectseele:nerv_",
                        "projectseele:clear_glass",
                        "minecraft:smooth_quartz_stairs",
                        "minecraft:sea_lantern",
                    )
                ):
                    b.put(x, y, z, AIR)
    for z in range(525, 530):
        for height in range(1, 5):
            b.put(
                200,
                -467 + height,
                z,
                "projectseele:clear_glass"
                if height in (2, 3)
                else "projectseele:nerv_wall_panel",
            )


def repaint_existing(b, raster):
    # Overlay the original builder's actual interior, shaft and shaft cladding,
    # so a panel shared by the optical housing and a working room keeps its role.
    class Layout:
        def __init__(self):
            self.world = b.world
            self.states = {}
            self.tags = {}

        def get(self, *p):
            return self.states.get(p, AIR)

        def put(self, x, y, z, s):
            self.states[x, y, z] = s if ":" in s else "minecraft:" + s

        def box(self, x, y, z, xx, yy, zz, s):
            for i in range(x, xx + 1):
                for j in range(y, yy + 1):
                    for k in range(z, zz + 1):
                        self.put(i, j, k, s)

        def sign(self, x, y, z, *args):
            self.put(x, y, z, "minecraft:warped_wall_sign")

        def output(self, *args):
            pass

    after = Layout()
    interiors(after)
    elevator(after)
    skin(after)
    allowed = {
        "minecraft:" + key
        for key in (
            "smooth_sandstone",
            "cut_sandstone",
            "white_terracotta",
            "light_gray_terracotta",
            "polished_andesite",
            "polished_deepslate",
            "cut_copper",
            "ochre_froglight[axis=y]",
        )
    }
    targets = {
        "minecraft:smooth_quartz",
        "minecraft:white_concrete",
        "minecraft:sea_lantern",
        "minecraft:pearlescent_froglight[axis=y]",
    }
    for i, j, h in zip(*np.nonzero(raster["m"])):
        i, j, h = map(int, (i, j, h))
        p = (X + i, GROUND + h, Z + j)
        after.states.setdefault(p, "minecraft:" + cladding(i, j, h))
    for p, s in after.states.items():
        if s in targets and b.get(*p) in allowed:
            b.put(*p, s)

"""Recess the three native MTR berth edges for the 6.1 m beam of the lake ship."""

from dogma_recommission import AIR
from renew_ashi_collectors import WATER


def commission(b):
    ports = [(-288, 1086, 0, -2), (377, 2303, 2, 1), (491, 2029, 2, 0)]
    results = []
    for cx, cz, dx, dz in ports:
        marks = {}
        for x in range(cx - 31, cx + 32):
            for z in range(cz - 30, cz + 31):
                state = b.get(x, 100, z)
                if state.startswith("mtr:platform_slab"):
                    marks[x, z] = state
        assert len(marks) in (28, 29, 37), (cx, cz, len(marks))
        normal_length = (dx * dx + dz * dz) ** 0.5
        # The diagonal quay follows a 45° track. Its landward normal is (+1,+1).
        nx, nz = (
            (1 / 2**0.5, 1 / 2**0.5)
            if dx and dz
            else (dx / normal_length, dz / normal_length)
        )
        for x in range(cx - 33, cx + 34):
            for z in range(cz - 29, cz + 30):
                if (x - cx) * nx + (z - cz) * nz > 3.5:
                    continue
                for y in (100, 99, 98, 97, 96):
                    state = b.get(x, y, z)
                    if state.startswith(
                        (
                            "mtr:platform_slab",
                            "minecraft:spruce_planks",
                            "minecraft:spruce_log",
                        )
                    ):
                        b.put(x, y, z, AIR if y >= 100 else WATER)
        for (x, z), state in marks.items():
            X, Z = x + dx, z + dz
            b.put(X, 100, Z, state)
            if "spruce_log" in b.reader.get(x, 99, z):
                b.put(X, 99, Z, "spruce_log[axis=y]")
        # The original fence at Tōgendai had two openings near the ends of the old
        # consist. Open its middle directly opposite the doors of the single ship.
        if cx == -288:
            for x in range(-299, -292):
                if "fence" in b.get(x, 101, 1081):
                    b.put(x, 101, 1081, AIR)
        results.append(dict(berth=[cx, cz], native_platform_slabs=len(marks)))
    # The native bogie sweep cuts toward the west end of this diagonal berth.
    # Keep the long platform edge on the dry side of that arc while preserving its slabs.
    for x in range(361, 398):
        inner = 2685
        if 362 <= x <= 381:
            inner += min(6, x - 362, 381 - x)
        for z in range(2287, 2327):
            if x + z > inner:
                continue
            for y in (99, 100):
                s = b.get(x, y, z)
                if s.startswith("mtr:platform_slab"):
                    b.put(x, y, inner + 1 - x, s)
                if s.startswith(
                    (
                        "mtr:platform_slab",
                        "minecraft:spruce_planks",
                        "minecraft:spruce_log",
                        "minecraft:stone_bricks",
                    )
                ):
                    b.put(x, y, z, WATER if y == 99 else AIR)
    # Aft quarter of the hull sweeps the end of the Motohakone wharf as the bow turns away.
    for z in (2042, 2043):
        s = b.get(495, 100, z)
        if s.startswith("mtr:platform_slab"):
            b.put(495, 100, z, AIR)
            b.put(496, 100, z, s)
    return results

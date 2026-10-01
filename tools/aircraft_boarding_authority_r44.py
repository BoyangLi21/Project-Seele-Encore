"""Finite boarding-device/door ownership shared by map repair producers.

A retracted stair or an open vehicle interface must not become a static
unguarded-drop repair. Authority comes from the saved native gate recipe,
never from an airport-sized exclusion rectangle or from empty voxels.
"""
from pathlib import Path
import json
import math


class AircraftBoardingAuthority:
    def __init__(self, world):
        path = Path(world) / "regional_boarding_gates.json"
        self.path = path
        self.components = []
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf8"))
        if data.get("version") != 1:
            raise ValueError(f"Unknown boarding authority version: {path}")
        for gate in data["gates"]:
            owned = {tuple(row[:3]) for row in gate["stairs"]}
            platforms = [row[:3] for row in gate["stairs"] if row[3].startswith("mtr:platform[")]
            if not platforms or gate["direction"] not in ("north", "south", "east", "west"):
                raise ValueError(f"Incomplete native aircraft port: {gate['id']}")
            lo = [min(p[i] for p in platforms) for i in range(3)]
            hi = [max(p[i] for p in platforms) + 1 for i in range(3)]
            lo[1] += 1
            hi[1] += 2
            axis = 2 if gate["direction"] in ("north", "south") else 0
            sign = -1 if gate["direction"] in ("north", "west") else 1
            # Entire three-wide apron mouth, plus native doorway crossing.
            # The dynamic recipe still owns/supports the staircase itself.
            lo[axis] -= 2 if sign < 0 else 1
            hi[axis] += 2 if sign > 0 else 1
            self.components.append(dict(id=gate["id"], owned=owned, lo=tuple(lo), hi=tuple(hi), gate=gate))

    def owner(self, point):
        point = tuple(map(math.floor, point))
        for item in self.components:
            if point in item["owned"] or all(item["lo"][i] <= point[i] < item["hi"][i] for i in range(3)):
                return item["id"]
        return None

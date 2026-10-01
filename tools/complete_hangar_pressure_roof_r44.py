"""Exact finishing remainder after applied v3, without altering any shape.

The complete existing transfer roof was inside v3's deliberately oversized
body keep mask. This explicit same-shape-only finish revision completes it;
all actual native lift components are excluded, including captured floors.
"""
from pathlib import Path
from plan_tv_hangar_envelope_r44 import plan, WORLD

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44/tv_hangar_pressure_roof_finish_v2"

if __name__ == "__main__":
    plan(WORLD, OUT, finish_inside_geometry_keepouts=True,
         restore_applied_strip_lights=True)

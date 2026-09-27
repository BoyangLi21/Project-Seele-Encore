"""Update reader-relative arrows using the final R42 geometry and navigation."""
from pathlib import Path
import argparse
import refresh_wayfinding_r40 as previous
from measure_world_r40 import MeasuredWorld

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R42_REVIEW'


def main(apply=False):
    if apply:
        from release_combat_r36 import guard
        guard()
    previous.WORLD=WORLD
    previous.OUT=ROOT/'artifacts/rebuild_r42/signage'
    # MeasuredWorld's constructor default belongs to its original module;
    # changing the caller's WORLD global alone does not change that default.
    previous.MeasuredWorld=lambda:MeasuredWorld(WORLD)
    previous.main(apply)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)

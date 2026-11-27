"""Commission the surveyed facilities in an offline copy of the GeoFront save."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "map_buildings"))

from dogma_arrivals import arrivals
from dogma_city_art import lake_mirrors, street_fronts
from dogma_graveyard import graveyard
from dogma_recommission import Works, apartment, passages, tanks
from dogma_subterminal import terminal


def build(
    world,
    reference,
    civic_region,
    model,
    out,
    authority=None,
    street_survey=None,
    emergency=None,
):
    if bool(authority) != bool(street_survey):
        raise ValueError(
            "Supply the city authority save and its street survey together"
        )
    if emergency and not authority:
        raise ValueError(
            "Arrival checks need the authority save and an open-gate survey"
        )
    works = Works(world, reference, out)
    passages(works)
    tanks(works)
    apartment(works)
    graveyard(works, model)
    terminal(works, civic_region)
    if authority:
        street_fronts(works, authority, street_survey)
        lake_mirrors(works)
    works.write()
    if emergency:
        arrivals(world, authority, emergency)
    print(works.reports, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("world", "reference", "civic_region", "model", "out"):
        parser.add_argument("--" + arg, type=Path, required=True)
    parser.add_argument(
        "--authority", type=Path, help="Full baseline save for unchanged city districts"
    )
    parser.add_argument(
        "--street-survey", type=Path, help="Surveyed static facade locations (TSV.gz)"
    )
    parser.add_argument(
        "--emergency", type=Path, help="Save with the EVA passages fully released"
    )
    build(**vars(parser.parse_args()))

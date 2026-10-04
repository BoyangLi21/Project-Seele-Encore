"""Prevent dedicated R44 school producers from becoming R45 maintenance."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RECEIPT=ROOT/'artifacts/rebuild_r45/component_installations/school_campus_v2/installation.json'


def refuse_retired_school_producer(historical=False):
    if RECEIPT.exists() and not historical:
        raise RuntimeError('The complete R45 school/pool is already installed. This R44 school producer is retired for current-world maintenance. Use author_school_campus_r45.py --repair-current (or prepare_school_hakone_lifecycle_r45.py), which measures the current world and emits only remaining exact deltas. For explicitly historical R44 evidence only, pass --historical-r44; that output must never be replayed into R45.')

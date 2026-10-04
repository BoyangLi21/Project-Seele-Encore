"""Root-approved whole427 bridge extension; all original safety rules remain.

Adds one classified exact component and one static metadata filename. Does
not copy/alter the Root-owned model or admit progress/SavedData/region copies.
Original v1-v3 implementation/catalog epochs are left byte-identical.
"""
from pathlib import Path
import compose_r45_candidate as base

base.ALLOWED_IDS=base.ALLOWED_IDS|{'bridge427','tv_encounter_inputs_v17','coordination_inputs_v17'}
base.ALLOWED_DERIVED_TARGETS=base.ALLOWED_DERIVED_TARGETS|{'r44_tv_personnel_platforms.json','tv_encounter_sites_r45.json','city_coordination_r44.json','nerv_staff_r15.json'}
base.DEFAULT_CATALOG=Path('artifacts/rebuild_r45/integration_sol_followup/offline_composer_v4/catalog.json')

if __name__=='__main__':raise SystemExit(base.main())

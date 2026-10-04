"""Prevent historical parcel commissioning from resurrecting installed cities.

Metadata/receipt read only. Current measured repairs use dedicated exact-delta
authors; this guard creates no building permission or saved-world writes.
"""
from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[1]
CATALOGUE=ROOT/'artifacts/rebuild_r44/city_expansion/manual_review_closeout_20261001_v1/installed_city_landform_delivery_manifest.json'


def installed_ids(catalogue=CATALOGUE):
    path=Path(catalogue)
    if not path.exists():return {}
    data=json.loads(path.read_text('utf8'));owners={}
    for district in data['districts']:
        receipt=Path(district['receipt'])
        if not receipt.is_file() or hashlib.sha256(receipt.read_bytes()).hexdigest()!=district['receipt_sha256']:
            raise RuntimeError('Installed city receipt is missing or changed; historical commissioning refused: '+str(receipt))
        if not json.loads(receipt.read_text('utf8')).get('verified'):
            raise RuntimeError('Installed city receipt is not verified: '+str(receipt))
        for building in district['buildings']:
            owners[building['id']]=dict(district=district['installed_latest'],receipt=str(receipt),bounds=building['bounds_xz'])
    return owners


def refuse_installed_city_commissioning(design,historical=False,*,catalogue=CATALOGUE):
    owners=installed_ids(catalogue)
    # TV-school has its own existing lifecycle guard and source owner.
    # This helper governs the installed city/residential commissioning paths.
    overlaps=[b['id'] for b in design.get('buildings',[]) if b.get('kind') not in ('tv_school','tv_gym')
              and not b['id'].startswith('r44/tv_school/') and b['id'] in owners]
    if not overlaps:return []
    if not historical:
        raise RuntimeError('Historical city commissioning is retired for installed IDs '+', '.join(overlaps)+
            '. Read the current R45 world and prepare an exact whole-component delta; do not replay an old baseline, rooms, facade or public grade. '
            'Use --historical-r44 only to retain a non-executable evidence candidate.')
    design['historical_evidence_only']=True
    design['installed_ids_not_replayable']=overlaps
    design['historical_source_guard_catalogue']=str(catalogue)
    design['construction_or_current_world_promotion_allowed']=False
    return overlaps

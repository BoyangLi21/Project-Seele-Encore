"""Record the user's staged delivery boundary without asserting readiness."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    base = args.base.resolve()
    scope = dict(
        id='scope124', user_requested=True,
        included=['1: nine launch channels and original well/Hakone outlets',
                  '2: hangar preparation, service pits, launch and return',
                  '4: airlift shaft, gates, dispatch, transport and recovery',
                  'all underground corridors at their full usable width',
                  'every actual pyramid floor ring and both main lifts; office lift retained',
                  'complete obsolete corridors, intersections, signs and old hangar retirement',
                  'direct descent/ascent at the sole underground HQ station; other GeoFront rail/stations on its surface',
                  'fast actual surface/underground transport on shortest clear routes',
                  'commands and legacy code replacement necessary for 1/2/4',
                  'server and client containing the same current map'],
        deferred=['3: new Yashima cannon, magazine and combat-site work',
                  '5: additional MTR piers, airport F07 and unrelated old defects',
                  '6: unrelated global navigation and generator cleanup'],
        completed_migrations='Retain installed migration for manual inspection; no rollback implied',
        acceptance='Current launch/return/airlift, full-width underground, every pyramid floor and two lifts, retirement and direct fast transit checks; actual scene review and delivered copy readback')
    outstanding = [
        'nine actual ascent bores, steel, seats and current outlet/gate construction',
        'necessary original-bay controls and typed native mechanical assembly',
        'current airlift directory and end-to-end core124 runtime',
        'complete pyramid, underground and obsolete component work',
        'direct HQ surface railway and very fast actual transport',
        'build, native core124 checks and migration scene review',
        'server/client packaging, actual delivery readback, commit and push']
    for path in (root/'.Codex/map_complete_20261013/CURRENT_CONTRACT.json', base/'ROOT_SPATIAL_PLAN.json'):
        doc = json.loads(path.read_text('utf8'))
        doc['delivery_scope'] = scope
        doc['outstanding'] = outstanding
        if 'status' in doc:
            doc['status'] = 'ACTIVE_SCOPE124_MIGRATION_ACCEPTANCE_DELIVERY'
            for item in ('remote_airshaft_and_actual_machine_bearings',
                         'HQ_66_native_rails_and_40_preserved_vehicle_states',
                         'three_original_lower_assembly_dry_service_pits'):
                if item not in doc['completed_core_stages']:
                    doc['completed_core_stages'].append(item)
            doc['latest_overrides'].append('USER: include complete underground/pyramid/retirement/direct HQ and fast transit in this delivery; only unrelated expansion remains deferred')
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2)+'\n', 'utf8')
    print(json.dumps(scope, ensure_ascii=False))


if __name__ == '__main__':
    main()

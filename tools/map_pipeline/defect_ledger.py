"""Build one evidence-linked ledger without treating unreviewed material as defects.

Construction work, confirmed findings, uncertain observations and coverage are
separate denominators. No missing observation automatically closes a defect.
All inputs are immutable reports; this command never opens or edits a world.
"""
import argparse
import collections
import json
from pathlib import Path

import numpy as np
from map_pipeline.delivery_check import read, write


def build(args):
    state = read(args.continuation)
    work_path = Path(state['station_construction_worklist'])
    work = read(work_path)
    if work['latest_installed_batch'] != state['latest_installed_batch']:
        raise ValueError('Station worklist is not at the installed authority')
    audit = read(args.road_audit/'audit.json')
    if Path(audit['authority']) != Path(state['planning_authority']):
        raise ValueError('Road baseline does not describe the current authority')
    survey = read(args.observed_roads/'survey.json')
    if Path(survey['world']) != Path(audit['world']):
        raise ValueError('Observed and declared roads came from different worlds')
    tasks = []
    for row in work['geographic_stations']:
        complete = all(row.get(k, False) for k in ('physical_structure_installed',
                       'native_registration_installed', 'passenger_access_geometry_verified'))
        tasks.append(dict(id='new-station/'+row['name'], category='new_station_structure_and_access',
            stage=2, region=row['name'], position_xz=row['track_centre_xz'],
            state='installed_static' if complete else 'pending',
            evidence=row.get('delivery', str(work_path)), live_service_complete=False))
    for row in work['existing_stations']:
        tasks.append(dict(id='retained-station/'+row['native_id'], category='retained_station_final_acceptance',
            stage=2, region=row['name'], bounds=row['bounds'],
            state='complete' if row.get('station_complete', False) else 'pending_final_review',
            evidence=str(work_path), partial_static_evidence_retained=True))
    water_path = Path(work['stage_three_water_carryover'])
    water = read(water_path)
    for row in water['components']:
        ref = row['reference_component']
        tasks.append(dict(id='water-reference/'+str(ref['id']), category='water_component_interface',
            stage=3, region='expanded-geography', bounds_xz=ref['bounds'],
            state='pending', evidence=str(water_path), unit='cached_reference_component',
            prior_local_water_releases_preserved=row['previously_installed_local_water_not_overwritten']))
    findings = []
    with np.load(args.road_audit/'actual-routes.npz') as source:
        x, z, g = source['x'], source['z'], source['grade2']
        full, floor, body = source['full'], source['floor_ok'], source['body_ok']
        for category, selected, status in (
            ('declared_floor_or_grade', full & ~floor, 'confirmed_open'),
            ('declared_clearance', full & ~body, 'needs_review'),
            ('declared_column_not_full', ~full, 'unverified')):
            for i in np.flatnonzero(selected):
                px, pz, grade = int(x[i]), int(z[i]), int(g[i])
                findings.append(dict(id=f'{category}/{px}/{grade}/{pz}', category=category,
                    stage=4, state=status, unit='declared_public_column',
                    position=[px, grade/2+1, pz], evidence=str(args.road_audit/'actual-routes.npz'),
                    note='Measured obstruction at a declared layer; check current layered route ownership before calling it a physical defect.'
                    if category=='declared_clearance' else ''))
    for row in read(args.road_audit/'destinations.json'):
        if row['accessible_component'] is None:
            findings.append(dict(id='catalog-approach/'+str(row['id']), category='catalog_approach_mismatch',
                state='needs_review', stage=4, position=row['approach'],
                evidence=str(args.road_audit/'destinations.json'),
                note='May be an outdated anchor or a layered entrance; no physical failure inferred.'))
    if args.confirmed_findings:
        for row in read(args.confirmed_findings):
            if row['state']!='confirmed_open' or not Path(row['evidence']).is_file():
                raise ValueError('A confirmed manual finding lacks its evidence')
            findings.append(row)
    closures = []
    for row in read(args.closures):
        delivery = read(row['delivery'])
        receipt = read(delivery['installation'])
        if not delivery.get('world_written') or receipt.get('status') != 'installed' or not receipt.get('changed_section_readback'):
            raise ValueError('Closure lacks installed readback: '+row['id'])
        closures.append(dict(**row, state='closed_static', stage=2,
                             installed_batch=delivery['batch'], live_acceptance=False))
    all_ids = [r['id'] for r in tasks+findings+closures]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError('Duplicate ledger IDs')
    diagnostics = [q for row in survey['regions'] for q in row['diagnostics']]
    corrupt = [q for q in diagnostics if q.get('kind') != 'empty_region']
    scope = dict(observed_saved_full_chunks=survey['full_chunks'],
        material_observation_snapshot_batch=args.observed_snapshot_batch,
        declared_route_snapshot_batch=state['latest_installed_batch'],
        material_inventory_is_current=args.observed_snapshot_batch==state['latest_installed_batch'],
        observed_material_layers=survey['road_material_layers'],
        unclassified_material_components=len(survey['components']),
        material_component_evidence=str(args.observed_roads/'survey.json'),
        observed_y_range=survey['bounds_y'], chunk_statuses=survey['chunk_statuses'],
        empty_region_placeholders=sum(q.get('kind')=='empty_region' for q in diagnostics),
        decoding_failures=corrupt, declared_public_columns=audit['declared_columns'],
        global_material_classification_complete=False, global_vehicle_sweep_complete=False,
        global_material_pattern_detection_complete=False, global_tunnel_endpoints_complete=False,
        global_geometry_deviation_budget_complete=False, global_floating_and_conflicts_complete=False,
        rendered_or_user_acceptance_complete=False)
    summary = dict(confirmed_open_by_category=dict(collections.Counter(r['category'] for r in findings if r['state']=='confirmed_open')),
        uncertain_by_category=dict(collections.Counter(r['category'] for r in findings if r['state']!='confirmed_open')),
        imported_closed_static_defect_groups=len(closures),
        work_by_category={key:dict(collections.Counter(r['state'] for r in tasks if r['category']==key))
                          for key in sorted({r['category'] for r in tasks})},
        whole_map_defect_total_known=False, whole_map_completion_percentage=None)
    args.out.mkdir(parents=True, exist_ok=False)
    write(args.out/'ledger.json', dict(schema_version=1, installed_batch=state['latest_installed_batch'],
        authority=state['planning_authority'], worklist=str(work_path),
        summary=summary, coverage=scope, construction_work_items=tasks,
        findings=findings, closed_static_defect_groups=closures, world_written=False,
        scope_note='Known findings only; construction tasks and unclassified materials are not added to a fabricated global defect count.'))
    write(args.out/'summary.json', dict(installed_batch=state['latest_installed_batch'], **summary, coverage=scope))
    print('LEDGER: '+json.dumps(summary, ensure_ascii=False, separators=(',', ':')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    for key in ('continuation', 'road-audit', 'observed-roads', 'closures', 'out'):
        parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--observed-snapshot-batch',type=int,required=True)
    parser.add_argument('--confirmed-findings',type=Path)
    build(parser.parse_args())

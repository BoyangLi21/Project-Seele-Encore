"""Assemble the independently validated mechanical and real-wall meshes.

No world/source-resource installation. Root installs this exact private result
with its paired pad resource and native-checks that same frozen epoch.
"""
from pathlib import Path
import argparse,hashlib,json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rebuild_r44/hangar_machinery'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=BASE/'tv_cage_whole_candidate_v3');args=parser.parse_args()
    cage_path=BASE/'tv_shoulder_shells_v2/tv_shoulder_shells_r44.json';wall_path=BASE/'tv_wet_bay_lining_v1/tv_wet_bay_lining_r44.json'
    pad=BASE/'shoulder_contact_v3/hangar_shoulder_contacts_r44.json'
    physical=json.loads((cage_path.parent/'complete_physical_interfaces.json').read_text('utf8'))
    assert physical['resource_sha256']==hashlib.sha256(cage_path.read_bytes()).hexdigest()
    assert not any(physical[k] for k in ('all_states_crew_hits','capsule_full121_hits','wet_envelope_hits','original_02_arrival_body_hits','actual_world_intersections'))
    assert not any(r['conflicts'] for r in physical['complete_carrier_fixed_part_exact_checks'])
    wall_current=json.loads((wall_path.parent/'current_cage_crew_contract.json').read_text('utf8'))
    assert not any(wall_current[k] for k in ('cage_vs_lining_swept_hits','full_two_lane_crew_hits','current_wall_dependency_stale'))
    wall_world=json.loads((wall_path.parent/'actual_world_and_full_carrier_contract.json').read_text('utf8'))
    assert wall_world['resource_sha256']==hashlib.sha256(wall_path.read_bytes()).hexdigest()
    assert not wall_world['actual_world_hits'] and not wall_world['whole_carrier_allrise_bounds_hits']
    c=json.loads(cage_path.read_text('utf8'));w=json.loads(wall_path.read_text('utf8'))
    for k in ('parts','collision_parts'):
        assert not set(c[k])&set(w[k]);c[k].update(w[k])
    c['components'].extend(w['components']);c['whole_wet_pressure_lining_source_sha256']=hashlib.sha256(wall_path.read_bytes()).hexdigest()
    c['integration']['preserve_original_pad_resource']=False
    c['integration']['requires_contact_resource_sha256']=hashlib.sha256(pad.read_bytes()).hexdigest()
    c['integration']['contact_candidate_source']='hangar_machinery/shoulder_contact_v3/hangar_shoulder_contacts_r44.json'
    args.out.mkdir(parents=True,exist_ok=True);p=args.out/'tv_shoulder_shells_r44.json'
    p.write_text(json.dumps(c,separators=(',',':')),encoding='utf8')
    report={'cage_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'pad_sha256':hashlib.sha256(pad.read_bytes()).hexdigest(),
        'cage_parts':len(c['parts']),'cage_components':len(c['components']),'whole_triangles':sum(len(v)//18 for v in c['parts'].values()),
        'collision_boxes':sum(len(v) for v in c['collision_parts'].values()),'source_cage_sha256':hashlib.sha256(cage_path.read_bytes()).hexdigest(),
        'source_wall_sha256':hashlib.sha256(wall_path.read_bytes()).hexdigest(),'checks':['tv_shoulder_shells_v2/complete_physical_interfaces.json',
        'tv_wet_bay_lining_v1/current_cage_crew_contract.json','tv_shoulder_shells_v2/new_pad_vs_actual_fullbody.json'],
        'source_phase':'Candidate only; geometry+collider must be installed together after root source/space review',
        'native_passed':False,'visual_passed':False,'world_write_performed':False}
    (args.out/'installation_contract.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))


if __name__=='__main__':main()

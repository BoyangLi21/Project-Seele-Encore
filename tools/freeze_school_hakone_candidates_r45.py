"""Freeze only agent artifacts and source epochs; never opens a world for writing."""
from pathlib import Path
import argparse
import json
import shutil

from school_hakone_patch_r45 import ROOT,ART,sha


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--school',default='school_v5')
    p.add_argument('--manifest',default='delivery_manifest_v2.json')
    p.add_argument('--source-name',default='source_epoch_v2')
    a=p.parse_args()
    assert all('/' not in s and '\\' not in s for s in [a.school,a.manifest,a.source_name])
    manifest=ART/a.manifest
    assert not manifest.exists(),'Final delivery manifest already exists; do not silently replace it'
    source_dir=ART/a.source_name
    assert not source_dir.exists()
    source_dir.mkdir()
    files=[ROOT/'tools'/n for n in ['author_school_campus_r45.py','author_hakone_station_r45.py','school_hakone_patch_r45.py','audit_school_hakone_r45.py','survey_school_hakone_r45.py','freeze_school_hakone_candidates_r45.py','query_blocks.py','measure_world_r40.py','regional_voxels.py','audit_facility_transit_r44.py','information_fixture_guard_r44.py']]
    files.append(ROOT/'docs/SCHOOL_HAKONE_R45.md')
    sources=[]
    for i,p in enumerate(files):
        dest=source_dir/(str(i).zfill(2)+'_'+p.name)
        shutil.copy2(p,dest)
        sources.append(dict(original_path=str(p.resolve()),frozen_path=str(dest.resolve()),sha256=sha(dest)))
    candidates=[]
    for name in [a.school,'hakone_v5']:
        folder=ART/name
        contract=json.loads((folder/'contract.json').read_text('utf8'))
        audit=json.loads((folder/'static_audit.json').read_text('utf8'))
        assert not audit['precondition_errors'] and not audit['changed_original_BE']
        assert not any(c['status']=='STATIC_OBSTRUCTION' for c in audit['flat_cases'])
        assert not contract.get('unresolved_service_rooms')
        frozen={p.relative_to(folder).as_posix():dict(path=str(p.resolve()),sha256=sha(p)) for p in folder.rglob('*') if p.is_file()}
        candidates.append(dict(name=name,path=str(folder.resolve()),files=frozen,exact_cells=contract['exact_cells'],preserved_full_BE=contract['preserved_original_block_entities'],new_full_BE=contract['new_block_entities'],rooms=contract['room_count'],floor_regions=len(audit['full_floor_regions']),ports=len(json.loads((folder/'ports.json').read_text('utf8'))),camera_views=len(json.loads((folder/'camera_itinerary.json').read_text('utf8'))),static_path_status=audit['flat_case_status'],native_shape_unknowns=audit['unknown_native_shapes'],world_written=False,native_passed=False,visual_passed=False,release_ready=False))
    result=dict(title='R45 school/pool and entire existing Hakone-station static candidates',final_candidate_names=[a.school,'hakone_v5'],candidates=candidates,source_epochs=sources,world_writer='root only',review_world=str((ROOT/'run/saves/SEELE_FIELD_R45_REVIEW').resolve()),unchanged_traffic_files=True,model_animation_shared_source_edits=False,no_minecraft_or_build_started=True,world_written=False,delivery_doc=str((ROOT/'docs/SCHOOL_HAKONE_R45.md').resolve()),history='Earlier epochs remain as construction/negative evidence and are excluded from installation. Do not replay v22 or earlier full R44 station/city sources.',required_root_steps=['Re-read full before state and NBT under exclusive world lock','Apply only precise positive masks through full-NBT Painter; preserve original BE and traffic identities','Merge five Hakone path replacements by matching exact old paths, not a catalogue wholesale copy','Capture newly requested native states including actual position-dependent fixture parts','Run real room/door/gate/swim/platform/transfer/boarding and final installed-copy readback','Inspect all actual shader views; user visual approval remains unverified'])
    manifest.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('Frozen final candidates',[(c['name'],c['exact_cells'],c['new_full_BE'],c['rooms'],c['ports']) for c in candidates],flush=True)


if __name__=='__main__':main()

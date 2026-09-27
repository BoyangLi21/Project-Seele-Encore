"""Assemble traceable native evidence; never relabel inherited paths as new tests."""
from pathlib import Path
import datetime,hashlib,json

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r42'
def read(p):return json.loads(p.read_text('utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    visual=read(ART/'visual_review.json');assert visual['reviewed'] and not visual['unresolved_regressions']
    labels=[f'locomotion_{i}_clear' for i in range(5)]+['rifle_1_clear','basic_1_clear','duel_1_clear','awakening_1_shader']
    motion=[]
    for label in labels:
        pointer=read(ART/'native'/f'latest_{label}.json');p=Path(pointer['result']);report=read(p)
        assert pointer['passed'] and report['passed'] and not report['error'],label
        motion.append(dict(label=label,result=str(p),sha256=sha(p),media=pointer['media'],cases=report['cases']))
    paths=read(ART/'affected_native_results.json');assert len(paths)==60 and all(r['status']=='pass' for r in paths)
    lifts=read(ART/'lift_trips_result.json');assert not lifts['error'] and not lifts['damage'] and len(lifts['trips'])==3 and all(t['passed'] for t in lifts['trips'])
    clearance=read(ART/'clearance_result.json');assert len(clearance)==2 and all(r['denied_without_card'] and r['admitted_with_card'] for r in clearance)
    rooms=read(ART/'navigation/room_goal_reachability.json');assert len(rooms)==50 and all(r['connected_to_all_goals'] for r in rooms)
    cameras={}
    for group,count in [('interiors_shader',12),('interiors_clear',12),('stations_shader',26),('entrances_shader',8)]:
        folder=ART/'photos'/f'verified_{group}';rows=read(folder/'positions.json');assert len(rows)==count
        records=[]
        for row in rows:
            assert row['position_error_metres']<.1 and row['dimension']=='projectseele:geofront'
            path=folder/row['file'];digest=sha(path)
            if 'sha256' in row:assert row['sha256']==digest
            records.append(dict(file=str(path),sha256=digest))
        cameras[group]=records
    runtime={}
    for path in [ART/'motion/eva_body_r42.json',ART/'first_battle/first_battle_r42.json']+[ART/'motion'/f'eva_gameplay_r42_{i}.json' for i in range(5)]:
        # These candidates were not reauthored after the native runs listed above.
        if path.name.startswith('eva_gameplay'):
            rig=int(path.stem.rsplit('_',1)[1]);proof=Path(read(ART/'native'/f'latest_locomotion_{rig}_clear.json')['result'])
        else:proof=Path(read(ART/'native/latest_awakening_1_shader.json')['result'])
        assert path.stat().st_mtime<=proof.stat().st_mtime,('Untested newer candidate',path)
        runtime[path.name]=dict(path=str(path),sha256=sha(path))
    baseline=read(ROOT/'artifacts/facility_r31/baseline.json')
    for name,digest in baseline['original_user_files'].items():assert sha(ROOT/name)==digest,('Owner source changed',name)
    result=dict(passed=True,created=datetime.datetime.now().astimezone().isoformat(),revision=42,protocol=45,
                runtime_inputs=runtime,motion=motion,spatial_native=60,passages=read(ART/'passage_provenance.json'),
                lift_trips=lifts,access_clearance=clearance,navigation=read(ART/'navigation/navigation_manifest.json'),
                rooms_connected=50,photos=cameras,visual_review=visual,
                scope='Current native and visually reviewed R42 candidate; aesthetic judgment remains with the user; inherited path results are labelled separately.')
    (ART/'native_acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('Recorded native/visual evidence and',len(runtime),'candidate hashes',flush=True)


if __name__=='__main__':main()

"""Read-only finite preapply epoch: complete before states, BEs and local entities."""
from pathlib import Path
import argparse,hashlib,json,time,nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,dimension_dir
from inspect_map_assets import region_chunks

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r44/hangar_machinery';WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main(out,model_revision='tv_personnel_supports_v5_draft9',metadata_revision='personnel_platforms_v5_boundaries_v2'):
    out=Path(out)
    if out.exists():raise ValueError('Fresh epoch required')
    ops_path=BASE/metadata_revision/'operations.json';inverse_path=ops_path.with_name('inverse.json')
    ops=json.loads(ops_path.read_text());inverse=json.loads(inverse_path.read_text());positions={tuple(r['position']) for r in ops}
    if len(positions)!=427:raise ValueError('Expected427 unique cell owners')
    inv={tuple(r['position']):r for r in inverse}
    for r in ops:
        i=inv[tuple(r['position'])]
        if i['before']!=r['after'] or i['after']!=r['before']:raise ValueError('Inverse mismatch')
    lo=(-40,-448,-274);hi=(110,-348,-210);dim=dimension_dir(WORLD,'projectseele:geofront')
    files=list((dim/'region').glob('r.*.*.mca'))+list((dim/'entities').glob('r.*.*.mca'))
    # Narrow chunks belong to at mostfour region containers; hash only those.
    regionids={(x//512,z//512) for x in (lo[0],hi[0]) for z in (lo[2],hi[2])}
    files=[p for p in files if tuple(map(int,p.stem.split('.')[1:])) in regionids]
    identityfiles=[p for folder in (WORLD/'data',dim/'data') for p in folder.glob('projectseele*.dat')]
    start={str(p):sha(p) for p in files+identityfiles}
    w=MeasuredWorld(WORLD);w.box(lo,hi);w.load();states=[];mismatches=[]
    bes=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi));betouched=[]
    for row in ops:
        q=tuple(row['position']);before=w.block(q);tag=bes.get(q)
        states.append(row|{'actual_before':before,'before_be_snbt':tag.snbt() if tag is not None else None})
        if before!=row['before']:mismatches.append({'position':q,'expected':row['before'],'actual':before})
        if tag is not None:betouched.append(q)
    berows=[{'position':q,'state':w.block(q),'snbt':t.snbt()} for q,t in sorted(bes.items())]
    entities=[]
    for p in files:
        if p.parent.name!='entities':continue
        for cx,cz,chunk in region_chunks(p,(lo[0]//16,hi[0]//16,lo[2]//16,hi[2]//16)):
            for e in chunk.get('Entities',chunk.get('entities',[])):
                pos=list(map(float,e.get('Pos',[])))
                if len(pos)!=3 or not all(lo[i]-64<=pos[i]<=hi[i]+64 for i in range(3)):continue
                entities.append({'chunk':[cx,cz],'id':str(e.get('id','')),'uuid_ints':list(map(int,e.get('UUID',[]))),'position':pos,'snbt':e.snbt()})
    identityrecords=[{'path':str(p),'sha256':sha(p),'full_snbt':nbtlib.load(p).snbt()} for p in identityfiles]
    finish={str(p):sha(p) for p in files+identityfiles};out.mkdir(parents=True)
    for name,value in [('exact_before_cells_and_BEs.json',states),('complete_local_BEs.json',berows),('complete_local_entities.json',entities)]:
        (out/name).write_text(json.dumps(value,indent=2),'utf8')
    (out/'complete_identity_saveddata.json').write_text(json.dumps(identityrecords,indent=2),'utf8')
    deps=[ops_path,inverse_path,ops_path.with_name('r44_tv_personnel_platforms.json'),BASE/model_revision/'tv_shoulder_shells_r44.json',WORLD/'native_collision_shapes.json']
    deps += [ROOT/'src/main/java/com/projectseele/world'/n for n in ('EvaHangarBuilder.java','TvPersonnelPlatformInterlockR44.java','EvaLogisticsDirector.java','TvCageCollisionR44.java','CityPersonnelDoorR44.java')]
    fleet=[{'path':str(p),'sha256':sha(p)} for p in identityfiles]
    r={'epoch_unix':time.time(),'operations':len(states),'matching_current_before':len(states)-len(mismatches),'state_mismatches':mismatches,
       'touched_BEs':betouched,'complete_local_BEs':len(berows),'complete_local_saved_entities':len(entities),'container_epoch_stable':start==finish,
       'container_hashes_before':start,'container_hashes_after':finish,'dependencies':{str(p):sha(p) for p in deps},'identity_data_hashes':fleet,
       'world_write':False,'preapply_ready':False,'native_passed':False,'art_passed':False,
       'required_remaining':['fresh source producer implementation/parity','complete crane and fullnative floor/guard vs carrier source envelopes','complete installed metadata/resource hash binding','root on-quiescent-world re-read exact before/BEs/identity epochs immediately before applying','actual native standing/return/occupancy/clock/cold/multiplayer and art']}
    (out/'contract.json').write_text(json.dumps(r,indent=2),'utf8');print(json.dumps({k:r[k] for k in ('operations','matching_current_before','touched_BEs','complete_local_BEs','complete_local_saved_entities','container_epoch_stable','preapply_ready')}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--model-revision',default='tv_personnel_supports_v5_draft9');p.add_argument('--metadata-revision',default='personnel_platforms_v5_boundaries_v2')
    a=p.parse_args();main(a.out,a.model_revision,a.metadata_revision)

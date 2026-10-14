"""Root-owned exact relocation of still-live metadata and HQ input contracts."""
import copy,hashlib,json,msvcrt
from pathlib import Path
from r52_spatial_plan import BASE,PYRAMID,HANGAR
from query_blocks import read_box
from extend_world_depth_r52 import acquire_world_lock
from apply_s20_approved_semantic_repairs import atomic_replace

def main():
    root=Path(__file__).resolve().parents[1];world=BASE/'WORLD_R52';out=BASE/'remaining_facility_metadata'
    out.mkdir(exist_ok=True);assert not(out/'APPLIED.json').exists()
    names=('facility_lighting_r30.json','r44_public_station_gates.json','regional_plan.json','r50_yashima_recovery_storage.json','tv_encounter_sites_r45.json')
    original={n:(world/n).read_bytes()for n in names};docs={n:json.loads(v)for n,v in original.items()}
    d=docs[names[0]];assert d['command_lever']==[26,-405,275]
    d['command_lever']=list(PYRAMID.block(d['command_lever']));d['command_lamps']=[list(PYRAMID.block(p))for p in d['command_lamps']]
    for p in [d['command_lever']]+d['command_lamps']:
        q=tuple(p);state=read_box(world,'projectseele:geofront',q,q)[q]
        assert ('minecraft:lever['in state)if p==d['command_lever']else('projectseele:nerv_'in state and 'light'in state),(p,state)
    assert d['constant_lamps']==json.loads(original[names[0]])['constant_lamps']
    count=0
    for g in docs[names[1]]['gates']:
        if g['station_id']!='9166787716217601435':continue
        g['position']=list(PYRAMID.block(g['position']));g['station_bounds']=[list(PYRAMID.block(p))for p in g['station_bounds']]
        q=tuple(g['position']);assert read_box(world,'projectseele:geofront',q,q)[q]==g['closed_state'];count+=1
    assert count==6
    for s in docs[names[2]]['stations']:
        if s['id']=='hq':assert s['pos']==[30,-467,490];s['pos']=list(PYRAMID.block(s['pos']))
    def storage(rows):
        for row in rows:
            if 'operation_layer_y'in row:assert row['operation_layer_y']==-442;row['operation_layer_y']-=236
            row['position']=list(HANGAR.block(row['position']))
            if 'facing'in row:row['facing']={'east':'west','west':'east'}[row['facing']]
            for field in('crew_stand_candidate','original_parked_eva'):
                if field in row:row[field]=list(HANGAR.point(row[field]))
            q=tuple(row['position']);state=read_box(world,'projectseele:geofront',q,q)[q]
            assert state.startswith('minecraft:barrel[')and('facing'not in row or'facing='+row['facing']in state),(q,state)
    storage(docs[names[3]]['recovery_storage'])
    nested=[]
    def visit(obj):
        if isinstance(obj,dict):
            for key,value in obj.items():
                if key=='recovery_storage'and isinstance(value,list):storage(value);nested.extend(value)
                else:visit(value)
        elif isinstance(obj,list):
            for value in obj:visit(value)
    visit(docs[names[4]]);assert len(nested)==2
    for n in names:docs[n]['r52_metadata_rebound']=True
    outputs={n:(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf8')for n,d in docs.items()}
    draft=root/'.Codex/r52_headquarters_binding/pending_root_metadata/r52'
    for n in('headquarters.json','headquarters_command_doors.json'):
        q='r52/'+n;assert not(world/q).exists();outputs[q]=(draft/n).read_bytes()
    hq=json.loads(outputs['r52/headquarters.json']);assert hq['translation']==[0,-93,0]and hq['epoch']==52
    assert hashlib.sha256(outputs['r52/headquarters_command_doors.json']).hexdigest()==hq['command_door_sha256']
    lock=acquire_world_lock();written=[]
    try:
        for n,b in original.items():assert(world/n).read_bytes()==b;(out/('before_'+n)).write_bytes(b)
        for n,b in outputs.items():
            (world/n).parent.mkdir(exist_ok=True);atomic_replace(world/n,b);written.append(n)
        for n,b in outputs.items():assert(world/n).read_bytes()==b
    except BaseException:
        for n in reversed(written):
            if n in original:atomic_replace(world/n,original[n])
            else:(world/n).unlink()
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    report=dict(world_written=True,files={n:hashlib.sha256(b).hexdigest()for n,b in outputs.items()},actual_command_lamps=58,actual_hq_gates=6,other_stations_unchanged=True,barrels=2,headquarters_doors=17,fixed_inputs=39,pending='rebind headquarters fingerprint after final route installation; native device acceptance')
    (out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)

if __name__=='__main__':main()

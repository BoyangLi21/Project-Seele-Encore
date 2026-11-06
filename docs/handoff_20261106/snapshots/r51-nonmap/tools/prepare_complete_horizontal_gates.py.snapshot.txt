"""Current 27 upper/retained/exit hatches: real supports, full lap and pockets.

Root's explicit fixed footprints only. Mechanical full-source clearance is a
separate native check; this script never replaces it with a voxel count.
"""
import argparse,gzip,hashlib,json,math,msvcrt
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
import regional_voxels as vox
import extend_world_depth_r52 as extension
from query_blocks import iter_selected_sections,iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--gates',type=Path,required=True)
    p.add_argument('--interface',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    base=a.base.resolve();world=base/'WORLD';out=base/'horizontal_launch_hatches';assert not(out/'APPLIED.json').exists()
    source=json.loads(a.gates.read_text('utf8'));interface=json.loads(a.interface.read_text('utf8'))
    assert source['epoch']==53 and source['directory_sha256']==interface['directory_sha256']
    assert hashlib.sha256(a.gates.read_bytes()).hexdigest()==interface['root_gate_candidate']['sha256']
    gates=[g for g in source['gates'] if g['resource'].startswith('bank_') and g['kind']=='SILO']
    assert len(gates)==27
    measured={r['resource']:r for r in interface['gates']};selected=defaultdict(set);boxes={};tables={}
    for g in gates:
        q=g['frame']['position'];cx,y,cz=q;y=math.floor(y)
        b=measured[g['resource']]['complete_mesh_motion_broadphase_bounds']
        lo=(math.floor(b[0]-.15),y-5,math.floor(b[2]-.15));hi=(math.floor(b[3]+.15),math.ceil(b[4]+.15),math.floor(b[5]+.15))
        boxes[g['resource']]=(lo,hi)
        ref=g['collision_steps'];path=a.gates.parent/ref['cells_file'];raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==ref['sha256']
        phases=json.loads(gzip.decompress(raw));assert len(phases)==1
        assert all(c['closed']=='minecraft:barrier' and c['open']=='minecraft:air' and c['position'][1]==y for c in phases[0])
        tables[g['resource']]=phases[0]
        for x in range(lo[0]//16,hi[0]//16+1):
            for z in range(lo[2]//16,hi[2]//16+1):selected[x,z].update(range(lo[1]//16,hi[1]//16+1))
    names=[];codes={};before={}
    def code(s):
        if s not in codes:codes[s]=len(names);names.append(s)
        return codes[s]
    for cx,cz,sy,palette,values in iter_selected_sections(world,'projectseele:geofront',selected):
        before[cx,cz,sy]=np.asarray([code(s) for s in palette],np.uint16)[values]
    assert len(before)==sum(map(len,selected.values()))
    after={k:v.copy() for k,v in before.items()};air=code('minecraft:air');panel=code('projectseele:nerv_structural_panel');barrier=code('minecraft:barrier')
    def at(q):
        x,y,z=map(int,q);return (x//16,z//16,y//16),(y%16)*256+(z%16)*16+x%16
    def get(q,which=before):k,j=at(q);return names[int(which[k][j])]
    def put(q,state):k,j=at(q);after[k][j]=state
    def fill(lo,hi,state,except_xz=None):
        for x in range(lo[0],hi[0]+1):
            for z in range(lo[2],hi[2]+1):
                if except_xz is not None and (x,z) in except_xz:continue
                for y in range(lo[1],hi[1]+1):put((x,y,z),state)
    for g in gates:
        lo,hi=boxes[g['resource']];y=math.floor(g['frame']['position'][1])
        opening={(c['position'][0],c['position'][2]) for c in tables[g['resource']]}
        # A continuous, three-block ring connects the measured eight feet to
        # surrounding original rock/shell, while retaining the whole aperture.
        fill(lo,(hi[0],y-3,hi[2]),panel,opening)
        fill((lo[0],y-2,lo[2]),hi,air)
    # Neighboring pocket footprints may overlap; complete all clearances first
    # and then author their real bearing columns and shared closed laps.
    for g in gates:
        lo,hi=boxes[g['resource']];y=math.floor(g['frame']['position'][1])
        assert len(g['supports'])==8
        for support in g['supports']:
            x,sy,z=support['position'];assert sy==y-3 and support['state']=='projectseele:nerv_structural_panel'
            fill((x,y-5,z),(x,y-3,z),panel)
        for c in tables[g['resource']]:put(c['position'],barrier)
    retained_sidewalk=[]
    for x in range(-33,-29):
        for z in range(132,142):
            q=(x,-467,z)
            if get(q)=='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]':
                k,j=at(q);after[k][j]=before[k][j];retained_sidewalk.append(list(q))
    assert len(retained_sidewalk)==22
    allowed={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:stone','minecraft:deepslate','minecraft:deepslate[axis=y]',
             'minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:gravel','minecraft:sand','minecraft:barrier','minecraft:iron_block',
             'minecraft:black_concrete','minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:polished_basalt[axis=y]',
             'minecraft:sea_lantern','minecraft:smooth_stone','minecraft:chiseled_quartz_block','minecraft:orange_concrete','minecraft:purple_concrete','minecraft:red_concrete',
             'minecraft:ladder[facing=north,waterlogged=false]','minecraft:ladder[facing=south,waterlogged=false]'}
    changed=Counter();foreign=[];total=0
    for (cx,cz,sy),old in before.items():
        delta=np.flatnonzero(old!=after[cx,cz,sy]);total+=len(delta)
        for j in delta:
            state=names[int(old[j])];changed[state]+=1
            if state not in allowed and not state.startswith('projectseele:nerv_'):
                foreign.append(dict(position=[cx*16+int(j)%16,sy*16+int(j)//256,cz*16+int(j)%256//16],state=state))
    lower=tuple(min(v[0][i] for v in boxes.values()) for i in range(3));upper=tuple(max(v[1][i] for v in boxes.values()) for i in range(3))
    for q,tag in iter_block_entities(world,'projectseele:geofront',lower,upper,selected_chunks=selected):
        k,j=at(q)
        if k in before:assert before[k][j]==after[k][j],('Original device in hatch footprint',q,str(tag['id']))
    for g in gates:
        for c in g['supports']:assert get(c['position'],after)==c['state']
        for c in tables[g['resource']]:assert get(c['position'],after)==c['closed']
    out.mkdir(exist_ok=True);keys=sorted(before)
    np.savez_compressed(out/'EXACT_BEFORE_AFTER.npz',section_keys=keys,before=np.array([before[k] for k in keys]),after=np.array([after[k] for k in keys]),palette=names)
    report=dict(world_written=False,root_author=True,gates=27,changed_cells=total,changed_materials=changed,foreign=foreign,
                mechanical_source_clearance_passed=False,full_body_admission_passed=False,
                gate_candidate_sha256=hashlib.sha256(a.gates.read_bytes()).hexdigest(),interface_sha256=hashlib.sha256(a.interface.read_bytes()).hexdigest(),
                complete_actual_closed_lap_cells=sum(len(t) for t in tables.values()),source_sized_foundation_contacts=216,
                original_sidewalk_half_slabs_retained=retained_sidewalk,sidewalk_actual_mesh_check_pending=True)
    (out/'CANDIDATE.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({**{k:v for k,v in report.items() if k!='foreign'},'foreign_count':len(foreign),
                      'foreign_materials':dict(Counter(r['state'] for r in foreign))}),flush=True)
    if not a.apply:return
    assert not foreign,'Original material requires explicit ownership before modification'
    vox.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-1344,320))
    for cx,cz,sy in keys:cuboids(painter,(cx*16,sy*16,cz*16),before[cx,cz,sy].reshape(16,16,16),after[cx,cz,sy].reshape(16,16,16),names,'current_source_matched_horizontal_gate_civil')
    painter.meta.update(report);painter.save_plan('twenty_seven_source_sized_hatches')
    lock=extension.acquire_world_lock()
    try:
        receipt=painter.apply('twenty_seven_source_sized_hatches',session_lock=lock);read=0
        for cx,cz,sy,palette,values in iter_selected_sections(world,vox.DIM,selected):
            assert np.array_equal(np.asarray([codes[s] for s in palette])[values],after[cx,cz,sy]);read+=1
        assert read==len(keys);report.update(world_written=True,full_selected_sections_read_back=read,receipt=receipt)
        (out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8')
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()

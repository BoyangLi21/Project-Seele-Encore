"""Open only measured full-source steel intersections and bind its four real feet."""
import argparse,json,hashlib,math,copy,msvcrt
from pathlib import Path
from collections import defaultdict,Counter
from query_blocks import iter_selected_sections,iter_block_entities,AIR
import regional_voxels as vox
from r52_spatial_plan import BASE
from extend_world_depth_r52 import acquire_world_lock
from apply_s20_approved_semantic_repairs import atomic_replace


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    root=Path(__file__).resolve().parents[1];world=BASE/'WORLD_R52';out=BASE/'mechanical_foundations';out.mkdir(exist_ok=True)
    source=root/'.Codex/r52_surface_armor_attack/results/LEGACY_LEAD_GEOMETRY.json';data=json.loads(source.read_text('utf8'))
    assert data['source']=='41e876a42b6ae2e7e68cc87895f135bcf79b59f583ec68e9b6e432ba8b3d02f8'
    units_path=BASE/'runtime_directory/units/ROOT_UNITS.json';original=units_path.read_bytes();units=json.loads(original)
    feet={};clear=set()
    for row in data['rows']:
        for name in ['actual_service_T_hits','carrier_full64_hits','service33_open_hits','service33_full_curve_idle_hits']:assert not row[name]
        for p in row['required_clear_cell_candidates']:clear.add(tuple(map(int,p.split('/'))))
        for p in row['feet']:
            assert p['y']==-746
            q=(math.floor(p['x']),-747,math.floor(p['z']));feet[q]=(row['variant'],p)
    assert len(feet)==12 and not(clear&set(feet))
    wanted=clear|set(feet)|{(x,y-1,z)for x,y,z in feet};selected=defaultdict(set);sections=defaultdict(set);states={}
    for x,y,z in wanted:selected[x//16,z//16].add(y//16);sections[x//16,z//16,y//16].add((x,y,z))
    for cx,cz,sy,palette,ix in iter_selected_sections(world,'projectseele:geofront',selected):
        a=ix.reshape(16,16,16)
        for x,y,z in sections[cx,cz,sy]:states[x,y,z]=palette[int(a[y%16,z%16,x%16])]
    assert len(states)==len(wanted)
    allowed=AIR|{'projectseele:nerv_shaft_panel','projectseele:nerv_structural_panel'}
    assert all(states[p]in allowed for p in clear)
    for p,(variant,centre)in feet.items():
        assert states[p]=='projectseele:nerv_shaft_panel'and states[p[0],p[1]-1,p[2]]=='projectseele:nerv_shaft_panel'
        assert min(centre['x']-p[0],p[0]+1-centre['x'],centre['z']-p[2],p[2]+1-centre['z'])>=.12
        unit=next(r for r in units['units']if r['variant']==variant)
        assert len(unit['carrier_support'])in(2,3,4,5)
        unit['carrier_support'].append(dict(position=list(p),state=states[p]))
    lo=tuple(min(p[i]for p in wanted)for i in range(3));hi=tuple(max(p[i]for p in wanted)for i in range(3))
    for p,t in iter_block_entities(world,'projectseele:geofront',lo,hi,selected_chunks=set(selected)):assert tuple(p)not in wanted,('Existing protected device',p)
    vox.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-960,320));stage='actual_lead_steel_clearance_and_bearing'
    assert not list((out/stage).glob('applied_*'))
    changed={p:states[p]for p in clear if states[p]not in AIR}
    for p,state in sorted(changed.items()):painter.exact((*p,*p),state,'minecraft:air','R52_source_mesh_lead_column_and_retreat_clearance')
    painter.meta.update(root_author=True,actual_source_sha256=data['source'],finite_source_pose_samples=129,source_file_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        four_real_bearing_cells_per_bay=[dict(position=p,variant=v,centre=c)for p,(v,c)in feet.items()],native_verified=False)
    folder=painter.save_plan(stage);report=dict(world_written=False,source_sha256=data['source'],changed_cells=len(changed),before_states=dict(Counter(changed.values())),
        actual_bearing_cells=12,bearing_geometry_changed=False,units_before_sha256=hashlib.sha256(original).hexdigest(),native_verified=False)
    encoded=(json.dumps(units,ensure_ascii=False,indent=2)+'\n').encode('utf8');(folder/'ROOT_UNITS_AFTER.json').write_bytes(encoded);(folder/'ROOT_UNITS_BEFORE.json').write_bytes(original)
    if args.apply:
        lock=acquire_world_lock()
        try:
            assert units_path.read_bytes()==original
            report['application']=painter.apply(stage,session_lock=lock)
            atomic_replace(units_path,encoded);assert units_path.read_bytes()==encoded
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
        report['world_written']=True;report['units_after_sha256']=hashlib.sha256(encoded).hexdigest()
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)


if __name__=='__main__':main()

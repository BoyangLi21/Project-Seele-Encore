"""Root phase-one rail sockets: existing shell contacts only; isolated pads stay pending."""
import argparse,json,hashlib
from collections import defaultdict,Counter
from pathlib import Path
import regional_voxels as vox
from query_blocks import iter_selected_sections,iter_block_entities
from r52_spatial_plan import BASE


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--body-clearance-receipt',type=Path);args=ap.parse_args()
    root=Path(__file__).resolve().parents[1];folder=root/'artifacts/r52_original_owner_candidate_20261010'
    source=folder/'ACTUAL_ROOT_NEW_FOOT_RAILS_ANCHORS_FINAL_PIN_OCT11.json';rows=json.loads(source.read_text('utf8'))
    gates=json.loads((root/'.Codex/r52_rail_foundations/FINAL_FIXED_GUIDE_GATE_CLEARANCE.json').read_text('utf8'))
    assert gates['clear']and gates['gates']==42 and gates['fixed_path_source_sha256']==rows['paths_sha256']and gates['rig_source_sha256']==rows['source_sha256']
    rawpaths=root/'src/main/resources/assets/projectseele/facility/r52_ground_guide_paths.json'
    assert hashlib.sha256(rawpaths.read_bytes()).hexdigest()==rows['paths_sha256']
    assert hashlib.sha256((BASE/'runtime_directory/gates/ROOT_GATES.json').read_bytes()).hexdigest()==gates['gate_file_sha256']
    anchors={tuple(map(int,r['position'])):r for r in rows['native_anchor_cells']};assert len(anchors)==1542
    def neighbours(p):
        for axis in range(3):
            for sign in(-1,1):q=list(p);q[axis]+=sign;yield tuple(q)
    wanted=set(anchors)
    for p in anchors:wanted.update(neighbours(p))
    selected=defaultdict(set);sections=defaultdict(set)
    for x,y,z in wanted:selected[x//16,z//16].add(y//16);sections[x//16,z//16,y//16].add((x,y,z))
    states={};world=BASE/'WORLD_R52'
    for cx,cz,sy,palette,indices in iter_selected_sections(world,'projectseele:geofront',selected):
        data=indices.reshape(16,16,16)
        for x,y,z in sections[cx,cz,sy]:states[x,y,z]=palette[int(data[y%16,z%16,x%16])]
    assert len(states)==len(wanted)
    bearing={'projectseele:nerv_shaft_panel','projectseele:nerv_structural_panel','projectseele:nerv_machine_edge',
             'projectseele:nerv_machine_panel','projectseele:nerv_floor_panel','minecraft:stone','minecraft:andesite','minecraft:diorite',
             'minecraft:black_concrete','minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:deepslate','minecraft:deepslate[axis=y]'}
    free={'minecraft:air','minecraft:cave_air','minecraft:void_air'}
    out=BASE/'fixed_foot_rail_foundations';stage='existing_shell_native_sockets';assert not list((out/stage).glob('applied_*'))
    vox.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';paint=vox.Painter(vertical_bounds=(-960,320));ready=[];pending=[]
    for p,row in anchors.items():
        old=states[p];assert old in bearing|free,(p,old)
        contacts=[dict(position=q,state=states[q])for q in neighbours(p)if states[q]in bearing]
        record=dict(row,position=list(p),before=old,existing_full_face_contacts=contacts)
        if old not in bearing and not contacts:pending.append(record);continue
        ready.append(record)
        if old!=row['state']:paint.exact((*p,*p),old,row['state'],'R52_fixed_rail_socket_in_original_lining')
    chunks={(p[0]//16,p[2]//16)for p in anchors};lo=tuple(min(p[i]for p in anchors)for i in range(3));hi=tuple(max(p[i]for p in anchors)for i in range(3))
    for p,tag in iter_block_entities(world,'projectseele:geofront',lo,hi,selected_chunks=chunks):assert tuple(p)not in anchors,('Protected block entity at proposed rail anchor',p,str(tag['id']))
    paint.meta.update(root_author=True,source_sha256=rows['paths_sha256'],rig_sha256=rows['source_sha256'],partial_installation=True,
        rule='Existing documented launch-shaft lining/structure only; isolated air pads need separately designed real foundations')
    plan=paint.save_plan(stage)
    report=dict(world_written=False,ready_anchors=len(ready),changed_cells=len(paint.ops),pending_isolated=len(pending),
                source_sha256=rows['paths_sha256'],rig_sha256=rows['source_sha256'],gate_curve_clearance=True,native_verified=False,
                supports=ready,pending=pending)
    if args.apply:
        assert args.body_clearance_receipt is not None,'Complete actual moving EVA/carrier against selected fixed guides and socket cubes required'
        evidence=json.loads(args.body_clearance_receipt.read_text('utf8'))
        assert evidence['clear'] and evidence['path_source_sha256']==rows['paths_sha256']and evidence['includes_full_eva_and_original_carrier']
        report['application']=paint.apply(stage);report['world_written']=True
    (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items()if k not in('supports','pending')}),flush=True)


if __name__=='__main__':main()

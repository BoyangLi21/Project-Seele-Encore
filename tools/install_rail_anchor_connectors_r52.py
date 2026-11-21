"""Install Root's selected 37 foundations after gate and complete-body admission."""
import argparse,json,hashlib
from pathlib import Path
from collections import defaultdict
import regional_voxels as vox
from query_blocks import AIR,iter_selected_sections,iter_block_entities
from r52_spatial_plan import BASE


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    root=Path(__file__).resolve().parents[1];folder=BASE/'fixed_foot_rail_foundations/connectors';world=BASE/'WORLD_R52'
    chosen=json.loads((folder/'SELECTED_37_SUPPORT_PATHS.json').read_text('utf8'))['paths'];assert len(chosen)==37
    gated=set();body=set();proofs=[]
    for path in [folder/'GATE_CLEARANCE.json',folder/'EXTENDED_GATE_CLEARANCE.json']:
        d=json.loads(path.read_text('utf8'));assert d['gate_count']==42
        assert d['gates_sha256']==hashlib.sha256((BASE/'runtime_directory/gates/ROOT_GATES.json').read_bytes()).hexdigest()
        gated.update(map(tuple,d['clear_cells']));proofs.append(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    for name in ['NEW_37_SUPPORT_PER_CELL_RECEIPT.json','EXTENDED_13_SUPPORT_PER_CELL_RECEIPT.json']:
        path=root/'.Codex/r52_surface_armor_attack/results'/name;d=json.loads(path.read_text('utf8'))
        assert d['includes_actual_full_eva_and_carrier_and_station']and d['fixed_source_sha256']=='e09fe5a920585e1ae12df8b27a55d53102550c33c84b5c1009e58ee890a3e287'
        clear=d['clear_cells']if 'clear_cells'in d else[r['cell']for r in d['cells']if r['clear']and not r['hits']]
        body.update(map(tuple,clear));proofs.append(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    cells={tuple(p)for r in chosen for p in r['cells']};assert cells<=gated and cells<=body
    wanted=cells|{tuple(r['attachment'])for r in chosen};selected=defaultdict(set);sections=defaultdict(set);states={}
    for x,y,z in wanted:selected[x//16,z//16].add(y//16);sections[x//16,z//16,y//16].add((x,y,z))
    for cx,cz,sy,palette,ix in iter_selected_sections(world,'projectseele:geofront',selected):
        a=ix.reshape(16,16,16)
        for x,y,z in sections[cx,cz,sy]:states[x,y,z]=palette[int(a[y%16,z%16,x%16])]
    assert len(states)==len(wanted)
    for row in chosen:
        path=list(map(tuple,row['cells']))+[tuple(row['attachment'])];assert path[0]==tuple(row['anchor'])
        assert all(sum(abs(a[i]-b[i])for i in range(3))==1 for a,b in zip(path,path[1:]))
        assert states[path[-1]]==row['attachment_state']and all(states[p]in AIR for p in path[:-1])
    lo=tuple(min(p[i]for p in wanted)for i in range(3));hi=tuple(max(p[i]for p in wanted)for i in range(3))
    for p,t in iter_block_entities(world,'projectseele:geofront',lo,hi,selected_chunks=set(selected)):
        assert tuple(p)not in cells,('Protected device in selected footing',p)
    vox.WORLD=world;vox.OUT=folder;vox.DIM='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-960,320));stage='selected_37_finite_structural_connections'
    assert not list((folder/stage).glob('applied_*')),'Never replay applied foundations'
    for p in sorted(cells):painter.exact((*p,*p),states[p],'projectseele:nerv_structural_panel','R52_actual_fixed_rail_anchor_foundation')
    painter.meta.update(root_author=True,paths=chosen,evidence=proofs,gate_curves=42,full_turn_stations=12,native_verified=False)
    out=painter.save_plan(stage);report=dict(world_written=False,anchors=37,foundation_cells=len(cells),all_face_connected_to_existing_structure=True,evidence=proofs,native_verified=False)
    if args.apply:report['application']=painter.apply(stage);report['world_written']=True
    (out/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)


if __name__=='__main__':main()

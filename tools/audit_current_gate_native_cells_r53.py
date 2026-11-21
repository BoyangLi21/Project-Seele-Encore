"""Read exact current41 gate proxy/support cells and bounded footing columns."""
from pathlib import Path
import argparse,collections,gzip,hashlib,json,math
from query_blocks import iter_selected_sections,iter_block_entities
from regional_voxels import canonical_state
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--interface',type=Path,required=True);ap.add_argument('--interface-sha256',required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    assert sha(a.interface)==a.interface_sha256;d=read(a.interface);parent=a.interface.parent;candidate=parent/d['root_gate_candidate']['file'];assert sha(candidate)==d['root_gate_candidate']['sha256'];gates=read(candidate)['gates'];frames={g['resource']:g for g in d['gates']}
    wanted=set();closed={};support={};columns={}
    for g in gates:
        ref=g['collision_steps'];path=parent/ref['cells_file'];assert sha(path)==ref['sha256'];rows=json.loads(gzip.decompress(path.read_bytes()));closed[g['resource']]=[c for row in rows for c in row];support[g['resource']]=g['supports'];wanted.update(tuple(c['position']) for c in closed[g['resource']]+g['supports'])
        for contact in frames[g['resource']]['bearing_contacts']:
            if contact['kind']=='native_top_face':
                x,y,z=contact['candidate_cell'];columns[x,z]=max(y,columns.get((x,z),-1344))
    moving_proxies={tuple(c['position']) for cells in closed.values() for c in cells}
    for (x,z),y in columns.items():wanted.update((x,j,z) for j in range(-1344,y+1))
    selected=collections.defaultdict(set);by_section=collections.defaultdict(list)
    for x,y,z in wanted:selected[x//16,z//16].add(y//16);by_section[x//16,z//16,y//16].append((x,y,z))
    regions={a.world/'dimensions/projectseele/geofront/region'/f'r.{cx//32}.{cz//32}.mca' for cx,cz in selected};before={str(p):sha(p) if p.exists() else None for p in regions};states={}
    for cx,cz,sy,palette,indices in iter_selected_sections(a.world,'projectseele:geofront',selected):
        for x,y,z in by_section[cx,cz,sy]:states[x,y,z]=palette[int(indices[((y&15)<<8)|((z&15)<<4)|(x&15)])]
    native_file=a.world/'native_collision_shapes.json';shapes={canonical_state(k):v for k,v in read(native_file).items()}
    supplement=ROOT/'.Codex/map_complete_20261013/route_audit/prelaunch_world_current/CURRENT_PRODUCTION_SUPPLEMENTAL_SHAPES.json'
    if supplement.exists():
        for k,v in read(supplement)['rows'].items():shapes[canonical_state(k)]=v['native_boxes']
    def boxes(at):
        state=states.get(tuple(at));return shapes.get(canonical_state(state)) if state is not None else None
    def top_face(at,point,half):
        native=boxes(at)
        if native is None:return None
        for b in native:
            if all(b[0]+at[0]-1e-7<=point[0]+dx<=b[3]+at[0]+1e-7 and b[2]+at[2]-1e-7<=point[2]+dz<=b[5]+at[2]+1e-7 for dx in (-half,0,half) for dz in (-half,0,half)):
                return at[1]+b[4]
        return False
    a.out.mkdir(parents=True,exist_ok=True);rows=[];mismatch=[];footings=[]
    for g in gates:
        name=g['resource'];counts=collections.Counter();bad=[]
        for kind,cells,key in [('support',support[name],'state'),('closed_proxy',closed[name],'closed')]:
            for c in cells:
                at=tuple(c['position']);actual=states.get(at);expected=c[key];counts[kind+'_total']+=1;counts[kind+'_match']+=actual==expected
                if actual!=expected:row=dict(resource=name,kind=kind,position=list(at),expected=expected,actual=actual,classification='missing_chunk_or_section' if actual is None else 'air' if actual.startswith(('minecraft:air','minecraft:cave_air','minecraft:void_air')) else 'barrier' if actual=='minecraft:barrier' else 'existing_material');bad.append(row);mismatch.append(row)
        for contact in frames[name]['bearing_contacts']:
            at=contact['candidate_cell'];point=contact['point_world'];normal=contact['normal_world'];native=boxes(at);bearing=False
            if native is not None:
                axis=next(i for i,v in enumerate(normal) if abs(v)>.999999);axes=[i for i in range(3) if i!=axis];half=contact['half_width_m'];bearing=all(any(abs(point[axis]-(b[axis+3] if normal[axis]>0 else b[axis])-at[axis])<=.0002 and all(b[j]+at[j]-.0002<=point[j]+offset<=b[j+3]+at[j]+.0002 for j,offset in zip(axes,(u,v))) for b in native) for u in (-half,0,half) for v in (-half,0,half))
            row=dict(resource=name,contact=contact,actual_state=states.get(tuple(at)),native_shape_known=native is not None,actual_finite_native_face_bears=bearing)
            if contact['kind']=='native_top_face' and not bearing:
                unknown=[];nearest=None;excluded=[]
                for y in range(at[1],-1345,-1):
                    q=(at[0],y,at[2]);top=top_face(q,point,contact['half_width_m'])
                    if q in moving_proxies or states.get(q)=='minecraft:barrier':excluded.append(dict(position=list(q),state=states.get(q)));continue
                    if top is None:unknown.append(list(q));break
                    if top is not False:
                        nearest=dict(position=list(q),state=states[q],top_y=top,gap_to_required_bearing_y=point[1]-top);break
                row.update(nearest_known_native_top_face_below=nearest,unknown_before_foundation=unknown,excluded_moving_or_barrier_proxies=excluded,construction_authorized=False)
            footings.append(row)
        rows.append(dict(resource=name,counts=dict(counts),closed_proxy_bounds=[[min(c['position'][i] for c in closed[name]) for i in range(3)],[max(c['position'][i] for c in closed[name]) for i in range(3)]],mismatches=len(bad)))
    # Exact BE presence is preserved separately; no inferred deletion permission.
    focus={tuple(r['position']) for r in mismatch};bes=[]
    if focus:
        lo=tuple(min(p[i] for p in focus) for i in range(3));hi=tuple(max(p[i] for p in focus) for i in range(3));chunks={(p[0]//16,p[2]//16) for p in focus}
        for at,tag in iter_block_entities(a.world,'projectseele:geofront',lo,hi,selected_chunks=chunks):
            if at in focus:bes.append(dict(position=list(at),id=str(tag.get('id','')),nbt_snbt=str(tag)))
    after={str(p):sha(p) if p.exists() else None for p in regions};changed=[p for p in before if before[p]!=after[p]]
    result=dict(schema='projectseele.r53.current41-gate-native-cell-readback.v1',world=str(a.world.resolve()),interface_sha256=a.interface_sha256,candidate_sha256=sha(candidate),world_written=False,native_game_started=False,regions_unchanged_during_read=not changed,changed_regions=changed,region_sha256=after,native_shape_source_sha256=sha(native_file),supplement_sha256=sha(supplement) if supplement.exists() else None,gates=rows,mismatches=mismatch,bearing_contacts=footings,block_entities_at_mismatches=bes,unknown_cells=len(wanted-states.keys()),notes=['Native support faces use saved exact block-state shape tables, with current production supplemental shapes. Unknown shape stops downward search.','Nearest support is a measured vertical candidate only; no inference of room ownership or permission to bridge a void.','Root decides bounded supported civil changes; original actors/BE/stairs/static mechanical steel remain protected.'])
    path=a.out/'CURRENT41_NATIVE_CELLS.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf8');print(json.dumps(dict(path=str(path),gates=len(rows),mismatches=len(mismatch),supports_without_actual_face=sum(not f['actual_finite_native_face_bears'] for f in footings),unknown=result['unknown_cells'],consistent=not changed,world_written=False)))
if __name__=='__main__':main()

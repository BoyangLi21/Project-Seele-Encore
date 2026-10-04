"""Read v7 exact facility state/NBT and third-walk domains; never writes a world."""
from pathlib import Path
import argparse,gzip,hashlib,json,math,re,sys
sys.dont_write_bytecode=True
import nbtlib,numpy as np
import query_blocks as q

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r45'
V5=ART/'composition_candidates/R45_source_candidate_20261004_v5_01/world'
V7=ART/'composition_candidates/R45_source_candidate_20261004_v7_01/world'
OWN=ART/'pyramid_components_sol_v1/v7_631_actual_readback_v1'
PREP=ART/'pyramid_components_sol_v1/v5_combined_entry_v2'
RUN=ART/'native_facility_session_v1/native_components_v5_third_v1'
RECEIPT=ART/'city_transport_xhigh_r45/station_lower_frame_complete_ports_v2/root_install_v7_01/full_file_receipt.json'
DIM='projectseele:geofront'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p))
def write(p,v):Path(p).write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def inventory(w):return{p.relative_to(w).as_posix():sha(p)for p in sorted(w.rglob('*'))if p.is_file()}
def main():
    assert not OWN.exists();OWN.mkdir()
    receipt=read(RECEIPT);assert receipt['phase']=='COMPLETE'and Path(receipt['world']).resolve()==V7.resolve()
    current=inventory(V7);assert current==receipt['full_after_inventory']and len(current)==1736
    with gzip.open(PREP/'forward631.jsonl.gz','rt',encoding='utf8')as f:rows=[json.loads(s)for s in f if s.strip()]
    assert len(rows)==len({tuple(r['pos'])for r in rows})==631
    replacements=read(PREP/'replacement_BE8.json');planned=read(ART/'pyramid_components_sol_v1/v5_native_entry_preparation_v1/real_player_cases165.UNBOUND.json')
    native=read(RUN/'components165_BE17.native.json');walks=native['walk_cases']
    assert native['walk_complete']==165 and native['actual_actor_restored']and len(walks)==165 and all(c['passed']for c in walks)
    assert {c['id']for c in planned['cases']}=={c['id']for c in walks}
    selected={}
    def box(lo,hi):
        for cx in range(math.floor(lo[0])//16,math.floor(hi[0])//16+1):
            for cz in range(math.floor(lo[2])//16,math.floor(hi[2])//16+1):
                selected.setdefault((cx,cz),set()).update(range(math.floor(lo[1])//16,math.floor(hi[1])//16+1))
    for r in rows:box(r['pos'],r['pos'])
    for r in replacements:box(r['position'],r['position'])
    # Full sections cover body, bearing, complete boundary and neighbor sweep.
    for c in planned['cases']:
        points=c.get('path',[c.get('start'),c.get('target')]);points=[p for p in points if p is not None]
        for a,b in zip(points,points[1:]+points[-1:]):box([min(a[i],b[i])-2 for i in range(3)],[max(a[i],b[i])+4 for i in range(3)])
    for c in walks:
        for sample in c['trace']:
            for key in ('actual_body','actual_client_body'):
                nums=[float(n)for n in re.findall(r'-?\d+(?:\.\d+)?(?:E[-+]?\d+)?',sample[key])]
                assert len(nums)==6;box([v-2 for v in nums[:3]],[v+2 for v in nums[3:]])
    def snapshot(world):
        states={};sections={};tags={};seen=set()
        assert all(v=='full'for v in q.chunk_statuses(world,DIM,selected).values())
        for cx,cz,sy,palette,indices in q.iter_selected_sections(world,DIM,selected):
            key=cx,cz,sy;sections[key]=np.asarray(palette,dtype=object)[indices];seen.add(key)
        bounds=min(x for x,z in selected),max(x for x,z in selected),min(z for x,z in selected),max(z for x,z in selected)
        for cx,cz,chunk in q.iter_chunks(q.dimension_dir(world,DIM),bounds,selected):
            for tag in chunk.get('block_entities',[]):
                pos=tuple(int(tag[k])for k in ('x','y','z'))
                if pos[1]//16 in selected[cx,cz]:tags[pos]=tag
        for r in rows+replacements:
            p=tuple(r.get('pos',r.get('position')));x,y,z=p;key=x//16,z//16,y//16
            arr=sections.get(key);states[p]='minecraft:air'if arr is None else str(arr[((y&15)<<8)|((z&15)<<4)|(x&15)])
        return states,sections,tags
    a,old_sections,old_tags=snapshot(V5);b,new_sections,new_tags=snapshot(V7)
    observations=[]
    for r in rows:
        p=tuple(r['pos']);tag=new_tags.get(p);want=None if r['after_nbt']is None else nbtlib.parse_nbt(r['after_nbt'])
        observations.append(dict(pos=p,component=r['component'],expected_state=r['after'],actual_state=b[p],complete_actual_NBT=None if tag is None else tag.snbt(),expected_complete_NBT=r['after_nbt'],state_equal=b[p]==r['after'],typed_NBT_equal=tag==want))
    write(OWN/'all631_actual_state_and_complete_NBT.json',observations)
    assert all(r['state_equal']and r['typed_NBT_equal']for r in observations)
    replacement_results=[]
    for r in replacements:
        p=tuple(r['position']);tag=new_tags.get(p);ok=b[p]==r['state']and tag==nbtlib.parse_nbt(r['full_nbt'])
        replacement_results.append(dict(pos=p,state=b[p],complete_actual_NBT=None if tag is None else tag.snbt(),full_state_and_typed_NBT_equal=ok))
    write(OWN/'eight_preserved_replacements_complete.json',replacement_results);assert all(r['full_state_and_typed_NBT_equal']for r in replacement_results)
    section_rows=[]
    for cx,cz in sorted(selected):
        for sy in sorted(selected[cx,cz]):
            key=cx,cz,sy;old=old_sections.get(key);new=new_sections.get(key)
            ok=(old is None and new is None)or(old is not None and new is not None and np.array_equal(old,new))
            section_rows.append(dict(chunk=[cx,cz],section_y=sy,all4096_full_states_equal=bool(ok)))
    write(OWN/'complete_planned_and_actual_walk_body_sections.json',section_rows)
    assert all(r['all4096_full_states_equal']for r in section_rows)and old_tags==new_tags
    files=[]
    for op in read(PREP/'static_files_forward_inverse.json'):
        p=V7/op['target'];files.append(dict(target=op['target'],actual_sha256=sha(p),expected_after_sha256=op['after_sha256'],complete_bytes_equal=p.read_bytes()==Path(op['after_file']).read_bytes()))
    assert len(files)==2 and all(r['complete_bytes_equal']for r in files)
    uid=nbtlib.load(V7/'dimensions/projectseele/geofront/data/projectseele_tokyo3_building_world_id_r44.dat')['data']['WorldUUID']
    assert str(uid)=='50ba377e-9053-5dfa-93be-9601e623037c'
    assert inventory(V7)==current
    report=dict(schema='projectseele.v7-facility-exact-map-inheritance.v1',source_world=str(V7),actual_source_receipt=ref(RECEIPT),full1736_after_inventory_equal=True,exact631_full_state_NBT_equal=True,eight_replacement_fixtures_full_state_NBT_equal=True,static_metadata=files,walk_domain_complete_sections=len(section_rows),walk_domain_voxels_compared=4096*len(section_rows),walk_domain_full_BE_equal=True,walk_inherited165_from=ref(RUN/'components165_BE17.native.json'),walk_executed_this_audit=0,inheritance_scope='Map geometry and original walk/closed-boundary cases only; no new native execution or changed-runtime assertion.',BE_tick_completed_in_parent=9,BE_required17=True,BE_relog_pass=False,full_lifecycle_pass=False,world_written=False,Java_MC_started=False,models_or_NPC_changed=False)
    write(OWN/'report.json',report);print(json.dumps(report,ensure_ascii=True,indent=2))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--version',choices=('v7','v8'),default='v7');args=parser.parse_args()
    if args.version=='v8':
        V7=ART/'composition_candidates/R45_source_candidate_20261004_v8_01/world'
        OWN=ART/'pyramid_components_sol_v1/v8_631_actual_readback_v1'
        RECEIPT=ART/'city_transport_xhigh_r45/retired_station_overbridge_complete_v1/root_install_v8_01/full_file_receipt.json'
    main()

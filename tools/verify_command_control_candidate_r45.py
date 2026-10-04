"""Verify a finite door proposal in memory against the full 1736-file source."""
from __future__ import annotations
import argparse, gzip, hashlib, json, math, sys
from pathlib import Path
sys.dont_write_bytecode=True
from measure_world_r40 import MeasuredWorld, properties
from query_blocks import iter_block_entities, AIR
from prepare_school_hakone_native_r45 import ActualGeometry

ROOT=Path(__file__).resolve().parents[1]
BASELINE=ROOT/'artifacts/rebuild_r45/city_atomic_integration_r45/qa_copy_revision_v1/copy_plan_v2/copy_plan.json'
NORMAL={'north':(0,-1),'south':(0,1),'west':(-1,0),'east':(1,0)}
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf8')
def rows(p):
    with gzip.open(p,'rt',encoding='utf8')as f:return [json.loads(line)for line in f]

def main(args):
    folder,out=args.proposal.resolve(),args.out.resolve()
    assert not out.exists() and not out.is_relative_to(Path(read(BASELINE)['source_world']))
    baseline=read(BASELINE);world=Path(baseline['source_world']);assert len(baseline['files'])==1736
    def full_source_hashes():
        expected={r['relative']:r['sha256']for r in baseline['files']}
        actual={p.relative_to(world).as_posix()for p in world.rglob('*')if p.is_file()}
        assert actual==set(expected),('Complete source inventory changed',sorted(actual-set(expected)),sorted(set(expected)-actual))
        measured={name:sha(world/name)for name in sorted(expected)}
        assert measured==expected,'At least one complete frozen baseline file changed'
        return measured
    before=full_source_hashes();proposal=read(folder/'proposal.json')
    assert proposal['world']==str(world) and proposal['world_written']is False
    for key,name in [('forward_sha256','forward.jsonl.gz'),('inverse_sha256','inverse.jsonl.gz')]:assert proposal[key]==sha(folder/name)
    marker_before=read(folder/'command_marker.before.json');marker_after=read(folder/'command_marker.after.json')
    assert (folder/'command_marker.before.json').read_bytes()==(world/proposal['marker_file_proposal']['relative']).read_bytes()
    assert proposal['marker_file_proposal']['after_sha256']==sha(folder/'command_marker.after.json')
    assert marker_before['excludedOriginalDoors']==marker_after['excludedOriginalDoors']
    assert {tuple(r['lower'])for r in marker_before['excludedOriginalDoors']}=={(24,-423,254),(24,-418,254)}
    original={r['id']:r for r in marker_before['doors']};candidate={r['id']:r for r in marker_after['doors']}
    assert len(original)==len(candidate)==17 and set(original)==set(candidate)==set(range(19))-{5,14}
    forward,inverse,mask=rows(folder/'forward.jsonl.gz'),rows(folder/'inverse.jsonl.gz'),rows(folder/'positive_edit_mask.jsonl.gz')
    assert len(forward)==len(inverse)==len(mask)==18
    assert {tuple(r['pos'])for r in forward}==set(map(tuple,mask)) and len(set(map(tuple,mask)))==18
    measured=MeasuredWorld(world)
    for row in candidate.values():measured.around(row['lower'],9)
    measured.load();assert all(v=='full'for v in measured.status.values())
    tags=dict(iter_block_entities(world,'projectseele:geofront',(-20,-445,225),(80,-400,380),selected_chunks=set(measured.selected)))
    def full(q):
        tag=tags.get(tuple(q));return dict(pos=list(q),state=measured.block(q),full_nbt=None if tag is None else tag.snbt())
    image={};apertures={tuple(q)for r in original.values()for q in r['aperture']}
    for row,reverse in zip(forward,inverse):
        q=tuple(row['pos']);actual=full(q)
        assert actual['state']==row['before'] and actual['full_nbt']==row['before_nbt']
        assert q not in apertures and row['before']in AIR and row['before_nbt']is None and row['after_nbt']is None
        assert row['after'].startswith('minecraft:stone_button[')
        for key,val in [('pos','pos'),('before','after'),('after','before'),('before_nbt','after_nbt'),('after_nbt','before_nbt')]:assert reverse[key]==row[val]
        image[q]=row['after']
    class Candidate:
        def __init__(self):self.world=world
        def block(self,q):return image.get(tuple(q),measured.block(q))
        def get(self,x,y,z):return self.block(tuple(map(math.floor,(x,y,z))))
    geometry=ActualGeometry(Candidate());buttons=set();support_cells=set();aliases=[]
    for ident,row in sorted(candidate.items()):
        old=original[ident]
        assert all(row[key]==old[key]for key in ('id','lower','facing','axis','aperture'))
        contracts=row['fixedInputContractsR45'];assert {tuple(c['pos'])for c in contracts}==set(map(tuple,row['buttons']))
        assert {c['side']for c in contracts}=={-1,1}
        for c in contracts:
            q=tuple(c['pos']);support=tuple(c['fixed_support']['pos']);p=properties(c['state_after']);dx,dz=NORMAL[p['facing']]
            assert q not in buttons and q not in apertures and support not in apertures
            assert c['input_before']==full(q) and c['fixed_support']==full(support)
            assert c['fixed_support']['full_nbt']is None and c['input_before']['full_nbt']is None
            assert support==(q[0]-dx,q[1],q[2]-dz) and p['face']=='wall'
            assert geometry.boxes(support)==[[0.0,0.0,0.0,1.0,1.0,1.0]]
            assert Candidate().block(q)==c['state_after']
            assert geometry.standing(c['operator'])=='STATIC_STANDING'
            assert math.dist([c['operator'][0],c['operator'][1]+1.62,c['operator'][2]],[q[0]+.5,q[1]+.5,q[2]+.5])<=4
            nx,nz=NORMAL[row['facing']];assert ((c['operator'][0]-row['lower'][0]-.5)*nx+(c['operator'][2]-row['lower'][2]-.5)*nz)*c['side']>=.3
            buttons.add(q);support_cells.add(support)
            if c.get('preserved_original_alias'):aliases.append(dict(id=ident,pos=list(q)))
    assert len(buttons)==37 and len(aliases)==3
    # Applying the exact inverse to the heap image restores all source cells.
    for row in inverse:image[tuple(row['pos'])]=row['after']
    assert all(Candidate().block(r['pos'])==measured.block(r['pos'])for r in forward)
    after=full_source_hashes();assert before==after
    out.mkdir(parents=True)
    write(out/'full_source_before_after_sha256.json',dict(before=before,after=after))
    write(out/'verification.json',dict(schema='projectseele.r45-command-control-offline-proof.v1',
        source_world=str(world),full_source_files=1736,baseline=dict(path=str(BASELINE),sha256=sha(BASELINE)),
        source_complete_inventory_and_all_hashes_unchanged=True,proposal=dict(path=str(folder/'proposal.json'),sha256=sha(folder/'proposal.json')),
        door_owners=17,complete_moving_cells_preserved=102,primary_inputs=34,preserved_original_aliases=aliases,all_input_contracts=37,
        static_edits=18,exact_positive_inverse_cells=True,exact_original_marker_bytes_preserved=True,
        all_input_supports_complete_old_state_and_NBT_preserved=True,all37_actual_supported_operator_points=True,
        whole_closed_open_inputs_functional_pass=False,exact_native_outline_and_canSurvive_pass=False,ID15_original_stair_interface_native_pass=False,
        world_written=False,java_started=False,gradle_started=False,all679_native_pass=False,
        required_before_install='Recheck the unchanged complete 1736-file frozen source and all old full state/NBT. Root alone may install the exact static and marker delta into a fresh admitted QA world, then derive a new checkpoint/lease.'))
    print(json.dumps(dict(full_source_files=1736,all_hashes_unchanged=True,doors=17,inputs=37,static_cells=18,world_written=False,native_pass=False)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--proposal',type=Path,required=True);p.add_argument('--out',type=Path,required=True);main(p.parse_args())

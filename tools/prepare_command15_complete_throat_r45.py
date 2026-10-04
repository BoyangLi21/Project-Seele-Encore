"""Prepare six-cell whole three-lane stair throat and exact producer patch only."""
from pathlib import Path
import ast,copy,difflib,gzip,hashlib,json,math,sys
sys.dont_write_bytecode=True
from measure_world_r40 import MeasuredWorld
from prepare_school_hakone_native_r45 import ActualGeometry
from query_blocks import iter_block_entities

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r45'
WORLD=ART/'composition_candidates/R45_source_candidate_20261004_v7_01/world'
OUT=ART/'lifts_doors_lifecycle_sol_v2/command15_complete_three_lane_throat_v1'
STAIR='minecraft:stone_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]'
EXPECTED={(x,y,283):('minecraft:smooth_stone'if y in(-414,-412)else'minecraft:black_concrete',STAIR if y==-414 else'minecraft:air')for x in(27,29)for y in(-414,-413,-412)}
GUARDS={(28,-414,283):STAIR,(28,-415,282):'minecraft:white_concrete'}
GUARDS.update({(x,-414,284):'minecraft:polished_andesite'for x in(27,28,29)})
GUARDS.update({(x,y,283):s for x in(26,30)for y,s in[(-414,'minecraft:smooth_stone'),(-413,'minecraft:yellow_concrete'),(-412,'minecraft:smooth_stone')]})
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p))
def write(p,v):Path(p).write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def jsonl(p,rows):
    with Path(p).open('wb')as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0)as f:
        for r in rows:f.write((json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf8'))
def main():
    assert not OUT.exists();OUT.mkdir()
    m=MeasuredWorld(WORLD);m.box((25,-416,280),(31,-409,288));m.load();assert all(s=='full'for s in m.status.values())
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(25,-416,280),(31,-409,288),selected_chunks=set(m.selected)))
    marker_file=WORLD/'.projectseele_command_sliding_doors_r01.json';marker=read(marker_file);door=next(r for r in marker['doors']if r['id']==15)
    assert door['lower']==[28,-413,284]and len(door['aperture'])==6
    aperture={tuple(p)for p in door['aperture']};all_apertures={tuple(p)for d in marker['doors']for p in d['aperture']}
    inputs={tuple(p)for d in marker['doors']for p in d['buttons']}
    assert not(set(EXPECTED)&(all_apertures|inputs|set(tags)))
    assert all(m.block(p)==a for p,(a,b)in EXPECTED.items())and all(m.block(p)==s for p,s in GUARDS.items())
    rows=[dict(dimension='projectseele:geofront',pos=list(p),before=a,after=b,before_nbt=None,after_nbt=None,owner='r45/command15/complete_three_lane_stair_throat',reason='Complete the existing 3-wide door with original central south step and two matching supported side steps; retire only inner jamb pair and preserve outside framing, original roof, ladders, controls, all aperture cells and identities.')for p,(a,b)in sorted(EXPECTED.items())]
    jsonl(OUT/'forward.jsonl.gz',rows);jsonl(OUT/'inverse.jsonl.gz',[dict(r,before=r['after'],after=r['before'])for r in rows]);jsonl(OUT/'positive_edit_mask.jsonl.gz',[r['pos']for r in rows])
    changes={tuple(r['pos']):r['after']for r in rows}
    class Image:
        world=WORLD
        def __init__(self,after):self.after=after
        def block(self,p):return 'minecraft:air'if tuple(p)in aperture else changes.get(tuple(p),m.block(p))if self.after else m.block(p)
        def get(self,x,y,z):return self.block((math.floor(x),math.floor(y),math.floor(z)))
    before=ActualGeometry(Image(False));after=ActualGeometry(Image(True));routes=[]
    def nine_bearing_within_step(g,p):
        hits=[]
        for dx in(-.25,0,.25):
            for dz in(-.25,0,.25):
                x,z=p[0]+dx,p[2]+dz;heights=[]
                for y in range(math.floor(p[1])-2,math.floor(p[1])+1):
                    at=(math.floor(x),y,math.floor(z));boxes=g.boxes(at);assert boxes is not None
                    for b in boxes:
                        top=y+b[4]
                        if at[0]+b[0]<=x<=at[0]+b[3]and at[2]+b[2]<=z<=at[2]+b[5]and p[1]-.65<=top<=p[1]+.01:heights.append(top)
                assert heights,'Candidate has an actual unsupported stair footprint'
                hits.append(dict(ray=[x,p[1],z],actual_top=max(heights),datum_drop=p[1]-max(heights)))
        return hits
    for x in(27.5,28.5,29.5):
        path=[[x,-414,282.5],[x,-413.5,283.1],[x,-413,283.8],[x,-413,284.5],[x,-413,285.5]]
        proofs=[]
        for p in path:
            body=after.clear(p);assert body=='CLEAR';proofs.append(dict(point=p,before_body=before.clear(p),after_body=body,after_nine_support_rays=nine_bearing_within_step(after,p),exact_datum_bearing=after.standing(p)))
        sweeps=[]
        for a,b in zip(path,path[1:]):
            high=max(a[1],b[1]);p=[a[0],high,a[2]];target=[b[0],high,b[2]];status=after.clear(p,target=target);assert status=='CLEAR'
            sweeps.append(dict(start=a,finish=b,actual_high_datum=high,body_clear=status,native_vanilla_step_required=a[1]!=b[1]))
        routes.append(dict(lane_x=x,path=path,points=proofs,complete_neighbor_body_sweeps=sweeps,native_pass=False))
    assert not before.unknown and not after.unknown
    write(OUT/'complete_three_lane_before_after_body_bearing_and_sweeps.json',routes)
    component=[dict(pos=[x,y,z],state=m.block((x,y,z)),full_nbt=None if(x,y,z)not in tags else tags[x,y,z].snbt())for x in range(25,32)for y in range(-416,-408)for z in range(280,289)]
    write(OUT/'complete_component_before_state_NBT_and_preserved_neighbors.json',component)
    # Same exact helper can run within the original door producer. Other
    # doors, widened planes and original manual shaft doors remain separate.
    source=ROOT/'tools/s41_install_command_sliding_doors.py';raw=source.read_bytes();eol='\r\n'if b'\r\n'in raw else'\n';text=raw.decode('utf8').replace('\r\n','\n')
    helper='''def complete_id15_stair_throat(cells, block_entities):
    expected = '''+repr(EXPECTED)+'''
    guards = '''+repr(GUARDS)+'''
    for pos, state in guards.items():
        if cells.get(pos) != state or pos in block_entities:
            raise RuntimeError("ID15 authored approach guard changed: " + str(pos))
    changes = []
    for pos, (before, after) in sorted(expected.items()):
        if pos in block_entities or cells.get(pos) not in {before, after}:
            raise RuntimeError("ID15 exact approach preimage or full BE changed: " + str(pos))
        if cells[pos] != after:
            changes.append((pos, after))
    return changes


'''
    text=text.replace('from query_blocks import AIR, dimension_dir, read_box','from query_blocks import AIR, dimension_dir, read_box, iter_block_entities',1)
    needle='def plan(world: Path) -> tuple[list[Change], list[dict]]:';assert text.count(needle)==1;text=text.replace(needle,helper+needle,1)
    needle='    return (sorted(changes.values(), key=lambda c: (c.y, c.z, c.x)),\n            report)'
    replacement='''    approach_tags = dict(iter_block_entities(
        world, DIMENSION, (26, -415, 282), (30, -412, 284)))
    for pos, after in complete_id15_stair_throat(cells, approach_tags):
        add(pos, after, "complete_ID15_original_three_lane_south_stair_throat")

'''+needle
    assert text.count(needle)==1;text=text.replace(needle,replacement,1);ast.parse(text)
    candidate=text.replace('\n',eol).encode('utf8');(OUT/'s41_install_command_sliding_doors.before.txt').write_bytes(raw);(OUT/'s41_install_command_sliding_doors.candidate.txt').write_bytes(candidate)
    patch=''.join(difflib.unified_diff(raw.decode('utf8').splitlines(True),candidate.decode('utf8').splitlines(True),fromfile='a/tools/s41_install_command_sliding_doors.py',tofile='b/tools/s41_install_command_sliding_doors.py'))
    (OUT/'root_complete_ID15_throat_producer.forward.patch').write_bytes(patch.encode('utf8'))
    inverse=''.join(difflib.unified_diff(candidate.decode('utf8').splitlines(True),raw.decode('utf8').splitlines(True),fromfile='a/tools/s41_install_command_sliding_doors.py',tofile='b/tools/s41_install_command_sliding_doors.py'))
    (OUT/'root_complete_ID15_throat_producer.inverse.patch').write_bytes(inverse.encode('utf8'))
    # Replay only the pure producer helper against actual source and seven
    # foreign-state controls. No plan/apply or legacy world is opened.
    namespace={};exec(helper,namespace);fn=namespace['complete_id15_stair_throat'];cells={tuple(r['pos']):r['state']for r in component}
    assert dict(fn(cells,tags))==changes;assert fn(dict(cells,**{})|changes,tags)==[]
    controls=[]
    for label,p,value,is_tag in [('side_step_changed',(27,-414,283),'minecraft:diamond_block',False),('foreign_NBT_on_inner_column',(27,-413,283),None,True),('original_central_stair_changed',(28,-414,283),'minecraft:air',False),('outer_left_column_changed',(26,-413,283),'minecraft:air',False),('outer_right_column_changed',(30,-412,283),'minecraft:air',False),('continuation_floor_changed',(29,-414,284),'minecraft:air',False),('foreign_NBT_on_original_central_stair',(28,-414,283),None,True)]:
        fake=dict(cells);fake_tags=dict(tags)
        if is_tag:fake_tags[p]='foreign complete NBT'
        else:fake[p]=value
        try:fn(fake,fake_tags)
        except RuntimeError as exc:controls.append(dict(name=label,rejected=True,reason=str(exc)))
        else:raise AssertionError('Producer accepted foreign component: '+label)
    write(OUT/'actual_source_producer_replay_and_negative_controls.json',dict(real_source_exact6_replay=True,already_after_idempotent_zero_writes=True,negative_controls=controls,world_written=False))
    regions={str(WORLD/'dimensions/projectseele/geofront/region'/f'r.{x//32}.{z//32}.mca'):sha(WORLD/'dimensions/projectseele/geofront/region'/f'r.{x//32}.{z//32}.mca')for x,z in m.selected}
    report=dict(source_world=str(WORLD),source_epoch=ref(ART/'city_transport_xhigh_r45/station_lower_frame_complete_ports_v2/root_install_v7_01/full_file_receipt.json'),source_marker=ref(marker_file),forward=ref(OUT/'forward.jsonl.gz'),inverse=ref(OUT/'inverse.jsonl.gz'),exact_delta_cells=6,complete_component_cells=len(component),whole3_lane_steps=True,original_centre_step_retained=True,all102_door_aperture_cells_and37_inputs_retained=True,outside_columns_roof_and_ladders_retained=True,all_BEs_preserved=True,NBT_delta_count=0,progress_or_actor_identity_changed=False,producer_first_widening=ref(ROOT/'artifacts/s41_command_sliding_doors_20260821_211108/receipt.json'),producer_source_before=ref(source),producer_patch=ref(OUT/'root_complete_ID15_throat_producer.forward.patch'),producer_applied=False,native_vanilla_step_and_door_occupation=False,installed=False,visual_accepted=False,source_regions_sha256=regions,world_written=False,Java_MC_started=False,models_changed=False)
    write(OUT/'report.json',report);print(json.dumps({k:v for k,v in report.items()if k!='source_regions_sha256'},ensure_ascii=True,indent=2))
if __name__=='__main__':main()

"""Exact rear-of-Tree chamber/reader proposal; Root alone installs world deltas."""
import json,gzip,hashlib,copy,argparse
from pathlib import Path
import nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,AIR
from regional_voxels import canonical_state
ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW';OUT=ROOT/'artifacts/rebuild_r45/dead_sea_chamber_sol_followup/component_v2'
DIM='projectseele:geofront';KEY='r45/dead_sea/highest_tree_chamber'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def state_tag(s):
    name,_,props=s.partition('[');t=nbtlib.Compound({'Name':nbtlib.String(name)})
    if props:t['Properties']=nbtlib.Compound({k:nbtlib.String(v) for k,v in (x.split('=',1) for x in props.rstrip(']').split(','))})
    return t
def main():
    assert not OUT.exists();OUT.mkdir(parents=True)
    w=MeasuredWorld(WORLD);lo=(22,-331,333);hi=(38,-314,351);w.box(lo,hi);w.load();assert all(s=='full' for s in w.status.values())
    tags=dict(iter_block_entities(WORLD,DIM,lo,hi));target={}
    art=(30,-322,339);book=(30,-329,340);book_after=(30,-329,345)
    assert w.block(art)=='projectseele:wall_artwork' and str(tags[art]['Artwork'])=='tree'
    assert float(tags[art]['Width'])==10 and float(tags[art]['Height'])==12 and int(tags[art]['Facing'])==2
    assert w.block((30,-329,338))=='another_furniture:black_stool[low=false,waterlogged=false]'
    assert w.block((30,-329,339))=='projectseele:command_seat_back[facing=north,half=lower]'
    assert w.block(book)=='projectseele:dead_sea_archive[facing=north]' and str(tags[book]['id'])=='projectseele:dead_sea_archive'
    assert w.block((30,-329,341))==w.block((30,-328,341))=='minecraft:white_concrete'
    never={q for q in tags if q not in [book]}|{(30,y,339) for y in [-329,-328]}|{(30,-329,338),(30,-329,341),(30,-328,341)}
    def put(q,after,reason,after_nbt=None,allow_existing=False):
        q=tuple(q);assert q not in never,('Protected existing identity',q)
        before=w.block(q);assert before is not None
        if q in tags and not allow_existing:raise AssertionError(('Full original BE protected',q))
        if before==after and after_nbt is None:return
        target[q]=dict(pos=list(q),before=before,after=canonical_state(after),before_nbt=tags[q].snbt() if q in tags else None,
            after_nbt=after_nbt,owner=KEY,reason=reason)
    # User-defined room behind the actual mural: existing intact floor, whole
    # explicit enclosure. No floor or room inferred from a standable-air scan.
    room=[25,-329,341,35,-326,347]
    for x in range(25,36):
        for z in range(341,348):assert w.get(x,-330,z).partition('[')[0] in ['minecraft:white_concrete','minecraft:black_concrete','minecraft:red_concrete','minecraft:polished_blackstone']
    for y in range(-329,-325):
        for z in range(341,349):
            for x in [24,36]:
                assert w.get(x,y,z) in AIR
                put((x,y,z),'minecraft:white_concrete','Complete finite side enclosure behind confirmed Tree wall; no outer glazing changed')
        for x in range(25,36):
            assert w.get(x,y,348) in AIR
            put((x,y,348),'minecraft:white_concrete','Complete room rear wall below retained inclined pyramid glazing')
    for x in range(24,37):
        for z in range(341,349):
            assert w.get(x,-325,z) in AIR
            put((x,-325,z),'minecraft:white_concrete','Whole room ceiling below retained highest-room glazing')
    for x in (27,33):put((x,-325,344),'minecraft:sea_lantern','Two original native ceiling luminaires attached to the complete chamber ceiling')
    # Human-left seen facing the north-facing mural is +X. This reader needs
    # its own real backing extension; X36/Z340 was measured void_air.
    for y in range(-329,-315):
        assert w.get(36,y,340) in AIR
        put((36,y,340),'minecraft:white_concrete','Complete wall-left reader backing tied to existing wall/floor; human-left is east')
    # Close the retired chair-back niche, without moving either seat/back or
    # the historical white display column. Move only the existing full book BE.
    put(book,'minecraft:white_concrete','Retire old book-in-wall niche; whole original book moves into user-defined chamber',allow_existing=True)
    put((30,-328,340),'minecraft:white_concrete','Close the old two-high book niche independently of new passage')
    moved=copy.deepcopy(tags[book])
    for k,v in zip(('x','y','z'),book_after):moved[k]=nbtlib.Int(v)
    assert w.block(book_after) in AIR
    put(book_after,'projectseele:dead_sea_archive[facing=north]','Relocate same full original book BE to intact floor; root model/render remain unchanged',moved.snbt())
    readers=[((36,-328,339),'north','outside_left'),((35,-328,341),'south','inside_exit')]
    for q,face,role in readers:
        # Inside reader interrupts only our new wall-independent circulation,
        # never the retained display column or painting anchor.
        if q in target:assert target[q]['after']=='minecraft:white_concrete'
        else:assert w.block(q) in AIR
        tag=nbtlib.Compound({'id':nbtlib.String('projectseele:nerv_access_reader'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),
            'Gate':nbtlib.Long((32<<38)|(340<<12)|(-329&4095)),'Exit':nbtlib.Long(0),'Width':nbtlib.Int(3),'Height':nbtlib.Int(3),'Clearance':nbtlib.Int(3),
            'AlongX':nbtlib.Byte(1),'Linked':nbtlib.Byte(1),'Style':nbtlib.Int(0),'DoorId':nbtlib.Int(0),'Label':nbtlib.String('死海文书'),
            'ChamberId':nbtlib.String(KEY),'ChamberRole':nbtlib.String(role),'OpenUntil':nbtlib.Long(0),'SwipeAt':nbtlib.Long(-1),'IndicateUntil':nbtlib.Long(0),'Presented':nbtlib.Int(0),'Status':nbtlib.Int(0)})
        put(q,f'projectseele:nerv_access_reader[facing={face}]','Explicit highest-card reader; separate exact 200tick chamber controller, no generic lift lease/model',tag.snbt())
    cells=[(x,y,340) for x in range(32,35) for y in range(-329,-326)]
    assert all(w.block(q)=='minecraft:white_concrete' and q not in tags for q in cells)
    images=nbtlib.List[nbtlib.Compound]([nbtlib.Compound({'Pos':nbtlib.Long((q[0]<<38)|(q[2]<<12)|(q[1]&4095)),
        'State':state_tag(w.block(q))}) for q in cells])
    images.append(nbtlib.Compound({'Pos':nbtlib.Long((art[0]<<38)|(art[2]<<12)|(art[1]&4095)),
        'State':state_tag(w.block(art)),'NBT':copy.deepcopy(tags[art])}))
    identity=str(nbtlib.load(WORLD/'dimensions/projectseele/geofront/data/projectseele_tokyo3_building_world_id_r44.dat')['data']['WorldUUID'])
    binding=nbtlib.List[nbtlib.Compound]([nbtlib.Compound({'Pos':nbtlib.Long((q[0]<<38)|(q[2]<<12)|(q[1]&4095)),'Role':nbtlib.String(role),'Facing':nbtlib.String(face)}) for q,face,role in readers])
    data=nbtlib.Compound({'Version':nbtlib.Int(1),'Configured':nbtlib.Byte(1),'WorldUUID':nbtlib.String(identity),'ChamberId':nbtlib.String(KEY),
        'Gate':nbtlib.Long((32<<38)|(340<<12)|(-329&4095)),'Width':nbtlib.Int(3),'Height':nbtlib.Int(3),'OpenTicks':nbtlib.Int(200),
        'Mode':nbtlib.String('CLOSED'),'OpenUntil':nbtlib.Long(0),'Fault':nbtlib.String(''),'Images':images,'Readers':binding})
    marker=OUT/'projectseele_dead_sea_chamber_r45.dat';nbtlib.File({'DataVersion':nbtlib.Int(3465),'data':data}).save(marker,gzipped=True)
    rows=[target[q] for q in sorted(target)]
    for label,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(OUT/(label+'.jsonl.gz'),'wt',encoding='utf8') as stream:
            for row in rows:
                r=copy.deepcopy(row)
                if inverse:r['before'],r['after']=r['after'],r['before'];r['before_nbt'],r['after_nbt']=r['after_nbt'],r['before_nbt']
                stream.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
    with gzip.open(OUT/'positive_edit_mask.jsonl.gz','wt',encoding='utf8') as stream:
        for row in rows:stream.write(json.dumps(row['pos'])+'\n')
    (OUT/'preserved_full_BE.json').write_text(json.dumps([dict(pos=q,state=w.block(q),full_snbt=t.snbt()) for q,t in tags.items() if q!=book],ensure_ascii=False,indent=2),'utf8')
    report=dict(world=str(WORLD),world_id=identity,actual_mural=dict(pos=art,state=w.block(art),full_snbt=tags[art].snbt()),
        original_book=dict(pos=book,full_snbt=tags[book].snbt()),new_book=book_after,room_interior=room,
        portal=dict(base=[32,-329,340],width=3,height=3),readers=[dict(pos=q,facing=face,role=role) for q,face,role in readers],
        highest_card_clearance=3,exact_authorized_open_ticks=200,mural_left_seen_from_north='+X/east',
        whole_original_chair_back_and_white_display_column_preserved=True,region_field_NBT_not_normalized=True,
        candidate_cells=len(rows),new_full_BE=2,relocated_same_book_BE=1,other_original_BE_preserved=len(tags)-1,
        world_written=False,source_models_render_or_animation_changed=False,native_pass=False,art_pass=False,
        forward_sha256=sha(OUT/'forward.jsonl.gz'),inverse_sha256=sha(OUT/'inverse.jsonl.gz'),marker_sha256=sha(marker))
    (OUT/'contract.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Frozen chamber candidate',len(rows),'cells, two tier3 readers, full original book moved; no world writes')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=OUT);a=p.parse_args();OUT=a.out.resolve();main()

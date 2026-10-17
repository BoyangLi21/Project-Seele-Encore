"""Retire the commissioned near-city Yashima decks, piers and two stock machines.

Bounds and ownership come from prepare_battle_civil_r50.yashima and the world's
r50_yashima_civil marker. Natural ridge and underlying city streets remain.
"""
from pathlib import Path
from collections import Counter
import argparse, gzip, json, uuid, math, copy, msvcrt
import nbtlib
from query_blocks import read_box, iter_block_entities, AIR
from repair_r53_reported_landings import apply as apply_cells
from transplant_s22_authority import read_region, parse_chunk, build_region, chunk_blob
from apply_s20_approved_semantic_repairs import atomic_replace, parse_state

DIM='projectseele:geofront'
FLOOR='projectseele:nerv_floor_panel'
FRAME='projectseele:nerv_structural_panel'

def packed(p):
    x,y,z=p;n=((x&67108863)<<38)|((z&67108863)<<12)|(y&4095)
    return n-(1<<64) if n>=1<<63 else n

def plan(world,out):
    marker=json.loads((world/'r50_yashima_civil.json').read_text('utf8'))
    assert marker['hero']==[30.5,104,498.5] and marker['cover']==[30.5,110,458.5]
    lo=(-90,79,437);hi=(150,174,530)
    cells=read_box(world,DIM,lo,hi);tags=dict(iter_block_entities(world,DIM,lo,hi));rows=[]
    owned={}
    def own(x0,x1,y0,y1,z0,z1,reason):
        for x in range(x0,x1+1):
            for z in range(z0,z1+1):
                for y in range(y0,y1+1):owned[x,y,z]=reason
    own(6,54,81,103,467,529,'hero_deck_and_piers')
    own(20,94,81,109,448,466,'shield_deck_and_piers')
    own(55,94,81,109,469,489,'shield_approach_and_piers')
    own(77,94,81,109,448,489,'shield_return_deck')
    own(95,129,81,109,446,529,'two_weapon_stock_decks_and_piers')
    for x in range(-86,7):
        floor=79+math.floor((x+86)*24/92)
        own(x,x,79,floor,488,507,'retired_eva_approach')
    own(66,71,80,107,502,528,'retired_crew_stairs')
    own(55,58,104,117,499,511,'retired_power_and_controls')
    hardware={'projectseele:umbilical_socket','minecraft:lever','minecraft:stone_button',
              'minecraft:black_concrete','minecraft:polished_andesite_stairs'}
    for p,reason in owned.items():
        before=cells.get(p,'minecraft:air');name=before.split('[')[0]
        is_deck=before in (FLOOR,FRAME) or name.startswith('mtr:escalator_')
        is_control=reason=='retired_power_and_controls' and (name in hardware or name.startswith('projectseele:'))
        is_stair=reason=='retired_crew_stairs' and name=='minecraft:polished_andesite_stairs'
        if not (is_deck or is_control or is_stair):continue
        tag=tags.get(p)
        if tag is not None:assert is_control,('Unrelated device',p,tag.snbt())
        # At the original city level preserve the existing street; the old
        # ramp's thin panels are replaced by the matching road surface.
        after='minecraft:air' if p[1]>80 else 'minecraft:black_concrete' if p[1]==80 else 'minecraft:stone'
        if before==after:continue
        rows.append(dict(pos=p,before=before,after=after,before_nbt=None if tag is None else tag.snbt(),after_nbt=None,reason=reason))
    out.mkdir(parents=True,exist_ok=True)
    (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows,ensure_ascii=False).encode('utf8'),mtime=0))
    targets={r[k] for r in marker['yashima_controls']['supply_racks'] for k in ('uuid','cargo_uuid')}
    actors=[]
    for name in ('r.0.0.mca','r.0.1.mca'):
        path=world/'dimensions/projectseele/geofront/entities'/name
        if not path.exists():continue
        stamps,blobs=read_region(path)
        for slot,blob in enumerate(blobs):
            if not blob:continue
            for e in parse_chunk(blob).get('Entities',[]):
                uid=str(uuid.UUID(''.join(f'{int(v)&0xffffffff:08x}' for v in e['UUID'])))
                if uid in targets:
                    assert 90<=float(e['Pos'][0])<=140 and 430<=float(e['Pos'][2])<=540
                    actors.append(dict(uuid=uid,region=name,slot=slot,before=e.snbt()))
    report=dict(world=str(world),cells=len(rows),reasons=dict(Counter(r['reason'] for r in rows)),actors=actors,natural_ridge_retained=True,installed=False)
    (out/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Old Yashima plan:',len(rows),'cells,',len(actors),'original weapon actors')

def apply(world,out):
    apply_cells(world,out)
    report=json.loads((out/'PLAN.json').read_text('utf8'));rows=json.loads(gzip.decompress((out/'EXACT_DELTA.json.gz').read_bytes()))
    with (world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        for name in {r['region'] for r in report['actors']}:
            path=world/'dimensions/projectseele/geofront/entities'/name;stamps,blobs=read_region(path)
            for row in [r for r in report['actors'] if r['region']==name]:
                doc=parse_chunk(blobs[row['slot']]);found=[e for e in doc['Entities'] if e.snbt()==row['before']]
                assert len(found)==1
                doc['Entities']=nbtlib.List[nbtlib.Compound]([e for e in doc['Entities'] if e.snbt()!=row['before']]);blobs[row['slot']]=chunk_blob(doc)
            atomic_replace(path,build_region(stamps,blobs))
        # The static generator must not recreate the retired deck after reset.
        data=world/'dimensions/projectseele/geofront/data'
        topology=nbtlib.load(next(data.glob('projectseele_city_rigid_topology_r45_*.dat')))['data']
        folder=data/str(topology['GenerationFolder'])/'chunks';grouped={}
        for row in rows:grouped.setdefault((row['pos'][0]//16,row['pos'][2]//16),[]).append(row)
        for (cx,cz),batch in grouped.items():
            path=folder/f'{cx}_{cz}.dat'
            if not path.exists():continue
            doc=nbtlib.load(path);bypos={int(r['Pos']):r for r in doc['Static']};palette=doc['Palette'];ids={r.snbt():i for i,r in enumerate(palette)};changed=False
            for r in batch:
                old=bypos.get(packed(r['pos']))
                if old is None:continue
                state=parse_state(r['after']);key=state.snbt()
                if key not in ids:ids[key]=len(palette);palette.append(state)
                old['StateId']=nbtlib.Int(ids[key]);old.pop('NBT',None);changed=True
            if changed:doc.save(path,gzipped=True)
        for name in ('r50_yashima_civil.json','r50_yashima_supply_entities_receipt.json'):
            path=world/name;before=path.read_text('utf8');d=json.loads(before);d.update(installed=False,retired_r53=True,retirement='User removed the old near-city platform and both stock machines')
            (out/(name+'.before')).write_text(before,'utf8');path.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')
        path=world/'tv_encounter_sites_r45.json';before=path.read_text('utf8');d=json.loads(before);r=d['sites'].get('ramiel',{})
        if r.get('hero')==[30.5,104,498.5]:
            r['retired_r53']=True;r['geometry_validated']=False
            if 'yashima_controls' in r:r['yashima_controls']['installed']=False
            (out/'tv_encounter_sites_r45.json.before').write_text(before,'utf8');path.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')
        report['installed']=True;report['generator_updated']=True
        (out/'COMPLETE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
        print('Original platform, weapons and generator retired')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args();(apply if a.apply else plan)(a.world,a.output)

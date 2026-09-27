"""Receiving aprons outside the UN hangar roof, with real foundations and links.

Only the two named review copies can be written. Original actors and equipment
remain untouched; exact block preconditions/inverses are handled by Painter.
"""
from pathlib import Path
import argparse,json,math,nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,ROOT
from query_blocks import iter_block_entities
from inspect_map_assets import region_chunks

PADS=[dict(serial=1,home=6282,centre=[6278.5,78.6,-6048.5],box=[6240,6316,-6090,-6006]),
      dict(serial=0,home=6442,centre=[6466.5,78.6,-6048.5],box=[6426,6506,-6090,-6006])]
FLOOR='minecraft:light_gray_concrete'
NATURAL={'minecraft:air','minecraft:dirt','minecraft:grass_block','minecraft:stone','minecraft:gravel','minecraft:andesite','minecraft:diorite','minecraft:granite'}
PAVING={'minecraft:light_gray_concrete','minecraft:gray_concrete','minecraft:white_concrete','minecraft:black_concrete','minecraft:yellow_concrete','projectseele:nerv_structural_panel','projectseele:nerv_floor_panel'}


def main(world,apply=False):
    world=world.resolve()
    assert world.parent==ROOT/'run/saves' and world.name in ('SEELE_FIELD_R40_REVIEW','SEELE_R32_AIR_REVIEW')
    out=ROOT/'artifacts/world_combat_r40/un_reception'/world.name
    v.WORLD=world;v.OUT=out;p=v.Painter();w=MeasuredWorld(world)
    masks=[]
    for pad in PADS:
        x0,x1,z0,z1=pad['box'];mask={(x,z) for x in range(x0,x1+1) for z in range(z0,z1+1)}
        for z in range(-6102,-6047):
            t=(z+6102)/54;cx=round(pad['home']*(1-t)+(pad['centre'][0]-.5)*t)
            mask.update((x,z) for x in range(cx-24,cx+25))
        masks.append(mask)
        w.box((min(x for x,z in mask),58,-6102),(max(x for x,z in mask),170,z1))
    w.load();allmask=set.union(*masks)
    # A real actor parked in the work volume is a conflict, not an expendable prop.
    path=world/'dimensions/projectseele/geofront/entities/r.12.-12.mca'
    occupants=[];preserved_carts=[]
    saved=nbtlib.load(world/'dimensions/projectseele/geofront/data/projectseele_un_airlift_r29.dat')['data']
    cart_ids={tuple(map(int,saved[k])) for k in ('Cart0','Cart1') if k in saved}
    if path.exists():
        for _,_,chunk in region_chunks(path,(384,415,-384,-353)):
            for entity in chunk.get('Entities',[]):
                pos=list(map(float,entity.get('Pos',[])))
                if len(pos)==3 and (math.floor(pos[0]),math.floor(pos[2])) in allmask and pos[1]<82:
                    if str(entity.get('id'))=='projectseele:un_transport' and tuple(map(int,entity.get('UUID',[]))) in cart_ids and pos[1]>=77:
                        preserved_carts.append(dict(position=pos,uuid=list(map(int,entity['UUID']))));continue
                    occupants.append(dict(type=str(entity.get('id')),position=pos))
    if occupants:raise RuntimeError(('Occupied receiving-apron work volume',occupants))
    tags=dict(iter_block_entities(world,v.DIM,(6238,58,-6102),(6508,170,-6006)))
    if any(any(pad['box'][0]<=x<=pad['box'][1] and pad['box'][2]<=z<=pad['box'][3] for pad in PADS) and y<=79 for x,y,z in tags):
        raise RuntimeError('Existing block entity in the aircraft receiving column')
    changes={};held=[]
    def put(q,state,why):
        before=w.block(q)
        if before is None:raise RuntimeError(('Unmeasured',q))
        if q in tags:return
        if before!=state:changes[q]=(state,why)
    for pad,mask in zip(PADS,masks):
        x0,x1,z0,z1=pad['box'];cx,_,cz=pad['centre']
        for x,z in sorted(mask):
            states=[w.get(x,y,z) for y in range(58,77)]
            ground=max((y for y,s in zip(range(58,77),states) if s!='minecraft:air'),default=57)
            if ground<58:raise RuntimeError(('No measured foundation bearing',x,z))
            for y in range(ground+1,76):
                boundary=any((x+dx,z+dz) not in mask for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)))
                put((x,y,z),'projectseele:nerv_structural_panel' if boundary else 'minecraft:gravel','foundation')
            before=w.get(x,76,z).partition('[')[0]
            if before not in NATURAL|PAVING:held.append([x,76,z,before]);continue
            inpad=x0<=x<=x1 and z0<=z<=z1
            stripe=inpad and (x in (x0+4,x1-4) or z in (z0+4,z1-4))
            seam=(x-x0)%8==0 or (z-z0)%8==0
            paint='minecraft:yellow_concrete' if stripe else 'minecraft:gray_concrete' if seam else FLOOR
            put((x,76,z),paint,'paving_and_load_zone')
            for y in range(77,171):
                current=w.get(x,y,z);name=current.partition('[')[0]
                if name=='minecraft:air':continue
                if (x,y,z) in tags:continue
                if name in {'minecraft:iron_bars','projectseele:nerv_ceiling_light'}:
                    put((x,y,z),'minecraft:air','retire_old_apron_edge_inside_extension')
                else:held.append([x,y,z,current])
        # Personnel rails are outside the reserved payload rectangle, with a
        # broad rear opening onto the existing level approach.
        for x,z in sorted(mask):
            if not any((x+dx,z+dz) not in mask for dx,dz in ((1,0),(-1,0),(0,1),(0,-1))):continue
            if z<=-6090:continue
            for y in (77,78):put((x,y,z),'minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]','perimeter_guard')
        for x in range(x0+6,x1-5,10):
            for z in (z0+2,z1-2):put((x,77,z),'projectseele:nerv_ceiling_light[hanging=false,lit=true]','flush_guidance_light')
        # Flush UN identification; no pole or sign crosses the aircraft column.
        glyphs={'U':['10001','10001','10001','10001','01110'],'N':['10001','11001','10101','10011','10001']}
        for letter,offset in [('U',-12),('N',2)]:
            for row,bits in enumerate(glyphs[letter]):
                for col,bit in enumerate(bits):
                    if bit=='1':
                        for dx in (0,1):
                            for dz in (0,1):put((int(cx)+offset+col*2+dx,76,int(cz)+row*2+dz),'minecraft:white_concrete','UN_floor_identity')
    if held:raise RuntimeError(('Unapproved structures in receiving-apron volume',held[:40],len(held)))
    for q,(after,why) in sorted(changes.items()):p.match((*q,*q),w.block(q),after,'r40/un_reception/'+why)
    entries=[dict(serial=pad['serial'],deck=pad['centre'],floor_y=77,bounds=pad['box'],approach=[pad['home']+.5,78.6,-6101.5]) for pad in PADS]
    marker={'schema':'projectseele.un-reception.r40.v1','pads':entries,'reason':'Whole fallen body requires an unobstructed vertical arrival column outside the hangar overhang','source':'User-authorized UN recovery platform and global circulation correction'}
    p.meta.update(marker=marker,preserved_entities=True,registered_carts_unchanged=preserved_carts,
                  retained_approach_devices=[dict(position=q,type=str(t.get('id'))) for q,t in tags.items()],
                  foundation='Fill to measured bearing surface; retaining perimeter; no floating deck')
    p.save_plan('reception_aprons')
    if apply:
        p.apply('reception_aprons')
        (world/'un_air_reception_r40.json').write_text(json.dumps(marker,ensure_ascii=False,indent=2),encoding='utf8')
    print('Receiving-apron cells',len(changes),world,flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--world',type=Path,default=ROOT/'run/saves/SEELE_FIELD_R40_REVIEW');a.add_argument('--apply',action='store_true');args=a.parse_args();main(args.world,args.apply)

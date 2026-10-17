"""Clear measured obsolete well intrusions and improve the existing facade emblem."""
from pathlib import Path
import argparse, gzip, json, math, msvcrt
from collections import Counter
import numpy as np
import nbtlib
from PIL import Image
from scipy.ndimage import label, find_objects
import survey_r52_original_complex as survey
import plan_r53_old_well_enclosure as envelope
from query_blocks import read_box, iter_block_entities
from repair_r53_reported_landings import apply
from retire_r53_old_yashima_platform import packed
from apply_s20_approved_semantic_repairs import parse_state

DIM='projectseele:geofront'
PANEL='projectseele:nerv_pyramid_panel'
MARK='projectseele:nerv_pyramid_marking'

def protect_owner(world, value, cells, seen):
    if isinstance(value,dict):
        p=value.get('position')
        if isinstance(p,list) and len(p)==3:cells.add(tuple(p))
        name=value.get('cells_file')
        if name and name not in seen:
            seen.add(name);p=world/name
            raw=p.read_bytes();protect_owner(world,json.loads(gzip.decompress(raw) if name.endswith('.gz') else raw),cells,seen)
        for v in value.values():protect_owner(world,v,cells,seen)
    elif isinstance(value,list):
        for v in value:protect_owner(world,v,cells,seen)

def plan(world,base,out):
    lo=(-35,-466,-60);hi=(95,74,8)
    survey.WORLD=world;current,palette=survey.measure(lo,hi)
    survey.WORLD=base/'R50_RESTORE/server/SEELE_R50_WORLD';old,oldnames=survey.measure(lo,hi)
    envelope.LO=np.array(lo);envelope.HI=np.array(hi)
    core,_,_=envelope.envelopes(base.parent/'map_complete_20261013')
    protected=set();protect_owner(world,json.loads((world/'ROOT_MECHANICAL_OWNER.json').read_text('utf8')),protected,set())
    tags=dict(iter_block_entities(world,DIM,lo,hi));protected.update(tags)
    ids={s:i for i,s in enumerate(palette)};oldmap=np.array([ids.get(s,65535) for s in oldnames],np.uint16)
    # Only original obsolete architectural material inside the measured travel
    # volume; rail foundations, door proxies and all native devices are retained.
    architecture=np.array([s.startswith(('projectseele:nerv_shaft_panel','projectseele:nerv_structural_panel','projectseele:nerv_machine_edge','projectseele:nerv_wall_panel','projectseele:nerv_floor_panel','minecraft:stone_bricks','minecraft:polished_andesite','minecraft:polished_deepslate','minecraft:smooth_stone')) for s in palette])
    candidates=core&architecture[current]&(current==oldmap[old])
    rows=[]
    for y,z,x in np.argwhere(candidates):
        p=(int(x+lo[0]),int(y+lo[1]),int(z+lo[2]))
        if p in protected or 89<=p[0]<=120 and -447<=p[1]<=-437 and -64<=p[2]<=12:continue
        rows.append(dict(pos=p,before=palette[int(current[y,z,x])],after='minecraft:air',before_nbt=None,after_nbt=None,reason='obsolete_original_block_inside_active_travel_volume'))
    # Reuse the user's installed emblem, increasing voxel resolution to the complete above-water face.
    rgb=np.asarray(Image.open(base/'client/projectseele-local-maps/nerv_logo_r04.png').convert('RGB'))
    red=(rgb[:,:,0]>140)&(rgb[:,:,1]<90)&(rgb[:,:,2]<90);components,n=label(red);keep=np.zeros(red.shape,bool)
    for i,b in enumerate(find_objects(components),1):
        if b[0].stop-b[0].start>red.shape[0]*.1:keep|=components==i
    points=np.argwhere(keep);a=points.min(0);b=points.max(0)+1
    mask=Image.fromarray(keep[a[0]:b[0],a[1]:b[1]].astype('uint8')*255)
    h=41;w=round(h*mask.width/mask.height);mask=np.asarray(mask.resize((w,h),Image.Resampling.LANCZOS))>112
    top=-425;radius=lambda y:math.floor(120*(1-(y+559)/172)+.5)
    wanted={(30+int(c)-w//2,top-int(r),327+radius(top-int(r))) for r,c in np.argwhere(mask)}
    assert all(abs(x-30)<=radius(y)-2 for x,y,z in wanted)
    lo2=(-30,-531,345);hi2=(90,-415,430)
    cells=read_box(world,DIM,lo2,hi2);devices=dict(iter_block_entities(world,DIM,lo2,hi2))
    old_logo={p for p,s in cells.items() if s==MARK}
    for p in old_logo|wanted:
        before=cells[p];after=MARK if p in wanted else PANEL
        assert p not in devices and before in (PANEL,MARK),('Facade changed or device',p,before)
        if before!=after:rows.append(dict(pos=p,before=before,after=after,before_nbt=None,after_nbt=None,reason='clearer_existing_pyramid_emblem'))
    out.mkdir(parents=True,exist_ok=True)
    (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(),mtime=0))
    report=dict(changed_cells=len(rows),reasons=dict(Counter(r['reason'] for r in rows)),protected_cells=len(protected),old_logo_cells=len(old_logo),new_logo_cells=len(wanted),emblem_height=h,installed=False)
    (out/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report))

def install(world,out,generators_only=False):
    if not generators_only:apply(world,out)
    rows=json.loads(gzip.decompress((out/'EXACT_DELTA.json.gz').read_bytes()))
    with (world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        if generators_only:
            points=np.asarray([r['pos'] for r in rows]);cells=read_box(world,DIM,tuple(points.min(0)),tuple(points.max(0)))
            assert all(cells[tuple(r['pos'])]==r['after'] for r in rows),'Live edits have not been saved'
        data=world/'dimensions/projectseele/geofront/data'
        top=nbtlib.load(next(data.glob('projectseele_city_rigid_topology_r45_*.dat')))['data']
        folder=data/str(top['GenerationFolder'])/'chunks';groups={};count=0
        for r in rows:groups.setdefault((r['pos'][0]//16,r['pos'][2]//16),[]).append(r)
        for (x,z),batch in groups.items():
            p=folder/f'{x}_{z}.dat'
            if not p.exists():continue
            doc=nbtlib.load(p);entries={int(v['Pos']):v for v in doc['Static']};pal=doc['Palette'];ids={v.snbt():i for i,v in enumerate(pal)}
            for r in batch:
                cell=entries.get(packed(r['pos']))
                if cell is None:continue
                state=parse_state(r['after']);key=state.snbt()
                if key not in ids:ids[key]=len(pal);pal.append(state)
                cell['StateId']=nbtlib.Int(ids[key]);count+=1
            doc.save(p,gzipped=True)
        (out/'GENERATORS.json').write_text(json.dumps(dict(existing_owned_cells_updated=count)),'utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--apply',action='store_true');p.add_argument('--generators-only',action='store_true');a=p.parse_args()
    install(a.world,a.out,a.generators_only) if a.apply or a.generators_only else plan(a.world,a.base,a.out)

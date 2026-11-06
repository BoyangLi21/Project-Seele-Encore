"""Install the authored far mountain emplacement without restoring a world.

Only the three documented construction volumes, controls, and four new site
actors are copied. Current player, original fleet and campaign data are retained.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,copy,gzip,json,math,uuid,msvcrt
import nbtlib
from query_blocks import read_box,iter_block_entities
from repair_r53_reported_landings import apply as apply_cells
from transplant_s22_authority import read_region,parse_chunk,build_region,chunk_blob
from apply_s20_approved_semantic_repairs import atomic_replace

DIM='projectseele:geofront'
def uid(e):return str(uuid.UUID(''.join(f'{int(v)&0xffffffff:08x}' for v in e['UUID'])))
def route(points):
    out=[]
    for a,b in zip(points,points[1:]):
        steps=max(1,math.ceil(math.dist(a,b)/2))
        out.extend([[a[k]+(b[k]-a[k])*i/steps for k in range(3)] for i in range(steps)])
    return out+[points[-1]]

def plan(world,source,out):
    out.mkdir(parents=True,exist_ok=True)
    old_site=json.loads((source/'tv_encounter_sites_r45.json').read_text('utf8'))['sites']['ramiel']
    cannon=json.loads((source/'yashima_cannon_station_r52.json').read_text('utf8'))
    current=json.loads((world/'tv_encounter_sites_r45.json').read_text('utf8'))
    site=copy.deepcopy(old_site);site['id']='r53/hakone_ground_exit_yashima'
    site['yashima_controls']['recovery_storage']=current['sites']['ramiel']['yashima_controls']['recovery_storage']
    site['departure']='hakone';site['native_verified']=False;site['user_accepted']=False
    # The shield's waiting point must clear the cannon line. Reuse the
    # existing founded shoulder, 31 metres before its defence endpoint.
    shield_route=site['cover_after_supply_route']
    if math.dist(site['shield_wait_port'],site['cover'])<1:
        side=max(i for i,p in enumerate(shield_route) if math.dist(p,site['cover'])>=31)
        site['shield_wait_port']=shield_route[side]
        site['cover_after_supply_route']=shield_route[:side+1]
    ids={cannon[k] for k in ('cannon_uuid','hatch_uuid','source_rack_uuid','source_weapon_uuid')}
    ids|={r[k] for r in site['yashima_controls']['supply_racks'] for k in ('uuid','cargo_uuid')}
    mapping={s:str(uuid.uuid5(uuid.NAMESPACE_URL,'projectseele:r53:hakone:'+s)) for s in ids}
    def remap(data):
        s=json.dumps(data,ensure_ascii=False)
        for a,b in mapping.items():s=s.replace(a,b)
        return json.loads(s)
    cannon=remap(cannon);site=remap(site)
    for unit,start in [('0',[-1130,175,-1520.724]),('1',[-1250,175,-1520.724])]:
        landing=site['landings'][unit]['point'];site['landings'][unit]['point']=start
        prefix=route([start,[start[0],175,-1488.5],[landing[0],175,-1488.5],landing])
        site['eva_access_routes'][unit]=prefix[:-1]+site['eva_access_routes'][unit]
    cannon['eva_access_route']=site['eva_access_routes']['1']
    cannon['id']='root_hakone_fixed_cannon_r53';cannon['installation_pending']='native commissioning'
    current['sites']['ramiel']=site
    boxes=[((-1279,157,-1429),(-1224,180,-1366),'authored_fixed_cannon_pit'),
           ((-1315,111,-1383),(-1297,189,-1359),'authored_magazine_and_power'),
           ((-1206,171,-1457),(-1171,175,-1422),'authored_shield_foundation')]
    cells={};tags={};wanted={};newtags={};reason={}
    for lo,hi,label in boxes:
        src=read_box(source,DIM,lo,hi);dst=read_box(world,DIM,lo,hi)
        st=dict(iter_block_entities(source,DIM,lo,hi));dt=dict(iter_block_entities(world,DIM,lo,hi))
        cells.update(dst);tags.update(dt)
        for p,after in src.items():
            before=dst[p]
            assert p not in dt or (p in st and dt[p].snbt()==st[p].snbt()),('Existing unrelated device',p)
            wanted[p]=after;reason[p]=label;newtags[p]=st.get(p)
    # Native floor-level button for the original cannon lift.
    for p,state in [((-1302,175,-1374),'minecraft:stone_button[face=floor,facing=north,powered=false]')]:
        if p not in cells:cells.update(read_box(world,DIM,p,p))
        wanted[p]=state;reason[p]='cannon_lift_input';newtags[p]=None
    # Inspect the complete thirteen-metre foot corridor, not just route centres.
    lo=(-1340,171,-1530);hi=(-1118,190,-1349)
    terrain=read_box(world,DIM,lo,hi);devices=dict(iter_block_entities(world,DIM,lo,hi))
    cells.update(terrain);tags.update(devices)
    owner=json.loads((world/'ROOT_MECHANICAL_OWNER.json').read_text('utf8'))
    hatch_columns=set()
    for gate in owner['gates']:
        if gate['resource'] not in ('bank_3_surface_lane_1','bank_3_surface_lane_2'):continue
        supports=[s['position'] for s in gate['supports']]
        for xx in range(min(p[0] for p in supports)-1,max(p[0] for p in supports)+2):
            for zz in range(min(p[2] for p in supports)-1,max(p[2] for p in supports)+2):
                hatch_columns.add((xx,zz))
    natural={'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:air','minecraft:cave_air'}
    for unit in ('0','1'):
        points=site['eva_access_routes'][unit]
        for point in points:
            x,z=math.floor(point[0]),math.floor(point[2])
            for xx in range(x-6,x+7):
                for zz in range(z-6,z+7):
                    if (xx,zz) in hatch_columns or any(a[0]<=xx<=b[0] and a[2]<=zz<=b[2] for a,b,_ in boxes):continue
                    p=(xx,174,zz)
                    before=wanted.get(p,cells.get(p))
                    if before is None:raise ValueError(('Corridor outside survey',p))
                    if before in ('minecraft:air','minecraft:cave_air','minecraft:water'):
                        for y in range(171,175):
                            q=(xx,y,zz);assert q not in tags
                            existing=wanted.get(q,cells[q])
                            assert existing.split('[')[0] in natural|{'minecraft:water'},('Existing corridor structure',q,existing)
                            wanted[q]='minecraft:grass_block[snowy=false]' if y==174 else 'minecraft:dirt' if y>=172 else 'minecraft:stone'
                            reason[q]='hakone_exit_ground_approach';newtags[q]=None
    rows=[]
    for p,after in wanted.items():
        a=tags.get(p);b=newtags.get(p,a);sa=None if a is None else a.snbt();sb=None if b is None else b.snbt()
        if cells[p]!=after or sa!=sb:rows.append(dict(pos=p,before=cells[p],after=after,before_nbt=sa,after_nbt=sb,reason=reason[p]))
    actors=[]
    for f in (source/'dimensions/projectseele/geofront/entities').glob('r.-3.-3.mca'):
        _,blobs=read_region(f)
        for blob in blobs:
            if not blob:continue
            for e in parse_chunk(blob).get('Entities',[]):
                old=uid(e)
                if old not in ids:continue
                e=copy.deepcopy(e);new=uuid.UUID(mapping[old]);e['UUID']=nbtlib.IntArray([v if v<2**31 else v-2**32 for v in [(new.int>>s)&0xffffffff for s in (96,64,32,0)]])
                def remap_uuid_tags(tag):
                    if isinstance(tag,nbtlib.IntArray) and len(tag)==4:
                        value=str(uuid.UUID(''.join(f'{int(v)&0xffffffff:08x}' for v in tag)))
                        if value in mapping:
                            u=uuid.UUID(mapping[value]).int
                            return nbtlib.IntArray([v if v<2**31 else v-2**32 for v in [(u>>s)&0xffffffff for s in (96,64,32,0)]])
                    if isinstance(tag,nbtlib.Compound):
                        for k in list(tag):tag[k]=remap_uuid_tags(tag[k])
                    elif isinstance(tag,nbtlib.List):
                        for k in range(len(tag)):tag[k]=remap_uuid_tags(tag[k])
                    return tag
                e=remap_uuid_tags(e);raw=e.snbt()
                for a,b in mapping.items():raw=raw.replace(a,b)
                e=nbtlib.parse_nbt(raw)
                if 'ForgeData' in e:
                    e['ForgeData'].pop('StationLayoutR52',None)
                if str(e['id'])=='projectseele:nerv_armament_station':
                    row=next(r for r in site['yashima_controls']['supply_racks'] if r['uuid']==uid(e))
                    def uuid_tag(value):
                        u=uuid.UUID(value).int
                        return nbtlib.IntArray([v if v<2**31 else v-2**32 for v in [(u>>s)&0xffffffff for s in (96,64,32,0)]])
                    e['ForgeData']['TvMissionDeclaredRackR53']=uuid_tag(row['uuid'])
                    e['ForgeData']['TvMissionDeclaredCargoR53']=uuid_tag(row['cargo_uuid'])
                if str(e['id'])=='projectseele:nerv_silo_door':
                    e.setdefault('ForgeData',nbtlib.Compound())['CannonProxyBoxR53']=nbtlib.IntArray([-1271,174,-1424,-1233,174,-1372])
                actors.append(e.snbt())
    assert len(actors)==4,len(actors)
    (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows,ensure_ascii=False).encode('utf8'),mtime=0))
    for name,data in [('tv_encounter_sites_r45.json',current),('yashima_cannon_station_r52.json',cannon),('new_site_actors.json',actors)]:
        (out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    (out/'PLAN.json').write_text(json.dumps(dict(world=str(world),cells=len(rows),reasons=dict(Counter(r['reason'] for r in rows)),new_actors=4,installed=False),indent=2),'utf8')
    print('Hakone new construction:',len(rows),'cells; four new site actors; current campaign/fleet untouched')

def apply(world,out):
    actors=[nbtlib.parse_nbt(s) for s in json.loads((out/'new_site_actors.json').read_text('utf8'))]
    path=world/'dimensions/projectseele/geofront/entities/r.-3.-3.mca'
    stamps,blobs=read_region(path);existing=set()
    for b in blobs:
        if b:
            for e in parse_chunk(b).get('Entities',[]):existing.add(uid(e))
    assert not existing.intersection(uid(e) for e in actors),'New site already installed'
    apply_cells(world,out)
    with (world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        for e in actors:
            cx=math.floor(float(e['Pos'][0]))>>4;cz=math.floor(float(e['Pos'][2]))>>4;slot=(cx&31)+32*(cz&31)
            doc=parse_chunk(blobs[slot]) if blobs[slot] else nbtlib.File({'DataVersion':nbtlib.Int(3465),'Position':nbtlib.IntArray([cx,cz]),'Entities':nbtlib.List[nbtlib.Compound]()})
            doc['Entities'].append(e);blobs[slot]=chunk_blob(doc)
        atomic_replace(path,build_region(stamps,blobs))
        for name in ('tv_encounter_sites_r45.json','yashima_cannon_station_r52.json'):
            atomic_replace(world/name,(out/name).read_bytes())
    report=json.loads((out/'PLAN.json').read_text());report['installed']=True
    (out/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    print('Installed new Hakone site into current save')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--apply',action='store_true');a=ap.parse_args()
    if a.apply:apply(a.world,a.out)
    else:plan(a.world,a.source,a.out)

"""Measured, reversible UN wet-cell expansion on the explicitly authorized R31 copy."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import msvcrt
import numpy as np
import nbtlib
import regional_voxels as vox
import scan_regional_completion as scan
from query_blocks import iter_block_entities

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / 'run/saves/SEELE_FIELD_R31_REVIEW'
OUT = ROOT / 'artifacts/facility_r31/un_hangars'
AIR = 'minecraft:air'
FLOOR = 'projectseele:nerv_floor_panel'
WALL = 'projectseele:nerv_wall_panel'
STRUCTURE = 'projectseele:nerv_structural_panel'
EDGE = 'projectseele:nerv_machine_edge'
BAR_NS = 'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]'
BAR_EW = 'minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def phase(serial):
    name = 'projectseele_military_r07' if serial == 0 else 'projectseele_un01_annex_r20'
    data = nbtlib.load(WORLD / 'dimensions/projectseele/geofront/data' / (name + '.dat'))['data']
    value = str(data['Phase'])
    assert value in ('WET', 'DRY', 'OPEN'), ('Freeze completed mechanism phase before expansion', value)
    return value

def author(serial, painter):
    cx = 6442 - 160 * serial
    lo, hi = (cx-66,70,-6292), (cx+66,164,-6104)
    before, palette = scan.volume(lo, hi)
    after = before.copy()
    lookup = {s:i for i,s in enumerate(palette)}
    def code(state):
        if state not in lookup:
            lookup[state] = len(palette); palette.append(state)
        return lookup[state]
    def index(box):
        x0,y0,z0,x1,y1,z1 = box
        assert lo[0] <= x0 <= x1 <= hi[0] and lo[1] <= y0 <= y1 <= hi[1] and lo[2] <= z0 <= z1 <= hi[2], box
        return (slice(y0-lo[1],y1-lo[1]+1),slice(z0-lo[2],z1-lo[2]+1),slice(x0-lo[0],x1-lo[0]+1))
    def fill(box, state):
        after[index(box)] = code(state)
    def copy_box(source, dx, nonair=False, preserve_control=False):
        target = tuple(v+dx if i in (0,3) else v for i,v in enumerate(source))
        src = before[index(source)]
        dst = after[index(target)]
        mask = np.ones(src.shape,dtype=bool)
        if nonair: mask &= np.asarray([not s.startswith(('minecraft:air','minecraft:cave_air','minecraft:void_air')) for s in palette])[src]
        if preserve_control:
            xs=np.arange(target[0],target[3]+1)[None,None,:]
            ys=np.arange(target[1],target[4]+1)[:,None,None]
            zs=np.arange(target[2],target[5]+1)[None,:,None]
            mask &= ~((xs>=cx-54)&(xs<=cx-26)&(ys<=83)&(zs>=-6156)&(zs<=-6140))
        dst[mask] = src[mask]

    stage = phase(serial)
    # Measured outer wall/column strips move outward 8 m. Extend the whole slab,
    # foundation, roof and transverse trusses; the campus road remains untouched.
    for side in (-1,1):
        old0,old1 = sorted((cx+side*57,cx+side*58))
        new0,new1 = sorted((cx+side*59,cx+side*66))
        fill((new0,73,-6288,new1,75,-6136),STRUCTURE)
        fill((new0,76,-6288,new1,76,-6136),FLOOR)
        fill((new0,160,-6288,new1,160,-6136),'minecraft:gray_concrete')
        for z in (-6288,-6136):fill((new0,77,z,new1,159,z),WALL)
        fill((old0,77,-6287,old1,159,-6137),AIR)
        copy_box((old0,77,-6288,old1,159,-6136),side*8)
        for z in range(-6276,-6145,24):
            xa,xb=sorted((cx+side*56,cx+side*65))
            fill((xa,155,z,xb,157,z+1),'minecraft:gray_concrete')
        # A grounded exterior edge closes the extended foundation to the apron.
        fill((new0,73,-6135,new1,75,-6128),STRUCTURE)
        fill((new0,76,-6135,new1,76,-6128),FLOOR)

    for side in (-1,1):
        old0,old1=sorted((cx+side*17,cx+side*23))
        # Remove only the measured old tank wall / inner service strip. The rear
        # gallery remains as a wider junction to the untouched personnel stair.
        fill((old0,77,-6227,old1,141,-6137),AIR)
        copy_box((old0,77,-6252,old1,141,-6142),side*8,nonair=True,preserve_control=True)
        # Keep the original control room intact. Its roof carries this one post.
        if side<0:
            fill((cx-31,84,-6148,cx-31,132,-6148),'minecraft:gray_concrete')
            fill((cx-31,84,-6148,cx-26,84,-6148),EDGE)
        x=cx+side*25
        # Copy the full measured pressure wall, including its existing boarding
        # portal and window rhythm, not just the part alongside the gallery.
        copy_box((cx+side*17,77,-6227,cx+side*17,141,-6137),side*8,nonair=False)
        # Extend the boarding gallery to the relocated walls. Preserve the exact
        # central plug opening / setback from R29 rather than filling it in.
        xa,xb=sorted((cx+side*17,cx+side*24))
        fill((xa,126,-6226,xb,126,-6214),FLOOR)
        fill((xa,127,-6226,xb,127,-6226),BAR_EW)
        fill((xa,127,-6214,xb,127,-6214),BAR_EW)
        fill((x,126,-6220,x,126,-6215),FLOOR)
        fill((x,127,-6219,x,130,-6216),AIR)
        fill((x,131,-6220,x,131,-6215),'minecraft:iron_block')
        # Old gallery lamps inside the new machine envelope must not hover.
        fill((old0,131,-6228,old1,134,-6137),AIR)
        # Restore the central boarding portal's measured header at the new wall.
        fill((x,131,-6220,x,131,-6215),'minecraft:iron_block')

    fill((cx-24,77,-6227,cx+24,141,-6227),'minecraft:gray_concrete')
    fill((cx-24,77,-6226,cx+24,120,-6137),'projectseele:lcl[level=0]' if stage=='WET' else AIR)
    # The new front opening is continuous from the floor to Y141, preserving the
    # current open/closed state instead of resetting either player's machine.
    fill((cx-24,77,-6136,cx+24,141,-6136),AIR if stage=='OPEN' else 'minecraft:barrier')
    # Four vertical door leaves telescope into an enclosed top cassette. The
    # cassette is outside personnel routes and below the unchanged Y160 roof.
    fill((cx-25,142,-6137,cx+25,159,-6134),AIR)
    fill((cx-27,142,-6133,cx+27,159,-6133),WALL)
    fill((cx-27,160,-6137,cx+27,160,-6133),'minecraft:gray_concrete')
    for x in (cx-27,cx+27):fill((x,142,-6137,x,159,-6133),STRUCTURE)
    for x in (cx-26,cx+26):
        fill((x,77,-6136,x,159,-6136),EDGE)
        fill((x,144,-6133,x,144,-6133),'projectseele:nerv_warning_beacon[lit=false]')
    # Retire the old lamps embedded in the previous door header.
    for x in (cx-19,cx+19):
        pos=(x,144,-6136,x,144,-6136)
        if 'warning_beacon' in palette[int(before[index(pos)].item())]:fill(pos,AIR)
    # Keep the pressure floor supported and mark the widened floor lanes without
    # placing any railings or signs inside the machine's travel envelope.
    # Widening incorporates the old personnel belt into the wet cell. Retire
    # its complete floor assembly; painting only the left half left 26 broken
    # MTR pairs and encouraged a later repair to cut the pressure rear wall.
    wet_floor=index((cx-24,76,-6239,cx+24,76,-6137))
    retired_steps=np.asarray([s.startswith('mtr:escalator_step[') for s in palette])[before[wet_floor]]
    retained=after[wet_floor];retired_count=int(retired_steps.sum());retained[retired_steps]=code(FLOOR)
    for x in (cx-24,cx+24):
        for z in range(-6223,-6137,8):fill((x,76,z,x,76,min(z+3,-6137)),'minecraft:yellow_terracotta')
    # The UN-01 copied apron had a knee-high rail across its named staff entry.
    fill((cx-42,77,-6133,cx-38,79,-6133),AIR)

    # Every changed coordinate is exact-state match authored from query_blocks.
    diff=before!=after
    be=list(iter_block_entities(WORLD,vox.DIM,lo,hi))
    for pos,tag in be:
        at=(pos[1]-lo[1],pos[2]-lo[2],pos[0]-lo[0])
        assert not diff[at], ('Protected block entity',pos,str(tag.get('id')))
    owner=f'r31/un{serial:02d}/measured_full_hangar_widening'
    for yy,zz in np.argwhere(diff.any(axis=2)):
        xs=np.flatnonzero(diff[yy,zz]);start=previous=int(xs[0]);old=int(before[yy,zz,start]);new=int(after[yy,zz,start])
        def row(a,b,o,n):
            painter.match((a+lo[0],int(yy)+lo[1],int(zz)+lo[2],b+lo[0],int(yy)+lo[1],int(zz)+lo[2]),palette[o],palette[n],owner)
        for xx in xs[1:]:
            xx=int(xx);o=int(before[yy,zz,xx]);n=int(after[yy,zz,xx])
            if xx==previous+1 and o==old and n==new:previous=xx
            else:row(start,previous,old,new);start=previous=xx;old=o;new=n
        row(start,previous,old,new)
    np.savez_compressed(OUT/f'planned_un{serial}.npz',before=before,after=after,palette=np.asarray(palette),lo=lo,hi=hi)
    return dict(serial=serial,centre=cx,phase_preserved=stage,bounds=[lo,hi],changed_cells=int(diff.sum()),
                old_outer_width=117,new_outer_width=133,old_pressure_width=33,new_pressure_width=49,
                wet_min=[cx-24,77,-6226],wet_max=[cx+24,120,-6137],door=[cx+.5,77,-6135.5],
                door_width=49,door_height=65,top_cassette=[cx-27,142,-6137,cx+27,160,-6133],
                block_entities_preserved=len(be),retired_pressure_floor_step_cells=retired_count,home=[cx+.5,77,-6205.5])

def main(apply=False):
    assert WORLD.name=='SEELE_FIELD_R31_REVIEW'
    if (WORLD/'un_hangars_r31.json').exists():
        raise RuntimeError('R31 geometry is already installed; use the exact receipt for rollback, never re-author a migrated shell.')
    OUT.mkdir(parents=True,exist_ok=True)
    vox.WORLD=scan.WORLD=WORLD;vox.OUT=scan.OUT=OUT
    painter=vox.Painter();rows=[author(s,painter) for s in (0,1)]
    routes=[]
    for s,cx in ((0,6442),(1,6282)):
        routes.extend([
            dict(id=f'r31/un{s:02d}/staff_entry',path=[[cx-40+.5,77,-6132.5],[cx-40+.5,77,-6138.5],[cx-56+.5,77,-6138.5],[cx-56+.5,77,-6239.5],[cx+38+.5,77,-6239.5]]),
            dict(id=f'r31/un{s:02d}/upper_east_gallery',path=[[cx+38+.5,127,-6249.5],[cx+28+.5,127,-6249.5],[cx+28+.5,127,-6217.5],[cx+4+.5,127,-6217.5]]),
            dict(id=f'r31/un{s:02d}/upper_west_gallery',path=[[cx+28+.5,127,-6249.5],[cx+28+.5,127,-6217.5],[cx+8+.5,127,-6217.5],[cx+8+.5,127,-6224.5],[cx-8+.5,127,-6224.5],[cx-8+.5,127,-6217.5],[cx-28+.5,127,-6217.5],[cx-28+.5,127,-6143.5]]),
            dict(id=f'r31/un{s:02d}/door_centre_open',path=[[cx+.5,77,-6150.5],[cx+.5,77,-6128.5]],runtime_only='drain_and_open_gate'),
        ])
    full_routes={}
    for serial,cx in ((0,6442),(1,6282)):
        path=copy.deepcopy(routes[serial*4]['path'])
        path.extend([[cx+38+.5,77,-6248.5],[cx+34+.5,77,-6248.5]])
        for i in range(5):
            y=77+i*10
            path.extend([[cx+34+.5,y,-6248.5],[cx+34+.5,y+5,-6255.5],
                         [cx+40+.5,y+5,-6255.5],[cx+40+.5,y+10,-6248.5]])
        path.extend(copy.deepcopy(routes[serial*4+1]['path']))
        full_routes[serial]=path
        routes.append(dict(id=f'r31/un{serial:02d}/staff_to_plug',path=path))
        routes.append(dict(id=f'r31/un{serial:02d}/staff_to_plug/return',path=path[::-1]))
    painter.meta.update(authorization='User requested both UN hangars wider; measured R31 review copy only',hangars=rows,
                        preserved=['original units and capsules','staff identities and posts','control rooms and buttons','MTR files','personnel stair tower','central plug opening'],walk_cases=routes)
    (OUT/'walk_cases.json').write_text(json.dumps(routes,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'geometry.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
    if not apply:
        painter.save_plan('widening');return
    protected={p:sha(WORLD/p) for p in ('nerv_staff_r15.json','un01_annex_r20.json','r07_installations.json')}
    lock_path=WORLD/'session.lock'
    if not lock_path.exists():
        with lock_path.open('xb') as empty_lock:empty_lock.write(bytes((0xe2,0x98,0x83)))
    with (WORLD/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        receipt=painter.apply('widening',session_lock=lock)
        assert all(sha(WORLD/p)==h for p,h in protected.items())
        marker=WORLD/'un_hangars_r31.json';assert not marker.exists()
        marker.write_text(json.dumps(dict(schema='projectseele.un-hangars-r31.v1',revision=31,hangars=rows),ensure_ascii=False,indent=2),encoding='utf8')
        catalog_path=WORLD/'quality_walk_cases.json';catalog_before=catalog_path.read_bytes()
        (OUT/'quality_walk_cases.before.json').write_bytes(catalog_before)
        catalog=json.loads(catalog_before);ids={row['id'] for row in catalog}
        for row in catalog:
            if row['id']=='r07/secret/gantry':row['path']=copy.deepcopy(routes[1]['path'])
            elif row['id']=='r07/secret/gantry/return':row['path']=copy.deepcopy(routes[1]['path'][::-1])
            elif row['id']=='r07/secret/continuous_staff_to_plug':row['path']=copy.deepcopy(full_routes[0])
            elif row['id']=='r07/secret/continuous_staff_to_plug/return':row['path']=copy.deepcopy(full_routes[0][::-1])
        catalog.extend(row for row in routes if row['id'] not in ids)
        catalog_path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf8')
        (OUT/'quality_walk_cases.after.json').write_bytes(catalog_path.read_bytes())
        (OUT/'installed.json').write_text(json.dumps(dict(receipt=receipt,marker=str(marker),metadata_preserved=protected,
             catalog_before_sha256=hashlib.sha256(catalog_before).hexdigest(),catalog_after_sha256=sha(catalog_path),
             catalog_rows=len(catalog)),ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');main(parser.parse_args().apply)

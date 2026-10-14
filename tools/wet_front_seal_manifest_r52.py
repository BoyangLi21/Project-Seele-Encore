"""Bounded actual three-bay seal metadata shared by final delivery readers.

No World writes or geometry/native PASS. Native side bearings are derived
from the same selected Spec as NervWetFloorSealR52's published wall plates.
"""
import gzip, hashlib, itertools, json, math
from pathlib import Path, PurePosixPath

def need(p,s):
    if not p:raise ValueError(s)

def phase_rows(gate,parent):
    value=gate['collision_steps']
    if isinstance(value,list):return value
    name=value['cells_file'];rel=PurePosixPath(name);parent=Path(parent).resolve()
    need(name and not rel.is_absolute() and ':' not in name and '\\' not in name and all(p not in ('','.','..') for p in name.split('/')),'Bounded actual gate table path required')
    path=(parent/name).resolve();need(path.is_relative_to(parent) and path.is_file(),'Actual gate table absent/outside selected source')
    need(path.stat().st_size<=32_000_000,'Compressed actual gate table exceeds32MB bound')
    raw=path.read_bytes();need(hashlib.sha256(raw).hexdigest()==value['sha256'],'Actual gate table SHA differs')
    with gzip.GzipFile(fileobj=__import__('io').BytesIO(raw)) as stream:decoded=stream.read(32_000_001)
    need(len(decoded)<=32_000_000,'Actual gate table exceeds32MB decoded bound')
    rows=json.loads(decoded);need(isinstance(rows,list),'Actual gate phase array required');return rows

def transform(frame,p,vector=False):
    q=frame['quaternion'];need(len(q)==4 and all(math.isfinite(x) for x in q) and abs(sum(x*x for x in q)-1)<1e-6,'Actual normalized gate quaternion required')
    x,y,z,w=q;a,b,c=p
    result=[(1-2*y*y-2*z*z)*a+(2*x*y-2*z*w)*b+(2*x*z+2*y*w)*c,
            (2*x*y+2*z*w)*a+(1-2*x*x-2*z*z)*b+(2*y*z-2*x*w)*c,
            (2*x*z-2*y*w)*a+(2*y*z+2*x*w)*b+(1-2*x*x-2*y*y)*c]
    return result if vector else [result[k]+frame['position'][k] for k in range(3)]

def sealed_front_specs(gates,require_complete=True):
    wanted={f'bay_{i}_front' for i in range(3)};result={}
    for g in gates:
        f=g.get('hangar_stack',{}).get('floor_seal')
        if f is None:
            need('floor_seal_original_cells' not in g,'Original seal-cell trace requires its actual physical Spec')
            continue
        need(g['kind']=='HANGAR' and g['resource']==f"bay_{g['variant']}_front" and g['resource'] in wanted,'Wet-floor seal belongs only to its original three bay fronts')
        need(g['resource'] not in result,'Duplicate sealed front resource')
        version=f.get('version',1);retained=f.get('retained_box_count',0)
        need(type(version) is int and version in (1,2),'Actual supported floor-seal version required')
        rows=f.get('closed_boxes');need(isinstance(rows,list) and 1<=len(rows)<=(64 if version==1 else 512),'Actual finite seal boxes required')
        need({'closed_boxes','drop_m','retreat_local_z_m'}<=set(f) and set(f)<={'closed_boxes','drop_m','retreat_local_z_m','version','retained_box_count'},'Unknown actual seal Spec fields')
        need((version==1 and retained==0) or (version==2 and type(retained) is int and 0<retained<len(rows) and retained<=64),'Explicit retained original floor mechanism required')
        for key,maximum in [('drop_m',6),('retreat_local_z_m',32)]:need(type(f[key]) in (int,float) and math.isfinite(f[key]) and 0<f[key]<=maximum,'Bounded actual seal travel required')
        cells=set()
        for box in rows:
            need(len(box)==6 and all(type(x) in (int,float) and math.isfinite(x) for x in box) and all(box[k]<box[k+3] for k in range(3)),'Finite ordered actual seal box required')
            corners=[transform(g['frame'],p) for p in itertools.product(*[(box[k],box[k+3]) for k in range(3)])]
            lo=[math.floor(min(p[k] for p in corners)+1e-6) for k in range(3)]
            hi=[math.floor(max(p[k] for p in corners)-1e-6) for k in range(3)]
            counts=[hi[k]-lo[k]+1 for k in range(3)];need(all(0<n<=256 for n in counts) and math.prod(counts)<=256,'Actual seal voxel budget exceeded')
            cells.update(itertools.product(*(range(lo[k],hi[k]+1) for k in range(3))))
        need(0<len(cells)<=512,'Actual complete bounded floor-cell union required')
        if version==2:need('floor_seal_original_cells' in g,'Expanded floor requires its exact original-cell trace')
        if 'floor_seal_original_cells' in g:need(len(g['floor_seal_original_cells'])==len(cells) and {tuple(p) for p in g['floor_seal_original_cells']}==cells,'Original floor-seal trace must equal the complete actual factory-cell union')
        need(not cells&{tuple(c['position']) for c in g['supports']},'Moving seal cannot retire its fixed support')
        legacy_rows=rows[:retained] if version==2 else rows
        b=[min(row[k] for row in legacy_rows) for k in range(3)]+[max(row[k+3] for row in legacy_rows) for k in range(3)]
        side=-1 if (b[0]+b[3])/2<0 else 1
        start=b[2]-.35;end=b[5]+f['retreat_local_z_m']+.35;count=math.ceil((end-start)/6)
        bearings=[]
        for j in range(count+1):
            # Actual end_wall_return/0 joins the first tie to its relocated
            # wall plate; it must not reuse the withdrawn pit-intersecting seat.
            seat_z=b[2]+3.5 if j==0 else start+(end-start)*j/count
            p=transform(g['frame'],[side*g['width']/2,b[1]-f['drop_m']-.66,seat_z])
            normal=transform(g['frame'],[-side,0,0],True);normal=[round(x) if abs(x-round(x))<1e-6 else x for x in normal]
            need(sum(abs(x) for x in normal)==1 and sum(x*x for x in normal)==1,'Actual native wall face must stay axis-aligned')
            at=[math.floor(p[k]-normal[k]*.001) for k in range(3)]
            bearings.append(dict(resource=g['resource'],bearing=p,normal=normal,at=at,contact_half_width_m=.10))
        if version==2:
            extra=rows[retained:];e=[min(row[k] for row in extra) for k in range(3)]+[max(row[k+3] for row in extra) for k in range(3)]
            need((b[0]+b[3])/2<0 and e[3]>0 and e[0]>=-g['width']/2 and e[3]<=g['width']/2 and e[5]-e[2]<=12 and e[1]==b[1],'Actual opposite-side extension geometry differs')
            start=e[2]+.1 if e[5]-e[2]>4 else e[2]-.35;end=e[5]+f['retreat_local_z_m']+.35;count=math.ceil((end-start)/6)
            for j in range(count+1):
                seat_z=e[2]+3.5 if e[5]-e[2]>4 and j==0 else start+(end-start)*j/count
                p=transform(g['frame'],[g['width']/2,e[1]-f['drop_m']-.66,seat_z]);normal=transform(g['frame'],[-1,0,0],True);normal=[round(x) if abs(x-round(x))<1e-6 else x for x in normal]
                at=[math.floor(p[k]-normal[k]*.001) for k in range(3)];bearings.append(dict(resource=g['resource'],bearing=p,normal=normal,at=at,contact_half_width_m=.10))
        result[g['resource']]=dict(gate=g,cells=cells,wall_bearings=bearings)
    if require_complete:
        need(set(result)==wanted,'Final continuous delivery requires all three real bay-front floor seals; old gate table is not complete')
        need(all(0<len(s['wall_bearings'])<=128 for s in result.values()),'All actual finite native wall plates required')
        for s in result.values():
            supports={tuple(c['position']):c['state'] for c in s['gate']['supports']}
            for a in s['wall_bearings']:need(tuple(a['at']) in supports and supports[tuple(a['at'])] not in ('minecraft:air','minecraft:cave_air','minecraft:void_air'),'Actual seal wall plate must have a declared native support at '+str(a['at']))
    return result

def validate_seal_phase_tables(gates,table_reader,require_complete=True):
    seals=sealed_front_specs(gates,require_complete);allcells=set()
    for name,seal in seals.items():
        rows=table_reader(seal['gate']);index={}
        for row in rows:
            for c in row:
                p=tuple(c['position']);need(p not in index,'Duplicate actual moving gate cell');index[p]=c
        for p in seal['cells']:
            c=index.get(p);need(c and c['closed'].split('[')[0] in ('projectseele:nerv_floor_panel','projectseele:nerv_machine_hazard','projectseele:nerv_machine_panel','projectseele:nerv_machine_edge','minecraft:polished_basalt','minecraft:cut_copper','minecraft:exposed_cut_copper','minecraft:iron_block','minecraft:polished_blackstone','minecraft:sea_lantern') and c['open']=='minecraft:air','Complete actual floor_panel/air phase table missing at '+str(p))
        need(not allcells&seal['cells'],'Shared physical seal floor cell');allcells.update(seal['cells'])
    if require_complete:need(0<len(allcells)<=1536,'Complete bounded non-overlapping original floor seals required')
    return seals

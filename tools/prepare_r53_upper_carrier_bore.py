"""Prepare, never apply, an exact reversible current upper-carrier bore patch.

Uses the existing continuous Bezier/height-band engineering envelope. The
positive mask requires either a current unchanged authored lining receipt or
natural fill within five metres of that lining in the declared nine bores.
No entity, route, support, gate, block entity, or navigation data is written.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import zipfile
import numpy as np
from scipy.spatial import cKDTree
from build_current_launch_height_hulls import clipped, bands
from measure_upright_bores_r52 import make_parts
from plan_bank3_exact_geometry_r52 import contains
from query_blocks import iter_selected_sections, iter_block_entities
from prepare_continuous_upright_civil_r52 import xyz_for

AIR = {'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'}
LINING = {'projectseele:nerv_shaft_panel', 'projectseele:nerv_machine_edge',
          'projectseele:nerv_strip_light[lit=true]'}
NATURAL = {'minecraft:stone', 'minecraft:deepslate', 'minecraft:deepslate[axis=y]',
           'minecraft:bedrock', 'minecraft:gravel', 'minecraft:andesite',
           'minecraft:diorite', 'minecraft:granite', 'minecraft:tuff',
           'minecraft:coal_ore', 'minecraft:iron_ore', 'minecraft:copper_ore',
           'minecraft:deepslate_coal_ore', 'minecraft:deepslate_iron_ore',
           'minecraft:deepslate_copper_ore'}
KNOWN = (57, -888, -23)


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def dump(path, obj):
    data = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf8')
    if str(path).endswith('.gz'):
        data = gzip.compress(data, mtime=0)
    Path(path).write_bytes(data)


def slot(p):
    x,y,z = map(int,p)
    return (x//16,z//16,y//16),(y%16)*256+(z%16)*16+x%16


def positioned_rows(value):
    if isinstance(value, dict):
        if 'position' in value and isinstance(value['position'], list) and len(value['position']) == 3:
            yield value['position']
        for v in value.values():
            yield from positioned_rows(v)
    elif isinstance(value, list):
        for v in value:
            yield from positioned_rows(v)


def inherited_protection(x,y,z):
    return (((y>=-410)&(x>=-54)&(x<=110)&(z>=-58)&(z<=-15))
        |((x>=-90)&(x<=150)&(z>=207)&(z<=447)&(y>=-563)&(y<=-384))
        |((x>=-54)&(x<=108)&(z>=280)&(z<=375)&(y>=-1136)&(y<=-930))
        |((y<-956)&(x>=-54)&(x<=108)&(z>=9)&(z<=148))
        |((y>=-490)&(z>=-190)&(z<=-55)&(x>=-54)&(x<=110))
        |((x>=89)&(z>=-56)&(z<=-46))
        |((x>=-31)&(x<=91)&(y>=-444)&(y<=-411)&(z>=-16)&(z<=-6)))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('world','jar','author_base','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--workers',type=int,default=4)
    a=p.parse_args();w=a.world.resolve();out=a.output.resolve()
    assert not out.is_relative_to(w) and not out.exists(), 'Fresh output outside the world required'
    out.mkdir(parents=True)
    directory=read(w/'ROOT_RUNTIME_DIRECTORY.json');owner=read(w/'ROOT_MECHANICAL_OWNER.json')
    contract=read(a.author_base/'ROOT_SPATIAL_PLAN.json')
    assert contract['epoch']==53 and contract['map_author']=='root' and contract['delivery_scope']['id']=='scope124'
    legs=[v for v in directory['legs'] if v['id'].endswith('/upright_continuous')]
    assert len(legs)==9 and all(v['eva_from_xyzw']==[0,1,0,0] and v['eva_to_xyzw']==[0,1,0,0] for v in legs)
    with zipfile.ZipFile(a.jar) as z:
        mesh=json.loads(z.read('assets/projectseele/mesh/carrier_mk2_r53.json'))
        feet=json.loads(z.read('assets/projectseele/mesh/foot_guide_rig_r52.json'))['nominal_sole_bindings']
    assert mesh['stride']==8 and mesh['engineering_upright_drive_r53']['mode']=='fixed_load_mast_with_four_independent_hollow_jaw_slides'
    # Closed, fully raised shallow carrier: every actual part is identity in
    # source space. yaw180 is independent of the upright directory frame.
    all_triangles=[];parts=[]
    for name,values in mesh['parts'].items():
        tri=np.asarray(values,dtype=np.float32).reshape(-1,3,8)[:,:,:3].astype(float)
        touched=(tri[:,:,1].min(1)<=46)&(tri[:,:,1].max(1)>=37)
        if touched.any():
            all_triangles.append(tri[touched]);parts.append(dict(part=name,triangles=int(touched.sum())))
    assert any(v['part']=='jaw_fixed_upper_r' for v in parts)
    source=np.concatenate(all_triangles);variants=[];offsets={}
    nodes={n['id']:n for n in directory['nodes']}
    units={u['variant']:u for u in owner['units']}
    for v in range(3):
        b=feet[str(v)];foot=(np.asarray(b['l'])+b['r'])/2
        bay=units[v]['bay_frame']
        assert bay['quaternion']==[0,1,0,0], 'Registered actual owner must use yaw180'
        registered=(np.asarray(nodes[f'unit{v}/bay']['foot_frame']['translation'])-bay['position'])*[-1,1,-1]
        assert np.max(np.abs(registered-foot))<1e-10, 'Actual registered foot datum differs from the installed sole source'
        # Same equation as FootSupportFrameR52.sample: root=foot-Q*centre.
        posed=(source-foot)*[-1,1,-1];rows=clipped(posed)
        rows={y:p for y,p in rows.items() if 37<=y<46}
        variants.append(dict(variant=v,height_slices_1m=bands(rows)))
        offsets[v]=(-foot*np.array([-1,1,-1])).tolist()
    shapes=make_parts(dict(legs=legs),dict(variants=variants))
    members=defaultdict(list)
    for i,s in enumerate(shapes):
        low,high=[np.floor(v/16).astype(int) for v in s['bounds']]
        grid=np.indices(tuple(high-low+1)).reshape(3,-1).T+low;active=np.arange(len(grid));centres=grid*16+8
        for begin in range(0,len(s['equations']),16):
            e=s['equations'][begin:begin+16]
            active=active[np.all(centres[active]@e[:,:3].T+e[:,3]<=3.1+8*np.abs(e[:,:3]).sum(1),axis=1)]
            if not len(active):break
        for cx,sy,cz in grid[active]:members[int(cx),int(cz),int(sy)].append(i)
    selected=defaultdict(set)
    for cx,cz,sy in members:selected[cx,cz].add(sy)
    print('Upper carrier continuous source:',len(parts),'parts;',len(shapes),'hulls;',len(members),'sections',flush=True)
    current={};palette=[];codes={}
    def code(s):
        if s not in codes:codes[s]=len(palette);palette.append(s)
        return codes[s]
    for cx,cz,sy,pal,values in iter_selected_sections(w,'projectseele:geofront',selected,skip_unfinished=True):
        current[cx,cz,sy]=np.array([code(s) for s in pal],np.uint16)[values]
    assert members.keys()<=current.keys(), 'Every selected actual section must be FULL'
    air=code('minecraft:air');panel=code('projectseele:nerv_shaft_panel')
    # Replay only ownership from applied construction, not its block state.
    # Later differences revoke that ownership instead of being overwritten.
    prior={};receipts=[]
    for stem in ('phased_routes/final68_ascent_civil','phased_routes/west_early_current/combined_civil'):
        base=a.author_base/stem;receipt=read(base/'APPLIED.json');assert receipt['world_written']
        d=np.load(base/'CIVIL_CANDIDATE.npz');pm=np.array([code(str(s)) for s in d['palette']],np.uint16)
        for k,old,new in zip(d['section_keys'],d['before'],d['after']):
            key=tuple(map(int,k))
            if key not in current:continue
            mask=old!=new
            if mask.any():
                saved=prior.setdefault(key,np.full(4096,-1,np.int32));saved[mask]=pm[new[mask]]
        receipts.append(str(base/'APPLIED.json'))
    protected=defaultdict(set)
    for section in ('gates','resources','receivers','units'):
        for pos in positioned_rows(owner.get(section,{})):
            if all(float(c).is_integer() for c in pos):
                key,j=slot(pos);protected[key].add(j)
    kk=np.asarray(list(members));lo=kk[:,[0,2,1]].min(0)*16;hi=kk[:,[0,2,1]].max(0)*16+15
    devices=list(iter_block_entities(w,'projectseele:geofront',lo,hi,selected_chunks=selected))
    for pos,_ in devices:key,j=slot(pos);protected[key].add(j)
    lining_ids=np.array([codes[s] for s in LINING if s in codes]);air_ids=np.array([codes[s] for s in AIR if s in codes]);natural_ids=np.array([codes[s] for s in NATURAL if s in codes])
    own={};anchors=[]
    for key,old in current.items():
        receipt=prior.get(key,np.full(4096,-1,np.int32));same=old==receipt
        lining=same&np.isin(old,lining_ids);own[key]=lining
        if lining.any():anchors.append(xyz_for(key)[lining])
    tree=cKDTree(np.concatenate(anchors));local=np.indices((16,16,16)).reshape(3,-1).T[:,[2,0,1]]
    def section(key):
        old=current[key];xyz=xyz_for(key);x,y,z=xyz.T;core=np.zeros(4096,bool);shell=np.zeros(4096,bool);bank=np.zeros(4096,np.uint8)
        for i in members[key]:
            s=shapes[i];c=contains(s,xyz+.5);sh=contains(s,xyz+.5,2)
            core|=c;shell|=sh;bank[sh]|=1<<(s['bank']-1)
        permitted=shell&((((bank&1)!=0)&(y<=-467))|(((bank&2)!=0)&(y<=80))|(((bank&4)!=0)&(y<=174)))
        keep=inherited_protection(x,y,z)
        keep[list(protected.get(key,()))]=True
        keep|=np.array([('glass' in palette[j] or palette[j].startswith('minecraft:ladder[') or palette[j] in ('minecraft:barrier','minecraft:structure_void','minecraft:lodestone')) for j in old])
        natural=np.isin(old,natural_ids)&permitted&~keep;near=np.zeros(4096,bool)
        if natural.any():near[natural]=tree.query(xyz[natural],workers=1)[0]<=5.
        positive=(own[key]|near)&permitted&~keep
        after=old.copy();after[positive&core]=air
        # Preserve the existing ribs and lamps on the retained outer shell.
        after[positive&~core&~own[key]]=panel
        # Existing empty cavities are never sealed. This is the union with
        # the full old bore, not a new thin upper-only tunnel through it.
        changed=after!=old
        blocked=permitted&core&~np.isin(old,air_ids)&~positive&~keep
        foreign=[dict(position=list(map(int,xyz[j])),state=palette[old[j]]) for j in np.flatnonzero(blocked)]
        records=[]
        for j in np.flatnonzero(changed):
            records.append(dict(position=list(map(int,xyz[j])),before=palette[old[j]],after=palette[after[j]],
                authority='unchanged_applied_lining' if own[key][j] else 'declared_bore_adjacent_natural_fill',
                role='clearance' if core[j] else 'two_metre_outer_lining'))
        return key,records,foreign,int((core&permitted).sum()),int((permitted&core&keep&~np.isin(old,air_ids)).sum())
    forward=[];holds=[];core_cells=0;kept=0
    with ThreadPoolExecutor(max_workers=max(1,min(8,a.workers))) as pool:
        for i,(key,records,foreign,n,k) in enumerate(pool.map(section,sorted(members)),1):
            forward.extend(records);holds.extend(foreign);core_cells+=n;kept+=k
            if i%500==0:print('Prepared',i,'/',len(members),'sections; changes',len(forward),'unclassified',len(holds),flush=True)
    found=[r for r in forward if tuple(r['position'])==KNOWN]
    assert len(found)==1 and found[0]['before']=='projectseele:nerv_shaft_panel' and found[0]['after']=='minecraft:air', 'Known upper-jaw source failure must be detected and reversibly corrected'
    assert len({tuple(r['position']) for r in forward})==len(forward)
    inverse=[dict(position=r['position'],before=r['after'],after=r['before']) for r in forward]
    positive=[dict(position=r['position'],expected_state=r['before'],authority=r['authority']) for r in forward]
    summary=dict(world_written=False,candidate_only=True,installable_without_review=False,world=str(w),
        covered_forward_legs=[v['id'] for v in legs],source_carrier_parts=parts,height_band_m=[37,46],
        world_rotation='yaw180',root_offsets_from_actual_foot_source=offsets,engineering_clearance_m=1.01,outer_lining_m=2,
        continuous_hulls=len(shapes),measured_sections=len(current),core_cells=core_cells,changed_cells=len(forward),
        changes_by_role=dict(Counter(r['role'] for r in forward)),changes_by_authority=dict(Counter(r['authority'] for r in forward)),
        protected_gate_support_device_cells=kept,block_entities_preserved=len(devices),unclassified_core_cells=len(holds),
        known_failure=found[0],applied_ownership_receipts=receipts,
        requires_review=['This upper carrier band does not replace full-body runtime admission.','Gate phases/supports and all devices remain owned and unchanged.','Re-read exact before state after cold stop before applying.'],
        routes_entities_player_tasks_navigation_traffic_written=False)
    dump(out/'FORWARD.json.gz',forward);dump(out/'INVERSE.json.gz',inverse);dump(out/'POSITIVE_MASK.json.gz',positive)
    dump(out/'UNCLASSIFIED.json.gz',holds);dump(out/'SUMMARY.json',summary)
    print(json.dumps({k:summary[k] for k in ('world_written','changed_cells','changes_by_role','unclassified_core_cells','known_failure')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()

"""Four approved original launch-control templates: exact cold-world candidate, no application."""
from pathlib import Path
from collections import Counter, defaultdict
import copy
import gzip
import hashlib
import json
import shutil
import uuid
import nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR, iter_block_entities
from inspect_c03_lowrise_r48 import WORLD, DATA, unpack
from inspect_c03_registered_lowrise_r48 import nbt_uuid, state_text

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r48/city/c03_lowrise_restore_candidate'
ORIGIN=(30,80,220)
DEFS=[('r48_launch_control_nw',(-10,80,180)),('r48_launch_control_sw',(-10,80,260)),
      ('r48_launch_control_ne',(70,80,180)),('r48_launch_control_se',(70,80,260))]
LINER='minecraft:polished_deepslate'
IRON='minecraft:iron_block'


def packed(q):
    x,y,z=q; v=((x&67108863)<<38)|((z&67108863)<<12)|(y&4095)
    return v-(1<<64) if v>=1<<63 else v


def state_tag(value):
    name,_,rest=value.partition('['); t=nbtlib.Compound({'Name':nbtlib.String(name)})
    if rest: t['Properties']=nbtlib.Compound({k:nbtlib.String(v) for k,v in (p.split('=',1) for p in rest[:-1].split(','))})
    return t


def owner(world,centre):
    fmt=lambda p:f'BlockPos{{x={p[0]}, y={p[1]}, z={p[2]}}}'
    # Java UUID.nameUUIDFromBytes compatibility; identity construction, not an asset/file SHA audit.
    return uuid.UUID(bytes=hashlib.md5((world+'/'+fmt(ORIGIN)+'/rigid-owner/'+fmt(centre)).encode()).digest(),version=3)


def uuid_tag(value):
    return nbtlib.IntArray([x if x<2147483648 else x-4294967296 for x in
                          [(value.int>>(32*(3-i)))&4294967295 for i in range(4)]])


def template(cx,cz):
    cells={}
    for x in range(-7,8):
        for z in range(-7,8):
            cells[x,0,z]=LINER
            for y in range(1,11):
                shell=abs(x)==7 or abs(z)==7
                value='minecraft:air' if not shell else 'minecraft:orange_concrete' if y==3 else \
                    'minecraft:gray_stained_glass' if 5<=y<=7 and abs(x)<6 else \
                    LINER if abs(x)==7 and abs(z)==7 else 'minecraft:gray_concrete'
                cells[x,y,z]=value
            cells[x,11,z]='minecraft:sea_lantern' if (x+z)%6==0 else 'minecraft:smooth_stone'
    inward=7 if cz<220 else -7
    for x in range(-1,2):
        for y in range(1,4): cells[x,y,inward]='minecraft:air'
    lamp='minecraft:redstone_lamp[lit=false]'
    cells[0,11,0]=lamp
    for y in range(12,26): cells[0,y,0]=lamp if y%4==0 else \
        'minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]'
    cells[0,26,0]='minecraft:lightning_rod[facing=up,powered=false,waterlogged=false]'
    for x in range(-5,6): cells[x,11,0]='minecraft:orange_concrete' if cx<30 else 'minecraft:red_concrete'
    cells[0,11,0]=lamp
    return cells


def main():
    marker=DATA/'projectseele_city_rigid_topology_r45_8246338109520.dat'
    control=DATA/'projectseele_city_rigid_control_r45_8246338109520.dat'
    wrapper=nbtlib.load(marker); topology=wrapper['data']; ledger=nbtlib.load(control)['data']
    assert len(topology['Towers'])==96 and int(topology['Origin'])==packed(ORIGIN)
    assert str(ledger['Phase'])=='IDLE' and int(ledger['Depth'])==int(ledger['Target'])==0 and int(ledger['Queued'])==-1
    assert not str(ledger['Fault']) and not str(ledger['QueueFault']) and int(ledger['SavedPlans'])==int(ledger['Created'])==96
    assert not OUT.exists(), 'Candidate output is immutable; use a new version directory instead of overwriting.'
    world_id=str(topology['WorldUUID'])
    old65=nbtlib.load(DATA/'city_rigid_journal_r45'/nbt_uuid(ledger['Journey'])/'65.dat')
    assert str(owner(world_id,(-170,80,60)))==nbt_uuid(old65['Owner']), 'Java existing owner derivation mismatch'
    w=MeasuredWorld(WORLD)
    for _,(cx,_,cz) in DEFS: w.box((cx-13,-9,cz-13),(cx+13,110,cz+13))
    w.load()
    assert all(v=='full' for v in w.status.values()), 'Unknown/uncompleted source component chunk'
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(-23,-9,167),(83,110,273),selected_chunks=set(w.selected)))
    OUT.mkdir(); (OUT/'cargo').mkdir(); (OUT/'recipes').mkdir(); (OUT/'metadata_before').mkdir()
    shutil.copyfile(marker,OUT/'metadata_before'/marker.name)
    shutil.copyfile(control,OUT/'metadata_before'/control.name)
    manifest=dict(schema='projectseele.r48.c03-four-original-lowrise-restoration-candidate.v1',
                  stage='DRAFT_ROOT_REVIEW_ONLY_NOT_APPLIED', world_written=False, source_world=str(WORLD),world_id=world_id,
                  user_scope='Root relays approval to restore these four original planned full26m launch-control cells',
                  source_template='ThirdTokyoSurfaceBuilder.buildLaunchControlBlock',original_members=96,new_members=4,
                  original_actor_progress_and_control_bytes_unchanged=True,
                  source_ledger_full_snbt=ledger.snbt(),source_topology_full_snbt=topology.snbt(),
                  new_owner_policy='Same server city journey/WAL, deterministic independent new UUIDs; no new player command/control',
                  frame_transform=dict(surface_base_y=80,retracted_base_y=-7,complete_height_including_mast=26,
                                       surface_top_y=106,retracted_top_y=19,physical_travel_metres=87,
                                       transaction_depth_0_312_is_not_actual_312m_displacement=True,
                                       retired_s22_surface68_not_used=True),
                  selected_chunks=len(w.selected),unknown=0,holds=[],components=[])
    desired={}; roles={}; static_masks=defaultdict(dict); ground_masks=defaultdict(list)
    natural={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:stone'}
    paving={'minecraft:polished_deepslate','minecraft:smooth_stone','minecraft:polished_blackstone','minecraft:sea_lantern'}
    def put(q,st,role):
        if q in desired and desired[q]!=st and role!='complete_surface_template':
            if roles[q] not in {'complete_clear_swept_volume','static_liner_outside_sweep'}:
                raise RuntimeError(f'Conflicting explicit roles {q}: {roles[q]} -> {role}')
        desired[q]=st; roles[q]=role
    for i,(name,centre) in enumerate(DEFS,96):
        cx,cy,cz=centre; cells=template(cx,cz)
        comp=dict(index=i,template_id=name,centre=list(centre),owner=str(owner(world_id,centre)),
                  complete_source_box=[cx-7,80,cz-7,cx+7,109,cz+7],swept_box=[cx-7,-7,cz-7,cx+7,109,cz+7],
                  complete_static_and_clearance_inspection_box=[cx-13,-9,cz-13,cx+13,110,cz+13],
                  source_geometry_provenance='Original source loop (7x7 half-width, room10 + roof11 + original mast through26), unchanged coefficients',
                  primary_room_height=10,complete_mast_height=26,doorway=dict(x_range=[cx-1,cx+1],y_range=[81,83],
                                                                        z=cz+(7 if cz<220 else -7)),
                  new_component_BE_count=0,original_BEs=[],road_and_device_bounds=[],roles={},native_passed=False)
        preimage=OUT/f'{name}_complete_before.jsonl.gz'
        with gzip.open(preimage,'wt',encoding='utf8') as handle:
            for y in range(-9,111):
                for z in range(cz-13,cz+14):
                    for x in range(cx-13,cx+14):
                        q=x,y,z; st=w.block(q); assert st is not None
                        row=dict(pos=list(q),state=st,full_nbt=tags[q].snbt() if q in tags else None)
                        handle.write(json.dumps(row)+'\n')
                        if q in tags: comp['original_BEs'].append(row)
        comp['full_before_preimage']=str(preimage)
        # No actor/cargo substitution: complete final surface template is separate from the immutable original96.
        for x in range(-7,8):
            for z in range(-7,8):
                for y in range(-7,110):
                    q=cx+x,y,cz+z
                    put(q,'minecraft:air','complete_clear_swept_volume')
                    static_masks[q[0]//16,q[2]//16][q]='minecraft:air'
                seam=(x+7)%5==0 or (z+7)%5==0
                st=LINER if abs(x)==7 or abs(z)==7 else IRON if seam else 'minecraft:gray_concrete'
                ground_masks[(cx+x)//16,(cz+z)//16].append((cx+x,80,cz+z,st,i))
                put((cx+x,-8,cz+z),LINER,'complete_lower_bearing_saddle')
                static_masks[(cx+x)//16,(cz+z)//16][cx+x,-8,cz+z]=LINER
        for y in range(-8,81):
            for x in range(-8,9):
                for z in range(-8,9):
                    if max(abs(x),abs(z))!=8: continue
                    q=cx+x,y,cz+z; put(q,LINER,'static_liner_outside_sweep'); static_masks[q[0]//16,q[2]//16][q]=LINER
        for y in (20,24):
            for x in range(-11,12):
                for z in range(-11,12):
                    if max(abs(x),abs(z))<9: continue
                    q=cx+x,y,cz+z; put(q,IRON,'two_complete_outside_sweep_structural_rings'); static_masks[q[0]//16,q[2]//16][q]=IRON
            for x,z in [(x,z) for x in range(-1,2) for z in (-8,8)]+[(x,z) for z in range(-1,2) for x in (-8,8)]:
                q=cx+x,y,cz+z; put(q,IRON,'outside_sweep_liner_ring_connections'); static_masks[q[0]//16,q[2]//16][q]=IRON
        anchors=[]
        for sx in (-1,1):
            for sz in (-1,1):
                for x in (sx*10,sx*11):
                    for z in (sz*10,sz*11):
                        for y in range(20,80):
                            q=cx+x,y,cz+z; put(q,IRON,'complete_outside_sweep_bearing_column'); static_masks[q[0]//16,q[2]//16][q]=IRON
                        for y in range(21,25): anchors.append(packed((cx+x,y,cz+z)))
        for p,st in cells.items():
            if st not in AIR: put((cx+p[0],80+p[1],cz+p[2]),st,'complete_surface_template')
        for old_index,t in enumerate(topology['Towers']):
            oc=unpack(t['Centre']); f=t['Footprint']
            sep=cx+13<oc[0]+int(f['MinX']) or cx-13>oc[0]+int(f['MaxX']) or cz+13<oc[2]+int(f['MinZ']) or cz-13>oc[2]+int(f['MaxZ'])
            if not sep: manifest['holds'].append(dict(type='ORIGINAL96_FOOTPRINT_BOUNDARY_OVERLAP',component=name,index=old_index))
        for sx in (-12,30,72):
            comp['road_and_device_bounds'].append(dict(type='original_silo_hatch_external_envelope',box=[sx-20.7,79,199.3,sx+20.7,106,240.7],
                                                       horizontal_z_clearance=min(abs(cz-220)-13-20.7,999),
                                                       note='Known original measured outer equipment envelope; no geometry/model edit'))
        comp['road_and_device_bounds'].append(dict(type='original_grid_street_planes',nearest_x=[10,50],nearest_z=[200,240],
                                                   device_side_routes='All static members stay at x/z offsets<=11; room doors face the already-planned court. No overhead/roof public route added.'))
        cargo=nbtlib.List[nbtlib.Compound]()
        for p,st in sorted(cells.items()):
            if st not in AIR: cargo.append(nbtlib.Compound({'Pos':nbtlib.Long(packed(p)),'State':state_tag(st)}))
        frame=nbtlib.Compound({k:nbtlib.Int(v) for k,v in dict(MinX=-7,MaxX=7,MinZ=-7,MaxZ=7).items()})
        building=nbtlib.Compound({'Centre':nbtlib.Long(packed(centre)),'Origin':nbtlib.Long(packed(ORIGIN)),
                                 'Half':nbtlib.Int(7),'Height':nbtlib.Int(26),'FixedStreetCore':nbtlib.Byte(0),
                                 'R45Footprint':copy.deepcopy(frame),'NegativeDomeAnchorMask':nbtlib.LongArray(anchors),'Cargo':cargo,
                                 'R48TemplateId':nbtlib.String(name),'R48SourceTemplate':nbtlib.String(manifest['source_template'])})
        nbtlib.File({'data':nbtlib.Compound({'Version':nbtlib.Int(1),'WorldUUID':nbtlib.String(world_id),
                    'Buildings':nbtlib.List[nbtlib.Compound]([building])})}).save(OUT/'cargo'/f'{i}.dat',gzipped=True)
        comp['full_cargo_cells']=len(cargo); comp['full_cargo']=str(OUT/'cargo'/f'{i}.dat')
        topology['Towers'].append(nbtlib.Compound({'Centre':nbtlib.Long(packed(centre)),'Height':nbtlib.Int(26),'Half':nbtlib.Int(7),
                    'Kind':nbtlib.String('r48_launch_control'),'RetractedBaseY':nbtlib.Int(-7),'Footprint':frame,
                    'NegativeDomeAnchorMask':nbtlib.LongArray(anchors),'R48TemplateId':nbtlib.String(name),
                    'R48SourceTemplate':nbtlib.String(manifest['source_template']),'R48FullComponentHeight':nbtlib.Int(26),
                    'R48Owner':uuid_tag(owner(world_id,centre))}))
        manifest['components'].append(comp)
    # Candidate stores complete before images and never overwrites an unknown occupied component.
    counts=Counter(); changed=0; before_be=0
    forward=gzip.open(OUT/'forward.jsonl.gz','wt',encoding='utf8'); inverse=gzip.open(OUT/'inverse.jsonl.gz','wt',encoding='utf8')
    for q,st in sorted(desired.items()):
        before=w.block(q); full=tags[q].snbt() if q in tags else None
        name=before.partition('[')[0]
        if full is not None or (name not in natural and not(q[1]==80 and name in paving)):
            manifest['holds'].append(dict(type='UNKNOWN_OR_OWNED_OCCUPANCY_NOT_CLEARABLE',pos=list(q),before=before,full_before_nbt=full,role=roles[q]))
        if before==st and full is None: continue
        row=dict(pos=list(q),before=before,after=st,before_nbt=full,after_nbt=None,role=roles[q]); forward.write(json.dumps(row)+'\n')
        inverse.write(json.dumps(dict(pos=list(q),before=st,after=before,before_nbt=None,after_nbt=full,role=roles[q]))+'\n')
        changed+=1; before_be+=full is not None; counts[roles[q]]+=1
    forward.close(); inverse.close()
    old_topology=nbtlib.load(marker)['data']
    topology['LowriseAddonR48']=nbtlib.Compound({'Version':nbtlib.Int(1),'Stage':nbtlib.String('DRAFT_ROOT_REVIEW_ONLY'),
          'RootApprovedSourceTemplate':nbtlib.Byte(1),'ExactComponentMigrationPassed':nbtlib.Byte(0),'FullSweepVerified':nbtlib.Byte(0),
          'WorldUUID':nbtlib.String(world_id),'Origin':nbtlib.Long(packed(ORIGIN)),
          'Original96Towers':copy.deepcopy(old_topology['Towers'])})
    assert all(topology['Towers'][i]==old_topology['Towers'][i] for i in range(96))
    wrapper.save(OUT/'projectseele_city_rigid_topology_r45_8246338109520.dat',gzipped=True)
    for (x,z),mask in static_masks.items():
        existing=DATA/'city_rigid_generation_r45/chunks'/f'{x}_{z}.dat'
        tag=nbtlib.load(existing) if existing.exists() else nbtlib.File({'Version':nbtlib.Int(1),'WorldUUID':nbtlib.String(world_id),
                   'InitialDepth':nbtlib.Int(0),'Palette':nbtlib.List[nbtlib.Compound](),
                   'Static':nbtlib.List[nbtlib.Compound](),'Ground':nbtlib.List[nbtlib.Compound]()})
        if existing.exists(): shutil.copyfile(existing,OUT/'metadata_before'/f'recipe_{x}_{z}.dat')
        palette=tag['Palette']; lookup={state_text(st):i for i,st in enumerate(palette)}
        def code(st):
            if st not in lookup: lookup[st]=len(palette); palette.append(state_tag(st))
            return lookup[st]
        static={int(r['Pos']):r for r in tag['Static']}
        for q,st in mask.items():
            if packed(q) in static and str(palette[int(static[packed(q)]['StateId'])]['Name']) not in AIR and state_text(palette[int(static[packed(q)]['StateId'])])!=st:
                manifest['holds'].append(dict(type='PREEXISTING_RECIPE_STATIC_ROLE_COLLISION',pos=list(q)))
            static[packed(q)]=nbtlib.Compound({'Pos':nbtlib.Long(packed(q)),'StateId':nbtlib.Int(code(st))})
        tag['Static']=nbtlib.List[nbtlib.Compound]([static[k] for k in sorted(static)])
        for xx,yy,zz,st,i in ground_masks[x,z]:
            tag['Ground'].append(nbtlib.Compound({'Pos':nbtlib.Long(packed((xx,yy,zz))),'StateId':nbtlib.Int(code(st)),'Object':nbtlib.Int(i)}))
        tag.save(OUT/'recipes'/f'{x}_{z}.dat',gzipped=True)
    manifest['changed_cells']=changed; manifest['changed_cell_full_before_NBT_count']=before_be
    manifest['changed_roles']=dict(counts); manifest['complete_source_component_before_BE_count']=sum(len(c['original_BEs']) for c in manifest['components'])
    manifest['candidate_world_application_allowed']=False
    manifest['holds_count']=len(manifest['holds'])
    manifest['source_control_after_candidate_is_identical_file']=str(OUT/'metadata_before'/control.name)
    manifest['runtime_hooks_required_before_any_install']='CityLowriseAddonR48 strict count/prefix/whitelist; flat-floor cover fix; generation original96-journal fallback; preserve existing ledger and original96 recipe/cargo.'
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(output=str(OUT),world_written=False,changed_cells=changed,holds=len(manifest['holds']),
                          changed_roles=dict(counts),before_BEs=before_be,
                          components=[dict(id=c['template_id'],owner=c['owner'],cargo_cells=c['full_cargo_cells']) for c in manifest['components']]),indent=2))


if __name__=='__main__': main()

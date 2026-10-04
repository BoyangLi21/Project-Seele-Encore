"""Plan exact outside-sweep supports, lined shafts and relocated controllers.

Uses query_blocks' shared save reader. Produces proposals/inverses only; Root
reviews structure, native shapes, ports and art before any world/archive write.
"""
from pathlib import Path
from collections import Counter
import argparse,copy,gzip,hashlib,json
import nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from measure_city_placements_r45 import unpack_pos

ROOT=Path(__file__).resolve().parents[1]
NATURAL={'minecraft:stone','minecraft:deepslate','minecraft:dirt','minecraft:grass_block','minecraft:coarse_dirt','minecraft:rooted_dirt','minecraft:gravel','minecraft:andesite','minecraft:diorite','minecraft:granite','minecraft:tuff','minecraft:calcite','minecraft:bedrock','minecraft:iron_ore','minecraft:deepslate_iron_ore'}
IRON='minecraft:iron_block';LINER='minecraft:polished_deepslate';FLOOR='minecraft:smooth_stone'

def packed(q):
    x,y,z=q;value=((x&0x3ffffff)<<38)|((z&0x3ffffff)<<12)|(y&4095)
    return value-(1<<64) if value>=1<<63 else value

def ground_hatch_state(x,z,half,outer_ward):
    edge=max(abs(x),abs(z))
    name='polished_deepslate'if edge>=half-1 else('orange_concrete'if(x+z)%4<2 else'black_concrete')if edge==half-2 else'iron_block'if x%6==0 or z%6==0 else'light_gray_concrete'if outer_ward else'gray_concrete'
    if abs(x)==half-3 and abs(z)==half-3:name='sea_lantern'
    return 'minecraft:'+name


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--world',type=Path,default=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW')
    parser.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r45/city_motion/topology_v1');args=parser.parse_args()
    world=args.world.resolve();out=args.out.resolve();assert world.name=='SEELE_FIELD_R45_REVIEW' and not out.exists()
    preflight=json.loads((ROOT/'artifacts/rebuild_r45/city_motion/create_probe_v2/preflight.json').read_text())
    w=MeasuredWorld(world);buildings=[]
    for row in preflight['records']:
        cx,cy,cz=row['center'];half=row['half'];base=19-row['height'];r=half+4
        w.box((cx-r-1,base-2,cz-r-1),(cx+r+2,83,cz+r+1))
        building=nbtlib.load(row['path'])['data']['Buildings'][0];buildings.append(building)
    # Freeze the source section read epoch; do not equate a running QA world's
    # directory name with a cold/static measurement guarantee.
    region=world/'dimensions/projectseele/geofront/region';region_files={region/f'r.{x//32}.{z//32}.mca' for x,z in w.selected}
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in region_files if p.exists()}
    w.load();points=[r['center'] for r in preflight['records']]
    lo=(min(p[0] for p in points)-20,-110,min(p[2] for p in points)-20);hi=(max(p[0] for p in points)+22,83,max(p[2] for p in points)+20)
    tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
    district=nbtlib.load(world/'dimensions/projectseele/geofront/data/projectseele_tokyo3_retraction.dat')['data']['Districts'][0]
    assert int(district['Depth'])==int(district['TargetDepth'])==312 and int(district['Cursor'])==int(district['VoxelCursor'])==0
    out.mkdir(parents=True);(out/'archive_migration').mkdir();records=[];held=[];change_counts=Counter()
    forward=gzip.open(out/'forward.jsonl.gz','wt',encoding='utf8');inverse=gzip.open(out/'inverse.jsonl.gz','wt',encoding='utf8')
    retained=[]
    for index,(row,building) in enumerate(zip(preflight['records'],buildings)):
        cx,cy,cz=row['center'];h=row['height'];half=row['half'];base=19-h;r=half+3;wall=half+1
        current_cargo={}
        for cell in building['Cargo']:
            x,y,z=unpack_pos(int(cell['Pos']));current_cargo[(cx+x,base+y,cz+z)]=cell
            if 'NBT'in cell:retained.append(dict(pos=[cx+x,base+y,cz+z],tower=index,full_original_cargo_nbt=cell['NBT'].snbt()))
        desired={};roles={}
        def put(q,state,role):
            if q in desired and desired[q]!=state and role not in {'liner_to_ring_radial_bearing','complete_external_bearing_column','overhead_3x3_load_spreading_plate','complete_moving_floor_after_core_relocation','preserved_underfloor_inspection_light_on_static_liner'}:
                raise RuntimeError(f'Overlapping topology roles {q}: {desired[q]} vs {state}')
            desired[q]=state;roles[q]=role
        # Explicit functional shaft domain, not inferred permission from air.
        # Retain all current complete cargo/BE cells at the contracted endpoint.
        for x in range(-half,half+1):
            for z in range(-half,half+1):
                for y in range(base,80):
                    q=(cx+x,y,cz+z)
                    if q not in current_cargo:put(q,'minecraft:air','clear_complete_rigid_swept_shaft')
                # The complete registered surface cover is part of the same
                # component. Preserve exact preimages, including original air
                # holes; future Ground and native opening require this mask.
                put((cx+x,80,cz+z),ground_hatch_state(x,z,half,index>=64),'complete_declared_street_hatch_cover')
        # Continuous liner outside the whole moving prism; its lower collar
        # supports the landing apron and its upper collar joins the roof beam.
        for y in range(base-1,80):
            for x in range(-wall,wall+1):
                for z in range(-wall,wall+1):
                    if max(abs(x),abs(z))==wall:
                        if z==wall and abs(x)<=1 and base+1<=y<=base+3:continue
                        put((cx+x,y,cz+z),LINER,'outside_sweep_continuous_liner')
        # A complete lower saddle lies one block below the swept minimum,
        # supporting every endpoint floor cell while remaining outside motion.
        # It connects on all four sides to the continuous shaft liner.
        for x in range(-half,half+1):
            for z in range(-half,half+1):put((cx+x,base-1,cz+z),LINER,'complete_endpoint_bearing_saddle_below_sweep')
        # The two-ring structure joins four complete external steel columns.
        # Entire beam and column footprint stays >= half+1 outside cargo.
        for y in (20,24):
            for x in range(-r-1,r+2):
                for z in range(-r-1,r+2):
                    if r<=max(abs(x),abs(z))<=r+1:put((cx+x,y,cz+z),IRON,'connected_roof_ring_beam')
            for sign in (-1,1):
                for offset in range(wall,r+1):
                    for side in (-1,0,1):
                        put((cx+sign*offset,y,cz+side),IRON,'liner_to_ring_radial_bearing')
                        put((cx+side,y,cz+sign*offset),IRON,'liner_to_ring_radial_bearing')
        anchors=[];bearings=[]
        for sx in (-1,1):
            for sz in (-1,1):
                # Search only a measured 3x3 complete existing roof/earth slab.
                # Do not call a floating plate or a partial-support sample ready.
                foot_x,foot_z=cx+sx*r,cz+sz*r
                bearing=None
                for y in range(26,78):
                    if all(w.get(foot_x+dx,yy,foot_z+dz) is not None
                        and w.get(foot_x+dx,yy,foot_z+dz).partition('[')[0] in NATURAL
                        and (foot_x+dx,yy,foot_z+dz) not in tags
                        for dx in (-1,0,1) for dz in (-1,0,1) for yy in (y,y+1)):
                        bearing=y;break
                if bearing is None:
                    held.append(dict(tower=index,kind='NO_COMPLETE_MEASURED_OVERHEAD_BEARING',footprint=[foot_x,foot_z]));bearing=26
                for x in (sx*r,sx*(r+1)):
                    for z in (sz*r,sz*(r+1)):
                        for y in range(20,bearing):
                            put((cx+x,y,cz+z),IRON,'complete_external_bearing_column')
                            if 21<=y<=24:anchors.append((cx+x,y,cz+z))
                for dx in (-1,0,1):
                    for dz in (-1,0,1):put((foot_x+dx,bearing-1,foot_z+dz),IRON,'overhead_3x3_load_spreading_plate')
                bearings.append(dict(pad_center=[foot_x,bearing-1,foot_z],measured_bearing_y=bearing,
                    two_layers=[[[foot_x+dx,yy,foot_z+dz],w.get(foot_x+dx,yy,foot_z+dz)] for dx in (-1,0,1) for dz in (-1,0,1) for yy in (bearing,bearing+1)]))
        # Complete declared doorway connection: a supported five-wide apron
        # joins the two-door portal; its edges have supported rails.
        for x in range(-2,3):
            for z in range(wall,wall+5):put((cx+x,base,cz+z),LINER,'supported_existing_door_landing_apron')
        for x in (-3,3):
            for z in range(wall+1,wall+5):
                put((cx+x,base,cz+z),LINER,'apron_rail_bearing')
                for y in (base+1,base+2):put((cx+x,y,cz+z),'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]','landing_edge_guard')
        core=None
        migrated=copy.deepcopy(building)
        if bool(building['FixedStreetCore']):
            old=(cx,80,cz);core=(cx+r,80,cz)
            before=w.block(old)
            if before is None or not before.startswith('projectseele:retractable_building_core') or old in tags:
                held.append(dict(tower=index,kind='CORE_STATE_NBT_REQUIRES_EXPLICIT_MIGRATION',pos=old,state=before,nbt=tags[old].snbt() if old in tags else None))
            else:
                put(old,IRON,'old_controller_position_becomes_operable_hatch_cover')
                put(core,before,'preserved_fixed_controller_relocated_outside_sweep')
                for x in range(r-1,r+3):
                    for z in range(-2,3):
                        put((cx+x,79,cz+z),LINER,'continuous_fixed_operator_platform_bearing')
                        if (cx+x,80,cz+z)!=core:
                            existing=w.get(cx+x,80,cz+z)
                            put((cx+x,80,cz+z),existing if existing in {'minecraft:light_gray_concrete',FLOOR,LINER} else FLOOR,'fixed_operator_platform_floor')
                # Old local0 never was cargo. Add an explicit new whole-lift
                # floor cell; original core and underside-light remain separate
                # preserved components, not silently captured or destroyed.
                put((cx,base,cz),LINER,'complete_moving_floor_after_core_relocation')
                put((cx+wall,base,cz), 'minecraft:sea_lantern','preserved_underfloor_inspection_light_on_static_liner')
                floor=nbtlib.Compound({'Pos':nbtlib.Long(0),'State':nbtlib.Compound({'Name':nbtlib.String(LINER)})})
                migrated['Cargo'].append(floor);migrated['FixedStreetCore']=nbtlib.Byte(0)
                migrated['R45OriginalFixedStreetCore']=nbtlib.Byte(1)
                migrated['R45FixedControllerPos']=nbtlib.Long(packed(core))
        migrated['NegativeDomeAnchorMask']=nbtlib.LongArray([packed(q) for q in anchors])
        migrated['R45RigidTopologyVersion']=nbtlib.Int(1)
        migration=out/'archive_migration'/Path(row['path']).name
        original=nbtlib.load(row['path']);original['data']['Buildings'][0]=migrated;original.save(migration,gzipped=True)
        emitted=0;local_holds=[]
        for q,after in sorted(desired.items()):
            before=w.block(q);nbt=tags[q].snbt() if q in tags else None
            if before==after:continue
            role=roles[q];name=(before or '').partition('[')[0]
            allow=before is not None and nbt is None and (name in AIR or name in NATURAL
                or name in {IRON,LINER,FLOOR,'minecraft:sea_lantern','minecraft:deepslate_bricks','minecraft:deepslate_tiles'}
                or role=='old_controller_position_becomes_operable_hatch_cover' and name=='projectseele:retractable_building_core'
                or role=='preserved_fixed_controller_relocated_outside_sweep' and name=='minecraft:light_gray_concrete')
            if q in current_cargo and not(role=='complete_moving_floor_after_core_relocation'):
                allow=False
            if not allow:
                held_row=dict(tower=index,kind='NON_TEMPLATE_OR_FULL_NBT_INTERFACE',pos=q,before=before,before_nbt=nbt,desired=after,role=role)
                held.append(held_row);local_holds.append(held_row);continue
            value=dict(pos=q,before=before,after=after,before_nbt=None,after_nbt=None,owner=f'r45/city_rigid_topology/{index}',reason=role)
            forward.write(json.dumps(value)+'\n');value=dict(value);value['before'],value['after']=value['after'],value['before'];inverse.write(json.dumps(value)+'\n')
            emitted+=1;change_counts[role]+=1
        records.append(dict(index=index,source_center=row['center'],height=h,half=half,source_archive_sha256=row['sha256'],
            rigid_sweep_box=[[cx-half,base,cz-half],[cx+half,80+h+3,cz+half]],endpoint_delta_y=-61-h,
            preserved_current_full_cargo_cells=len(building['Cargo']),new_moving_floor_cells=int(bool(building['FixedStreetCore'])),
            original_anchor_mask=list(map(int,building['NegativeDomeAnchorMask'])),new_negative_anchor_mask=anchors,
            original_core=[cx,80,cz] if bool(building['FixedStreetCore']) else None,new_fixed_core=core,
            original_door_port=[cx,base+1,cz+half],new_liner_port=[[cx-1,base+1,cz+wall],[cx+1,base+3,cz+wall]],
            support_ring_levels=[20,24],outside_ring_radius=r,shaft_liner_radius=wall,overhead_bearings=bearings,
            lower_saddle_y=base-1,lower_saddle_box=[[cx-half,base-1,cz-half],[cx+half,base-1,cz+half]],
            changed_cells=emitted,held_interfaces=len(local_holds),archive_candidate=str(migration),archive_candidate_sha256=hashlib.sha256(migration.read_bytes()).hexdigest()))
        print(f'topology {index+1}/93 changes={emitted} holds={len(local_holds)}',flush=True)
    forward.close();inverse.close()
    changed_region=[p for p,digest in hashes.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=digest]
    report=dict(schema='projectseele.city-rigid-topology-plan-r45.v1',world=str(world),world_id=preflight['world_id'],
        world_written=False,source_archives_written=False,root_structural_art_review=False,native_shapes=False,
        candidate_ready_for_apply=False,complete_cargo_nbt_retained=1471,
        measured_regions=hashes,region_files_changed_during_read=changed_region,towers=len(records),
        changed_cells=sum(r['changed_cells'] for r in records),changed_by_role=dict(change_counts),held=held,
        generator_positions=dict(legacy_core='ThirdTokyoSurfaceBuilder.buildTvTower/updateCoreStates original center→new_fixed_core map',
            legacy_fixed_columns='ThirdTokyoSurfaceBuilder.buildTvTower lines TvWorldPreviewTerrain.ROOF_Y-3..ROOF_Y corners±half→new external 2x2 columns and rings',
            legacy_negative_mask='Tokyo3BuildingArchiveR44.fixedAnchors original4corner16→new_negative_anchor_mask64; R45 never swallows a colliding cargo cell',
            old_maintenance='Tokyo3RetractionDirector register/request/tickLevel, ThirdTokyoSurfaceBuilder sweepLegacySurfaceCaps/sweepStrayMasts/applyRetractionDepth, LocalMapAssetLoader travel/repair must defer to persistent R45 topology/owner'),
        records=records)
    (out/'retained_complete_cargo_nbt.json').write_text(json.dumps(retained,indent=2),'utf8')
    (out/'topology.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('records','held','measured_regions','generator_positions')},indent=2))


if __name__=='__main__':main()

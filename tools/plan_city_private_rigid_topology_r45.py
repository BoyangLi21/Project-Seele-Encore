"""Extend the exact rigid-city proposal to all three real imported buildings.

Captures current full native rectangular cargo, including every BE, instead of
reconstructing a canonical template or resetting private-building inventory.
"""
from pathlib import Path
import argparse,gzip,hashlib,json
from collections import Counter
import nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from plan_city_rigid_topology_r45 import NATURAL,IRON,LINER,packed

ROOT=Path(__file__).resolve().parents[1]


def state_tag(value):
    name,_,rest=value.partition('[');tag=nbtlib.Compound({'Name':nbtlib.String(name)})
    if rest:tag['Properties']=nbtlib.Compound({k:nbtlib.String(v) for k,v in (x.split('=',1) for x in rest.rstrip(']').split(','))})
    return tag


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r45/city_motion/private_topology_v1');args=parser.parse_args()
    out=args.out.resolve();assert not out.exists();world=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW'
    data_dir=world/'dimensions/projectseele/geofront/data';identity=str(nbtlib.load(data_dir/'projectseele_tokyo3_building_world_id_r44.dat')['data']['WorldUUID'])
    d=nbtlib.load(data_dir/'projectseele_tokyo3_retraction.dat')['data']['Districts'][0];assert int(d['Depth'])==int(d['TargetDepth'])==312
    definitions=[dict(center=(-99,81,155),box=(-11,11,-5,6)),dict(center=(144,81,139),box=(-5,6,-11,11)),dict(center=(131,81,296),box=(-11,11,-5,6))]
    w=MeasuredWorld(world)
    for spec in definitions:
        cx,cy,cz=spec['center'];a,b,c,d=spec['box'];w.box((cx+a-4,-63,cz+c-4),(cx+b+4,84,cz+d+4))
    regions={world/'dimensions/projectseele/geofront/region'/f'r.{x//32}.{z//32}.mca' for x,z in w.selected};hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in regions if p.exists()}
    w.load();tags=dict(iter_block_entities(world,'projectseele:geofront',(-130,-63,110),(175,84,325),selected_chunks=set(w.selected)))
    out.mkdir(parents=True);(out/'cargo').mkdir();rows=[];held=[];counts=Counter()
    f=gzip.open(out/'forward.jsonl.gz','wt',encoding='utf8');inv=gzip.open(out/'inverse.jsonl.gz','wt',encoding='utf8')
    for number,spec in enumerate(definitions):
        index=93+number;cx,cy,cz=spec['center'];a,b,c,d=spec['box'];base=-61;height=82
        current={};cargo=nbtlib.List[nbtlib.Compound]()
        for y in range(height+4):
            for x in range(a,b+1):
                for z in range(c,d+1):
                    pos=(cx+x,base+y,cz+z);before=w.block(pos);assert before is not None
                    if before in AIR and pos not in tags:continue
                    entry=nbtlib.Compound({'Pos':nbtlib.Long(packed((x,y,z))),'State':state_tag(before)})
                    if pos in tags:entry['NBT']=tags[pos]
                    cargo.append(entry);current[pos]=entry
        assert len(cargo)>5000,'Incomplete authoritative imported tower; preserve actual failure, do not reconstruct template'
        desired={};roles={}
        def put(q,state,role):
            if q in desired and desired[q]!=state and role not in {'liner_to_ring_radial_bearing','complete_external_bearing_column','overhead_3x3_load_spreading_plate'}:raise RuntimeError(q)
            desired[q]=state;roles[q]=role
        for x in range(a,b+1):
            for z in range(c,d+1):
                for y in range(base,80):
                    q=(cx+x,y,cz+z)
                    if q not in current:put(q,'minecraft:air','clear_private_complete_rigid_shaft')
                saddle=(cx+x,base-1,cz+z)
                put(saddle,w.block(saddle) if w.block(saddle)=='minecraft:netherite_block' else LINER,'complete_private_endpoint_bearing_saddle')
        for y in range(base-1,80):
            for x in range(a-1,b+2):
                for z in range(c-1,d+2):
                    if x in (a-1,b+1) or z in (c-1,d+1):
                        q=(cx+x,y,cz+z)
                        put(q,'minecraft:netherite_block' if y==base-1 and w.block(q)=='minecraft:netherite_block' else LINER,'private_outside_sweep_continuous_liner')
        anchors=[];bearings=[]
        for x,z in ((a-3,c-3),(a-3,d+3),(b+3,c-3),(b+3,d+3)):
            footing=None
            for y in range(26,78):
                if all(w.get(cx+x+dx,yy,cz+z+dz) is not None and w.get(cx+x+dx,yy,cz+z+dz).partition('[')[0] in NATURAL and (cx+x+dx,yy,cz+z+dz) not in tags
                    for dx in (-1,0,1) for dz in (-1,0,1) for yy in (y,y+1)):footing=y;break
            if footing is None:held.append(dict(index=index,kind='NO_COMPLETE_MEASURED_PRIVATE_BEARING',xz=[cx+x,cz+z]));footing=26
            sx=-1 if x<0 else 1;sz=-1 if z<0 else 1
            for xx in (x,x+sx):
                for zz in (z,z+sz):
                    for y in range(20,footing):
                        put((cx+xx,y,cz+zz),IRON,'complete_external_bearing_column')
                        if 21<=y<=24:anchors.append((cx+xx,y,cz+zz))
            for dx in (-1,0,1):
                for dz in (-1,0,1):put((cx+x+dx,footing-1,cz+z+dz),IRON,'overhead_3x3_load_spreading_plate')
            bearings.append(dict(pad=[cx+x,footing-1,cz+z],bearing_y=footing,
                complete_two_layers=[[[cx+x+dx,yy,cz+z+dz],w.get(cx+x+dx,yy,cz+z+dz)] for dx in (-1,0,1) for dz in (-1,0,1) for yy in (footing,footing+1)]))
        for y in (20,24):
            for x in range(a-4,b+5):
                for z in range(c-4,d+5):
                    if x<a-2 or x>b+2 or z<c-2 or z>d+2:put((cx+x,y,cz+z),IRON,'private_connected_roof_ring_beam')
            for x in range(a-3,a):put((cx+x,y,cz),IRON,'liner_to_ring_radial_bearing')
            for x in range(b+1,b+4):put((cx+x,y,cz),IRON,'liner_to_ring_radial_bearing')
            for z in range(c-3,c):put((cx,y,cz+z),IRON,'liner_to_ring_radial_bearing')
            for z in range(d+1,d+4):put((cx,y,cz+z),IRON,'liner_to_ring_radial_bearing')
        building=nbtlib.Compound({'Centre':nbtlib.Long(packed(spec['center'])),'Origin':nbtlib.Long(packed((30,80,220))),
            'Height':nbtlib.Int(height),'Half':nbtlib.Int(11),'FixedStreetCore':nbtlib.Byte(0),'Cargo':cargo,
            'NegativeDomeAnchorMask':nbtlib.LongArray([packed(q) for q in anchors]),'R45RigidTopologyVersion':nbtlib.Int(1),
            'R45Footprint':nbtlib.Compound({k:nbtlib.Int(v) for k,v in zip(('MinX','MaxX','MinZ','MaxZ'),spec['box'])})})
        archive=out/'cargo'/f'projectseele_city_private_cargo_r45_{number}.dat'
        nbtlib.File({'DataVersion':nbtlib.Int(3465),'data':nbtlib.Compound({'Version':nbtlib.Int(1),'WorldUUID':nbtlib.String(identity),'Buildings':nbtlib.List[nbtlib.Compound]([building])})}).save(archive,gzipped=True)
        changes=0;local_holds=[]
        for q,after in sorted(desired.items()):
            before=w.block(q)
            if before==after:continue
            name=(before or '').partition('[')[0]
            allowed=before is not None and q not in tags and q not in current and (name in AIR or name in NATURAL or name in {IRON,LINER,'minecraft:smooth_stone','minecraft:sea_lantern','minecraft:deepslate_bricks','minecraft:deepslate_tiles'})
            if not allowed:
                hold=dict(index=index,pos=q,before=before,after=after,role=roles[q],full_nbt=tags[q].snbt() if q in tags else None);held.append(hold);local_holds.append(hold);continue
            value=dict(pos=q,before=before,after=after,before_nbt=None,after_nbt=None,owner=f'r45/private_city_rigid/{number}',reason=roles[q])
            f.write(json.dumps(value)+'\n');value['before'],value['after']=value['after'],value['before'];inv.write(json.dumps(value)+'\n');changes+=1;counts[roles[q]]+=1
        rows.append(dict(index=index,kind='private',center=spec['center'],height=height,half=11,footprint=dict(zip(('MinX','MaxX','MinZ','MaxZ'),spec['box'])),
            retracted_base_y=base,endpoint_delta_y=-142,full_cargo_cells=len(cargo),block_entities=sum('NBT'in cell for cell in cargo),
            new_negative_anchor_mask=anchors,overhead_bearings=bearings,changed_cells=changes,held=local_holds,
            archive=str(archive),archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest()))
    f.close();inv.close()
    report=dict(schema='projectseele.private-city-rigid-topology-r45.v1',world=str(world),world_id=identity,world_written=False,source_cargo_written=False,
        private_objects=3,changed_cells=sum(r['changed_cells'] for r in rows),changed_by_role=dict(counts),held=held,
        measured_regions=hashes,region_files_changed_during_read=[p for p,h in hashes.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h],
        native_shapes=False,root_structure_art_review=False,candidate_ready_for_apply=False,records=rows)
    (out/'topology.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items() if k not in ('records','held','measured_regions')},indent=2));print('holds',len(held))


if __name__=='__main__':main()

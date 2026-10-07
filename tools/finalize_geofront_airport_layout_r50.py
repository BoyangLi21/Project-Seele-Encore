"""Join exact civil layouts and one new plane factory NBT; no world writes."""
from pathlib import Path
import json,uuid
import nbtlib

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'artifacts/rebuild_r50/underground_airport'

def main():
    uid=json.loads((P/'aircraft_uuid.json').read_text('utf8'))['aircraft_uuid']
    value=uuid.UUID(uid).int
    ints=[(value>>s)&0xffffffff for s in(96,64,32,0)]
    ints=[v-0x100000000 if v>=0x80000000 else v for v in ints]
    tag=nbtlib.Compound({'id':nbtlib.String('projectseele:un_transport'),'UUID':nbtlib.IntArray(ints),
        'Pos':nbtlib.List[nbtlib.Double]([nbtlib.Double(v)for v in(-440,-464,-270)]),
        'Motion':nbtlib.List[nbtlib.Double]([nbtlib.Double(0)]*3),
        'Rotation':nbtlib.List[nbtlib.Float]([nbtlib.Float(0)]*2),
        'NoGravity':nbtlib.Byte(1),'Invulnerable':nbtlib.Byte(1),'Air':nbtlib.Short(300),'Fire':nbtlib.Short(-1),
        'FallDistance':nbtlib.Float(0),'PortalCooldown':nbtlib.Int(0),'OnGround':nbtlib.Byte(0),
        'NervAircraft':nbtlib.Byte(1),'UNSerial':nbtlib.Int(50),'Cargo':nbtlib.Byte(0),'Kind':nbtlib.Int(0),
        'Deploy':nbtlib.Float(0),'HoistDistance':nbtlib.Float(112)})
    entity=P/'new_underground_plane_candidate.snbt';entity.write_text(tag.snbt(),'utf8')
    receiver=json.loads((P/'candidates/receiver/receiver_layout.json').read_text('utf8'))
    airport=json.loads((P/'candidates/airport/airport_layout.json').read_text('utf8'))
    nodes=[dict(id='airport',pos=[-440,-464,-270],yaw=0,empty_only=True),
           dict(id='airportLift',pos=[-440,-260,-270]),dict(id='northLane',pos=[-440,-260,100.5]),
           dict(id='laneMid',pos=[-200,-260,100.5])]
    edges=[['airport','airportLift'],['airportLift','northLane'],['northLane','laneMid']]
    for v,x in enumerate((-11.5,30.5,72.5)):
        nodes.extend([dict(id=f'receiver_{v}',pos=[x,-260,100.5]),dict(id=f'drop_{v}',pos=[x,-298,100.5],yaw=180)])
        edges.extend([['laneMid',f'receiver_{v}'],[f'receiver_{v}',f'drop_{v}']])
    air=[dict(id='park_yaw0',bounds=[[-512,-475,-330],[-368,-396,-208]],yaw=0),
        dict(id='west_vertical_and_north',bounds=[[-536,-438,-366],[-344,-237,196]]),
        dict(id='south_receiving_lane',bounds=[[-536,-411,5],[169,-237,196]]),
        dict(id='west_natural_pickup',bounds=[[-796,-491,-496],[-114,-237,-4]])]
    zones=[dict(id='measured_northwest_cavern_field',bounds=[[-700,-489,-400],[-210,-455,-100]])]
    for v,x in enumerate((-11.5,30.5,72.5)):
        zones.append(dict(id=f'receiver_pickup_{v}',bounds=[[x-17,-413,83],[x+17,-408,118]]))
    geometry=dict(schema=50,installed=False,dimension='projectseele:geofront',domain_id='geofront_main_cavern_r50',
        aircraft_uuid=uid,aircraft_nbt_candidate=str(entity),airport_stand=[-440,-464,-270],airport_yaw=0,
        airport_node='airport',nodes=nodes,edges=edges,airspace=air,pickup_zones=zones,
        receivers=[dict(variant=r['variant'],drop_feet=r['feet'],drop_yaw=180,node=f'receiver_{r["variant"]}')for r in receiver['receivers']],
        all_yaw_planning_radius=95,hoist_offset=112,
        pickup_scope='Measured west free-field and installed receivers; further domains require actual connected main-cavern geometry',
        airspace_is_operational_domain_not_permission_to_erase_current_obstacles=True,
        current_bearing_contact_and_pad_guards_preserved=True,world_written=False,native_verified=False)
    (P/'flight_geometry_candidate.json').write_text(json.dumps(geometry,ensure_ascii=False,indent=2),'utf8')
    marker=dict(schema=50,installed=False,dimension='projectseele:geofront',receivers=receiver['receivers'],
        crew_redirects=receiver['crew_redirects'],airport=airport,aircraft_uuid=uid,
        original_surface_UN_aircraft_untouched=True,world_written=False,native_verified=False)
    (P/'r50_underground_airport.json').write_text(json.dumps(marker,ensure_ascii=False,indent=2),'utf8')
    world=ROOT/'artifacts/rebuild_r49/construction/SEELE_R49_WORLD'
    before=json.loads((world/'r50_underground_airport.json').read_text('utf8'))if(world/'r50_underground_airport.json').exists()else None
    (P/'airport_marker_metadata_patch.json').write_text(json.dumps(dict(schema=50,operations=[dict(relative_target='r50_underground_airport.json',before=before,after=marker)],world_written=False),ensure_ascii=False,indent=2),'utf8')
    print(uid,len(nodes),'nodes',len(edges),'edges; candidate only',flush=True)

if __name__=='__main__':main()

"""Offline spatial hypothesis only: preserve roots and source faces above bay floor.

Does not author a production actuator, edit a world, or certify route bearing.
The payload, plugs, bridges and rear track heads must be rebased consistently
before a spatially clear candidate could become an operable machine.
"""
import argparse
import copy
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frames',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--floor-offset',type=float,default=4.25)
    p.add_argument('--stroke',type=float,default=1.0)
    a=p.parse_args()
    assert a.floor_offset>4.0078125 and 0<a.stroke<3
    source=json.loads(a.frames.read_text('utf8'));out=copy.deepcopy(source)
    out['kinematics']='UNINSTALLED SPATIAL HYPOTHESIS: source production rise frames, below-floor stroke replaced by declared above-floor stroke'
    out['hypothesis']={'carrier_local_y_offset':a.floor_offset,'bay_body_stroke':a.stroke,
        'world_written':False,'installed':False,'controller_roots_unchanged':True,
        'payload_plug_bridge_bearing_proven':False,'rear_track_bearing_proven':False,
        'source_faces_changed':False,'production_actuator':False}
    for row in out['poses']:
        rise=row['rise'];fraction=max(0,1-rise/.8999999761581421)
        row['leg']+='/above_floor_hypothesis'
        for part,frame in zip(out['parts'],row['frames']):
            deck=part['name'] in ('carrier/deck','carrier/toe_l','carrier/toe_r')
            # Bay roots in the native export are upright. No rotated global-Y
            # assumption is permitted for other route frames.
            assert abs(row['root'][3])+abs(row['root'][5])<1e-10
            frame[1]+=a.floor_offset+(0 if deck else (64-a.stroke)*fraction)
    a.output.write_text(json.dumps(out,separators=(',',':')),'utf8')
    print('uninstalled_spatial_hypothesis',len(out['poses']),'frames',a.floor_offset,a.stroke)


if __name__=='__main__':main()

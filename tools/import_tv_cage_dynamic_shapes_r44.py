"""Validate a real current-state native cage export for QA/navigation consumers."""
from pathlib import Path
import argparse,hashlib,json

ROOT=Path(__file__).resolve().parents[1]


class DynamicCageShapes:
    def __init__(self,path,resource):
        self.source=Path(path)
        self.document=json.loads(self.source.read_text(encoding='utf8'))
        d=self.document
        assert d['schema']==44 and d['geometry_enabled'] and d['dimension']=='projectseele:geofront'
        assert Path(d['world']).name=='SEELE_FIELD_R44_REVIEW'
        assert d['resource_sha256']==hashlib.sha256(Path(resource).read_bytes()).hexdigest(),'Native/source geometry hashes differ; do not promote the snapshot'
        rows=d['actual_gantries'];assert len(rows)==3 and {r['variant'] for r in rows}=={0,1,2}
        assert all(r['gantry_uuid'] and 0<=r['closed']<=1 and len(r['world_aabbs'])>100 for r in rows)
        self.cache_key=(d['resource_sha256'],tuple((r['variant'],r['gantry_uuid'],r['closed']) for r in rows))
        self.boxes=[box for r in rows for box in r['world_aabbs']]
        assert all(len(b)==6 and all(b[i]<b[i+3] for i in range(3)) for b in self.boxes)

    def intersections(self,query):
        return [b for b in self.boxes if all(query[i+3]>b[i] and query[i]<b[i+3] for i in range(3))]

    def support_top(self,x,z,maximum_y):
        values=[b[4] for b in self.boxes if b[0]<=x<=b[3] and b[2]<=z<=b[5] and b[4]<=maximum_y+.04]
        return max(values) if values else None


def main():
    p=argparse.ArgumentParser();p.add_argument('--native-export',type=Path,required=True)
    p.add_argument('--resource',type=Path,default=ROOT/'src/main/resources/assets/projectseele/mesh/tv_shoulder_shells_r44.json')
    p.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r44/hangar_machinery/tv_shoulder_shells_v1/native_dynamic_shapes')
    args=p.parse_args();actual=DynamicCageShapes(args.native_export,args.resource);args.out.mkdir(parents=True,exist_ok=True)
    report={'source':str(actual.source),'source_sha256':hashlib.sha256(actual.source.read_bytes()).hexdigest(),
        'cache_identity':actual.cache_key,'actual_bay_states':actual.document['actual_gantries'],
        'shape_count':len(actual.boxes),'actual_consumers':'Native Entity.collide + explicit DynamicCageShapes.intersections/support_top QA outlet',
        'not_consumers':'Block-only nav export, nearestLift cache, block raycasts and NPC pathfinding are not silently claimed to include these equipment surfaces',
        'public_route_added':False,'native_walk_passed':False,'occupied_stop_passed':False,'cold_reload_passed':False}
    (args.out/'dynamic_shape_contract.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('Actual dynamic machinery snapshot validated:',len(actual.boxes),'world AABBs; movement/occupancy/cold reload remain pending')


if __name__=='__main__':main()

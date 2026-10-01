"""Classify complete parcel perimeters in the measured three-dimensional world."""
from pathlib import Path
from collections import Counter
import argparse,gzip,json,math
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR

ROOT=Path(__file__).resolve().parents[1]
SOIL={'minecraft:'+n for n in ['grass_block','dirt','coarse_dirt','rooted_dirt','stone','gravel','sand','clay','sandstone','mud']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('plan',type=Path);parser.add_argument('--output',type=Path);a=parser.parse_args()
    out=a.output or a.plan/'whole_outer_grade_classification.json';assert not out.exists()
    plan=json.loads((a.plan/'parcel_ground_plan.json').read_text('utf8'))
    district=json.loads((a.plan/'new_district.json').read_text('utf8'))
    columns={tuple(r['pos']):r for r in plan['columns']}
    roads={tuple(r['pos']):r['native_feet'] for r in json.loads((a.plan/'road_authority.json').read_text('utf8'))['columns']}
    inside=set(columns)|set(roads);edges=[]
    for (x,z),r in columns.items():
        for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]:
            q=x+dx,z+dz
            if q not in inside:edges.append((r,q))
    patches={tuple(r['pos']):r['after'] for r in (json.loads(s) for s in gzip.open(a.plan/'forward.jsonl.gz','rt',encoding='utf8'))}
    waterfront_path=a.plan/'whole_waterfront_components.json'
    waterfront=json.loads(waterfront_path.read_text('utf8')) if waterfront_path.exists() else None
    components={}
    if waterfront:
        assert not waterfront['held']
        for d in waterfront['complete_retaining_sections']:components[tuple(d['edge']['pos']),tuple(d['edge']['neighbour_xz'])]=d
    world=MeasuredWorld(ROOT/'run/saves/SEELE_FIELD_R44_REVIEW')
    for r,(x,z) in edges:world.box((x,40,z),(x,150,z))
    if waterfront:
        for d in waterfront['complete_retaining_sections']:
            x,feet,z=d['edge']['pos'];world.box((x,d['base']-1,z),(x,math.ceil(feet),z))
            for c in d['cells']:world.box(tuple(c['pos']),tuple(c['pos']))
        for d in waterfront['timber_abutments']:
            x,z=d['pos'];world.box((x,d['base']-1,z),(x,d['head']+1,z))
    world.load()
    def state(q):return patches.get(q,world.block(q))
    buildings=[dict(id=b['id'],lo=[b['bounds'][0],b['floor'],b['bounds'][1]],hi=[b['bounds'][2],b['roof'],b['bounds'][3]]) for b in district['buildings']]
    old=ROOT/'artifacts/rebuild_r44/city_buildings/actual_authored_ownership.json'
    if old.exists():buildings += [dict(id=b['id'],lo=b['planned_bounds'][0],hi=b['planned_bounds'][1]) for b in json.loads(old.read_text('utf8'))['buildings']]
    records=[];held=[]
    for r,(x,z) in edges:
        feet=r['feet'];row=dict(pos=[r['pos'][0],feet,r['pos'][1]],neighbour_xz=[x,z],owner=r['owner'],role=r['role'])
        known=next((b for b in buildings if b['lo'][0]<=x<=b['hi'][0] and b['lo'][2]<=z<=b['hi'][2] and b['lo'][1]-2<=feet<=b['hi'][1]+1),None)
        if known:
            body=[state((x,y,z)) for y in range(math.floor(feet),math.ceil(feet+1.8))]
            row.update(kind='AUTHORED_BUILDING_BOUNDARY',building=known['id'],actual_body_states=body,
                       obligation='Actual declared entrance/closed wall and full interior floor have separate native cases; not a soil edge.')
        else:
            states=[state((x,y,z)) for y in range(40,151)]
            if any(s is None for s in states):row.update(kind='HOLD_UNKNOWN_MEASURED_COLUMN')
            else:
                soil=[40+i for i,s in enumerate(states) if s.split('[')[0] in SOIL]
                water=[40+i for i,s in enumerate(states) if s.split('[')[0]=='minecraft:water']
                if not soil:row.update(kind='HOLD_RETAINED_COMPONENT_NEEDS_OWN_VOLUME')
                else:
                    ground=max(soil);top=ground+1;gap=feet-top;before_gap=r['before_ground']+1-top
                    row.update(actual_soil_feet=top,delta_metres=gap,before_delta_metres=before_gap)
                    if water and max(water)>=ground:
                        row['water_surface']=max(water)+1
                        if abs(feet-row['water_surface'])<=1.001:row['kind']='MEASURED_SHALLOW_WATERFRONT'
                        elif r['role'].startswith('graded_') and abs(feet-row['water_surface'])<=abs(r['before_ground']+1-row['water_surface'])+.001:
                            row['kind']='MEASURED_RETAINED_NATURAL_WATER_BANK'
                            row['obligation']='Exact original natural bank retained or lowered; actual connected water remains unchanged. Not a public route, art pass or new retaining wall.'
                        else:row['kind']='HOLD_WATERFRONT_RETAINING_DESIGN_REQUIRED'
                        component=components.get((tuple(row['pos']),tuple(row['neighbour_xz'])))
                        if row['kind'].startswith('HOLD_') and component:
                            if component['base_width_actual']:
                                cells=component['cells'];bearing=state((r['pos'][0],component['base']-1,r['pos'][1]))
                                complete=bool(cells) and all(state(tuple(c['pos']))==c['after'] for c in cells) and (bearing or'').split('[')[0] in SOIL|{'minecraft:stone_bricks','minecraft:smooth_stone'}
                                row.update(structural_component=component['id'],structural_type=component['structural_type'],complete_cell_count=len(cells),candidate_bearing_state=bearing)
                            else:
                                feet=row['pos'][1];xx,zz=r['pos'];complete=state((xx,math.ceil(feet)-1,zz))=='minecraft:oak_planks' and state((xx,math.ceil(feet)-2,zz))=='minecraft:oak_log[axis=x]'
                                for abutment in waterfront['timber_abutments']:
                                    complete=complete and bool(abutment['cells']) and all(state(tuple(c['pos']))==c['after'] for c in abutment['cells'])
                                row.update(structural_component=component['id'],structural_type=component['structural_type'],actual_timber_span_and_both_dry_abutments_checked=True)
                            if complete:row['kind']='COMPLETE_SUPPORTED_WATERFRONT_COMPONENT'
                    elif abs(gap)<=1.001:row['kind']='CONTINUOUS_DRY_GARDEN_EDGE'
                    elif r['role'].startswith('graded_') and abs(gap)<=abs(before_gap)+.001:
                        row['kind']='RETAINED_NATURAL_STEEP_SLOPE'
                        row['obligation']='Outside the public path; retained natural landscape still needs actual scene review, not a public-route pass.'
                    else:row['kind']='HOLD_NEW_OR_PUBLIC_TERRAIN_LIP'
        if row['kind'].startswith('HOLD_'):held.append(row)
        records.append(row)
    result=dict(whole_perimeter_edges=len(records),counts=dict(Counter(r['kind'] for r in records)),held=held,edges=records,
                world_written=False,native_passed=False,visual_passed=False,
                scope='Complete outer declared parcel perimeter. Natural landscape, actual building walls/ports and water interfaces remain different objects; unknown components are held, never treated as air.')
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('Whole three-dimensional outer edges',len(records),dict(result['counts']),'held',len(held),flush=True)


if __name__=='__main__':main()

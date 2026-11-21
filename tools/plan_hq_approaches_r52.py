"""Root-only HQ approach candidate. Original external endpoints are fixed.

The short west U2 link cannot descend 93 metres within 32 metres of track.
Finite descent circuits are candidate civil engineering, not installed rails.
Native MTR sampling and complete conflict checks are mandatory before writing.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    originals=json.loads((ROOT/'artifacts/r52_hq_rail_boundary/hq_ten_rails.json').read_text('utf8'))
    segments=[];routes={}
    def add(name,a,angle_a,b,angle_b,source):
        segments.append(dict(id=name,from_angle=angle_a,to_angle=angle_b,shape='TWO_RADII',vertical_radius=100,
            **{'from':a,'to':b},source_original_indices=source));return name
    def clockwise(name,start,radius,end_y,source):
        x,y,z=start;dy=end_y-y
        points=[start,[x+radius,round(y+dy*.25),z+radius],[x,round(y+dy*.5),z+2*radius],
                [x-radius,round(y+dy*.75),z+radius],[x,end_y,z]]
        forward=['E','S','W','N'];backward=['N','E','S','W']
        return [add(name+'_'+str(i),points[i],forward[i],points[i+1],backward[i],source) for i in range(4)]
    west_u2=clockwise('u2_west_descent',[-34,-467,522],220,-560,[0])
    west_u2.append(add('u2_west_station_threshold',[-34,-560,522],'E',[-2,-560,522],'W',[0]));routes['original_0']=west_u2
    west_u1=[add('u1_west_retained_station_threshold',[-298,-467,785],'E',[-274,-467,785],'W',[6,8])]
    west_u1+=clockwise('u1_west_descent',[-274,-467,785],200,-520,[6,8])
    west_u1.append(add('u1_west_lower_turn',[-274,-520,785],'E',[-230,-542,550],'S',[6,8]))
    west_u1.append(add('u1_west_station_approach',[-230,-542,550],'N',[-50,-560,490],'W',[6,8]))
    for old,z in ((6,486),(8,494)):
        routes[f'original_{old}']=west_u1+[add(f'u1_west_platform_{z}',[-50,-560,490],'E',[-2,-560,z],'W',[old])]
    # Concentric paired east approaches stay eight metres apart. Three
    # quarters of a circuit produce the original end tangent directly.
    for old,z,radius in ((2,486,160),(3,494,168)):
        name=f'u1_east_{z}'
        cx,cz=470,330
        nodes=[[cx,-545,cz+radius],[cx+radius,-523,cz],[cx,-502,cz-radius],[cx-radius,-480,cz]]
        chain=[add(name+'_approach',[62,-560,z],'E',nodes[0],'W',[old])]
        for i in range(3):chain.append(add(name+'_rise_'+str(i),nodes[i],['E','N','W'][i],nodes[i+1],['S','E','N'][i],[old]))
        chain.append(add(name+'_merge',nodes[-1],'S',[310,-480,370],'N',[old]))
        routes[f'original_{old}']=chain
    u1_east_shared=add('u1_east_rise_to_retained_station',[310,-480,370],'S',[310,-467,505],'N',[2,3])
    u1_east_threshold=add('u1_east_original_endpoint',[310,-467,505],'S',[310,-467,533],'N',[2,3])
    for old in (2,3):routes[f'original_{old}'] += [u1_east_shared,u1_east_threshold]
    u2_east_shared=add('u2_east_common_approach',[62,-560,522],'E',[430,-544,518],'W',[4,5])
    for old,x,radius in ((4,296,192),(5,304,184)):
        name=f'u2_east_{x}'
        cx,cz=488,706
        nodes=[[cx,-541,cz-radius],[cx+radius,-519,cz],[cx,-498,cz+radius],[cx-radius,-480,cz]]
        chain=[u2_east_shared,add(name+'_approach',[430,-544,518],'E',nodes[0],'W',[old])]
        for i in range(3):chain.append(add(name+'_rise_'+str(i),nodes[i],['E','S','W'][i],nodes[i+1],['N','E','S'][i],[old]))
        # Stay east of the entire research district, including Sigma's deep
        # foundation and the three eastern laboratories, before turning back
        # after their northern edge. Preserving the station alone is not enough.
        # Explicit concentric bends preserve eight metres between tracks.
        # Independent S-curves with merely offset endpoints can cross.
        south_z=646 if old==4 else 654;east_x=490 if old==4 else 498;north_z=300 if old==4 else 292
        bypass=[(nodes[-1],'N'),([356,-480,south_z],'E'),([430,-480,south_z],'E'),
                ([east_x,-478,586],'N'),([east_x,-474,360],'N'),([430,-471,north_z],'W'),
                ([356,-469,north_z],'W'),([x,-467,240],'N')]
        opposite={'N':'S','E':'W','S':'N','W':'E'}
        for j,((a,heading),(b,next_heading)) in enumerate(zip(bypass,bypass[1:])):
            chain.append(add(name+'_research_district_bypass_'+str(j),a,heading,b,opposite[next_heading],[old]))
        chain.append(add(name+'_original_endpoint',[x,-467,240],'N',[x,-467,212],'S',[old]))
        routes[f'original_{old}']=chain
    for old in (1,7,9):
        d=originals[old]['data'];a=[d['position1'][k] for k in ('x','y','z')];b=[d['position2'][k] for k in ('x','y','z')];a[1]-=93;b[1]-=93
        routes[f'original_{old}']=[add(f'platform_{old}',a,d['angle1'],b,d['angle2'],[old])]
    out=ROOT/'artifacts/r52_hq_approach_candidate';out.mkdir(exist_ok=True)
    document=dict(schema='projectseele.r52.root-hq-approach-candidate.v1',status='design_not_installed',map_author='root',
        original_station_and_platform_ids_unchanged=True,all_non_HQ_stations_rails_vehicles_untouched=True,
        only_original_indices=list(range(10)),routes=routes,segments=segments,
        required=['native curve validity/grade','shared direction and graph connectivity','whole train/tunnel collision and retained-rail clearance',
                  'actual terrain and structure inventory','original MTR vehicle/path provenance preservation'])
    (out/'CANDIDATE.json').write_text(json.dumps(document,indent=2),'utf8');print(out/'CANDIDATE.json')


if __name__=='__main__':main()

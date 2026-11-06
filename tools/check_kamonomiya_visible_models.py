"""Sweep offline visible MTR model geometry along both straight station tracks.

Uses the primary agent's decoded cube vertices and declared door motions; does
not open a JAR, native database, server or world. Each integer Y band is clipped
exactly in projected XY, with 0.03m vertical and lateral margins. The complete
straight station span is swept continuously, including the 10.627m maximum
longitudinal model extent plus 0.03m. This is not a rendered-frame acceptance.
"""
import argparse,itertools,json,math
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from query_blocks import AIR

def clipped_half_width(vertices,slide,low,high):
    offsets=np.asarray(list(itertools.product((-slide[0],slide[0]),(-slide[1],slide[1]))))
    v=(vertices[None,:,:2]+offsets[:,None,:]).reshape(-1,2)
    values=list(v[(v[:,1]>=low)&(v[:,1]<=high),0])
    i,j=np.triu_indices(len(v),1);a,b=v[i],v[j];dy=b[:,1]-a[:,1]
    for y in(low,high):
        keep=(np.abs(dy)>1e-12)&((a[:,1]-y)*(b[:,1]-y)<=0)
        t=(y-a[keep,1])/dy[keep];values.extend(a[keep,0]+t*(b[keep,0]-a[keep,0]))
    return max(map(abs,values))if values else None

def verify(candidate,models,out,write=True):
    native=json.loads((candidate/'native-station-plan.json').read_text('utf8'));e=Editor(candidate);margin=.03
    rows=[];errors=[];all_obstacles=[]
    for ident in('eidan_9000_cab_1','eidan_9000_trailer','eidan_9000_cab_2'):
        report=json.loads((models/(ident+'.json')).read_text('utf8'))
        if not report['all_selected_conditions_enclosed']:raise ValueError('Visible model condition coverage is incomplete')
        with np.load(models/(ident+'-visible-cubes.npz'))as f:cubes=f['cubes'];slides=f['door_slides'];names=list(map(str,f['names']))
        lo=np.min(cubes.reshape(-1,3),0)-np.max(slides,0);hi=np.max(cubes.reshape(-1,3),0)+np.max(slides,0)
        longitudinal=max(10.627,max(abs(float(report['visible_motion_bounds'][i][2]))for i in(0,1)))+margin
        bands=[]
        for y in range(math.floor(float(lo[1])-margin),math.ceil(float(hi[1])+margin)):
            widths=[]
            for v,slide,name in zip(cubes,slides,names):
                w=clipped_half_width(v,slide,y-margin,y+1+margin)
                if w is not None:widths.append((w,name))
            if not widths:continue
            w,name=max(widths);bands.append(dict(y=[y,y+1],clipped_visible_half_width=w,lateral_margin=margin,swept_half_width=w+margin,widest_part=name))
        obstacles=[];tested=0
        for rail in native['rails']:
            start,end=rail['from'],rail['to']
            if start[1:]!=end[1:] or rail['from_angle']!='E'or rail['to_angle']!='W':raise ValueError('This proof requires strictly east-west flat tracks')
            X0,X1=min(start[0],end[0])+.5-longitudinal,max(start[0],end[0])+.5+longitudinal;zc=start[2]+.5;floor=start[1]
            for band in bands:
                y=floor+band['y'][0];z0,z1=zc-band['swept_half_width'],zc+band['swept_half_width']
                for z in range(math.floor(z0),math.ceil(z1)):
                    for x in range(math.floor(X0),math.ceil(X1)):
                        state=e.state(x,y,z);tested+=1
                        # Full-cube treatment of every non-air block is
                        # conservative for panes, posts and other partial blocks.
                        if state.split('[')[0]not in AIR|{'minecraft:light'}:obstacles.append(dict(rail=rail['id'],xyz=[x,y,z],state=state,y_band=band['y']))
        if obstacles:errors.append(ident+': visible swept model intersects station blocks')
        all_obstacles.extend(obstacles)
        floor_band=next(q for q in bands if q['y']==[0,1]);visible_floor_gap=1.5-floor_band['clipped_visible_half_width']
        rows.append(dict(vehicle=ident,cubes=len(cubes),bands=bands,longitudinal_half_extent_with_margin=longitudinal,block_tests=tested,obstacle_count=len(obstacles),obstacles=obstacles[:30],
            platform_floor_visible_gap_after_vertical_margin_before_lateral_margin=visible_floor_gap,platform_floor_residual_clearance_after_margins=visible_floor_gap-margin,
            native_two_metre_calibration_gap=.5,actual_visible_gap_is_not_the_native_calibration_gap=True))
    proof=dict(errors=errors,candidate=str(candidate),model_source=str(models),margin=margin,vehicles=rows,obstacle_count=len(all_obstacles),continuous_straight_sweep=True,
        clipping='all translated cube corners plus every pairwise intersection with Y-band boundaries; vertical band widened by 0.03m, lateral width expanded by 0.03m',
        rendered_frame_verified=False,native_boarding_runtime_verified=False,all_line_vehicle_sweep_complete=False,world_written=False)
    if write:out.write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf8')
    print('Visible station model sweep:',len(all_obstacles),'obstacles;',[(q['vehicle'],round(q['platform_floor_residual_clearance_after_margins'],6))for q in rows],flush=True)
    if errors:raise ValueError(errors)
    return proof

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('candidate','models','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();verify(a.candidate,a.models,a.out)

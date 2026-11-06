"""Independent visible-model sweep for a straight, level mainline station.

The envelope uses installed model cubes clipped into rail-relative metre bands,
including declared door slides. Native metadata width alone is not accepted.
All longitudinal positions across the platform are enclosed analytically; the
model envelope extends past both platform ends. No world or native DB is opened.
"""
import argparse,json,math
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from query_blocks import AIR

def check(candidate,models):
    native=json.loads((candidate/'native-station-plan.json').read_text('utf8'))
    summary=json.loads((models/'summary.json').read_text('utf8'))
    bands=json.loads((models/'platform-height-bands.json').read_text('utf8'))
    source=json.loads((models/'resource-source-check.json').read_text('utf8'))
    assert not source['project_jar_overrides']and not any(r['overrides']for r in source['enabled_resource_pack_checks'])
    assert source['gangway_contained_by_body_bands']
    widths=[max(r['bands'][i]['half_width']for r in bands)for i in range(4)]
    half_length=max(abs(r['visible_motion_bounds'][side][2])for r in summary['vehicles']for side in(0,1))
    margin=.03;errors=[];rails=[];e=Editor(candidate)
    for rail in native['rails']:
        a,b=rail['from'],rail['to']
        if a[1]!=b[1]or a[2]!=b[2]or{rail['from_angle'],rail['to_angle']}!={'E','W'}:raise ValueError('This verifier only supports straight level east-west platforms')
        start,end=sorted([a[0]+.5,b[0]+.5]);l=start-half_length-margin;r=end+half_length+margin;centre=a[2]+.5;rail_y=a[1]
        rows=[]
        for i,half_width in enumerate(widths):
            low,high=centre-half_width-margin,centre+half_width+margin
            obs=[];tested=0
            # Positive-volume intersections only; the full model band is
            # deliberately conservative within each one-block Y interval.
            for x in range(math.floor(l),math.ceil(r)):
                for z in range(math.floor(low),math.ceil(high)):
                    tested+=1;state=e.state(x,rail_y+i,z)
                    if state.split('[')[0]not in AIR|{'minecraft:light'}:obs.append([x,rail_y+i,z,state])
            rows.append(dict(rail_relative_y=[i,i+1],half_width=half_width,margin=margin,checked_cells=tested,obstacles=obs))
            if obs:errors.append(dict(rail=rail['id'],band=i,obstacle_count=len(obs)))
        rails.append(dict(id=rail['id'],native_length=end-start,rail_y=rail_y,centre_z=centre,longitudinal_sweep=[l,r],bands=rows))
    report=dict(errors=errors,model_source=str(models),native_metadata_width=2,visible_maximum_width=max(widths)*2,visible_half_width_at_platform_height=widths[0],model_nose_half_length=half_length,rails=rails,all_straight_platform_positions_enclosed=True,declared_door_slide_enclosed=True,resource_overrides_checked=True,world_written=False,rendered_frame_verified=False,live_boarding_verified=False)
    (candidate/'visible-model-clearance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Visible model station clearance:',len(errors),'errors;',sum(b['checked_cells']for r in rails for b in r['bands']),'cells;',round(max(widths)*2,6),'maximum visible width',flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--models',type=Path,required=True);a=p.parse_args()
    if check(a.candidate,a.models)['errors']:raise SystemExit(1)

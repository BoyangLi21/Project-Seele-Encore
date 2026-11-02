"""Check dense native boat geometry against measured blocks, without world writes.

The model calculation uses the selected installed parts, rounded native cube
sizes and inflation. It is a mathematical envelope, not a rendered-frame test.
"""
import argparse, json, math, zipfile
from itertools import product
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from author_hakone_lakefront import Editor


def boat_model(jar):
    parts=[]
    with zipfile.ZipFile(jar) as archive:
        def read(resource):
            ns, name=resource.split(':');return json.loads(archive.read('assets/'+ns+'/'+name))
        car=next(v for v in json.loads(archive.read('assets/mtr/mtr_custom_resources.json'))['vehicles']
                 if v['id']=='dark_oak_boat_medium_two_level')
        for key, bogie in (('models',0),('bogie2Models',car['bogie2Position'])):
            for model in car[key]:
                geometry=read(model['modelResource']);props=read(model['modelPropertiesResource'])
                definitions={v['name']:v for v in read(model['positionDefinitionsResource'])['positionDefinitions']}
                elements={v['uuid']:v for v in geometry['elements']};groups={}
                def index(node):
                    if isinstance(node,dict):
                        groups[node['name']]=node
                        for child in node.get('children',[]):index(child)
                for node in geometry['outliner']:index(node)
                def rotate(points,node):
                    origin=np.asarray(node.get('origin',[0,0,0]))
                    return Rotation.from_euler('xyz',node.get('rotation',[0,0,0]),degrees=True).apply(points-origin)+origin
                def vertices(node):
                    if isinstance(node,str):
                        v=elements[node];a=np.asarray(v['from']);b=np.asarray(v['to']);size=np.floor(b-a+.5)
                        lo=np.r_[b[:2]-size[:2],a[2]];hi=np.r_[b[:2],a[2]+size[2]];inflate=v.get('inflate',0)
                        return rotate(np.asarray(list(product(*zip(lo-inflate,hi+inflate)))),v)
                    return rotate(np.concatenate([vertices(c)for c in node['children']]),node)
                for part in props['parts']:
                    for definition in part['positionDefinitions']:
                        for flipped,position_key in ((False,'positions'),(True,'positionsFlipped')):
                            for position in definitions.get(definition,{}).get(position_key,[]):
                                for name in part['names']:
                                    points=vertices(groups[name])*(np.array([-1,1,-1])if flipped else 1)
                                    points+=np.array([position.get(k,0)for k in ('x','y','z')]);points/=16
                                    points[:,1]+=props.get('modelYOffset',0)
                                    # Native model coordinates reverse BB Z. A symmetric longitudinal
                                    # envelope also covers the rudder's separate rear-bogie origin.
                                    points[:,2]*=-1;points[:,2]+=bogie
                                    parts.append(dict(name=name,kind=part.get('type','VISUAL'),
                                        lo=points.min(0).tolist(),hi=points.max(0).tolist(),
                                        door_slide=abs(part.get('doorZMultiplier',0))/16))
    visual=[p for p in parts if p['kind']=='VISUAL']
    lo=np.min([p['lo']for p in visual],axis=0);hi=np.max([p['hi']for p in visual],axis=0)
    half_width=max(abs(lo[0]),abs(hi[0]));half_length=max(abs(lo[2]),abs(hi[2]))
    # Door animation slides longitudinally and stays inside this same bound.
    half_length=max(half_length,max(max(abs(p['lo'][2]),abs(p['hi'][2]))+p['door_slide']*1.2 for p in visual))
    return dict(vehicle=car['id'],parts=parts,visual_bounds=[lo.tolist(),hi.tolist()],
                half_width=float(half_width),half_length=float(half_length),
                doorway_y=[p['lo'][1]for p in parts if p['kind']=='DOORWAY'],
                rendered_frame_test=False)


def swept_columns(rows,half_width,half_length,margin=.03):
    """Rasterize the entire rectangular envelope, not just centre/corner probes.

    Each native interval <= 0.125 m is covered by its midpoint envelope enlarged
    by half its displacement and a rotation bound from the adjoining samples.
    Near joins the same symmetric envelope covers either direction of travel.
    """
    result=[]
    for row in rows:
        points=np.asarray(row['points'])[:,[0,2]]
        segments=points[1:]-points[:-1];lengths=np.linalg.norm(segments,axis=1)
        units=segments/lengths[:,None];columns=set()
        turns=np.arccos(np.clip(np.sum(units[:-1]*units[1:],axis=1),-1,1))
        for i,(p,q,axis,d) in enumerate(zip(points[:-1],points[1:],units,lengths)):
            angular=max(turns[max(0,i-1):i+1],default=0)
            slack=margin+half_length*angular
            normal=np.array([-axis[1],axis[0]]);centre=(p+q)/2
            length=half_length+slack+d/2;width=half_width+slack
            corners=np.array([centre+axis*s*length+normal*t*width
                              for s,t in ((-1,-1),(-1,1),(1,1),(1,-1))])
            x0,z0=np.floor(corners.min(0)).astype(int);x1,z1=np.floor(corners.max(0)).astype(int)
            grid=np.stack(np.meshgrid(np.arange(x0,x1+1),np.arange(z0,z1+1)),axis=-1).reshape(-1,2)
            delta=grid+.5-centre
            # Separating axis test: native oriented rectangle against each
            # whole unit block square, including all four separating axes.
            overlap=(np.abs(delta@axis)<length+.5*np.abs(axis).sum()-1e-8)
            overlap&=np.abs(delta@normal)<width+.5*np.abs(normal).sum()-1e-8
            extent=np.abs(axis)*length+np.abs(normal)*width
            overlap&=(np.abs(delta)<extent+.5-1e-8).all(axis=1)
            columns.update(map(tuple,grid[overlap].tolist()))
        result.append((row,columns))
    return result


def check(editor, rows,model):
    report=[];all_columns=set()
    low=math.floor(99+model['visual_bounds'][0][1])
    rider_top=max(p['hi'][1]for p in model['parts']if p['kind']=='FLOOR')+1.8
    high=math.ceil(99+max(model['visual_bounds'][1][1],rider_top))-1
    for row,columns in swept_columns(rows,model['half_width'],model['half_length']):
        errors=[];all_columns.update(columns)
        for x,z in sorted(columns):
            for y in range(low,high+1):
                state=editor.state(x,y,z).split('[')[0]
                if state not in ('minecraft:air','minecraft:cave_air','minecraft:water'):
                    errors.append([x,y,z,state]);break
        report.append(dict(id=row['id'],columns=len(columns),obstructions=len(errors),examples=errors[:12]))
    return dict(rows=report,columns=len(all_columns),obstructions=sum(r['obstructions']for r in report),
                checked_y=[low,high],upper_deck_rider_headroom=True,native_max_step=max(r['spacing']for r in rows),
                method='Dense native rectangular hull sweep, complete rasterized footprint with interval and rotation margins',
                rendered_frame_test=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('candidate','samples','mtr_jar','out'):p.add_argument('--'+name.replace('_','-'),type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    model=boat_model(a.mtr_jar);(a.out/'model.json').write_text(json.dumps(model,indent=2),'utf8')
    report=check(Editor(a.candidate),json.loads(a.samples.read_text('utf8')),model)
    (a.out/'clearance.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(dict(half_width=model['half_width'],half_length=model['half_length'],doorway_y=model['doorway_y'],
        columns=report['columns'],obstructions=report['obstructions'],failures=[r for r in report['rows']if r['obstructions']])),flush=True)

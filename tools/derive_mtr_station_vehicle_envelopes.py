"""Derive conservative installed BBModel envelopes for station clearance.

No game, simulator or world is opened. Selected cube dimensions use the native
rounding/inflation convention. All selected part conditions are enclosed, with
both closed doors and the full declared slide. Results are not a rendered-frame
or native passenger movement acceptance. Invisible floor/door volumes are
reported separately from NORMAL visible geometry.
"""
import argparse,json,zipfile
from pathlib import Path
from itertools import product
import numpy as np
from scipy.spatial.transform import Rotation

def bounds(points):return [points.min(0).tolist(),points.max(0).tolist()]

def derive(jar,vehicles,out):
    out.mkdir(exist_ok=False);results=[]
    with zipfile.ZipFile(jar)as archive:
        def read(resource):
            ns,p=resource.split(':',1);return json.loads(archive.read('assets/'+ns+'/'+p))
        registry=json.loads(archive.read('assets/mtr/mtr_custom_resources.json'))
        for ident in vehicles:
            car=next(r for r in registry['vehicles']if r['id']==ident);parts=[];all_cubes=[];visible_cubes=[];visible_names=[];visible_slides=[];inactive=[]
            for key,offset in [('models',0),('bogie1Models',car.get('bogie1Position',0)),('bogie2Models',car.get('bogie2Position',0))]:
                for model in car.get(key,[]):
                    geometry=read(model['modelResource']);props=read(model['modelPropertiesResource']);definitions={r['name']:r for r in read(model['positionDefinitionsResource'])['positionDefinitions']}
                    elements={r['uuid']:r for r in geometry['elements']};groups={}
                    def index(node,ancestors=()):
                        if not isinstance(node,dict):return
                        if node['name']in groups:raise ValueError('Ambiguous selected group name')
                        groups[node['name']]=(node,ancestors)
                        for child in node.get('children',[]):index(child,ancestors+(node,))
                    for node in geometry['outliner']:index(node)
                    def rotated(points,node):
                        origin=np.asarray(node.get('origin',[0,0,0]),float)
                        return Rotation.from_euler('xyz',node.get('rotation',[0,0,0]),degrees=True).apply(points-origin)+origin
                    def vertices(node):
                        if isinstance(node,str):
                            e=elements[node];a=np.asarray(e['from'],float);b=np.asarray(e['to'],float);size=np.floor(b-a+.5)
                            lo=np.r_[b[:2]-size[:2],a[2]];hi=np.r_[b[:2],a[2]+size[2]];inflate=e.get('inflate',0)
                            return rotated(np.asarray(list(product(*zip(lo-inflate,hi+inflate))),float),e)
                        rows=[vertices(c)for c in node.get('children',[])];return rotated(np.concatenate(rows),node)if rows else np.empty((0,3))
                    for part in props['parts']:
                        for definition in part.get('positionDefinitions',[]):
                            if definition not in definitions:
                                # Installed PositionDefinitions.getPositionDefinition returns
                                # without invoking its callback when a named definition is absent.
                                inactive.append(dict(definition=definition,names=part['names'],model_group=key,reason='absent definition creates no native instances'))
                                continue
                            for flipped,position_key in ((False,'positions'),(True,'positionsFlipped')):
                                for position in definitions[definition].get(position_key,[]):
                                    for name in part['names']:
                                        node,ancestors=groups[name];v=vertices(node)
                                        if not len(v):continue
                                        for parent in reversed(ancestors):v=rotated(v,parent)
                                        v*=np.asarray([-1,1,-1])if flipped else 1
                                        v+=np.asarray([position.get(k,0)for k in ('x','y','z')]);v/=16
                                        v[:,1]+=props.get('modelYOffset',0);v[:,2]*=-1;v[:,2]+=offset
                                        # Longitudinal door motion can enlarge the footprint; include
                                        # either slide sign so flipping does not understate the envelope.
                                        slide=np.array([abs(part.get('doorXMultiplier',0)),abs(part.get('doorYMultiplier',0)),abs(part.get('doorZMultiplier',0))],float)/16
                                        expanded=np.concatenate([v+slide*np.asarray(sign)for sign in product((-1,1),repeat=3)])if slide.any()else v
                                        row=dict(name=name,kind=part.get('type','NORMAL'),model_group=key,closed_bounds=bounds(v),door_motion_bounds=bounds(expanded),declared_door_slide=slide.tolist(),condition=part.get('condition','NORMAL'))
                                        parts.append(row);all_cubes.append(v.reshape(-1,8,3))
                                        if row['kind']=='NORMAL':
                                            cubes=v.reshape(-1,8,3);visible_cubes.append(cubes);visible_names.extend([name]*len(cubes));visible_slides.extend([slide.tolist()]*len(cubes))
            visible=[r for r in parts if r['kind']=='NORMAL'];assert visible
            lo=np.min([r['door_motion_bounds'][0]for r in visible],0);hi=np.max([r['door_motion_bounds'][1]for r in visible],0)
            result=dict(vehicle=ident,native_length=car['length'],native_width=car['width'],visible_motion_bounds=[lo.tolist(),hi.tolist()],parts=parts,visible_part_instances=len(visible),selected_part_instances=len(parts),inactive_position_definitions=inactive,all_selected_conditions_enclosed=True,rendered_frame_verified=False,world_written=False)
            np.savez_compressed(out/(ident+'-closed-cubes.npz'),cubes=np.concatenate(all_cubes))
            np.savez_compressed(out/(ident+'-visible-cubes.npz'),cubes=np.concatenate(visible_cubes),names=np.asarray(visible_names),door_slides=np.asarray(visible_slides))
            (out/(ident+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');results.append(result)
            print(ident,'native width',car['width'],'visible bounds',result['visible_motion_bounds'],'parts',len(parts),flush=True)
    (out/'summary.json').write_text(json.dumps(dict(installed_jar=str(jar),vehicles=[{k:r[k]for k in('vehicle','native_length','native_width','visible_motion_bounds','selected_part_instances')}for r in results],world_written=False,rendered_frame_verified=False),indent=2),'utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--jar',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--vehicles',nargs='+',required=True);a=p.parse_args();derive(a.jar,a.vehicles,a.out)

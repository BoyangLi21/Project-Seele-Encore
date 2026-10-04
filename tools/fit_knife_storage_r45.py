"""Fit the real knife to the concave, sectioned shoulder enclosure.

The whole-pylon convex envelope bridges an intentional shoulder notch.
This fit tests each section, including knife-edge crossings at every section
boundary. It does not substitute for animated mesh/surface validation.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from scipy.spatial import ConvexHull
from scipy.optimize import differential_evolution
from author_knife_cage_r45 import section_hulls


def main():
    p=argparse.ArgumentParser();p.add_argument('--body-mesh',type=Path,required=True);p.add_argument('--hand',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--maximum-width',type=float,default=1.65);p.add_argument('--maximum-yz',type=float,default=1.10)
    p.add_argument('--padding',type=float,default=0);a=p.parse_args()
    body=json.loads(a.body_mesh.read_text());part=body['parts']['pylon_l'];raw=np.asarray(part['vertices']).reshape(-1,8).copy();raw[:,:3]+=part['pivot'];sections=section_hulls(raw)
    contract=json.loads((a.hand/'hand_rig_contract.json').read_text());attachment=contract['knife_attachment_r45'];file=Path(attachment['source_mesh']);knife=json.loads(file.read_text())['parts']['knife']
    points=(np.asarray(knife['vertices']).reshape(-1,8)[:,:3]+knife['pivot'])*[-1,1,1]-np.asarray(attachment['source_handle_centre'])*16
    hull=ConvexHull(points);vertices=points[hull.vertices];vh=ConvexHull(vertices)
    edges=np.unique(np.sort(np.concatenate([vh.simplices[:,[0,1]],vh.simplices[:,[1,2]],vh.simplices[:,[2,0]]]),axis=1),axis=0)
    def violation(parameters):
        x,y,z,angle,width,yz=parameters;blade=np.array([0.,-np.cos(angle),np.sin(angle)]);axis_y=-blade
        rotation=np.column_stack(([-1.,0,0],axis_y,np.cross([-1.,0,0],axis_y)))
        world=(vertices@rotation.T+[-x,y,z])*[-1,1,1];world[:,0]=19.24322+(world[:,0]-19.24322)/width
        world[:,1:3]=[168,0]+(world[:,1:3]-[168,0])/yz
        first,last=world[edges[:,0]],world[edges[:,1]];delta=last-first;worst=-100.
        for index,section in enumerate(sections):
            low,high=section['low'],section['high']
            selected=(world[:,1]>=low-1e-8)&(world[:,1]<=high+1e-8)
            if index==0:selected|=world[:,1]<low
            if index==len(sections)-1:selected|=world[:,1]>high
            samples=[world[selected]]
            for boundary in [low,high]:
                valid=abs(delta[:,1])>1e-10;t=np.zeros(len(edges));t[valid]=(boundary-first[valid,1])/delta[valid,1];mask=valid&(t>=0)&(t<=1)
                samples.append(first[mask]+t[mask,None]*delta[mask])
            sample=np.vstack(samples)
            if len(sample):
                eq=section['hull'].equations;norm=np.linalg.norm(eq[:,:3]*[1/width,1/yz,1/yz],axis=1)
                worst=max(worst,float(((sample@eq[:,:3].T+eq[:,3])/norm).max()))
        worst=max(worst,float(sections[0]['low']-world[:,1].min()),float(world[:,1].max()-sections[-1]['high']))
        return worst
    def objective(parameters):
        return max(0.,violation(parameters)+.12-a.padding)*100+(parameters[4]-1)*.03+(parameters[5]-1)
    result=differential_evolution(objective,[(14,22),(171,190),(-3,20),(-.85,.65),(1.,a.maximum_width),(1.,a.maximum_yz)],maxiter=320,popsize=12,tol=1e-7,seed=42,polish=False)
    gap=violation(result.x);report=dict(parameters=result.x[:4].tolist(),width_scale=float(result.x[4]),yz_scale=float(result.x[5]),
        maximum_section_violation=gap,maximum_convex_hull_violation=gap,scope='Eight concave enclosure sections and knife convex-edge boundary samples; animated surfaces still required',
        requested_shell_padding=a.padding,clearance_after_padding=a.padding-gap,end_section_planes_extended=True,
        body_sha256=hashlib.sha256(a.body_mesh.read_bytes()).hexdigest(),knife_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),visual_accepted=False)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2));print(json.dumps(report))


if __name__=='__main__':main()

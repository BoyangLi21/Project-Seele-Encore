"""Locate changes in the *recorded native* pose pipeline; does not approve art."""
from pathlib import Path
import argparse,json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]

def matrix(v):return np.asarray(v,float).reshape(4,4).T
def angle(a,b):
    return float(np.degrees(np.arccos(np.clip((np.trace(a[:3,:3].T@b[:3,:3])-1)/2,-1,1))))

def main():
    p=argparse.ArgumentParser();p.add_argument('media',type=Path);args=p.parse_args()
    raw=json.loads((args.media/'body_layers_r40.json').read_text());rows=[];last=None
    for sample in raw['samples']:
        layers=sample['layers'];names=list(layers)
        for a,b in zip(names,names[1:]):
            for bone in ('torso_lower','leg_l','leg_r','shin_l','shin_r','foot_l','foot_r'):
                if bone not in layers[a] or bone not in layers[b]:continue
                ma=matrix(layers[a][bone]['matrix']);mb=matrix(layers[b][bone]['matrix'])
                rows.append(dict(tick=sample['review_tick'],stage=sample['stage'],ordinary=sample['ordinary'],phase=sample['ordinary_phase'],
                                 layer=b,bone=bone,rotation_delta_degrees=angle(ma,mb),translation_delta_blocks=float(np.linalg.norm(ma[:3,3]-mb[:3,3])*5)))
        if 'rendered' in sample:
            for bone in sample['rendered']:
                if bone not in layers[names[-1]]:continue
                ma=matrix(layers[names[-1]][bone]['matrix']);mb=matrix(sample['rendered'][bone])
                rows.append(dict(tick=sample['review_tick'],stage=sample['stage'],ordinary=sample['ordinary'],phase=sample['ordinary_phase'],
                                 layer='rendered',bone=bone,rotation_delta_degrees=angle(ma,mb),translation_delta_blocks=float(np.linalg.norm(ma[:3,3]-mb[:3,3])*5)))
    out=args.media/'layer_deltas_r43.json';out.write_text(json.dumps(dict(scope='Measured writer deltas, not a validity or beauty threshold',samples=rows),indent=2),'utf8')
    worst={}
    for row in rows:
        key=row['layer']
        if key not in worst or row['rotation_delta_degrees']>worst[key]['rotation_delta_degrees']:worst[key]=row
    print(json.dumps(worst,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

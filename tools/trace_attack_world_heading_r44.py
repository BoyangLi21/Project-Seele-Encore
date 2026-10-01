"""Native first world-facing error, traced to the exact exported action root."""
from pathlib import Path
import argparse,json
import numpy as np
from scipy.spatial.transform import Rotation,Slerp


def heading(q):
    v=Rotation.from_quat(q).apply([0,0,-1.]);return float(np.degrees(np.arctan2(v[0],-v[2])))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--native',type=Path,required=True);ap.add_argument('--profile',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    samples=json.loads((args.native/'body_layers_r40.json').read_text('utf8'))['samples'];profile=json.loads(args.profile.read_text('utf8'));root_index=profile['bones'].index('root');rows=[]
    for sample in samples:
        if sample.get('stage')!='normal_contact'or sample.get('ordinary',-1)<0:continue
        phase=float(sample['ordinary_phase']);label=('r32_jab','r32_cross','r32_hook')[min(2,sample['ordinary'])];clip=profile['clips'][label]
        f=phase*(len(clip['frames'])-1);lo=int(np.floor(f));hi=min(lo+1,len(clip['frames'])-1);u=f-lo
        def quat(frame):
            w,x,y,z=frame['rotation_wxyz'][root_index];return[-x,-y,z,w]
        exported=quat(clip['frames'][lo])if lo==hi else Slerp([0,1],Rotation.from_quat([quat(clip['frames'][lo]),quat(clip['frames'][hi])]))([u]).as_quat()[0]
        layers=sample['layers'];actual=layers['authored']['root']['quaternion_xyzw'];delta=np.degrees((Rotation.from_quat(exported).inv()*Rotation.from_quat(actual)).magnitude())
        layer_heading={n:heading(v['root']['quaternion_xyzw'])for n,v in layers.items()if'root'in v}
        rows.append(dict(native_review_tick=sample['review_tick'],ordinary=sample['ordinary'],phase=phase,clip=label,
                         native_authored_vs_direct_exported_root_degrees=float(delta),native_layer_root_headings_degrees=layer_heading,
                         exported_root_heading_degrees=heading(exported),entry_blend_active=phase<.18))
    report=dict(rows=rows,at_tick39=next((r for r in rows if r['native_review_tick']==39),None),
        first_source_frame_error='V1 source importer aligned each take to its opening hip transverse axis, not the actual punch/task direction. Off-axis captured strikes retain their world bias in the exported pelvis/root and first enter native at authored; subsequent terrain/reaction/feet layers preserve this root.',
        limitations=['Entity world yaw is not in this layer recorder; this report compares exact model root at the same native phase','Head, hand surface sweep and target world direction still require the next native run'],
        changed_native_evidence=False,artistic_acceptance=False)
    args.out.mkdir(parents=True,exist_ok=True);(args.out/'first_world_heading_trace.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report['at_tick39'],indent=2))


if __name__=='__main__':main()

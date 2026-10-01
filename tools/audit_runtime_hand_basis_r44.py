"""Read actual five geometry hierarchies and runtime hand-basis construction."""
from pathlib import Path
import json
import numpy as np
from scipy.spatial.transform import Rotation as R
from prepare_tv_exchange_r44 import raw_rig,sha

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r44/combat/runtime_hands_basis';OUT.mkdir(parents=True,exist_ok=True)
def unit(v):return v/max(np.linalg.norm(v),1e-12)
def degrees(a,b):return float(np.degrees(np.arccos(np.clip(unit(a)@unit(b),-1,1))))
rows=[]
for key,asset in enumerate(('eva_unit00','eva_unit01','eva_unit02','eva_prototype','eva_un01')):
    rig,p,neutral,path=raw_rig(asset)
    for side in ('l','r'):
        hand='hand_'+side;axis='finger_middle_axis_'+side
        width=unit(p['finger_index_'+side]-p['finger_little_'+side]);along=p[hand]-p['forearm_'+side];along=unit(along-width*(along@width))
        palmar=unit(np.cross(width,along));bind=R.from_euler('xyz',np.asarray(rig[axis].get('rotation',[0,0,0]))*[-1,-1,1],degrees=True)
        if palmar@bind.apply([1,0,0])<0:palmar=-palmar
        extended=np.column_stack((palmar,-along,np.cross(palmar,-along)))
        parent=rig[axis]['parent'];basis=neutral[parent][:3,:3]
        raw_direction=p['finger_middle_tip_'+side]-p['finger_middle_'+side]
        actual_extended=basis@extended@unit(raw_direction)
        hand_direction=unit(basis@along)
        global_wrong=degrees(actual_extended,along)
        chain=[];n=parent
        while n:
            chain.append(dict(name=n,bind_degrees=rig[n].get('rotation',[0,0,0])));n=rig[n].get('parent')
        rows.append(dict(variant=key,asset=asset,side=side,geo_sha256=sha(path),axis_parent=parent,parent_chain=chain,
                         parent_bind_world_rotation=basis.tolist(),runtime_extended_local=extended.tolist(),
                         finger_raw_axis=unit(raw_direction).tolist(),neutral_extended_finger_direction=actual_extended.tolist(),
                         neutral_hand_longitudinal=hand_direction.tolist(),hand_local_extension_error_degrees=degrees(actual_extended,hand_direction),
                         error_if_claimed_global_basis_degrees=global_wrong,
                         scope='Exact current geo bind and R41 formula, not a sampled native final palette. Absolute pivot differences are pre-bind geometry coordinates; parent bind composes afterward.'))
(OUT/'five_rig_basis_readback.json').write_text(json.dumps(dict(rows=rows,quality='Not native or visual acceptance'),indent=2),'utf8')
print(json.dumps([dict(variant=r['variant'],side=r['side'],parent=r['axis_parent'],local_error=r['hand_local_extension_error_degrees'],global_error=r['error_if_claimed_global_basis_degrees'])for r in rows]))

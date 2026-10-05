"""Restore supported paired contact and direct pounce; retain the final bound wrap performance."""
from pathlib import Path
import copy,json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r48/first_battle';OUT.mkdir(parents=True,exist_ok=True)
TARGET=ROOT/'artifacts/rebuild_r48/runtime/projectseele-local-maps/first_battle_r44.json'

def mix_quats(a,b,t):
    a=np.asarray(a);b=np.asarray(b);b=np.where(((a*b).sum(1)<0)[:,None],-b,b)
    c=a*(1-t)+b*t;c/=np.linalg.norm(c,axis=1)[:,None];return c.tolist()

def main():
    baseline=OUT/'before_first_battle_r44.json'
    if not baseline.exists():baseline.write_bytes(TARGET.read_bytes())
    current=json.loads(baseline.read_text());direct=json.loads((ROOT/'artifacts/repair_r43/first_battle/first_battle_r43.json').read_text())
    result=copy.deepcopy(current);last=489;blend_from=479
    for role in ('eva','angel'):
        src=direct[role];dst=result[role];old=current[role]
        if src['bones']!=dst['bones']:raise ValueError('Paired source bone identity differs')
        for i in range(last):
            u=max(0,(i-blend_from)/(last-blend_from));u=u*u*(3-2*u)
            frame=copy.deepcopy(src['frames'][i]);frame['rotation_wxyz']=mix_quats(frame['rotation_wxyz'],old['frames'][i]['rotation_wxyz'],u)
            for key in ('root_m',):frame[key]=(np.asarray(frame[key])*(1-u)+np.asarray(old['frames'][i][key])*u).tolist()
            names=set(frame.get('bone_position_xyz',{}))|set(old['frames'][i].get('bone_position_xyz',{}))
            frame['bone_position_xyz']={n:(np.asarray(frame.get('bone_position_xyz',{}).get(n,[0,0,0]))*(1-u)+np.asarray(old['frames'][i].get('bone_position_xyz',{}).get(n,[0,0,0]))*u).tolist()for n in names}
            dst['frames'][i]=frame
            for key,values in src.items():
                if key.endswith('_blocks') and key in dst:dst[key][i]=(np.asarray(values[i])*(1-u)+np.asarray(old[key][i])*u).tolist()
    for key in ('position','target'):
        for i in range(last):
            u=np.clip((i-blend_from)/(last-blend_from),0,1);u=u*u*(3-2*u)
            result['camera'][key][i]=(np.asarray(direct['camera'][key][i])*(1-u)+np.asarray(current['camera'][key][i])*u).tolist()
    result['landing_tick']=direct['landing_tick']
    result['r48_direction']=dict(reference='TV episode 02: direct forward leap, supported close contact and joint-driven arms; original game choreography',
        source='authored R43 direct-contact revision',removed='Inherited R42 forward somersault and unrelated transported shoulder twist',
        preserved_final_wrap_from_frame=489,preserved_surface_identity=current['surface_deformation_r14'],native_verified=False)
    # The bound cached final wrap and all its actor/camera channels are kept
    # together, with no new cross explosion or separate retimed surface cache.
    for role in ('eva','angel'):
        for key,values in current[role].items():
            if isinstance(values,list)and len(values)==691:
                assert result[role][key][489:]==values[489:]
    TARGET.write_text(json.dumps(result,separators=(',',':')),'utf8')
    (OUT/'REPORT.json').write_text(json.dumps(result['r48_direction'],indent=2),'utf8');print('Paired direct approach/contact installed; final 202 frames preserved')

if __name__=='__main__':main()

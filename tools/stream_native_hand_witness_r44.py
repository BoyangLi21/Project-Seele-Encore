"""Stream the original large witness; retain full selected submissions and static geometry once."""
from pathlib import Path
import json,re,hashlib
import numpy as np
from prepare_tv_exchange_r44 import raw_rig
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r44/combat/runtime_hands_basis';OUT=BASE/'native_v1_stream_readback';OUT.mkdir(exist_ok=True)
clients=json.loads((ROOT/'artifacts/rebuild_r44/network_runtime/handnativev1/client_samples.json').read_text('utf8'))
targets={}
for variant in range(5):
    available=[r for r in clients if r['variant']==variant]
    for requested in (70,590):
        row=min(available,key=lambda r:abs(r['age']-requested));tick=row['foot_witness']['support_r44']['game_time']
        targets[(variant,requested)]=dict(tick=tick,observed_age=row['age'])
assets=('eva_unit00','eva_unit01','eva_unit02','eva_prototype','eva_un01');rigs=[raw_rig(asset)for asset in assets]
first_geometry={};counts={};palettes=[];selected=[];axis_rows=[]
with (BASE/'native_all5.jsonl').open('r',encoding='utf8') as source:
    for number,line in enumerate(source,1):
        prefix=line[:900];kind=re.search(r'"kind":"([^"]+)"',prefix).group(1);variant=int(re.search(r'"variant":(\d+)',prefix).group(1));tick=int(re.search(r'"tick":(\d+)',prefix).group(1))
        key=(variant,kind);counts[key]=counts.get(key,0)+1
        nearby=[(requested,t)for(v,requested),t in targets.items()if v==variant and abs(t['tick']-tick)<=6]
        if kind=='final_named_palette':
            row=json.loads(line);palettes.append(dict(variant=variant,tick=tick,frame=row['frame'],stance=row['stance'],shared_hands=row['shared_hands']))
            if nearby:
                destination=OUT/f"v{variant}_tick{tick}_palette.json";destination.write_text(line,'utf8');selected.append(dict(variant=variant,tick=tick,kind=kind,file=destination.name,targets=nearby))
                bones={b['name']:b for b in row['bones']};rig,p,neutral,path=rigs[variant]
                for side in ('l','r'):
                    hand='hand_'+side;axis='finger_middle_axis_'+side
                    parent=np.asarray(bones[hand]['final_model_column_major']).reshape(4,4).T[:3,:3]
                    adapter=np.asarray(bones[axis]['final_model_column_major']).reshape(4,4).T[:3,:3]
                    direction=np.linalg.inv(parent)@adapter@np.array([0.,-1.,0.]);direction/=np.linalg.norm(direction)
                    width=p['finger_index_'+side]-p['finger_little_'+side];width/=np.linalg.norm(width)
                    along=p[hand]-p['forearm_'+side];along-=width*(along@width);along/=np.linalg.norm(along)
                    error=float(np.degrees(np.arccos(np.clip(direction@along,-1,1))))
                    axis_rows.append(dict(variant=variant,tick=tick,side=side,stance=row['stance'],shared_hands=row['shared_hands'],
                                          actual_axis_local_extension=direction.tolist(),R41_expected_longitudinal=along.tolist(),
                                          actual_final_adapter_vs_R41_extension_degrees=error,
                                          scope='Final actual named palette relative to its actual hand parent, compared with the current R41 construction. Authored sharedHands clips may own a different pose; not a visual pass.'))
        elif kind=='actual_cpu_submitted_part':
            bone=re.search(r'"bone":"([^"]+)"',prefix).group(1);geometry_key=(variant,bone)
            if geometry_key not in first_geometry or nearby:
                row=json.loads(line)
                if geometry_key not in first_geometry:
                    packed=np.asarray(row['original_part_xyz'],dtype='<f4');digest=hashlib.sha256(packed.tobytes()).hexdigest()
                    destination=OUT/f'v{variant}_{bone}_actual_original.npy';np.save(destination,packed)
                    first_geometry[geometry_key]=dict(variant=variant,bone=bone,vertices=len(packed)//3,loaded_resource_sha256=row['loaded_resource_sha256'],
                                                        decoded_xyz_float32_sha256=digest,file=destination.name,part_pivot=row['part_pivot_authored'])
                if nearby:
                    destination=OUT/f'v{variant}_tick{tick}_{bone}_submitted.json';destination.write_text(line,'utf8');selected.append(dict(variant=variant,tick=tick,kind=kind,bone=bone,file=destination.name,targets=nearby))
        if number%3000==0:print('Streamed',number,'rows',flush=True)
report=dict(source_bytes=(BASE/'native_all5.jsonl').stat().st_size,counts=[dict(variant=v,kind=k,rows=n)for(v,k),n in counts.items()],
            original_resource_parts=list(first_geometry.values()),target_client_rows=[dict(variant=v,requested_age=a,**t)for(v,a),t in targets.items()],
            selected_actual_records=selected,adapter_stage_comparisons=axis_rows,palette_metadata=palettes,
            scope='Original native_v1 retained. Streaming analysis, no all-file read, no art/performance/collision acceptance. UN render scarcity remains a limitation.')
(OUT/'native_hand_stage_readback.json').write_text(json.dumps(report,indent=2),'utf8')
print('Saved',len(first_geometry),'actual original parts once;',len(selected),'selected actual records',flush=True)

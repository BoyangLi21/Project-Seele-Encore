"""Finite exact floor/guard/door proposal, inverse and whole staff admission.

This is a read-only construction proposal. It never invokes a world writer.
"""
from pathlib import Path
import argparse, hashlib, json, math
from measure_world_r40 import MeasuredWorld
from build_tv_personnel_deck_assets_r44 import authored, rotated

ROOT=Path(__file__).resolve().parents[1]


def main(layout,out):
    out=Path(out)
    if out.exists():raise ValueError('Fresh private revision required')
    plan=json.loads(Path(layout).read_text('utf8')); guards={};volumes=[];clear_widths=[]
    floors={(c['variant'],c['side'],c['position'][0],c['position'][2]) for c in plan['floor_cells']}
    for c in plan['floor_cells']:
        x,y,z=c['position'];variant,side=c['variant'],c['side']
        prop=dict(v.split('=') for v in c['after'].split('[')[1][:-1].split(','))
        boxes=[rotated(b,prop['facing']) for b in authored(prop['profile'],int(prop['level']))]
        high=max(b[4] for b in boxes)+y;low=min(b[4] for b in boxes)+y
        volumes.append({'variant':variant,'side':side,'role':c['role'],'bounds':[x,low-.10,z,x+1,high+2.4,z+1]})
        gy=math.ceil(high);drop=round((gy-high)*4)
        for dx,dz,face in [(-1,0,'east'),(1,0,'west'),(0,-1,'south'),(0,1,'north')]:
            if (variant,side,x+dx,z+dz) in floors:continue
            if c['role']=='supported_front_access_bridge' and dz==-1:continue
            if c['role']=='02_right_supported_entry_stair' and dx==1:continue
            if not (variant==2 and side==1) and dx==-side and z in (-256,-255):continue
            if variant==2 and side==1 and dx==-1 and z in (-254,-253):continue
            q=(x+dx,gy,z+dz);edge=face;inset=False
            # All original02 arrival cells are immutable, including its x85
            # boundary. One 55mm guard sits on this lane's own edge instead.
            if 85<=q[0]<=98 and -399<=q[1]<=-390 and -264<=q[2]<=-248:
                q=(x,gy,z);edge={'north':'south','south':'north','east':'west','west':'east'}[face];inset=True
            old=guards.setdefault(q,{'drop':drop,'faces':set(),'variant':variant,'side':side,'inside_floor_edge':inset})
            if old['drop']!=drop:raise ValueError(('Guard owner has inconsistent floor datum',q,old['drop'],drop))
            old['faces'].add(edge)
    w=MeasuredWorld(ROOT/'run/saves/SEELE_FIELD_R44_REVIEW')
    changed={tuple(c['position']):{'before':c['before'],'after':c['after'],'role':c['role']} for c in plan['floor_cells']}
    for q,item in guards.items():
        props={'drop':str(item['drop']),**{face:str(face in item['faces']).lower() for face in ('north','east','south','west')}}
        state='projectseele:tv_personnel_guard_r44['+','.join(k+'='+props[k] for k in sorted(props))+']'
        if q in changed:raise ValueError(('Floor and guard occupy same world cell',q))
        changed[q]={'after':state,'role':'personnel_boundary_guard'}
    for gate in plan['entry_gate_pairs']:
        for i,p in enumerate(gate['lower_positions']):
            for half in ('lower','upper'):
                q=(p[0],p[1]+(half=='upper'),p[2]);hinge='right' if i==0 else 'left'
                if q in changed:raise ValueError(('Guard/door owner conflict',q))
                changed[q]={'after':f'projectseele:city_personnel_door[facing={gate["facing"]},half={half},hinge={hinge},open=false,powered=false]','role':'finite_personnel_entry_gate'}
    for q in changed:w.around(q,2)
    w.load()
    for q,c in changed.items():
        actual=w.block(q)
        if actual is None:raise ValueError(('Unknown current state',q))
        if 'before' in c and c['before']!=actual:raise ValueError(('Floor source epoch changed',q,c['before'],actual))
        c['before']=actual
        if 85<=q[0]<=98 and -399<=q[1]<=-390 and -264<=q[2]<=-248:
            raise ValueError(('Arrival owner changed',q))
    # Fixed green decks are genuine inspection surfaces, not forbidden props.
    # Their receiver ends and swept shoulder ends remain equipment; clearance
    # approval is separately tested. The whole surface counts for clear-out.
    for variant in range(3):
        ox=-11.5+42*variant
        for side in (-1,1):
            x0,x1=(8.9,12.2) if variant==2 and side==1 else (8.9,14.5)
            if side<0:x0,x1=-x1,-x0
            volumes.append({'variant':variant,'side':side,'role':'green_cast_inspection_surface_and_equipment_clearout',
                            'bounds':[ox+x0,-394.10,-260,ox+x1,-387.86,-246.08]})
            clear_widths.append({'variant':variant,'side':side,'permanent_staff_lane_net_width_m':1.945 if variant==2 and side==1 else 2.,
                                 'green_cast_access':'02 direct side step from low staff lane at z[-254,-252]; other five via 2m rail portal and steel lip at z[-256,-254]',
                                 'requires_fixed_inspection_phase':True,'green_face_native_clearance_approved':False})
    payload={'schema':44,'dimension':'projectseele:geofront','entry_gate_pairs':plan['entry_gate_pairs'],'operator_volumes':volumes,
             'review_flag':'projectseele.r44TvPersonnelPlatformsReview','crew_exit_routes':plan['complete_entry_and_return_cases']}
    operations=[{'position':q,**c} for q,c in sorted(changed.items())]
    inverse=[{'position':q,'before':c['after'],'after':c['before'],'role':c['role']} for q,c in sorted(changed.items())]
    out.mkdir(parents=True)
    for name,value in [('operations.json',operations),('inverse.json',inverse),('r44_tv_personnel_platforms.json',payload)]:
        (out/name).write_text(json.dumps(value,indent=2),'utf8')
    report={'layout_sha256':hashlib.sha256(Path(layout).read_bytes()).hexdigest(),'floor_cells':len(plan['floor_cells']),
            'guard_cells':len(guards),'gate_cells':24,'operations':len(operations),'one_to_one_inverse':True,'actual_net_widths':clear_widths,
            'non_air_guard_sources':[{'position':q,'before':c['before']} for q,c in changed.items() if c['role']=='personnel_boundary_guard' and c['before'] not in ('minecraft:air','minecraft:cave_air','minecraft:void_air')],
            'preapply_ready':False,'native_passed':False,'art_passed':False,'world_write':False,
            'remaining':['full-width world/body/motion and boundary union clearance','green inspection surface and portal real walking','whole support load paths and native extended-shape neighbours','exact BEs/entity/source producer dependencies','root native occupied prepare/motion and gate lifecycle']}
    (out/'contract.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--layout',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();main(args.layout,args.out)

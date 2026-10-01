"""All actual carrier render-part monotone intervals vs new permanent members."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r44/hangar_machinery'
CHANGED={'platform_r','platform_l','platform_2_r','fixed_support_2_r','staff_deck_bearings_l','staff_deck_bearings_r'}

def smooth(v):
    v=np.clip(v,0,1);return v*v*(3-2*v)

def main(asset,operations,out):
    asset,operations,out=map(Path,(asset,operations,out))
    if out.exists():raise ValueError('Fresh output required')
    cage=json.loads(asset.read_text('utf8'));ops=json.loads(operations.read_text('utf8'))
    cp=ROOT/'src/main/resources/assets/projectseele/mesh/tv_facilities_r16.json';carrier=json.loads(cp.read_text('utf8'))
    rp=ROOT/'src/main/java/com/projectseele/client/render/TvFacilityMeshes.java'
    native=json.loads((BASE/'tv_personnel_deck_native_v1/native_union_readback/full_native_collision_shapes.json').read_text())
    native.update(json.loads((BASE/'tv_personnel_guard_native_v1/native_union_readback/native64.json').read_text()))
    rows=[];checks=[]
    for v in range(3):
        origin=np.array([-11.5+42*v,-442.96,-239.5]);fixed=[];owners=[]
        for c in cage['components']:
            if c['part'] in CHANGED and c.get('variant',v)==v:
                fixed.extend(cage['collision_parts'][c['part']]);owners.extend([c['part']]*len(cage['collision_parts'][c['part']]))
        for op in ops:
            # Exactbayownership: native grids belong only to this finite band.
            if not origin[0]-21<=op['position'][0]<=origin[0]+21:continue
            states=(op['after'],op['after'].replace('open=false','open=true')) if 'personnel_entry_gate' in op['role'] else (op['after'],)
            for state in set(states):
                for b in native[state]:fixed.append(np.array(b).reshape(2,3)+op['position']-origin);owners.append({'cell':op['position'],'state':state})
        fixed=np.array(fixed);mounts=np.array(carrier['carrier_actuator_mounts'][str(v)])
        def transform(name,tri,rise,release):
            t=tri.copy()+[0,.96,0]
            if name not in ('carrier_deck','carrier_deck_guides'):t[:,:,1]-=64*(1-rise)
            if name=='carrier_clamp':t[:,:,2]-=3*release
            if name.startswith('carrier_contact_pads_'):
                stroke=min(6*(1-smooth((rise-.8)/.2))+4*release,min(m[3]-m[2]-.28 for m in mounts));t[:,:,2]+=stroke
            return t
        for name,raw in carrier['parts'].items():
            if not name.startswith('carrier_') or name=='carrier_ram_unit' or name.startswith('carrier_contacts_'):continue
            if name[-1:] in ('0','1','2') and int(name[-1])!=v:continue
            tri=np.array(raw).reshape(-1,3,carrier['stride'])[:,:,:3];bound_hits=[];interval_count=0
            phases=[[(float(r),0.) for r in np.linspace(0,1,121)],[(1.,float(r)) for r in np.linspace(0,1,121)]]
            for phase in phases:
                for a,b in zip(phase[:-1],phase[1:]):
                    interval_count+=1;first=transform(name,tri,*a);last=transform(name,tri,*b)
                    low=np.minimum(first.min(1),last.min(1));high=np.maximum(first.max(1),last.max(1))
                    wholelo,wholehi=low.min(0),high.max(0)
                    candidates=np.flatnonzero(np.all((fixed[:,1]>wholelo+1e-6)&(fixed[:,0]<wholehi-1e-6),axis=1))
                    for i in candidates:
                        ids=np.flatnonzero(np.all((high>fixed[i,0]+1e-6)&(low<fixed[i,1]-1e-6),axis=1))
                        if len(ids):bound_hits.append({'interval':[a,b],'fixed_owner':owners[int(i)],'triangle_bound_hits':len(ids)})
            rows.extend({'variant':v,'part':name,**r} for r in bound_hits)
            checks.append({'variant':v,'actual_part':name,'actual_triangles':len(tri),'intervals':interval_count,'positive_continuous_triangle_bounds':len(bound_hits)})
    out.mkdir(parents=True)
    r={'inputs':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (asset,operations,cp,rp)},'checks':checks,'conservative_findings':rows,
       'continuous_clear_proven':not rows,'proof':'Each actual source vertex coordinate is monotone within each120rise or120release interval. Endpoint triangle AABB union contains the entire continuous source transform. Zero bound intersection proves clearance; any positive bound remains unresolved until exact refinement. LAUNCH_CLEAR clamp release and pads use actualsource3m and4m displacements; no legacy contacts fallback substituted for registered6mounts.',
       'remaining':['sixmountedram proof separately bound','nativecrane mesh/actualcoupled canonical transforms must be exported by root','actualnative lifecycle/occupancy/cold/multiplayer'],
       'world_write':False,'native_passed':False,'art_passed':False,'preapply_ready':False}
    (out/'contract.json').write_text(json.dumps(r,indent=2),'utf8');print(json.dumps({'checks':len(checks),'positive_bounds':len(rows),'first':rows[:1]}))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('asset','operations','out'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();main(a.asset,a.operations,a.out)

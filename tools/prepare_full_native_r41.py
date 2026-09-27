"""Independent native passage, whole-flight, grade and edge suites for R41."""
from pathlib import Path
import json,gzip,hashlib
from measure_world_r40 import MeasuredWorld

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/spatial_repair_r41'
WORLD=ROOT/'run/saves/SEELE_FIELD_R41_REVIEW';OUT=ART/'native_spatial/full'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    existing=json.loads((WORLD/'quality_walk_cases.json').read_text('utf8'))
    focused=json.loads((ART/'native_spatial/first_cases.json').read_text('utf8'))
    excluded=[];edges=[]
    for c in focused:
        q=c.get('candidate',{}).get('pos',[])
        if len(q)==3 and q[1]==-369 and q[2]==-55 and 91<=q[0]<=95:
            excluded.append({**c,'reason':'Probe was placed behind the closed landing door, inside the compact lift swept volume. Review through the actual outside call/landing interface.'})
        else:edges.append(c)
    ops=[];plans=set()
    for receipt in ART.glob('**/receipt.json'):
        record=json.loads(receipt.read_text('utf8'))
        if Path(record.get('world','')).resolve()==WORLD.resolve():plans.add(receipt.parent.parent/'ops.json.gz')
    for f in sorted(plans):
        with gzip.open(f,'rt',encoding='utf8') as stream:ops+=json.load(stream)
    rails={tuple(o['box'][:3]):o['state'] for o in ops if o['state'].startswith('projectseele:nerv_edge_rail[')}
    newgrades=[o for o in ops if 'half_metre_grade' in o['owner']]
    w=MeasuredWorld(WORLD)
    for q in rails:w.around(q,1)
    for o in newgrades:w.around(o['box'][:3],2)
    places=json.loads((ROOT/'artifacts/world_quality_r02/surface_layout.json').read_text('utf8'))['kept_plots']
    places+=json.loads((ROOT/'artifacts/world_quality_r02/kirisato_apartments/places.json').read_text('utf8'))['landmarks']
    stairs=[];held=[]
    for b in places:
        if 'storeys' not in b:continue
        x0,x1,z0,z1=b['bounds'];floor=b['floor'];estate=b['id'].startswith('kirisato/')
        for level in range(b['storeys'] if estate else b['storeys']-1):
            # The R02 repair widened the well and moved its southbound
            # flight from +6 to +7. Use that actual retained core.
            north=level%2==0;x=x0+((4 if north else 8) if estate else (3 if north else 7));z=z0+((10 if north else 4) if estate else (9 if north else 3));y=floor+level*5;dz=-1 if north else 1
            for lane in (-1,0,1):
                q=(x+lane,y+1,z);end=(x+lane,y+5,z+4*dz);w.around(q,1);w.around(end,1)
                stairs.append(dict(id=f"r41/full_flight/{b['id']}/{level}/{lane}",path=[[x+lane+.5,y+1,z-dz+.5],[x+lane+.5,y+6,z+5*dz+.5]],first=q,last=end,heading='north' if north else 'south'))
    w.load();directions={'east':(1,0),'west':(-1,0),'north':(0,-1),'south':(0,1)}
    for q in sorted(rails):
        actual=w.block(q)
        if not actual or not actual.startswith('projectseele:nerv_edge_rail['):
            held.append(dict(pos=q,reason='A runtime-owned rail is currently retracted or has changed',actual=actual));continue
        for side,(dx,dz) in directions.items():
            if side+'=true' not in actual:continue
            x,y,z=q;axis='x' if dx else 'z';normal=dx or dz;coordinate=x if dx else z
            edges.append(dict(id=f'r41/all_rails/{x}/{y}/{z}/{side}',path=[[x+.5,y,z+.5],[x+.5+dx*1.5,y,z+.5+dz*1.5]],barrier=dict(axis=axis,plane=coordinate+(1 if normal>0 else 0),maxGap=1.75)))
    grade_cases=[]
    for r in json.loads((ART/'regional_edges/decisions.json').read_text('utf8')):
        if r['decision']!='half_metre_shoulder':continue
        # Use the originally measured standing approach that justified this
        # curb. A neighbouring wall base is not a second pedestrian endpoint.
        X,Y,Z=r['pos'];dx,_,dz=r['normal'];x,y,z=X+dx,Y-1,Z+dz
        path=[[X+.5,Y,Z+.5],[x+.5,y+.5,z+.5]];key=f'r41/grade/{x}/{y}/{z}/{dx}/{dz}'
        grade_cases.extend([dict(id=key,path=path),dict(id=key+'/return',path=path[::-1])])
    flight_cases=[]
    for c in stairs:
        if not all('stairs[' in (w.block(c[k]) or '') and 'facing='+c['heading'] in w.block(c[k]) for k in ('first','last')):
            held.append({**c,'reason':'Original stair template differs from current actual steps; preserve current structure and review separately'});continue
        case={k:v for k,v in c.items() if k not in ('first','last','heading')};flight_cases.extend([case,{**case,'id':case['id']+'/return','path':case['path'][::-1]}])
    suites={'edges':edges,'passages':existing+flight_cases+grade_cases}
    for name,cases in suites.items():
        assert len({c['id'] for c in cases})==len(cases),(name,'duplicate id')
        (OUT/(name+'.json')).write_text(json.dumps(cases,ensure_ascii=False,separators=(',',':')),'utf8')
    (OUT/'new_public_passages.json').write_text(json.dumps(flight_cases+grade_cases,ensure_ascii=False,separators=(',',':')),'utf8')
    (OUT/'excluded_swept_volume_probes.json').write_text(json.dumps(excluded,ensure_ascii=False,indent=2),'utf8')
    (OUT/'held_approaches.json').write_text(json.dumps(held,ensure_ascii=False,indent=2),'utf8')
    report=dict(existing_passages=len(existing),whole_flight_passages=len(flight_cases),grade_passages=len(grade_cases),edge_and_interface_cases=len(edges),held=len(held),excluded_invalid_lift_probes=len(excluded))
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2),'utf8');print(report,flush=True)


if __name__=='__main__':main()

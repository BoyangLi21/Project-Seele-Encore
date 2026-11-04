"""Load before/after copies in the installed MTR engine and prove retained services."""
import argparse,copy,json,subprocess
from pathlib import Path
from native_transit_additions import inventory
from map_pipeline.native_geometry_patch import expected,decode
from prepare_mtr_member_patch_r52 import point,edge

def verify(a):
    if '.Codex'not in str(a.stage):raise ValueError('Isolated .Codex staging required')
    a.stage.mkdir(exist_ok=False);a.out.mkdir(exist_ok=False)
    final,proof=expected(a.candidate);baseline=inventory(a.candidate/'preserved-native')
    for kind,data in [('before',baseline),('after',final)]:
        for name,raw in data.items():
            p=a.stage/kind/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    libs=Path('C:/Users/liboy/.gradle/caches/modules-2/files-2.1/org.apache.logging.log4j')
    cp=';'.join(map(str,[a.repo/'.Codex/hakone-transit/classes',a.mtr]+sorted(libs.glob('*/2.19.0/*/*.jar'))))
    for kind in('before','after'):
        with(a.out/(kind+'.log')).open('w',encoding='utf8')as log:
            subprocess.run([str(a.java),'-cp',cp,'TransitSnapshotR20',str(a.stage/kind),str(a.out/(kind+'.json'))],stdout=log,stderr=subprocess.STDOUT,check=True)
        print('Native engine loaded',kind,'isolated copy',flush=True)
    old=json.loads((a.out/'before.json').read_text('utf8'));new=json.loads((a.out/'after.json').read_text('utf8'))
    ops=json.loads((a.candidate/'native-geometry/operations.json').read_text('utf8'))
    moves={tuple(r['before']):tuple(r['after'])for r in ops['node_moves']}
    rails={edge(decode(baseline[r['before_member']])[0].value['position1'],decode(baseline[r['before_member']])[0].value['position2']):decode(final[r['after_member']])[0].value for r in ops['rail_geometry']}
    def transform(value,root=False,allow_identity=False):
        if isinstance(value,list):return[transform(v)for v in value]
        if not isinstance(value,dict):return value
        result=copy.deepcopy(value)
        if {'startPosition','endPosition','shape','verticalRadius'}<=set(value):
            r=rails.get(edge(value['startPosition'],value['endPosition']))
            if r is not None:
                for k in('startPosition','endPosition'):
                    p=point(value[k]);result[k]=dict(zip(('x','y','z'),moves.get(p,p)))
                for k in('shape','verticalRadius'):result[k]=r[k]
            return result
        for k,v in value.items():
            if allow_identity and root and k in('position1','position2'):
                p=point(v);result[k]=dict(zip(('x','y','z'),moves.get(p,p)))
            elif k!='vehicles':result[k]=transform(v)
        return result
    counts={}
    for key in('stations','platforms','routes','sidings','depots','rails','lifts'):
        if len(old[key])!=len(new[key]):raise ValueError('Loaded count changed '+key)
        counts[key]=len(new[key])
    for key in('stations','platforms','routes','sidings','depots','lifts'):
        left={r['id']:r for r in old[key]};right={r['id']:r for r in new[key]}
        if set(left)!=set(right):raise ValueError('Native identities changed '+key)
        for identity,r in left.items():
            predicted=transform(r,True,key in('platforms','sidings')and ops.get('migration_kind')=='cable_station_vertical')
            if predicted!=right[identity]:raise ValueError(('Undeclared loaded service or vehicle change',key,[k for k in predicted if predicted[k]!=right[identity].get(k)]))
    sort=lambda data:sorted(data,key=lambda r:json.dumps(r,sort_keys=True))
    if sort(old['resolved_platforms'])!=sort(new['resolved_platforms']):raise ValueError('Native platform lost its original station or route association')
    gaps=[];paths=0
    for key in('depots','sidings'):
        prior={r['id']:r for r in old[key]}
        for row in new[key]:
            for field in('path','pathSidingToMainRoute','pathMainRouteToSiding'):
                pp=row.get(field,[]);aa=prior[row['id']].get(field,[]);paths+=len(pp)
                if len(aa)!=len(pp):raise ValueError('Native path count changed')
                for i,(p,q)in enumerate(zip(pp,pp[1:])):
                    if p['endPosition']!=q['startPosition']and aa[i]['endPosition']==aa[i+1]['startPosition']:gaps.append([key,field,i])
    if gaps:raise ValueError('New native path gap')
    proof.update(loaded_counts=counts,loaded_paths_checked=paths,new_path_gaps=gaps,service_and_vehicle_records_equal=True,actual_world_written=False)
    (a.out/'validation.json').write_text(json.dumps(proof,indent=2),'utf8')
    (a.candidate/'native-load-check.json').write_text(json.dumps(proof,indent=2),'utf8')
    print(json.dumps(proof),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('candidate','stage','out','repo','mtr','java'):p.add_argument('--'+n,type=Path,required=True)
    verify(p.parse_args())

"""Refresh derived transit geometry from actual native MTR members; DB and trains stay byte-identical."""
import argparse,copy,hashlib,json,msvcrt,subprocess
from pathlib import Path
from audit_hq_mtr_protection_r52 import record
from r52_spatial_plan import BASE
from extend_world_depth_r52 import acquire_world_lock
from apply_s20_approved_semantic_repairs import atomic_replace


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];world=BASE/'WORLD_R52';folder=world/'mtr/projectseele/geofront';out=BASE/'derived_transit';out.mkdir(exist_ok=True)
    assert not(out/'APPLIED.json').exists(),'Never replay a delivered derived-data update'
    source={};tables={};rails=[]
    for kind in('stations','platforms','routes','sidings','depots','rails'):
        tables[kind]=[]
        for path in sorted((folder/kind).rglob('*')):
            if not path.is_file():continue
            raw=path.read_bytes();source[str(path.relative_to(world))]=sha(raw);data=record(raw)['data'];tables[kind].append(data)
            if kind=='rails':rails.append((path.name,data))
    hq=next(s for s in tables['stations']if s['id']==9166787716217601435)
    assert hq['position1']['y']==-575 and hq['position2']['y']==-542
    segments=[]
    for name,row in rails:
        segments.append(dict(id=name,**{'from':[row['position1'][k]for k in('x','y','z')],'to':[row['position2'][k]for k in('x','y','z')]},
            from_angle=row['angle1'],to_angle=row['angle2'],shape=row['shape'],vertical_radius=row['verticalRadius']))
    request=out/'ACTUAL_RAIL_INPUT.json';request.write_text(json.dumps(dict(segments=segments),separators=(',',':')),'utf8')
    oldargs=[json.loads(x)if x.startswith('"')else x for x in(root/'.Codex/r52_mtr_progress/candidate_compile.args').read_text().splitlines()if x.strip()]
    key='-classpath'if'-classpath'in oldargs else'-cp';classpath=oldargs[oldargs.index(key)+1];classes=out/'classes';classes.mkdir(exist_ok=True)
    compile=['-encoding','UTF-8','-classpath',classpath,'-d',str(classes),str(root/'tools/java/RailCandidateGeometryR52.java')]
    (out/'compile.args').write_text('\n'.join(json.dumps(v)for v in compile),'utf8');jdk=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin')
    with(out/'compile.log').open('wb')as log:subprocess.run([str(jdk/'javac.exe'),'@'+str(out/'compile.args')],check=True,stdout=log,stderr=subprocess.STDOUT)
    run=['-Xmx512m','-classpath',str(classes)+';'+classpath,'RailCandidateGeometryR52',str(request),str(out/'ACTUAL_NATIVE_CURVES.json'),'.5']
    (out/'run.args').write_text('\n'.join(json.dumps(v)for v in run),'utf8')
    with(out/'run.log').open('wb')as log:subprocess.run([str(jdk/'java.exe'),'@'+str(out/'run.args')],check=True,stdout=log,stderr=subprocess.STDOUT)
    curves=json.loads((out/'ACTUAL_NATIVE_CURVES.json').read_text('utf8'));assert len(curves)==len(rails)==215 and all(c['valid']for c in curves)
    actual_by_id={c['id']:c for c in curves};target=world/'native_transit_r28.json';before=target.read_bytes();old=json.loads(before)
    result=copy.deepcopy(old);result.update(tables);result['curves']=[dict(id=name,mode=r['transportMode'],kind='platform'if r['isPlatform']else'siding'if r['isSiding']else'rail',points=actual_by_id[name]['points'])for name,r in rails]
    result['depot_paths']=[dict(depot=d['id'],name=d['name'],path=d.get('path',[]))for d in tables['depots']]
    result['r52_derived_provenance']=dict(source='Exact installed native MessagePack members; real pinned MTR RailMath',member_sha256=source,
        sampling_metres=.5,world_or_db_authored=False,train_journey_verified=False)
    encoded=(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf8');(out/'native_transit_r28.json').write_bytes(encoded)
    # Resolve the actual U2 station sequence for passenger guidance, not a walking shortcut.
    stations=tables['stations'];platforms={p['id']:p for p in tables['platforms']};u2=next(r for r in tables['routes']if r.get('routeNumber')=='U2');stops=[]
    for ref in u2['routePlatformData']:
        p=platforms[ref['platformId']];centre={k:(p['position1'][k]+p['position2'][k])/2 for k in('x','y','z')}
        owners=[s for s in stations if all(min(s['position1'][k],s['position2'][k])<=centre[k]<=max(s['position1'][k],s['position2'][k])for k in('x','y','z'))]
        assert len(owners)==1,(p['id'],owners);s=owners[0];stops.append(dict(station_id=s['id'],station=s['name'],platform_id=p['id'],platform_centre=centre))
    (out/'ACTUAL_U2_SERVICE.json').write_text(json.dumps(dict(id=u2['id'],name=u2['name'],route_number=u2['routeNumber'],stops=stops,native_ride_verified=False),ensure_ascii=False,indent=2),'utf8')
    report=dict(world_written=False,derived_only=True,source_native_members=len(source),rails=len(rails),native_math_curves=len(curves),
        station_count=len(stations),original_station_names_and_IDs_retained=True,derived_sha256=sha(encoded),native_ride_verified=False)
    if args.apply:
        lock=acquire_world_lock()
        try:
            assert target.read_bytes()==before
            for name,digest in source.items():assert sha((world/name).read_bytes())==digest,name
            (out/'before_native_transit_r28.json').write_bytes(before);atomic_replace(target,encoded);assert target.read_bytes()==encoded
            for name,digest in source.items():assert sha((world/name).read_bytes())==digest,name
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
        report['world_written']=True;(out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8')
    else:(out/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()

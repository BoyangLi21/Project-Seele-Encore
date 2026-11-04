"""Prepare finite, token-preserving railway geometry changes in an offline candidate.

Existing station, route, siding, depot and vehicle identities are retained. Native
horizontal lengths must stay identical, allowing saved vehicle progress and path
distances to remain unchanged. This tool never writes the actual world.
"""
import argparse,copy,json
from pathlib import Path
from prepare_mtr_member_patch_r52 import Parser,patch,point,edge
from native_transit_additions import inventory


def decode(raw):
    reader=Parser(raw);node=reader.node()
    return node,raw[reader.offset:]


def prepare(candidate,proposal,samples,old_samples):
    root=candidate/'native-geometry'
    if root.exists():raise ValueError('Use a fresh native geometry candidate')
    before=inventory(candidate/'preserved-native')
    spec=json.loads(proposal.read_text('utf8'))
    station_lift=spec.get('migration_kind')=='cable_station_vertical'
    measured={r['id']:r for r in json.loads(samples.read_text('utf8'))}
    original={r['id']:r for r in json.loads(old_samples.read_text('utf8'))}
    moves={tuple(r['before']):tuple(r['after']) for r in spec['moves']}
    declared={};new_names=set();old_names=set();by_edge={};trace=[];proof=[]
    for row in spec['rails']:
        old,new=row['before'],row['after'];id=row['id'];result=measured[id];prior=original[id]
        if not result['valid'] or not prior['valid']:raise ValueError('Invalid native geometry '+id)
        if abs(result['length']-prior['length'])>1e-8:raise ValueError('Path distances require a different migration')
        for k in old:
            if k not in {'position1','position2','shape','verticalRadius'} and old[k]!=new[k]:raise ValueError('Non-geometric rail field changed')
        for key in ('position1','position2'):
            if point(new[key])!=moves.get(point(old[key]),point(old[key])):raise ValueError('Undeclared endpoint move')
        name=prior['native_relative_path'];dest=result['native_relative_path']
        if name in old_names or dest in new_names:raise ValueError('Duplicate native railway operation')
        node,tail=decode(before[name])
        if node.value!=old:raise ValueError('Current rail differs from proposal '+id)
        local=[];raw=patch(node,new,local)+tail
        if dest!=name and dest in before:raise ValueError('Rail endpoint destination already exists')
        declared[name]=None;declared[dest]=raw;old_names.add(name);new_names.add(dest)
        by_edge[edge(old['position1'],old['position2'])]=new
        trace.extend(dict(member=name,**t) for t in local)
        proof.append(dict(id=id,before_member=name,after_member=dest,length_before=prior['length'],length_after=result['length'],maximum_grade=result['maximum_sampled_grade']))
    # Every incident rail must follow a moved junction; no dangling old nodes.
    for name,raw in before.items():
        if '/rails/' not in name:continue
        node,_=decode(raw)
        if any(point(node.value[k]) in moves for k in ('position1','position2')) and name not in old_names:
            raise ValueError('Junction has an unmodified incident rail '+name)
    path_count=0;vehicle_arrays=0;path_members=[]
    def update(value):
        nonlocal path_count,vehicle_arrays
        if isinstance(value,list):return [update(v) for v in value]
        if not isinstance(value,dict):return value
        if {'startPosition','endPosition','startDistance','endDistance','shape','verticalRadius'}<=set(value):
            new=by_edge.get(edge(value['startPosition'],value['endPosition']))
            if new is None:
                if point(value['startPosition']) in moves or point(value['endPosition']) in moves:raise ValueError('Unknown cached edge touches moved junction')
                return value
            result=copy.deepcopy(value)
            for key in ('startPosition','endPosition'):
                q=moves.get(point(value[key]))
                if q is not None:result[key]=dict(zip(('x','y','z'),q))
            result['shape']=new['shape'];result['verticalRadius']=new['verticalRadius'];path_count+=1
            return result
        if 'vehicles' in value:vehicle_arrays+=1
        return {k:(v if k=='vehicles' else update(v)) for k,v in value.items()}
    identity_members=[]
    for name,raw in before.items():
        if not any('/'+kind+'/' in name for kind in (('depots','sidings','platforms')if station_lift else('depots','sidings'))):continue
        node,tail=decode(raw);result=update(node.value)
        if station_lift and any('/'+kind+'/' in name for kind in ('platforms','sidings')):
            for key in ('position1','position2'):
                q=moves.get(point(node.value[key]))
                if q is not None:
                    if node.value['transportMode']!='CABLE_CAR':raise ValueError('Station lift touches another transport mode')
                    result[key]=dict(zip(('x','y','z'),q))
            if any(result[k]!=node.value[k]for k in ('position1','position2')):identity_members.append(name)
        if result==node.value:continue
        local=[];declared[name]=patch(node,result,local)+tail;path_members.append(name)
        trace.extend(dict(member=name,**t) for t in local)
    root.mkdir()
    operations=[]
    for name,raw in sorted(declared.items()):
        old=before.get(name)
        if old==raw:continue
        for category,data in (('before',old),('after',raw)):
            if data is not None:
                target=root/category/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        operations.append(dict(member=name,before=old is not None,after=raw is not None))
    report=dict(operations=operations,rail_geometry=proof,cached_path_entries=path_count,cached_path_members=path_members,
                vehicle_arrays_untouched=vehicle_arrays,trace=trace,node_moves=spec['moves'],world_written=False)
    if station_lift:report.update(migration_kind='cable_station_vertical',station_identity_members=identity_members)
    (root/'operations.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    m=json.loads((candidate/'manifest.json').read_text('utf8'));m['native_geometry_patch']='native-geometry/operations.json'
    (candidate/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),'utf8')
    print('Prepared finite native geometry:',len(proof),'rails;',path_count,'cached path entries;',vehicle_arrays,'vehicle arrays unchanged')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('candidate','proposal','samples','old-samples'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();prepare(a.candidate,a.proposal,a.samples,a.old_samples)

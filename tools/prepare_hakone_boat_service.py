"""Extract only new native boat members; retain every existing service byte.

Native authoring may simulate older vehicles in its disposable copy. None of
those changed old members are published. Reconstruct an integration copy from
the untouched original members plus the additions for the final circuit proof.
"""
import argparse,json,shutil
from collections import Counter
from pathlib import Path
from native_transit_additions import inventory,assert_preserved,KINDS
from install_r53_carrier_trays import stopped_world
from prepare_mtr_member_patch_r52 import Parser


def prepare(a):
    if (a.candidate/'preserved-native').exists()or a.integration.exists():raise ValueError('Fresh native preparation required')
    old=inventory(a.baseline);current=inventory(a.runtime)
    with stopped_world(a.world):assert_preserved(a.world,old)
    if not set(old)<=set(current):raise ValueError('Native authoring removed an existing identity')
    new=sorted(set(current)-set(old));kinds=Counter(Path(n).parts[2]for n in new)
    expected=dict(rails=len(json.loads(a.plan.read_text('utf8'))['rails']),platforms=3,sidings=1,stations=3,routes=1,depots=1)
    if dict(kinds)!=expected:raise ValueError(('Unexpected new native programme',dict(kinds),expected))
    known={}
    for name,data in old.items():
        kind=Path(name).parts[2]if len(Path(name).parts)>2 else''
        if kind in KINDS:
            node=Parser(data).node().value
            if node.get('id'):known.setdefault(kind,set()).add(node['id'])
    for name in new:
        parts=Path(name).parts
        if len(parts)!=5 or parts[:2]!=('projectseele','geofront')or parts[2]not in KINDS:raise ValueError('Unexpected native addition '+name)
        node=Parser(current[name]).node().value
        identifier=node.get('id')
        if identifier is not None:
            if identifier in known.get(parts[2],set()):raise ValueError('Existing native identity reused')
            known.setdefault(parts[2],set()).add(identifier)
    shutil.copytree(a.baseline,a.candidate/'preserved-native');shutil.copytree(a.baseline,a.integration)
    for name in new:
        for root in(a.candidate/'after/mtr',a.integration):
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(current[name])
    manifest=json.loads((a.candidate/'manifest.json').read_text('utf8'))
    manifest.update(native_additions=['mtr/'+name for name in new],native_addition_counts=dict(kinds),
                    old_native_members=len(old),discarded_authoring_changes=sum(old[n]!=current[n]for n in old))
    (a.candidate/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    (a.candidate/'functional-check.json').write_text(json.dumps(dict(errors=['Reconstructed native circuit proof pending']),indent=2),'utf8')
    print('Prepared only new native members:',len(new),'preserved originals:',len(old),flush=True)


def verify(a):
    proof=json.loads(a.circuit.read_text('utf8'));manifest=json.loads((a.candidate/'manifest.json').read_text('utf8'))
    if not proof['passed']or proof['distinct_vehicles']!=1:raise ValueError('Native loop proof incomplete')
    import numpy as np
    previous=None;order=['togendai','hakonemachi','motohakone'];observed=[]
    for stop in proof['stops']:
        centre=np.asarray(stop['bogies']).mean((0,1));key='togendai'if centre[0]<0 else'motohakone'if centre[0]>450 else'hakonemachi'
        expected=next(r for r in manifest['boarding_stops']if r['port']==key)
        if np.linalg.norm(centre-np.array(expected['centre']))>.005:raise ValueError('Final native stop moved away from the tested landing')
        index=order.index(key)
        if previous is not None and index!=(previous+1)%3:raise ValueError('Native boat visits ports in an unexpected order')
        previous=index;observed.append(key)
    if len(observed)<5:raise ValueError('Native loop did not prove a repeated visit')
    shutil.copy2(a.circuit,a.candidate/'native-circuit.json')
    report=dict(errors=[],native_circuit_passed=True,native_stop_order=observed,old_native_members=manifest['old_native_members'],
        native_additions=len(manifest['native_additions']),boarding_walks=manifest['boarding_walks'],boarding_stops=manifest['boarding_stops'],
        full_hull_clearance=json.loads((a.candidate/'clearance.json').read_text('utf8')),visual_verified=False)
    (a.candidate/'functional-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Reconstructed native service and all three boarding interfaces verified:',observed,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--phase',choices=('prepare','verify'),required=True)
    for name in('world','candidate','baseline','runtime','integration','plan','circuit'):p.add_argument('--'+name,type=Path)
    a=p.parse_args();(prepare if a.phase=='prepare'else verify)(a)

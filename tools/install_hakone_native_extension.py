"""Append commissioned native MTR members, leaving every existing member intact."""
import argparse,json
from pathlib import Path
from collections import Counter
from prepare_mtr_member_patch_r52 import Parser
from install_r53_carrier_trays import stopped_world
from apply_s20_approved_semantic_repairs import atomic_replace


def install(a):
    result=json.loads(a.receipt.read_text('utf8'))
    if not result.get('passed')or not all(r.get('one_vehicle_distinct_positions',0)>=5 for r in result['validation']):
        raise ValueError('Native routes require successful individual vehicle movement')
    if a.backup.exists():raise ValueError('Use a fresh native installation receipt directory')
    kinds=('stations','platforms','rails','routes','sidings','depots');rows=[];counts=Counter()
    target_root=a.world/'mtr/projectseele/geofront'
    with stopped_world(a.world):
        for kind in kinds:
            for source in sorted((a.source/kind).rglob('*')):
                if not source.is_file():continue
                relative=source.relative_to(a.source);target=target_root/relative
                if target.exists():raise ValueError('Native identity already exists; will not overwrite: '+str(relative))
                data=source.read_bytes();value=Parser(data).node().value
                required=('position1','position2')if kind=='rails'else('id',)
                if not isinstance(value,dict)or any(k not in value for k in required):raise ValueError('Invalid native member '+str(relative))
                rows.append((target,data,relative));counts[kind]+=1
        expected={'rails':result['native_rails'],'platforms':result['native_platforms'],'routes':len(result['lines']),'stations':len(result['stations'])}
        if any(counts[k]!=n for k,n in expected.items()):raise ValueError('Incomplete native extension')
        a.backup.mkdir(parents=True);receipt=a.backup/'installation.json';written=[]
        report=dict(status='prepared',world=str(a.world),source=str(a.source),commissioning=str(a.receipt),counts=dict(counts),
                    new_members=[str(r)for _,_,r in rows],existing_members_written=[],progress_files_written=[])
        atomic_replace(receipt,json.dumps(report,indent=2).encode())
        try:
            for target,data,_ in rows:
                target.parent.mkdir(parents=True,exist_ok=True);atomic_replace(target,data);written.append(target)
            report['status']='installed';atomic_replace(receipt,json.dumps(report,indent=2).encode())
        except BaseException:
            for target in written:target.unlink(missing_ok=True)
            report['status']='rolled-back';atomic_replace(receipt,json.dumps(report,indent=2).encode());raise
    print(json.dumps({k:v for k,v in report.items()if k!='new_members'}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('world','source','receipt','backup'):p.add_argument('--'+name,type=Path,required=True)
    install(p.parse_args())

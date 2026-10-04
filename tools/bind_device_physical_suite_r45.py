"""Reorder an already root-bound lift suite after exact25 install; no world IO."""
from __future__ import annotations
import argparse,copy,json
from pathlib import Path
from prepare_device_physical_bundle_r45 import read,write,sha,ROOT

def main(args):
    out=args.out.resolve();assert not out.exists() and 'saves'not in{p.lower()for p in out.parts}
    b=read(args.bundle);receipt=read(args.apply_receipt);lease=read(args.binding);base=read(args.base_bound_job);priority=read(args.priority_cases)
    assert b['schema']=='projectseele.device-physical-bundle-r45.v1' and b['cells']==25
    assert receipt['schema']=='projectseele.device25-actual-root-apply-r45.v1' and receipt['installed'] and receipt['bundle_sha256']==sha(args.bundle)
    assert Path(receipt['world']).resolve()==Path(lease['world']).resolve() and not receipt['navigation_or_model_installed']
    assert not Path(lease['preworld_receipt_output']).exists(),'Use one fresh unused post-repair checkpoint/lease'
    assert lease['world_id']==b['source_world_id'] and int(lease['world_seed'])==int(b['source_seed'])
    assert base['bound'] and base['candidate_binding_sha256']==sha(args.binding) and Path(base['candidate_binding']).resolve()==args.binding.resolve()
    assert len(base['cases'])==len(priority['cases'])==90 and base['cases_required']==90 and base['stops_required']==24 and base['groups_required']==7
    assert not priority['bound']
    def key(c):return(c['group'],tuple(c['from_controller']),tuple(c['to_controller']),c['runtime_alias'])
    assert {key(c)for c in priority['cases']}=={key(c)for c in base['cases']} and len({key(c)for c in base['cases']})==90
    files={r['relative']:r['sha256']for r in lease['world_files']}
    assert files[b['marker']['relative']]==b['marker']['after_sha256'],'New lease does not contain the actual physical marker update'
    for row in lease['source_epoch']:assert sha(row['path'])==row['sha256'],'A source/class/artifact changed after root binding'
    assert sha(base['interfaces_file'])==base['interfaces_sha256'];interfaces=read(base['interfaces_file'])
    assert isinstance(interfaces,list) and len(interfaces)==7 and sum(len(r['landings'])for r in interfaces)==24
    job=copy.deepcopy(base);job['cases']=priority['cases'];job.update(physical_bundle=str(args.bundle.resolve()),physical_bundle_sha256=sha(args.bundle),physical_apply_receipt=str(args.apply_receipt.resolve()),physical_apply_receipt_sha256=sha(args.apply_receipt))
    out.mkdir(parents=True);path=out/'all90_physical_priority.bound.json';write(path,job)
    if args.base_launch:
        launch=read(args.base_launch);needle='-Dprojectseele.r45LiftTripCases=';assert sum(s.startswith(needle)for s in launch['command'])==1
        launch['command']=[needle+str(path)if s.startswith(needle)else s for s in launch['command']]
        write(out/'physical90_priority.launch.json',launch)
    write(out/'binding_receipt.json',dict(bound=True,world_written=False,Java_Gradle_MC_started=False,new_postrepair_lease=True,cases=90,stops=24,groups=7,deep_priority_cases=8,compact_priority_cases=6,native_verified=False))
    print('Prepared exact same90 pairs in deep/compact priority order; no process launched and no world read/written.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in('bundle','apply-receipt','binding','base-bound-job','priority-cases','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--base-launch',type=Path);main(p.parse_args())

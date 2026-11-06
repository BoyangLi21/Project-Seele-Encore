"""Check frozen offline interface evidence, without opening any world or JAR."""
import argparse,json
from pathlib import Path

def read(p):return json.loads(Path(p).read_text('utf8'))

def proofs(obj):
    if isinstance(obj,dict):
        if all(isinstance(obj.get(k),dict)and'kind'in obj[k]for k in('forward','reverse')):
            yield obj
        for v in obj.values():yield from proofs(v)
    elif isinstance(obj,list):
        for v in obj:yield from proofs(v)

def run(a):
    r=read(a.readiness);errors=[];checks=[]
    if len(r['stations'])!=10:errors.append('Expected ten bounded old-city stations')
    for q in r['evidence_files']:
        p=Path(q['path'])
        if not p.is_file():errors.append('Missing '+str(p));continue
        data=read(p);nested=list(proofs(data))
        if isinstance(data,dict)and data.get('errors'):errors.append('Evidence errors '+str(p))
        bad=[n for n in nested if any(n[d]['kind']!='strict_static_clear'for d in('forward','reverse'))]
        if bad:errors.append('Independent path failure '+str(p))
        checks.append(dict(file=str(p),bidir_proofs=len(nested),bad_proofs=len(bad)))
    port=Path(r['pending_physical_candidate']['path']);m=read(port/'manifest.json');c=read(port/'changes.json');f=read(port/'functional-check.json')
    if len(c)!=39 or m['cells']!=39:errors.append('Port candidate count changed')
    if sum(q['before']=='minecraft:air'for q in c)!=36:errors.append('Port AIR additions changed')
    altered=[q for q in c if q['before']!='minecraft:air']
    if len(altered)!=3 or any(q['before']!='projectseele:nerv_edge_rail[east=false,north=true,south=false,west=false]'or q['after']!='minecraft:air'for q in altered):errors.append('Port rail opening differs')
    if len(f['support_columns'])!=15 or len(f['guard_probes'])!=8:errors.append('Port support/guard count changed')
    if len(f['negative_tests'])!=4 or not all(q['rejected']for q in f['negative_tests']):errors.append('Port negative test failed')
    for sub in('source','delta'):
        if not(port/sub).is_dir():errors.append('Missing candidate '+sub)
    g=read(Path(r['pending_metadata_candidate']['path'])/'declaration-patch.json')
    if g['retire_count']!=39 or len(g['headroom_flag_retire'])!=39:errors.append('Gora retirement scope differs')
    if len(g['retained_north_walk'])!=3:errors.append('Gora north walk preservation differs')
    if any(q['before']['grade2']!=q['after']['grade2']or q['before']['road']!=q['after']['road']for q in g['headroom_flag_retire']):errors.append('Gora grade or road mutation proposed')
    for q in r['views_inspected']:
        if not Path(q).is_file():errors.append('Missing inspected view '+q)
    result=dict(errors=errors,stations=10,evidence_files=len(checks),independent_bidir_proofs=sum(q['bidir_proofs']for q in checks),checks=checks,
        port_candidate_cells=39,gora_obsolete_walk_claims=39,gora_north_ground_claims_kept=3,
        world_opened=False,world_written=False,live_acceptance_performed=False)
    if a.out:a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('Old-station readiness:',len(checks),'evidence files;',result['independent_bidir_proofs'],'bidir proofs; errors',errors)
    if errors:raise ValueError('Readiness evidence inconsistent')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--readiness',type=Path,required=True);p.add_argument('--out',type=Path);run(p.parse_args())

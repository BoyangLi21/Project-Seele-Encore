"""Merge unchanged historical proof with fresh native tests, keeping barriers separate."""
from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r42'


def read(path):return json.loads(path.read_text('utf8'))
def write(name,value):(ART/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')


def main():
    source=ART/'source_world_backup';old=read(source/'quality_walk_cases.json')
    original={r['id']:r for r in read(source/'quality_native_walk_results.json')}
    inventory=read(ART/'affected_path_inventory.json');fresh=read(ART/'affected_native_results.json')
    latest={r['id']:r for r in fresh};assert len(latest)==len(fresh) and all(r['status']=='pass' for r in fresh)
    cases={r['id']:r for r in old};assert len(cases)==len(old)
    barriers=[];fresh_ids=set()
    for row in inventory['cases']:
        evidence=latest[row['id']]
        for field in ('path','start','end'):
            if field in row:assert evidence[field]==row[field],(row['id'],field)
        if 'barrier' in row:
            barriers.append(dict(case=row,evidence=evidence));continue
        cases[row['id']]=row;fresh_ids.add(row['id'])
    result=[]
    for key,case in cases.items():
        proof=dict(latest[key] if key in fresh_ids else original[key])
        assert proof['status']=='pass',key
        for field in ('path','start','end'):
            if field in case:assert proof[field]==case[field],(key,field)
        proof['evidence_revision']='R42 native rerun' if key in fresh_ids else 'R41 retained; outside changed collision envelopes'
        result.append(proof)
    write('final_public_passages.json',list(cases.values()));write('final_passage_evidence.json',result)
    write('barrier_evidence.json',barriers)
    write('passage_provenance.json',dict(total=len(cases),fresh_public=len(fresh_ids),retained=len(cases)-len(fresh_ids),
          fresh_safety=len(barriers),original=len(old),added=len(cases)-len(old),
          selection='All original full player-volume sweeps overlapping changed native collision boxes; plus new reader approaches',
          inventory_sha256=hashlib.sha256((ART/'affected_path_inventory.json').read_bytes()).hexdigest()))
    print(read(ART/'passage_provenance.json'))


if __name__=='__main__':main()

"""Read-only currentworld/fullcarrier proof for changed fixed personnel parts.

This supplements frozen v4; it does not repeat or overwrite that evidence.
"""
from pathlib import Path
import argparse,json,hashlib
from audit_tv_cage_v2_interfaces_r44 import main as audit

def main(asset,out):
    asset,out=Path(asset),Path(out)
    if out.exists():raise ValueError('Fresh private interface proof required')
    d=json.loads(asset.read_text('utf8'));out.mkdir(parents=True)
    changed={'platform_r','platform_l','platform_2_r','fixed_support_2_r','staff_deck_bearings_l','staff_deck_bearings_r'}
    d['components']=[c for c in d['components'] if c['part'] in changed]
    filtered=out/'filtered_changed_components.json';filtered.write_text(json.dumps(d,separators=(',',':')),'utf8')
    audit(filtered,out)
    report=out/'complete_physical_interfaces.json';r=json.loads(report.read_text('utf8'))
    r['full_candidate_sha256']=hashlib.sha256(asset.read_bytes()).hexdigest()
    r['scope']='Only six changed fixed personnel part families; supplements immutable v4 unchanged moving/base/wall evidence. Full native new deck/guard state unions and movement envelopes separately audited.'
    r['preapply_ready']=False
    report.write_text(json.dumps(r,indent=2),'utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--asset',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.asset,a.out)

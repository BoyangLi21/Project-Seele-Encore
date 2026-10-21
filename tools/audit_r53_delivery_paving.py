"""Compare declared delivery paving with exact saved cells; never edit terrain."""
import argparse,json
from pathlib import Path
from query_blocks import read_box


def audit(world,manifest):
    rows=[]
    for receiver in manifest['receivers']:
        if not receiver.get('delivery'):continue
        cells=receiver['actual_support_cells'];positions=[c['position'] for c in cells]
        lo=tuple(min(p[a] for p in positions)for a in range(3))
        hi=tuple(max(p[a] for p in positions)for a in range(3))
        actual=read_box(world,manifest['dimension'],lo,hi)
        changes=[dict(position=c['position'],declared=c['state'],actual=actual.get(tuple(c['position']),'UNMEASURED'))
                 for c in cells if c['state']!=actual.get(tuple(c['position']),'UNMEASURED')]
        rows.append(dict(port=receiver['port'],cells=len(cells),changed=len(changes),changes=changes))
    return dict(receivers=rows,world_modified=False,collision_or_release_acceptance=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--frozen-world',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert not a.output.exists(),'Preserve earlier evidence'
    result=audit(a.frozen_world,json.loads(a.manifest.read_bytes()))
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps([{k:r[k]for k in ('port','cells','changed')}for r in result['receivers']]))

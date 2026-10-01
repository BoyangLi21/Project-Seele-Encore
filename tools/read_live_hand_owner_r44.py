"""Compact streaming owner inputs; tolerates an incomplete final async line."""
from pathlib import Path
import argparse,json
ap=argparse.ArgumentParser();ap.add_argument('source',type=Path);args=ap.parse_args();first={};last={};low={};counts={}
with args.source.open('r',encoding='utf8') as stream:
    for line in stream:
        if not line.startswith('{"kind":"final_named_palette"'):continue
        try:row=json.loads(line)
        except json.JSONDecodeError:continue
        v=row['variant'];value=row['actual_owner_inputs'];first.setdefault(v,value);last[v]=value;counts[v]=counts.get(v,0)+1
        if row['stance']>2.9:low[v]=value
keys=('powered','power_ticks','plug_inserted','pilot_entity','bay_repair','shared_body','shared_hands','stance','legacy_trigger_playing','server_movement_owner')
print(json.dumps(dict(bytes=args.source.stat().st_size,rigs=[dict(variant=v,palettes=counts[v],first={k:first[v][k]for k in keys},last={k:last[v][k]for k in keys},prone={k:low[v][k]for k in keys}if v in low else None)for v in sorted(last)]),indent=2))

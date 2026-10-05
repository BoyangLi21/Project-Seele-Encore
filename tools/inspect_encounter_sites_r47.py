"""One finite raw-voxel readback of inherited uninstalled encounter coordinates."""
from pathlib import Path
from collections import Counter
import json
from query_blocks import read_box, AIR
ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'artifacts/rebuild_r47/baseline/SEELE_R46_WORLD'
SOURCE=ROOT/'artifacts/rebuild_r45/campaign_wiring_sol_v17/tv_encounter_sites_r45.source_bound.PENDING_NATIVE.json'
OUT=ROOT/'artifacts/rebuild_r47/audio_staff/encounter_site_readback.json'

def main():
    sites=json.loads(SOURCE.read_text('utf8')); rows=[]
    for chapter,site in sites['sites'].items():
        for role in ['hero','cover','support_port','angel']:
            if role not in site:continue
            x,y,z=map(int,site[role]); bounds=((x-4,y-1,z-4),(x+4,y+24,z+4))
            blocks=read_box(WORLD,sites['dimension'],*bounds)
            floor=Counter(blocks.get((xx,y-1,zz),'UNKNOWN') for xx in range(x-4,x+5) for zz in range(z-4,z+5))
            column=[dict(pos=[x,yy,z],state=blocks.get((x,yy,z),'UNKNOWN')) for yy in range(y-1,y+25)]
            body=Counter(s for (xx,yy,zz),s in blocks.items() if yy>=y and s not in AIR)
            rows.append(dict(chapter=chapter,role=role,centre=[x,y,z],raw_bounds=bounds,
                below_9x9_state_counts=dict(floor),centre_column=column,nonair_9x25x9_counts=dict(body),
                native_collision_or_standing_proof=False))
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(dict(world=str(WORLD),source_candidate=str(SOURCE),rows=rows,
        site_installed=(WORLD/'tv_encounter_sites_r45.json').is_file(),ready_flags_changed=False,
        map_written=False,interpretation='Raw finite measurements only. Air/solid states do not certify a full EVA support footprint, shot corridor, original route or model readiness.'),ensure_ascii=False,indent=2)+'\n','utf8')
    print('Inherited uninstalled site roles measured:',len(rows),'no ready flags or world writes')

if __name__=='__main__':main()

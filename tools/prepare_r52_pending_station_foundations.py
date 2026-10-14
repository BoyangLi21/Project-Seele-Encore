"""Extract real selected-source foundation needs for Root's three pending slots.

Writes candidate planning data only. Native states, construction deltas and
all physical installation remain Root-owned after the whole curve passes.
"""
from pathlib import Path
import argparse, hashlib, json
REPO=Path(__file__).resolve().parents[1]
OUT=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009/runtime_directory/candidate')
ASSET=REPO/'src/main/resources/assets/projectseele/mesh/foot_guide_dock_r52.json'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-packet',type=Path,required=True);parser.add_argument('--support-readback',type=Path,default=OUT/'ROOT_STATION_SUPPORTS.json');args=parser.parse_args();packet=read(args.source_packet)
    if packet['dock_source_sha256']!=sha(ASSET) or len(packet['stations'])!=12:raise ValueError('Actual current12-station Source packet required; never retag an old packet')
    supports=read(args.support_readback)['resources'];rows=[]
    for variant in range(3):
        leg=f'unit{variant}/exit3/turn_in';station=next(s for s in packet['stations'] if s['leg']==leg);resource='support/'+leg
        cells={tuple(p) for p in station['native_foundation_cells']};faces=station['actual_native_pad_contact_faces']
        if station['foundation_top']!=-572 or not cells or not faces:raise ValueError('Current actual bank3 finite feet/top/faces missing')
        present={tuple(c['position']):c['state'] for c in supports.get(resource,[])}
        rows.append({'leg':leg,'variant':variant,'support_resource':resource,'foundation_top_m':station['foundation_top'],'actual_native_foundation_cells':[list(p) for p in sorted(cells)],'actual_feet':station['feet'],'actual_native_pad_contact_faces':faces,'already_root_declared_states':[{'position':list(p),'state':present[p]} for p in sorted(cells) if p in present],'pending_root_state_readback_cells':[list(p) for p in sorted(cells) if p not in present],'native_installed':False,'whole_curve_admission':False})
    report={'world_written':False,'native_installed':False,'native_admission':False,'source_packet':str(args.source_packet.resolve()),'source_packet_sha256':sha(args.source_packet),'dock_source_sha256':packet['dock_source_sha256'],'rig_source_sha256':packet['rig_source_sha256'],'pending_slots':rows,'scope':'Actual currentSource finite foot faces and required Native cells only. The repeated Source feet may share cells. Root chooses and reads real states; a missing declaration is not treated as air or filled with fabricated rail blocks.'}
    path=OUT/'PENDING_THREE_STATION_REAL_FOUNDATION_REQUIREMENTS.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'pending_slots':len(rows),'distinct_required_cells':len({tuple(p) for r in rows for p in r['actual_native_foundation_cells']}),'world_written':False,'native_admission':False,'dock_source':packet['dock_source_sha256']}))
if __name__=='__main__':main()

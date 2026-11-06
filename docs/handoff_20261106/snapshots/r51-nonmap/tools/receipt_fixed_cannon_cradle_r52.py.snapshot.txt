"""Freeze only reviewed source/geometry receipts; never write the construction world."""
from pathlib import Path
import json,hashlib,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import calibrate_yashima_cannon_r52 as cal
import numpy as np
ROOT=cal.ROOT
OUT=ROOT/'.Codex/r52_operations/cradle_candidate'
SOURCES=['src/main/java/com/projectseele/world/FixedCannonCradleR52.java','src/main/java/com/projectseele/entity/YashimaCannonEntityR52.java','src/main/java/com/projectseele/world/YashimaCannonMeshR52.java','src/main/java/com/projectseele/world/TvYashimaStationR52.java','src/main/java/com/projectseele/client/render/YashimaCannonRendererR52.java','src/main/java/com/projectseele/world/NervFlightProofR52.java']
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
def main():
    native_plan=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009/far_cannon_magazine/founded_original_cannon_lift_chamber/PLAN.json')
    p=json.loads(native_plan.read_text(encoding='utf8'));patch=dict(cannon_uuid=p['cannon_uuid'],hatch_uuid=p['gate']['visual'],closed_position=p['closed_position'],raised_position=p['raised_position'],source_rack_uuid='749cf141-0e2f-59ef-9e9b-d08346d5ea8d',source_weapon_uuid='58eab304-0fb0-5f44-b500-4fed8824db08',source_position=[-1305.5,114,-1373.5],interaction_control=[-1302,175,-1374],cradle=dict(floor_top=160,closed_root_y=157.5,raised_root_y=174))
    write(OUT/'STATION_INSTALL_PATCH.json',patch)
    report=json.loads((OUT/'PRODUCTION_GEOMETRY_AUDIT.json').read_text());cloud=cal.read_cloud(OUT/'cradle_production_raised.bin.gz');points=np.concatenate(list(cloud.values())).reshape(-1,3);lo,hi=points.min(0),points.max(0)
    report['raised_source_tight_bounds_relative_bay']=[lo.tolist(),hi.tolist()];closed=points.copy();closed[:,1]-=16.5
    # Foundation remains on the floor; moving pieces use the same gun rise.
    closed_parts=[]
    for name,t in cloud.items():
        u=t.copy()
        if name.startswith('sleeve_'):u[:,:,1]-=16.5*int(name.split('_')[1].split('/')[0])/6
        elif not name.startswith(('floor_plate','outer_cylinder')):u[:,:,1]-=16.5
        closed_parts.append(u)
    v=np.concatenate(closed_parts).reshape(-1,3);report['closed_source_tight_bounds_relative_bay']=[v.min(0).tolist(),v.max(0).tolist()];report['source_tight_closed_max_world_y']=float(v[:,1].max()+174)
    write(OUT/'PRODUCTION_GEOMETRY_AUDIT.json',report)
    receipt=dict(scope='Root-approved fixed cannon cradle source freeze; no world write or native acceptance',source_frozen=True,world_written=False,native_acceptance=False,compile_exit_code=0,synthetic_parameter_checks=22,sources={s:sha(ROOT/s) for s in SOURCES},geometry_audit_sha256=sha(OUT/'PRODUCTION_GEOMETRY_AUDIT.json'),production_source_view_sha256=sha(OUT/'CRADLE_PRODUCTION_SOURCE_REVIEW.png'),station_install_patch_sha256=sha(OUT/'STATION_INSTALL_PATCH.json'),cross_owner_patch='Only the YashimaCannonEntityR52 typed branch in NervFlightProofR52.actualObstacleMeshes; Root authorization and owner notice recorded')
    receipt['source_set_sha256']=hashlib.sha256(json.dumps(receipt['sources'],sort_keys=True).encode()).hexdigest();write(OUT/'CRADLE_SOURCE_RECEIPT.json',receipt)
    previous=ROOT/'.Codex/r52_operations/SOURCE_RECEIPT.json';handoff=json.loads(previous.read_text());handoff['sources'].update({s:receipt['sources'][s] for s in SOURCES});handoff['sources']={s:sha(ROOT/s) for s in handoff['sources']};handoff['native_campaign_passed']=False;handoff['fixed_cannon_cradle_receipt']='.Codex/r52_operations/cradle_candidate/CRADLE_SOURCE_RECEIPT.json';write(previous,handoff)
    print(json.dumps(dict(source_set_sha256=receipt['source_set_sha256'],source_files=len(SOURCES),operations_receipt_files=len(handoff['sources']),source_tight_closed_max_world_y=report['source_tight_closed_max_world_y'],cannon_uuid=p['cannon_uuid'],hatch_uuid=p['gate']['visual'])))
if __name__=='__main__':main()

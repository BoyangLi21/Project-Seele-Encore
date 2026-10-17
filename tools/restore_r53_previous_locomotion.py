"""Keep R51 combat work while restoring only the requested preceding walk/run."""
from pathlib import Path
import argparse,json,hashlib

def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);a=p.parse_args()
    source=a.base/'R50_RESTORE/client-package/overrides/projectseele-local-maps'
    previous=json.loads((source/'eva_body_r44.json').read_text('utf8'))
    destination=a.base/'client/projectseele-local-maps'
    path=destination/'eva_body_r44.json';body=json.loads(path.read_text('utf8'))
    assert body['rigs']==previous['rigs']
    for rig in ('0','1','2'):
        for clip in ('walk','run'):
            body['stance_clips_by_rig'][rig]['clips'][clip]=previous['stance_clips_by_rig'][rig]['clips'][clip]
            body['locomotion_contract_r43'][rig][clip]=previous['locomotion_contract_r43'][rig][clip]
    body.pop('r51_user_locomotion',None)
    path.write_text(json.dumps(body,ensure_ascii=False,separators=(',',':')),'utf8')
    bundle=destination/'combat_bundle_r44.json';catalog=json.loads(bundle.read_text('utf8'))
    catalog['bundle_id']='R53_REPAIRED_WITH_PREVIOUS_WALK_RUN'
    catalog['files'][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    bundle.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n','utf8')
    actual=json.loads(path.read_text('utf8'))
    assert all(actual['stance_clips_by_rig'][r]['clips'][c]==previous['stance_clips_by_rig'][r]['clips'][c] for r in ('0','1','2') for c in ('walk','run'))
    print('Actual client: preceding walk/run and their contact curves restored for all three original EVAs; rig and other clips retained.')

if __name__=='__main__':main()

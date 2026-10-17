"""Install an explicitly supplied local performance into an existing bundle."""
from pathlib import Path
import argparse, hashlib, json, math


def install(bundle, source, label):
    raw=source.read_bytes()
    clip=json.loads(raw)
    assert clip['fps'] in (30,60) and clip['duration_ticks']==460
    count=round(clip['fps']*23)+1
    for role in ('eva','angel'):
        assert len(clip[role]['frames'])==count
        assert len(set(clip[role]['bones']))==len(clip[role]['bones'])
        for curve in ('root_blocks','eye_blocks','hand_l_blocks','hand_r_blocks'):
            assert len(clip[role][curve])==count
            assert all(len(v)==3 and all(math.isfinite(x) for x in v) for v in clip[role][curve])
        assert all(len(f['rotation_wxyz'])==len(clip[role]['bones']) for f in clip[role]['frames'])
        for frame in clip[role]['frames']:
            assert all(len(q)==4 and all(math.isfinite(x) for x in q) and sum(x*x for x in q)>.5 for q in frame['rotation_wxyz'])
    assert all(len(clip['camera'][key])==count for key in ('position','target','fov'))
    manifest_path=bundle/'combat_bundle_r44.json'
    manifest=json.loads(manifest_path.read_text('utf8'))
    name='first_battle_r44.json'
    assert name in manifest['files']
    (bundle/name).write_bytes(raw)
    manifest['files'][name]=hashlib.sha256(raw).hexdigest()
    manifest['r53_finisher_revision']=label
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
    assert (bundle/name).read_bytes()==raw
    assert json.loads(manifest_path.read_text('utf8'))['files'][name]==hashlib.sha256(raw).hexdigest()
    print(f'Installed supplied performance: {count} frames at {clip["fps"]} fps; bundle read back')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--clip',type=Path,required=True)
    p.add_argument('--label',required=True)
    a=p.parse_args();install(a.bundle,a.clip,a.label)

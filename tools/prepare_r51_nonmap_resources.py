"""Select only explicitly reviewed character assets over the delivered R50 bytes."""
from pathlib import Path
import hashlib,json,shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=Path('D:/eva/artifacts/r51_nonmap_release')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    plan=json.loads((ROOT/'artifacts/rebuild_r51_nonmap/motion_render_resources.json').read_text('utf8'))
    assets=BASE/'selected_assets';runtime=BASE/'selected_runtime'
    assert not assets.exists() and not runtime.exists(), 'Preserve existing reviewed selections'
    shutil.copytree(BASE/'baseline_assets',assets)
    shutil.copytree(BASE/'baseline_runtime',runtime)
    operations=[]
    for row in plan['whitelist']:
        source=Path(row['source']);baseline=Path(row['baseline'])
        assert sha(source)==row['source_sha256'] and sha(baseline)==row['baseline_sha256']
        target=(assets if row['kind']=='jar_overlay' else runtime)/row['relative']
        assert sha(target)==row['baseline_sha256']
        shutil.copyfile(source,target);assert sha(target)==row['source_sha256']
        operations.append(dict(relative=row['relative'],kind=row['kind'],before=row['baseline_sha256'],after=row['source_sha256'],source=str(source)))
    bundle_path=runtime/'projectseele-local-maps/combat_bundle_r44.json'
    bundle=json.loads(bundle_path.read_text('utf8'));bundle['bundle_id']='R51_NONMAP_WITH_ORIGINAL_R50_WORLD'
    for name in bundle['files']:
        bundle['files'][name]=sha(runtime/'projectseele-local-maps'/name)
    bundle_path.write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n','utf8')
    files={p.relative_to(assets).as_posix():sha(p) for p in sorted(assets.rglob('*')) if p.is_file()}
    expected={r['relative'] for r in plan['whitelist'] if r['kind']=='jar_overlay'}
    changed={name for name,digest in files.items() if digest!=sha(BASE/'baseline_assets'/name)}
    assert changed==expected and len(files)==860
    manifest=dict(schema='projectseele.final-assets-frozen.r45.v1',files=files,
        source='Actual delivered R50 server JAR with only the three reviewed EVA mesh replacements',
        user_art_accepted=False,world_written=False)
    (assets/'ASSET_FROZEN.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
    receipt=dict(release='R51',baseline='R50 delivered archives',world_source_unchanged=True,
        assets=str(assets),runtime=str(runtime),operations=operations,
        runtime_bundle_metadata=dict(relative='projectseele-local-maps/combat_bundle_r44.json',sha256=sha(bundle_path)),
        asset_members=len(files),new_map_assets=0,new_yashima_or_marine_assets=0,native_verified=False)
    (BASE/'RESOURCE_SELECTION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps(dict(asset_members=len(files),changed_meshes=len(changed),changed_motion_files=3,world_written=False)))

if __name__=='__main__':main()

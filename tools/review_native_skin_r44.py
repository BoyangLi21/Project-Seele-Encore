"""Root-only isolated native skin trials with exact original asset restoration."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,time
from freeze_native_r44 import freeze
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rebuild_r44/combat/native_skin_witness'

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('case',choices=('canonical_binding','running'));a=p.parse_args();guard()
    out=BASE/('actual_binding_c_v1' if a.case=='canonical_binding' else 'actual_running_v1')
    witness=out/'actual_rigged_skin.jsonl';assert not witness.exists(),'Preserve the prior native trial'
    spec=json.loads((out/'launch_unfrozen.json').read_text('utf8'))
    assert spec['command'][spec['command'].index('--quickPlaySingleplayer')+1]=='SEELE_FIELD_R31_REVIEW'
    spec['command']=[s for s in spec['command'] if not s.startswith(('-Xms','-Xmx','-Dprojectseele.r44RigidMachineryGpu='))]
    spec['command'][1:1]=['-Xms1G','-Xmx5G','-Dprojectseele.r44RigidMachineryGpu=true']
    spec=freeze(spec,out/'epoch');launch=out/'launch_frozen.json';launch.write_text(json.dumps(spec),'utf8')
    asset=ROOT/'run/resourcepacks/eva_real_model/assets/projectseele/mesh/sachiel.mesh.json'
    original=asset.read_bytes();assert sha(original)=='c7a84d505921b787bae4ab86897f9812782a906f4232b55fe779b028791ef0f9'
    expected=sha(original);options=ROOT/'run/config/oculus.properties';prior=options.read_bytes();began=time.time()
    (out/'oculus_before.properties').write_bytes(prior)
    try:
        if a.case=='canonical_binding':
            plan=json.loads((out/'plan.json').read_text());candidate=Path(plan['overlay']).read_bytes()
            assert sha(candidate)==plan['candidate_mesh_sha'];expected=sha(candidate)
            (out/'runtime_mesh.before').write_bytes(original);asset.write_bytes(candidate)
        options.write_text(prior.decode('utf8').replace('enableShaders=true','enableShaders=false'),'utf8')
        with (out/'native.log').open('w',encoding='utf8') as log:
            code=subprocess.run([sys.executable,'-X','utf8','tools/launch_rendered_client_r17.py','--prepared-file',str(launch)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
        proofs=[p for p in (ROOT/'run/saves/SEELE_FIELD_R31_REVIEW/Review').glob('r31_combat_*.json') if p.stat().st_mtime>=began]
        assert proofs,'No fresh native scene receipt'
        proof=max(proofs,key=lambda p:p.stat().st_mtime);shutil.copy2(proof,out/'server_evidence.json')
        actual=None
        with witness.open(encoding='utf8') as stream:
            for line in stream:
                row=json.loads(line)
                if row.get('kind')=='actual-parsed-weighted-resource':actual=row;break
        assert actual and actual['source_bytes_sha256']==expected,'Native renderer did not load the intended exact source'
        (out/'root_run.json').write_text(json.dumps(dict(exit_code=code,case=a.case,source_bytes_sha256=expected,native_source_loaded=True,
            same_shader_and_rigid_gpu_settings_as_AB=True,visual_passed=False),indent=2),'utf8')
        assert code==0 and json.loads(proof.read_text()).get('passed'),str(proof)
    finally:
        asset.write_bytes(original);options.write_bytes(prior)
        assert sha(asset.read_bytes())==sha(original)
        (out/'runtime_restore.json').write_text(json.dumps(dict(source_restored=True,original_sha256=sha(original))),'utf8')

if __name__=='__main__':main()

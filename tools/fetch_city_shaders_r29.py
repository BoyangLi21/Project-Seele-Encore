"""Fetch unmodified shader components from their pinned official Modrinth files."""
from pathlib import Path
import argparse,hashlib,json,urllib.request,datetime,shutil
ROOT=Path(__file__).resolve().parents[1]

def install(enable=False):
    for row in json.loads((ROOT/'tools/city_shaders_r29.json').read_text()):
        directory=ROOT/('.Codex/local-mods' if row['project']=='oculus' else 'run/shaderpacks')
        directory.mkdir(parents=True,exist_ok=True);p=directory/row['filename']
        if not p.is_file() or hashlib.sha512(p.read_bytes()).hexdigest()!=row['sha512']:
            request=urllib.request.Request(row['url'],headers={'User-Agent':'Project-SEEELE/private-city-review'})
            with urllib.request.urlopen(request,timeout=90) as response:data=response.read()
            assert hashlib.sha512(data).hexdigest()==row['sha512'];p.write_bytes(data)
        if row['project']!='oculus':shader=p.name
    if enable:
        if shader=='ComplementaryUnbound_r5.3.zip':
            from patch_lcl_shader_compat_r35 import build
            shader=build(ROOT/'run/shaderpacks'/shader,ROOT/'run/shaderpacks/ComplementaryUnbound_r5.3_SEELE_LCL.zip').name
        revisions=[ROOT/'run/projectseele-local-maps'/name for name in ('visuals_r44.json','revision_r39.json','revision_r38.json')]
        revision=next((p for p in revisions if p.is_file()),revisions[-1])
        if revision.is_file():
            selected=json.loads(revision.read_text())['shader'];candidate=ROOT/'run/shaderpacks'/selected['filename']
            if hashlib.sha256(candidate.read_bytes()).hexdigest()!=selected['sha256']:raise ValueError('Pinned facility shader changed after review')
            shader=candidate.name
        folder=ROOT/'run/config';folder.mkdir(exist_ok=True);p=folder/'oculus.properties'
        if p.exists():
            backup=ROOT/'.Codex/shader-config-backup'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S');backup.mkdir(parents=True,exist_ok=True);shutil.copy2(p,backup/p.name)
        lines=p.read_text(encoding='utf8').splitlines() if p.exists() else []
        lines=[line for line in lines if line.partition('=')[0] not in ('enableShaders','shaderPack')]
        p.write_text('\n'.join(lines+['enableShaders=true','shaderPack='+shader])+'\n',encoding='utf8')
        # External, ordinary user settings: leave the author's ZIP unchanged.
        settings='SHADOW_QUALITY=1\nshadowDistance=128.0\nWATER_REFLECT_QUALITY=2\nBLOCK_REFLECT_QUALITY=1\nLIGHTSHAFT_QUALI_DEFINE=1\nSSAO_QUALI_DEFINE=2\nFXAA_DEFINE=1\nDETAIL_QUALITY=2\nCLOUD_QUALITY=2\nCOLORED_LIGHTING=0\nENTITY_SHADOWS_DEFINE=-1\n'
        settings+='CAVE_FOG=false\nAMBIENT_MULT=110\nBLOOM_STRENGTH=0.081\n'
        if (ROOT/'run/resourcepacks/eva_real_model/assets/projectseele/eva/un_models_r30.json').is_file():settings+='RP_MODE=3\n'
        if (ROOT/'run/resourcepacks/eva_real_model/assets/projectseele/eva/materials_r37.json').is_file():
            values=dict(line.split('=',1) for line in settings.splitlines() if '=' in line)
            values.update(SHADOW_QUALITY='2',shadowDistance='160.0',BLOCK_REFLECT_QUALITY='2',ENTITY_SHADOWS_DEFINE='1',RP_MODE='3',NORMAL_MAP_STRENGTH='70')
            settings=''.join(k+'='+v+'\n' for k,v in values.items())
        settings_path=ROOT/'run/shaderpacks'/(shader+'.txt')
        if not (revision.is_file() and settings_path.is_file()):settings_path.write_text(settings,encoding='utf8')
    print('Verified Oculus and Complementary Unbound; enabled='+str(enable))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--enable',action='store_true');install(p.parse_args().enable)

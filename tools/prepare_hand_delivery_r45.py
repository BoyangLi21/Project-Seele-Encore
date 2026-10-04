"""Freeze the root-selected anatomical hand assets as a portable core overlay.

No original source geometry, running resource pack, world, or installed client
is overwritten. Author provenance is retained without machine-specific paths.
"""
from pathlib import Path
import argparse,hashlib,json,re,shutil

ROOT=Path(__file__).resolve().parents[1]
SELECTED={0:'transition_crease_refinement_v136/unit00',1:'cannon_support_candidate_v133/unit01',2:'unit02_sword_thumb_v209/unit02'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def portable(value):
    if isinstance(value,dict):return {k:portable(v)for k,v in value.items()}
    if isinstance(value,list):return [portable(v)for v in value]
    if isinstance(value,str):
        text=value.replace('\\','/')
        if text.lower().startswith('d:/eva/'):return text[7:]
        if re.match(r'^[A-Za-z]:/',text):return 'author-reference/'+Path(text).name
    return value
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    assets=a.out/'assets/projectseele';rows=[]
    def put(src,relative):
        target=assets/relative;target.parent.mkdir(parents=True,exist_ok=True);assert not target.exists();shutil.copy2(src,target)
        rows.append(dict(source=str(src),target=target.relative_to(a.out).as_posix(),sha256=sha(target)))
    for rig,name in SELECTED.items():
        selected=ROOT/'artifacts/rebuild_r45/models/hands'/name;unit=f'eva_unit0{rig}'
        original=ROOT/f'run/resourcepacks/eva_real_model/assets/projectseele/geo/{unit}.geo.json'
        old={b['name']:b for b in json.loads(original.read_text())['minecraft:geometry'][0]['bones']}
        new={b['name']:b for b in json.loads((selected/(unit+'.geo.json')).read_text())['minecraft:geometry'][0]['bones']}
        assert all(new.get(n)==b for n,b in old.items()),'Selected candidate changed the original non-hand rig'
        c=json.loads((selected/'hand_rig_contract.json').read_text());assert c['rig']==rig
        put(selected/(unit+'.geo.json'),'geo/'+unit+'.geo.json')
        put(selected/(unit+'_anatomical_hands_r45.mesh.json'),'mesh/'+unit+'_anatomical_hands_r45.mesh.json')
        for key in ['knife_attachment_r45','sword_attachment_r45']:
            if key not in c:continue
            source=Path(c[key]['source_mesh']);source=source if source.is_absolute()else ROOT/source
            assert source.is_file();target=assets/'mesh'/source.name
            if target.exists():assert sha(target)==sha(source)
            else:put(source,'mesh/'+source.name)
            c[key]['source_mesh']=source.name
        if'mechanism' in c:raise ValueError('Unexpected unclassified generic mechanism')
        if'knife_mechanism_r45'in c:
            mesh=c['knife_mechanism_r45']['body_mesh'];put(selected/mesh,'mesh/'+mesh)
        target=assets/f'hand_rigs/unit0{rig}/hand_rig_contract.json';target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(portable(c),ensure_ascii=False,indent=2)+'\n','utf8')
        assert not re.search(r'[A-Za-z]:[/\\]',target.read_text())
        rows.append(dict(source=str(selected/'hand_rig_contract.json'),target=target.relative_to(a.out).as_posix(),sha256=sha(target),portable_provenance=True))
    texture=ROOT/'src/main/resources/assets/projectseele/textures/entity/eva02_longsword.png';put(texture,'textures/entity/'+texture.name)
    (a.out/'manifest.json').write_text(json.dumps(dict(schema='projectseele.selected-hand-delivery.r45.v1',files=rows,original_nonhand_bones_preserved=True,originals_written=False,world_written=False,user_art_accepted=False),indent=2))
    print('Frozen portable hand/core overlay:',len(rows),'files')
if __name__=='__main__':main()

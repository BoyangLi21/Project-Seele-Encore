"""Install only the complete supplied UN asset/rig package into Root's selected release inputs."""
from pathlib import Path
import json,shutil

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r48'
SOURCE=BASE/'un_native_candidate';DEST=BASE/'assets/assets/projectseele';MAPS=BASE/'runtime/projectseele-local-maps'

def main():
    backup=BASE/'un_promotion_before'
    if backup.exists():raise ValueError('UN promotion already performed; preserve the first complete before package')
    backup.mkdir();files=[];models={}
    for name in ('eva_prototype','eva_un01'):
        for rel in [f'mesh/{name}.mesh.json',f'geo/{name}.geo.json',*[f'textures/entity/{name}{suffix}.png'for suffix in ('','_n','_s','_eyes')]]:
            src=SOURCE/'assets/projectseele'/rel;dst=DEST/rel
            if not src.is_file():raise ValueError('Complete UN package member missing: '+rel)
            before=backup/'assets'/rel;before.parent.mkdir(parents=True,exist_ok=True)
            if dst.exists():shutil.copy2(dst,before)
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);files.append(rel)
        mesh=json.loads((DEST/'mesh'/f'{name}.mesh.json').read_text());geo=json.loads((DEST/'geo'/f'{name}.geo.json').read_text())
        names={b['name']for b in geo['minecraft:geometry'][0]['bones']}
        if set(mesh['parts'])-names:raise ValueError('Imported visible part lacks a real rig bone')
        if 'dorsal_cover'not in mesh['parts']or 'dorsal_liner'not in mesh['parts']:raise ValueError('Working dorsal assembly missing')
        models[name]=dict(triangles=mesh['triangleCount'],parts=len(mesh['parts']),visible_parts=sorted(mesh['parts']),
                          original_highpoly_retained=True,root_authored_rig=True,native_verified=False)
    rel='motion/un_finger_poses_r48.json';src=SOURCE/'assets/projectseele'/rel
    if not src.exists():raise ValueError('Measured fist control absent')
    (DEST/'motion').mkdir(exist_ok=True);shutil.copy2(src,DEST/rel)
    (DEST/'eva/un_models_r48.json').write_text(json.dumps(dict(schema='projectseele.owner-tripo-r48.v1',models=models),indent=2),'utf8')
    # NERV carry, handling and paired direction work may have progressed since
    # the UN candidate was authored. Merge only the two UN rig ownerships.
    for filename,sections in [('eva_body_r44.json',('rigs','rig_support','eye_positions')),
                              ('articulated_bodies_r35.json',('models',))]:
        target=MAPS/filename;shutil.copy2(target,backup/filename)
        actual=json.loads(target.read_text());candidate=json.loads((SOURCE/'projectseele-local-maps'/filename).read_text())
        for section in sections:
            for key in ('3','4'):actual[section][key]=candidate[section][key]
        target.write_text(json.dumps(actual,separators=(',',':')),'utf8')
    target=MAPS/'eva_dorsal_r30.json';shutil.copy2(target,backup/target.name)
    actual=json.loads(target.read_text());candidate=json.loads((SOURCE/'projectseele-local-maps'/target.name).read_text())
    for name in models:actual['profiles'][name]=candidate['profiles'][name]
    target.write_text(json.dumps(actual,indent=2),'utf8')
    for key in ('3','4'):
        target=MAPS/f'eva_gameplay_r44_{key}.json';shutil.copy2(target,backup/target.name)
        shutil.copy2(SOURCE/'projectseele-local-maps'/target.name,target)
    (backup/'promotion.json').write_text(json.dumps(dict(files=files,models=models,world_written=False,native_verified=False),indent=2),'utf8')
    print([(n,m['triangles'],m['parts'])for n,m in models.items()])

if __name__=='__main__':main()

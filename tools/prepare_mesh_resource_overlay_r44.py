"""Mesh-only native review overlay; base resources and installed packs remain intact."""
from pathlib import Path
import hashlib,json,re,shutil,zipfile

ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def prepare(spec,source,dest,*,cage_study=False):
    source=Path(source).resolve();dest=Path(dest);assert source.is_dir(),'Mesh overlay directory missing';files={}
    for path in source.rglob('*'):
        if not path.is_file():continue
        relative=path.relative_to(source).as_posix()
        if relative=='mesh_only_manifest.json':continue
        if cage_study:
            assert relative=='assets/projectseele/mesh/tv_shoulder_shells_r44.json','Cage study accepts one exact machinery resource only'
            document=json.loads(path.read_text('utf8'))
            assert document.get('stride')==6 and document.get('frame')=='fixed_gantry_local_metres_world_axes'
            assert document.get('parts') and document.get('collision_parts') and document.get('components')
        else:
            assert re.fullmatch(r'assets/projectseele/mesh/[a-z0-9_.-]+\.mesh\.json',relative),'Non-mesh resource overlay rejected: '+relative
            json.loads(path.read_text('utf8'))
        files[relative]=sha(path)
    assert files,'Empty mesh-only overlay'
    stage=dest/'private_resource_overlay';stage.mkdir();payload=stage/'payload'
    for relative,digest in files.items():
        target=payload/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/relative,target);assert sha(target)==digest
    entries=spec['environment']['MOD_CLASSES'].split(';');redirected=[];bases=[]
    for entry in entries:
        if '%%'not in entry:redirected.append(entry);continue
        name,directory=entry.split('%%',1);base=Path(directory)
        if name!='projectseele'or not(base/'assets').is_dir():redirected.append(entry);continue
        private=stage/('compiled_resources_'+str(len(bases)));shutil.copytree(base,private)
        for relative in files:
            target=private/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(payload/relative,target)
        redirected.append(name+'%%'+private.resolve().as_posix());bases.append(dict(original=str(base.resolve()),private=str(private.resolve())))
    assert bases,'No actual projectseele compiled resources to redirect'
    spec['environment']['MOD_CLASSES']=';'.join(redirected)
    pack=stage/'mesh_review_overlay.zip';metadata=dict(pack=dict(pack_format=15,description='SEELE R44 private mesh-only review'))
    with zipfile.ZipFile(pack,'w',zipfile.ZIP_DEFLATED,compresslevel=1)as archive:
        archive.writestr('pack.mcmeta',json.dumps(metadata))
        for relative in files:archive.write(payload/relative,relative)
    with zipfile.ZipFile(pack)as archive:
        assert all(hashlib.sha256(archive.read(relative)).hexdigest()==digest for relative,digest in files.items())
    record=dict(source=str(source),files=files,compiled_resource_redirects=bases,private_pack=str(pack.resolve()),private_pack_sha256=sha(pack),
        expected_resource_identities={relative.replace('assets/projectseele/','projectseele:'):digest for relative,digest in files.items()},
        activation_reason='Existing file/eva_real_model has higher priority than mod resources, so the same frozen mesh-only payload is temporarily selected at highest pack priority.',main_source_build_or_pack_overwritten=False)
    (stage/'resource_overlay_manifest.json').write_text(json.dumps(record,indent=2),'utf8');return spec,record

def activate(record,dest,*,kind='mesh'):
    dest=Path(dest);pack_root=(ROOT/'run/resourcepacks').resolve();options=ROOT/'run/options.txt';original=options.read_bytes();pack=Path(record['private_pack']);assert sha(pack)==record['private_pack_sha256']
    assert kind in ('mesh','material')
    target=pack_root/('seele_r44_'+kind+'_review_'+record['private_pack_sha256'][:16]+'_'+dest.name+'.zip');assert target.parent==pack_root and not target.exists(),'Temporary review pack collision'
    activation=dict(options=options,options_before=original,target=target,created=False,main_mesh_before={relative:sha(ROOT/'run/resourcepacks/eva_real_model'/relative)for relative in record['files']if(ROOT/'run/resourcepacks/eva_real_model'/relative).is_file()})
    shutil.copy2(pack,target);activation['created']=True;assert sha(target)==record['private_pack_sha256'];selected_id='file/'+target.name
    try:
        lines=original.decode('utf8').splitlines();found=False
        for i,line in enumerate(lines):
            if line.startswith('resourcePacks:'):
                chosen=json.loads(line.partition(':')[2]);chosen=[p for p in chosen if p!=selected_id]+[selected_id];lines[i]='resourcePacks:'+json.dumps(chosen,separators=(',',':'));found=True;break
        if not found:lines.append('resourcePacks:'+json.dumps(['file/eva_real_model',selected_id],separators=(',',':')))
        options.write_text('\n'.join(lines)+'\n','utf8');(dest/'resource_overlay_activation.json').write_text(json.dumps(dict(selected_pack=selected_id,options_original_sha256=hashlib.sha256(original).hexdigest(),temporary_pack_sha256=sha(target),main_mesh_before=activation['main_mesh_before']),indent=2),'utf8')
    except Exception:
        deactivate(activation,dest);raise
    return activation

def deactivate(activation,dest):
    activation['options'].write_bytes(activation['options_before']);assert activation['options'].read_bytes()==activation['options_before']
    if activation['created']:
        assert activation['target'].parent==(ROOT/'run/resourcepacks').resolve();activation['target'].unlink()
    main_after={relative:sha(ROOT/'run/resourcepacks/eva_real_model'/relative)for relative in activation['main_mesh_before']};assert main_after==activation['main_mesh_before']
    (Path(dest)/'resource_overlay_restore.json').write_text(json.dumps(dict(options_restored=True,temporary_pack_removed=not activation['target'].exists(),main_mesh_unchanged=True,main_mesh_after=main_after),indent=2),'utf8')

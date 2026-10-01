"""Prepare explicit parent-only native city QA jobs; no world write or JVM launch."""
from pathlib import Path
import argparse,json,uuid,nbtlib,hashlib,re

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
ART=ROOT/'artifacts/rebuild_r44/central_towers/native_quality'

def main():
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,default=WORLD);p.add_argument('--attempt');args=p.parse_args()
    world=args.world.resolve();ART.mkdir(parents=True,exist_ok=True)
    jobs_root=ART
    if args.attempt:
        assert re.fullmatch('[a-z0-9][a-z0-9_-]{0,63}',args.attempt),'Use a short safe attempt name'
        jobs_root=ART/('attempt_'+args.attempt)
        assert not jobs_root.exists(),'Preserve every earlier attempt and choose a new name'
    else:
        assert not (ART/'queue_contract.json').exists(),'Existing jobs/evidence must stay immutable; use --attempt'
    level=nbtlib.load(world/'level.dat')['Data'];seed=int(level['WorldGenSettings']['seed'])
    identity_file=world/'dimensions/projectseele/geofront/data/projectseele_tokyo3_building_world_id_r44.dat'
    identity=ART/'prepared_world_identity.json'
    if identity_file.exists():world_id=str(nbtlib.load(identity_file)['data']['WorldUUID'])
    elif identity.exists():world_id=json.loads(identity.read_text('utf8'))['world_id']
    else:world_id=str(uuid.uuid4())
    header=dict(world=str(world),world_seed=seed,world_id=world_id)
    if identity.exists():
        previous=json.loads(identity.read_text('utf8'))
        if previous!=header:
            if previous['world']!=header['world'] or previous['world_seed']!=header['world_seed'] or any((ART/previous['world_id']/'cargo_before').glob('tower_*.nbt')):
                raise RuntimeError('Prepared city identity/snapshot belongs to a different world')
            (ART/'unused_prepared_world_identity.before.json').write_text(json.dumps(previous,indent=2),'utf8')
    if not identity.exists() or json.loads(identity.read_text('utf8'))!=header:identity.write_text(json.dumps(header,indent=2),'utf8')
    snapshot_dir=ART/world_id/'cargo_before'
    modes=[('rooms_underground','rooms',{}),('capture_underground','capture',{}),
        ('occupied_underground','occupied',{}),('occupied_underground_roof','occupied',dict(roof_occupancy=True)),('restore_surface','travel',dict(retract=False)),
        ('rooms_surface','rooms',{}),('occupied_surface','occupied',{}),('occupied_surface_roof','occupied',dict(roof_occupancy=True)),
        ('retract_underground','travel',dict(retract=True)),
        ('interrupt_restore','interrupt',dict(retract=False,halt_on_checkpoint=True,output_group='restart_restore')),
        ('resume_restore','resume',dict(retract=False,output_group='restart_restore')),
        ('interrupt_reverse','interrupt',dict(retract=True,queue_reversal=True,halt_on_checkpoint=True,output_group='restart_reverse')),
        ('resume_reverse','resume',dict(retract=True,queue_reversal=True,output_group='restart_reverse'))]
    jobs_root.mkdir(parents=True,exist_ok=True)
    jobs=[]
    for name,mode,extra in modes:
        extra=dict(extra);outgroup=extra.pop('output_group',name)
        output_group=(('attempt_'+args.attempt+'/') if args.attempt else '')+outgroup
        data=dict(header,mode=mode,output=str(ART/world_id/output_group),snapshot_dir=str(snapshot_dir),timeout_ticks=180000,**extra)
        path=jobs_root/(name+'.json');path.write_text(json.dumps(data,indent=2),'utf8')
        jobs.append(dict(name=name,input=str(path),property='-Dprojectseele.r44TokyoQualityJob='+str(path),
            complete_marker=str(path)+('.checkpoint.json' if mode=='interrupt' else '.complete.json'),
            failed_marker=str(path)+'.failed.json'))
    plan=dict(header,jobs=jobs,world_written=False,java_started=False,
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'src/main/java/com/projectseele/world/Tokyo3BuildingQualityR44.java',ROOT/'src/main/java/com/projectseele/world/Tokyo3BuildingArchiveR44.java',ROOT/'src/main/java/com/projectseele/world/Tokyo3BuildingWorldIdentityR44.java']},
        sequence='Existing complete underground rooms/cargo/occupancy evidence remains immutable; resume the matching ongoing restore if present and verify all cargo at explicit depth0; surface rooms/occupancy; retract; interrupt/resume restoration; then interrupt descent with queued ascent back to depth0. Each interruption pair uses one durable output directory.',
        snapshot_baseline=dict(directory=str(snapshot_dir),existing_snapshots=len(list(snapshot_dir.glob('tower_*.nbt'))),policy='Never rerun capture over these files; snapshot replacement is not enabled. Reuse the preserved 93-file baseline for every actual movement/verify.'),
        snapshot_policy='93 sparse complete NBT cargo files, full prism reads including air and roof+1/+2; no all-district in-memory cache; centre immutable street controller and dome anchors separately counted',
        reference_limits='Native server use and MoverType.SELF physics are not client input or visual/user approval',
        legacy_archive_migration='No legacy archive may bind silently; if present root must preserve exact data files and explicitly set projectseele.r44BindLegacyCityArchives for one reversible migration')
    (jobs_root/'queue_contract.json').write_text(json.dumps(plan,indent=2),'utf8');print(json.dumps(dict(world_id=world_id,jobs=len(jobs),source_only=True,job_directory=str(jobs_root))))

if __name__=='__main__':main()

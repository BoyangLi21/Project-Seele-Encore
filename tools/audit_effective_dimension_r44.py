"""Inventory active world packs and frozen native resource dimension definitions."""
from pathlib import Path
import argparse,json,zipfile,hashlib
import nbtlib

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';OUT=ROOT/'artifacts/rebuild_r44/ecology'
KEY='data/projectseele/dimension/geofront.json'
sha=lambda raw:hashlib.sha256(raw).hexdigest()

def entry(origin,raw,enabled,priority,kind):
    data=json.loads(raw.decode('utf8'));g=data['generator'];b=g['biome_source']
    return dict(origin=str(origin),kind=kind,enabled=enabled,priority=priority,sha256=sha(raw),generator=g['type'],biome_source=b['type'],
        surface_datum=g.get('surface_datum'),tv_preview=g.get('tv_preview'),settings=g.get('settings'),seed_explicit=b.get('seed'),
        reservations=len(b.get('reserved_bounds',[])),underground_reservations=len(b.get('underground_reserved_bounds',[])))

def main():
    p=argparse.ArgumentParser();p.add_argument('--native-run',type=Path,default=ROOT/'artifacts/rebuild_r44/native_authors/ecology/20260930_135946');args=p.parse_args()
    level=nbtlib.load(WORLD/'level.dat')['Data'];enabled=[str(t) for t in level['DataPacks']['Enabled']];disabled=[str(t) for t in level['DataPacks']['Disabled']];found=[]
    source=ROOT/'src/main/resources'/KEY
    if source.exists():found.append(entry(source,source.read_bytes(),True,'source reference only','source'))
    for pack in (WORLD/'datapacks').iterdir():
        name='file/'+pack.name;active=name in enabled;priority=enabled.index(name) if active else None
        if pack.is_dir():
            definition=pack/KEY
            if definition.exists():found.append(entry(definition,definition.read_bytes(),active,priority,'world datapack'))
        elif zipfile.is_zipfile(pack):
            with zipfile.ZipFile(pack) as archive:
                if KEY in archive.namelist():found.append(entry(str(pack)+'!/'+KEY,archive.read(KEY),active,priority,'world zip datapack'))
    witness_path=args.native_run/'runtime_witness.json';witness=json.loads(witness_path.read_text('utf8')) if witness_path.exists() else []
    for item in witness:
        frozen=Path(item['frozen'])/KEY
        if frozen.exists():found.append(entry(frozen,frozen.read_bytes(),True,enabled.index('mod:projectseele'),'frozen native mod resource'))
    spec_path=args.native_run/'launch.json'
    if spec_path.exists():
        spec=json.loads(spec_path.read_text('utf8'));mods=Path(spec['workingDirectory'])/'mods'
        for jar in mods.glob('*.jar'):
            if not zipfile.is_zipfile(jar):continue
            with zipfile.ZipFile(jar) as archive:
                if KEY in archive.namelist():found.append(entry(str(jar)+'!/'+KEY,archive.read(KEY),'runtime mod discovered; see mod manifest','mod pack position must be verified','runtime mod jar'))
    selected=[r for r in found if r['kind'].startswith('world') and r['enabled']]
    effective=max(selected,key=lambda r:r['priority']) if selected else None
    data=dict(world=str(WORLD),world_seed=int(level['WorldGenSettings']['seed']),enabled_packs=enabled,disabled_packs=disabled,
        dimension_definitions=found,effective_world_override=effective,
        saved_level_source=str(level['WorldGenSettings']['dimensions']['projectseele:geofront']['generator']['biome_source']['type']),
        native_epoch_witness=str(witness_path),actual_native_guard_passed=json.loads((OUT/'calibration.result.json').read_text('utf8')).get('native_preview_complete',False),
        policy='Enabled world datapack definitions supersede mod dimension definitions and can overwrite serialized level.dat on load/save; inspect actual native classes and source before accepting the configuration.')
    (OUT/'effective_dimension_audit.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    print('Definition providers',len(found),'active world overrides',len(selected),'effective',effective['origin'] if effective else 'none',flush=True)

if __name__=='__main__':main()

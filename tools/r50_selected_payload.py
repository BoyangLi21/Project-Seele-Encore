"""R50 payload coverage; inherited R48 loaders remain mandatory, without hashing."""
from pathlib import Path
import json,zipfile
from r48_selected_payload import (selected_resources,sound_files,equal_streams,equal_files,
    inherited_texture_overrides,REQUIRED_R48,validate_selected_payload as inherited_payload)
ROOT=Path(__file__).resolve().parents[1]
REQUIRED_R50=REQUIRED_R48+(
 'assets/projectseele/mesh/gaghiel_r49.mesh.json',
 'assets/projectseele/geo/gaghiel_r49.geo.json',
 'assets/projectseele/animations/gaghiel_r49.animation.json',
 'assets/projectseele/textures/entity/gaghiel_r49.png')

def validate_selected_payload(jar,overlay):
    result=inherited_payload(jar,overlay)
    with zipfile.ZipFile(jar) as selected:
        entries=set(selected.namelist());classes=[]
        for source in (ROOT/'src/main/java/com/projectseele').rglob('*.java'):
            if not any(revision in source.name for revision in ('R49','R50')):continue
            name=source.relative_to(ROOT/'src/main/java').as_posix()[:-5]+'.class'
            if name not in entries:raise ValueError('Final Jar omits current R50 source class: '+name)
            classes.append(name)
        missing=[name for name in REQUIRED_R50 if name not in entries]
        if missing:raise ValueError('Final Jar omits selected R50 real encounter resources: '+str(missing))
        if 'com/projectseele/entity/GaghielEntity.class' not in entries:raise ValueError('Real Gaghiel entity is absent')
        markers={
            'com/projectseele/entity/EvaUnit01Entity.class':(b'cannonPermissionR50',b'missionPowerAnchor',b'returnedTvMissionCargoR50',b'autonomousMarineBraceR50',b'missionCannonRayClearR50'),
            'com/projectseele/entity/RamielEntity.class':(b'missionDrillR50',),
            'com/projectseele/world/TvMissionEquipmentR45.class':(b'returnToRecoveryStorage',b'issueFromRecoveryStorage'),
            'com/projectseele/world/NervPilotCombatR30.class':(b'TvMarineArrivalR50',),
            'com/projectseele/event/TvCampaignDirector.class':(b'TvYashimaDirectorR50',b'TvMarineDirectorR50')}
        for name,values in markers.items():
            if name not in entries or any(marker not in selected.read(name) for marker in values):raise ValueError('Final Jar lacks current production hooks: '+name)
    result['new_R50_classes_present']=len(classes)
    return result

def validate_identity_coverage(overlay,runtime):
 resources=selected_resources(overlay);frozen=json.loads((Path(overlay)/'ASSET_FROZEN.json').read_text('utf-8-sig'))
 expected={n for n in resources if n.startswith(('assets/','data/'))}
 if frozen.get('schema')!='projectseele.final-assets-frozen.r45.v1'or set(frozen.get('files',{}))!=expected:
  raise ValueError('ASSET_FROZEN does not cover this exact current overlay; Root must generate the final R50 identities')
 maps=Path(runtime)/'projectseele-local-maps';bundle=json.loads((maps/'combat_bundle_r44.json').read_text('utf-8-sig'))
 expected_maps={p.name for p in maps.iterdir()if p.is_file()and p.name not in('combat_bundle_r44.json','manifest.json')}
 if bundle.get('revision')!=44 or bundle.get('bundle_id')!='R50_CURRENT_SELECTED_RUNTIME'or set(bundle.get('files',{}))!=expected_maps:
  raise ValueError('Current default combat bundle identity is missing/incomplete; Root must generate the final R50 identities')
 record=json.loads(Path(frozen['source_inputs'][0]['source']).read_text('utf-8-sig'));epoch=record.get('source_epoch_r50')
 if epoch is None:raise ValueError('R50 formal source epoch missing; Root must generate current R50 identities once')
 def spec(p):
  p=Path(p).resolve();return {'path':str(p),'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns}
 if epoch.get('resources')!={n:spec(resources[n])for n in expected}or epoch.get('maps')!={n:spec(maps/n)for n in expected_maps}or epoch.get('owner')!=spec(Path(runtime)/'config/projectseele-runtime-r45.properties'):
  raise ValueError('Selected sources changed after formal R50 identity generation; final input freeze required')
 for values in(frozen['files'],bundle['files']):
  if any(not isinstance(h,str)or len(h)!=64 or any(c not in'0123456789abcdef'for c in h)for h in values.values()):raise ValueError('Malformed formal selected-resource digest')
 return {'formal_asset_members':len(expected),'formal_default_maps_members':len(expected_maps),'coverage_checked_only':True,'hash_or_native_acceptance_claimed':False}

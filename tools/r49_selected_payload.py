"""R49 payload coverage; inherited R48 loaders remain mandatory, without hashing."""
from pathlib import Path
import json,zipfile
from r48_selected_payload import (selected_resources,sound_files,equal_streams,equal_files,
    inherited_texture_overrides,REQUIRED_R48,validate_selected_payload as inherited_payload)
ROOT=Path(__file__).resolve().parents[1]
REQUIRED_R49=REQUIRED_R48

def validate_selected_payload(jar,overlay):
    result=inherited_payload(jar,overlay)
    with zipfile.ZipFile(jar) as selected:
        entries=set(selected.namelist());classes=[]
        for source in (ROOT/'src/main/java/com/projectseele').rglob('*R49*.java'):
            name=source.relative_to(ROOT/'src/main/java').as_posix()[:-5]+'.class'
            if name not in entries:raise ValueError('Final Jar omits current R49 source class: '+name)
            classes.append(name)
    result['new_R49_classes_present']=len(classes)
    return result

def validate_identity_coverage(overlay,runtime):
 resources=selected_resources(overlay);frozen=json.loads((Path(overlay)/'ASSET_FROZEN.json').read_text('utf-8-sig'))
 expected={n for n in resources if n.startswith(('assets/','data/'))}
 if frozen.get('schema')!='projectseele.final-assets-frozen.r45.v1'or set(frozen.get('files',{}))!=expected:
  raise ValueError('ASSET_FROZEN does not cover this exact current overlay; Root must generate the final R49 identities')
 maps=Path(runtime)/'projectseele-local-maps';bundle=json.loads((maps/'combat_bundle_r44.json').read_text('utf-8-sig'))
 expected_maps={p.name for p in maps.iterdir()if p.is_file()and p.name not in('combat_bundle_r44.json','manifest.json')}
 if bundle.get('revision')!=44 or bundle.get('bundle_id')!='R49_CURRENT_SELECTED_RUNTIME'or set(bundle.get('files',{}))!=expected_maps:
  raise ValueError('Current default combat bundle identity is missing/incomplete; Root must generate the final R49 identities')
 for values in(frozen['files'],bundle['files']):
  if any(not isinstance(h,str)or len(h)!=64 or any(c not in'0123456789abcdef'for c in h)for h in values.values()):raise ValueError('Malformed formal selected-resource digest')
 return {'formal_asset_members':len(expected),'formal_default_maps_members':len(expected_maps),'coverage_checked_only':True,'hash_or_native_acceptance_claimed':False}

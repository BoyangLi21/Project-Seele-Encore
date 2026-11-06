"""Native block-model paint and clipped-inset hazard strokes; no raster editing."""
import copy,hashlib,json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
name='assets/projectseele/models/block/entry_plug_bridge_fascia.json'
baseline=Path('D:/eva/artifacts/r51_nonmap_release/selected_assets')/name
model=json.loads(baseline.read_text('utf8'));original=copy.deepcopy(model)
model['textures']['hazard']='minecraft:block/white_concrete'
for element in model['elements']:
    for face in element['faces'].values():
        if face['texture']=='#hazard':face['tintindex']=0
for x in(3.75,11.75):
    for z in(-.012,.812):
        model['elements'].append(dict(from_=[x-.7,3.25,z-.002],to=[x+.7,12.25,z+.002],
            rotation=dict(origin=[x,7.75,z],axis='z',angle=45,rescale=False),
            faces={face:dict(texture='#dark',uv=[0,0,16,16])for face in('north','south')}))
        model['elements'][-1]['from']=model['elements'][-1].pop('from_')
target=root/'src/main/resources'/name;target.write_text(json.dumps(model,indent=2)+'\n','utf8')
out=root/'.Codex/r52_bridge_finish';out.mkdir(exist_ok=True)
report=dict(baseline_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),source_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),variant_colours=['#DB9A32','#8655BD','#BC3932'],existing_structural_elements_preserved=len(original['elements']),new_painted_warning_strokes=4,collision_geometry_unchanged=True,uses_existing_minecraft_white_and_black_materials=True,native_verified=False)
(out/'MODEL_RECEIPT.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report))

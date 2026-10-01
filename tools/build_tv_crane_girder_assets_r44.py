"""Original dark flange/web railmodels for the dedicated native6-state block.

Private artifacts only while root's client is running. A distinct block keeps
all other existing machine-edge floors/frames and native shapes unchanged.
"""
from pathlib import Path
import json,hashlib
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r44/hangar_machinery/tv_crane_girder_v1'


def main():
    assets=OUT/'assets/projectseele';models=assets/'models/block';textures=assets/'textures/block';states=assets/'blockstates'
    for p in (models,textures,states):p.mkdir(parents=True,exist_ok=True)
    # New original128px coatedsteel and burnished wheel strip, never TV pixels.
    for name,color in (('tv_crane_web_r44',(46,60,63)),('tv_crane_running_r44',(53,65,66))):
        im=Image.new('RGB',(128,128),color);d=ImageDraw.Draw(im)
        for y in range(0,128,16):d.line((0,y,127,y),fill=tuple(max(0,c-3) for c in color),width=1)
        if name.endswith('running_r44'):
            d.rectangle((42,0,85,127),fill=(120,135,135))
            for x in (42,44,83,85):d.line((x,0,x,127),fill=(150,162,159) if x in (44,83) else (72,87,89))
            for y in range(2,128,7):d.line((46,y,81,y),fill=(114,130,131),width=1)
        else:
            for x in (6,121):d.line((x,0,x,127),fill=(60,73,74))
        im.save(textures/(name+'.png'))
    def element(lo,hi,texture='web'):
        faces={face:{'texture':'#'+texture} for face in ('north','south','east','west','up','down')}
        return {'from':lo,'to':hi,'faces':faces}
    dims={'base':[([2.8,0,0],[13.2,1.92,16]),([7.04,1.92,0],[8.96,16,16])],
        'web':[([7.04,0,0],[8.96,16,16])],
        'top':[([7.04,0,0],[8.96,13.44,16]),([2.24,13.44,0],[13.76,16,16])]}
    variants={};shape_spec={}
    for segment,boxes in dims.items():
        for joint in (False,True):
            name='tv_crane_girder_r44_'+segment+('_joint' if joint else '')
            elements=[element(a,b) for a,b in boxes]
            if segment=='top':elements[-1]['faces']['up']['texture']='#running'
            physical=[[[x/16 for x in a],[x/16 for x in b]] for a,b in boxes]
            if joint:
                cap=13.44 if segment=='top' else 16
                elements.append(element([5.36,0,6.88],[10.64,cap,9.12]));physical.append([[5.36/16,0,6.88/16],[10.64/16,cap/16,9.12/16]])
                # Captive hexfasteners live inside the native spliceplate
                # envelope, without raised bolts on the wheel running face.
                for y in (3,10):
                    for z in (7.20,8.30):
                        elements.append(element([5.37,y,z],[5.62,y+.50,z+.50]))
                        elements.append(element([10.38,y,z],[10.63,y+.50,z+.50]))
            model={'ambientocclusion':True,'textures':{'particle':'projectseele:block/tv_crane_web_r44',
                'web':'projectseele:block/tv_crane_web_r44','running':'projectseele:block/tv_crane_running_r44'},'elements':elements}
            (models/(name+'.json')).write_text(json.dumps(model,separators=(',',':')),encoding='utf8')
            key=f'joint={str(joint).lower()},segment={segment}';variants[key]={'model':'projectseele:block/'+name};shape_spec[key]=physical
    (states/'nerv_crane_girder_r44.json').write_text(json.dumps({'variants':variants},indent=2),encoding='utf8')
    report={'same_running_plane_world_y':-373,'same_bottom_bearing_world_y':-376,'same_railcenter_offsets':[-4,4],
        'source_expected_shapes_m':shape_spec,'six_states':6,'source_block':'TvCraneGirderR44','original_material':True,
        'collision_model_relation':'Modelboxenvelopes exactly match native base/web/flange/splice; tinybolt cuboids stay inside splice solid',
        'native_shapes_export_required_before_apply':True,'installed_resources':False,'world_write_performed':False,
        'source_sha256':hashlib.sha256((ROOT/'src/main/java/com/projectseele/world/TvCraneGirderR44.java').read_bytes()).hexdigest(),
        'textures':[{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(textures.glob('*.png'))]}
    (OUT/'asset_contract.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in report.items() if k not in ('source_expected_shapes_m',)}))


if __name__=='__main__':main()

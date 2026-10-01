"""Original thin facade assets; model boxes and declared collision boxes share one definition."""
from pathlib import Path
import json,hashlib,re,argparse
from PIL import Image

ROOT=Path(__file__).resolve().parents[1];ASSET=ROOT/'src/main/resources/assets/projectseele'
NORTH={'city_rain_pipe':[[6,0,0,10,16,4]],'city_rain_gutter':[[0,12,0,16,13,4],[0,13,0,16,16,1],[0,13,3,16,16,4]]}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'artifacts/rebuild_r44/city_expansion/rain_detail_assets_v3');args=parser.parse_args()
    image=Image.new('RGB',(32,32));pixels=image.load()
    for y in range(32):
        for x in range(32):
            noise=((x*109+y*61+x*y*7)%9)-4
            seam=-7 if x in (0,31) else 0
            pixels[x,y]=(126+noise+seam,136+noise+seam,133+noise+seam)
    texture=ASSET/'textures/block/city_rain_metal_r44.png';texture.parent.mkdir(parents=True,exist_ok=True);image.save(texture)
    files=[texture];cases=[]
    for name,boxes in NORTH.items():
        model=ASSET/'models/block'/(name+'.json');state=ASSET/'blockstates'/(name+'.json');item=ASSET/'models/item'/(name+'.json')
        model.write_text(json.dumps(dict(textures=dict(all='projectseele:block/city_rain_metal_r44',particle='projectseele:block/city_rain_metal_r44'),
            elements=[dict(**{'from':box[:3],'to':box[3:]},faces={face:dict(texture='#all') for face in ['north','east','south','west','up','down']}) for box in boxes]),indent=2)+'\n','utf8')
        variants={};rotated=boxes
        java=ROOT/'src/main/java/com/projectseele/world'/('CityRainPipeR44.java' if name.endswith('pipe') else 'CityRainGutterR44.java')
        body=java.read_text('utf8')
        for i,facing in enumerate(['north','east','south','west']):
            variants['facing='+facing+(',outlet=false' if name.endswith('gutter') else '')]=dict(model='projectseele:block/'+name,y=i*90)
            declared=re.search(r'case '+facing.upper()+r' -> ([^;]+);',body).group(1)
            native=[list(map(int,m.split(', '))) for m in re.findall(r'Block\.box\(([^)]+)\)',declared)]
            assert sorted(native)==sorted(rotated),(name,facing,'Model/native collision mismatch',native,rotated)
            cases.append(dict(state='projectseele:'+name+'[facing='+facing+(',outlet=false' if name.endswith('gutter') else '')+']',source_boxes_pixels=native,model_collision_exact=True,root_native_shape_test_pending=True))
            if name.endswith('gutter'):
                connector=[[6,0,0,10,12,4]]
                for _ in range(i):connector=[[16-b[5],b[1],b[0],16-b[2],b[4],b[3]] for b in connector]
                declarations=re.findall(r'case '+facing.upper()+r' -> Block\.box\(([^)]+)\);',body)
                assert list(map(int,declarations[-1].split(', ')))==connector[0]
                variants['facing='+facing+',outlet=true']=dict(model='projectseele:block/'+name+'_outlet',y=i*90)
                cases.append(dict(state='projectseele:'+name+'[facing='+facing+',outlet=true]',source_boxes_pixels=native+connector,model_collision_exact=True,root_native_shape_test_pending=True))
            rotated=[[16-b[5],b[1],b[0],16-b[2],b[4],b[3]] for b in rotated]
        state.write_text(json.dumps(dict(variants=variants),indent=2)+'\n','utf8');item.write_text(json.dumps(dict(parent='projectseele:block/'+name),indent=2)+'\n','utf8');files.extend([model,state,item,java])
        if name.endswith('gutter'):
            outlet=ASSET/'models/block'/(name+'_outlet.json');payload=json.loads(model.read_text('utf8'))
            payload['elements'].append(dict(**{'from':[6,0,0],'to':[10,12,4]},faces={face:dict(texture='#all') for face in ['north','east','south','west','up','down']}))
            outlet.write_text(json.dumps(payload,indent=2)+'\n','utf8');files.append(outlet)
    for language,names in [('zh_cn',['旧式金属落水管','旧式金属檐沟']),('en_us',['Period Metal Downpipe','Period Metal Eaves Gutter'])]:
        file=ASSET/'lang'/(language+'.json');data=json.loads(file.read_text('utf8'))
        for name,label in zip(NORTH,names):data['block.projectseele.'+name]=label
        file.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf8');files.append(file)
    out=args.output;assert not out.exists();out.mkdir()
    (out/'shape_contract.json').write_text(json.dumps(dict(cases=cases,texture_source='Original deterministic32x32 muted galvanized-metal pixel texture; no archival/publisher imagery included',block_entities=False,
        full_cube_collision=False,source_shape_parity=True,root_compile_native_and_shader_review_pending=True,
        files=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]),indent=2),'utf8')
    print('Two facade detail assets /12 cardinal states with actual outlet connector /exact model-source collision parity PASS /native UNVERIFIED',flush=True)


if __name__=='__main__':main()

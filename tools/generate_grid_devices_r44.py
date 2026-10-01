"""Original industrial controls; code-authored textures and reproducible block models."""
from pathlib import Path
import json
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'src/main/resources/assets/projectseele'


def write_json(relative, data):
    path=ASSETS/relative
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2)+'\n','utf8')


def front_image(name, lit, indicator=False):
    size=(128,64) if indicator else (128,128)
    im=Image.new('RGB',size,(37,49,54));d=ImageDraw.Draw(im)
    d.rectangle((3,3,size[0]-4,size[1]-4),outline=(111,128,132),width=2)
    d.rectangle((8,8,size[0]-9,size[1]-9),outline=(15,25,29),width=2)
    for x in (7,size[0]-8):
        for y in (7,size[1]-8):
            d.ellipse((x-2,y-2,x+2,y+2),fill=(178,183,178))
    if indicator:
        d.rectangle((18,18,110,46),fill=(7,14,17))
        color=(97,219,174) if lit else (46,65,63)
        for x in (24,53,82):d.rectangle((x,23,x+21,41),fill=color)
        d.line((17,50,111,50),fill=(86,102,108),width=1)
    else:
        d.rectangle((28,16,100,114),fill=(18,28,32),outline=(88,105,111),width=2)
        d.line((63,22,63,33),fill=(200,210,207),width=3)
        d.ellipse((58,95,68,105),outline=(200,210,207),width=2)
        color=(91,221,170) if lit else (156,93,65)
        d.rectangle((36,39,92,47),fill=color)
        d.rectangle((35,53,93,89),fill=(56,69,74),outline=(117,134,136),width=2)
        for x in range(41,92,8):d.line((x,55,x,86),fill=(32,43,46),width=1)
    target=ASSETS/'textures/block'/f'{name}.png';target.parent.mkdir(parents=True,exist_ok=True);im.save(target)


def element(lo, hi, texture, uv=None):
    face={'texture':'#'+texture}
    if uv is not None:face['uv']=uv
    return {'from':lo,'to':hi,'faces':{name:dict(face) for name in ('north','south','east','west','up','down')}}


def main():
    for lit in (False,True):
        status='on' if lit else 'off'
        front_image('grid_switch_'+status,lit)
        front_image('circuit_indicator_'+status,lit,True)
        model=dict(parent='minecraft:block/block',textures={'front':'projectseele:block/grid_switch_'+status,
              'case':'projectseele:block/nerv_machine_panel'},elements=[
              element([2,2,14],[14,14,16],'case'),element([2.5,2.5,13.95],[13.5,13.5,14],'front',[0,0,16,16]),
              element([5,5 if lit else 7,12],[11,8 if lit else 10,14],'case'),
              element([3.5,4,12.5],[4.5,11,14],'case'),element([11.5,4,12.5],[12.5,11,14],'case')])
        write_json('models/block/nerv_grid_switch_'+status+'.json',model)
        indicator=dict(parent='minecraft:block/block',textures={'front':'projectseele:block/circuit_indicator_'+status,
              'case':'projectseele:block/nerv_machine_panel'},elements=[element([1,4,14],[15,12,16],'case'),
              element([1.4,4.4,13.95],[14.6,11.6,14],'front',[0,0,16,16])])
        write_json('models/block/nerv_circuit_indicator_'+status+'.json',indicator)
    switches={};indicators={}
    for facing,rotation in [('north',0),('east',90),('south',180),('west',270)]:
        for lit in (False,True):
            status='on' if lit else 'off';text=str(lit).lower()
            for face,pitch in [('wall',0),('floor',90),('ceiling',270)]:
                switches[f'face={face},facing={facing},powered={text}']={'model':'projectseele:block/nerv_grid_switch_'+status,'x':pitch,'y':rotation}
            indicators[f'facing={facing},lit={text}']={'model':'projectseele:block/nerv_circuit_indicator_'+status,'y':rotation}
    write_json('blockstates/nerv_grid_switch.json',{'variants':switches})
    write_json('blockstates/nerv_circuit_indicator.json',{'variants':indicators})
    for block in ('nerv_grid_switch','nerv_circuit_indicator'):
        write_json('models/item/'+block+'.json',{'parent':'projectseele:block/'+block+'_off'})
    language=ASSETS/'lang/zh_cn.json';entries=json.loads(language.read_text('utf8'))
    entries['block.projectseele.nerv_grid_switch']='NERV 馈线开关'
    entries['block.projectseele.nerv_circuit_indicator']='NERV 馈线指示灯'
    language.write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n','utf8')
    print('Original industrial switch and feeder indicator assets generated')


if __name__=='__main__':main()

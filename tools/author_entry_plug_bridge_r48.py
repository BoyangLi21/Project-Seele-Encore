"""Reference-led rear bridge plate and slender guards; no world mutation."""
from pathlib import Path
import json, shutil
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'src/main/resources/assets/projectseele'
OUT=ROOT/'artifacts/rebuild_r48/assets/assets/projectseele'

def save(relative,document):
    for root in (SRC,OUT):
        p=root/relative;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(document,indent=2)+'\n','utf8')

def box(a,b,material,uv=None):
    return dict(from_=a,to=b,faces={face:dict(texture='#'+material,uv=uv or [0,0,16,16]) for face in ('up','down','north','south','east','west')})

def model(name,elements,textures):
    for element in elements:element['from']=element.pop('from_')
    save('models/block/'+name+'.json',dict(parent='minecraft:block/block',ambientocclusion=True,textures=dict(textures,particle=textures.get('paint',textures.get('steel'))),elements=elements))

def main():
    tex=dict(paint='projectseele:block/nerv_machine_panel',steel='projectseele:block/nerv_machine_edge',dark='minecraft:block/black_concrete',hazard='projectseele:entity/nerv_pressure_hazard_r45')
    plate=[box([0,13.5,0],[16,16,16],'paint'),box([1,0,1],[3,13.5,15],'steel'),box([13,0,1],[15,13.5,15],'steel'),box([3,2,7],[13,4,9],'steel')]
    # Recess-like inset panel seams lie flush to the deck, below any footstep.
    for x in (1.8,14):plate.append(box([x,16,.9],[x+.16,16.012,15.1],'dark'))
    for z in (.9,14.94):plate.append(box([1.8,16,z],[14.16,16.012,z+.16],'dark'))
    for x in (2.5,13.0):
        for z in (1.65,13.8):plate.append(box([x,16,z],[x+.4,16.025,z+.4],'steel'))
    model('entry_plug_bridge_deck',plate,tex)
    model('entry_plug_bridge_fascia',[box([0,2,0],[16,13.5,.8],'hazard',[0,0,16,8]),box([0,12.9,0],[16,13.5,1.05],'dark'),box([0,1.5,0],[16,2,1.05],'steel')],tex)
    save('blockstates/entry_plug_bridge_deck.json',dict(multipart=[dict(apply=dict(model='projectseele:block/entry_plug_bridge_deck'))]+[
        dict(when={side:'true'},apply=dict(model='projectseele:block/entry_plug_bridge_fascia',y=turn)) for side,turn in [('north',0),('east',90),('south',180),('west',270)]]))
    model('entry_plug_bridge_rail_beam',[box([.8,8,0],[15.2,8.8,.8],'dark'),box([.8,16.8,0],[15.2,17.6,.8],'dark')],tex)
    model('entry_plug_bridge_rail_post',[box([0,0,0],[.8,17.6,.8],'dark'),box([0,0,0],[1.2,.35,1.2],'steel')],tex)
    parts=[dict(when={side:'true'},apply=dict(model='projectseele:block/entry_plug_bridge_rail_beam',y=angle))for side,angle in [('north',0),('east',90),('south',180),('west',270)]]
    for first,second,angle in [('north','west',0),('north','east',90),('south','east',180),('south','west',270)]:
        parts.append(dict(when={'OR':[{first:'true'},{second:'true'}]},apply=dict(model='projectseele:block/entry_plug_bridge_rail_post',y=angle)))
    save('blockstates/entry_plug_bridge_guard.json',dict(multipart=parts))
    for name in ('entry_plug_bridge_deck','entry_plug_bridge_guard'):
        save('models/item/'+name+'.json',dict(parent='projectseele:block/'+('entry_plug_bridge_deck' if name.endswith('deck') else 'entry_plug_bridge_rail_beam')))
        for locale,label in [('zh_cn','插入栓检修桥面' if name.endswith('deck') else '插入栓检修桥护栏'),('en_us','Entry Plug Inspection Deck' if name.endswith('deck') else 'Entry Plug Inspection Guard')]:
            for root in (SRC,OUT):
                path=root/'lang'/f'{locale}.json';data=json.loads(path.read_text('utf8'));data['block.projectseele.'+name]=label
                path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf8')
    print('Authored grey-green steel deck, inset fasteners, red-black fascia and 1.1m slender guards.')

if __name__=='__main__':main()

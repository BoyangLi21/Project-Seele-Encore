"""Prepare four supported half slabs at Yumoto's side stair entrance.

Uses captured sources only. The first tread faces a rear wall, so entering the
flight from the hall side currently requires a whole-block jump. A 2 x 2 low
landing supplies the missing half step without cutting the wall or stair.
"""
import argparse,json,math
from pathlib import Path
import nbtlib
import numpy as np
from export_hakone_station_surface import export
from author_hakone_lakefront import Editor
from map_pipeline.station_sections import StationSections
from audit_mountain_station_access import Nav,SupplementedSections,shape_for
from propose_mountain_station_steps import Overlay
from render_hakone_voxel_3d import render

def render_sections(reader,changes,shapes,out):
    from PIL import Image,ImageDraw,ImageFont
    im=Image.new('RGB',(1600,820),'#f2f4f0');draw=ImageDraw.Draw(im)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',22);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',15)
    panels=[('侧向进入首级：补齐两个半格高差','x',1179.25,2219,2227),
            ('原有楼梯保持：每个踏步由两个半格构成','z',2223.5,1173,1182)]
    positions={tuple(r['pos'])for r in changes}
    for panel,(title,axis,fixed,lo,hi)in enumerate(panels):
        ox=panel*800+65;oy=720;scale=68;low=-57;high=-48
        draw.text((panel*800+25,15),title,fill='#18362d',font=font)
        draw.text((panel*800+25,47),'蓝色为新增底半砖；棕色为原木楼梯；灰色为原结构。',fill='#38564d',font=small)
        for h in range(lo,hi):
            for y in range(low,high):
                x,z=(h,math.floor(fixed))if axis=='x'else(math.floor(fixed),h)
                state=reader.state(x,y,z);boxes,_=shape_for(state,shapes,True)
                if boxes is None:continue
                for box in boxes:
                    j=2 if axis=='x' else 0;offset=fixed-math.floor(fixed)
                    if not box[j]<=offset<box[j+3]:continue
                    left=h+box[0 if axis=='x' else 2]-lo;right=h+box[3 if axis=='x' else 5]-lo
                    bottom=y+box[1]-low;top=y+box[4]-low
                    colour='#3b96c0'if(x,y,z)in positions else'#986d49'if'_stairs['in state else'#9ea59e'
                    draw.rectangle((ox+left*scale,oy-top*scale,ox+right*scale,oy-bottom*scale),fill=colour,outline='#59675e',width=1)
        for y in range(low,high+1):draw.text((ox-42,oy-(y-low)*scale-8),str(y),fill='#38564d',font=small)
        for h in range(lo,hi+1):draw.text((ox+(h-lo)*scale-10,oy+12),str(h),fill='#38564d',font=small)
        draw.text((ox,770),('Z='+str(fixed)+' 的 X/Y 断面')if axis=='x'else('X='+str(fixed)+' 的 Z/Y 断面'),fill='#38564d',font=small)
    im.save(out)

def run(a):
    export(a.source,[2208,1168,2223,1183],a.out)
    capture=json.loads((a.out/'capture.json').read_text('utf8'))
    protected={tuple(int(t[k])for k in('x','y','z'))for t in nbtlib.load(a.out/'captured-devices.dat')['Devices']}
    changes=[];e=Editor(a.out)
    for x in (2221,2222):
        for z in (1178,1179):
            p=[x,-55,z];old=e.state(*p);bearing=e.state(x,-56,z)
            if old!='minecraft:air' or bearing!='minecraft:smooth_stone':raise ValueError('Changed landing source '+str((p,old,bearing)))
            if tuple(p)in protected:raise ValueError('Protected device at landing')
            state='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
            e.put(*p,state);changes.append(dict(pos=p,before=old,after=state,bearing=bearing))
    regions=e.save()
    if sum(r['cells']for r in regions)!=4:raise ValueError('Landing scope changed')
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound]([])}).save(a.out/'block-entities.dat',gzipped=True)
    old=SupplementedSections(a.context,a.context_supplement);fresh=StationSections(a.source)
    class Combined:
        def state(self,x,y,z):
            v=fresh.state(x,y,z)
            return old.state(x,y,z)if v is None else v
        def box(self,b):
            blocks,palette=old.box(b);new,names=fresh.box(b);ids={s:i for i,s in enumerate(palette)};codes=[]
            for state in names:
                if state not in ids:ids[state]=len(palette);palette.append(state)
                codes.append(ids[state])
            mask=new!=0;blocks[mask]=np.asarray(codes,np.uint16)[new[mask]]
            return blocks,palette
    base=Combined();after=Overlay(base,changes)
    spec=next(s for s in json.loads(a.review.read_text('utf8'))['stations']if s['id']=='yumoto')
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    proofs=[];views=[]
    for phase,reader in [('before',base),('after',after)]:
        nav=Nav(reader,spec['bounds'],shapes,True);routes,count=nav.routes(spec['goals'],'platform')
        proofs.append(dict(phase=phase,reachable_nodes=count,goals=routes))
        views.append(render(reader,[2219,-57,1171,2227,-45,1182],a.out/'review-3d'/(phase+'.png'),
                            '箱根汤本站房·楼梯侧向落脚平台 '+phase))
    old_upper=next(r['reachable']for r in proofs[0]['goals']if r['name']=='upper_room')
    errors=[]
    if old_upper:errors.append('Baseline upper room is already reachable; revise proposed repair')
    if not all(r['reachable']for r in proofs[1]['goals']):errors.append('A station goal remains unreachable')
    manifest=dict(world=capture['world'],kind='measured-yumoto-stair-landing-repair',bounds_xz=capture['bounds_xz'],
        bounds_3d=[2221,-55,1178,2222,-55,1179],regions=regions,cells=4,station='箱根湯本駅',
        changed_chunks=[[138,73]],original_floor_and_stairs_retained=True,device_changes=0,actor_changes=0,native_changes=0,
        world_written=False,production_recipe_replay_pending=True,source_snapshot=str(a.source))
    (a.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    (a.out/'step-changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=errors,changed_cells=4,before_after_routes=proofs,
        preserved_devices=len(protected),preserved_actors=len(capture['actors']),ordinary_wooden_doors_assumed_open=True,
        native_gate_bypass=False,maximum_local_riser=.5,player_width=.6,player_height=1.8,
        world_written=False,live_passenger_validation_pending=True,current_native_collision_export_pending=True),ensure_ascii=False,indent=2),'utf8')
    (a.out/'views.json').write_text(json.dumps(views,ensure_ascii=False,indent=2),'utf8')
    render_sections(after,changes,shapes,a.out/'collision-sections.png')
    print('Yumoto landing:',4,'cells;',len(protected),'preserved devices; reachable goals',
          [(r['name'],r['reachable'])for r in proofs[1]['goals']],'; errors',errors,flush=True)
    if errors:raise ValueError('Landing access proof failed')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('source','context','context-supplement','review','metadata','out'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())

"""Classify stale scalar road declarations at the installed Gora stair.

Produces a reviewable metadata-only patch and explicit multilayer paths.
Neither authority arrays nor any world file are written.
"""
import argparse,json,math
from pathlib import Path
import numpy as np
from audit_mountain_station_access import shape_for
from build_gora_protected_transfer import Combined,TrainSweep,SafeNav,IndependentWalker,GOALS
from propose_mountain_station_steps import Overlay
from review_underground_station_evidence import strict_walk
import audit_mountain_station_access as mountain
from render_hakone_voxel_3d import render

mountain.FLOORS|={'minecraft:grass_block','minecraft:dirt','minecraft:gravel','minecraft:stone','minecraft:sand','minecraft:coarse_dirt'}

def pocket_view(reader,shapes,paths,out):
    from PIL import Image,ImageDraw,ImageFont
    im=Image.new('RGB',(1800,920),'#f3f5f1');d=ImageDraw.Draw(im)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',24);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
    d.text((35,20),'强罗桥台北侧：同高地面，保留通路，不是封闭坑',font=font,fill='#16382a')
    d.text((35,60),'左：脚位 56 的实际地面与墙体；右：X=915.5 的精确碰撞断面。蓝线为独立复核路径。',font=small,fill='#426154')
    ox,oy,scale=70,140,42
    for z in range(628,643):
        for x in range(912,923):
            floor=reader.state(x,55,z);body=reader.state(x,56,z)
            color='#8faf79'if floor and'grass_block'in floor else'#c9d0c4'
            if body and body!='minecraft:air':color='#3f8092'
            d.rectangle((ox+(x-912)*scale,oy+(z-628)*scale,ox+(x-911)*scale,oy+(z-627)*scale),fill=color,outline='#f3f5f1')
    for q in paths:
        if not q['goal'].startswith('retained_north'):continue
        p=[p for p in q['path']if 912<=p[0]<=923 and 628<=p[2]<=643 and p[1]==56]
        for a,b in zip(p,p[1:]):
            if abs(a[0]-b[0])+abs(a[2]-b[2])<=1.01:d.line((ox+(a[0]-912)*scale,oy+(a[2]-628)*scale,ox+(b[0]-912)*scale,oy+(b[2]-628)*scale),fill='#155aa8',width=4)
    for x in range(914,917):
        d.ellipse((ox+(x-912+.25)*scale,oy+5.25*scale,ox+(x-912+.75)*scale,oy+5.75*scale),fill='#e59737')
    d.text((60,805),'橙点：原步道三格，脚位 56；绿色草地也为脚位 56。',font=small,fill='#244b38')
    sx,sy,ss=770,780,44
    for z in range(628,642):
        for y in range(53,67):
            state=reader.state(915,y,z);bs,_=shape_for(state or'__unavailable__',shapes,True)
            if bs is None:continue
            for b in bs:
                if not b[0]<=.5<b[3]:continue
                c='#8faf79'if'grass_block'in state else'#3f8092'if'stone_bricks'in state else'#535e62'if'iron_bars'in state else'#c9d0c4'
                d.rectangle((sx+(z+b[2]-628)*ss,sy-(y+b[4]-53)*ss,sx+(z+b[5]-628)*ss,sy-(y+b[1]-53)*ss),fill=c,outline='#647668')
    for y in range(53,68):d.text((sx-36,sy-(y-53)*ss-10),str(y),font=small,fill='#244b38')
    for z in range(628,643,2):d.text((sx+(z-628)*ss-16,sy+10),str(z),font=small,fill='#244b38')
    d.text((770,840),'桥顶北缘铁栏已按实际薄碰撞形状验证；桥台外侧无高度跌坑。',font=small,fill='#244b38')
    im.save(out)

def run(a):
    a.out.mkdir(exist_ok=False)
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    cap=json.loads((a.installed/'capture.json').read_text('utf8'))
    before=Combined(a.context,a.supplement,Path(cap['exact_station_source']))
    changes=json.loads((a.installed/'changes.json').read_text('utf8'));after=Overlay(before,changes)
    sweep=TrainSweep(json.loads(a.native.read_text('utf8')),json.loads(a.model.read_text('utf8')))
    wb=IndependentWalker(before,shapes,sweep);wa=IndependentWalker(after,shapes,sweep)
    nav=SafeNav(after,shapes,sweep)
    with np.load(a.authority/'network.npz')as f:
        ax,az,aX,aZ=map(int,f['bounds']);walk=f['walk'];road=f['road'];grade=f['grade2']
    retire=[];errors=[]
    for z in range(634,648):
        for x in range(914,917):
            if not walk[z-az,x-ax]:continue
            g=int(grade[z-az,x-ax]);feet=g/2+1;p=[x+.5,feet,z+.5]
            b=wb.body(*p);q=wa.body(*p)
            if g!=110 or b is not None or q is None:errors.append('Flag classification differed '+str([x,z]))
            existing=[dict(pos=[n[0]+.5,n[1]/2,n[2]+.5],floor_grade2=n[1]-2)
                for n in nav.column.get((x,z),[])if 56<=n[1]/2<=64]
            retire.append(dict(cell=[x,z],before={'walk':int(walk[z-az,x-ax]),'grade2':g,'road':int(road[z-az,x-ax])},
                after={'walk':0,'grade2':g,'road':int(road[z-az,x-ax])},
                old_feet=feet,before56_body=b,installed56_body=q,
                retained_old_floor=after.state(x,55,z),measured_upper_nodes=existing,
                reason='The previous feet=56 scalar claim now lies inside the supported stair/abutment; use measured multilayer access.'))
    if len(retire)!=39:errors.append('Expected exactly 39 stale scalar declarations')
    goals=dict(GOALS)
    for x in range(914,917):goals['retained_north_ground_'+str(x)]=[x,56,633]
    rows,count=nav.routes(goals,'rail_platform');proofs=[];nodeids={};nodes=[];edges=set()
    old_rows,_=SafeNav(before,shapes,sweep).routes(goals,'funicular_waiting')
    old_by={q['name']:q for q in old_rows};new_by={q['name']:q for q in rows};retained_north=[]
    for x in range(914,917):
        name='retained_north_ground_'+str(x);old=old_by[name];new=new_by[name];z=633
        if not old['reachable']or not new['reachable']:errors.append('North ground path missing '+str(x))
        retained_north.append(dict(cell=[x,z],unchanged={'walk':int(walk[z-az,x-ax]),'grade2':int(grade[z-az,x-ax]),'road':int(road[z-az,x-ax])},
            before56_path=old['path'],before56_forward=strict_walk(wb,old['path']),before56_reverse=strict_walk(wb,list(reversed(old['path']))),
            installed56_body=wa.body(x+.5,56,z+.5),installed56_has_safe_station_route=new['reachable'],
            reason='Same-level natural grass provides a measured safe detour around the abutment. Keep these three public walk declarations.'))
    def nid(p):
        key=tuple(p)
        if key not in nodeids:
            i=len(nodes);nodeids[key]=i;nodes.append(dict(id=i,pos=p,feet=p[1],layer='bridge_or_stair'if p[1]>56 else'ground',
                support=after.state(math.floor(p[0]),math.ceil(p[1])-1,math.floor(p[2]))))
        return nodeids[key]
    for row in rows:
        q=dict(goal=row['name'],requested=row['requested'],reachable=row['reachable'],path=row['path'])
        if row['reachable']:
            q['forward']=strict_walk(wa,row['path']);q['reverse']=strict_walk(wa,list(reversed(row['path'])))
            q['strict_pass']=all(q[d]['kind']=='strict_static_clear'for d in('forward','reverse'))
            if not q['strict_pass']:errors.append('Independent path failed '+q['goal'])
            ids=[nid(p)for p in row['path']];q['node_ids']=ids
            for left,right in zip(ids,ids[1:]):edges.add(tuple(sorted((left,right))))
        elif row['name']in GOALS:errors.append('Operational station destination inaccessible '+row['name'])
        proofs.append(q)
    # Reproduce the original route guard tests against the installed geometry.
    negative=[]
    for label,patch,pos in[
        ('removed_bridge_floor',dict(pos=[925,62,635],after='minecraft:air'),[925.5,63,635.5]),
        ('blocked_bridge_headroom',dict(pos=[925,64,635],after='minecraft:stone_bricks'),[925.5,63,635.5])]:
        p=strict_walk(IndependentWalker(Overlay(after,[patch]),shapes,sweep),[pos]);rejected=p['kind']!='strict_static_clear'
        negative.append(dict(case=label,rejected=rejected,result=p))
        if not rejected:errors.append('Negative test failed')
    guards=[]
    for x in range(914,917):
        pos=[x+.5,63,634.6];hit=wa.body(*pos)
        guards.append(dict(pos=pos,hit=hit))
        if hit is None or hit['kind']!='body_obstruction':errors.append('Upper north guard missing')
    pos=[915.5,63,634.6]
    removed=IndependentWalker(Overlay(after,[dict(pos=[915,63,634],after='minecraft:air')]),shapes,sweep).body(*pos)
    rejected=wa.body(*pos)is not None and removed is None
    negative.append(dict(case='removed_upper_north_guard',rejected=rejected,intact_hit=wa.body(*pos),removed_hit=removed))
    if not rejected:errors.append('Removed guard fault not detected')
    patch=dict(kind='scalar-walk-retirement-with-multilayer-replacement',authority=str(a.authority),
        exact_before_required=True,retire_count=len(retire),headroom_flag_retire=retire,retained_north_walk=retained_north,nodes=nodes,
        edges=[dict(nodes=list(e),bidirectional=True)for e in sorted(edges)],paths=proofs,
        entity_changes=0,terrain_changes=0,world_written=False,authority_written=False,
        grade2_policy='Keep original grade2 as retained ground elevation; clear only these obsolete walk bits. Do not flatten bridge layers into grade2.',
        dependent_installed_bridge=str(a.installed))
    report=dict(errors=errors,classification='stale ground-level scalar walk declarations; installed transfer remains physically passable',
        stale_flags=len(retire),operational_transfer_breaks=0 if not errors else None,
        retained_north_walk=retained_north,north_pocket_trap=False,north_ground_elevation=56,upper_north_guards=guards,
        natural_ground_in_graph=True,prior_versions_superseded='v1/v2 incorrectly omitted grass in their north-ground connectivity check; no northern walk bits should be retired.',
        before56_clear=sum(q['before56_body']is None for q in retire),after56_obstructed=sum(q['installed56_body']is not None for q in retire),
        original_ground_floor_retained=True,paths=proofs,reachable_nodes=count,independent_negative_tests=negative,
        train_envelope=sweep.info(),world_written=False,authority_written=False,
        verified_scope='Only the 39 specified Gora regressions, not all 717 global scan flags.',
        unverified=['current native collision export','rendered train and open-door sweep','live dynamic gates and passenger boarding'])
    render(after,[910,52,628,921,65,640],a.out/'north-ground-3d.png','强罗桥台北侧·同高草地绕行与上层防跌栏')
    pocket_view(after,shapes,proofs,a.out/'north-ground-plan-section.png')
    for name,data in[('declaration-patch.json',patch),('evidence.json',report)]:
        (a.out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    print('Gora declarations:',len(retire),'stale headroom;',len(retained_north),'north ground nodes kept;',sum(q.get('strict_pass',False)for q in proofs),'independent bidirectional paths; errors',errors,flush=True)
    if errors:raise ValueError('Declaration audit requires review')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in('context','supplement','metadata','native','model','installed','authority','out'):p.add_argument('--'+k,type=Path,required=True)
    run(p.parse_args())

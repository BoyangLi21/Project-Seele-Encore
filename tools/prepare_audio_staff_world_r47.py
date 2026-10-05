"""Read-only R47 light-circuit and personnel candidate; Root alone writes saves."""
from pathlib import Path
from collections import Counter
import json, math
from query_blocks import read_box, iter_block_entities, AIR

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'artifacts/rebuild_r47/baseline/SEELE_R46_WORLD'
OUT=ROOT/'artifacts/rebuild_r47/audio_staff/world'
DIM='projectseele:geofront'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    before=json.loads((WORLD/'facility_lighting_r30.json').read_text('utf8'))
    # R30's named command platform/atrium circuit, including its southern upper platforms.
    bounds=((6,-445,272),(52,-403,365))
    blocks=read_box(WORLD,DIM,*bounds)
    fixtures=[]; census=Counter()
    for q,state in blocks.items():
        name=state.split('[')[0]
        if name in {'projectseele:nerv_strip_light','projectseele:nerv_ceiling_light','projectseele:nerv_alert_light'}:
            fixtures.append(list(q)); census[name]+=1
    after=dict(before,revision='R47',command_lamps=sorted(fixtures))
    file_patches=[dict(path='facility_lighting_r30.json',before=before,after=after,
        reason='Circuit previously controlled only a stale 53-ceiling-light list; include every measured dedicated lamp in its named command room.')]
    roster=json.loads((WORLD/'nerv_staff_r15.json').read_text('utf8'))
    additions=[]; held=[]
    stations=roster['stations']; by_room={}
    for station in stations:
        by_room.setdefault(station.get('room',''),[]).append(station)
    # Known staffed rooms provide semantic ownership; no new rooms are inferred from air.
    allowed=[room for room in by_room if room.startswith(('hq/','science/','logistics/','base/'))]
    for room in allowed:
        prior=by_room[room]
        if len(prior)>3: continue
        anchor=prior[0]; x,y,z=anchor['feet']
        local=read_box(WORLD,DIM,(x-4,y-1,z-4),(x+4,y+2,z+4))
        chosen=None
        for dx,dz in [(3,0),(-3,0),(0,3),(0,-3),(3,3),(-3,-3)]:
            q=(x+dx,y,z+dz)
            if any(math.dist(q,s['feet'])<2.8 for s in stations+additions):continue
            if local.get(q) not in AIR or local.get((q[0],y+1,q[2])) not in AIR:continue
            support=local.get((q[0],y-1,q[2]),'UNKNOWN')
            if support in AIR or support=='UNKNOWN' or any(k in support for k in ('water','lcl','stairs','slab','rail','light','door')):continue
            chosen=q;break
        if chosen is None:
            held.append(dict(room=room,reason='No measured unobstructed companion work position inside known staffed-room anchor neighbourhood'));continue
        role=anchor['role']
        label={'operator':'通信轮值员','scientist':'研究记录员','technician':'设备检修员','un_crew':'UN勤务员','un_guard':'UN警戒员','guard':'安保轮值员','medic':'医疗轮值员'}.get(role,'设施值班员')
        row=dict(id='r47/staff/'+room.replace('/','_'),name=label,role=role,skin=anchor['skin'],feet=list(chosen),yaw=anchor['yaw'],room=room)
        additions.append(row)
    # New experiment hall is authored by the facility agent; install these only after that patch.
    lab=[]
    for index,x in enumerate((30,58)):
        lab.append(dict(id=f'r47/experiment/researcher_{index}',name=('同步实验研究员' if index==0 else 'LCL实验研究员'),role='scientist',skin='technician',feet=[x,-468,-81],yaw=180,room='r47/experiment_control',requires_component='r47/experiment_hall'))
    after_roster=dict(roster,stations=stations+additions+lab)
    file_patches.append(dict(path='nerv_staff_r15.json',before=roster,after=after_roster,reason='Append distinct new work posts; every original row and existing UUID mapping remains untouched.'))
    patch=dict(schema='projectseele.r47.files.before_after.v1',world=str(WORLD),files=file_patches,
        forward_patch=file_patches,inverse_patch=[dict(path=r['path'],before=r['after'],after=r['before']) for r in file_patches],
        world_written=False,nbt_written=False,old_identity_map_unchanged=True)
    (OUT/'personnel_circuit_patch.json').write_text(json.dumps(patch,ensure_ascii=False,indent=2)+'\n','utf8')
    (OUT/'survey.json').write_text(json.dumps(dict(command_room_bounds=bounds,fixture_counts=dict(census),old_controlled=len(before['command_lamps']),new_controlled=len(fixtures),added_posts=additions,experiment_posts=lab,held=held,world_written=False),ensure_ascii=False,indent=2)+'\n','utf8')
    print('Command fixtures:',dict(census),'staff additions:',len(additions),'lab:',len(lab),'held:',len(held))

if __name__=='__main__':main()

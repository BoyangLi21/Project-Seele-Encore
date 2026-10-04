"""Two through services, reusing surveyed alignments and native station identities."""
from pathlib import Path
import copy,hashlib,json,math
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/access_r22/transit'
DIR={'E':(1,0),'W':(-1,0),'N':(0,-1),'S':(0,1)}
def xyz(p):return tuple(p[k] for k in ('x','y','z'))
def pos(p):return dict(zip(('x','y','z'),p))
def key(a,b):return tuple(sorted((xyz(a),xyz(b))))
def ident(label):return int.from_bytes(hashlib.sha256(('seele/r22/'+label).encode()).digest()[:8],'big')&0x7fffffffffffffff
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 s=json.loads((OUT.parent/'native_before.json').read_text());routes={r['routeNumber']:r for r in s['routes']};deps={d['routeIds'][0]:d for d in s['depots']}
 paths={r['routeNumber']:copy.deepcopy(next(d['path'] for d in s['depot_paths'] if d['depot']==deps[r['id']]['id'])) for r in s['routes']}
 oldrails={key(r['position1'],r['position2']):r for r in s['rails']};oldplats={key(p['position1'],p['position2']):p for p in s['platforms']}
 template=next(r for r in s['rails'] if r['transportMode']=='TRAIN' and not r['isPlatform'] and not r['isSiding'])
 ptemplate=next(r for r in s['rails'] if r['transportMode']=='TRAIN' and r['isPlatform'])
 rails={};platforms={};migrations=[]
 def segment(a,aa,b,bb,platform=None):return dict(startPosition=pos(a),startAngle=aa,endPosition=pos(b),endAngle=bb,platform=platform)
 def copied(line,start,end):
  result=copy.deepcopy(paths[line][start:end])
  for q in result:
   p=oldplats.get(key(q['startPosition'],q['endPosition']));q['platform']=copy.deepcopy(p) if p else None
  return result
 def endpoint(q,field,p):q[field]=pos(p)
 def newplat(label,original,a,b):
  p=copy.deepcopy(original);p.update(id=ident(label),position1=pos(a),position2=pos(b));return p
 # R1 is extended at both ends: housing--Hakone--Tokyo--Bay airport.
 kiri=copied('S2',0,6);out=copied('R1',0,7);bay=copied('A1',1,7);retbay=copied('A1',7,14);ret=copied('R1',8,14);retk=copied('S2',8,14)
 endpoint(kiri[-1],'endPosition',xyz(out[0]['startPosition']))
 endpoint(bay[0],'startPosition',xyz(out[-1]['endPosition']))
 endpoint(ret[0],'startPosition',xyz(retbay[-1]['endPosition']))
 hp=ret[-1]['platform'];ha=xyz(ret[-1]['startPosition']);hb=xyz(ret[-1]['endPosition']);ha=(ha[0],130,632);hb=(hb[0],130,632)
 ret[-1]=segment(ha,'W',hb,'E',newplat('hakone_r1_return',hp,ha,hb));endpoint(ret[-2],'endPosition',ha);endpoint(retk[0],'startPosition',hb)
 line1=kiri+out+bay+retbay+ret+retk
 # The old shared terminal throats swapped track sides when stitched. Keep a
 # consistent running side and grade-separate Hakone's western junction.
 replace1={(-1528,118,640):(-1528,130,640),(-1432,118,640):(-1432,130,640),(-2404,114,700):(-2404,119,700),(-2396,114,700):(-2396,119,700),(-168,94,-136):(-168,94,-176),(-72,94,-136):(-72,94,-176)}
 for q in line1:
  for field in ('startPosition','endPosition'):q[field]=pos(replace1.get(xyz(q[field]),xyz(q[field])))
 # S1 now crosses both cities, reaches the NERV gateway and terminates at port.
 line2=copied('S1',10,20)
 endpoint(line2[-2],'endPosition',(-1528,118,680));endpoint(line2[-1],'startPosition',(-1528,118,680));endpoint(line2[-1],'endPosition',(-1432,118,680))
 nerv=copy.deepcopy(oldplats[key(paths['C1'][8]['startPosition'],paths['C1'][8]['endPosition'])]);bp=copy.deepcopy(oldplats[key(paths['C1'][4]['startPosition'],paths['C1'][4]['endPosition'])]);port=copy.deepcopy(oldplats[key(paths['P1'][4]['startPosition'],paths['P1'][4]['endPosition'])])
 no=newplat('nerv_out',nerv,(-408,94,688),(-312,94,688));bo=newplat('bay_s1_out',bp,(312,106,348),(312,106,252))
 line2 += [segment((-1432,118,680),'E',(-408,94,688),'W'),segment((-408,94,688),'E',(-312,94,688),'W',no),
  segment((-312,94,688),'E',(272,106,688),'W'),segment((272,106,688),'E',(312,106,640),'S'),segment((312,106,640),'N',(312,106,348),'S'),segment((312,106,348),'N',(312,106,252),'S',bo),
  segment((312,106,252),'N',(440,106,124),'W'),segment((440,106,124),'E',(1030,98,124),'W'),segment((1030,98,124),'E',(1080,96,174),'N'),segment((1080,96,174),'S',(1080,94,400),'N'),segment((1080,94,400),'S',(1160,94,472),'W'),
  segment((1160,94,472),'E',(1208,94,472),'W',port),segment((1208,94,472),'W',(1160,94,472),'E',port),
  segment((1160,94,472),'W',(1088,94,400),'S'),segment((1088,94,400),'N',(1088,96,174),'S'),segment((1088,96,174),'N',(1030,98,116),'E'),segment((1030,98,116),'W',(440,106,116),'E'),segment((440,106,116),'W',(320,106,252),'N')]
 bp.update(position1=pos((320,106,252)),position2=pos((320,106,348)))
 line2 += [segment((320,106,252),'S',(320,106,348),'N',bp),segment((320,106,348),'S',(320,106,632),'N'),segment((320,106,632),'S',(272,106,680),'E'),segment((272,106,680),'W',(-312,94,680),'E'),segment((-312,94,680),'W',(-408,94,680),'E',nerv)]
 hak=copy.deepcopy(oldplats[key(paths['S1'][0]['startPosition'],paths['S1'][0]['endPosition'])]);hr=newplat('hakone_s1_return',hak,(-1432,118,672),(-1528,118,672))
 line2 += [segment((-408,94,680),'W',(-1432,118,672),'E'),segment((-1432,118,672),'W',(-1528,118,672),'E',hr)]
 back=copied('S1',1,10);endpoint(back[0],'startPosition',(-1528,118,672));line2+=back
 replace2={(312,106,640):(320,106,640),(312,106,348):(320,106,348),(312,106,252):(320,106,252),(320,106,252):(312,106,252),(320,106,348):(312,106,348),(320,106,632):(312,106,640),(440,106,124):(440,106,132),(440,106,116):(440,106,124),(1030,98,124):(1030,98,132),(1030,98,116):(1030,98,124)}
 for q in line2:
  for field in ('startPosition','endPosition'):q[field]=pos(replace2.get(xyz(q[field]),xyz(q[field])))
 allseq={'R1':line1,'S1':line2}
 def add(q,kind='rail',speed=90):
  a,b=q['startPosition'],q['endPosition'];k=key(a,b)
  if k in rails:
   prior=rails[k];assert kind=='platform' or prior['isPlatform'],('duplicate running track',k)
   return
  r=copy.deepcopy(ptemplate if kind=='platform' else template);r.update(position1=copy.deepcopy(a),position2=copy.deepcopy(b),angle1=q['startAngle'],angle2=q['endAngle'],isPlatform=kind=='platform',isSiding=kind=='siding',canTurnBack=kind=='siding',canConnectRemotely=False,signalColors=[],speedLimit1=speed,speedLimit2=speed if kind in ('platform','siding') else 0)
  rails[k]=r
 for line,seq in allseq.items():
  # Extend each platform and every incident throat by the same endpoint map.
  length=128 if line=='R1' else 96;mapping={}
  for q in seq:
   p=q['platform']
   if p is None:continue
   a,b=xyz(q['startPosition']),xyz(q['endPosition']);dx,dz=DIR[q['startAngle']];cx,cy,cz=[(a[i]+b[i])//2 for i in range(3)];aa=(cx-dx*length//2,cy,cz-dz*length//2);bb=(cx+dx*length//2,cy,cz+dz*length//2)
   mapping[a]=aa;mapping[b]=bb
  for q in seq:
   q['startPosition']=pos(mapping.get(xyz(q['startPosition']),xyz(q['startPosition'])));q['endPosition']=pos(mapping.get(xyz(q['endPosition']),xyz(q['endPosition'])))
   p=q['platform']
   if p is not None:
    if p['id'] not in platforms:
     original=next((x for x in s['platforms'] if x['id']==p['id']),None);p=copy.deepcopy(p);p.update(position1=q['startPosition'],position2=q['endPosition'],dwellTime=14000,name=str(1 if line=='R1' else 3));platforms[p['id']]=p
     migrations.append(dict(id=p['id'],line=line,old=[xyz(original['position1']),xyz(original['position2'])] if original else None,new=[xyz(p['position1']),xyz(p['position2'])]))
    add(q,'platform',80)
   else:add(q)
 # Keep U1/U2 and both flight alignments byte-for-byte; their identities survive.
 out={k:copy.deepcopy(s[k]) for k in ('stations','lifts')};out['rails']=[r for r in s['rails'] if r['transportMode']!='TRAIN' or r['position1']['y']<0]+list(rails.values())
 out['platforms']=[p for p in s['platforms'] if p['transportMode']!='TRAIN' or p['position1']['y']<0]+list(platforms.values())
 retained={'U1','U2','F1','F2'};out['routes']=[copy.deepcopy(r) for r in s['routes'] if r['routeNumber'] in retained];out['sidings']=[];out['depots']=[]
 for r in out['routes']:
  d=copy.deepcopy(deps[r['id']]);out['depots'].append(d)
  sid=copy.deepcopy(next(x for x in s['sidings'] if x['name'].startswith(r['routeNumber'])))
  if r['transportMode']=='TRAIN':
   trailer=copy.deepcopy(sid['vehicleCars'][0]);trailer.update(vehicleId='eidan_9000_mini_trailer',bogie1Position=-5.0,bogie2Position=5.0,couplingPadding1=0.0,couplingPadding2=0.0)
   sid['vehicleCars'][1:1]=[copy.deepcopy(trailer),copy.deepcopy(trailer)]
  out['sidings'].append(sid)
 for line,seq in allseq.items():
  stops=[]
  for q in seq:
   if q['platform'] is not None and (not stops or stops[-1]['platformId']!=q['platform']['id']):stops.append(dict(platformId=q['platform']['id'],customDestination=''))
  r=copy.deepcopy(routes[line]);r.update(name='雾里—箱根—第三新东京—湾岸机场贯通线' if line=='R1' else '新箱根机场—NERV—湾岸港口贯通线',routePlatformData=stops);out['routes'].append(r)
  a,b=((-3032,94,-960),(-2856,94,-960)) if line=='R1' else ((-1920,94,-265),(-1760,94,-265));first=xyz(seq[0]['startPosition']);assert first[0]>b[0]
  q=segment(a,'E',b,'W');add(q,'siding',30);out['rails'].append(rails[key(pos(a),pos(b))]);q=segment(b,'E',first,'W');add(q,'siding',30);link=rails[key(pos(b),pos(first))];link['isSiding']=False;link['canTurnBack']=False;out['rails'].append(link)
  sid=copy.deepcopy(next(x for x in s['sidings'] if x['name'].startswith(line)));sid.update(position1=pos(a),position2=pos(b),railLength=b[0]-a[0],maxVehicles=24,name=line+'车辆段')
  stock=copy.deepcopy(next(x for x in s['sidings'] if x['name'].startswith('R1'))['vehicleCars']);sid['vehicleCars']=stock[:1]+[copy.deepcopy(stock[1]) for _ in range(4 if line=='R1' else 2)]+stock[-1:];out['sidings'].append(sid)
  d=copy.deepcopy(deps[r['id']]);d.update(position1=pos((a[0]-8,a[1]-5,a[2]-8)),position2=pos((b[0]+8,b[1]+15,b[2]+8)),name=r['name']+'运营所',routeIds=[r['id']],repeatInfinitely=True,useRealTime=True,realTimeDepartures=list(range(0,86400000,60000)),frequencies=[240]*24);out['depots'].append(d)
 for sid in out['sidings']:
  for k in ('vehicles','pathSidingToMainRoute','pathMainRouteToSiding','path','departures','trips'):sid.pop(k,None)
  if sid['transportMode']=='TRAIN':sid['maxVehicles']=24;sid['earlyVehicleIncreaseDwellTime']=True;sid['delayedVehicleReduceDwellTimePercentage']=0
 # Expand the existing station bounds to cover longer platforms; never rename a
 # platform using a guessed global station number.
 for st in out['stations']:
  for p in platforms.values():
   original=next((x for x in s['platforms'] if x['id']==p['id']),None)
   if original is None:continue
   centre={k:(original['position1'][k]+original['position2'][k])/2 for k in ('x','y','z')}
   if all(min(st['position1'][k],st['position2'][k])<=centre[k]<=max(st['position1'][k],st['position2'][k]) for k in centre):
    for k in centre:st['position1'][k]=min(st['position1'][k],p['position1'][k]-12,p['position2'][k]-12);st['position2'][k]=max(st['position2'][k],p['position1'][k]+12,p['position2'][k]+12)
 out.update(platform_migrations=migrations,timezone='Asia/Shanghai',train_headway_ms=60000,retired_routes=[routes[x]['id'] for x in ('C1','A1','S2','P1')],alignment_source='Existing native R21 curves, explicitly connected through former terminals')
 assert len({key(r['position1'],r['position2']) for r in out['rails']})==len(out['rails'])
 (OUT/'native_plan.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
 print('R22 plan',len(out['rails']),'rails',len(out['routes']),'services; surface=2')
if __name__=='__main__':main()

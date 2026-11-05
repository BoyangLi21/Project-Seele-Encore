"""Inventory retained native stations and geographic reservations without edits.

Platform associations below are spatial review candidates, not a replacement
for MTR's native loader, passenger traversal or vehicle clearance verification.
"""
import argparse,json,re
from pathlib import Path
from collections import Counter
from audit_hq_mtr_protection_r52 import Reader

def records(root,kind):
    rows=[]
    for path in sorted((root/kind).rglob('*')):
        if path.is_file():
            reader=Reader(path.read_bytes());data=reader.read()
            if not isinstance(data,dict):raise ValueError('Expected native member map')
            rows.append(data)
    return rows

def point(d,key):return [float(d[key][a]) for a in ('x','y','z')]
def identity(d):return str(int(d['id'])&0xffffffffffffffff)
def normalized(name):return re.sub(r'[\s駅站]','',name).casefold()
def bounds(d):
    a,b=point(d,'position1'),point(d,'position2')
    return [min(a[i],b[i]) for i in range(3)]+[max(a[i],b[i]) for i in range(3)]

def plan(a):
    stations=records(a.native,'stations');platforms=records(a.native,'platforms');routes=records(a.native,'routes')
    existing=[];platform_review=[]
    for s in stations:
        box=bounds(s);assigned=[]
        for p in platforms:
            mid=[(u+v)/2 for u,v in zip(point(p,'position1'),point(p,'position2'))]
            if all(box[i]<=mid[i]<=box[i+3] for i in range(3)):assigned.append(identity(p))
        existing.append(dict(native_id=identity(s),name=s['name'],transport_mode=s['transportMode'],bounds=box,
          spatial_platform_candidates=assigned,exit_definition_count=len(s.get('exits',[])),
          actual_passenger_access_verified=False,native_station_assignment_verified=False,vehicle_clearance_verified=False))
    for p in platforms:
        ident=identity(p);parents=[s['name'] for s in existing if ident in s['spatial_platform_candidates']]
        platform_review.append(dict(native_id=ident,name=p['name'],transport_mode=p['transportMode'],bounds=bounds(p),
          spatial_station_candidates=parents,assignment_ambiguous=len(parents)!=1))
    programme=json.loads((a.programme/'district-programme.json').read_text('utf8'));geographic=[]
    for s in programme['stations']:
        matches=[r for r in existing if normalized(r['name'])==normalized(s['name'])]
        geographic.append(dict(name=s['name'],track_centre_xz=s['track_centre_xz'],reference_terrain_y=s['terrain_y'],
          same_name_native_candidates=[dict(native_id=r['native_id'],bounds=r['bounds']) for r in matches],
          reserved_geometry=s['geometry'],station_built_verified=False,platform_layout_verified=False,
          current_track_height_and_grade_verified=False))
    report=dict(status='read-only station scope inventory; no completion claims',native_snapshot=str(a.native),
      native_station_count=len(existing),native_platform_count=len(platform_review),native_route_count=len(routes),
      stations=existing,platforms=platform_review,geographic_stations=geographic,
      geographic_station_count=len(geographic),same_name_geographic_count=sum(bool(r['same_name_native_candidates']) for r in geographic),
      platforms_needing_assignment_review=sum(r['assignment_ambiguous'] for r in platform_review),
      station_names_repeated={n:c for n,c in Counter(r['name'] for r in existing).items() if c>1},
      reserved_un_land_only=True,un_relocation_allowed=False,world_written=False,native_members_written=False)
    a.out.mkdir(parents=True,exist_ok=False)
    (a.out/'station-inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('stations','platforms','geographic_stations')},ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('native','programme','out'):p.add_argument('--'+name,type=Path,required=True)
    plan(p.parse_args())

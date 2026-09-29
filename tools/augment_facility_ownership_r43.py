"""Reproducible building/ship ownership, never inferred quality acceptance."""
from pathlib import Path
import gzip,json,hashlib
from collections import Counter

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43';OUT=ART/'facility_catalogue'

def main():
    sources=[ROOT/'artifacts/world_quality_r02/surface_layout.json',ROOT/'artifacts/world_quality_r02/kirisato_apartments/places.json',ROOT/'artifacts/world_refinement_r08/ships/selected.json',OUT/'physical_components.json.gz']
    data=json.loads(gzip.open(sources[-1],'rt',encoding='utf8').read());catalogue=json.loads((OUT/'catalogue.json').read_text('utf8'))
    physical={c['id']:c for c in data};station_ids={i for s in catalogue['stations'] for i in s['component_candidates']}
    def members(bounds):
        lo,hi=bounds
        return [dict(id=c['id'],dimension=c['dimension'],kind=c['kind'],bounds=c['bounds']) for c in data if c['dimension']=='projectseele:geofront' and all(c['bounds'][1][i]>=lo[i] and c['bounds'][0][i]<=hi[i] for i in range(3)) and any(all(lo[i]<=q[i]<=hi[i] for i in range(3)) for q in c['raw_cells'])]
    plots=json.loads(sources[0].read_text('utf8'))['kept_plots'];estate=json.loads(sources[1].read_text('utf8'))['landmarks'];buildings=[];nonstandard=[]
    for p in plots+estate:
        if 'bounds' not in p:continue
        if 'storeys' not in p:nonstandard.append(p);continue
        x0,x1,z0,z1=p['bounds'];bounds=[[x0,p['floor'],z0],[x1,p['floor']+5*p['storeys']+6,z1]]
        buildings.append(dict(id=p['id'],dimension='projectseele:geofront',planned_bounds=bounds,entry=p.get('entry'),storeys=p['storeys'],style=p.get('style'),
            planned_floor_feet=[p['floor']+1+5*i for i in range(p['storeys'])],physical_components=members(bounds),
            interpretation='Historical authored identity plus exact frozen-world component intersection. Floor elevations, all entrances, flights, ornaments and actual use remain unreviewed.',quality_status='UNREVIEWED'))
    ships=[]
    for p in json.loads(sources[2].read_text('utf8')):
        a,b=p['actual_bounds'];cx,z0=p['destination'];cz=(a[2]+b[2])//2
        bounds=[[cx-(b[2]-cz),a[1]-43,z0],[cx-(a[2]-cz),b[1]-43,z0+b[0]-a[0]]]
        ships.append(dict(id=p['id'],dimension='projectseele:geofront',imported_bounds=bounds,physical_components=members(bounds),
            source_author='Nekoseal',source='https://www.planetminecraft.com/project/ijn-destroyer-division-6-akatsuki-class-destroyer/',
            transform='build_r08_historic_berths.py: (cx-(sourceZ-cz),sourceY-43,z0+sourceX-xmin)',
            public_interfaces=[dict(name='preserved boarding gangway',deck_feet=[cx-7.5,69,420.5]),dict(name='aft deck',feet=[cx-7.5,69,402.5])],
            interpretation='Hull ownership only. Stair blocks can be sculptural hull details; public deck flights and exits must be distinguished before repair.',quality_status='UNREVIEWED'))
    owned=station_ids|{c['id'] for b in buildings+ships for c in b['physical_components']}
    remaining=[dict(id=c['id'],dimension=c['dimension'],kind=c['kind'],bounds=c['bounds']) for c in data if c['id'] not in owned]
    result=dict(buildings=buildings,ships=ships,nonstandard_height_objects=nonstandard,unassigned_components=remaining,
        provenance=[dict(file=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sources],
        scope='Ownership denominator only, zero quality passes. Frozen source IDs remain stable; R43 retirements and moves have separate inverse receipts. Never merge coordinates across dimensions.')
    (OUT/'authored_ownership.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    summary=dict(buildings=len(buildings),ships=len(ships),building_components=len({c['id'] for b in buildings for c in b['physical_components']}),ship_components=len({c['id'] for b in ships for c in b['physical_components']}),remaining=len(remaining),remaining_by_dimension=dict(Counter(c['dimension'] for c in remaining)),quality_passes=0)
    (OUT/'authored_ownership_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf8');print(summary,flush=True)

if __name__=='__main__':main()

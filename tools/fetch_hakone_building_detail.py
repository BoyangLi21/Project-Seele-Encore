"""Cache only missing detailed GSI building tiles around measured station towns."""
import argparse,json,math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from collections import Counter
from hakone_geography import Frame,tile_xy,fetch_tile,vectors


def detail(a):
    config=json.loads((a.gis/'geography.json').read_text('utf8'));frame=Frame(config);tiles=set();zoom=16
    survey=json.loads((a.gis/'tozan-survey.json').read_text('utf8'))
    for station in survey['stations']:
        if not station['passenger']:continue
        x,z=station['point'];radius=260 if station['id']=='yumoto' else 190
        west,north=frame.geographic(x-radius,z-radius);east,south=frame.geographic(x+radius,z+radius)
        x0,y0=map(math.floor,tile_xy(west,north,zoom));x1,y1=map(math.floor,tile_xy(east,south,zoom))
        tiles.update((x,y)for x in range(x0,x1+1)for y in range(y0,y1+1))
    counts=Counter()
    with ThreadPoolExecutor(max_workers=4)as pool:
        futures=[pool.submit(fetch_tile,a.gis,'optimal_bvmap-v1',zoom,x,y,'pbf')for x,y in sorted(tiles)]
        for i,f in enumerate(as_completed(futures),1):
            _,status=f.result();counts[status]+=1
            if i%12==0 or i==len(futures):print('Detailed building tiles',i,'/',len(futures),dict(counts),flush=True)
    config['vector_zoom']=zoom
    _,features=vectors(config,a.gis,frame,{'BldA','SpcfArea'},'valley-buildings-detail.world.geojson.gz')
    (a.gis/'valley-building-detail-sources.json').write_text(json.dumps(dict(zoom=zoom,tiles=sorted(tiles),counts=dict(counts),feature_counts=dict(features),source='https://cyberjapandata.gsi.go.jp/xyz/optimal_bvmap-v1/'),indent=2),'utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--gis',type=Path,required=True);detail(p.parse_args())

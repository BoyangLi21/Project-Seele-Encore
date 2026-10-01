"""Stream large actual mesh JSON, retaining only two decoded foot parts."""
from pathlib import Path
import json,re,numpy as np
ROOT=Path(__file__).resolve().parents[1];ASSETS=ROOT/'artifacts/rebuild_r44/network_runtime/private_resources/assets/projectseele';OUT=ROOT/'artifacts/rebuild_r44/combat/runtime_hands_basis/actual_foot_points';OUT.mkdir(exist_ok=True)
def part(path,name):
    pattern=re.compile(r'"'+re.escape(name)+r'"\s*:\s*(\{)');buffer='';inside=False
    with path.open('r',encoding='utf8')as stream:
        for chunk in iter(lambda:stream.read(65536),''):
            buffer+=chunk
            if not inside:
                match=pattern.search(buffer)
                if match:buffer=buffer[match.start(1):];inside=True
                else:buffer=buffer[-256:];continue
            try:return json.JSONDecoder().raw_decode(buffer)[0]
            except json.JSONDecodeError:pass
    raise ValueError('Actual part not found: '+name)
rows=[]
for variant,asset in enumerate(('eva_unit00','eva_unit01','eva_unit02','eva_prototype','eva_un01')):
    path=ASSETS/'mesh'/(asset+'.mesh.json')
    for side in ('l','r'):
        name='foot_'+side;value=part(path,name)
        if 'vertices'not in value or 'pivot'not in value:raise ValueError('Matched another field instead of an actual mesh part')
        points=(np.asarray(value['vertices'],np.float32).reshape(-1,8)[:,:3]+value['pivot'])*[-1,1,1]/16
        destination=OUT/f'variant_{variant}_{name}.npy';np.save(destination,points.astype(np.float32));rows.append(dict(variant=variant,bone=name,actual_decoded_vertices=len(points),file=destination.name,actual_mesh=str(path)))
(OUT/'actual_points_receipt.json').write_text(json.dumps(dict(parts=rows,scope='Decoded original native resource foot parts, streamed without reading the large full UN JSON into memory. Before late CPU joint/seam skin.'),indent=2),'utf8');print(json.dumps(rows,indent=2))

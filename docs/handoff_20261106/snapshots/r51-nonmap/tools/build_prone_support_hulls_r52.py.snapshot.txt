"""Derive exact minimal directional support vertices from the selected source JAR."""
from pathlib import Path
import argparse, hashlib, json, zipfile
import numpy as np
from scipy.spatial import ConvexHull

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('jar',type=Path)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'src/main/resources/assets/projectseele/eva/prone_leg_support_hulls_r52.json')
    args=parser.parse_args()
    result={'schema':'projectseele.prone-support-hulls.r52.v1','scope':'Exact convex hull vertices of unchanged original rest thigh/shin surfaces; original renderer ankle DQ seam remains active; no replacement rendered geometry','rigs':{}}
    with zipfile.ZipFile(args.jar) as jar:
        for variant in range(3):
            resource=f'mesh/eva_unit0{variant}.mesh.json';raw=jar.read('assets/projectseele/'+resource);mesh=json.loads(raw)
            row={'source_resource':resource,'source_sha256':hashlib.sha256(raw).hexdigest(),'parts':{}}
            for side in 'lr':
                for family in ['leg_','shin_']:
                    name=family+side;part=mesh['parts'][name]
                    if name in mesh.get('jointSkins',{}):raise ValueError('New authored lower-leg palette requires a new support proof')
                    # Match the renderer's original float32 pivot addition and
                    # model-unit conversion, without changing any source mesh.
                    vertices=np.array(part['vertices'],dtype=np.float32).reshape(-1,mesh['stride'])[:,:3]+np.array(part['pivot'],dtype=np.float32)
                    vertices*=np.array([-1,1,1],dtype=np.float32)/np.float32(16);vertices=np.unique(vertices,axis=0)
                    row['parts'][name]=vertices[ConvexHull(vertices).vertices].tolist()
            result['rigs'][str(variant)]=row
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,separators=(',',':')),'utf8')
    print(json.dumps({'support_points':{k:sum(map(len,v['parts'].values())) for k,v in result['rigs'].items()},'bytes':args.output.stat().st_size}))

if __name__=='__main__':main()

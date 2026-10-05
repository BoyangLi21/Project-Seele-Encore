"""Original bevelled SEELE display housing; artwork remains the owner's unchanged file."""
from pathlib import Path
import argparse,itertools,json,shutil
import numpy as np
from scipy.spatial import ConvexHull

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'src/main/resources/assets/projectseele/mesh/seele_monolith_r47.mesh.json'

def bevel_box(half,centre,bevel=.035):
    half=np.asarray(half);points=[]
    for signs in itertools.product((-1,1),repeat=3):
        for axis in range(3):
            point=half-bevel;point[axis]=half[axis];points.append(point*np.array(signs))
    vertices=np.asarray(points);hull=ConvexHull(vertices);faces=[];normals=[]
    for rawface in hull.simplices:
        face=list(rawface);a,b,c=vertices[face];normal=np.cross(b-a,c-a)
        if normal@((a+b+c)/3)<0:face[1],face[2]=face[2],face[1];normal=-normal
        normals.append(normal/np.linalg.norm(normal));faces.append(face)
    vertices+=np.asarray(centre)
    raw=[]
    for face,normal in zip(faces,normals):
        for index in face:
            p=vertices[index];raw.extend([*(-p[0]*16,p[1]*16,p[2]*16),.5,.5,*(-normal[0],normal[1],normal[2])])
    return raw

def save(path,raw,description,height,revision=47):
    doc=dict(format_version=1,stride=8,source=description,model_height=height*16,triangle_count=len(raw)//24,
        parts={'body':dict(pivot=[0,0,0],vertices=raw)})
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(doc,separators=(',',':')),encoding='utf8')
    target=ROOT/f'artifacts/rebuild_r{revision}/assets'/path.relative_to(ROOT/'src/main/resources');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--r48-desk',action='store_true');args=parser.parse_args()
    if args.r48_desk:
        desk=[]
        desk.extend(bevel_box([2.25,.055,.8],[0,.985,0],.035))
        desk.extend(bevel_box([.34,.43,.38],[0,.45,0],.035))
        desk.extend(bevel_box([.92,.035,.64],[0,.035,0],.025))
        save(OUT.with_name('seele_desk_r48.mesh.json'),desk,'Original R48 white enlarged commander conference desk',1.04,48)
        print('R48 desk only: 4.5m wide, 1.6m deep; R47 assets preserved');return
    raw=bevel_box([1.1,2.25,.175],[0,2.43,0]);save(OUT,raw,'Original R47 bevelled SEELE communication housing',4.5)
    desk=[]
    desk.extend(bevel_box([1.65,.055,.65],[0,.985,0],.025))
    desk.extend(bevel_box([.28,.43,.3],[0,.45,0],.025))
    desk.extend(bevel_box([.70,.035,.48],[0,.035,0],.02))
    save(OUT.with_name('seele_desk_r47.mesh.json'),desk,'Original R47 single commander conference desk',1.04)
    print(f'Authored monolith {len(raw)//24} and commander desk {len(desk)//24} triangles')
if __name__=='__main__':main()

"""Build tools-only terrain observation plans from a final immutable candidate jar.

Required sections are explicit actual landmark section coordinates supplied by
Root. This never starts a client, reads Minecraft chunks, or edits a save.
"""
from pathlib import Path
import argparse,hashlib,json,math,zipfile
from build_immutable_r52_candidate import DELIVERY_CLASSES, delivery_class_pins
CANDIDATE=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009/runtime_directory/candidate').resolve()
PINS=['com.projectseele.ProjectSeele','com.projectseele.world.DeadSeaChamberR45','com.projectseele.world.DeadSeaChamberSavedDataR45','com.projectseele.world.NervOriginalCarrierR52','com.projectseele.world.NervLegacyCarrierRideR52','com.projectseele.world.SeeleLightingR48','com.projectseele.client.render.EvaUnit01Renderer','com.projectseele.client.render.LocalTriangleMeshLayer','com.projectseele.client.render.LocalVisualAssetFingerprint','com.projectseele.entity.EvaUnit01Entity']+[n[:-6].replace('/','.') for n in DELIVERY_CLASSES]
OLD_C8='b613ca90f4429347accb193b64eeee8da17ef50325d4933c94ad819e4a6c623e'
def build_plan(jar,name,position,target,required_sections,deadline_seconds=120):
    jar=Path(jar).resolve();digest=hashlib.sha256(jar.read_bytes()).hexdigest()
    if digest==OLD_C8:raise ValueError('Used QA highest-chamber rebind requires C9 or later; C8 refused')
    if not required_sections or len(required_sections)>8192:raise ValueError('Explicit bounded visible landmark section coverage is required')
    cells=[]
    for cell in required_sections:
        if len(cell)!=3 or any(not isinstance(n,int) or isinstance(n,bool) for n in cell):raise ValueError('Exact integer [sectionX,sectionY,sectionZ] required')
        if abs(cell[0])>1875000 or abs(cell[2])>1875000 or abs(cell[1])>4096:raise ValueError('Bounded section coordinates required')
        if cell in cells:raise ValueError('Distinct actual landmark sections required')
        cells.append(cell)
    if len(position)!=3 or len(target)!=3 or not all(math.isfinite(n) for n in position+target):raise ValueError('Finite actual camera and target coordinates required')
    eye=[position[0],position[1]+1.62,position[2]];dx,dy,dz=[target[i]-eye[i] for i in range(3)]
    with zipfile.ZipFile(jar) as archive:delivery_class_pins(archive);pins={name:hashlib.sha256(archive.read(name.replace('.','/')+'.class')).hexdigest() for name in PINS}
    return dict(schema='projectseele.r52.terrain-readiness.v1',camera_name=name,dimension='projectseele:geofront',
                camera_eye=eye,camera_yaw=math.degrees(math.atan2(-dx,dz)),camera_pitch=math.degrees(math.atan2(-dy,math.hypot(dx,dz))),
                camera_tolerance_m=.25,required_sections=cells,deadline_seconds=deadline_seconds,stable_samples=6,minimum_rendered_frames=100,
                candidate_jar=str(jar),candidate_jar_sha256=digest,loaded_class_sha256=pins,world_written=False,
                coverage_scope='Actual declared landmark sections; the observer tests their intersection with the native camera frustum')
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--jar',type=Path,required=True);ap.add_argument('--name',required=True)
    ap.add_argument('--position',type=float,nargs=3,required=True);ap.add_argument('--target',type=float,nargs=3,required=True)
    ap.add_argument('--required-sections',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--deadline-seconds',type=int,default=120)
    a=ap.parse_args();output=a.output.resolve()
    if not output.is_relative_to(CANDIDATE) or output.exists():raise ValueError('Fresh candidate-only plan path required')
    if not 5<=a.deadline_seconds<=300:raise ValueError('Explicit 5..300 second deadline required')
    plan=build_plan(a.jar,a.name,a.position,a.target,json.loads(a.required_sections.read_text('utf8')),a.deadline_seconds)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(plan,indent=2)+'\n','utf8');print(output)
if __name__=='__main__':main()

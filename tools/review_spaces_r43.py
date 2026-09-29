"""One construction world, native photos with camera/compiled-section proof."""
from pathlib import Path
import argparse,hashlib,json,math,shutil,subprocess,sys,time
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43';WORLD=ROOT/'run/saves/SEELE_FIELD_R43_REVIEW'

def main():
    p=argparse.ArgumentParser();p.add_argument('--group',default='before_interfaces');p.add_argument('--shaders',action='store_true');p.add_argument('--no-occlusion',action='store_true');p.add_argument('--rebuild-terrain',action='store_true');p.add_argument('--itinerary',type=Path);args=p.parse_args();guard()
    # Java's world-directory validation rejects a junction here. The private
    # save is small enough for a normal directory; do not weaken that check.
    if not WORLD.exists():
        shutil.copytree(ART/'source_world_backup',WORLD)
        (WORLD/'session.lock').write_bytes(bytes([0xe2,0x98,0x83]))
    assert WORLD.resolve()==WORLD.absolute(),'Unexpected construction world link'
    out=ART/'space_photos'/args.group/time.strftime('%Y%m%d_%H%M%S');out.mkdir(parents=True)
    views=[]
    def add(name,at,target,required):
        d=[target[i]-at[i] for i in range(3)];d[1]-=1.62
        views.append(dict(file='r43_'+args.group+'_'+name+'.png',position=at,
            yaw=math.degrees(math.atan2(-d[0],d[2])),pitch=-math.degrees(math.atan2(d[1],math.hypot(d[0],d[2]))),
            warmupTicks=180,requiredSections=required))
    add('dogma_west_boundary',[-31.1,-566,303.5],[-27.5,-566,317],[[-30,-567,310],[-29,-566,310],[-28,-568,310]])
    add('dogma_east_boundary',[91.1,-566,376.5],[88,-566,357],[[89,-567,370],[89,-566,360],[88,-568,360]])
    add('hangar_station_foyer',[94.5,-442,-46.5],[90.5,-441.3,-43],[[90,-443,-43],[90,-442,-43],[91,-442,-42]])
    add('hangar_station_threshold',[101.5,-442,-39.5],[91,-440.7,-41],[[97,-443,-41],[90,-443,-43],[96,-442,-43]])
    add('pyramid_walk_cap',[54.5,-442,271.5],[59,-441,271.8],[[57,-443,271],[58,-442,271],[62,-443,272]])
    add('hakone_transfer_cap',[-1484.5,131,649.5],[-1481.5,131.5,654],[[-1483,131,650],[-1480,131,654],[-1480,130,648]])
    add('bay_transfer_cap',[336.5,107,301.3],[332,107.5,302.5],[[335,107,302],[332,106,302],[336,106,303]])
    if args.itinerary:views=json.loads(args.itinerary.read_text('utf8'))
    (WORLD/'r30_photo_views.json').write_text(json.dumps(views,ensure_ascii=False,indent=2),'utf8');(out/'itinerary.json').write_text(json.dumps(views,ensure_ascii=False,indent=2),'utf8')
    spec=json.loads((ROOT/'.Codex/client-r42-interiors-photos.json').read_text('utf8'))
    spec['command']=['-Dprojectseele.regionalBuild=r43-facility-photos' if s.startswith('-Dprojectseele.regionalBuild=') else s for s in spec['command']]
    if args.no_occlusion:spec['command'][1:1]=['-Dprojectseele.reviewNoOcclusion=true']
    if args.rebuild_terrain:spec['command'][1:1]=['-Dprojectseele.reviewRebuildTerrain=true']
    keys=[s.split('=',1)[0] for s in spec['command'] if s.startswith('-Dprojectseele.')]
    assert len(keys)==len(set(keys)),'Duplicate photo review JVM properties'
    spec['command'][spec['command'].index('--quickPlaySingleplayer')+1]=WORLD.name
    launch=out/'launch.json';launch.write_text(json.dumps(spec),'utf8')
    cfg=ROOT/'run/config/oculus.properties';previous=cfg.read_bytes();began=time.time();text=previous.decode('utf8')
    witnesses=[ROOT/'build/classes/java/main/com/projectseele'/p for p in ('client/visual/RegionalStationPhoto.class','client/render/StationDepartureBoardRenderer.class','mixin/client/LargeStructureRenderMixin.class')]
    fingerprints=[dict(file=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in witnesses]
    (out/'code_witness.json').write_text(json.dumps(fingerprints,indent=2),'utf8')
    (out/'original_oculus.properties').write_bytes(previous)
    cfg.write_text(text.replace('enableShaders=false','enableShaders=true') if args.shaders else text.replace('enableShaders=true','enableShaders=false'),'utf8')
    try:
        with (out/'native.log').open('w',encoding='utf8') as stream:
            subprocess.run([sys.executable,'tools/launch_rendered_client_r17.py','--prepared-file',str(launch)],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=True)
        proof=json.loads((WORLD/'verified_photo_positions_r42.json').read_text('utf8'))
        assert all(hashlib.sha256(Path(r['file']).read_bytes()).hexdigest()==r['sha256'] for r in fingerprints),'Review code changed while client was running'
        assert {r['file'] for r in proof}=={r['file'] for r in views}
        for row in proof:
            assert row['position_error_metres']<.1 and row['dimension']=='projectseele:geofront'
            if args.no_occlusion:assert row.get('smart_cull') is False,('Visibility treatment did not remain applied',row)
            image=ROOT/'run/screenshots'/row['file'];assert image.stat().st_mtime>=began;shutil.copy2(image,out/image.name)
            row['sha256']=hashlib.sha256(image.read_bytes()).hexdigest()
        (out/'positions.json').write_text(json.dumps(proof,indent=2),'utf8')
        (ART/'space_photos'/('latest_'+args.group+'.json')).write_text(json.dumps(dict(folder=str(out),photos=len(proof),shaders=args.shaders,quality='UNREVIEWED until actual pictures inspected'),indent=2),'utf8')
        print('Fresh native photos with actual camera and compiled sections:',len(proof),out,flush=True)
    finally:cfg.write_bytes(previous)

if __name__=='__main__':main()

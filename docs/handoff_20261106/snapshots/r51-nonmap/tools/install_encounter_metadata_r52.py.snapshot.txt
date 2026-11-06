"""Root's measured encounter locations; no actors, mission progress or terrain copied."""
import argparse,copy,hashlib,json,math,msvcrt
from pathlib import Path
import numpy as np
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from extend_world_depth_r52 import acquire_world_lock
from apply_s20_approved_semantic_repairs import atomic_replace


def digest(raw):return hashlib.sha256(raw).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    root=Path(__file__).resolve().parents[1];world=BASE/'WORLD_R52';out=BASE/'encounter_installation';out.mkdir(exist_ok=True)
    assert not(out/'APPLIED.json').exists(),'Never replay an applied metadata migration'
    paths=json.loads((BASE/'surface_angel_routes/READ_ONLY_ROUTES.json').read_text('utf8'))
    armor=json.loads((world/'nerv_armor_column_r50.json').read_text('utf8'));assert armor['installed']and armor['surface']==[30.5,80,355.5]
    attack=json.loads((root/'.Codex/r52_surface_armor_attack/results/ATTACK_REPORT.json').read_text('utf8'))
    assert attack['checks']==28 and all(r['plate_hits']>0 and r['underground_vertices_outside_plate']==0 for r in attack['results'])
    # Fresh original raised-city readback, not a cached plan promoted to pass.
    lo=(-230,80,-460);hi=(230,145,440);actual,palette=measure(lo,hi)
    frozen=np.load(BASE/'surface_angel_routes/ACTUAL_RAISED_CITY.npz');names=list(map(str,frozen['palette']));lookup={s:i for i,s in enumerate(names)}
    assert np.array_equal(np.asarray([lookup.get(s,-1) for s in palette])[actual],frozen['states']), 'Street geometry changed since the full-width survey'
    surface=dict(schema=52,id='r52/original_city_surface_approaches',dimension='projectseele:geofront',installed=True,geometry_validated=True,
                 armor_column=armor['id'],sites={},native_verified=False)
    for row in paths:
        chapter=row['chapter'];route=row['route'];assert route[0]==row['spawn'] and route[-1]==[10.5,81,355.5]
        assert all(math.dist(a,b)<=8.001 for a,b in zip(route,route[1:]))
        d=np.asarray(route[1])-np.asarray(route[0]);yaw=math.degrees(math.atan2(-d[0],d[2]))
        surface['sites'][chapter]=dict(spawn=route[0],route=route,intercept=route[-1],yaw=yaw,speed=.34 if chapter=='sachiel'else .42,
            arrival_radius=.7,engagement_range=160,attack_period_ticks=160,armor_damage=120)
    old=(world/'tv_encounter_sites_r45.json').read_bytes();sites=json.loads(old)
    site=json.loads((BASE/'far_yashima_access/ROOT_SITE_CANDIDATE.json').read_text('utf8'))
    site['angel']=[30.5,114,355.5];site['geometry_validated']=True;site['native_verified']=False
    # Verify every independently installed route's actual standing support.
    a,p=measure((-1348,174,-1496),(-1148,177,-1350));base=(-1348,174,-1496)
    check_points=site['eva_access_routes']['0']+site['eva_access_routes']['1']+site['cover_after_supply_route']+[site['support_port']]
    ground={'minecraft:grass_block[snowy=false]','projectseele:nerv_floor_panel','projectseele:nerv_structural_panel'}
    for point in check_points:
        x,z=math.floor(point[0]),math.floor(point[2]);assert p[int(a[0,z-base[2],x-base[0]])]in ground,point
        assert p[int(a[1,z-base[2],x-base[0]])]=='minecraft:air',point
    sites['sites']['ramiel']=site
    assert sites['sites']['gaghiel']==json.loads(old)['sites']['gaghiel']
    station=json.loads((root/'.Codex/r52_operations/calibration_powered/STATION_CANDIDATE.json').read_text('utf8'))
    station.update(json.loads((root/'.Codex/r52_operations/cradle_candidate/STATION_INSTALL_PATCH.json').read_text('utf8')))
    station['eva_access_route']=site['eva_access_routes']['1'];station.update(installed=False,geometry_validated=True,native_verified=False)
    station['installation_pending']='Only physical controller creation and native commissioning remain; no mission or gun inventory is copied.'
    assert station['prone_position']==site['hero'] and math.dist(station['raised_position'],site['angel'])+64<station['attack_range']
    production=json.loads((root/'.Codex/r52_operations/cradle_candidate/PRODUCTION_GEOMETRY_AUDIT.json').read_text('utf8'))
    assert all(not production[k] for k in ('raised_body_intersections','raised_hatch_intersections','whole_lift_body_intersections','whole_lift_hatch_intersections'))
    (out/'STATION_DESIGN.json').write_text(json.dumps(station,ensure_ascii=False,indent=2),'utf8')
    documents={'surface_angel_assault_r52.json':surface,'tv_encounter_sites_r45.json':sites}
    encoded={n:(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf8')for n,d in documents.items()}
    report=dict(world_written=False,files={n:digest(v)for n,v in encoded.items()},surface_geometry_fresh_readback=True,
        source_attack_checks=28,yashima_walk_points=len(check_points),original_marine_metadata_unchanged=True,actor_or_progress_writes=False,
        native_verified=False,station_controller_installed=False,balance=dict(new_surface_only=dict(sachiel_speed=.34,shamshel_speed=.42,
        attack_period_ticks=160,top_plate_damage=120,unchanged_plate_health=1200)))
    if args.apply:
        lock=acquire_world_lock();written=[];before={}
        try:
            for name in encoded:
                target=world/name;before[name]=target.read_bytes()if target.exists()else None
            assert before['tv_encounter_sites_r45.json']==old and before['surface_angel_assault_r52.json']is None
            for name,raw in before.items():
                if raw is not None:(out/('before_'+name)).write_bytes(raw)
            for name,raw in encoded.items():atomic_replace(world/name,raw);written.append(name);assert(world/name).read_bytes()==raw
        except BaseException:
            for name in reversed(written):
                if before[name]is None:(world/name).unlink()
                else:atomic_replace(world/name,before[name])
            raise
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
        report['world_written']=True;(out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8')
    else:(out/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()

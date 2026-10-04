"""Actual 17-owner/37-input/full-aperture source data; no world/runtime writes."""
from pathlib import Path
import csv,gzip,hashlib,json,math,sys
sys.dont_write_bytecode=True
from measure_world_r40 import MeasuredWorld,properties
from query_blocks import iter_block_entities,AIR
from prepare_school_hakone_native_r45 import ActualGeometry

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r45'
WORLD=ART/'composition_candidates/R45_source_candidate_20261004_v7_01/world'
OUT=ART/'lifts_doors_lifecycle_sol_v2/command17_current_source_v7_v1'
NORMAL={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p))
def write(p,v):Path(p).write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def main():
    assert not OUT.exists();OUT.mkdir()
    marker_path=WORLD/'.projectseele_command_sliding_doors_r01.json';marker=read(marker_path)
    assert len(marker['doors'])==17 and len({r['id']for r in marker['doors']})==17
    m=MeasuredWorld(WORLD)
    for d in marker['doors']:m.around(d['lower'],8)
    m.load();assert all(s=='full'for s in m.status.values())
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(-20,-445,225),(80,-400,380),selected_chunks=set(m.selected)))
    paths={WORLD/'dimensions/projectseele/geofront/region'/f'r.{x//32}.{z//32}.mca'for x,z in m.selected};before={str(p):sha(p)for p in paths}
    apertures={tuple(p)for d in marker['doors']for p in d['aperture']}
    assert len(apertures)==102 and all(m.block(p)in AIR|{'minecraft:barrier'}and p not in tags for p in apertures)
    class OpenImage:
        world=WORLD
        def block(self,p):return 'minecraft:air'if tuple(p)in apertures else m.block(p)
        def get(self,x,y,z):return self.block((math.floor(x),math.floor(y),math.floor(z)))
    g=ActualGeometry(OpenImage());traits=read(WORLD/'native_state_traits_r44.json')
    def full(p):
        p=tuple(p);t=tags.get(p);return dict(pos=list(p),state=m.block(p),full_nbt=None if t is None else t.snbt())
    inputs=[];owners=[]
    for d in marker['doors']:
        assert len(d['aperture'])==6 and len(d['fixedInputContractsR45'])==len(d['buttons'])
        for c in d['fixedInputContractsR45']:
            p=tuple(c['pos']);support=c['fixed_support'];state=m.block(p);sp=tuple(support['pos'])
            assert state==c['state_after']and m.block(sp)==support['state']and p not in tags and sp not in tags
            assert 'ButtonBlock'in traits[state]['runtime_class']and properties(state)['face']=='wall'
            dx,dz=NORMAL[properties(state)['facing']];assert sp==(p[0]-dx,p[1],p[2]-dz)
            assert g.standing(c['operator'])=='STATIC_STANDING'
            inputs.append(dict(id=f"command/{d['id']}/input/{p[0]}_{p[1]}_{p[2]}",door_id=d['id'],side=c['side'],block=full(p),fixed_support=full(sp),actual_operator=c['operator'],actual_operator_body_and_nine_bearing='STATIC_STANDING',preserved_original_alias=c.get('preserved_original_alias',False),native_required=['actual loaded-state canSurvive','actual native OUTLINE reachable client raycast','actual ServerPlayer use event before target retirement','full6 owned aperture open','owned no-save entity leaves complete progress','real keys crossing actual authored approach','occupied expiry remains safe','clear threshold and full6 close'],native_pass=False))
        x,y,z=d['lower'];dx,dz=NORMAL[d['facing']];ax,az=(1,0)if d['axis']=='x'else(0,1)
        lanes=[]
        for lane in (-1,0,1):
            points=[]
            for dist in (-1.5,-1,-.5,0,.5,1,1.5):
                p=[x+.5+ax*lane+dx*dist,y,z+.5+az*lane+dz*dist]
                points.append(dict(point=p,body=g.clear(p),nine_bearing=g.standing(p)))
            centre=[x+.5+ax*lane,y,z+.5+az*lane]
            assert g.clear(centre)=='CLEAR'and g.standing(centre)=='STATIC_STANDING'
            lanes.append(dict(lane=lane,actual_aperture_point=centre,aperture_body_and_bearing='STATIC_STANDING',direct_approach_probes=points,direct_approach_static_pass=all(p['nine_bearing']=='STATIC_STANDING'for p in points)))
        owners.append(dict(id=d['id'],lower=d['lower'],axis=d['axis'],facing=d['facing'],complete6_aperture_current=[full(p)for p in d['aperture']],lanes=lanes,actual_command_marker=d,scope='Door aperture and fixed controls; approach narrowing is separately classified, not auto-filled.',native_pass=False))
    assert len(inputs)==37 and len({tuple(r['block']['pos'])for r in inputs})==37
    write(OUT/'all37_current_fixed_input_requests.UNBOUND.json',dict(schema='projectseele.command17-current-input-requests.v1',world=str(WORLD),source_marker=ref(marker_path),bound=False,inputs=inputs))
    write(OUT/'all17_actual_full_apertures_and_approaches.json',owners)
    # Preserve the authored ID15 stair/columns and the source installer evidence.
    d=next(d for d in marker['doors']if d['id']==15)
    cells=[full((x,y,z))for x in range(26,31)for y in range(-415,-410)for z in range(280,287)]
    with(ROOT/'artifacts/s41_command_sliding_doors_20260821_211108/block_diff.csv').open('r',encoding='utf-8-sig',newline='')as f:
        historical=[r for r in csv.DictReader(f)if 26<=int(r['x'])<=30 and 282<=int(r['z'])<=285 and -415<=int(r['y'])<=-410]
    write(OUT/'ID15_complete_authored_stair_throat_and_first_installer.json',dict(cells=cells,current_owner=d,historical_actual_applied_deltas=historical,first_installer=ref(ROOT/'tools/s41_install_command_sliding_doors.py'),actual_installer_receipt=ref(ROOT/'artifacts/s41_command_sliding_doors_20260821_211108/receipt.json'),disposition='Original 1-wide centre stair approaches a 3-wide enlarged door plane; side pillars and support are authored components, not air gaps. No widening/retirement is authorized merely by aperture width. Native centre-stair use and occupied closure still unverified.',geometry_changed=False))
    assert all(sha(Path(p))==h for p,h in before.items())and not g.unknown
    report=dict(world=str(WORLD),door_owners17=True,complete_aperture_cells102=True,static_inputs37_state_support_NBT_and_standing_equal=True,all51_aperture_lane_body_and_bearing_clear_in_owned_open_RAM_image=True,direct_approach_static_pass_lanes=sum(l['direct_approach_static_pass']for r in owners for l in r['lanes']),direct_approach_nonflat_or_obstructed_lanes=[dict(door=r['id'],lane=l['lane'],probes=l['direct_approach_probes'])for r in owners for l in r['lanes']if not l['direct_approach_static_pass']],scope='Measured source/open RAM geometry, not actual runtime door collision/activation or production delivery acceptance.',native_pass=False,world_written=False,Java_MC_started=False,models_changed=False,aperture_image_only_cells102=True,original_stairs_columns_ladders_kept=True)
    write(OUT/'report.json',report);print(json.dumps({k:v for k,v in report.items()if k!='direct_approach_nonflat_or_obstructed_lanes'},ensure_ascii=True,indent=2))
if __name__=='__main__':main()

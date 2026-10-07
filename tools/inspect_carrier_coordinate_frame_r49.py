"""Read actual encoded parts and source frame rules; no models/world/game changes."""
from pathlib import Path
import json,math
import numpy as np
ROOT=Path(__file__).resolve().parents[1]

def main():
    folder=ROOT/'artifacts/rebuild_r49/carrier_surface'
    resource=ROOT/'artifacts/rebuild_r49/assets/assets/projectseele/mesh/tripo_carrier_r48.json'
    mesh=json.loads(resource.read_text('utf8'));hinge=np.asarray(mesh['anchors']['service_platform']);anchor=np.asarray(mesh['anchors']['power_reel'])
    part_info={};folded=[];nearest=None
    for name,encoded in mesh['parts'].items():
        points=np.asarray(encoded).reshape(-1,8)[:,:3]
        part_info[name]=dict(min=points.min(0).tolist(),max=points.max(0).tolist(),vertices=len(points))
        if name=='body':nearest=float(np.linalg.norm(points-anchor,axis=1).min())
        transformed=points.copy()
        if name=='service_platform':
            d=transformed-hinge;transformed=np.column_stack((d[:,1],-d[:,0],d[:,2]))+hinge
        folded.append(transformed)
    points=np.concatenate(folded);lo=points.min(0);hi=points.max(0)
    actual_bounds=[lo.tolist(),hi.tolist()];actual_width=float(hi[0]-lo[0]);actual_depth=float(hi[2]-lo[2])
    old_report=json.loads((folder/'REPORT.json').read_text('utf8'))
    phase_coordinates=[]
    world=ROOT/'artifacts/rebuild_r49/construction/SEELE_R49_WORLD'
    beds=json.loads((world/'eva_facility_r20.json').read_text('utf8'))
    for slot,bed in enumerate(beds['cages']):
        root=np.asarray(bed,float)+np.array([.5,1,.5])
        phase_coordinates.append(dict(slot=slot,bed=bed,root=root.tolist(),reel_at_rise={str(r):(root+anchor-np.array([0,64*(1-r),0])).tolist() for r in(0,.5,1)}))
    render=(ROOT/'src/main/java/com/projectseele/client/render/EvaUnit01Renderer.java').read_text('utf8')
    cable=(ROOT/'src/main/java/com/projectseele/client/render/EvaUmbilicalCableRenderer.java').read_text('utf8')
    source=(ROOT/'src/main/java/com/projectseele/client/render/TripoMachineryR48.java').read_text('utf8')
    kinematics=(ROOT/'src/main/java/com/projectseele/entity/EvaRifleKinematics.java').read_text('utf8')
    origin_line=next(l.strip() for l in render.splitlines() if 'Vec3 origin=' in l and 'animatable' in l)
    # Reproduce the actual three-line transfer clock from world metadata and
    # the source HORIZONTAL_BLOCKS_PER_TICK=.35. Compare one analytic sample
    # to linear interpolation of the adjacent integer samples, not gameplay.
    def ease(t):return t*t*t*(t*(t*6-15)+10)
    def height(fr,to,t):
        dy=to[1]-fr[1];dz=to[2]-fr[2]
        if abs(dy)<4 or abs(dz)<64:return fr[1]+dy*t
        low,high=(fr,to) if dy>0 else(to,fr);sign=np.sign(high[2]-low[2]);start=low[2]+sign*28;end=high[2]-sign*16
        length=(end-start)*sign;z=fr[2]+dz*t;d=np.clip((z-start)*sign,0,length);blend=min(6,length*.15);effective=length-blend
        def rounded(x):return x*.5-blend/(2*math.pi)*math.sin(math.pi*x/blend)
        rise=rounded(d) if d<blend else effective-rounded(length-d) if d>length-blend else d-blend*.5
        return low[1]+(high[1]-low[1])*rise/effective
    fr=np.asarray(beds['cages'][0],float)+np.array([.5,1,.5]);to=np.asarray(beds['launches'][0],float)+np.array([.5,1,.5])
    duration=max(80,math.ceil(float(np.linalg.norm(to-fr))/.35))
    def sample(t):
        e=ease(np.clip(t/duration,0,1));p=fr+(to-fr)*e;p[1]=height(fr,to,e);return p
    errors=[]
    for tick in range(1,duration+1):
        analytic=sample(tick-.5);linear=(sample(tick-1)+sample(tick))*.5
        errors.append((float(np.linalg.norm(linear-analytic)),tick,analytic.tolist(),linear.tolist()))
    largest=max(errors)
    report=dict(schema=49,resource=str(resource),units=mesh['units'],uniform_scale_baked_once=mesh['r49_uniform_structure']['scale'],part_bounds=part_info,
        encoded_parts_folded_bounds=actual_bounds,encoded_parts_folded_width=actual_width,encoded_parts_folded_depth=actual_depth,
        published_report_width=old_report['folded_width'],published_report_matches_encoded_parts=abs(old_report['folded_width']-actual_width)<1e-5,
        published_report_issue='Global platform_ids folding rotates shared body/deck seam vertices in the report; renderer rotates only the independent service_platform triangles',
        power_anchor=anchor.tolist(),anchor_nearest_actual_body_vertex=nearest,slot_rise_coordinates=phase_coordinates,
        carrier_parent_chain=['EntityRenderDispatcher translation + EvaUnit01Renderer.getRenderOffset','NervMovingCarrierRenderer before Gecko super.render/applyRotations','TvFacilityMeshes.carrier, no scale or yaw','TripoMachineryR48 body translateY=-64*(1-rise)'],
        fixed_silo_yaw=180,model_rotation_at_silo=0,basis_right=[1,0,0],basis_rear=[0,0,1],double_sink_in_body_reel_formula=False,
        carrier_source_formula='carrierRenderPosition(partial) + bakedBlockAnchor + [0,-64*(1-rise),0]',
        pose_capture_origin_source=origin_line,pose_capture_ordinary_carrier_still_uses_packet_position=':animatable.getPosition(partialTick)' in origin_line,
        analytic_vs_linear_transfer_example=dict(from_=fr.tolist(),to=to.tolist(),duration=duration,partial=.5,max_coordinate_difference=largest[0],tick=largest[1],analytic=largest[2],linear=largest[3]),
        clear_endpoint_uses_unattached_lerp='.lerp(pylon,handoff)' in cable,
        phases=dict(DRAINING='Body and anchor use the same single -64*(1-rise); rise smooth(ticks/100) is concurrent with drain',TO_SILO='Both use analytic carrierRenderPosition; captured body connector origin must match that same rendered origin',LOCKED='rise=1, fixed mechanical yaw, same body/reel coordinate',CLEAR='rack=false at surface; endpoint must stay on real rack reel or real block pylon, not their midpoint',DEPLOYED='rise=0 hides body except clear-phase handoff; normal ground pylon owns the endpoint'),
        fitted_connector_fallback_uses_shared_carrier_root='if(!posed&&entity.hasActiveCarrierMotion())position=entity.carrierRenderPosition(partial);' in kinematics,
        previously_reported_faults=['CLEAR midpoint was unattached; removed in current source','Folded report rotated shared global seam vertices; current report matches independent rendered part triangles','PoseGraph capture origin used packet interpolation; current source uses renderedOrigin; fitted fallback also selects carrier root'],
        world_written=False,model_written=False,game_controlled=False,native_verified=False,visual_verified=False)
    folder.mkdir(parents=True,exist_ok=True);(folder/'COORDINATE_SOURCE_REVIEW.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:report[k] for k in ['encoded_parts_folded_width','encoded_parts_folded_depth','published_report_matches_encoded_parts','anchor_nearest_actual_body_vertex','pose_capture_ordinary_carrier_still_uses_packet_position','clear_endpoint_uses_unattached_lerp','native_verified']},ensure_ascii=False))
if __name__=='__main__':main()

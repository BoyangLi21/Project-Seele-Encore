package com.projectseele.entity;

import com.projectseele.world.*;
import com.projectseele.world.NervRouteReservationsR52.Original;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.*;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Landed occupied release. Every accepted source/hands/socket pose has
 * finite actual sole bearing and a conservative selected-palette sweep.
 * Failure retains the current source; the clock never advances privately. */
public final class EvaMechanicalReleaseR52 {
    private static final int TICKS=20;
    private static boolean actualShutterSurfaceR52(ServerLevel l,Vec3 at)
    {
        for(var hatch:l.getEntitiesOfClass(NervSiloDoorEntity.class,new AABB(at,at).inflate(36),x->x.declaredSpecR52()!=null)){
            var frame=hatch.actualFrameR52();var local=frame.inverse().transformPoint(at);var spec=hatch.declaredSpecR52();if(Math.abs(local.x)>spec.openingX()/2||Math.abs(local.z)>spec.openingZ()/2||Math.abs(local.y-1)>.08)continue;if(hatch.actualOpenProgressR52()!=0)return false;double top=Double.NEGATIVE_INFINITY;for(var piece:hatch.declaredGeometryR52().pieces(0)){var xyz=piece.part().xyz();for(int n=0;n<xyz.length;n+=3){var p=piece.local().transformPoint(new Vec3(xyz[n],xyz[n+1],xyz[n+2]));xyz[n]=p.x;xyz[n+1]=p.y;xyz[n+2]=p.z;}top=Math.max(top,NervMappedPlugMechanicsR52.surfaceHeight(xyz,local.x,local.z));}return Double.isFinite(top)&&Math.abs(top-local.y)<.0021;
        }return true;
    }
    private static double crossR53(Vec3 a,Vec3 b,Vec3 c)
    { return (b.x-a.x)*(c.z-a.z)-(b.z-a.z)*(c.x-a.x); }
    private static double areaR53(List<Vec3> polygon)
    {
        double area=0;for(int i=0;i<polygon.size();i++){var a=polygon.get(i);var b=polygon.get((i+1)%polygon.size());area+=a.x*b.z-a.z*b.x;}return Math.abs(area)*.5;
    }
    private static List<Vec3> overlapR53(List<Vec3> sole,List<Vec3> steel)
    {
        double orientation=Math.signum(crossR53(steel.get(0),steel.get(1),steel.get(2)));
        if(orientation==0)return List.of();var polygon=new ArrayList<>(sole);
        for(int edge=0;edge<3&&!polygon.isEmpty();edge++)
        {
            var a=steel.get(edge);var b=steel.get((edge+1)%3);var next=new ArrayList<Vec3>();
            Vec3 previous=polygon.get(polygon.size()-1);double last=orientation*crossR53(a,b,previous);
            for(var current:polygon)
            {
                double distance=orientation*crossR53(a,b,current);
                if((distance>=0)!=(last>=0)){double fraction=last/(last-distance);next.add(previous.add(current.subtract(previous).scale(fraction)));}
                if(distance>=0)next.add(current);previous=current;last=distance;
            }
            polygon=next;
        }
        return polygon;
    }
    private static List<Vec3> hullR53(List<Vec3> points)
    {
        var sorted=new ArrayList<>(points);sorted.sort(Comparator.comparingDouble((Vec3 p)->p.x).thenComparingDouble(p->p.z));
        var unique=new ArrayList<Vec3>();for(var p:sorted)if(unique.isEmpty()||p.x!=unique.get(unique.size()-1).x||p.z!=unique.get(unique.size()-1).z)unique.add(p);
        if(unique.size()<3)return List.of();var hull=new ArrayList<Vec3>();
        for(var p:unique){while(hull.size()>=2&&crossR53(hull.get(hull.size()-2),hull.get(hull.size()-1),p)<=0)hull.remove(hull.size()-1);hull.add(p);}
        int lower=hull.size();for(int i=unique.size()-2;i>=0;i--){var p=unique.get(i);while(hull.size()>lower&&crossR53(hull.get(hull.size()-2),hull.get(hull.size()-1),p)<=0)hull.remove(hull.size()-1);hull.add(p);}hull.remove(hull.size()-1);return hull;
    }
    /** A ribbed closed leaf supports a sole across grooves. Use intersections
     * of actual lowest sole triangles and actual coplanar top-steel triangles;
     * their support polygon must surround the finite sole area's centroid. */
    private static boolean actualShutterBearingR53(ServerLevel level,List<double[]> source,RigidTransform root,List<Vec3> contacts)
    {
        if(contacts.isEmpty())return false;var first=contacts.get(0);
        for(var hatch:level.getEntitiesOfClass(NervSiloDoorEntity.class,new AABB(first,first).inflate(36),h->h.declaredSpecR52()!=null))
        {
            var frame=hatch.actualFrameR52();var inverse=frame.inverse();var spec=hatch.declaredSpecR52();
            boolean inside=true;for(var point:contacts){var p=inverse.transformPoint(point);if(Math.abs(p.x)>spec.openingX()/2||Math.abs(p.z)>spec.openingZ()/2||Math.abs(p.y-SiloHatchMechanism.PANEL_TOP)>.08){inside=false;break;}}
            if(!inside)continue;if(hatch.actualOpenProgressR52()!=0)return false;
            double plane=frame.transformPoint(new Vec3(0,SiloHatchMechanism.PANEL_TOP,0)).y;
            var soles=new ArrayList<List<Vec3>>();Vec3 centre=Vec3.ZERO;double soleArea=0;
            for(var xyz:source)for(int i=0;i<xyz.length;i+=9)
            {
                var triangle=new ArrayList<Vec3>();boolean lowest=true;
                for(int v=0;v<3;v++){var p=root.transformPoint(new Vec3(xyz[i+v*3],xyz[i+v*3+1],xyz[i+v*3+2]));triangle.add(p);if(Math.abs(p.y-plane)>.0021)lowest=false;}
                if(!lowest)continue;double area=areaR53(triangle);if(area<=1e-9)continue;
                soles.add(triangle);centre=centre.add(triangle.get(0).add(triangle.get(1)).add(triangle.get(2)).scale(area/3));soleArea+=area;
            }
            if(soleArea<=.0025)return false;centre=centre.scale(1/soleArea);
            var support=new ArrayList<Vec3>();double contactArea=0;
            for(var piece:hatch.declaredGeometryR52().pieces(0))
            {
                var transform=frame.compose(piece.local());var xyz=piece.part().xyz();
                for(int i=0;i<xyz.length;i+=9)
                {
                    var triangle=new ArrayList<Vec3>();double low=Double.POSITIVE_INFINITY,high=Double.NEGATIVE_INFINITY;
                    for(int v=0;v<3;v++){var p=transform.transformPoint(new Vec3(xyz[i+v*3],xyz[i+v*3+1],xyz[i+v*3+2]));triangle.add(p);low=Math.min(low,p.y);high=Math.max(high,p.y);}
                    if(high<plane-.0021||areaR53(triangle)<=1e-9)continue;
                    for(var sole:soles)
                    {
                        var intersection=overlapR53(sole,triangle);double area=areaR53(intersection);if(area<=1e-9)continue;
                        if(high>plane+.0021)return false;
                        if(low>=plane-.0021){contactArea+=area;support.addAll(intersection);}
                    }
                }
            }
            var hull=hullR53(support);if(contactArea<=.0025||hull.size()<3||areaR53(hull)<=.0025)return false;
            for(int i=0;i<hull.size();i++)if(crossR53(hull.get(i),hull.get((i+1)%hull.size()),centre)<-1e-7)return false;
            return true;
        }
        for(var point:contacts)if(!actualShutterSurfaceR52(level,point))return false;
        return true;
    }
    public static boolean actualGroundBearingR52(ServerLevel l,EvaUnit01Entity e,EvaOriginalMeshGeometryR52.Geometry geometry,RigidTransform root) {
        if(!NervTraversalPolicyR53.strict(l))return EntryPlugEjectionR48.loaded(l,e.getBoundingBox().move(root.translation().subtract(e.position())));
        for(String name:List.of("foot_l","foot_r")){var contacts=new ArrayList<Vec3>();var soleSource=new ArrayList<double[]>();for(var part:geometry.parts())if(part.bone().equals(name)){soleSource.add(part.triangles());double low=part.bounds().minY;for(var p:part.vertices())if(p.y<=low+.002){var at=root.transformPoint(p);var block=BlockPos.containing(at.add(0,-.003,0));if(!l.hasChunkAt(block))return false;double top=Double.NEGATIVE_INFINITY;for(var b:l.getBlockState(block).getCollisionShape(l,block).toAabbs()){var world=b.move(block);if(at.x>=world.minX-1e-6&&at.x<=world.maxX+1e-6&&at.z>=world.minZ-1e-6&&at.z<=world.maxZ+1e-6)top=Math.max(top,world.maxY);}if(!Double.isFinite(top)||Math.abs(top-at.y)>.0021)return false;contacts.add(at);}}
            boolean finite=false;for(int a=0;a<contacts.size()&&!finite;a++)for(int b=a+1;b<contacts.size()&&!finite;b++)for(int c=b+1;c<contacts.size();c++){var x=contacts.get(a);var y=contacts.get(b);var z=contacts.get(c);if(Math.abs((y.x-x.x)*(z.z-x.z)-(z.x-x.x)*(y.z-x.z))>.0025){finite=true;break;}}if(!finite||!actualShutterBearingR53(l,soleSource,root,contacts))return false;
        }return true;
    }
    public static boolean beginGroundedR52(ServerLevel l,EvaUnit01Entity e,Original o) {
        if(e.level()!=l||!e.onGround()||!EvaMechanicalFrameR52.ballisticCustodyR52(e)||EvaMechanicalFrameR52.epoch(e)!=o.epoch()||EvaShutdownR30.disabled(e)||!actualGroundBearingR52(l,e,EvaMechanicalFrameR52.capturedGeometry(e),EvaMechanicalFrameR52.frame(e,1)))return false;
        if(!EvaMechanicalFrameR52.groundReleaseStateR52(e).isEmpty())return true;var input=EvaBodyPose.ordinaryReleaseInputsR52(e,1);var target=EvaBodyPose.ordinaryReleaseTargetR52(e,input,l.getGameTime()+TICKS);var hands=EvaAnatomicalHandsR45.ordinaryReleaseTargetR52(e.getUnitVariant(),input.prone(),input.guard());var state=new CompoundTag();state.putLong("Epoch",o.epoch());state.putString("Source",EvaMechanicalFrameR52.capturedGeometry(e).sourceFingerprint());state.put("Body",EvaShutdownR30.encode(EvaMechanicalFrameR52.frozenLocalPose(e)));state.put("Hands",EvaFrozenHandsR52.capture(e,1));state.put("Target",EvaShutdownR30.encode(target));state.put("TargetHands",EvaFrozenHandsR52.encode(e.getUnitVariant(),EvaAnatomicalHandsR45.contractFingerprintR45(e.getUnitVariant()),hands));state.putInt("Step",0);state.putLong("Since",l.getGameTime());EvaMechanicalFrameR52.groundReleaseStateR52(e,state);return true;
    }
    private static EvaBodyPose.Sample body(EvaUnit01Entity e,CompoundTag state,double progress) {var a=EvaBodyPose.neutralForTransportR32(e);var b=EvaBodyPose.neutralForTransportR32(e);EvaShutdownR30.decode(state.getCompound("Body"),a);EvaShutdownR30.decode(state.getCompound("Target"),b);return EvaBodyPose.blend(a,b,(float)progress);}
    private static EvaAnatomicalHandsR45.Pose hands(EvaUnit01Entity e,CompoundTag state,double progress) {var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();var a=EvaFrozenHandsR52.decode(e.getUnitVariant(),provider.handContractFingerprint(e.getUnitVariant()),provider.handJoints(e.getUnitVariant()),state.getCompound("Hands"));var b=EvaFrozenHandsR52.decode(e.getUnitVariant(),provider.handContractFingerprint(e.getUnitVariant()),provider.handJoints(e.getUnitVariant()),state.getCompound("TargetHands"));var out=new LinkedHashMap<String,Quaternionf>();for(String n:a.rotations().keySet())out.put(n,new Quaternionf(a.rotations().get(n)).slerp(b.rotations().get(n),(float)progress).normalize());return new EvaAnatomicalHandsR45.Pose(b.left(),b.right(),Map.copyOf(out));}
    private static double weight(double step) {double t=step/TICKS;return t*t*t*(10+t*(-15+6*t));}
    private static boolean clear(ServerLevel l,EvaUnit01Entity e,Original o,CompoundTag state,double a,double b,int depth) {
        if(!NervTraversalPolicyR53.strict(l))
            return EntryPlugEjectionR48.loaded(l,e.getBoundingBox())
                    &&l.getEntity(o.plug()) instanceof EntryPlugCarrierEntity capsule&&capsule.getVehicle()==e
                    &&capsule.isHatchFullySealed()&&capsule.getFirstPassenger()!=null
                    &&capsule.getFirstPassenger().getUUID().equals(o.pilot());
        var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();var from=body(e,state,weight(a));var fromHands=hands(e,state,weight(a));var to=body(e,state,weight(b));var toHands=hands(e,state,weight(b));var first=provider.evaluate(e.getUnitVariant(),from,fromHands);var last=provider.evaluate(e.getUnitVariant(),to,toHands);var root=EvaMechanicalFrameR52.frame(e,1);if(!actualGroundBearingR52(l,e,first,root)||!actualGroundBearingR52(l,e,last,root))return false;var bounds=provider.releaseMotionBoundsR52(e.getUnitVariant(),from,fromHands,to,toHands,first);var own=TransportMembershipR52.members(o,TransportMembershipR52.Kind.OCCUPIED);boolean clear=true;
        for(var part:first.parts()){double motion=bounds.get(part.bone());if(!Double.isFinite(motion)){clear=false;break;}if(part.bone().startsWith("foot_")&&motion!=0){state.putString("Hold","actual_sole_motion_requires_ground_contact_solver");return false;}var mesh=new NervRigidMeshSweepR52(part.triangles());var envelope=mesh.envelope(root,root).inflate(motion);if(!EntryPlugEjectionR48.loaded(l,envelope))return false;for(var shape:l.getBlockCollisions(e,envelope))for(var obstacle:shape.toAabbs()){boolean bearing=motion==0&&(part.bone().startsWith("foot_")||part.bone().startsWith("toe_"))&&Math.abs(obstacle.maxY-envelope.minY)<.0021;if(!bearing&&mesh.intersects(root,root,obstacle.inflate(motion),.003))clear=false;}for(var actor:l.getEntities((Entity)null,envelope,x->!own.contains(x.getUUID())&&x.isAlive()&&(x instanceof LivingEntity||x.canBeCollidedWith()))){var actual=NervFlightProofR52.actualObstacleMeshes(actor);if(actual==null||actual.isEmpty()){if(mesh.intersects(root,root,actor.getBoundingBox().inflate(motion),.003))clear=false;}else for(var m:actual)if(mesh.intersects(root,root,m.mesh(),m.frame(),m.endFrame(),.003,new Vec3(motion,motion,motion)))clear=false;}if(!clear)break;}
        if(clear)clear=clearCapsule(l,e,o,from,to,root,own);if(clear)return true;if(depth>=6){state.putString("Hold","selected_palette_continuous_release_sweep_blocked");return false;}double mid=(a+b)/2;return clear(l,e,o,state,a,mid,depth+1)&&clear(l,e,o,state,mid,b,depth+1);
    }
    private static boolean clearCapsule(ServerLevel l,EvaUnit01Entity e,Original o,EvaBodyPose.Sample from,EvaBodyPose.Sample to,RigidTransform root,Set<UUID> own) {
        if(!(l.getEntity(o.plug()) instanceof EntryPlugCarrierEntity capsule)||capsule.getVehicle()!=e||!capsule.isHatchFullySealed()||capsule.getFirstPassenger()==null)return false;var a=EvaMechanicalFrameR52.emptySocketReferenceR52(from,EvaRifleKinematics.frameWorldR52(e.position(),EvaMechanicalFrameR52.baseYaw(e)),EvaDorsalProfile.of(e));var b=EvaMechanicalFrameR52.emptySocketReferenceR52(to,EvaRifleKinematics.frameWorldR52(e.position(),EvaMechanicalFrameR52.baseYaw(e)),EvaDorsalProfile.of(e));double angle=0,displacement=0,radius=0;var primitives=new ArrayList<AABB>();for(var source:NervMappedPlugMechanicsR52.selectedMachinery().closedPlugParts(o.variant()).values()){var mesh=new NervRigidMeshSweepR52(source);primitives.add(mesh.envelope(a,a));}var seat=a.transformPoint(EntryPlugKinematics.PILOT_SEAT_P);primitives.add(capsule.getFirstPassenger().getBoundingBox().move(seat.subtract(capsule.getFirstPassenger().getBoundingBox().getCenter())));
        for(String n="torso_upper";n!=null;n=from.rig.get(n).parent()){var q=from.rotations.get(n);var r=to.rotations.get(n);angle+=q.equals(r,1e-7F)?0:2*Math.acos(Math.min(1,Math.abs(q.dot(r))));displacement+=from.positions.get(n).distance(to.positions.get(n))*EvaScale.RENDER_SCALE;var p=from.matrix(n).transformPosition(new Vector3f(from.rig.get(n).pivot())).mul(EvaScale.RENDER_SCALE);var pivot=root.transformPoint(new Vec3(p.x,p.y,p.z));for(var box:primitives)for(double x:new double[]{box.minX,box.maxX})for(double y:new double[]{box.minY,box.maxY})for(double z:new double[]{box.minZ,box.maxZ})radius=Math.max(radius,pivot.distanceTo(new Vec3(x,y,z)));}
        double motion=(radius+displacement)*Math.expm1(angle)+displacement+.00005;for(var source:NervMappedPlugMechanicsR52.selectedMachinery().closedPlugParts(o.variant()).values()){var mesh=new NervRigidMeshSweepR52(source);var box=mesh.envelope(a,b).inflate(motion);if(!EntryPlugEjectionR48.loaded(l,box))return false;for(var shape:l.getBlockCollisions(capsule,box))for(var obstacle:shape.toAabbs())if(mesh.intersects(a,a,obstacle.inflate(motion),.003))return false;for(var actor:l.getEntities((Entity)null,box,x->!own.contains(x.getUUID())&&x.isAlive()&&(x instanceof LivingEntity||x.canBeCollidedWith())))if(mesh.intersects(a,a,actor.getBoundingBox().inflate(motion),.003))return false;}
        var rider=primitives.get(primitives.size()-1).inflate(motion);return EntryPlugEjectionR48.loaded(l,rider)&&!l.getBlockCollisions(capsule.getFirstPassenger(),rider).iterator().hasNext()&&l.getEntities((Entity)null,rider,x->!own.contains(x.getUUID())&&x.isAlive()&&(x instanceof LivingEntity||x.canBeCollidedWith())).isEmpty();
    }
    public static boolean advanceGroundedR52(ServerLevel l,EvaUnit01Entity e,Original o) {
        var state=EvaMechanicalFrameR52.groundReleaseStateR52(e);if(state.isEmpty()||state.getLong("Epoch")!=o.epoch()||!state.getString("Source").equals(EvaMechanicalFrameR52.capturedGeometry(e).sourceFingerprint())||!e.onGround())return false;int step=state.getInt("Step");if(step<0||step>=TICKS)return false;if(!clear(l,e,o,state,step,step+1,0)){EvaMechanicalFrameR52.groundReleaseStateR52(e,state);return false;}var body=body(e,state,weight(step+1));var hands=hands(e,state,weight(step+1));var geometry=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52().evaluate(e.getUnitVariant(),body,hands);if(!EvaMechanicalFrameR52.applyGroundedPoseR52(e,o,body,hands,geometry))return false;state.putInt("Step",step+1);state.remove("Hold");EvaMechanicalFrameR52.groundReleaseStateR52(e,state);if(step+1<TICKS)return false;e.restoreMechanicalStanceR52(EvaMechanicalFrameR52.originalStanceR52(e));if(!EvaMechanicalFrameR52.releaseUpright(e,o))return false;e.setNervLogisticsLocked(false);e.setNoGravity(false);e.clearSortieDestination();return true;
    }
    private EvaMechanicalReleaseR52(){}
}

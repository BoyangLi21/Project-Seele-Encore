package com.projectseele.world;

import com.projectseele.entity.*;
import com.projectseele.world.NervRouteReservationsR52.Original;
import com.projectseele.world.NervAirTransportManifestR52.*;
import com.projectseele.world.NervFlightProofR52.ObstacleMesh;
import com.projectseele.world.TransportMembershipR52.Kind;
import java.util.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.*;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** An original fallen hull stays on its actual aircraft jaws while it is slowly
 * brought upright above the declared receiving shoes. The separated V capsule
 * and pilot are provenance only, never motion members. */
public final class NervHullGroundRecoveryR52
{
    public static final int POSE_TICKS=120,LOWER_TICKS=80,TICKS=POSE_TICKS+LOWER_TICKS;
    private static final String KEY="HullGroundRecoveryR52";
    private static EvaBodyPose.Sample decode(EvaUnit01Entity e,CompoundTag tag)
    {var body=EvaBodyPose.neutralForTransportR32(e);EvaShutdownR30.decode(tag,body);return body;}
    public static EvaBodyPose.Sample mix(EvaBodyPose.Sample from,EvaBodyPose.Sample to,float fraction)
    {var body=new EvaBodyPose.Sample(from.rig);for(String name:from.rig.keySet()){var a=from.rotations.get(name);var b=to.rotations.get(name);body.rotations.put(name,fraction<=0||a.equals(b)?new Quaternionf(a):fraction>=1?new Quaternionf(b):new Quaternionf(a).slerp(b,fraction).normalize());var x=from.positions.get(name);var y=to.positions.get(name);body.positions.put(name,fraction<=0||x.equals(y)?new Vector3f(x):fraction>=1?new Vector3f(y):new Vector3f(x).lerp(y,fraction));}body.dirty();return body;}
    private static float ease(double value){return EvaDorsalMechanism.smooth((float)Math.max(0,Math.min(1,value)));}
    private static EvaOriginalMeshGeometryR52.Geometry evaluate(EvaUnit01Entity e,EvaBodyPose.Sample body,CompoundTag hands)
    {var p=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();return p.evaluate(e.getUnitVariant(),body,EvaFrozenHandsR52.decode(e.getUnitVariant(),p.handContractFingerprint(e.getUnitVariant()),p.handJoints(e.getUnitVariant()),hands));}
    private static FootSupportFrameR52.Binding binding(EvaUnit01Entity e,EvaBodyPose.Sample body,EvaOriginalMeshGeometryR52.Geometry geometry)
    {var socket=EvaMechanicalFrameR52.emptySocketReferenceR52(body,EvaRifleKinematics.frameWorldR52(Vec3.ZERO,180),EvaDorsalProfile.of(e));return EvaMechanicalFrameR52.sourceSoleBindingR52(geometry,socket);}
    private static List<Vec3> desiredAnchors(EvaBodyPose.Sample body)
    {var out=new ArrayList<Vec3>();for(String bone:List.of("arm_l","arm_r","leg_l","leg_r","shin_l","shin_r")){var p=body.matrix(bone).transformPosition(new Vector3f(body.rig.get(bone).pivot()).add(0,0,2.5F/EvaScale.RENDER_SCALE)).mul(EvaScale.RENDER_SCALE);out.add(new Vec3(p));}return List.copyOf(out);}
    private static boolean originalHull(EvaUnit01Entity e,Original o)
    {return e.isAlive()&&e.getUUID().equals(o.eva())&&e.getUnitVariant()==o.variant()&&e.getPassengers().isEmpty()&&TransportMembershipR52.originalEjectionReceipts(o,e.getPersistentData())&&EvaMechanicalFrameR52.active(e)&&EvaMechanicalFrameR52.kind(e)==Kind.HULL_ONLY_RECOVERY&&EvaMechanicalFrameR52.flightCustody(e)&&EvaMechanicalFrameR52.epoch(e)==o.epoch();}
    private static boolean sameBody(EvaBodyPose.Sample a,EvaBodyPose.Sample b)
    {if(!a.rig.keySet().equals(b.rig.keySet()))return false;for(String n:a.rig.keySet()){if(a.positions.get(n).distanceSquared(b.positions.get(n))>4e-12)return false;var x=new Quaternionf(a.rotations.get(n)).normalize();var y=new Quaternionf(b.rotations.get(n)).normalize();if(x.dot(y)<0)y.mul(-1);double dx=x.x-y.x,dy=x.y-y.y,dz=x.z-y.z,dw=x.w-y.w;if(dx*dx+dy*dy+dz*dz+dw*dw>4e-12)return false;}return true;}
    public static EvaBodyPose.Sample destinationPose(EvaUnit01Entity e,EvaBodyPose.Sample initial)
    {
        var target=EvaBodyPose.neutralForTransportR32(e);
        if(!target.rig.keySet().equals(initial.rig.keySet()))throw new IllegalStateException("Original captured skeleton cannot be substituted");
        // The original clamp/shoe source was engineered for these original
        // standing joint goals. They are reached through checked physical
        // samples; no caller can apply this target as a capture or snap.
        return target;
    }
    public static final class Plan
    {
        private final Original original;private final CompoundTag start,goal,hands;private final RigidTransform wait,stopped;private final String source,port;
        private Plan(Original o,CompoundTag start,CompoundTag goal,CompoundTag hands,RigidTransform wait,RigidTransform stopped,String source,String port)
        {original=o;this.start=start.copy();this.goal=goal.copy();this.hands=hands.copy();this.wait=wait;this.stopped=stopped;this.source=source;this.port=port;}
        public Original original(){return original;}public RigidTransform waitingRoot(){return wait;}public RigidTransform stoppedRoot(){return stopped;}public String port(){return port;}
        public EvaBodyPose.Sample body(EvaUnit01Entity e,double age){return mix(decode(e,start),decode(e,goal),ease(age/POSE_TICKS));}
        public RigidTransform root(double age){return wait.interpolate(stopped,ease((age-POSE_TICKS)/LOWER_TICKS));}
        public boolean done(int age){return age>=TICKS;}
        public CompoundTag hands(){return hands.copy();}
        private CompoundTag encode()
        {var tag=new CompoundTag();tag.put("Start",start.copy());tag.put("Goal",goal.copy());tag.put("Hands",hands.copy());tag.put("Waiting",NervAircraftFrameR52.encodeRigid(wait));tag.put("Stopped",NervAircraftFrameR52.encodeRigid(stopped));tag.putString("Source",source);tag.putString("Port",port);return tag;}
    }
    /** Planned source geometry may be inspected before flight custody. No actor is written or captured here. */
    public static Plan plan(ServerLevel level,NervFlightProofR52.FlightPickupPreview preview,Receiver receiver,CompoundTag data)throws java.io.IOException
    {
        if(preview==null||preview.kind()!=Kind.HULL_ONLY_RECOVERY||receiver.delivery()||!(level.getEntity(preview.original().eva()) instanceof EvaUnit01Entity e))return null;
        var saved=data.getCompound(KEY);if(!saved.isEmpty())
        {
            if(!saved.getString("Source").equals(preview.sourceFingerprint())||!saved.getString("Port").equals(receiver.port()))return null;
            return new Plan(preview.original(),saved.getCompound("Start"),saved.getCompound("Goal"),saved.getCompound("Hands"),NervAircraftFrameR52.decodeRigid(saved.getCompound("Waiting")),NervAircraftFrameR52.decodeRigid(saved.getCompound("Stopped")),saved.getString("Source"),receiver.port());
        }
        var initial=decode(e,preview.bodySnapshotR52());var target=decode(e,EvaShutdownR30.encode(destinationPose(e,initial)));var hands=preview.handSnapshotR52();
        // These are destination joint goals only. Every accepted sample remains
        // an independently swept, gradual change from the original captured pose.
        var geometry=evaluate(e,target,hands);var feet=binding(e,target,geometry);var context=NervRouteRuntimeR52.flightContext(level);if(context==null)return null;var directory=context.directory();var route=directory.route(receiver.reverseRoutes().get(e.getUnitVariant()));if(route==null||route.legs().isEmpty())return null;
        RigidTransform stopped;try{stopped=directory.sample(directory.leg(route.legs().get(0)),0,feet).evaRoot();}catch(IllegalArgumentException invalid){return null;}
        double minimum=Double.POSITIVE_INFINITY;
        if(sameBody(initial,target))minimum=NervRigidMeshSweepR52.transformed(geometry.bounds(),RigidTransform.of(Vec3.ZERO,stopped.rotation())).minY;
        else for(int i=0;i<=32;i++){var body=mix(initial,target,ease(i/32D));var g=evaluate(e,body,hands);minimum=Math.min(minimum,NervRigidMeshSweepR52.transformed(g.bounds(),RigidTransform.of(Vec3.ZERO,stopped.rotation())).minY);}
        // The complete original Tripo frame is taller than its shoe plane.
        // Keep the lowest source hull surface above that real upper frame.
        double top=NervOriginalCarrierR52.raisedBoundsAtR52(e.getUnitVariant(),stopped).maxY;var wait=RigidTransform.of(new Vec3(stopped.translation().x,Math.max(stopped.translation().y,top+2-minimum),stopped.translation().z),stopped.rotation());
        var plan=new Plan(preview.original(),EvaShutdownR30.encode(initial),EvaShutdownR30.encode(target),hands,wait,stopped,preview.sourceFingerprint(),receiver.port());data.put(KEY,plan.encode());data.putInt("HullRecoveryAgeR52",0);return plan;
    }
    public static final class AcceptedRecoveryStep
    {
        private final Original original;private final UUID aircraft;private final long at;private final CompoundTag before,after,hands;private final Frame from,to;private final EvaOriginalMeshGeometryR52.Geometry geometry;private final FootSupportFrameR52.Binding binding;private final List<NervAirCradleContactsR52.Contact> contacts;private final double rotorFrom,rotorTo;
        private AcceptedRecoveryStep(ServerLevel level,Original o,UUID plane,CompoundTag before,CompoundTag after,CompoundTag hands,Frame from,Frame to,EvaOriginalMeshGeometryR52.Geometry geometry,FootSupportFrameR52.Binding binding,List<NervAirCradleContactsR52.Contact> contacts,double rotor)
        {original=o;aircraft=plane;at=level.getGameTime();this.before=before.copy();this.after=after.copy();this.hands=hands.copy();this.from=from;this.to=to;this.geometry=geometry;this.binding=binding;this.contacts=List.copyOf(contacts);rotorFrom=rotor;rotorTo=rotor+1;}
        public Original original(){return original;}public UUID aircraft(){return aircraft;}public long checkedAt(){return at;}public CompoundTag fromBody(){return before.copy();}public CompoundTag toBody(){return after.copy();}public CompoundTag hands(){return hands.copy();}public Frame from(){return from;}public Frame to(){return to;}public RigidTransform fromRoot(){return from.cargo();}public RigidTransform toRoot(){return to.cargo();}public EvaOriginalMeshGeometryR52.Geometry geometry(){return geometry;}public FootSupportFrameR52.Binding binding(){return binding;}public String sourceFingerprint(){return geometry.sourceFingerprint();}public List<Vec3> anchors(){return contacts.stream().map(NervAirCradleContactsR52.Contact::centre).toList();}public List<Vec3> jawAxes(){return contacts.stream().map(NervAirCradleContactsR52.Contact::axis).toList();}public double rotorFrom(){return rotorFrom;}public double rotorTo(){return rotorTo;}
        public boolean aircraftCurrent(ServerLevel level)
        {return level.getGameTime()==at&&level.getEntity(aircraft) instanceof UNTransportEntity p&&NervAircraftFrameR52.active(p)&&NervAirTransportManifestR52.same(NervAircraftFrameR52.actual(p),from.plane())&&NervAircraftFrameR52.frame(p,1).rig().equals(from.rig())&&NervAirTransportManifestR52.same(NervAircraftFrameR52.frame(p,1).cargo(),from.cargo())&&NervAircraftFrameR52.rotorClock(p)==rotorFrom;}
        public boolean current(ServerLevel level)
        {return aircraftCurrent(level)&&level.getEntity(original.eva()) instanceof EvaUnit01Entity e&&originalHull(e,original)&&NervAirTransportManifestR52.same(EvaMechanicalFrameR52.frame(e,1),fromRoot())&&EvaAirTransportR31.cradleStateR50(e).getCompound("Origin").equals(before)&&EvaFrozenHandsR52.capture(e,1).equals(hands)&&EvaMechanicalFrameR52.capturedGeometry(e).sourceFingerprint().equals(sourceFingerprint());}
        public boolean cargoCommitted(ServerLevel level)
        {return aircraftCurrent(level)&&level.getEntity(original.eva()) instanceof EvaUnit01Entity e&&originalHull(e,original)&&NervAirTransportManifestR52.same(EvaMechanicalFrameR52.frame(e,1),toRoot())&&EvaAirTransportR31.cradleStateR50(e).getCompound("Origin").equals(after)&&EvaFrozenHandsR52.capture(e,1).equals(hands);}
    }
    record Chord(String bone,Vec3[] vertices,double error,AABB box){}
    static List<Chord> chords(EvaOriginalMeshGeometryR52.Geometry from,EvaOriginalMeshGeometryR52.Geometry to,RigidTransform a,RigidTransform b,double error)
    {
        if(from.parts().size()!=to.parts().size())throw new IllegalStateException("Original topology changed during recovery");var out=new ArrayList<Chord>();
        for(int part=0;part<from.parts().size();part++){var x=from.parts().get(part);var y=to.parts().get(part);if(!x.bone().equals(y.bone())||!x.sourceSHA256().equals(y.sourceSHA256()))throw new IllegalStateException("Original source part changed");double[] first=x.triangles(),last=y.triangles();if(first.length!=last.length)throw new IllegalStateException("Original triangle topology changed");for(int i=0;i<first.length;i+=9){var corners=new Vec3[6];AABB box=null;for(int k=0;k<3;k++){int n=i+k*3;corners[k]=a.transformPoint(new Vec3(first[n],first[n+1],first[n+2]));corners[k+3]=b.transformPoint(new Vec3(last[n],last[n+1],last[n+2]));for(int j:new int[]{k,k+3})box=box==null?new AABB(corners[j],corners[j]):box.minmax(new AABB(corners[j],corners[j]));}out.add(new Chord(x.bone(),corners,error,box.inflate(error)));}}return out;
    }
    static double curveError(EvaBodyPose.Sample a,EvaBodyPose.Sample b,EvaOriginalMeshGeometryR52.Geometry g,RigidTransform from,RigidTransform to)
    {double angle=NervRigidMeshSweepR52.angular(from,to);for(String n:a.rig.keySet()){var x=a.rotations.get(n);var y=b.rotations.get(n);if(x.equals(y))continue;double dot=Math.abs((double)x.x*y.x+(double)x.y*y.y+(double)x.z*y.z+(double)x.w*y.w),xx=(double)x.x*x.x+(double)x.y*x.y+(double)x.z*x.z+(double)x.w*x.w,yy=(double)y.x*y.x+(double)y.y*y.y+(double)y.z*y.z+(double)y.w*y.w;angle+=2*Math.acos(Math.min(1,dot/Math.sqrt(xx*yy)));}double error=.004+NervRigidMeshSweepR52.radius(g.bounds())*angle*angle/8;
        if(g.parts().size()==1&&NervRigidMeshSweepR52.angular(from,to)==0)
        {
            var fixedHands=new EvaAnatomicalHandsR45.Pose("fixed","fixed",Map.of());
            var bounds=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52().releaseMotionBoundsR52(g.variant(),a,fixedHands,b,fixedHands,g);
            var rigid=bounds.get("RigidCurveR53/"+g.parts().get(0).bone());if(rigid!=null)error=.004+rigid;
        }
        return error;}
    private static boolean intersects(Chord chord,SourceObstacle source)
    {var mesh=source.mesh();return chord.box().intersects(source.envelope())&&mesh.mesh().intersectsChord(chord.vertices(),new Vec3(chord.error(),chord.error(),chord.error()),mesh.frame(),mesh.endFrame());}
    private record SourceObstacle(ObstacleMesh mesh,boolean solePlane,AABB envelope)
    {SourceObstacle(ObstacleMesh mesh,boolean solePlane){this(mesh,solePlane,mesh.mesh().envelope(mesh.frame(),mesh.endFrame()));}}
    private static boolean bearingTangent(Chord chord,SourceObstacle obstacle)
    {
        if(!obstacle.solePlane()||!Set.of("foot_l","foot_r").contains(chord.bone())||!NervAirTransportManifestR52.same(obstacle.mesh().frame(),obstacle.mesh().endFrame()))return false;
        var up=obstacle.mesh().frame().transformVector(new Vec3(0,1,0));if(up.distanceToSqr(new Vec3(0,1,0))>1e-10)return false;
        double top=NervRigidMeshSweepR52.transformed(obstacle.mesh().mesh().bounds(),obstacle.mesh().frame()).maxY;
        for(Vec3 point:chord.vertices())if(point.y<top-2e-6)return false;return true;
    }
    static boolean clearWorld(ServerLevel level,Entity hull,List<Chord> chords,List<AABB> declared,Set<UUID> own)
    {
        var byPart=new LinkedHashMap<String,AABB>();AABB whole=null;
        for(var c:chords){byPart.merge(c.bone(),c.box(),AABB::minmax);whole=whole==null?c.box():whole.minmax(c.box());}
        if(whole==null)return false;
        // Match the pose caller's per-part SPACE request. Empty gaps between
        // separate source parts are only broad-phase query space, not cargo.
        for(var box:byPart.values())if(!NervAirspaceCoverageR52.covered(box,declared)||!EntryPlugEjectionR48.loaded(level,box))return false;
        var fixed=NervFlightProofR52.detachedCarrierObstacles(level);if(fixed==null)return false;
        var fixedNearby=new ArrayList<SourceObstacle>();for(var mesh:fixed){var source=new SourceObstacle(mesh,false);if(whole.intersects(source.envelope()))fixedNearby.add(source);}
        for(var chord:chords)for(var source:fixedNearby)if(intersects(chord,source))return false;
        var obstacles=new ArrayList<SourceObstacle>();var boxes=new ArrayList<AABB>();
        for(var shape:level.getBlockCollisions(hull,whole))boxes.addAll(shape.toAabbs());
        for(var e:level.getEntities((Entity)null,whole.inflate(200),e->!own.contains(e.getUUID())&&e.isAlive()&&!e.isSpectator()&&(e instanceof LivingEntity||e.canBeCollidedWith()||e instanceof UNTransportEntity||e instanceof NervSiloDoorEntity||e instanceof NervHangarDoorEntity||e instanceof NervCarrierPlatformEntity)))
        {
            if(e instanceof NervCarrierPlatformEntity carrier&&NervOriginalCarrierR52.declared(carrier))
            {try{for(var part:NervOriginalCarrierR52.actualPartsR52(carrier))obstacles.add(new SourceObstacle(new ObstacleMesh(part.mesh(),part.frame()),part.role()==NervOriginalCarrierR52.Role.SOLE_BEARING||part.name().equals("deck")));}catch(java.io.IOException absent){return false;}continue;}
            var meshes=NervFlightProofR52.actualObstacleMeshes(e);if(meshes==null){if(whole.intersects(e.getBoundingBox()))return false;}else if(meshes.isEmpty())boxes.add(e.getBoundingBox());else for(var mesh:meshes)obstacles.add(new SourceObstacle(mesh,false));
        }
        var nearby=new ArrayList<SourceObstacle>();for(var source:obstacles)if(whole.intersects(source.envelope()))nearby.add(source);
        for(var chord:chords){for(var box:boxes)if(chord.box().intersects(box)&&TriangleSweepMeshR52.convexSweepBox(chord.vertices(),chord.error(),box))return false;for(var source:nearby)if(!bearingTangent(chord,source)&&intersects(chord,source))return false;}return true;
    }
    /** Only this full source/world check can create a committable small pose step. */
    public static AcceptedRecoveryStep check(ServerLevel level,UUID task,UUID aircraft,NervAirframeGeometryR52 source,Plan plan,int age,Frame current,Set<String> spaces,Map<String,NervRouteNativeR52.Binding> bindings)
    {
        if(plan==null||age<0||age>=TICKS||!(level.getEntity(plan.original.eva()) instanceof EvaUnit01Entity e)||!originalHull(e,plan.original)||!(level.getEntity(aircraft) instanceof UNTransportEntity p)||!p.carrying()||current.cargo()==null||current.rig().deployment()!=1||current.rig().jaws()!=0)return null;
        var context=NervRouteRuntimeR52.flightContext(level);if(context==null)return null;var lease=context.pool().queryFlight(task);if(lease==null||!lease.original().equals(plan.original)||!lease.aircraft().equals(aircraft)||lease.kind()!=Kind.HULL_ONLY_RECOVERY||!lease.spaces().containsAll(spaces))return null;
        if(!NervAirTransportManifestR52.same(EvaMechanicalFrameR52.frame(e,1),plan.root(age))||!NervAirTransportManifestR52.same(current.cargo(),plan.root(age))||!sameBody(EvaMechanicalFrameR52.frozenLocalPose(e),plan.body(e,age))||!EvaFrozenHandsR52.capture(e,1).equals(plan.hands))return null;
        var declared=new ArrayList<AABB>();for(String id:spaces){var b=bindings.get(id);if(b==null)return null;declared.addAll(b.spaces());}
        var own=new HashSet<>(TransportMembershipR52.members(plan.original,Kind.HULL_ONLY_RECOVERY));own.add(aircraft);double rotor=NervAircraftFrameR52.rotorClock(p);
        var bodyFrom=EvaMechanicalFrameR52.frozenLocalPose(e);var geometryFrom=EvaMechanicalFrameR52.capturedGeometry(e);var contactsFrom=NervAirCradleContactsR52.evaluate(geometryFrom,desiredAnchors(bodyFrom));var after=EvaShutdownR30.encode(plan.body(e,age+1));
        var next=new Frame(current.plane(),plan.root(age+1),current.rig());var bodyTo=decode(e,after);boolean unchanged=sameBody(bodyFrom,bodyTo);var geometryTo=unchanged?geometryFrom:evaluate(e,bodyTo,plan.hands);var contactsTo=unchanged?contactsFrom:NervAirCradleContactsR52.evaluate(geometryTo,desiredAnchors(bodyTo));
        if(!NervAircraftFrameR52.anchors(p).equals(contactsFrom.stream().map(NervAirCradleContactsR52.Contact::centre).toList())||!NervAircraftFrameR52.jawAxes(p).equals(contactsFrom.stream().map(NervAirCradleContactsR52.Contact::axis).toList()))return null;
        int subdivisions=unchanged?1:4;
        for(int sample=0;sample<subdivisions;sample++)
        {
            float start=(float)sample/subdivisions,end=(float)(sample+1)/subdivisions;
            var pa=unchanged?bodyFrom:mix(bodyFrom,bodyTo,start);var pb=unchanged?bodyTo:mix(bodyFrom,bodyTo,end);var ga=unchanged?geometryFrom:evaluate(e,pa,plan.hands);var gb=unchanged?geometryTo:evaluate(e,pb,plan.hands);var ra=current.cargo().interpolate(next.cargo(),start);var rb=current.cargo().interpolate(next.cargo(),end);double error=curveError(pa,pb,ga,ra,rb);
            var bodyChords=new ArrayList<Chord>();
            for(int part=0;part<ga.parts().size();part++)
            {
                var aPart=new EvaOriginalMeshGeometryR52.Geometry(ga.variant(),ga.sourceFingerprint(),List.of(ga.parts().get(part)));
                var bPart=new EvaOriginalMeshGeometryR52.Geometry(gb.variant(),gb.sourceFingerprint(),List.of(gb.parts().get(part)));
                bodyChords.addAll(chords(aPart,bPart,ra,rb,curveError(pa,pb,aPart,ra,rb)));
            }
            if(!clearWorld(level,e,bodyChords,declared,own))return null;
            for(var chord:bodyChords)
            {
                if(source.bodyMesh().intersectsChord(chord.vertices(),new Vec3(chord.error(),chord.error(),chord.error()),current.plane()))return null;
                for(int r=0;r<4;r++)if(source.rotorMesh(r).intersectsChord(chord.vertices(),new Vec3(chord.error(),chord.error(),chord.error()),current.plane().compose(source.rotorLocalFrame(r,rotor+start)),current.plane().compose(source.rotorLocalFrame(r,rotor+end))))return null;
            }
            var ca=NervAirCradleContactsR52.evaluate(ga,desiredAnchors(pa));var cb=NervAirCradleContactsR52.evaluate(gb,desiredAnchors(pb));
            var fa=new Frame(current.plane(),ra,current.rig());var fb=new Frame(current.plane(),rb,current.rig());
            var partsA=source.parts(fa,ca.stream().map(NervAirCradleContactsR52.Contact::centre).toList(),ca.stream().map(NervAirCradleContactsR52.Contact::axis).toList(),rotor+start);
            var partsB=source.parts(fb,cb.stream().map(NervAirCradleContactsR52.Contact::centre).toList(),cb.stream().map(NervAirCradleContactsR52.Contact::axis).toList(),rotor+end);
            var cradleA=new ArrayList<EvaOriginalMeshGeometryR52.Part>();var cradleB=new ArrayList<EvaOriginalMeshGeometryR52.Part>();
            for(int i=5;i<partsA.size();i++){var x=partsA.get(i);var y=partsB.get(i);var mx=new NervRigidMeshSweepR52(x.xyz());var my=new NervRigidMeshSweepR52(y.xyz());cradleA.add(new EvaOriginalMeshGeometryR52.Part(x.name(),"original-air-cradle",source.fingerprint(),x.xyz(),mx.bounds()));cradleB.add(new EvaOriginalMeshGeometryR52.Part(y.name(),"original-air-cradle",source.fingerprint(),y.xyz(),my.bounds()));}
            if(!clearWorld(level,e,chords(new EvaOriginalMeshGeometryR52.Geometry(e.getUnitVariant(),source.fingerprint(),cradleA),new EvaOriginalMeshGeometryR52.Geometry(e.getUnitVariant(),source.fingerprint(),cradleB),current.plane(),current.plane(),error),declared,own))return null;
            // Jaws are the named actual contacts. Other struts/crossbars may not cut through the original body.
            for(int i=5;i<partsA.size();i++)if(!partsA.get(i).name().startsWith("jaw/")){var rigid=new NervRigidMeshSweepR52(partsA.get(i).xyz());for(var chord:bodyChords)if(rigid.intersectsChord(chord.vertices(),new Vec3(chord.error(),chord.error(),chord.error()),current.plane()))return null;}
        }
        if(age+1==TICKS)
        {var carrier=NervOriginalCarrierR52.controller(level,plan.original);try{if(carrier==null||!NervOriginalCarrierR52.carrierFootBearingR52(level,carrier,e,geometryTo,next.cargo()))return null;}catch(java.io.IOException absent){return null;}}
        return new AcceptedRecoveryStep(level,plan.original,aircraft,EvaAirTransportR31.cradleStateR50(e).getCompound("Origin"),after,plan.hands,current,next,geometryTo,binding(e,bodyTo,geometryTo),contactsTo,rotor);
    }
    private NervHullGroundRecoveryR52(){}
}

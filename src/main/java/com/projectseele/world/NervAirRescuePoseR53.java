package com.projectseele.world;

import com.projectseele.entity.*;
import com.projectseele.world.NervAirTransportManifestR52.*;
import com.projectseele.world.NervRouteReservationsR52.Original;
import java.util.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Same-tick occupied recovery sweep, including the original capsule and pilot. */
final class NervAirRescuePoseR53
{
    private record TargetCache(EvaOriginalMeshGeometryR52.Geometry source,Object provider,net.minecraft.nbt.CompoundTag body,
            Map<String,Quaternionf> hands,EvaOriginalMeshGeometryR52.Geometry target){}
    private static final Map<EvaUnit01Entity,TargetCache> TARGETS=new WeakHashMap<>();
    private static List<NervAirCradleContactsR52.Contact> contacts(EvaBodyPose.Sample body,EvaOriginalMeshGeometryR52.Geometry geometry)
    {
        var anchors=new ArrayList<Vec3>();
        for(String bone:List.of("arm_l","arm_r","leg_l","leg_r","shin_l","shin_r"))
        {
            var point=body.matrix(bone).transformPosition(new Vector3f(body.rig.get(bone).pivot()).add(0,0,2.5F/EvaScale.RENDER_SCALE)).mul(EvaScale.RENDER_SCALE);
            anchors.add(new Vec3(point));
        }
        return NervAirCradleContactsR52.evaluate(geometry,anchors);
    }
    private static EvaOriginalMeshGeometryR52.Geometry cradle(NervAirframeGeometryR52 source,Frame frame,
            List<Vec3> anchors,List<Vec3> axes,int variant)
    {
        var parts=new ArrayList<EvaOriginalMeshGeometryR52.Part>();
        for(var part:source.cradleParts(frame,anchors,axes,false))
        {
            var xyz=part.xyz();parts.add(new EvaOriginalMeshGeometryR52.Part(part.name(),"original-cradle",source.fingerprint(),xyz,new NervRigidMeshSweepR52(xyz).bounds()));
        }
        return new EvaOriginalMeshGeometryR52.Geometry(variant,source.fingerprint(),parts);
    }
    private record RodPair(EvaOriginalMeshGeometryR52.Geometry aligned,double error){}
    private static Vec3 point(double[] xyz,int at){return new Vec3(xyz[at],xyz[at+1],xyz[at+2]);}
    private static Vec3 ringCentre(double[] xyz,int at)
    {var centre=Vec3.ZERO;for(int side=0;side<12;side++)centre=centre.add(point(xyz,side*18+at));return centre.scale(1D/12);}
    private static double angle(Vec3 a,Vec3 b){return Math.acos(Math.max(-1,Math.min(1,a.dot(b))));}
    private static RodPair alignRods(EvaOriginalMeshGeometryR52.Geometry from,EvaOriginalMeshGeometryR52.Geometry to)
    {
        var aligned=new ArrayList<EvaOriginalMeshGeometryR52.Part>();double error=0;
        for(int p=0;p<from.parts().size();p++)
        {
            var a=from.parts().get(p);var b=to.parts().get(p);var x=a.triangles();var y=b.triangles();
            if(x.length!=216||y.length!=216||!a.bone().equals(b.bone()))throw new IllegalStateException("Original twelve-sided rod topology required");
            var ca=ringCentre(x,0);var cb=ringCentre(y,0);var ua=ringCentre(x,15).subtract(ca).normalize();var ub=ringCentre(y,15).subtract(cb).normalize();
            var radial=point(x,0).subtract(ca).normalize();int shift=0;double best=Double.POSITIVE_INFINITY;
            for(int side=0;side<12;side++){double d=radial.distanceToSqr(point(y,side*18).subtract(cb).normalize());if(d<best){best=d;shift=side;}}
            // A cyclic ring reindex changes no rendered surface. It prevents
            // a basis switch from pairing opposite sides of the same rod.
            var reordered=new double[y.length];for(int side=0;side<12;side++)System.arraycopy(y,((side+shift)%12)*18,reordered,side*18,18);
            double axial=angle(ua,ub),radius=Math.max(point(x,0).distanceTo(ca),point(y,0).distanceTo(cb));
            boolean branchA=Math.abs(ua.y)<.95,branchB=Math.abs(ub.y)<.95;
            var reference=branchA?new Vec3(0,1,0):new Vec3(1,0,0);
            double transverse=Math.min(ua.cross(reference).length(),ub.cross(reference).length())-ua.distanceTo(ub);
            double directionChange=ua.distanceTo(ub);
            boolean sameBranch=branchA==branchB&&(branchA?Math.max(Math.abs(ua.y),Math.abs(ub.y))+directionChange<.95:
                    Math.min(Math.abs(ua.y),Math.abs(ub.y))-directionChange>=.95);
            double rotation=sameBranch&&transverse>.05?axial*(1+1/transverse):axial*22+Math.PI/6;
            // Rod centres interpolate affinely. Only the real current-tick
            // axial/radial turn bends its surface; no whole-radius padding.
            double reach=radius+(a.bone().startsWith("jaw/")?1.6:0);
            error=Math.max(error,reach*rotation*rotation/(8*Math.max(.1,Math.cos(Math.min(Math.PI/2,rotation)/2)))+reach*8e-6);
            aligned.add(new EvaOriginalMeshGeometryR52.Part(b.bone(),b.resource(),b.sourceSHA256(),reordered,b.bounds()));
        }
        return new RodPair(new EvaOriginalMeshGeometryR52.Geometry(to.variant(),to.sourceFingerprint(),aligned),error);
    }
    static EvaOriginalMeshGeometryR52.Geometry check(ServerLevel level,Original original,UNTransportEntity plane,EvaUnit01Entity eva,
            EvaBodyPose.Sample target,EvaAnatomicalHandsR45.Pose targetHands,NervAirframeGeometryR52 source)
    {
        var context=NervRouteRuntimeR52.flightContext(level);
        var job=NervAirTransportRuntimeR52.state(level).aircraft(plane.getUUID());
        if(context==null||job==null||!job.original().equals(original)||!job.carrying()
                ||!(level.getEntity(original.pilot()) instanceof LivingEntity pilot)
                ||NervMappedPlugMechanicsR52.actualCarrierVisibleR52(eva)&&!EvaMechanicalFrameR52.detachedCarrierR52(eva))return null;
        var initial=EvaMechanicalFrameR52.frozenLocalPose(eva);var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();
        var initialHands=EvaFrozenHandsR52.decode(eva.getUnitVariant(),provider.handContractFingerprint(eva.getUnitVariant()),
                provider.handJoints(eva.getUnitVariant()),EvaFrozenHandsR52.capture(eva,1));
        var frame=NervAircraftFrameR52.frame(plane,1);var root=frame.cargo();double clock=NervAircraftFrameR52.rotorClock(plane);
        var own=new HashSet<>(TransportMembershipR52.members(original,TransportMembershipR52.Kind.OCCUPIED));own.add(plane.getUUID());
        var skinA=EvaMechanicalFrameR52.capturedGeometry(eva);
        boolean unchanged=EvaShutdownR30.encode(initial).equals(EvaShutdownR30.encode(target))&&initialHands.rotations().equals(targetHands.rotations());
        if(unchanged)return skinA;
        var targetTag=EvaShutdownR30.encode(target);var cached=TARGETS.get(eva);
        EvaOriginalMeshGeometryR52.Geometry skinB;
        if(cached!=null&&cached.source()==skinA&&cached.provider()==provider&&cached.body().equals(targetTag)&&cached.hands().equals(targetHands.rotations()))skinB=cached.target();
        else
        {
            skinB=provider.evaluate(eva.getUnitVariant(),target,targetHands);var joints=new LinkedHashMap<String,Quaternionf>();
            targetHands.rotations().forEach((name,rotation)->joints.put(name,new Quaternionf(rotation)));
            TARGETS.put(eva,new TargetCache(skinA,provider,targetTag.copy(),Map.copyOf(joints),skinB));
        }
        // Normal recovery already holds the payload in its cleared pickup/lift
        // corridor. Articulating the supported body is not a second flight
        // admission: strict per-joint padding can engulf otherwise empty space.
        if(!NervTraversalPolicyR53.strict(level))return skinB;
        var geometryA=NervFlightProofR52.occupiedPoseGeometryR53(eva,initial,skinA,pilot);
        var geometryB=NervFlightProofR52.occupiedPoseGeometryR53(eva,target,skinB,pilot);
        double totalAngle=0;
        for(String name:initial.rig.keySet())totalAngle+=rotationAngle(initial.rotations.get(name),target.rotations.get(name));
        for(String name:initialHands.rotations().keySet())totalAngle+=rotationAngle(initialHands.rotations().get(name),targetHands.rotations().get(name));
        double error=.004+Math.max(NervRigidMeshSweepR52.radius(geometryA.bounds()),NervRigidMeshSweepR52.radius(geometryB.bounds()))*totalAngle*totalAngle/8;
        var localMotion=provider.releaseMotionBoundsR52(eva.getUnitVariant(),initial,initialHands,target,targetHands,skinA);
        var all=new ArrayList<NervHullGroundRecoveryR52.Chord>();
        for(int index=0;index<geometryA.parts().size();index++)
        {
            var a=geometryA.parts().get(index);var b=geometryB.parts().get(index);double partError=error;
            var rigid=localMotion.get("RigidCurveR53/"+a.bone());if(rigid!=null)partError=.004+rigid;
            if(a.bone().startsWith("capsule/")||a.bone().equals("pilot"))
            {
                double angle=0,translation=0,radius=0;
                for(String name="torso_upper";name!=null;name=initial.rig.get(name).parent())
                {
                    angle+=rotationAngle(initial.rotations.get(name),target.rotations.get(name));
                    translation+=initial.positions.get(name).distance(target.positions.get(name))*EvaScale.RENDER_SCALE;
                    var pivot=initial.matrix(name).transformPosition(new Vector3f(initial.rig.get(name).pivot())).mul(EvaScale.RENDER_SCALE);
                    for(var vertex:a.vertices())radius=Math.max(radius,vertex.distanceTo(new Vec3(pivot)));
                }
                partError=.004+(radius+translation)*Math.exp(angle)*angle*angle/8+translation*angle/4;
            }
            var ga=new EvaOriginalMeshGeometryR52.Geometry(geometryA.variant(),geometryA.sourceFingerprint(),List.of(a));
            var gb=new EvaOriginalMeshGeometryR52.Geometry(geometryB.variant(),geometryB.sourceFingerprint(),List.of(b));
            all.addAll(NervHullGroundRecoveryR52.chords(ga,gb,root,root,partError));
        }
        var nextContacts=contacts(target,skinB);
        var cradleA=cradle(source,frame,NervAircraftFrameR52.anchors(plane),NervAircraftFrameR52.jawAxes(plane),eva.getUnitVariant());
        var cradleB=cradle(source,frame,nextContacts.stream().map(NervAirCradleContactsR52.Contact::centre).toList(),nextContacts.stream().map(NervAirCradleContactsR52.Contact::axis).toList(),eva.getUnitVariant());
        var rods=alignRods(cradleA,cradleB);
        // These are the identical root tests made by intersectsChord, shared
        // only within this pose step. Rotor envelopes retain their arc error.
        var bodyBounds=NervRigidMeshSweepR52.transformed(source.bodyMesh().bounds(),frame.plane());
        var rotorFrom=new RigidTransform[4];var rotorTo=new RigidTransform[4];var rotorBounds=new AABB[4];
        for(int rotor=0;rotor<4;rotor++)
        {
            rotorFrom[rotor]=frame.plane().compose(source.rotorLocalFrame(rotor,clock));
            rotorTo[rotor]=frame.plane().compose(source.rotorLocalFrame(rotor,clock+1));
            rotorBounds[rotor]=source.rotorMesh(rotor).envelope(rotorFrom[rotor],rotorTo[rotor]);
        }

        for(var chord:all)
        {
            var rounding=new Vec3(chord.error(),chord.error(),chord.error());
            if(bodyBounds.intersects(chord.box())&&source.bodyMesh().intersectsChord(chord.vertices(),rounding,frame.plane()))return null;
            for(int rotor=0;rotor<4;rotor++)
                if(rotorBounds[rotor].intersects(chord.box())&&source.rotorMesh(rotor).intersectsChord(chord.vertices(),rounding,
                        rotorFrom[rotor],rotorTo[rotor]))return null;
        }
        all.addAll(NervHullGroundRecoveryR52.chords(cradleA,rods.aligned(),frame.plane(),frame.plane(),rods.error()));
        var byPart=new LinkedHashMap<String,AABB>();
        for(var chord:all)byPart.merge(chord.bone(),chord.box(),AABB::minmax);
        var envelopes=List.copyOf(byPart.values());
        Set<String> spaces;
        try{spaces=context.directory().dynamicSpacesR52().domains().isEmpty()?job.spaces():context.directory().dynamicSpacesR52().required(original.dimension(),envelopes,context.bindings());}
        catch(IllegalArgumentException unavailable){return null;}
        var declared=new ArrayList<AABB>();for(String id:spaces){var binding=context.bindings().get(id);if(binding==null)return null;declared.addAll(binding.spaces());}
        if(!NervHullGroundRecoveryR52.clearWorld(level,eva,all,declared,own))return null;
        return NervAirTransportRuntimeR52.reservePoseSpacesR53(level,job,spaces)?skinB:null;
    }
    private static double rotationAngle(Quaternionf a,Quaternionf b)
    {
        if(a.equals(b))return 0;
        double dot=(double)a.x*b.x+(double)a.y*b.y+(double)a.z*b.z+(double)a.w*b.w;
        double aa=(double)a.x*a.x+(double)a.y*a.y+(double)a.z*a.z+(double)a.w*a.w;
        double bb=(double)b.x*b.x+(double)b.y*b.y+(double)b.z*b.z+(double)b.w*b.w;
        return 2*Math.acos(Math.min(1,Math.abs(dot)/Math.sqrt(aa*bb)));
    }
    private NervAirRescuePoseR53(){}
}

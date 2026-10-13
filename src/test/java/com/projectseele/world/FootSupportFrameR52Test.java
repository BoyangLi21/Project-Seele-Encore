package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.EvaBodyPose;
import com.projectseele.entity.EvaScale;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Original delivered three-rig/support proof, without entities or a world. */
public final class FootSupportFrameR52Test
{
    private static int checks;private static double worstFootDrift,worstDistanceError,worstPlugError,worstFootBasisError;
    private static void check(boolean condition,String reason){checks++;if(!condition)throw new AssertionError(reason);}
    private static void near(Vec3 a,Vec3 b,double tolerance,String reason){check(a.distanceTo(b)<=tolerance,reason+" distance="+a.distanceTo(b));}
    private static Vector3f vector(JsonArray a){return new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());}
    private static Vec3 point(JsonArray a){return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static EvaBodyPose.Sample pose(JsonArray rows)
    {
        var rig=new LinkedHashMap<String,EvaBodyPose.Bone>();
        for(var raw:rows)
        {
            var row=raw.getAsJsonObject();String name=row.get("name").getAsString();String parent=row.has("parent")&&!row.get("parent").isJsonNull()?row.get("parent").getAsString():null;
            var angles=row.has("rotation")?vector(row.getAsJsonArray("rotation")):row.has("bindRotationDegrees")?vector(row.getAsJsonArray("bindRotationDegrees")):new Vector3f();angles.mul(Mth.DEG_TO_RAD);
            rig.put(name,new EvaBodyPose.Bone(name,parent,vector(row.getAsJsonArray("pivot")).mul(-1,1,1).div(16),new Quaternionf().rotationZYX(angles.z,-angles.y,-angles.x)));
        }
        var result=new EvaBodyPose.Sample(Map.copyOf(rig));for(var bone:rig.values())result.rotations.put(bone.name(),new Quaternionf(bone.bindRotation()));result.dirty();return result;
    }
    private static List<Vec3> posedPoints(EvaBodyPose.Sample pose,String bone,JsonArray original)
    {
        var result=new ArrayList<Vec3>();var matrix=pose.matrix(bone);
        for(var raw:original){var p=matrix.transformPosition(vector(raw.getAsJsonArray()).div(16)).mul(EvaScale.RENDER_SCALE);result.add(new Vec3(p.x,p.y,p.z));}
        return List.copyOf(result);
    }
    private static Vec3 bearing(List<Vec3> original)
    {
        double low=original.stream().mapToDouble(p->p.y).min().orElseThrow();Vec3 centre=Vec3.ZERO;int count=0;
        for(var p:original)if(p.y<=low+.12){centre=centre.add(p);count++;}
        centre=centre.scale(1D/count);return new Vec3(centre.x,low,centre.z);
    }
    private static RigidTransform seatedPlug(JsonObject dorsal)
    {
        // Exact original R50 locked-cage socket, expressed in EVA-local metres.
        var marker=point(dorsal.getAsJsonArray("centre")).scale(EvaScale.RENDER_SCALE/16D);var authored=point(dorsal.getAsJsonArray("outward"));var up=new Vec3(0,1,0);
        var outward=new Vec3(0,authored.y,authored.z).normalize();var hatchUp=up.subtract(outward.scale(up.dot(outward))).normalize();
        var socket=RigidTransform.fromAxes(new Vec3(-marker.x,marker.y,marker.z),hatchUp.cross(outward).normalize(),hatchUp,outward);
        return socket.compose(RigidTransform.of(new Vec3(0,0,-EntryPlugKinematics.LOCK_DEPTH_BLOCKS),new Quaternionf()));
    }
    private static void fails(Runnable operation,String reason)
    {boolean failed=false;try{operation.run();}catch(IllegalArgumentException|NullPointerException expected){failed=true;}check(failed,reason);}
    private static void rig(int variant,JsonObject fixture)
    {
        var pose=pose(fixture.getAsJsonObject("rigs").getAsJsonArray(Integer.toString(variant)));var support=fixture.getAsJsonObject("support");
        var left=bearing(posedPoints(pose,"foot_l",support.getAsJsonArray("foot_l")));var right=bearing(posedPoints(pose,"foot_r",support.getAsJsonArray("foot_r")));
        var binding=new FootSupportFrameR52.Binding(left,right,seatedPlug(fixture.getAsJsonObject("dorsal").getAsJsonObject(Integer.toString(variant))));
        check(binding.contactCentre().length()>1e-4,"Native support was replaced by an origin-centred dummy");
        var originalMatrices=new LinkedHashMap<String,Matrix4f>();for(String name:pose.rig.keySet())originalMatrices.put(name,pose.matrix(name));
        var body=new ArrayList<Vec3>();for(var row:support.entrySet())body.addAll(posedPoints(pose,row.getKey(),row.getValue().getAsJsonArray()));
        check(body.size()==396,"Complete original rendered support points missing");
        // Also retain every actual native rig joint, including the three rigs'
        // distinct pivots; support evidence alone uses the original shared set.
        for(var bone:pose.rig.values())
        {var p=pose.matrix(bone.name()).transformPosition(new Vector3f(bone.pivot())).mul(EvaScale.RENDER_SCALE);body.add(new Vec3(p.x,p.y,p.z));}
        var span=right.subtract(left).normalize();var first=new Quaternionf().rotationY(.19F).rotateZ(-.07F);
        var axis=first.transform(span.toVector3f()).normalize();var last=new Quaternionf().rotationAxis(Mth.HALF_PI,axis.x,axis.y,axis.z).mul(new Quaternionf(first));
        var firstCopy=new Quaternionf(first);var lastCopy=new Quaternionf(last);
        // Pure test-space frames, not authored track/world coordinates.
        var frame=RigidTransform.of(new Vec3(17.25,-5.5,9.75),new Quaternionf().rotationY(.71F).rotateX(-.11F));
        var beginning=FootSupportFrameR52.sample(binding,frame,first,last,0);var pivot=binding.contactCentre();
        for(int step=0;step<=128;step++)
        {
            double t=step/128D;var current=FootSupportFrameR52.sample(binding,frame,first,last,t);
            if(step%16==0)
            {
                var transported=pose(fixture.getAsJsonObject("rigs").getAsJsonArray(Integer.toString(variant)));
                var outer=new Quaternionf().rotationY(1.234F);
                var composed=FootSupportFrameR52.composeModelRoot(transported.rig.get("root").pivot(),transported.positions.get("root"),
                        transported.rotations.get("root"),outer,current.evaRoot().rotation());
                transported.positions.put("root",composed.offset());transported.rotations.put("root",composed.rotation());transported.dirty();
                var oldOuter=RigidTransform.of(current.evaRoot().translation(),outer);
                for(var row:support.entrySet())
                {
                    var original=posedPoints(pose,row.getKey(),row.getValue().getAsJsonArray());
                    var adjusted=posedPoints(transported,row.getKey(),row.getValue().getAsJsonArray());
                    for(int index=0;index<original.size();index++)near(oldOuter.transformPoint(adjusted.get(index)),
                            current.evaRoot().transformPoint(original.get(index)),.00015,"Actual CPU/Gecko root-bone composition differs from whole rigid frame");
                }
                for(String name:pose.rig.keySet())if(!name.equals("root"))
                {
                    check(transported.rotations.get(name).equals(pose.rotations.get(name)),"Carrier turn bent an original joint "+name);
                    check(transported.positions.get(name).equals(pose.positions.get(name)),"Carrier turn moved an original joint "+name);
                }
            }
            double drift=Math.max(current.leftContact().distanceTo(beginning.leftContact()),current.rightContact().distanceTo(beginning.rightContact()));worstFootDrift=Math.max(worstFootDrift,drift);
            check(drift<.00005,"Native left/right bearing slipped during 90-degree rotation");near(current.evaRoot().transformPoint(pivot),frame.translation(),.00005,"Measured bearing centre moved");
            near(current.evaRoot().transformPoint(left),current.leftContact(),0,"Left contact is not in the same sampled root frame");near(current.evaRoot().transformPoint(right),current.rightContact(),0,"Right contact is not in the same sampled root frame");
            var sign=FootSupportFrameR52.sample(binding,frame,first,new Quaternionf(last).mul(-1),t);
            for(var p:body)
            {
                var a=current.evaRoot().transformPoint(p);var b=current.evaRoot().transformPoint(pivot);double error=Math.abs(a.distanceTo(b)-p.distanceTo(pivot));worstDistanceError=Math.max(worstDistanceError,error);
                check(error<.00008,"Original body/support scale changed");near(a,sign.evaRoot().transformPoint(p),.00005,"Quaternion sign selected a different physical path");
                near(current.evaRoot().inverse().transformPoint(a),p,.00008,"Original body point changed in its local frame");
            }
            for(var marker:List.of(Vec3.ZERO,new Vec3(0,1,0),new Vec3(0,0,5)))
            {
                var expected=current.evaRoot().transformPoint(binding.plugInEva().transformPoint(marker));var actual=current.plugWorld().transformPoint(marker);double error=expected.distanceTo(actual);worstPlugError=Math.max(worstPlugError,error);near(expected,actual,.00005,"Original plug used a different sample instant/frame");
            }
            for(String name:List.of("ankle_l","foot_l","ankle_r","foot_r"))
            {
                var original=originalMatrices.get(name);check(original!=null,"Original native ankle/foot missing: "+name);
                var localPivot=original.transformPosition(new Vector3f(pose.rig.get(name).pivot())).mul(EvaScale.RENDER_SCALE);
                var worldPivot=current.evaRoot().transformPoint(new Vec3(localPivot.x,localPivot.y,localPivot.z));
                near(current.evaRoot().inverse().transformPoint(worldPivot),new Vec3(localPivot.x,localPivot.y,localPivot.z),.00005,"Original ankle/foot joint pivot changed");
                // Preserve all three local vector bases, hence the direction
                // and magnitude of any original foot push. This adds no force
                // and does not pretend to test a runtime propulsion solver.
                for(var axisPoint:List.of(new Vector3f(1,0,0),new Vector3f(0,1,0),new Vector3f(0,0,1)))
                {
                    var local=original.transformDirection(axisPoint);var direction=new Vec3(local.x,local.y,local.z);var world=current.evaRoot().transformVector(direction);
                    double error=current.evaRoot().inverse().transformVector(world).distanceTo(direction);worstFootBasisError=Math.max(worstFootBasisError,error);
                    check(Math.abs(world.length()-direction.length())<1e-6,"Original foot push vector magnitude changed");check(error<1e-6,"Original foot push vector basis changed");
                }
            }
            double expectedAngle=t*90,actualAngle=beginning.evaRoot().rotationErrorDegrees(current.evaRoot());check(Math.abs(actualAngle-expectedAngle)<.1,"90-degree shortest-path angle is discontinuous");
        }
        check(first.equals(firstCopy)&&last.equals(lastCopy),"Input orientation mutated");
        var scaledInput=FootSupportFrameR52.sample(binding,frame,new Quaternionf(first).mul(3),new Quaternionf(last).mul(5),.5);
        var unitInput=FootSupportFrameR52.sample(binding,frame,first,last,.5);
        for(var p:body)near(scaledInput.evaRoot().transformPoint(p),unitInput.evaRoot().transformPoint(p),.00008,"Nonunit input quaternion introduced scale");
        for(String name:pose.rig.keySet())check(pose.matrix(name).equals(originalMatrices.get(name)),"Original joint matrix changed: "+name);
        var moved=FootSupportFrameR52.sample(binding,RigidTransform.of(frame.translation().add(.6,1.1,-.3),frame.rotation()),first,last,.5);var fixed=FootSupportFrameR52.sample(binding,frame,first,last,.5);
        near(moved.leftContact().subtract(fixed.leftContact()),new Vec3(.6,1.1,-.3),1e-12,"Carrier translation did not carry original left contact");near(moved.plugWorld().translation().subtract(fixed.plugWorld().translation()),new Vec3(.6,1.1,-.3),1e-12,"Carrier translation did not carry original plug");
        var before=new Quaternionf().rotationAxis((float)Math.toRadians(350),(float)span.x,(float)span.y,(float)span.z);var after=new Quaternionf().rotationAxis((float)Math.toRadians(10),(float)span.x,(float)span.y,(float)span.z);
        var middle=FootSupportFrameR52.sample(binding,frame,before,after,.5);for(var p:body)near(middle.evaRoot().transformPoint(p),FootSupportFrameR52.sample(binding,frame,new Quaternionf(),new Quaternionf(),0).evaRoot().transformPoint(p),.00008,"350-to-10 turn took the long route");
        var flipped=new Quaternionf().rotationTo(span.toVector3f(),span.cross(Math.abs(span.y)<.9?new Vec3(0,1,0):new Vec3(1,0,0)).normalize().toVector3f());
        fails(()->FootSupportFrameR52.sample(binding,frame,new Quaternionf(),flipped,.5),"Incompatible two-foot axis silently slid the original feet");
        fails(()->FootSupportFrameR52.sample(binding,frame,new Quaternionf(0,0,0,0),after,.5),"Degenerate quaternion accepted");fails(()->FootSupportFrameR52.sample(binding,frame,first,last,Double.NaN),"Nonfinite time accepted");fails(()->FootSupportFrameR52.sample(binding,frame,first,last,1.1),"Out-of-range sample accepted");
        fails(()->new FootSupportFrameR52.Binding(left,left,binding.plugInEva()),"Coincident foot contacts accepted");fails(()->new FootSupportFrameR52.Binding(new Vec3(Double.NaN,0,0),right,binding.plugInEva()),"Invalid original foot accepted");
        System.out.println("Original EVA-0"+variant+" rig="+pose.rig.size()+" supportAndRigPoints="+body.size()+" left="+left+" right="+right+" pivot="+pivot);
    }
    public static void main(String[] args)throws Exception
    {
        JsonObject fixture;try(var stream=FootSupportFrameR52Test.class.getResourceAsStream("/physics/foot_support_r52_native_rigs.json"))
        {check(stream!=null,"Original delivered rig evidence missing");fixture=JsonParser.parseReader(new InputStreamReader(stream,StandardCharsets.UTF_8)).getAsJsonObject();}
        check(fixture.getAsJsonObject("source").get("body_sha256").getAsString().equals("181632e1834980ff8d383b0760663dcf54ada7e3b0acc09db25c3caca9d9b324"),"Unexpected original delivered body evidence");
        for(int variant=0;variant<3;variant++)rig(variant,fixture);
        System.out.println("Foot rigid-frame PASS checks="+checks+" worstFootDriftMetres="+worstFootDrift+" worstRigidDistanceErrorMetres="+worstDistanceError+" worstSameTimePlugErrorMetres="+worstPlugError+" worstFootBasisError="+worstFootBasisError+"; original three rigs/ankles/foot push bases unchanged, 90-degree fixed bearings, shortest quaternion path, moving measured frame; no world/entity/logistics/propulsion or animation acceptance");
    }
}

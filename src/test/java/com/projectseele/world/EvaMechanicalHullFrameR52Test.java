package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import java.lang.reflect.Method;
import java.nio.file.*;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;

/** Actual three-rig body/dorsal inputs validate the production empty-socket
 * helper and stopped root handoff. No live entity/game acceptance claim. */
public final class EvaMechanicalHullFrameR52Test
{
    private static int checks;
    private static double worstPosition,worstAngle;
    private static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    private static Vec3 point(JsonArray a){return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static void same(RigidTransform a,RigidTransform b,String why)
    {double p=a.translation().distanceTo(b.translation()),angle=a.rotationErrorDegrees(b);worstPosition=Math.max(worstPosition,p);worstAngle=Math.max(worstAngle,angle);check(p<.0002&&angle<.0001,why+" pos="+p+" angle="+angle);}
    public static void main(String[] args)throws Exception
    {
        var data=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var dorsal=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject().getAsJsonObject("profiles");
        Method makeBody=EvaOriginalMeshGeometryR52Test.class.getDeclaredMethod("body",JsonObject.class,int.class);makeBody.setAccessible(true);
        for(int v=0;v<3;v++)
        {
            var spec=dorsal.getAsJsonObject("eva_unit0"+v);var profile=new EvaDorsalProfile.Profile(point(spec.getAsJsonArray("centre")),point(spec.getAsJsonArray("outward")),point(spec.getAsJsonArray("hinge")),point(spec.getAsJsonArray("hinge_axis")),spec.get("open_angle_degrees").getAsFloat());
            for(float yaw:new float[]{0,37,180})for(boolean fallen:new boolean[]{false,true})
            {
                var frozen=(EvaBodyPose.Sample)makeBody.invoke(null,data,v);if(fallen){frozen.rotations.put("root",new Quaternionf().rotationX(1.25F));frozen.rotations.put("torso_upper",new Quaternionf().rotationZ(.21F));frozen.positions.get("root").set(.13F,.25F,-.1F);frozen.dirty();}
                Vec3 origin=new Vec3(40,20,-30);var basis=RigidTransform.of(origin,new Quaternionf().rotationY((180-yaw)*(float)Math.PI/180));
                var before=EvaMechanicalFrameMathR52.emptySocket(frozen,EvaRifleKinematics.frameWorldR52(origin,yaw),profile);var local=basis.inverse().compose(before);
                // Compose exactly the production mechanical root handoff,
                // then independently rerun the posed chest/profile socket.
                for(float turn:new float[]{0,.3F,1.1F})
                {
                    var wanted=RigidTransform.of(origin.add(.4,1,-.3),basis.rotation().mul(new Quaternionf().rotationX(turn)));
                    var composed=FootSupportFrameR52.composeModelRoot(frozen.rig.get("root").pivot(),frozen.positions.get("root"),frozen.rotations.get("root"),basis.rotation(),wanted.rotation());
                    var rendered=EvaBodyPose.copy(frozen);rendered.positions.put("root",composed.offset());rendered.rotations.put("root",composed.rotation());rendered.dirty();
                    var after=EvaMechanicalFrameMathR52.emptySocket(rendered,EvaRifleKinematics.frameWorldR52(wanted.translation(),yaw),profile);
                    same(wanted.compose(local),after,"Same frozen body empty socket mismatch variant="+v+" fallen="+fallen);
                }
                var upright=(EvaBodyPose.Sample)makeBody.invoke(null,data,v);if(fallen)check(before.translation().distanceTo(EvaMechanicalFrameMathR52.emptySocket(upright,EvaRifleKinematics.frameWorldR52(origin,yaw),profile).translation())>1,"Fallen fixture did not reject unrelated upright reference");
            }
        }
        Vec3 root=new Vec3(5,10,-3);var offsetBox=new AABB(-4,7,-2,18,14,41);var clipped=offsetBox.move(.2,0,-.6);check(EvaMechanicalFrameMathR52.rootAfterNativeMove(root,offsetBox,clipped).distanceTo(root.add(.2,0,-.6))<1e-12,"Stopped hull adopted bbox centre/minY as root");
        check(EvaMechanicalFrameMathR52.rootAfterNativeMove(root,offsetBox,offsetBox).equals(root),"Blocked native move changed stopped root");
        System.out.println("R52 occupied/fallen empty-socket and stopped native-bounds handoff PASS checks="+checks+" worstPositionMetres="+worstPosition+" worstAngleDegrees="+worstAngle+"; real three-rig inputs, no live transport acceptance");
    }
    private EvaMechanicalHullFrameR52Test(){}
}

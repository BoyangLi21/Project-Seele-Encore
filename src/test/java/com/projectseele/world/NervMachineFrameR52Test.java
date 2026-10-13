package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import net.minecraft.world.phys.*;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Actual imported chuck vertices verify its complete outer/local composition. */
public final class NervMachineFrameR52Test
{
    public static void main(String[] args)throws Exception
    {
        byte[] source=args[0].equals("@classpath")?EvaOriginalMeshGeometryR52.classpathBytes("mesh/tripo_gripper_r48.json"):Files.readAllBytes(Path.of(args[0]));var root=JsonParser.parseString(new String(source,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();long count=0;double after=0,before=0;
        for(var outer:new Quaternionf[]{new Quaternionf().rotationY((float)Math.PI),new Quaternionf().rotationZYX(.29F,.71F,-.23F)})
        {
            var origin=new Vec3(12.5,-47,28.5);var world=RigidTransform.of(new Vec3(13.8,-52,31.2),new Quaternionf().rotationZYX(.4F,-.6F,.7F));var corrected=NervMachineFrameR52.worldToLocal(origin,outer,world.translation(),world.rotation());
            var outerMatrix=new Matrix4f().translate((float)origin.x,(float)origin.y,(float)origin.z).rotate(outer);var local=new Matrix4f(outerMatrix).translate((float)corrected.translation().x,(float)corrected.translation().y,(float)corrected.translation().z).rotate(corrected.rotation());
            var old=new Matrix4f(outerMatrix).translate((float)(world.translation().x-origin.x),(float)(world.translation().y-origin.y),(float)(world.translation().z-origin.z)).rotate(world.rotation());
            for(var part:root.getAsJsonObject("parts").entrySet()){var v=part.getValue().getAsJsonArray();for(int i=0;i<v.size();i+=8){var p=new Vector3f(v.get(i).getAsFloat(),v.get(i+1).getAsFloat(),v.get(i+2).getAsFloat());var expected=world.transformPoint(new Vec3(p.x,p.y,p.z));var actual=local.transformPosition(new Vector3f(p));var bad=old.transformPosition(new Vector3f(p));after=Math.max(after,new Vec3(actual.x,actual.y,actual.z).distanceTo(expected));before=Math.max(before,new Vec3(bad.x,bad.y,bad.z).distanceTo(expected));count++;}}
        }
        if(after>.00003||before<1)throw new AssertionError("Actual double-turn/outer-frame regression after="+after+" before="+before);var receipt=new JsonObject();receipt.addProperty("gripper_source_sha256",java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(source)));receipt.addProperty("actual_gripper_vertices",count);receipt.addProperty("before_doubleturn_max_error_m",before);receipt.addProperty("after_max_error_m",after);receipt.addProperty("native_acceptance",false);Files.writeString(Path.of(args[1]),receipt.toString()+"\n");System.out.println(receipt);
    }
}

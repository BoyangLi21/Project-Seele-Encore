package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import org.joml.Matrix4f;

/** Real selected imported clamp vertices compared with the production draw
 * PoseStack formulas at common crane endpoints. No trajectory pass claim. */
public final class NervCraneGeometryR52Test
{
    public static void main(String[] args)throws Exception
    {
        byte[] raw=EvaOriginalMeshGeometryR52.classpathBytes("mesh/tripo_gripper_r48.json");var root=JsonParser.parseString(new String(raw,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();String gripSha=java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(raw));byte[] procedural=Files.readAllBytes(Path.of(args[0]));String procSha=java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(procedural));var geometry=NervCraneGeometryR52.load(name->name.startsWith("eva/")?procedural:raw,procSha,gripSha);
        long compared=0;double maximum=0;int poses=0;
        for(var outer:new Quaternionf[]{new Quaternionf(),new Quaternionf().rotationY((float)Math.PI),new Quaternionf().rotationY(.73F)})for(int age:new int[]{0,10,40,70,100})
        {
            var machine=RigidTransform.of(new Vec3(12.5,-609.25,317.5),outer);var plug=RigidTransform.of(machine.translation().add(0,-28.25,3.75),new Quaternionf().rotationZYX(.19F,.63F,-.21F));var pose=NervCranePoseR52.evaluate(machine,-28.25+26.25*age/100,plug,false,null,null,geometry.mount());var actual=geometry.parts(pose);if(actual.size()!=19||actual.stream().filter(p->p.name().startsWith("gripper/")).count()!=3)throw new AssertionError("Incomplete actual whole crane inventory");
            for(var part:actual)
            {
                if(!part.name().startsWith("gripper/"))continue;String key=part.name().substring("gripper/".length());var values=root.getAsJsonObject("parts").getAsJsonArray(key);var matrix=new Matrix4f().rotate(machine.rotation()).translate((float)pose.grip().translation().x,(float)pose.grip().translation().y,(float)pose.grip().translation().z).rotate(pose.grip().rotation());
                if(!key.equals("body")){var a=root.getAsJsonObject("anchors").getAsJsonArray(key);float x=a.get(0).getAsFloat(),y=a.get(1).getAsFloat(),z=a.get(2).getAsFloat();matrix.translate(x,y,z).rotateZ((key.equals("jaw_left")?-1F:1F)*32*pose.released()*(float)(Math.PI/180)).translate(-x,-y,-z);}
                double[] nativeVertices=part.triangles();if(nativeVertices.length!=values.size()/8*3)throw new AssertionError("Original clamp topology was changed");
                for(int i=0,j=0;i<values.size();i+=8,j+=3){var source=new Vector3f(values.get(i).getAsFloat(),values.get(i+1).getAsFloat(),values.get(i+2).getAsFloat());var expected=matrix.transformPosition(source);var actualWorld=part.frame().transformPoint(new Vec3(nativeVertices[j],nativeVertices[j+1],nativeVertices[j+2]));maximum=Math.max(maximum,actualWorld.distanceTo(machine.translation().add(expected.x,expected.y,expected.z)));compared++;}
            }
            poses++;
        }
        if(maximum>.0001)throw new AssertionError("Actual crane draw/common geometry mismatch "+maximum);System.out.println("Actual clamp/common crane geometry comparison PASS poses="+poses+" vertices="+compared+" max_error_m="+maximum+"; no world/native/trajectory acceptance");
    }
}

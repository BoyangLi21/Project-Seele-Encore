package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.YashimaCannonGeometryR52;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPInputStream;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

/** Same native narrow-phase code and complete source triangles; read-only fitting, never a native campaign receipt. */
public final class AuditYashimaCannonMeshFitR52
{
    public static void main(String[] args)throws Exception
    {
        var candidate=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var g=YashimaCannonGeometryR52.parse(candidate);YashimaCannonMeshR52.requireOriginal(candidate,g);
        var method=YashimaCannonMeshR52.class.getDeclaredMethod("gun",float.class);method.setAccessible(true);var gun=(NervRigidMeshSweepR52)method.invoke(null,g.scale());
        var m=g.matrix(YashimaCannonGeometryR52.vector(candidate.getAsJsonArray("raised_position")),new Quaternionf());
        var frame=RigidTransform.of(new Vec3(m.getTranslation(new org.joml.Vector3f())),m.getUnnormalizedRotation(new Quaternionf()).normalize());
        var body=RigidTransform.of(YashimaCannonGeometryR52.vector(candidate.getAsJsonArray("prone_position")),new Quaternionf().rotationY((180-candidate.get("prone_yaw").getAsFloat())*(float)Math.PI/180));
        var blocked=new ArrayList<String>();var minimum=new LinkedHashMap<String,Double>();var meshes=new LinkedHashMap<String,NervRigidMeshSweepR52>();
        try(var input=new DataInputStream(new GZIPInputStream(Files.newInputStream(Path.of(args[1])))))
        {
            if(input.readInt()!=0x52353243||input.readInt()!=1)throw new IllegalArgumentException("Actual source cloud required");int count=input.readInt();
            for(int part=0;part<count;part++)
            {String name=input.readUTF(),sha=input.readUTF();int n=input.readInt();double[] vertices=new double[n*3];double min=Double.POSITIVE_INFINITY;for(int i=0;i<vertices.length;i++){vertices[i]=input.readFloat();if(i%3==1)min=Math.min(min,vertices[i]);}minimum.put(name,min);
                var mesh=new NervRigidMeshSweepR52(vertices);meshes.put(name,mesh);if(!Set.of("hand_l","hand_r","wrist_l","wrist_r").contains(name)&&gun.intersects(frame,frame,mesh,body,body,.001,Vec3.ZERO))blocked.add(name);}
        }
        var self=new ArrayList<String>();for(String arm:List.of("arm_l","arm_r","forearm_l","forearm_r"))
            for(String other:List.of("head","pylon_"+(arm.endsWith("l")?"r":"l"),"forearm_"+(arm.endsWith("l")?"r":"l")))
                if(meshes.get(arm).intersects(body,body,meshes.get(other),body,body,.001,Vec3.ZERO))self.add(arm+":"+other);
        for(String arm:List.of("forearm_l","forearm_r"))for(String other:List.of("torso_lower","torso_upper","pylon_l","pylon_r"))
            if(meshes.get(arm).intersects(body,body,meshes.get(other),body,body,.001,Vec3.ZERO))self.add(arm+":"+other);
        var report=Map.of("scope","Complete unchanged original source skin/gun with production paired BVH; model fitting only, not native station acceptance", "non_grip_triangle_intersections",blocked,"unconnected_arm_self_intersections",self,"skin_minimum_y_metres",minimum,"clear",blocked.isEmpty()&&self.isEmpty());
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(report));System.out.println(new Gson().toJson(report));
    }
}

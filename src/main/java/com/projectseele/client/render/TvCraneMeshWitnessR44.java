package com.projectseele.client.render;

import com.google.gson.*;
import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.entity.NervCarrierPlatformEntity;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import java.nio.file.*;
import java.util.*;

/** Reviewonly actual submitted crane quads and their current entity-relative frame. */
final class TvCraneMeshWitnessR44
{
    private record Frame(String uuid,int variant,long tick,float partial,Vec3 origin,Matrix4f inverse,JsonArray parts) { }
    private static final ThreadLocal<Frame> ACTIVE=new ThreadLocal<>();
    private static final Map<Integer,Long> LAST=new HashMap<>();
    private static final Map<Integer,Integer> COUNT=new HashMap<>();
    static void begin(NervCarrierPlatformEntity entity,float partial,PoseStack poses)
    {
        ACTIVE.remove();
        if(!Boolean.getBoolean("projectseele.r44NativeCraneMeshWitness")||!entity.isPlugCrane()
            ||!entity.level().dimension().location().toString().equals("projectseele:geofront"))return;
        int v=entity.getUnitVariant();long tick=entity.level().getGameTime();
        if(v<0||v>2||COUNT.getOrDefault(v,0)>=Integer.getInteger("projectseele.r44CraneWitnessMaximumPerBay",72)
            ||LAST.getOrDefault(v,Long.MIN_VALUE)==tick
            ||Math.floorMod(tick,Integer.getInteger("projectseele.r44CraneWitnessStride",20))!=0)return;
        LAST.put(v,tick);COUNT.merge(v,1,Integer::sum);
        ACTIVE.set(new Frame(entity.getStringUUID(),v,tick,partial,entity.getPosition(partial),
            new Matrix4f(poses.last().pose()).invert(),new JsonArray()));
    }
    static void part(float[] vertices,PoseStack poses)
    {
        var frame=ACTIVE.get();if(frame==null)return;
        Matrix4f relative=new Matrix4f(frame.inverse).mul(poses.last().pose());
        var triangles=new JsonArray();int quads=vertices.length/44;
        for(int q=0;q<quads;q++)for(int[] indices:new int[][]{{0,1,2},{0,2,3}})
        {
            Vector3f[] local=new Vector3f[3];var world=new JsonArray();
            for(int i=0;i<3;i++)
            {
                int k=q*44+indices[i]*11;
                local[i]=relative.transformPosition(new Vector3f(vertices[k],vertices[k+1],vertices[k+2]));
                var xyz=new JsonArray();xyz.add(frame.origin.x+local[i].x);xyz.add(frame.origin.y+local[i].y);xyz.add(frame.origin.z+local[i].z);world.add(xyz);
            }
            if(new Vector3f(local[1]).sub(local[0]).cross(new Vector3f(local[2]).sub(local[0])).lengthSquared()<1e-12F)continue;
            triangles.add(world);
        }
        var row=new JsonObject();row.addProperty("part_call_index",frame.parts.size());row.addProperty("source_quad_count",quads);
        row.add("actual_world_triangles",triangles);frame.parts.add(row);
    }
    static void end()
    {
        var frame=ACTIVE.get();ACTIVE.remove();if(frame==null)return;
        String target=System.getProperty("projectseele.r44CraneMeshWitnessPath","");
        if(target.isBlank())throw new IllegalStateException("Crane witness output must be explicit");
        var row=new JsonObject();row.addProperty("crane_uuid",frame.uuid);row.addProperty("variant",frame.variant);
        row.addProperty("world_tick",frame.tick);row.addProperty("partial",frame.partial);row.add("parts",frame.parts);
        row.addProperty("frame_basis","inverseinitialentityPose*submittedpartPose; entitygetPosition(partial) worldorigin added. No synthetic crane pose.");
        try{Path path=Path.of(target);Files.createDirectories(path.getParent());Files.writeString(path,new Gson().toJson(row)+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);}
        catch(java.io.IOException e){throw new IllegalStateException("Crane witness export failed",e);}
    }
    private TvCraneMeshWitnessR44() { }
}

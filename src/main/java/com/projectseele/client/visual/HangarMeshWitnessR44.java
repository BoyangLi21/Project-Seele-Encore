package com.projectseele.client.visual;

import com.google.gson.*;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.Minecraft;
import net.minecraft.world.level.storage.LevelResource;
import org.joml.Matrix4f;
import org.joml.Matrix3f;
import org.joml.Vector3f;
import java.nio.file.*;
import java.util.*;

/** Actual submitted wet-cage body surfaces; a bounding box is never a substitute for shoulder contact. */
public final class HangarMeshWitnessR44
{
    private static final double[] X={-11.5,30.5,72.5};
    private static final Map<Integer,JsonObject> actors=new TreeMap<>();
    private static final Map<Integer,Integer> frameTicks=new HashMap<>();
    private static final Map<Integer,Set<String>> parts=new HashMap<>();

    public static void capture(EvaUnit01Entity entity,String bone,float[] vertices,int stride,
                               float px,float py,float pz,Matrix4f worldMatrix)
    {
        if(!Boolean.getBoolean("projectseele.r44HangarMeshWitness")||entity.isExperimentalUnit())return;
        if(com.projectseele.client.render.ShaderShadowPassR44.active())return;
        int variant=entity.getUnitVariant();if(variant<0||variant>2)return;
        if(Math.abs(entity.getX()-X[variant])>.12||Math.abs(entity.getY()+442)>.12||Math.abs(entity.getZ()+239.5)>.12)return;
        var mc=Minecraft.getInstance();if(mc.getSingleplayerServer()==null)return;
        Path world=mc.getSingleplayerServer().getWorldPath(LevelResource.ROOT).normalize();
        if(!world.getFileName().toString().equals("SEELE_FIELD_R44_REVIEW"))throw new IllegalStateException("Hangar mesh witness refuses another world");
        if(!frameTicks.containsKey(variant))
        {
            frameTicks.put(variant,entity.tickCount);parts.put(variant,new HashSet<>());
            var row=new JsonObject();row.addProperty("variant",variant);row.addProperty("uuid",entity.getUUID().toString());
            row.addProperty("tick",entity.tickCount);row.addProperty("x",entity.getX());row.addProperty("y",entity.getY());row.addProperty("z",entity.getZ());
            row.addProperty("yaw",entity.getYRot());row.addProperty("locked",entity.isNervLogisticsLocked());
            row.addProperty("launch_phase",entity.getLaunchPhase());row.addProperty("pose_source","Actual render skinVertices and submitted modelToWorld; no outline approximation");
            row.add("parts",new JsonObject());actors.put(variant,row);
        }
        if(frameTicks.get(variant)!=entity.tickCount||!parts.get(variant).add(bone))return;
        double[] bounds={Double.POSITIVE_INFINITY,Double.POSITIVE_INFINITY,Double.POSITIVE_INFINITY,
                Double.NEGATIVE_INFINITY,Double.NEGATIVE_INFINITY,Double.NEGATIVE_INFINITY};
        Vector3f point=new Vector3f();var top=new ArrayList<double[]>();
        for(int i=0;i+stride<=vertices.length;i+=stride)
        {
            point.set(-(vertices[i]+px)/16,(vertices[i+1]+py)/16,(vertices[i+2]+pz)/16);worldMatrix.transformPosition(point);
            bounds[0]=Math.min(bounds[0],point.x);bounds[1]=Math.min(bounds[1],point.y);bounds[2]=Math.min(bounds[2],point.z);
            bounds[3]=Math.max(bounds[3],point.x);bounds[4]=Math.max(bounds[4],point.y);bounds[5]=Math.max(bounds[5],point.z);
            top.add(new double[]{point.x,point.y,point.z});
        }
        if(top.isEmpty())return;
        top.sort((a,b)->Double.compare(b[1],a[1]));var row=new JsonObject();row.add("world_bounds",new Gson().toJsonTree(bounds));
        row.addProperty("submitted_vertices",vertices.length/stride);row.add("top_surface_points",new Gson().toJsonTree(top.subList(0,Math.min(32,top.size()))));
        boolean fullBody=Boolean.getBoolean("projectseele.r44HangarFullBodyTriangles");
        if(fullBody||bone.startsWith("arm_")||bone.startsWith("pylon_"))
        {
            double bandDepth=Double.parseDouble(System.getProperty("projectseele.r44HangarContactBandDepth","1.5"));
            if(!Double.isFinite(bandDepth)||bandDepth<=0||bandDepth>100)
                throw new IllegalArgumentException("Finite contact diagnostic band in (0,100] required");
            var triangles=new JsonArray();var normalMatrix=new Matrix3f(worldMatrix).invert().transpose();
            for(int i=0;i+stride*3<=vertices.length;i+=stride*3)
            {
                var points=new JsonArray();boolean upper=false;
                for(int corner=0;corner<3;corner++)
                {
                    int k=i+corner*stride;point.set(-(vertices[k]+px)/16,(vertices[k+1]+py)/16,(vertices[k+2]+pz)/16);worldMatrix.transformPosition(point);
                    upper|=fullBody||point.y>=bounds[4]-bandDepth;
                    points.add(new Gson().toJsonTree(new float[]{point.x,point.y,point.z}));
                }
                if(!upper)continue;
                var n=new Vector3f(-vertices[i+5],vertices[i+6],vertices[i+7]);normalMatrix.transform(n).normalize();
                var triangle=new JsonObject();triangle.add("world_vertices",points);triangle.add("world_outward_normal",new Gson().toJsonTree(new float[]{n.x,n.y,n.z}));triangles.add(triangle);
            }
            row.add("top_band_triangles",triangles);row.addProperty("top_band_depth_metres",fullBody?Math.max(bandDepth,bounds[4]-bounds[1]):bandDepth);
            row.addProperty("complete_submitted_part_triangles",fullBody);
            if(fullBody&&triangles.size()*3!=vertices.length/stride)
                throw new IllegalStateException("Full body witness did not retain every submitted triangle: "+bone);
        }
        actors.get(variant).getAsJsonObject("parts").add(bone,row);
        try
        {
            var report=new JsonObject();report.add("actors",new Gson().toJsonTree(actors));report.addProperty("full_three_rig_record",actors.size()==3);
            report.addProperty("contact_quality","UNVERIFIED: pads must meet surfaces without body/capsule sweep penetration");
            Files.writeString(world.resolve("r44_hangar_body_surfaces.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));
        }
        catch(Exception error){throw new IllegalStateException("Could not save real hangar body surfaces",error);}
    }
    private HangarMeshWitnessR44(){}
}

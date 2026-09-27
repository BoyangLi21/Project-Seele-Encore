package com.projectseele.world;

import com.bulletphysics.collision.narrowphase.*;
import com.bulletphysics.collision.shapes.*;
import com.bulletphysics.linearmath.Transform;
import com.bulletphysics.util.ObjectArrayList;
import com.projectseele.entity.*;
import com.projectseele.physics.CombatBodyProfiles;
import com.google.gson.JsonArray;
import java.util.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.phys.*;
import org.joml.Matrix4f;
import org.joml.Vector3f;

/** Carrier translations follow measured convex parts, including the empty
 * corners of a rotated AABB. Uses the articulated solver's hulls and scale. */
public final class VerticalCarrierSweepR40
{
    private static final float SCALE=CombatBodyProfiles.BLOCK_TO_PHYSICS;
    private record Part(String name,ConvexHullShape shape,AABB bounds) {}
    private static final Map<ServerLevel,Map<String,Long>> REPORTED=new WeakHashMap<>();

    private static Matrix4f matrix(JsonArray values)
    {
        float[] a=new float[16];for(int i=0;i<16;i++)a[i]=values.get(i).getAsFloat();
        return new Matrix4f().set(a).transpose();
    }
    public static List<Vec3> localVertices(EvaUnit01Entity eva,EvaBodyPose.Sample pose)
    {
        var profile=CombatBodyProfiles.get(eva);if(profile==null)return EvaBodyPose.carrierVerticesR40(eva,pose);
        var points=new ArrayList<Vec3>();
        for(var element:profile.definition().getAsJsonArray("bodies"))
        {
            var row=element.getAsJsonObject();String n=row.get("name").getAsString();if(!pose.rig.containsKey(n))continue;
            var transform=pose.matrix(n);var bind=matrix(row.getAsJsonArray("bind"));
            for(var hull:row.getAsJsonArray("hulls"))for(var vertex:hull.getAsJsonArray())
            {
                var p=bind.transformPosition(CombatBodyProfiles.vector(vertex.getAsJsonArray())).div(CombatBodyProfiles.MODEL_TO_PHYSICS);
                transform.transformPosition(p).mul(EvaScale.RENDER_SCALE);points.add(new Vec3(p.x,p.y,p.z));
            }
        }
        return points;
    }

    private static ConvexHullShape shape(List<Vec3> vertices)
    {
        var points=new ObjectArrayList<javax.vecmath.Vector3f>();
        for(var p:vertices)points.add(new javax.vecmath.Vector3f((float)p.x*SCALE,(float)p.y*SCALE,(float)p.z*SCALE));
        var shape=new ConvexHullShape(points);shape.setMargin(.003F);return shape;
    }

    /** Standalone geometry entry used by the regression tests. */
    public static boolean obstructed(List<Vec3> vertices,AABB obstacle,double rise)
    {return obstructed(shape(vertices),obstacle,new Vec3(0,rise,0));}
    public static boolean obstructed(List<Vec3> vertices,AABB obstacle,Vec3 delta)
    {return obstructed(shape(vertices),obstacle,delta);}
    public static boolean obstructedCompound(List<List<Vec3>> hulls,AABB obstacle,Vec3 delta)
    {for(var hull:hulls)if(obstructed(shape(hull),obstacle,delta))return true;return false;}

    private static boolean obstructed(ConvexHullShape body,AABB obstacle,Vec3 delta)
    {
        var solid=new BoxShape(new javax.vecmath.Vector3f((float)obstacle.getXsize()*SCALE*.5F,
                (float)obstacle.getYsize()*SCALE*.5F,(float)obstacle.getZsize()*SCALE*.5F));
        solid.setMargin(.001F);
        var from=new Transform();from.setIdentity();var to=new Transform(from);
        to.origin.set((float)delta.x*SCALE,(float)delta.y*SCALE,(float)delta.z*SCALE);
        var block=new Transform();block.setIdentity();var centre=obstacle.getCenter();
        block.origin.set((float)centre.x*SCALE,(float)centre.y*SCALE,(float)centre.z*SCALE);
        var simplex=new VoronoiSimplexSolver();var detector=new GjkPairDetector();
        detector.init(body,solid,simplex,new GjkEpaPenetrationDepthSolver());
        var input=new DiscreteCollisionDetectorInterface.ClosestPointInput();input.init();
        input.transformA.set(from);input.transformB.set(block);var initial=new PointCollector();
        detector.getClosestPoints(input,initial,null);
        if(!initial.hasResult)return true;
        if(initial.distance<.0041F)
        {
            double separation=initial.normalOnBInWorld.x*delta.x+initial.normalOnBInWorld.y*delta.y+initial.normalOnBInWorld.z*delta.z;
            if(separation>1e-7)return false;
            if(initial.distance>-.0041F&&initial.normalOnBInWorld.y>.9F&&delta.y>=0)return false;
            if(initial.distance<-.001F)return true;
        }
        var result=new ConvexCast.CastResult();result.allowedPenetration=0;
        return new GjkConvexCast(body,solid,new VoronoiSimplexSolver())
                .calcTimeOfImpact(from,to,block,block,result);
    }

    /** Null retains the old conservative fallback when no measured rig exists. */
    static Boolean clear(ServerLevel level,EvaUnit01Entity eva,EvaBodyPose.Sample pose,
                         float pitch,float yaw,double rise)
    {return clearAt(level,eva,pose,pitch,yaw,eva.position(),rise);}
    static Boolean clearAt(ServerLevel level,EvaUnit01Entity eva,EvaBodyPose.Sample pose,
                           float pitch,float yaw,Vec3 origin,double rise)
    {return clearTranslationAt(level,eva,pose,pitch,yaw,origin,new Vec3(0,rise,0));}
    static Boolean clearTranslationAt(ServerLevel level,EvaUnit01Entity eva,EvaBodyPose.Sample pose,
                                     float pitch,float yaw,Vec3 origin,Vec3 delta)
    {
        var profile=CombatBodyProfiles.get(eva);if(profile==null)return null;
        var parts=new ArrayList<Part>();float heading=(float)Math.toRadians(180-yaw);
        for(var entry:profile.definition().getAsJsonArray("bodies"))
        {
            var row=entry.getAsJsonObject();String name=row.get("name").getAsString();
            if(!pose.rig.containsKey(name)||!row.has("hulls")||row.getAsJsonArray("hulls").isEmpty())return null;
            var bind=matrix(row.getAsJsonArray("bind"));var deformation=pose.matrix(name);
            int piece=0;
            for(var hull:row.getAsJsonArray("hulls"))
            {
                var vertices=new ArrayList<Vec3>();AABB bounds=null;
                for(var vertex:hull.getAsJsonArray())
                {
                    var p=bind.transformPosition(CombatBodyProfiles.vector(vertex.getAsJsonArray())).div(CombatBodyProfiles.MODEL_TO_PHYSICS);
                    deformation.transformPosition(p).mul(EvaScale.RENDER_SCALE);
                    Vec3 local=new Vec3(p.x,p.y,p.z);
                    if(EvaAirTransportR31.active(eva))p.set(EvaAirTransportR31.transformLocal(eva,local,pitch));
                    p.rotateY(heading);
                    local=new Vec3(p.x,p.y,p.z);vertices.add(local);
                    var point=new AABB(local,local);bounds=bounds==null?point:bounds.minmax(point);
                }
                if(vertices.size()<4)return null;
                // The upper torso is a compound of chest and shoulder shells.
                // Joining their vertices would fill the gaps between armour.
                parts.add(new Part(name+"#"+piece++,shape(vertices),bounds.inflate(.10)));
            }
        }
        for(var part:parts)
        {
            var sweep=part.bounds().expandTowards(delta).move(origin);
            for(var collision:level.getBlockCollisions(eva,sweep))for(var obstacle:collision.toAabbs())
            {
                if(!obstacle.intersects(sweep))continue;
                if(obstructed(part.shape(),obstacle.move(origin.scale(-1)),delta))
                {
                    if("r40-airlift".equals(System.getProperty("projectseele.regionalBuild","")))
                    {
                        var seen=REPORTED.computeIfAbsent(level,k->new HashMap<>());if(seen.size()>512)seen.clear();
                        String key=part.name()+net.minecraft.core.BlockPos.containing(origin)+obstacle.toString();long now=level.getGameTime();
                        if(now-seen.getOrDefault(key,Long.MIN_VALUE/2)>100)
                        {seen.put(key,now);com.projectseele.ProjectSeele.LOGGER.info("R40 convex carrier obstruction: part={} root={} delta={} yaw={} obstacle={}",part.name(),origin,delta,yaw,obstacle);}
                    }
                    return false;
                }
            }
        }
        return true;
    }
    private VerticalCarrierSweepR40(){}
}

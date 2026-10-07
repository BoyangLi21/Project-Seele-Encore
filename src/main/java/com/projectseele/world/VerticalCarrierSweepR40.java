package com.projectseele.world;

import com.bulletphysics.collision.narrowphase.*;
import com.bulletphysics.collision.shapes.*;
import com.bulletphysics.linearmath.Transform;
import com.bulletphysics.util.ObjectArrayList;
import com.projectseele.entity.*;
import com.projectseele.physics.CombatBodyProfiles;
import com.google.gson.JsonArray;
import java.lang.ref.WeakReference;
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
    private static final class MeasuredHull extends ConvexHullShape
    {
        final CarrierSupportEscapeR50 support;
        MeasuredHull(ObjectArrayList<javax.vecmath.Vector3f> points,List<Vec3> vertices)
        {super(points);support=new CarrierSupportEscapeR50(vertices);}
    }
    private static final Map<ServerLevel,Map<String,Long>> REPORTED=new WeakHashMap<>();
    private static final int CACHE_INSTANCES=6;
    private record CachedParts(WeakReference<EvaUnit01Entity> owner,CombatBodyProfiles.Profile profile,
                               JsonArray bodies,int[] state,List<Part> parts) {}
    // One exact geometry per real instance; no world positions, obstacles or
    // collision results are retained. Values do not retain their level/entity.
    private static final Map<ServerLevel,Map<UUID,CachedParts>> LOCAL_PARTS=new WeakHashMap<>();
    private static Map<UUID,CachedParts> localCache(ServerLevel level)
    {
        return LOCAL_PARTS.computeIfAbsent(level,ignored->new LinkedHashMap<UUID,CachedParts>(8,.75F,true)
        {
            @Override protected boolean removeEldestEntry(Map.Entry<UUID,CachedParts> entry)
            {return size()>CACHE_INSTANCES;}
        });
    }
    private static boolean sameDefinition(com.google.gson.JsonElement a,com.google.gson.JsonElement b)
    {
        if(a==b)return true;
        if(a==null||b==null||a.getClass()!=b.getClass())return false;
        if(a.isJsonPrimitive())
        {
            var x=a.getAsJsonPrimitive();var y=b.getAsJsonPrimitive();
            if(x.isNumber()&&y.isNumber())return Double.doubleToRawLongBits(x.getAsDouble())
                    ==Double.doubleToRawLongBits(y.getAsDouble());
            return x.equals(y);
        }
        if(a.isJsonArray())
        {
            var x=a.getAsJsonArray();var y=b.getAsJsonArray();if(x.size()!=y.size())return false;
            for(int n=0;n<x.size();n++)if(!sameDefinition(x.get(n),y.get(n)))return false;
            return true;
        }
        if(a.isJsonObject())
        {
            var x=a.getAsJsonObject();var y=b.getAsJsonObject();if(!x.keySet().equals(y.keySet()))return false;
            for(var entry:x.entrySet())if(!sameDefinition(entry.getValue(),y.get(entry.getKey())))return false;
            return true;
        }
        return a.equals(b);
    }

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
        // This is a clearance query, not the simulation's contact skin. The
        // old .003 physics-unit margin inflated limbs by 7.5 cm and produced
        // false penetration at a real fallen foot beside a platform corner.
        var shape=new MeasuredHull(points,vertices);shape.setMargin(.001F*SCALE);return shape;
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
            if(body instanceof MeasuredHull measured&&CarrierSupportEscapeR50.pureUp(delta))
            {
                if(measured.support.separatesUp(obstacle,delta))return false;
                if(initial.distance<=0)return true;
            }
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
        var bodies=profile.definition().getAsJsonArray("bodies");
        var deformations=new ArrayList<Matrix4f>(bodies.size());
        // All resolved body matrices include the complete effective pose and
        // its ancestors. Raw float bits preserve even sub-frame differences.
        int[] state=new int[14+17*bodies.size()];int at=0;
        state[at++]=Float.floatToRawIntBits(pitch);state[at++]=Float.floatToRawIntBits(yaw);
        boolean airborne=EvaAirTransportR31.active(eva);state[at++]=airborne?1:0;
        var frame=airborne?EvaAirTransportR31.cradleStateR50(eva):null;
        state[at++]=frame!=null&&frame.getBoolean("Adaptive")?1:0;
        for(String channel:List.of("HipX","HipY","HipZ","TurnX","TurnY","TurnZ","TurnW"))
            state[at++]=Float.floatToRawIntBits(frame==null?0:frame.getFloat(channel));
        state[at++]=Float.floatToRawIntBits(EvaScale.RENDER_SCALE);
        state[at++]=Float.floatToRawIntBits(CombatBodyProfiles.MODEL_TO_PHYSICS);
        state[at++]=Float.floatToRawIntBits(SCALE);
        float[] values=new float[16];
        for(var entry:bodies)
        {
            var row=entry.getAsJsonObject();String name=row.get("name").getAsString();
            if(!pose.rig.containsKey(name)||!row.has("hulls")||row.getAsJsonArray("hulls").isEmpty())return null;
            var deformation=pose.matrix(name);deformations.add(deformation);deformation.get(values);
            state[at++]=deformation.properties();
            for(float value:values)state[at++]=Float.floatToRawIntBits(value);
        }
        var cache=localCache(level);var previous=cache.get(eva.getUUID());List<Part> parts;
        if(previous!=null&&previous.owner().get()==eva&&previous.profile()==profile
                &&Arrays.equals(previous.state(),state)&&sameDefinition(previous.bodies(),bodies))parts=previous.parts();
        else
        {
            var rebuilt=new ArrayList<Part>();float heading=(float)Math.toRadians(180-yaw);int bodyIndex=0;
            for(var entry:bodies)
            {
                var row=entry.getAsJsonObject();String name=row.get("name").getAsString();
                var bind=matrix(row.getAsJsonArray("bind"));var deformation=deformations.get(bodyIndex++);
                int piece=0;
                for(var hull:row.getAsJsonArray("hulls"))
                {
                    var vertices=new ArrayList<Vec3>();AABB bounds=null;
                    for(var vertex:hull.getAsJsonArray())
                    {
                        var p=bind.transformPosition(CombatBodyProfiles.vector(vertex.getAsJsonArray())).div(CombatBodyProfiles.MODEL_TO_PHYSICS);
                        deformation.transformPosition(p).mul(EvaScale.RENDER_SCALE);
                        Vec3 local=new Vec3(p.x,p.y,p.z);
                        if(airborne)p.set(EvaAirTransportR31.transformLocal(eva,local,pitch));
                        p.rotateY(heading);
                        local=new Vec3(p.x,p.y,p.z);vertices.add(local);
                        var point=new AABB(local,local);bounds=bounds==null?point:bounds.minmax(point);
                    }
                    if(vertices.size()<4)return null;
                    // The upper torso is a compound of chest and shoulder shells.
                    // Joining their vertices would fill the gaps between armour.
                    rebuilt.add(new Part(name+"#"+piece++,shape(vertices),bounds.inflate(.10)));
                }
            }
            parts=List.copyOf(rebuilt);
            cache.put(eva.getUUID(),new CachedParts(new WeakReference<>(eva),profile,bodies.deepCopy(),state,parts));
        }
        for(var part:parts)
        {
            var sweep=part.bounds().expandTowards(delta).move(origin);
            for(var collision:level.getBlockCollisions(eva,sweep))for(var obstacle:collision.toAabbs())
            {
                if(!obstacle.intersects(sweep))continue;
                if(obstructed(part.shape(),obstacle.move(origin.scale(-1)),delta))
                {
                    // First real obstruction is diagnostic in ordinary play too;
                    // a repeated blocked frame must not fill the server log.
                    {
                        var seen=REPORTED.computeIfAbsent(level,k->new HashMap<>());if(seen.size()>512)seen.clear();
                        String key=eva.getUUID()+":"+part.name()+":"+obstacle;long now=level.getGameTime();
                        if(!seen.containsKey(key))
                        {seen.put(key,now);com.projectseele.ProjectSeele.LOGGER.info("Carrier obstruction: eva={} part={} root={} delta={} yaw={} obstacle={}",eva.getUUID(),part.name(),origin,delta,yaw,obstacle);}
                    }
                    return false;
                }
            }
        }
        return true;
    }
    private VerticalCarrierSweepR40(){}
}

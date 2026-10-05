package com.projectseele.physics;

import com.projectseele.entity.*;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import org.joml.Vector4f;
import java.util.*;

/** Sweeps against posed body surfaces after Minecraft's coarse candidate query. */
public final class CombatBodyContacts
{
    private record Part(String bone,Matrix4f bind,List<float[][]> hulls,List<Vector3f> vertices) {}
    private static final Map<String,List<Part>> CACHE=new java.util.concurrent.ConcurrentHashMap<>();
    private static List<Part> parts(CombatBodyProfiles.Profile profile)
    {
        return CACHE.computeIfAbsent(profile.key(),key->{
            List<Part> parts=new ArrayList<>();
            for(var element:profile.definition().getAsJsonArray("bodies"))
            {
                var row=element.getAsJsonObject();float[] a=new float[16];for(int i=0;i<16;i++)a[i]=row.getAsJsonArray("bind").get(i).getAsFloat();
                Matrix4f bind=new Matrix4f().set(a).transpose();List<float[][]> hulls=new ArrayList<>();
                if(row.has("hull_planes"))for(var hull:row.getAsJsonArray("hull_planes"))
                {
                    var planes=hull.getAsJsonArray();float[][] values=new float[planes.size()][4];
                    for(int i=0;i<values.length;i++)for(int j=0;j<4;j++)values[i][j]=planes.get(i).getAsJsonArray().get(j).getAsFloat();hulls.add(values);
                }
                if(hulls.isEmpty())
                {
                    var size=row.getAsJsonArray("size");float x=size.get(0).getAsFloat(),y=row.get("shape").getAsString().equals("box")?size.get(1).getAsFloat():size.get(1).getAsFloat()*.5F+x,z=size.size()>2?size.get(2).getAsFloat():x;
                    hulls.add(new float[][]{{1,0,0,-x},{-1,0,0,-x},{0,1,0,-y},{0,-1,0,-y},{0,0,1,-z},{0,0,-1,-z}});
                }
                List<Vector3f> vertices=new ArrayList<>();
                if(row.has("hulls"))for(var hull:row.getAsJsonArray("hulls"))for(var vertex:hull.getAsJsonArray())vertices.add(CombatBodyProfiles.vector(vertex.getAsJsonArray()));
                parts.add(new Part(row.get("name").getAsString(),bind,hulls,List.copyOf(vertices)));
            }return List.copyOf(parts);
        });
    }
    public static double torsoFrontage(LivingEntity actor,Vec3 toward)
    {
        var profile=CombatBodyProfiles.get(actor);if(profile==null)return Double.NaN;
        var pose=CombatBodyDynamics.raw(actor,0);
        double current=frontage(actor,toward,profile,pose);
        // Reserve the trunk space of the committed contact pose before a
        // lunge. Checking only today's guard pose let the next shoulder/head
        // animation grow through the opponent after both roots had stopped.
        if(actor instanceof EvaUnit01Entity eva)
        {
            var next=EvaGameplayMotionR32.committedContactPose(eva);
            if(next!=null)current=Math.max(current,frontage(actor,toward,profile,next));
        }
        else if(actor instanceof SachielEntity angel&&SachielGameplayMotionR32.phrases()&&angel.isStrikeActive())
            current=Math.max(current,frontage(actor,toward,profile,SachielGameplayMotionR32.pose(angel,SachielStrike.contactStart(angel.strikeMode())+2)));
        return current;
    }
    private static double frontage(LivingEntity actor,Vec3 toward,CombatBodyProfiles.Profile profile,EvaBodyPose.Sample pose)
    {
        var matrices=CombatBodyProfiles.physicalMatrices(pose,profile);
        var direction=toward.toVector3f().rotateY(-(180-actor.getYRot())*(float)Math.PI/180);float reach=Float.NEGATIVE_INFINITY;
        for(var part:parts(profile))if(part.bone.startsWith("torso_")||part.bone.equals("head"))
        {
            var matrix=new Matrix4f(matrices.get(part.bone)).mul(part.bind);
            for(var vertex:part.vertices)reach=Math.max(reach,matrix.transformPosition(new Vector3f(vertex)).dot(direction));
        }
        return Float.isFinite(reach)?Math.max(0,reach/CombatBodyProfiles.BLOCK_TO_PHYSICS):Double.NaN;
    }
    public static Vec3 strikeAim(LivingEntity attacker,LivingEntity target)
    {
        if(ShamshelPosedContactsR48.supports(target))return ShamshelPosedContactsR48.nearestSurfacePoint(target,attacker.getEyePosition());
        Vec3 centre=target.getBoundingBox().getCenter();var profile=CombatBodyProfiles.get(target);
        if(profile!=null)
        {
            var pose=CombatBodyDynamics.active(target)?CombatBodyDynamics.sample(target,0):CombatBodyDynamics.raw(target,0);
            for(var part:parts(profile))if(part.bone.equals("torso_upper"))
            {
                var transform=new Matrix4f(CombatBodyProfiles.physicalMatrices(pose,profile).get(part.bone)).mul(part.bind);
                var point=transform.getTranslation(new Vector3f()).div(CombatBodyProfiles.BLOCK_TO_PHYSICS).rotateY((180-target.getYRot())*(float)Math.PI/180);
                centre=target.position().add(point.x,point.y,point.z);break;
            }
        }
        Vec3 direction=target.position().subtract(attacker.position()).multiply(1,0,1).normalize();
        return clip(target,centre.subtract(direction.scale(70)),centre,.2).orElse(centre).add(direction.scale(.65));
    }
    /** A downward strike aims at the posed surface nearest its actual foot. */
    public static Vec3 bearingAim(LivingEntity target,Vec3 foot)
    {
        if(ShamshelPosedContactsR48.supports(target))return ShamshelPosedContactsR48.nearestSurfacePoint(target,foot);
        var profile=CombatBodyProfiles.get(target);if(profile==null)return target.getBoundingBox().getCenter();
        var pose=CombatBodyDynamics.active(target)?CombatBodyDynamics.sample(target,0):CombatBodyDynamics.raw(target,0);
        var matrices=CombatBodyProfiles.physicalMatrices(pose,profile);double best=Double.POSITIVE_INFINITY;Vec3 nearest=null;
        float yaw=(180-target.getYRot())*(float)Math.PI/180;
        for(var part:parts(profile))
        {
            var matrix=new Matrix4f(matrices.get(part.bone)).mul(part.bind);
            for(var vertex:part.vertices)
            {
                var local=matrix.transformPosition(new Vector3f(vertex)).div(CombatBodyProfiles.BLOCK_TO_PHYSICS).rotateY(yaw);
                var point=target.position().add(local.x,local.y,local.z);double distance=point.distanceToSqr(foot);
                if(distance<best){best=distance;nearest=point;}
            }
        }
        if(nearest==null)return target.getBoundingBox().getCenter();
        return clip(target,nearest.add(0,80,0),nearest.add(0,-4,0),.05).orElse(nearest).add(0,-.25,0);
    }
    public static Vector3f soleLocal(LivingEntity actor,EvaBodyPose.Sample pose,String side)
    {
        String name="foot_"+side;var profile=CombatBodyProfiles.get(actor);
        var fallback=pose.matrix(name).transformPosition(new Vector3f(pose.rig.get(name).pivot()));
        if(profile==null)return fallback;
        for(var part:parts(profile))if(part.bone.equals(name)&&!part.vertices.isEmpty())
        {
            var matrix=new Matrix4f(CombatBodyProfiles.physicalMatrices(pose,profile).get(name)).mul(part.bind);
            float low=Float.POSITIVE_INFINITY;
            for(var vertex:part.vertices)low=Math.min(low,matrix.transformPosition(new Vector3f(vertex)).y);
            Vector3f total=new Vector3f();int count=0;
            for(var vertex:part.vertices)
            {
                var point=matrix.transformPosition(new Vector3f(vertex));
                if(point.y<=low+.005F){total.add(point);count++;}
            }
            return total.div(count*CombatBodyProfiles.MODEL_TO_PHYSICS);
        }
        return fallback;
    }
    public static Optional<Vec3> clip(LivingEntity target,Vec3 from,Vec3 to,double radius)
    {
        if(ShamshelPosedContactsR48.supports(target))return ShamshelPosedContactsR48.clip(target,from,to,radius);
        var profile=CombatBodyProfiles.get(target);
        boolean field=target instanceof Angel angel&&angel.getAtField()>0||target instanceof EvaUnit01Entity eva&&eva.isAtFieldOn()&&eva.getAtFieldEnergy()>0;
        if(field||profile==null||!(target instanceof EvaUnit01Entity||target instanceof SachielEntity))
        {var box=target.getBoundingBox().inflate(radius);return box.contains(from)?Optional.of(from):box.clip(from,to);}
        var pose=CombatBodyDynamics.active(target)?CombatBodyDynamics.sample(target,0):CombatBodyDynamics.raw(target,0);
        AnatomicalLimbConstraints.apply(pose,profile);var matrices=CombatBodyProfiles.physicalMatrices(pose,profile);
        float angle=-(180-target.getYRot())*(float)Math.PI/180,scale=CombatBodyProfiles.BLOCK_TO_PHYSICS;
        Vector3f start=from.subtract(target.position()).toVector3f().rotateY(angle).mul(scale),end=to.subtract(target.position()).toVector3f().rotateY(angle).mul(scale);
        float best=Float.POSITIVE_INFINITY;
        for(var part:parts(profile))
        {
            Matrix4f inverse=new Matrix4f(matrices.get(part.bone)).mul(part.bind).invert();Vector3f p=inverse.transformPosition(new Vector3f(start)),q=inverse.transformPosition(new Vector3f(end));
            for(var hull:part.hulls)
            {
                float enter=0,leave=Math.min(1,best);boolean miss=false;
                for(var plane:hull)
                {
                    float a=plane[0]*p.x+plane[1]*p.y+plane[2]*p.z+plane[3]-(float)radius*scale;
                    float b=plane[0]*q.x+plane[1]*q.y+plane[2]*q.z+plane[3]-(float)radius*scale;
                    if(a>0&&b>0){miss=true;break;}if(a<=0&&b<=0)continue;
                    float t=a/(a-b);if(a>0)enter=Math.max(enter,t);else leave=Math.min(leave,t);
                    if(enter>leave){miss=true;break;}
                }
                if(!miss&&enter<=leave)best=Math.min(best,enter);
            }
        }
        return Float.isFinite(best)?Optional.of(from.lerp(to,best)):Optional.empty();
    }
    /** Two triangles cover the entire previous/current blade strip, not only its tip path. */
    public static Optional<Vec3> clipBladeSweepR45(LivingEntity target,Vec3 a,Vec3 b,Vec3 c,Vec3 d,double radius)
    {
        if(ShamshelPosedContactsR48.supports(target))return ShamshelPosedContactsR48.clipBladeSweep(target,a,b,c,d,radius);
        var profile=CombatBodyProfiles.get(target);
        if(fieldOrBox(target,profile))return clipBladeBoxR45(target.getBoundingBox().inflate(radius),a,b,c,d);
        var pose=CombatBodyDynamics.active(target)?CombatBodyDynamics.sample(target,0):CombatBodyDynamics.raw(target,0);
        AnatomicalLimbConstraints.apply(pose,profile);var matrices=CombatBodyProfiles.physicalMatrices(pose,profile);
        float angle=-(180-target.getYRot())*(float)Math.PI/180,scale=CombatBodyProfiles.BLOCK_TO_PHYSICS;
        Vec3[] world={a,b,c,d};Vector3f[] points=new Vector3f[4];
        for(int i=0;i<4;i++)points[i]=world[i].subtract(target.position()).toVector3f().rotateY(angle).mul(scale);
        for(var part:parts(profile))
        {
            var inverse=new Matrix4f(matrices.get(part.bone)).mul(part.bind).invert();
            Vector3f[] local=new Vector3f[4];for(int i=0;i<4;i++)local[i]=inverse.transformPosition(new Vector3f(points[i]));
            for(var hull:part.hulls)
            {
                double[][] planes=new double[hull.length][4];
                for(int i=0;i<hull.length;i++)planes[i]=new double[]{hull[i][0],hull[i][1],hull[i][2],hull[i][3]-radius*scale};
                for(int[] tri:new int[][]{{0,1,2},{0,2,3}})
                {
                    double[][] vertices=new double[3][3];for(int i=0;i<3;i++){var v=local[tri[i]];vertices[i]=new double[]{v.x,v.y,v.z};}
                    var hit=com.projectseele.combat.BladeSweepClipR45.triangle(vertices,planes);if(hit==null)continue;
                    var point=inverse.invert(new Matrix4f()).transformPosition(new Vector3f((float)hit[0],(float)hit[1],(float)hit[2]));
                    point.div(scale).rotateY(-angle).add(target.position().toVector3f());
                    return Optional.of(new Vec3(point.x,point.y,point.z));
                }
            }
        }
        return Optional.empty();
    }
    public static Optional<Vec3> clipBladeBoxR45(net.minecraft.world.phys.AABB box,Vec3 a,Vec3 b,Vec3 c,Vec3 d)
    {
        double[][] planes={{1,0,0,-box.maxX},{-1,0,0,box.minX},{0,1,0,-box.maxY},
                {0,-1,0,box.minY},{0,0,1,-box.maxZ},{0,0,-1,box.minZ}};
        Vec3[] p={a,b,c,d};
        for(int[] tri:new int[][]{{0,1,2},{0,2,3}})
        {
            double[][] points=new double[3][3];for(int i=0;i<3;i++){var v=p[tri[i]];points[i]=new double[]{v.x,v.y,v.z};}
            var hit=com.projectseele.combat.BladeSweepClipR45.triangle(points,planes);
            if(hit!=null)return Optional.of(new Vec3(hit[0],hit[1],hit[2]));
        }
        return Optional.empty();
    }
    private static boolean fieldOrBox(LivingEntity target,CombatBodyProfiles.Profile profile)
    {
        return profile==null||!(target instanceof EvaUnit01Entity||target instanceof SachielEntity)
                ||target instanceof Angel angel&&angel.getAtField()>0
                ||target instanceof EvaUnit01Entity eva&&eva.isAtFieldOn()&&eva.getAtFieldEnergy()>0;
    }
    private static Matrix4f worldPart(LivingEntity target,Map<String,Matrix4f> matrices,Part part)
    {
        return new Matrix4f().translation(target.position().toVector3f())
                .rotateY((180-target.getYRot())*(float)Math.PI/180).scale(1/CombatBodyProfiles.BLOCK_TO_PHYSICS)
                .mul(matrices.get(part.bone)).mul(part.bind);
    }
    private static Vector3f project(Vector3f point,float[][] planes,int passes,boolean closest)
    {
        Vector3f value=new Vector3f(point);float[][] correction=closest?new float[planes.length][3]:null;
        for(int pass=0;pass<passes;pass++)
        {
            float movement=0;
            for(int i=0;i<planes.length;i++)
            {
                var plane=planes[i];float x=value.x,y=value.y,z=value.z;
                if(closest){x+=correction[i][0];y+=correction[i][1];z+=correction[i][2];}
                float norm=plane[0]*plane[0]+plane[1]*plane[1]+plane[2]*plane[2];
                float outside=plane[0]*x+plane[1]*y+plane[2]*z+plane[3];
                float step=norm<1e-12F?0:Math.max(0,outside)/norm;
                float nx=x-plane[0]*step,ny=y-plane[1]*step,nz=z-plane[2]*step;
                if(closest){correction[i][0]=x-nx;correction[i][1]=y-ny;correction[i][2]=z-nz;}
                movement=Math.max(movement,value.distanceSquared(nx,ny,nz));value.set(nx,ny,nz);
            }
            if(movement<1e-12F)break;
        }
        return value;
    }
    private static boolean inside(Vector3f point,float[][] planes)
    {
        for(var plane:planes)
            if(plane[0]*point.x+plane[1]*point.y+plane[2]*point.z+plane[3]>2e-5F)return false;
        return true;
    }
    /** Volume attacks intersect posed convex parts, never only a standing box. */
    public static boolean overlap(LivingEntity target,net.minecraft.world.phys.AABB area)
    {
        if(ShamshelPosedContactsR48.supports(target))return ShamshelPosedContactsR48.overlap(target,area);
        var profile=CombatBodyProfiles.get(target);if(fieldOrBox(target,profile))return target.getBoundingBox().intersects(area);
        var pose=CombatBodyDynamics.active(target)?CombatBodyDynamics.sample(target,0):CombatBodyDynamics.raw(target,0);
        AnatomicalLimbConstraints.apply(pose,profile);var matrices=CombatBodyProfiles.physicalMatrices(pose,profile);
        Vector4f[] faces={new Vector4f(1,0,0,(float)-area.maxX),new Vector4f(-1,0,0,(float)area.minX),
                new Vector4f(0,1,0,(float)-area.maxY),new Vector4f(0,-1,0,(float)area.minY),
                new Vector4f(0,0,1,(float)-area.maxZ),new Vector4f(0,0,-1,(float)area.minZ)};
        for(var part:parts(profile))
        {
            var world=worldPart(target,matrices,part);var transpose=new Matrix4f(world).transpose();
            float[][] box=new float[6][4];
            for(int i=0;i<6;i++)
            {
                var plane=transpose.transform(new Vector4f(faces[i]));float norm=(float)Math.sqrt(plane.x*plane.x+plane.y*plane.y+plane.z*plane.z);
                box[i]=new float[]{plane.x/norm,plane.y/norm,plane.z/norm,plane.w/norm};
            }
            Vector3f centre=new Matrix4f(world).invert().transformPosition(area.getCenter().toVector3f());
            for(var hull:part.hulls)
            {
                float[][] both=new float[hull.length+6][];System.arraycopy(hull,0,both,0,hull.length);System.arraycopy(box,0,both,hull.length,6);
                var point=project(centre,both,64,false);if(inside(point,both))return true;
            }
        }
        return false;
    }
    /** The same attenuation curve uses the nearest real exposed body point. */
    public static Vec3 nearestSurfacePoint(LivingEntity target,Vec3 origin)
    {
        if(ShamshelPosedContactsR48.supports(target))return ShamshelPosedContactsR48.nearestSurfacePoint(target,origin);
        var profile=CombatBodyProfiles.get(target);
        if(fieldOrBox(target,profile))
        {
            var box=target.getBoundingBox();return new Vec3(net.minecraft.util.Mth.clamp(origin.x,box.minX,box.maxX),
                    net.minecraft.util.Mth.clamp(origin.y,box.minY,box.maxY),net.minecraft.util.Mth.clamp(origin.z,box.minZ,box.maxZ));
        }
        var pose=CombatBodyDynamics.active(target)?CombatBodyDynamics.sample(target,0):CombatBodyDynamics.raw(target,0);
        AnatomicalLimbConstraints.apply(pose,profile);var matrices=CombatBodyProfiles.physicalMatrices(pose,profile);
        Vec3 best=target.getBoundingBox().getCenter();double distance=Double.POSITIVE_INFINITY;
        for(var part:parts(profile))
        {
            var world=worldPart(target,matrices,part);var local=new Matrix4f(world).invert().transformPosition(origin.toVector3f());
            for(var vertex:part.vertices)
            {
                Vec3 candidate=new Vec3(world.transformPosition(new Vector3f(vertex)));double next=candidate.distanceToSqr(origin);
                if(next<distance){distance=next;best=candidate;}
            }
            for(var hull:part.hulls)
            {
                var point=project(local,hull,48,true);if(!inside(point,hull))continue;
                Vec3 candidate=new Vec3(world.transformPosition(point));double next=candidate.distanceToSqr(origin);
                if(next<distance){distance=next;best=candidate;}
            }
        }
        return best;
    }
    public static net.minecraft.world.phys.AABB coreBounds(LivingEntity actor)
    {
        var profile=CombatBodyProfiles.get(actor);if(profile==null)return actor.getBoundingBox();
        var pose=CombatBodyDynamics.active(actor)?CombatBodyDynamics.sample(actor,0):CombatBodyDynamics.raw(actor,0);
        var matrices=CombatBodyProfiles.physicalMatrices(pose,profile);net.minecraft.world.phys.AABB result=null;
        for(var part:parts(profile))if(part.bone.startsWith("torso_"))
        {
            var transform=new Matrix4f(matrices.get(part.bone)).mul(part.bind);
            for(var vertex:part.vertices)
            {
                var p=transform.transformPosition(new Vector3f(vertex)).div(CombatBodyProfiles.BLOCK_TO_PHYSICS).rotateY((180-actor.getYRot())*(float)Math.PI/180);
                var v=actor.position().add(p.x,p.y,p.z);var box=new net.minecraft.world.phys.AABB(v,v);result=result==null?box:result.minmax(box);
            }
        }
        return result==null?actor.getBoundingBox():result;
    }
    private CombatBodyContacts(){}
}

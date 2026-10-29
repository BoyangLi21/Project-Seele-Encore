package com.projectseele.entity;

import com.google.gson.*;
import net.minecraft.nbt.*;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** The normalized standalone original gun has one transform for rendering, muzzle, grips and native hull checks. */
public final class YashimaCannonGeometryR52
{
    /** Follow the target sector with aiming error space, without allowing the long barrel to overturn. */
    public static Quaternionf aimWithinSectorR54(Geometry g,Vec3 origin,Vec3 target,Vec3 centre)
    {
        var base=g.boreWorld(new Quaternionf());var pivot=g.point(origin,new Quaternionf(),g.pivot());
        var sector=centre==null?base:centre.subtract(pivot).normalize();
        if(sector.lengthSqr()<1e-8)sector=base;
        double yaw=Math.atan2(sector.x,sector.z),pitch=Math.asin(Math.max(-1,Math.min(1,sector.y)));
        var q=new Quaternionf().rotationTo(base.toVector3f(),sector.toVector3f());
        for(int i=0;i<8;i++)
        {
            var wanted=target.subtract(g.point(origin,q,g.muzzle())).normalize();
            if(wanted.lengthSqr()<1e-8)break;
            double delta=Math.atan2(Math.sin(Math.atan2(wanted.x,wanted.z)-yaw),Math.cos(Math.atan2(wanted.x,wanted.z)-yaw));
            double y=yaw+Math.max(-Math.toRadians(12),Math.min(Math.toRadians(12),delta));
            double p=pitch+Math.max(-Math.toRadians(8),Math.min(Math.toRadians(8),Math.asin(Math.max(-1,Math.min(1,wanted.y)))-pitch));
            q.rotationTo(base.toVector3f(),new Vector3f((float)(Math.sin(y)*Math.cos(p)),(float)Math.sin(p),(float)(Math.cos(y)*Math.cos(p)))).normalize();
        }
        return q;
    }
    public record Geometry(Vec3 translation,Quaternionf rotation,float scale,AABB bounds,Vec3 pivot,Vec3 bore,Vec3 muzzle,Vec3 left,Vec3 right)
    {
        public Matrix4f base(){return new Matrix4f().translation(translation.toVector3f()).rotate(rotation).scale(scale);}
        public Matrix4f matrix(Vec3 origin,Quaternionf aim)
        {
            var base=base();var center=base.transformPosition(pivot.toVector3f());
            return new Matrix4f().translation(origin.toVector3f()).translate(center).rotate(aim).translate(-center.x,-center.y,-center.z).mul(base);
        }
        public Vec3 point(Vec3 origin,Quaternionf aim,Vec3 local){return new Vec3(matrix(origin,aim).transformPosition(local.toVector3f()));}
        public Vec3 boreWorld(Quaternionf aim){return new Vec3(aim.transform(base().transformDirection(bore.toVector3f()).normalize())).normalize();}
        public AABB worldBounds(Vec3 origin,Quaternionf aim)
        {
            var matrix=matrix(origin,aim);AABB out=null;
            for(double x:new double[]{bounds.minX,bounds.maxX})for(double y:new double[]{bounds.minY,bounds.maxY})for(double z:new double[]{bounds.minZ,bounds.maxZ})
            {var p=new Vec3(matrix.transformPosition(new Vector3f((float)x,(float)y,(float)z)));var box=new AABB(p,p);out=out==null?box:out.minmax(box);}
            return out;
        }
    }
    public static Vec3 vector(JsonArray a)
    {
        if(a==null||a.size()!=3)throw new IllegalArgumentException("Explicit cannon vector required");
        var v=new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());
        if(!Double.isFinite(v.lengthSqr()))throw new IllegalArgumentException("Non-finite cannon vector");return v;
    }
    public static Geometry parse(JsonObject root)
    {
        var frame=root.getAsJsonObject("mesh_frame");var q=frame.getAsJsonArray("quaternion_xyzw");
        if(q==null||q.size()!=4)throw new IllegalArgumentException("Measured cannon quaternion required");
        var rotation=new Quaternionf(q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());
        float scale=frame.get("scale").getAsFloat();var box=root.getAsJsonArray("bounds_local");
        if(!Float.isFinite(rotation.lengthSquared())||Math.abs(rotation.lengthSquared()-1)>.001||!Float.isFinite(scale)||scale<=0||scale>20||box==null||box.size()!=2)
            throw new IllegalArgumentException("Cannon mesh frame or complete bounds rejected");
        var min=vector(box.get(0).getAsJsonArray());var max=vector(box.get(1).getAsJsonArray());var bore=vector(root.getAsJsonArray("bore_local"));
        if(min.x>=max.x||min.y>=max.y||min.z>=max.z||Math.abs(bore.length()-1)>.001)throw new IllegalArgumentException("Cannon complete hull or bore rejected");
        var bounds=new AABB(min,max);Vec3 pivot=vector(root.getAsJsonArray("aim_pivot_local")),muzzle=vector(root.getAsJsonArray("muzzle_local")),left=vector(root.getAsJsonArray("grip_left_local")),right=vector(root.getAsJsonArray("grip_right_local"));
        if(!bounds.inflate(.01).contains(pivot)||!bounds.inflate(.1).contains(muzzle)||!bounds.inflate(.1).contains(left)||!bounds.inflate(.1).contains(right))
            throw new IllegalArgumentException("Cannon markers must belong to the complete original model");
        return new Geometry(vector(frame.getAsJsonArray("translation")),rotation.normalize(),scale,bounds,pivot,bore,muzzle,left,right);
    }
    public static CompoundTag encode(Geometry g)
    {
        var tag=new CompoundTag();put(tag,"translation",g.translation());put(tag,"min",new Vec3(g.bounds().minX,g.bounds().minY,g.bounds().minZ));put(tag,"max",new Vec3(g.bounds().maxX,g.bounds().maxY,g.bounds().maxZ));
        put(tag,"pivot",g.pivot());put(tag,"bore",g.bore());put(tag,"muzzle",g.muzzle());put(tag,"left",g.left());put(tag,"right",g.right());tag.putFloat("scale",g.scale());
        var q=new ListTag();for(float v:new float[]{g.rotation().x,g.rotation().y,g.rotation().z,g.rotation().w})q.add(FloatTag.valueOf(v));tag.put("rotation",q);return tag;
    }
    public static Geometry decode(CompoundTag tag)
    {var q=tag.getList("rotation",Tag.TAG_FLOAT);if(q.size()!=4)throw new IllegalArgumentException("Missing measured cannon frame");return new Geometry(get(tag,"translation"),new Quaternionf(q.getFloat(0),q.getFloat(1),q.getFloat(2),q.getFloat(3)),tag.getFloat("scale"),new AABB(get(tag,"min"),get(tag,"max")),get(tag,"pivot"),get(tag,"bore"),get(tag,"muzzle"),get(tag,"left"),get(tag,"right"));}
    private static void put(CompoundTag tag,String name,Vec3 v){var a=new ListTag();a.add(DoubleTag.valueOf(v.x));a.add(DoubleTag.valueOf(v.y));a.add(DoubleTag.valueOf(v.z));tag.put(name,a);}
    private static Vec3 get(CompoundTag tag,String name){var a=tag.getList(name,Tag.TAG_DOUBLE);if(a.size()!=3)throw new IllegalArgumentException("Incomplete cannon marker");return new Vec3(a.getDouble(0),a.getDouble(1),a.getDouble(2));}
    private YashimaCannonGeometryR52(){}
}

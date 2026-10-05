package com.projectseele.entity;

import com.google.gson.JsonParser;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Matrix3f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import net.minecraft.world.phys.AABB;
import java.util.Optional;
import java.util.List;
import java.util.ArrayList;

/** The displayed shield and beam interception share the fitted, actual hand frame. */
public final class EvaShieldRigR47
{
    private record Triangle(Vec3 a,Vec3 edge1,Vec3 edge2){}
    private record Attachment(Vector3f source,Vector3f target,Quaternionf rotation){}
    private record Surface(List<Triangle> triangles,Vec3 pivot,AABB bounds,Attachment attachment){}
    private static Surface surface;
    private static synchronized Surface surface()
    {
        if(surface!=null)return surface;
        try(var stream=EvaShieldRigR47.class.getResourceAsStream("/assets/projectseele/mesh/yashima_shield.mesh.json"))
        {
            if(stream==null)throw new IllegalStateException("Shield mesh is absent");
            var root=JsonParser.parseString(new String(stream.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
            var part=root.getAsJsonObject("parts").getAsJsonObject("shield");
            var vertices=part.getAsJsonArray("vertices");
            if(root.get("stride").getAsInt()!=8||vertices.size()%24!=0)throw new IllegalStateException("Invalid shield triangles");
            var pivot=part.getAsJsonArray("pivot");
            Vec3 origin=new Vec3(pivot.get(0).getAsDouble(),pivot.get(1).getAsDouble(),pivot.get(2).getAsDouble());
            var result=new ArrayList<Triangle>();
            double minX=Double.POSITIVE_INFINITY,minY=minX,minZ=minX;
            double maxX=Double.NEGATIVE_INFINITY,maxY=maxX,maxZ=maxX;
            for(int i=0;i<vertices.size();i+=24)
            {
                Vec3 a=new Vec3(vertices.get(i).getAsDouble(),vertices.get(i+1).getAsDouble(),vertices.get(i+2).getAsDouble());
                Vec3 b=new Vec3(vertices.get(i+8).getAsDouble(),vertices.get(i+9).getAsDouble(),vertices.get(i+10).getAsDouble());
                Vec3 c=new Vec3(vertices.get(i+16).getAsDouble(),vertices.get(i+17).getAsDouble(),vertices.get(i+18).getAsDouble());
                if(b.subtract(a).cross(c.subtract(a)).lengthSqr()>1e-16)result.add(new Triangle(a,b.subtract(a),c.subtract(a)));
                for(Vec3 point:List.of(a,b,c))
                {
                    minX=Math.min(minX,point.x);minY=Math.min(minY,point.y);minZ=Math.min(minZ,point.z);
                    maxX=Math.max(maxX,point.x);maxY=Math.max(maxY,point.y);maxZ=Math.max(maxZ,point.z);
                }
            }
            if(result.isEmpty())throw new IllegalStateException("Shield surface is empty");
            Attachment attachment=null;
            if(root.has("shield_attachment"))
            {
                var binding=root.getAsJsonObject("shield_attachment");
                if(!"hand_l".equals(binding.get("hand").getAsString()))throw new IllegalStateException("Shield hand mismatch");
                var source=binding.getAsJsonArray("source_handle_centre");
                var target=binding.getAsJsonArray("target_handle_centre");
                var rotation=binding.getAsJsonArray("rotation_column_major");
                if(source.size()!=3||target.size()!=3||rotation.size()!=9)throw new IllegalStateException("Incomplete shield attachment");
                var basis=new Matrix3f();
                for(int column=0;column<3;column++)basis.setColumn(column,new Vector3f(
                        rotation.get(column*3).getAsFloat(),rotation.get(column*3+1).getAsFloat(),rotation.get(column*3+2).getAsFloat()));
                attachment=new Attachment(new Vector3f(source.get(0).getAsFloat(),source.get(1).getAsFloat(),source.get(2).getAsFloat()),
                        new Vector3f(target.get(0).getAsFloat(),target.get(1).getAsFloat(),target.get(2).getAsFloat()),
                        new Quaternionf().setFromNormalized(basis).normalize());
            }
            return surface=new Surface(List.copyOf(result),origin,new AABB(minX,minY,minZ,maxX,maxY,maxZ),attachment);
        }
        catch(Exception error){throw new IllegalStateException("Shield surface is unavailable",error);}
    }
    public static boolean equipped(EvaUnit01Entity e)
    {
        return !e.isExperimentalUnit()&&e.getUnitVariant()==0&&e.getWeapon()==EvaUnit01Entity.WEAPON_SHIELD_R45
                &&(e.getArmamentMask()&EvaUnit01Entity.ARMAMENT_MASK_SHIELD_R45)!=0;
    }

    public static void attach(EvaUnit01Entity entity,EvaBodyPose.Sample body)
    {
        if(!equipped(entity))return;
        var attachment=surface().attachment();if(attachment==null)return;
        var socket=body.rig.get("shield");
        if(socket==null||!body.rig.containsKey("hand_l"))throw new IllegalStateException("Shield socket is absent from the actual rig");
        Matrix4f fitted=new Matrix4f(body.matrix("hand_l")).translate(attachment.target())
                .rotate(attachment.rotation()).translate(new Vector3f(attachment.source()).negate());
        Matrix4f parent=socket.parent()==null?new Matrix4f():new Matrix4f(body.matrix(socket.parent()));
        Matrix4f local=parent.invert().mul(fitted);
        body.rotations.put("shield",local.getUnnormalizedRotation(new Quaternionf()).normalize());
        body.positions.put("shield",local.transformPosition(new Vector3f(socket.pivot())).sub(socket.pivot()));body.dirty();
    }

    /** Carry the full-size plate upright, with the real rear handrail in the palm.
     * The library's generic shield hand is not calibrated to this tall rail. */
    public static void applyCarryR48(EvaUnit01Entity entity,EvaBodyPose.Sample body)
    {
        if(!equipped(entity)||entity.isNervLogisticsLocked()||entity.isFirstBattleActive()
                ||EvaShutdownR30.disabled(entity)||entity.hasLiveActionForRender(0))return;
        var attachment=surface().attachment();if(attachment==null)return;
        var physics=com.projectseele.physics.CombatBodyProfiles.get(entity);if(physics==null)return;
        String upper="arm_l",lower="forearm_l",hand="hand_l";
        var root=body.matrix("root");var forward=root.transformDirection(new Vector3f(0,0,-1));forward.y=0;
        if(forward.lengthSquared()<1e-8F)return;forward.normalize();
        var right=new Vector3f(forward).cross(new Vector3f(0,1,0)).normalize();
        var shieldRotation=new Quaternionf().setFromNormalized(new Matrix3f()
                .setColumn(0,right).setColumn(1,new Vector3f(0,1,0)).setColumn(2,new Vector3f(forward).negate()));
        var shoulder=body.matrix(upper).transformPosition(new Vector3f(body.rig.get(upper).pivot()));
        var other=body.matrix("arm_r").transformPosition(new Vector3f(body.rig.get("arm_r").pivot()));
        var rail=shoulder.lerp(other,.5F).fma(2F,forward);
        float minimumRail=attachment.source().y-(float)surface().bounds().minY/16F+.15F;
        rail.y=Math.max(minimumRail,rail.y-1.5F);
        var handRotation=new Quaternionf(shieldRotation).mul(new Quaternionf(attachment.rotation()).invert());
        var target=new Vector3f(rail).sub(handRotation.transform(new Vector3f(attachment.target()).sub(body.rig.get(hand).pivot())));
        var joint=com.projectseele.physics.AnatomicalLimbConstraints.elbowJoint(physics,"l",body.rig.get(lower).pivot());
        var upperWorld=body.matrix(upper).getUnnormalizedRotation(new Quaternionf()).normalize();
        var lowerWorld=body.matrix(lower).getUnnormalizedRotation(new Quaternionf()).normalize();
        var origin=body.matrix(upper).transformPosition(new Vector3f(body.rig.get(upper).pivot()));
        var middle=body.matrix(upper).transformPosition(new Vector3f(joint));
        var end=body.matrix(hand).transformPosition(new Vector3f(body.rig.get(hand).pivot()));
        var pole=new Vector3f(origin).fma(-.55F,right).add(0,-1.2F,.4F);
        var solved=com.projectseele.physics.AuthoredTwoBoneIKR45.solveWithPole(origin,middle,end,target,pole,new Vector3f(right));
        if(solved==null)return;
        upperWorld=solved.upperSwing().mul(upperWorld);lowerWorld=solved.lowerSwing().mul(lowerWorld);
        String parent=body.rig.get(upper).parent();
        body.rotations.put(upper,body.matrix(parent).getUnnormalizedRotation(new Quaternionf()).normalize().invert().mul(upperWorld));body.dirty();
        parent=body.rig.get(lower).parent();
        var localLower=body.matrix(parent).getUnnormalizedRotation(new Quaternionf()).normalize().invert().mul(lowerWorld);
        body.rotations.put(lower,localLower);
        body.positions.put(lower,com.projectseele.physics.AuthoredJointCentreR45.translation(new Vector3f(joint).sub(body.rig.get(lower).pivot()),localLower));body.dirty();
        parent=body.rig.get(hand).parent();
        body.rotations.put(hand,body.matrix(parent).getUnnormalizedRotation(new Quaternionf()).normalize().invert().mul(handRotation));body.dirty();
    }

    private static Vec3 local(Matrix4f inverse,Vec3 point,Vec3 pivot)
    {
        var p=inverse.transformPosition(point.toVector3f());
        return new Vec3(-p.x*16-pivot.x,p.y*16-pivot.y,p.z*16-pivot.z);
    }

    public static Optional<Vec3> intercept(EvaUnit01Entity e,Vec3 from,Vec3 to)
    {
        if(!equipped(e))return Optional.empty();
        var pose=EvaBodyPose.sample(e,0);if(!pose.rig.containsKey("shield"))return Optional.empty();
        var matrix=EvaRifleKinematics.world(e,0).mul(pose.matrix("shield"));
        var mesh=surface();matrix.invert();Vec3 start=local(matrix,from,mesh.pivot()),end=local(matrix,to,mesh.pivot()),direction=end.subtract(start);
        if(!mesh.bounds().contains(start)&&!mesh.bounds().contains(end)&&mesh.bounds().clip(start,end).isEmpty())return Optional.empty();
        double nearest=Double.POSITIVE_INFINITY;
        for(var triangle:mesh.triangles())
        {
            Vec3 cross=direction.cross(triangle.edge2());double determinant=triangle.edge1().dot(cross);
            if(Math.abs(determinant)<1e-10)continue;
            Vec3 offset=start.subtract(triangle.a());double u=offset.dot(cross)/determinant;
            if(u<0||u>1)continue;
            Vec3 q=offset.cross(triangle.edge1());double v=direction.dot(q)/determinant;
            if(v<0||u+v>1)continue;
            double t=triangle.edge2().dot(q)/determinant;
            if(t>=0&&t<=1&&t<nearest)nearest=t;
        }
        return Double.isFinite(nearest)?Optional.of(from.lerp(to,nearest)):Optional.empty();
    }

    private EvaShieldRigR47(){}
}

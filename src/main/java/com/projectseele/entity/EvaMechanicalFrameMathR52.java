package com.projectseele.entity;

import com.projectseele.world.EntryPlugKinematics;
import com.projectseele.world.RigidTransform;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Pure math shared by the production owner and original-rig checks; loading
 * it does not initialize entity registries or an application/world. */
public final class EvaMechanicalFrameMathR52
{
    public static Vec3 rootAfterNativeMove(Vec3 previousRoot,AABB before,AABB after)
    {return previousRoot.add(after.minX-before.minX,after.minY-before.minY,after.minZ-before.minZ);}
    public static RigidTransform emptySocket(EvaBodyPose.Sample body,Matrix4f world,EvaDorsalProfile.Profile profile)
    {
        var chest=new Matrix4f(world).mul(body.matrix("torso_upper"));var centre=profile.centreModel();var out=profile.outwardModel();var hinge=profile.hingeAxisModel();
        var p=chest.transformPosition(new Vector3f((float)-centre.x,(float)centre.y,(float)centre.z).div(16));
        var z=chest.transformDirection(new Vector3f((float)-out.x,(float)out.y,(float)out.z)).normalize();var y=chest.transformDirection(new Vector3f((float)-hinge.x,(float)hinge.y,(float)hinge.z)).normalize();
        var up=new Vec3(y.x,y.y,y.z);var outward=new Vec3(z.x,z.y,z.z);var socket=RigidTransform.fromAxes(new Vec3(p.x,p.y,p.z),up.cross(outward),up,outward);
        return socket.compose(RigidTransform.of(new Vec3(0,0,-EntryPlugKinematics.LOCK_DEPTH_BLOCKS),new Quaternionf()));
    }
    private EvaMechanicalFrameMathR52(){}
}

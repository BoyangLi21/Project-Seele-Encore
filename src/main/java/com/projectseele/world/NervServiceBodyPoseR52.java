package com.projectseele.world;
import com.projectseele.entity.*;
import com.projectseele.util.QuaternionChannelsR45;
import org.joml.Quaternionf;

/** Same bind-rest plus late dorsal channels as EvaLockedCagePoseR44 and
 * EvaDorsalPose. Used only for stationary mechanical service clearance. */
public final class NervServiceBodyPoseR52
{
    public static EvaBodyPose.Sample sample(EvaUnit01Entity e)
    {if(EvaMechanicalFrameR52.serviceSourceHeldR52(e))return EvaMechanicalFrameR52.serviceBodyR52(e);var body=EvaBodyPose.neutralForTransportR32(e);for(var bone:body.rig.values()){body.rotations.put(bone.name(),new Quaternionf(bone.bindRotation()));body.positions.get(bone.name()).zero();}return applyDorsal(body,EvaDorsalProfile.of(e),EvaDorsalMechanism.open(e),EvaDorsalMechanism.bow(e));}
    public static EvaBodyPose.Sample applyDorsal(EvaBodyPose.Sample body,EvaDorsalProfile.Profile profile,float open,float bow)
    {
        // The sampled and rendered head face -Z: negative X lowers both.
        var axis=profile.hingeAxisModel();if(body.rotations.containsKey("dorsal_cover"))body.rotations.put("dorsal_cover",new Quaternionf().rotationAxis((float)Math.toRadians(profile.openAngle()*open),(float)axis.x,(float)-axis.y,(float)-axis.z));
        if(open>=.0001F||bow>=.0001F){float weight=Math.max(open,bow);for(String n:new String[]{"root","torso_lower","torso_upper","neck","head"})if(body.rig.containsKey(n)){var a=QuaternionChannelsR45.euler(body.rotations.get(n));a.mul(1-weight);if(n.equals("head"))a.x-=.72F*bow;body.rotations.put(n,new Quaternionf().rotationZYX(a.z,a.y,a.x));body.positions.get(n).mul(1-weight);}}
        body.dirty();return body;
    }
    private NervServiceBodyPoseR52(){}
}

package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.entity.*;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.util.Mth;
import org.joml.Vector3f;

/** Six telescopic supports contact the current load before the receiving rack moves it. */
final class EvaGroundReceiverRendererR50
{
    static void render(PoseStack poses,MultiBufferSource buffers,int light,EvaUnit01Entity eva,float partial)
    {
        var pose=EvaBodyPose.sample(eva,partial);
        float yaw=(180-EvaAirTransportR31.frameYaw(eva,partial))*Mth.DEG_TO_RAD;
        float clamp=Mth.clamp(eva.carrierRiseProgress(partial),0,1);
        float deck=(float)(EvaAirTransportR31.cradleStateR50(eva).getDouble("GroundDeckY")-eva.getY());
        for(String bone:new String[]{"arm_l","arm_r","leg_l","leg_r","shin_l","shin_r"})
        {
            var target=pose.matrix(bone).transformPosition(new Vector3f(pose.rig.get(bone).pivot()).add(0,0,2.5F/EvaScale.RENDER_SCALE))
                    .mul(EvaScale.RENDER_SCALE).rotateY(yaw);
            var foot=new Vector3f(Mth.clamp(target.x,-13,13),deck-.4F,Mth.clamp(target.z,-10,10));
            var end=new Vector3f(foot).lerp(target,clamp);
            var collar=new Vector3f(foot).lerp(end,.58F);
            UNTransportRenderer.rod(poses,buffers,light,foot,collar,.48F,52);
            UNTransportRenderer.rod(poses,buffers,light,collar,end,.25F,160);
            UNTransportRenderer.rod(poses,buffers,light,new Vector3f(end).add(-1.5F,0,0),new Vector3f(end).add(1.5F,0,0),.65F,62);
            UNTransportRenderer.rod(poses,buffers,light,new Vector3f(foot).add(-1.2F,0,0),new Vector3f(foot).add(1.2F,0,0),.28F,45);
        }
    }
    private EvaGroundReceiverRendererR50() {}
}

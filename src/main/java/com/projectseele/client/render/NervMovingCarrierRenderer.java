package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.renderer.MultiBufferSource;

/** One rigid carrier assembly in exactly the same world frame as its EVA. */
public final class NervMovingCarrierRenderer
{
    public static void render(PoseStack poses,MultiBufferSource buffers,int light,EvaUnit01Entity unit,float partial)
    {
        TvFacilityMeshes.withBuffers(buffers,()->TvFacilityMeshes.carrier(poses,light,unit,partial));
        if(com.projectseele.visual.NervStaffR24Review.R26&&unit.getLaunchPhase()==EvaUnit01Entity.LAUNCH_CLEAR)
            com.projectseele.visual.NervStaffR24Review.rackRenderedDuringClosing=true;
    }
    private NervMovingCarrierRenderer() {}
}

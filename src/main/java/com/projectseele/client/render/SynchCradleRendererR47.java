package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaScale;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;

final class SynchCradleRendererR47
{
    static boolean visible(EntryPlugCarrierEntity plug, net.minecraft.client.renderer.culling.Frustum frustum)
    {
        int slot = plug.laboratorySlotR47();
        if (slot < 0) return false;
        var bounds = LocalTriangleMeshLayer.standaloneBounds(
                new ResourceLocation(ProjectSeele.MODID, "mesh/synch_cradle_r47.mesh.json"));
        if (bounds == null) return false;
        double scale = EvaScale.ENTRY_PLUG_RENDER_SCALE, x = slot == 0 ? 30.5 : 55.5;
        return frustum.isVisible(new net.minecraft.world.phys.AABB(
                x + bounds.minX * scale, -466.5 + bounds.minY * scale, -123 + bounds.minZ * scale,
                x + bounds.maxX * scale, -466.5 + bounds.maxY * scale, -123 + bounds.maxZ * scale));
    }

    static void render(PoseStack pose,MultiBufferSource buffers,EntryPlugCarrierEntity plug,float partial,int light)
    {
        int slot=plug.laboratorySlotR47();if(slot<0)return;
        var current=plug.getInterpolatedCanonicalTransform(partial).translation();
        double x=slot==0?30.5:55.5;
        pose.pushPose();pose.translate(x-current.x,-466.5-current.y,-123-current.z);
        pose.scale(EvaScale.ENTRY_PLUG_RENDER_SCALE,EvaScale.ENTRY_PLUG_RENDER_SCALE,EvaScale.ENTRY_PLUG_RENDER_SCALE);
        LocalTriangleMeshLayer.renderStandalone(pose,buffers,new ResourceLocation(ProjectSeele.MODID,"mesh/synch_cradle_r47.mesh.json"),
                new ResourceLocation(ProjectSeele.MODID,"textures/entity/synch_cradle_r47.png"),light,OverlayTexture.NO_OVERLAY);
        pose.popPose();
    }
    private SynchCradleRendererR47(){}
}

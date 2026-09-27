package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import com.projectseele.client.TreeOfLifeWallClient;
import com.projectseele.world.WallArtworkBlockEntity;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.blockentity.BlockEntityRenderer;
import net.minecraft.client.renderer.blockentity.BlockEntityRendererProvider;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.world.phys.Vec3;

/** Cutout in the normal depth-tested block pass, with no late framebuffer flush. */
public final class WallArtworkRenderer implements BlockEntityRenderer<WallArtworkBlockEntity>
{
    public WallArtworkRenderer(BlockEntityRendererProvider.Context context){}
    @Override public void render(WallArtworkBlockEntity panel,float partial,PoseStack poses,MultiBufferSource buffers,int light,int overlay)
    {
        if(!panel.supported())return;
        var mc=Minecraft.getInstance();Vec3 normal=Vec3.atLowerCornerOf(panel.facing().getNormal());
        if(mc.gameRenderer.getMainCamera().getPosition().subtract(panel.centre()).dot(normal)<=.001)return;
        var texture=TreeOfLifeWallClient.artworkTexture(panel.artwork());if(texture==null)return;
        float halfWidth=Math.min(panel.width(),panel.height()*TreeOfLifeWallClient.artworkAspect(panel.artwork()))*.5F,h=panel.height()*.5F;
        poses.pushPose();var offset=panel.offset();poses.translate(offset.x,offset.y,offset.z);
        poses.mulPose(Axis.YP.rotationDegrees(-panel.facing().toYRot()));
        var pose=poses.last().pose();var normals=poses.last().normal();var consumer=buffers.getBuffer(RenderType.entityCutoutNoCull(texture));
        for(float[] v:new float[][]{{-halfWidth,-h,0,1},{halfWidth,-h,1,1},{halfWidth,h,1,0},{-halfWidth,h,0,0}})
            consumer.vertex(pose,v[0],v[1],0).color(255,255,255,255).uv(v[2],v[3]).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light).normal(normals,0,0,1).endVertex();
        poses.popPose();
    }
    @Override public int getViewDistance(){return 112;}
}

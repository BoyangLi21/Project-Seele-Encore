package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
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
        var mc=Minecraft.getInstance();var basis=panel.surfaceBasisR52();Vec3 normal=basis.normal();
        if(mc.gameRenderer.getMainCamera().getPosition().subtract(panel.centre()).dot(normal)<=.001)return;
        var texture=TreeOfLifeWallClient.artworkTexture(panel.artwork());if(texture==null)return;
        float halfWidth=Math.min(panel.width(),panel.height()*TreeOfLifeWallClient.artworkAspect(panel.artwork()))*.5F,h=panel.height()*.5F;
        poses.pushPose();var offset=panel.offset();poses.translate(offset.x,offset.y,offset.z);
        var pose=poses.last().pose();var normals=poses.last().normal();
        var consumer=buffers.getBuffer(panel.artwork().equals("tree_ink")?RenderType.entityTranslucent(texture):RenderType.entityCutoutNoCull(texture));
        int tint=panel.tintR52();int red=tint>>>16&255,green=tint>>>8&255,blue=tint&255,alpha=tint>>>24;
        // A mural has to follow its real supporting wall. Checking only the
        // centre let a twelve-metre sheet cover doors and new wall openings.
        double horizontalCentre=panel.centre().dot(basis.right()),verticalCentre=panel.centre().dot(basis.up());
        for(double bottom=-h;bottom<h;)
        {
            double top=WallArtworkBlockEntity.nextTileBoundaryR52(verticalCentre,bottom,h);
            for(double left=-halfWidth;left<halfWidth;)
            {
                double right=WallArtworkBlockEntity.nextTileBoundaryR52(horizontalCentre,left,halfWidth);
                if(panel.supportsTile((left+right)*.5,(bottom+top)*.5))
                {
                    float u0=(float)((left+halfWidth)/(2*halfWidth)),u1=(float)((right+halfWidth)/(2*halfWidth)),v0=(float)((h-top)/(2*h)),v1=(float)((h-bottom)/(2*h));
                    for(float[] v:new float[][]{{(float)left,(float)bottom,u0,v1},{(float)right,(float)bottom,u1,v1},{(float)right,(float)top,u1,v0},{(float)left,(float)top,u0,v0}})
                    {
                        var point=basis.right().scale(v[0]).add(basis.up().scale(v[1]));
                        consumer.vertex(pose,(float)point.x,(float)point.y,(float)point.z).color(red,green,blue,alpha).uv(v[2],v[3]).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light).normal(normals,(float)normal.x,(float)normal.y,(float)normal.z).endVertex();
                    }
                }
                left=right;
            }
            bottom=top;
        }
        poses.popPose();
    }
    @Override public int getViewDistance(){return 112;}
}

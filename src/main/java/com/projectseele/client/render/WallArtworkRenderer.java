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
        // A mural has to follow its real supporting wall. Checking only the
        // centre let a twelve-metre sheet cover doors and new wall openings.
        double coordinate=panel.facing().getAxis()==net.minecraft.core.Direction.Axis.Z?panel.centre().x:panel.centre().z;
        double sign=panel.facing().getAxis()==net.minecraft.core.Direction.Axis.Z?normal.z:-normal.x;
        for(float bottom=-h;bottom<h;)
        {
            float top=Math.min(h,(float)(Math.floor(panel.centre().y+bottom+1e-5)+1-panel.centre().y));
            for(float left=-halfWidth;left<halfWidth;)
            {
                double global=coordinate+sign*left;
                double boundary=sign>0?Math.floor(global+1e-5)+1:Math.ceil(global-1e-5)-1;
                float right=Math.min(halfWidth,(float)((boundary-coordinate)/sign));
                if(panel.supportsTile((left+right)*.5,(bottom+top)*.5))
                {
                    float u0=(left+halfWidth)/(2*halfWidth),u1=(right+halfWidth)/(2*halfWidth),v0=(h-top)/(2*h),v1=(h-bottom)/(2*h);
                    for(float[] v:new float[][]{{left,bottom,u0,v1},{right,bottom,u1,v1},{right,top,u1,v0},{left,top,u0,v0}})
                        consumer.vertex(pose,v[0],v[1],0).color(255,255,255,255).uv(v[2],v[3]).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light).normal(normals,0,0,1).endVertex();
                }
                left=right;
            }
            bottom=top;
        }
        poses.popPose();
    }
    @Override public int getViewDistance(){return 112;}
}

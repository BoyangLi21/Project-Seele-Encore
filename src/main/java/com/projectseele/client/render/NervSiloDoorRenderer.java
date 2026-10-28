package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.client.TreeOfLifeWallClient;
import com.projectseele.entity.NervSiloDoorEntity;
import com.projectseele.entity.SiloHatchMechanism;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.client.renderer.culling.Frustum;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.client.renderer.texture.TextureAtlas;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix3f;
import org.joml.Matrix4f;

/** Left/right armoured doors for all three EVA launch-shaft surface heads. */
public final class NervSiloDoorRenderer
        extends EntityRenderer<NervSiloDoorEntity>
{
    public NervSiloDoorRenderer(EntityRendererProvider.Context context)
    {
        super(context);
        this.shadowRadius = 0.0F;
    }

    @Override
    public boolean shouldRender(NervSiloDoorEntity entity, Frustum frustum,
            double cameraX, double cameraY, double cameraZ)
    {
        // The paired 31-block leaves are much larger than their lightweight
        // one-block server entity.  Never cull a tracked hatch by its origin.
        return true;
    }

    @Override
    public void render(NervSiloDoorEntity door, float yaw,
            float partialTick, PoseStack poses, MultiBufferSource buffers,
            int packedLight)
    {
        if(door.declaredGeometryMissingR52())return;
        var declared=door.declaredSpecR52();
        if(com.projectseele.world.NervR50CarrierModeR53.enabled()&&declared!=null
                &&declared.serviceColumnPorts()&&declared.separationSign()<0&&!door.declaredGeometryR52().retiredServiceLeavesR53())return;
        float open = door.getOpenProgress(partialTick);
        poses.pushPose();
        var spec=door.declaredSpecR52();if(spec!=null)poses.mulPose(door.actualFrameR52().rotation());
        TvFacilityMeshes.withBuffers(buffers,()->{if(spec==null)TvFacilityMeshes.shaftHatch(poses,packedLight,open);else TvFacilityMeshes.shaftHatchDeclared(poses,packedLight,open,spec,door.declaredGeometryR52());});
        if(!door.isTvBulkhead())renderSplitLogo(poses, buffers, open,spec);
        poses.popPose();
        super.render(door, yaw, partialTick, poses, buffers, packedLight);
    }

    private static void renderSplitLogo(PoseStack poses,
            MultiBufferSource buffers, float open,SiloHatchMechanism.Spec spec)
    {
        ResourceLocation texture = TreeOfLifeWallClient.nervLogoTexture(
                Minecraft.getInstance());
        if (texture == null)
        {
            return;
        }
        VertexConsumer consumer = buffers.getBuffer(
                RenderType.entityCutout(texture));
        for(int side:new int[]{-1,1})for(int index=0;index<SiloHatchMechanism.PANELS;index++)
        {
            double width=spec==null?SiloHatchMechanism.WIDTH:spec.panelWidth();double a=index*width;
            double b=Math.min(10,a+width);
            if(a>=b)continue;
            var panel=SiloHatchMechanism.panel(index,open,spec);
            double x0=side<0?-b:a,x1=side<0?-a:b;
            double shift=side*(panel.x()-a);
            // Rotate both UV axes through 180 degrees to face the northern
            // approach. Flipping only U would mirror the letters and leaf.
            logoHalf(poses,consumer,x0+shift,x1+shift,-10,10,
                    .995D+panel.y(),(float)(.5D-x0/20),(float)(.5D-x1/20));
        }
    }

    private static void logoHalf(PoseStack poses, VertexConsumer consumer,
            double x0, double x1, double z0, double z1, double y,
            float u0, float u1)
    {
        Matrix4f matrix = poses.last().pose();
        Matrix3f normal = poses.last().normal();
        logoVertex(consumer, matrix, normal, x0, y, z1, u0, 0.0F);
        logoVertex(consumer, matrix, normal, x1, y, z1, u1, 0.0F);
        logoVertex(consumer, matrix, normal, x1, y, z0, u1, 1.0F);
        logoVertex(consumer, matrix, normal, x0, y, z0, u0, 1.0F);
    }

    private static void logoVertex(VertexConsumer consumer, Matrix4f pose,
            Matrix3f normal, double x, double y, double z, float u, float v)
    {
        consumer.vertex(pose, (float)x, (float)y, (float)z)
                .color(255, 255, 255, 255).uv(u, v)
                .overlayCoords(OverlayTexture.NO_OVERLAY)
                .uv2(0x00F000F0).normal(normal, 0.0F, 1.0F, 0.0F)
                .endVertex();
    }

    @Override
    public ResourceLocation getTextureLocation(NervSiloDoorEntity entity)
    {
        return TextureAtlas.LOCATION_BLOCKS;
    }
}

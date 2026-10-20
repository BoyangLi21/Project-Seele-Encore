package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.math.Axis;
import com.projectseele.client.TreeOfLifeWallClient;
import com.projectseele.client.LiftDoorRenderAnchorR53;
import com.projectseele.entity.NervLiftDoorEntity;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.client.renderer.culling.Frustum;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.client.renderer.texture.TextureAtlas;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import org.joml.Matrix3f;
import org.joml.Matrix4f;

/** Scalable silver double leaves for every physical personnel-lift landing. */
public final class NervLiftDoorRenderer
        extends EntityRenderer<NervLiftDoorEntity>
{
    private static final BlockState SILVER =
            Blocks.IRON_BLOCK.defaultBlockState();
    private static final BlockState BLACK =
            Blocks.BLACK_CONCRETE.defaultBlockState();

    public NervLiftDoorRenderer(EntityRendererProvider.Context context)
    {
        super(context);
        this.shadowRadius = 0.0F;
    }

    @Override
    public boolean shouldRender(NervLiftDoorEntity entity, Frustum frustum,
            double cameraX, double cameraY, double cameraZ)
    {
        var centre = LiftDoorRenderAnchorR53.centre(entity, Minecraft.getInstance().getFrameTime());
        return centre.distanceToSqr(cameraX,cameraY,cameraZ)<144*144
                && frustum.isVisible(entity.getBoundingBox()
                        .move(centre.subtract(entity.position()))
                        .inflate(entity.getDoorWidth()+1,entity.getDoorHeight()+1,entity.getDoorWidth()+1));
    }

    @Override
    public void render(NervLiftDoorEntity door, float yaw,
            float partialTick, PoseStack poses, MultiBufferSource buffers,
            int packedLight)
    {
        var centre = LiftDoorRenderAnchorR53.centre(door, partialTick);
        poses.pushPose();
        poses.translate(centre.x - Mth.lerp(partialTick, door.xOld, door.getX()),
                centre.y - Mth.lerp(partialTick, door.yOld, door.getY()),
                centre.z - Mth.lerp(partialTick, door.zOld, door.getZ()));
        float progress = door.getOpenProgress(partialTick);
        double half = door.getDoorWidth() * 0.5D;
        float closedWidth = (float)half - 0.02F;
        if (door.getDoorStyle() == NervLiftDoorEntity.STYLE_GLASS)
        {
            poses.pushPose();
            if (!door.isAxisX()) poses.mulPose(Axis.YP.rotationDegrees(90));
            double slide=half*progress;
            for(double x:new double[]{-half-slide,.02+slide})
            {
                LiftGlassPocketR53.render(poses,buffers,packedLight,
                        x,closedWidth,door.getDoorHeight(),half);
            }
            NervDoorFinish.frame(poses,buffers,packedLight,half,door.getDoorHeight(),progress>=.95F);
            poses.popPose();
            poses.popPose();
            super.render(door,yaw,partialTick,poses,buffers,packedLight);
            return;
        }
        float pocketWidth = Math.min(0.96F, closedWidth);
        float leafWidth = Mth.lerp(progress, closedWidth, pocketWidth);
        double leftX = Mth.lerp(progress, -half,
                -half - pocketWidth);
        double rightX = Mth.lerp(progress, 0.02D, half);
        BlockState material = door.getDoorStyle()
                == NervLiftDoorEntity.STYLE_NERV_BLACK ? BLACK : SILVER;
        poses.pushPose();
        if (!door.isAxisX())
        {
            poses.mulPose(Axis.YP.rotationDegrees(90.0F));
        }
        panel(poses, buffers, packedLight, material,
                leftX, 0.0D, -0.09375D,
                leafWidth, door.getDoorHeight(), 0.1875F);
        panel(poses, buffers, packedLight, material,
                rightX, 0.0D, -0.09375D,
                leafWidth, door.getDoorHeight(), 0.1875F);
        NervDoorFinish.frame(poses,buffers,packedLight,half,door.getDoorHeight(),progress>=.82F);
        if (door.getDoorStyle() == NervLiftDoorEntity.STYLE_NERV_BLACK)
        {
            renderSplitLogo(poses, buffers, leftX, rightX, leafWidth,
                    door.getDoorHeight());
        }
        poses.popPose();
        poses.popPose();
        super.render(door, yaw, partialTick, poses, buffers, packedLight);
    }

    private static void panel(PoseStack poses, MultiBufferSource buffers,
            int light, BlockState material, double x, double y, double z,
            float sx, float sy, float sz)
    {
        NervDoorFinish.leaf(poses,buffers,light,x,y,z,sx,sy,sz,material==BLACK);
    }

    private static void renderSplitLogo(PoseStack poses,
            MultiBufferSource buffers, double leftX, double rightX,
            float leafWidth, int height)
    {
        ResourceLocation logo = TreeOfLifeWallClient.nervLogoTexture(
                Minecraft.getInstance());
        if (logo == null)
        {
            return;
        }
        VertexConsumer consumer = buffers.getBuffer(
                RenderType.entityTranslucent(logo));
        double y0 = Math.max(0.25D, height * 0.08D);
        double y1 = height - y0;
        logoHalf(poses, consumer, leftX, leftX + leafWidth,
                y0, y1, -0.108D, 1.0F, 0.5F);
        logoHalf(poses, consumer, rightX, rightX + leafWidth,
                y0, y1, -0.108D, 0.5F, 0.0F);
    }

    private static void logoHalf(PoseStack poses, VertexConsumer consumer,
            double x0, double x1, double y0, double y1, double z,
            float u0, float u1)
    {
        Matrix4f matrix = poses.last().pose();
        Matrix3f normal = poses.last().normal();
        logoVertex(consumer, matrix, normal, x0, y0, z, u0, 1.0F);
        logoVertex(consumer, matrix, normal, x1, y0, z, u1, 1.0F);
        logoVertex(consumer, matrix, normal, x1, y1, z, u1, 0.0F);
        logoVertex(consumer, matrix, normal, x0, y1, z, u0, 0.0F);
    }

    private static void logoVertex(VertexConsumer consumer, Matrix4f pose,
            Matrix3f normal, double x, double y, double z, float u, float v)
    {
        consumer.vertex(pose, (float)x, (float)y, (float)z)
                .color(255, 255, 255, 255).uv(u, v)
                .overlayCoords(OverlayTexture.NO_OVERLAY)
                .uv2(0x00F000F0).normal(normal, 0.0F, 0.0F, -1.0F)
                .endVertex();
    }

    @Override
    public ResourceLocation getTextureLocation(NervLiftDoorEntity entity)
    {
        return TextureAtlas.LOCATION_BLOCKS;
    }
}

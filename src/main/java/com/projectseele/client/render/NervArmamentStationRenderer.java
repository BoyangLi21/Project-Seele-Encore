package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.ProjectSeele;
import com.projectseele.client.TreeOfLifeWallClient;
import com.projectseele.entity.NervArmamentStationEntity;
import com.projectseele.entity.EvaScale;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.client.renderer.texture.TextureAtlas;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import com.mojang.math.Axis;
import com.mojang.blaze3d.vertex.VertexConsumer;
import net.minecraft.client.renderer.RenderType;
import org.joml.Matrix3f;
import org.joml.Matrix4f;

/** Smooth TV-style vertical Pallet Rifle armament building. */
public final class NervArmamentStationRenderer
        extends EntityRenderer<NervArmamentStationEntity>
{
    private static final ResourceLocation RIFLE_MESH = new ResourceLocation(
            ProjectSeele.MODID, "mesh/eva_pallet_smg.mesh.json");
    private static final ResourceLocation RIFLE_TEXTURE = new ResourceLocation(
            ProjectSeele.MODID, "textures/entity/eva_pallet_smg.png");
    private static final BlockState FRAME =
            Blocks.POLISHED_DEEPSLATE.defaultBlockState();
    private static final BlockState ARMOUR =
            Blocks.DEEPSLATE_TILES.defaultBlockState();
    private static final BlockState RAIL =
            Blocks.POLISHED_BLACKSTONE.defaultBlockState();
    private static final BlockState CRADLE =
            Blocks.IRON_BLOCK.defaultBlockState();
    private static final BlockState WARNING = Blocks.REDSTONE_LAMP
            .defaultBlockState().setValue(BlockStateProperties.LIT, true);

    public NervArmamentStationRenderer(EntityRendererProvider.Context context)
    {
        super(context);
        this.shadowRadius = 0.0F;
    }

    @Override
    public void render(NervArmamentStationEntity station, float yaw,
            float partialTick, PoseStack poses, MultiBufferSource buffers,
            int packedLight)
    {
        poses.pushPose();
        renderSurfaceFrame(poses, buffers, packedLight,station.rackHalfWidthR47());
        renderHatch(poses, buffers, packedLight,
                station.getHatchProgress(partialTick),station.rackHalfWidthR47(),station.payloadR47()==7);

        float lift = station.getLiftProgress(partialTick);
        if (lift > 0.001F || station.getStationState()
                != NervArmamentStationEntity.STOWED)
        {
            renderMovingRack(poses, buffers, packedLight, lift,
                    station.getDoorProgress(partialTick),
                    station.isStocked(),station.payloadR47(),station.rackHalfWidthR47(),station.podTravelR47(),station.podHeightR47());
        }
        poses.popPose();
        super.render(station, yaw, partialTick, poses, buffers, packedLight);
    }

    private static void renderSurfaceFrame(PoseStack poses,
            MultiBufferSource buffers, int light,int half)
    {
        for (int x = -half-1; x <= half+1; x++)
        {
            for (int z = -half-1; z <= half+1; z++)
            {
                if (Math.abs(x) == half+1 || Math.abs(z) == half+1)
                {
                    renderBlock(poses, buffers, light, FRAME, x, 0.0D, z);
                }
            }
        }
        for(int x:new int[]{-half-1,half+1})for(int z:new int[]{-half-1,half+1})
            renderBlock(poses,buffers,light,WARNING,x,1.0D,z);
    }

    private static void renderHatch(PoseStack poses,
            MultiBufferSource buffers, int light, float progress,int half,boolean hinged)
    {
        double slide = progress * (half+1.25D);
        for (int x = -half; x <= half; x++)
        {
            for (int z = -half; z <= half; z++)
            {
                // The wide shield well folds its cover at the outer edges;
                // a full sideways slide would sweep into the neighbouring well.
                if(hinged)
                {
                    double hinge=x<0?-half-.5D:half+.5D;
                    poses.pushPose();poses.translate(hinge,0,0);
                    poses.mulPose(Axis.ZP.rotationDegrees((x<0?1:-1)*progress*90.0F));
                    renderBlock(poses,buffers,light,ARMOUR,x-hinge,0.05D,z);poses.popPose();continue;
                }
                double shiftedX = x < 0 ? x - slide : x + slide;
                renderBlock(poses, buffers, light, ARMOUR,
                        shiftedX, 0.05D, z);
            }
        }
    }

    private static void renderMovingRack(PoseStack poses,
            MultiBufferSource buffers, int light, float progress,
            float doorProgress, boolean stocked,int payload,int half,float travel,float height)
    {
        float span=half*2+1,inner=half*2-1;
        double baseY = -travel + progress * travel;
        for (int x = -half; x <= half; x++)
        {
            for (int z = -half; z <= half; z++)
            {
                renderBlock(poses, buffers, light, ARMOUR,
                        x, baseY, z);
            }
        }

        // A complete sealed armour pod rises first. Large panels are scaled
        // block models rather than hundreds of individual world blocks, so
        // the motion remains cheap and visually continuous.
        renderPanel(poses, buffers, light, ARMOUR,
                -half-.5D, baseY + 1.0D, -half-.5D, 1.0F, height, span);
        renderPanel(poses, buffers, light, ARMOUR,
                half-.5D, baseY + 1.0D, -half-.5D, 1.0F, height, span);
        renderPanel(poses, buffers, light, ARMOUR,
                -half+.5D, baseY + 1.0D, half-.5D, inner, height, 1.0F);
        renderPanel(poses, buffers, light, FRAME,
                -half+.5D, baseY + height, -half+.5D,
                inner, 1.0F, inner);

        // Covers stay shut throughout the rise. The wide shield cover rolls
        // into its own header; the narrower original pods retain sliding leaves.
        double doorSlide = payload==7?0:doorProgress * (half-.25D);
        float doorHeight=(height-1)*(payload==7?1-doorProgress:1);
        double doorBase=baseY+1+(payload==7?(height-1)*doorProgress:0);
        if(doorHeight>.001F)
        {
        renderPanel(poses, buffers, light, ARMOUR,
                -half+.5D - doorSlide, doorBase, -half-.5D,
                inner/2, doorHeight, 1.0F);
        if(payload==7)
        {
            poses.pushPose();poses.translate(0,doorBase-(1-doorProgress)*(baseY+1),0);
            poses.scale(1,1-doorProgress,1);renderSplitDoorLogo(poses,buffers,baseY,0,half);poses.popPose();
        }
        else renderSplitDoorLogo(poses, buffers, baseY, doorSlide,half);
        renderPanel(poses, buffers, light, ARMOUR,
                doorSlide, doorBase, -half-.5D,
                inner/2, doorHeight, 1.0F);
        }

        // Internal lift rails and rifle cradle become visible through the
        // opening; they never form the exterior silhouette during travel.
        for (int y = 2; y <= height-2; y++)
        {
            renderBlock(poses, buffers, light, RAIL,
                    -half+1, baseY + y, half-1);
            renderBlock(poses, buffers, light, RAIL,
                    half-1, baseY + y, half-1);
        }
        for (int y = 3; y <= height-3; y += 5)
        {
            renderBlock(poses, buffers, light, CRADLE,
                    -half+1, baseY + y, 0);
            renderBlock(poses, buffers, light, CRADLE,
                    half-1, baseY + y, 0);
        }

        if (stocked)
        {
            poses.pushPose();
            poses.translate(0.5D, baseY + 1.0D, 0.5D);
            // The payload stays upright; only its front/back heading changes.
            poses.mulPose(Axis.YP.rotationDegrees(payload==7?0.0F:180.0F));
            // Use the exact same world scale as the rifle in an EVA's hands;
            // the former 3.6 scale made the station payload only 72% size.
            poses.scale(EvaScale.RENDER_SCALE, EvaScale.RENDER_SCALE,
                    EvaScale.RENDER_SCALE);
            LocalTriangleMeshLayer.renderStandalone(poses, buffers,
                    payload==7?new ResourceLocation(ProjectSeele.MODID,"mesh/yashima_shield_payload.mesh.json")
                            :payload==6?new ResourceLocation(ProjectSeele.MODID,"mesh/eva02_longsword_payload_r47.mesh.json")
                            :payload==2?new ResourceLocation(ProjectSeele.MODID,"mesh/positron_cannon_payload_r50.mesh.json"):RIFLE_MESH,
                    payload==7?new ResourceLocation(ProjectSeele.MODID,"textures/entity/yashima_shield.png")
                            :payload==6?new ResourceLocation(ProjectSeele.MODID,"textures/entity/eva02_longsword.png")
                            :payload==2?new ResourceLocation(ProjectSeele.MODID,"textures/entity/positron_cannon.png"):RIFLE_TEXTURE,light,
                    OverlayTexture.NO_OVERLAY);
            poses.popPose();
        }
    }

    private static void renderSplitDoorLogo(PoseStack poses,
            MultiBufferSource buffers, double baseY, double doorSlide,int half)
    {
        ResourceLocation logo = TreeOfLifeWallClient.nervLogoTexture(
                Minecraft.getInstance());
        if (logo == null)
        {
            return;
        }
        VertexConsumer consumer = buffers.getBuffer(
                RenderType.entityTranslucent(logo));
        renderLogoHalf(poses, consumer,
                -half+.5D - doorSlide, 0.0D - doorSlide,
                baseY + 15.0D, baseY + 31.0D,
                -half-.515D, 1.0F, 0.5F);
        renderLogoHalf(poses, consumer,
                0.0D + doorSlide, half-.5D + doorSlide,
                baseY + 15.0D, baseY + 31.0D,
                -half-.515D, 0.5F, 0.0F);
    }

    private static void renderLogoHalf(PoseStack poses,
            VertexConsumer consumer, double x0, double x1,
            double y0, double y1, double z, float u0, float u1)
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

    private static void renderBlock(PoseStack poses,
            MultiBufferSource buffers, int light, BlockState state,
            double x, double y, double z)
    {
        poses.pushPose();
        poses.translate(x - 0.5D, y, z - 0.5D);
        Minecraft.getInstance().getBlockRenderer().renderSingleBlock(
                state, poses, buffers, light, OverlayTexture.NO_OVERLAY);
        poses.popPose();
    }

    private static void renderPanel(PoseStack poses,
            MultiBufferSource buffers, int light, BlockState state,
            double x, double y, double z, float sizeX, float sizeY,
            float sizeZ)
    {
        poses.pushPose();
        poses.translate(x, y, z);
        poses.scale(sizeX, sizeY, sizeZ);
        Minecraft.getInstance().getBlockRenderer().renderSingleBlock(
                state, poses, buffers, light, OverlayTexture.NO_OVERLAY);
        poses.popPose();
    }

    @Override
    public ResourceLocation getTextureLocation(
            NervArmamentStationEntity entity)
    {
        return TextureAtlas.LOCATION_BLOCKS;
    }
}

package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import com.projectseele.entity.NervSlidingDoorEntity;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.client.renderer.culling.Frustum;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.client.renderer.texture.TextureAtlas;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;

/** Two silver leaves that retract completely into the authored wall pockets. */
public final class NervSlidingDoorRenderer
        extends EntityRenderer<NervSlidingDoorEntity>
{
    private static final BlockState SILVER =
            Blocks.IRON_BLOCK.defaultBlockState();

    public NervSlidingDoorRenderer(EntityRendererProvider.Context context)
    {
        super(context);
        this.shadowRadius = 0.0F;
    }

    @Override
    public boolean shouldRender(NervSlidingDoorEntity entity,
            Frustum frustum, double cameraX, double cameraY, double cameraZ)
    {
        return entity.distanceToSqr(cameraX,cameraY,cameraZ)<96*96&&frustum.isVisible(entity.getBoundingBox().inflate(3.2,2.2,3.2));
    }

    @Override
    public void render(NervSlidingDoorEntity door, float yaw,
            float partialTick, PoseStack poses, MultiBufferSource buffers,
            int packedLight)
    {
        double slide = door.getOpenProgress(partialTick) * 1.5D;
        poses.pushPose();
        if (!door.isAxisX())
        {
            poses.mulPose(Axis.YP.rotationDegrees(90.0F));
        }
        NervPressureDoorFinishR45.leaf(poses, buffers, packedLight, -1.5D - slide, true);
        NervPressureDoorFinishR45.leaf(poses, buffers, packedLight, .02D + slide, false);
        String number=String.format(java.util.Locale.ROOT,"%02d",door.getDoorId());
        NervPressureDoorFinishR45.identity(poses,buffers,packedLight,-1.5D-slide,"R",number);
        NervPressureDoorFinishR45.identity(poses,buffers,packedLight,.02D+slide,number,"R");
        NervPressureDoorFinishR45.frame(poses, buffers, packedLight, door.getOpenProgress(partialTick));
        poses.popPose();
        super.render(door, yaw, partialTick, poses, buffers, packedLight);
    }

    private static void panel(PoseStack poses, MultiBufferSource buffers,
            int light, double x, double y, double z,
            float sx, float sy, float sz)
    {
        NervDoorFinish.leaf(poses,buffers,light,x,y,z,sx,sy,sz,false);
    }

    @Override
    public ResourceLocation getTextureLocation(NervSlidingDoorEntity entity)
    {
        return TextureAtlas.LOCATION_BLOCKS;
    }
}

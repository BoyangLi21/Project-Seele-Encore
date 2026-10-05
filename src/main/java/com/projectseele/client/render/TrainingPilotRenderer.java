package com.projectseele.client.render;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.TrainingPilotEntity;
import net.minecraft.client.model.PlayerModel;
import net.minecraft.client.model.geom.ModelLayers;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.client.renderer.entity.MobRenderer;
import net.minecraft.resources.ResourceLocation;

/** Human-scale visual proxy for the automated NERV training pilot. */
public final class TrainingPilotRenderer
        extends MobRenderer<TrainingPilotEntity, PlayerModel<TrainingPilotEntity>>
{
    private static final ResourceLocation REI = texture("rei");
    private static final ResourceLocation SHINJI = texture("shinji");
    private static final ResourceLocation ASUKA = texture("asuka");

    public TrainingPilotRenderer(EntityRendererProvider.Context context)
    {
        super(context, new PlayerModel<>(
                context.bakeLayer(ModelLayers.PLAYER_SLIM), true), 0.5F);
    }

    @Override
    public ResourceLocation getTextureLocation(TrainingPilotEntity entity)
    {
        return switch (entity.getAssignedVariant())
        {
            case EvaUnit01Entity.UNIT_00 -> REI;
            case EvaUnit01Entity.UNIT_02 -> ASUKA;
            default -> SHINJI;
        };
    }

    @Override
    public void render(TrainingPilotEntity entity,float yaw,float partial,
                       com.mojang.blaze3d.vertex.PoseStack pose,
                       net.minecraft.client.renderer.MultiBufferSource buffers,int light)
    {
        boolean reclined=com.projectseele.client.EntryPlugPilotPoseR47.push(pose,entity,partial);
        try { super.render(entity,yaw,partial,pose,buffers,light); }
        finally { if(reclined)pose.popPose(); }
    }

    private static ResourceLocation texture(String pilot)
    {
        return new ResourceLocation(ProjectSeele.MODID,
                "textures/entity/training_pilot_" + pilot + ".png");
    }
}

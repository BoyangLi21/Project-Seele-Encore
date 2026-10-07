package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.entity.GaghielEntity;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.resources.ResourceLocation;
import software.bernie.geckolib.core.animation.AnimationState;
import software.bernie.geckolib.model.GeoModel;
import software.bernie.geckolib.renderer.GeoEntityRenderer;

/** The marine rig has a buoyancy origin, a hinged jaw and a continuous tail. */
public final class GaghielRendererR50 extends GeoEntityRenderer<GaghielEntity>
{
    private static final ResourceLocation MESH = new ResourceLocation("projectseele", "mesh/gaghiel_r49.mesh.json");

    public GaghielRendererR50(EntityRendererProvider.Context context)
    {
        super(context, new MarineModel());
        addRenderLayer(new RiggedAngelLayer<>(this, MESH));
        shadowRadius = 10;
    }

    @Override public void render(GaghielEntity entity, float yaw, float partial,
                                 PoseStack poses, MultiBufferSource buffers, int light)
    {
        withScale(entity.modelScaleR50());
        super.render(entity, yaw, partial, poses, buffers, light);
    }

    private static final class MarineModel extends GeoModel<GaghielEntity>
    {
        @Override public ResourceLocation getModelResource(GaghielEntity entity)
        { return new ResourceLocation("projectseele", "geo/gaghiel_r49.geo.json"); }
        @Override public ResourceLocation getTextureResource(GaghielEntity entity)
        { return new ResourceLocation("projectseele", "textures/entity/gaghiel_r49.png"); }
        @Override public ResourceLocation getAnimationResource(GaghielEntity entity)
        { return new ResourceLocation("projectseele", "animations/gaghiel_r49.animation.json"); }

        @Override public void setCustomAnimations(GaghielEntity entity, long id, AnimationState<GaghielEntity> state)
        {
            super.setCustomAnimations(entity, id, state);
            float partial = state.getPartialTick(), phase = entity.swimPhase(partial);
            for(int i=0;i<5;i++)
            {
                float turn=(float)Math.sin(phase-i*.65F)*(.07F+i*.035F);
                getAnimationProcessor().getBone("tail_"+i).setRotY(turn);
            }
            getAnimationProcessor().getBone("jaw_lower").setRotX(-1.05F*entity.mouthOpen(partial));
            getAnimationProcessor().getBone("fin_l").setRotZ((float)Math.sin(phase*.7F)*.09F);
            getAnimationProcessor().getBone("fin_r").setRotZ(-(float)Math.sin(phase*.7F)*.09F);
            getAnimationProcessor().getBone("dorsal").setRotZ((float)Math.sin(phase-.4F)*.05F);
        }
    }
}

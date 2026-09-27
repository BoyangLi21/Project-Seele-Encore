package com.projectseele.client.render;

import net.minecraft.resources.ResourceLocation;
import software.bernie.geckolib.animatable.GeoEntity;
import software.bernie.geckolib.model.GeoModel;

/** Resource-pack-overridable model descriptor for local licensed/test assets. */
public class LocalAddonGeoModel<T extends GeoEntity> extends GeoModel<T>
{
    private final ResourceLocation geometry;
    private final ResourceLocation texture;
    private final ResourceLocation animation;

    public LocalAddonGeoModel(ResourceLocation geometry, ResourceLocation texture,
                              ResourceLocation animation)
    {
        this.geometry = geometry;
        this.texture = texture;
        this.animation = animation;
    }

    @Override
    public ResourceLocation getModelResource(T animatable)
    {
        return this.geometry;
    }

    @Override
    public ResourceLocation getTextureResource(T animatable)
    {
        return this.texture;
    }

    @Override
    public ResourceLocation getAnimationResource(T animatable)
    {
        return this.animation;
    }

    @Override
    public void setCustomAnimations(T animatable,long instanceId,software.bernie.geckolib.core.animation.AnimationState<T> state)
    {
        super.setCustomAnimations(animatable,instanceId,state);
        if(animatable instanceof net.minecraft.world.entity.Entity entity
                && entity instanceof com.projectseele.entity.FirstBattleSignals.Actor actor
                && actor.firstBattleSignals().active(entity))
        {
            FirstBattlePoseRenderer.apply(entity,this.getBakedModel(this.getModelResource(animatable)),state.getPartialTick());
            return;
        }
        if(animatable instanceof net.minecraft.world.entity.LivingEntity body&&com.projectseele.physics.CombatBodyDynamics.active(body))
        {PhysicalBodyRenderer.apply(body,this.getBakedModel(this.getModelResource(animatable)),state.getPartialTick());return;}
        if(animatable instanceof com.projectseele.entity.SachielEntity actor&&!actor.isFirstBattleActive()&&com.projectseele.physics.CombatBodyDynamics.available(actor))
        {PhysicalBodyRenderer.write(com.projectseele.entity.SachielBodyPoseR35.sample(actor,state.getPartialTick()),this.getBakedModel(this.getModelResource(animatable)));return;}
        if(animatable instanceof net.minecraft.world.entity.LivingEntity living)
            AngelCombatPoseR31.rememberGecko(living,this.getBakedModel(this.getModelResource(animatable)));
        if(animatable instanceof com.projectseele.entity.SachielEntity angel)SachielStrikePose.apply(angel,this.getBakedModel(this.getModelResource(animatable)),state.getPartialTick());
        if(animatable instanceof com.projectseele.entity.ShamshelEntity angel)ShamshelWhipPose.apply(angel,this.getBakedModel(this.getModelResource(animatable)),state.getPartialTick());
        if(animatable instanceof net.minecraft.world.entity.Entity entity)
            FirstBattlePoseRenderer.apply(entity,this.getBakedModel(this.getModelResource(animatable)),state.getPartialTick());
        if(animatable instanceof net.minecraft.world.entity.LivingEntity living)
            EvaImpactPose.apply(living,this.getBakedModel(this.getModelResource(animatable)),state.getPartialTick());
        if(animatable instanceof net.minecraft.world.entity.LivingEntity living)
            AngelCombatPoseR31.apply(living,this.getBakedModel(this.getModelResource(animatable)),state.getPartialTick());
    }
}

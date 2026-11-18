package com.projectseele.entity;

import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import software.bernie.geckolib.animatable.GeoEntity;
import software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache;
import software.bernie.geckolib.core.animation.AnimatableManager;
import software.bernie.geckolib.util.GeckoLibUtil;

/** Immobile, invulnerable Terminal Dogma specimen and local mesh anchor. */
public class LilithEntity extends PathfinderMob implements GeoEntity
{
    private static final net.minecraft.network.syncher.EntityDataAccessor<Float> CONTAINMENT_SCALE=net.minecraft.network.syncher.SynchedEntityData.defineId(LilithEntity.class,net.minecraft.network.syncher.EntityDataSerializers.FLOAT);
    private static final net.minecraft.network.syncher.EntityDataAccessor<Boolean> SPEAR_SHOWN=net.minecraft.network.syncher.SynchedEntityData.defineId(LilithEntity.class,net.minecraft.network.syncher.EntityDataSerializers.BOOLEAN);
    /** How the sealing spear is shown: "auto" follows the TV story (taken in episode 22, chapter "arael"),
     *  "present" and "removed" fix it for reviews and custom maps. */
    public static final java.util.List<String> SPEAR_MODES=java.util.List.of("auto","present","removed");
    private static final String SPEAR_TAKEN_CHAPTER="arael";
    private String spearMode="auto";
    @Override protected void defineSynchedData(){super.defineSynchedData();this.entityData.define(CONTAINMENT_SCALE,1F);this.entityData.define(SPEAR_SHOWN,true);}
    public boolean isSpearShown(){return this.entityData.get(SPEAR_SHOWN);}
    public String getSpearMode(){return spearMode;}
    public void setSpearMode(String mode){spearMode=SPEAR_MODES.contains(mode)?mode:"auto";refreshSpear();}
    private void refreshSpear()
    {
        boolean shown=switch(spearMode){case "present"->true;case "removed"->false;default->!spearTakenInStory();};
        if(shown!=isSpearShown())this.entityData.set(SPEAR_SHOWN,shown);
    }
    private boolean spearTakenInStory()
    {
        if(!(this.level() instanceof net.minecraft.server.level.ServerLevel level))return false;
        var campaign=com.projectseele.world.TvCampaignSavedData.peek(level.getServer().overworld());
        return campaign!=null&&campaign.completed.contains(SPEAR_TAKEN_CHAPTER);
    }
    public float getContainmentScale(){return this.entityData.get(CONTAINMENT_SCALE);}
    public void setContainmentScale(float value){this.entityData.set(CONTAINMENT_SCALE,net.minecraft.util.Mth.clamp(value,.5F,2F));}
    @Override public void addAdditionalSaveData(net.minecraft.nbt.CompoundTag tag){super.addAdditionalSaveData(tag);tag.putFloat("ContainmentScale",getContainmentScale());tag.putString("SpearMode",spearMode);}
    @Override public void readAdditionalSaveData(net.minecraft.nbt.CompoundTag tag){super.readAdditionalSaveData(tag);setContainmentScale(tag.contains("ContainmentScale")?tag.getFloat("ContainmentScale"):1F);spearMode=SPEAR_MODES.contains(tag.getString("SpearMode"))?tag.getString("SpearMode"):"auto";}
    private final AnimatableInstanceCache geoCache =
            GeckoLibUtil.createInstanceCache(this);

    public LilithEntity(EntityType<? extends LilithEntity> type, Level level)
    {
        super(type, level);
        this.noPhysics = true;
        this.setNoGravity(true);
        this.setPersistenceRequired();
    }

    public static AttributeSupplier.Builder createAttributes()
    {
        return Mob.createMobAttributes()
                .add(Attributes.MAX_HEALTH, 1000.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.0D)
                .add(Attributes.KNOCKBACK_RESISTANCE, 1.0D);
    }

    @Override
    protected void registerGoals()
    {
        // Lilith is an architectural containment specimen, not an AI actor.
    }

    @Override
    public void tick()
    {
        super.tick();
        this.noPhysics = true;
        this.setNoGravity(true);
        this.setDeltaMovement(Vec3.ZERO);
        this.fallDistance = 0.0F;
        // The imported south-wall mesh faces arrivals at zero yaw.
        this.setYRot(0.0F);
        this.yBodyRot = 0.0F;
        this.yHeadRot = 0.0F;
        if (!this.level().isClientSide && this.tickCount % 40 == 0)
        {
            refreshSpear();
        }
    }

    @Override
    public boolean hurt(DamageSource source, float amount)
    {
        return false;
    }

    @Override
    public boolean isPushable()
    {
        return false;
    }

    @Override
    public boolean canBeCollidedWith()
    {
        return false;
    }

    @Override
    public boolean removeWhenFarAway(double distanceToClosestPlayer)
    {
        return false;
    }

    @Override
    public void registerControllers(
            AnimatableManager.ControllerRegistrar controllers)
    {
        // The reviewed model is intentionally static on the crucifix.
    }

    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache()
    {
        return this.geoCache;
    }
}

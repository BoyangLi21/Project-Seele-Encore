package com.projectseele.entity;

import com.projectseele.world.TrainingPilotDirector;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.level.Level;

/** Visible NERV test pilot for the otherwise multiplayer-only cockpit link. */
public final class TrainingPilotEntity extends PathfinderMob
{
    public static final int STAGE_WALKING = 0;
    public static final int STAGE_IN_PLUG = 1;
    public static final int STAGE_LINKED = 2;
    public static final int STAGE_STANDBY = 3;

    private static final EntityDataAccessor<Integer> DATA_VARIANT =
            SynchedEntityData.defineId(TrainingPilotEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_STAGE =
            SynchedEntityData.defineId(TrainingPilotEntity.class,
                    EntityDataSerializers.INT);

    public TrainingPilotEntity(EntityType<? extends TrainingPilotEntity> type,
                               Level level)
    {
        super(type, level);
        this.setPersistenceRequired();
    }

    public static AttributeSupplier.Builder createAttributes()
    {
        return PathfinderMob.createMobAttributes()
                .add(Attributes.MAX_HEALTH, 20.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.34D)
                .add(Attributes.FOLLOW_RANGE, 96.0D);
    }

    @Override
    protected net.minecraft.world.entity.ai.navigation.PathNavigation createNavigation(Level level)
    {
        return new TrainingPilotNavigationR47(this,level);
    }

    @Override
    protected void defineSynchedData()
    {
        super.defineSynchedData();
        this.entityData.define(DATA_VARIANT, EvaUnit01Entity.UNIT_01);
        this.entityData.define(DATA_STAGE, STAGE_WALKING);
    }

    public int getAssignedVariant()
    {
        return this.entityData.get(DATA_VARIANT);
    }

    public void assignVariant(int variant)
    {
        int safeVariant = Math.max(EvaUnit01Entity.UNIT_00,
                Math.min(EvaUnit01Entity.UNIT_02, variant));
        this.entityData.set(DATA_VARIANT, safeVariant);
        this.setCustomName(Component.literal(pilotName(safeVariant)));
        this.setCustomNameVisible(true);
    }

    public static String pilotName(int variant)
    {
        return switch (variant)
        {
            case 0 -> "绫波丽";
            case 2 -> "惣流·明日香·兰格雷";
            default -> "碇真嗣";
        };
    }

    public int getTrainingStage()
    {
        return this.entityData.get(DATA_STAGE);
    }

    public void setTrainingStage(int stage)
    {
        this.entityData.set(DATA_STAGE, stage);
    }

    @Override
    public void tick()
    {
        super.tick();
        if (!this.level().isClientSide)
        {
            TrainingPilotDirector.tickPilot(this);
            com.projectseele.world.PilotRadioR28.tick(this);
        }
    }

    @Override
    protected net.minecraft.world.InteractionResult mobInteract(net.minecraft.world.entity.player.Player player,net.minecraft.world.InteractionHand hand)
    {
        if(hand!=net.minecraft.world.InteractionHand.MAIN_HAND)return net.minecraft.world.InteractionResult.PASS;
        if(player instanceof net.minecraft.server.level.ServerPlayer server)com.projectseele.world.NervStaffDialogue.pilot(server,this);
        return net.minecraft.world.InteractionResult.sidedSuccess(level().isClientSide);
    }

    @Override
    public boolean removeWhenFarAway(double distance)
    {
        return false;
    }

    @Override
    public boolean causeFallDamage(float distance, float multiplier,
                                   DamageSource source)
    {
        return false;
    }

    @Override
    public void addAdditionalSaveData(CompoundTag tag)
    {
        super.addAdditionalSaveData(tag);
        tag.putInt("EvaVariant", this.getAssignedVariant());
        tag.putInt("TrainingStage", this.getTrainingStage());
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag)
    {
        super.readAdditionalSaveData(tag);
        if (tag.contains("EvaVariant"))
        {
            this.assignVariant(tag.getInt("EvaVariant"));
        }
        if (tag.contains("TrainingStage"))
        {
            this.setTrainingStage(tag.getInt("TrainingStage"));
        }
    }
}

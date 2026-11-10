package com.projectseele.capability;

import com.projectseele.config.SeeleConfig;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.player.Player;
import net.minecraftforge.common.capabilities.Capability;
import net.minecraftforge.common.capabilities.CapabilityManager;
import net.minecraftforge.common.capabilities.CapabilityToken;

/** Typed access and balance transforms for the pilot capability. */
public final class EvaPilotCapability
{
    public static final Capability<EvaPilotData> DATA =
            CapabilityManager.get(new CapabilityToken<>() {});

    private EvaPilotCapability() {}

    public static float synchronization(Player player)
    {
        return player.getCapability(DATA).map(EvaPilotData::synchronization)
                .orElse(EvaPilotData.initialSynchronization());
    }

    public static boolean tickActiveDriving(ServerPlayer player)
    {
        return player.getCapability(DATA).map(EvaPilotData::tickActiveDriving)
                .orElse(false);
    }

    public static float awardAngelKill(ServerPlayer player)
    {
        float gain = SeeleConfig.COMMON_SPEC.isLoaded()
                ? SeeleConfig.EVA_SYNC_ANGEL_KILL_GAIN.get().floatValue() : 2.5F;
        return player.getCapability(DATA).map(data -> data.increase(gain)).orElse(0.0F);
    }

    /** Initial synchronization is the no-bonus baseline. */
    public static float mobilityMultiplier(float synchronization)
    {
        float progress = normalizedGrowth(synchronization);
        float maximumBonus = SeeleConfig.COMMON_SPEC.isLoaded()
                ? SeeleConfig.EVA_SYNC_MAX_MOBILITY_BONUS.get().floatValue() : 0.25F;
        return 1.0F + maximumBonus * progress;
    }

    /** Used as a divisor for melee and automatic-fire cooldowns. */
    public static float attackSpeedMultiplier(float synchronization)
    {
        float progress = normalizedGrowth(synchronization);
        float maximumBonus = SeeleConfig.COMMON_SPEC.isLoaded()
                ? SeeleConfig.EVA_SYNC_MAX_ATTACK_SPEED_BONUS.get().floatValue() : 0.25F;
        return 1.0F + maximumBonus * progress;
    }


    private static float normalizedGrowth(float synchronization)
    {
        float initial = EvaPilotData.initialSynchronization();
        float span = Math.max(1.0F, EvaPilotData.maxSynchronization() - initial);
        return Mth.clamp((synchronization - initial) / span, 0.0F, 1.0F);
    }
}
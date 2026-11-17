package com.projectseele.world;

import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.RamielEntity;
import com.projectseele.network.ClientboundCannonServiceR64;
import com.projectseele.network.SeeleNetwork;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.network.PacketDistributor;

/**
 * R64: the Yashima gunnery told to the shooter's sight, ten times a second, while a human pilot has the shooting
 * Unit in the operation's approach or combat. Only read here: the power, the service after a shot, whether a charge
 * is admitted, the target's charge and core. An NPC shooter needs none of it and is sent nothing.
 */
@Mod.EventBusSubscriber(modid = "projectseele")
public final class CannonSightSyncR64
{
    private CannonSightSyncR64() {}

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END || event.getServer().getTickCount() % 2 != 0) return;
        var level = event.getServer().getLevel(FacilitySchemaV2.DIMENSION);
        // No emplacement in this world: no operation to tell of, and its saved data is left alone.
        if (level == null || TvYashimaStationR52.plan(level).isEmpty()) return;
        var data = TvCampaignSavedData.get(level);
        if (!data.active.equals("ramiel") || data.angel == null || data.targetDeathConfirmedR45) return;
        int phase = switch (data.phase) { case "approach" -> 2; case "combat" -> 3; default -> 0; };
        if (phase == 0) return;
        var shooter = TvSortiesR32.assignedUnit(level, data, 1);
        if (shooter == null || !(shooter.getPilotEntity() instanceof ServerPlayer pilot)) return;
        if (!(level.getEntity(data.angel) instanceof RamielEntity boss) || !boss.isAlive()) return;
        int[] power = TvYashimaDirectorR50.powerR64(level, shooter);
        if (power == null) return;
        var service = TvYashimaSavedDataR50.get(level);
        var core = boss.position().add(0, boss.getBbHeight() * .5, 0);
        // The notice is "operation · armour pierced · what holds the gun": the sight says the last of the three.
        String notice = data.notice == null ? "" : data.notice.substring(data.notice.lastIndexOf('·') + 1).trim();
        SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(() -> pilot), new ClientboundCannonServiceR64(shooter.getId(), phase,
                power[0], power[1] == 1, power[2] == 1, TvEncounterRulesR45.cannonPermissionR50(shooter),
                service.shots, Math.max(0, Math.min(120, service.serviceTicksR53)), service.reloadReady, service.coolantReady,
                TvYashimaCombatCommsR54.chargeRemainingR54(boss), SeeleConfig.YASHIMA_BEAM_CHARGE_TICKS.get(), boss.isExposed(),
                Math.max(0, boss.getBeamTicks()), Math.max(0, boss.getBeamDurationR54()), core.x, core.y, core.z, RamielEntity.CORE_RADIUS * boss.modelScaleR52(), notice));
    }
}

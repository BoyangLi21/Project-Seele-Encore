package com.projectseele.event;

import java.util.List;
import java.util.Locale;

import com.projectseele.ProjectSeele;
import com.projectseele.alarm.AngelAlarmSystem;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.RamielEntity;
import com.projectseele.registry.ModEntities;
import com.projectseele.world.IntegratedNervMapBuilder;
import com.projectseele.world.Tokyo3RamielBattleSavedData;
import com.projectseele.world.Tokyo3RamielBattleSavedData.StoredBattle;
import com.projectseele.world.Tokyo3RetractionDirector;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.MobSpawnType;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Persistent Operation Yashima encounter staged over integrated Tokyo-3. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID,
        bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class Tokyo3RamielBattleDirector
{
    private static final String BATTLE_TAG =
            "projectseele.tokyo3.operation_yashima";
    private static final int RESTORE_DELAY_TICKS = 100;
    private static final double BATTLE_MONITOR_RANGE = 420.0D;

    private Tokyo3RamielBattleDirector() {}

    public static BattleResult start(ServerLevel level, BlockPos origin,
                                     ServerPlayer commander)
    {
        Tokyo3RamielBattleSavedData data =
                Tokyo3RamielBattleSavedData.get(level);
        StoredBattle stored = data.get(origin).orElse(null);
        if (stored != null)
        {
            Entity existing = level.getEntity(stored.ramiel());
            if (existing instanceof RamielEntity ramiel && ramiel.isAlive())
            {
                return new BattleResult(false,
                        "Operation Yashima is already active: Ramiel HP "
                                + Math.round(ramiel.getHealth()) + "/"
                                + Math.round(ramiel.getMaxHealth()) + ".");
            }
            data.remove(origin);
        }

        RamielEntity ramiel = ModEntities.RAMIEL.get().create(level);
        if (ramiel == null)
        {
            return new BattleResult(false,
                    "Ramiel deployment failed: entity creation returned null.");
        }
        BlockPos spawn = origin.offset(0, 48, 80);
        ramiel.moveTo(spawn.getX() + 0.5D, spawn.getY() + 0.5D,
                spawn.getZ() + 0.5D, 180.0F, 0.0F);
        ramiel.finalizeSpawn(level, level.getCurrentDifficultyAt(spawn),
                MobSpawnType.EVENT, null, null);
        ramiel.setPersistenceRequired();
        ramiel.addTag(BATTLE_TAG);

        List<EvaUnit01Entity> units = level.getEntitiesOfClass(
                EvaUnit01Entity.class,
                new AABB(origin).inflate(180.0D, 96.0D, 180.0D),
                unit -> unit.isAlive());
        EvaUnit01Entity target = units.stream()
                .filter(unit -> unit.getUnitVariant()
                        == EvaUnit01Entity.UNIT_01)
                .findFirst().orElse(units.stream().findFirst().orElse(null));
        ramiel.setTarget(target != null ? target : commander);
        if (!level.addFreshEntity(ramiel))
        {
            return new BattleResult(false,
                    "Ramiel deployment failed: server rejected the entity.");
        }

        data.put(new StoredBattle(origin, ramiel.getUUID(), 0));
        Tokyo3RetractionDirector.request(level, origin, true);
        AngelAlarmSystem.engage(ramiel);
        broadcast(level, origin, Component.translatable("message.projectseele.tokyo3ramiel_battle_director.operation_yashima_ramiel_over_tokyo_3_armour"));
        ProjectSeele.LOGGER.info(
                "Operation Yashima started: ramiel={} origin={} spawn={} target={} route={} blocks",
                ramiel.getStringUUID(), origin.toShortString(),
                spawn.toShortString(), ramiel.getTarget() == null ? "none"
                        : ramiel.getTarget().getStringUUID(),
                IntegratedNervMapBuilder.ascentDistance());
        return new BattleResult(true,
                "Operation Yashima started. Ramiel is above the battle plaza; "
                        + "Tokyo-3 is retracting and NERV telemetry is live.");
    }

    public static BattleStatus status(ServerLevel level, BlockPos origin)
    {
        StoredBattle battle = Tokyo3RamielBattleSavedData.get(level)
                .get(origin).orElse(null);
        if (battle == null)
        {
            return new BattleStatus(false, "STANDBY", 0.0F, 0.0F,
                    0.0F, 0.0F, 0);
        }
        Entity entity = level.getEntity(battle.ramiel());
        if (entity instanceof RamielEntity ramiel && ramiel.isAlive())
        {
            return new BattleStatus(true,
                    ramiel.isExposed() ? "CORE EXPOSED" : "A.T. FIELD",
                    ramiel.getHealth(), ramiel.getMaxHealth(),
                    ramiel.getAtFieldEnergy(), ramiel.getAtFieldMax(),
                    battle.clearTicks());
        }
        return new BattleStatus(true, "CLEAR CONFIRMATION",
                0.0F, 0.0F, 0.0F, 0.0F, battle.clearTicks());
    }

    public static BattleResult abort(ServerLevel level, BlockPos origin)
    {
        Tokyo3RamielBattleSavedData data =
                Tokyo3RamielBattleSavedData.get(level);
        StoredBattle battle = data.get(origin).orElse(null);
        if (battle == null)
        {
            return new BattleResult(false,
                    "Operation Yashima is not active.");
        }
        Entity entity = level.getEntity(battle.ramiel());
        if (entity != null)
        {
            entity.discard();
        }
        AngelAlarmSystem.disengage(level.getServer(), battle.ramiel());
        data.remove(origin);
        Tokyo3RetractionDirector.request(level, origin, false);
        broadcast(level, origin, Component.translatable("message.projectseele.yashima.aborted"));
        ProjectSeele.LOGGER.info(
                "Operation Yashima aborted: ramiel={} origin={}",
                battle.ramiel(), origin.toShortString());
        return new BattleResult(true,
                "Operation Yashima aborted; Tokyo-3 restoration requested.");
    }

    @SubscribeEvent
    public static void onServerTick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END)
        {
            return;
        }
        for (ServerLevel level : event.getServer().getAllLevels())
        {
            tickLevel(level);
        }
    }

    private static void tickLevel(ServerLevel level)
    {
        Tokyo3RamielBattleSavedData data =
                Tokyo3RamielBattleSavedData.get(level);
        for (StoredBattle battle : data.battles())
        {
            Entity entity = level.getEntity(battle.ramiel());
            if (entity instanceof RamielEntity ramiel && ramiel.isAlive())
            {
                if (battle.clearTicks() != 0)
                {
                    data.put(new StoredBattle(battle.origin(),
                            battle.ramiel(), 0));
                }
                continue;
            }
            boolean monitored = level.players().stream().anyMatch(player ->
                    player.blockPosition().closerThan(
                            battle.origin(), BATTLE_MONITOR_RANGE));
            if (!monitored)
            {
                continue;
            }
            int clearTicks = battle.clearTicks() + 1;
            if (clearTicks < RESTORE_DELAY_TICKS)
            {
                data.put(new StoredBattle(battle.origin(),
                        battle.ramiel(), clearTicks));
                continue;
            }

            data.remove(battle.origin());
            AngelAlarmSystem.disengage(level.getServer(), battle.ramiel());
            Tokyo3RetractionDirector.request(level, battle.origin(), false);
            broadcast(level, battle.origin(), Component.translatable("message.projectseele.yashima.victory"));
            ProjectSeele.LOGGER.info(
                    "Operation Yashima complete: ramiel={} origin={} clearDelay={}",
                    battle.ramiel(), battle.origin().toShortString(),
                    RESTORE_DELAY_TICKS);
        }
    }

    private static void broadcast(ServerLevel level, BlockPos origin,
                                  Component message)
    {
        for (ServerPlayer player : level.players())
        {
            if (player.blockPosition().closerThan(origin,
                    BATTLE_MONITOR_RANGE))
            {
                player.displayClientMessage(message, false);
            }
        }
    }

    public record BattleResult(boolean accepted, String message) {}

    public record BattleStatus(boolean active, String phase,
                               float health, float maximumHealth,
                               float atField, float maximumAtField,
                               int clearTicks)
    {
        public String summary()
        {
            if (!this.active)
            {
                return "Operation Yashima: STANDBY";
            }
            return String.format(Locale.ROOT,
                    "Operation Yashima: %s HP %.0f/%.0f AT %.0f/%.0f clear=%d/%d",
                    this.phase, this.health, this.maximumHealth,
                    this.atField, this.maximumAtField,
                    this.clearTicks, RESTORE_DELAY_TICKS);
        }
    }
}

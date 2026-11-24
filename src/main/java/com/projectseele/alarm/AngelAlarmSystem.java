package com.projectseele.alarm;

import java.util.HashSet;
import java.util.Iterator;
import java.util.Set;
import java.util.UUID;

import com.projectseele.ProjectSeele;
import com.projectseele.network.ClientboundAlarmPacket;
import com.projectseele.network.SeeleNetwork;
import net.minecraft.ChatFormatting;
import net.minecraft.advancements.Advancement;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.game.ClientboundSetSubtitleTextPacket;
import net.minecraft.network.protocol.game.ClientboundSetTitleTextPacket;
import net.minecraft.network.protocol.game.ClientboundSetTitlesAnimationPacket;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Mob;

/**
 * Server-wide Angel attack alarm. Any {@link com.projectseele.entity.Angel}
 * that acquires a player target engages it; it stands down when no engaged
 * Angel remains alive with a target. Registering a new Angel entity requires
 * no extra wiring — the target-change event drives everything.
 */
public final class AngelAlarmSystem
{
    private static final Set<UUID> ENGAGED = new HashSet<>();
    private static final Set<Mob> TRACKED = new HashSet<>();
    /** Holds the alarm for a TV combat mission, whatever its Angels target (they fight EVAs, and never creative players). */
    private static final UUID MISSION = UUID.nameUUIDFromBytes("projectseele:tv-mission-alarm-r64".getBytes(java.nio.charset.StandardCharsets.UTF_8));

    private AngelAlarmSystem() {}

    public static void engage(Mob angel)
    {
        if (!com.projectseele.config.SeeleConfig.ALARM_ENABLED.get())
        {
            return;
        }
        boolean wasIdle = ENGAGED.isEmpty();
        if (ENGAGED.add(angel.getUUID()))
        {
            TRACKED.add(angel);
            if (wasIdle && angel.level().getServer() != null)
            {
                broadcastStart(angel.level().getServer(), angel);
            }
        }
    }

    public static void disengage(MinecraftServer server, UUID angelId)
    {
        if (ENGAGED.remove(angelId))
        {
            TRACKED.removeIf(mob -> mob.getUUID().equals(angelId));
            if (ENGAGED.isEmpty())
            {
                broadcastStop(server);
            }
        }
    }

    /** Periodic sweep: dead or distracted Angels stop holding the alarm. */
    public static void validate(MinecraftServer server)
    {
        Iterator<Mob> it = TRACKED.iterator();
        boolean removed = false;
        while (it.hasNext())
        {
            Mob angel = it.next();
            if (!angel.isAlive() || angel.isRemoved() || angel.getTarget() == null)
            {
                ENGAGED.remove(angel.getUUID());
                it.remove();
                removed = true;
            }
        }
        // A combat mission sounds the alarm from its alert phase until its Angel is confirmed dead or it ends,
        // and drops it while the mission pauses for its commander or has lost its Angel (MissionAudioR64).
        boolean mission = com.projectseele.config.SeeleConfig.ALARM_ENABLED.get()
                && com.projectseele.world.MissionAudioR64.missionActive(server);
        if (mission && !ENGAGED.contains(MISSION))
        {
            boolean wasIdle = ENGAGED.isEmpty();
            ENGAGED.add(MISSION);
            if (wasIdle) broadcastStart(server, null);
        }
        else if (!mission && ENGAGED.remove(MISSION))
        {
            removed = true;
        }
        if (removed && ENGAGED.isEmpty())
        {
            broadcastStop(server);
        }
    }

    /** Late joiners must hear the siren too. */
    public static void syncTo(ServerPlayer player)
    {
        SeeleNetwork.CHANNEL.send(
                net.minecraftforge.network.PacketDistributor.PLAYER.with(() -> player),
                new ClientboundAlarmPacket(!ENGAGED.isEmpty()));
    }

    public static void reset()
    {
        ENGAGED.clear();
        TRACKED.clear();
    }

    private static void broadcastStart(MinecraftServer server, Mob angel)
    {
        Component title = Component.translatable("title.projectseele.angel_alarm")
                .withStyle(ChatFormatting.DARK_RED, ChatFormatting.BOLD);
        Component subtitle = Component.translatable("subtitle.projectseele.angel_alarm")
                .withStyle(ChatFormatting.RED);
        for (ServerPlayer player : server.getPlayerList().getPlayers())
        {
            player.connection.send(new ClientboundSetTitlesAnimationPacket(5, 50, 15));
            player.connection.send(new ClientboundSetSubtitleTextPacket(subtitle));
            player.connection.send(new ClientboundSetTitleTextPacket(title));
            // Witnessing the attack begins the story chain (a mission alarm has no Angel to witness yet).
            if (angel != null && player.level() == angel.level()
                    && player.distanceToSqr(angel) < 192.0D * 192.0D)
            {
                award(player, "witness_angel");
            }
        }
        SeeleNetwork.CHANNEL.send(net.minecraftforge.network.PacketDistributor.ALL.noArg(),
                new ClientboundAlarmPacket(true));
        // R65: the siren's on and off are the checkpoints for "does the alarm end when the Angel dies".
        ProjectSeele.LOGGER.info("Angel alarm on: {}", angel == null ? "combat mission alert" : net.minecraft.world.entity.EntityType.getKey(angel.getType()) + " " + angel.getUUID());
    }

    private static void broadcastStop(MinecraftServer server)
    {
        SeeleNetwork.CHANNEL.send(net.minecraftforge.network.PacketDistributor.ALL.noArg(),
                new ClientboundAlarmPacket(false));
        ProjectSeele.LOGGER.info("Angel alarm off: no engaged Angel and no combat mission holds it");
    }

    /** Grants a mod advancement; silently ignores ones that do not exist yet. */
    public static void award(ServerPlayer player, String path)
    {
        Advancement advancement = player.server.getAdvancements()
                .getAdvancement(new ResourceLocation(ProjectSeele.MODID, path));
        if (advancement != null)
        {
            player.getAdvancements().award(advancement, "triggered");
        }
    }
}

package com.projectseele.world;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import com.projectseele.network.ClientboundHeadsetSoundPacket;
import com.projectseele.network.SeeleNetwork;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.network.PacketDistributor;

/**
 * Mission audio that must not depend on where a player stands (R64, owner's report on R63): the alert
 * phase's PA reaches every sortie participant at the ear, the city alarm follows the mission, and Ramiel's
 * attack echoes across the whole city.
 */
public final class MissionAudioR64
{
    public static final Set<String> COMBAT_PHASES = Set.of("alert", "approach", "combat");
    /** Participants this close to a NERV HQ speaker hear the room PA already; a second copy would double it. */
    private static final double NEAR_SPEAKER = 48;
    /** Players within this range of a city-wide attack hear its distant echo, louder nearer. */
    public static final double ECHO_RANGE = 1500;
    private static final float ECHO_NEAR = .8F;
    private static final float ECHO_FAR = .35F;

    private MissionAudioR64() {}

    /** The mission owner, every sortie commander and every player pilot, online. */
    public static List<ServerPlayer> participants(ServerLevel level, TvCampaignSavedData data)
    {
        var ids = new LinkedHashSet<UUID>();
        if (data.owner != null) ids.add(data.owner);
        for (var sortie : data.sorties.values())
        {
            if (sortie.commander != null) ids.add(sortie.commander);
            if (!sortie.npc && sortie.pilotR45 != null) ids.add(sortie.pilotR45);
        }
        var list = level.getServer().getPlayerList();
        return ids.stream().map(list::getPlayer).filter(p -> p != null).toList();
    }

    public static void headset(ServerPlayer player, SoundEvent sound, SoundSource source, float volume, float pitch)
    {
        SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(() -> player),
                new ClientboundHeadsetSoundPacket(sound.getLocation(), source, volume, pitch, false));
    }

    /** To each participant not already standing by one of the given speakers. */
    public static void toParticipants(ServerLevel level, TvCampaignSavedData data, SoundEvent sound, SoundSource source, float volume,
                                      List<Vec3> speakers)
    {
        for (var player : participants(level, data))
        {
            boolean near = player.level() == level
                    && speakers.stream().anyMatch(s -> s.distanceToSqr(player.getEyePosition()) < NEAR_SPEAKER * NEAR_SPEAKER);
            if (!near) headset(player, sound, source, volume, 1F);
        }
    }

    /** The distant echo of a city-wide event at {@code origin}, for every player in the level within ECHO_RANGE. */
    public static void echo(ServerLevel level, Vec3 origin, SoundEvent sound, SoundSource source)
    {
        for (var player : level.players())
        {
            double distance = player.getEyePosition().distanceTo(origin);
            if (distance > ECHO_RANGE) continue;
            float volume = (float) (ECHO_NEAR - (ECHO_NEAR - ECHO_FAR) * (distance / ECHO_RANGE));
            SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(() -> player),
                    new ClientboundHeadsetSoundPacket(sound.getLocation(), source, volume, 1F, true));
        }
    }

    /** True while any level runs a TV combat mission between its alert and the confirmed end of its Angel. */
    public static boolean missionActive(MinecraftServer server)
    {
        for (var level : server.getAllLevels())
        {
            var data = TvCampaignSavedData.peek(level);
            if (data != null && !data.active.isEmpty() && COMBAT_PHASES.contains(data.phase) && !data.targetDeathConfirmedR45)
                return true;
        }
        return false;
    }
}

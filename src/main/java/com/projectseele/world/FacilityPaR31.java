package com.projectseele.world;

import com.projectseele.registry.ModSounds;
import net.minecraft.network.protocol.game.ClientboundStopSoundPacket;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.phys.Vec3;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;

/** Nearby cages share a PA circuit; obsolete phase announcements are never queued. */
public final class FacilityPaR31
{
    private record Transmission(Vec3 position, String clip, long started, long until) {}
    private static final Map<ServerLevel, List<Transmission>> ACTIVE = new WeakHashMap<>();
    private static final Map<ServerLevel, List<Transmission>> WARNINGS = new WeakHashMap<>();
    private static final Map<String,Integer> CLIP_TICKS=loadDurations();
    private static Map<String,Integer> loadDurations()
    {
        try(var stream=FacilityPaR31.class.getResourceAsStream("/assets/projectseele/audio/facility_voice_r45.json"))
        {
            if(stream==null)return Map.of();
            var root=com.google.gson.JsonParser.parseReader(new java.io.InputStreamReader(stream,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonArray();
            var result=new java.util.HashMap<String,Integer>();
            for(var item:root){var row=item.getAsJsonObject();int ticks=row.get("minimum_sequence_ticks").getAsInt();if(ticks<1||ticks>600)throw new IllegalArgumentException("Facility clip duration");result.put(row.get("name").getAsString(),ticks);}
            return Map.copyOf(result);
        }
        catch(Exception error){throw new IllegalStateException("Facility voice timing resource rejected",error);}
    }

    private static List<Transmission> active(ServerLevel level)
    {
        var active = ACTIVE.computeIfAbsent(level, key -> new ArrayList<>());
        long now = level.getGameTime();
        active.removeIf(sound -> now < sound.started() || now >= sound.until());
        return active;
    }

    public static boolean busy(ServerLevel level, Vec3 position)
    {
        return active(level).stream().anyMatch(sound -> sound.position().distanceToSqr(position) < 140 * 140);
    }

    public static void announce(ServerLevel level, Vec3 position, String clip)
    {
        boolean countdown = clip.equals("pa_1") || clip.equals("pa_2") || clip.equals("pa_3") || clip.equals("pa_launch");
        var active = active(level);
        long now = level.getGameTime();
        for (var sound : active)
        {
            if (sound.position().distanceToSqr(position) >= 140 * 140) continue;
            if (sound.clip().equals(clip) || !countdown) return;
        }
        if (countdown)
        {
            for (var iterator = active.iterator(); iterator.hasNext();)
            {
                var previous = iterator.next();
                if (previous.position().distanceToSqr(position) >= 140 * 140) continue;
                for (var player : level.players())
                    if (player.position().distanceToSqr(previous.position()) < 240 * 240)
                        player.connection.send(new ClientboundStopSoundPacket(
                                new ResourceLocation("projectseele", previous.clip()), SoundSource.BLOCKS));
                iterator.remove();
            }
        }
        // Countdown clips must stay on the mechanism's actual second. Ordinary
        // reports can be omitted; delaying them would describe a phase already over.
        level.playSound(null, position.x, position.y, position.z,
                ModSounds.FACILITY.get(clip).get(), SoundSource.BLOCKS, 1.05F, 1);
        active.add(new Transmission(position, clip, now, now + durationTicks(clip)));
    }

    public static void warning(ServerLevel level, Vec3 position)
    {
        if (busy(level, position)) return;
        long now = level.getGameTime();
        var warnings = WARNINGS.computeIfAbsent(level, key -> new ArrayList<>());
        warnings.removeIf(sound -> now < sound.started() || now >= sound.until());
        if (warnings.stream().anyMatch(sound -> sound.position().distanceToSqr(position) < 140 * 140)) return;
        level.playSound(null, position.x, position.y, position.z,
                ModSounds.FACILITY.get("facility_siren").get(), SoundSource.BLOCKS, .48F, 1);
        warnings.add(new Transmission(position, "facility_siren", now, now + 60));
    }

    private static int durationTicks(String clip)
    {
        if(CLIP_TICKS.containsKey(clip))return CLIP_TICKS.get(clip);
        return switch (clip)
        {
            case "pa_1", "pa_2" -> 15;
            case "pa_3" -> 16;
            case "pa_launch" -> 19;
            case "pa_insert", "pa_lock" -> 30;
            case "pa_drain" -> 26;
            case "pa_return" -> 35;
            case "pa_standby" -> 33;
            case "pa_prepare", "pa_ready", "pa_recover" -> 60;
            case "pa_transfer", "pa_door_close" -> 59;
            case "pa_fill" -> 56;
            case "pa_fault" -> 68;
            case "pa_door_open" -> 61;
            case "pa_combat_r31" -> 66;
            default -> 80;
        };
    }

    private FacilityPaR31() {}
}

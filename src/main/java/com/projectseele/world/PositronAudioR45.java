package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModSounds;
import net.minecraft.core.Holder;
import net.minecraft.network.protocol.game.ClientboundSoundPacket;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.ModList;
import net.minecraftforge.fml.common.Mod;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.WeakHashMap;

/** Event references only: no Superb Warfare recordings are shipped by SEELE. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class PositronAudioR45
{
    private record Layer(String event, float volume) {}
    private record Pending(UUID listener, Vec3 position, SoundEvent event, float volume,
                           long queued, long due) {}
    private static final List<Layer> EXTERIOR = List.of(
            new Layer("annihilator_fire_3p", 12.8F),
            new Layer("annihilator_far", 22.4F),
            new Layer("annihilator_veryfar", 32.0F));
    private static final Map<ServerLevel, List<Pending>> PENDING = new WeakHashMap<>();
    private static final Map<ServerLevel, Map<UUID, Long>> LAST_FIRE = new WeakHashMap<>();

    /** Call once after authoritative fire succeeds; muzzle is supplied by the weapon owner. */
    public static void fire(ServerLevel level, Entity cannon, ServerPlayer pilot, Vec3 muzzle)
    {
        long now = level.getGameTime();
        var last = LAST_FIRE.computeIfAbsent(level, ignored -> new HashMap<>());
        last.entrySet().removeIf(entry -> now < entry.getValue() || now - entry.getValue() > 200);
        if (Long.valueOf(now).equals(last.put(cannon.getUUID(), now))) return;
        if (!ModList.get().isLoaded("superbwarfare"))
        {
            // The fallback is the existing CC0 recorded heavy contact, not the old synthetic beam.
            level.playSound(null, muzzle.x, muzzle.y, muzzle.z,
                    ModSounds.EVA_IMPACT_HEAVY.get(), SoundSource.PLAYERS, .7F, 1.0F);
            return;
        }
        if (pilot != null && pilot.level() == level)
            send(pilot, pilot.position(), event("annihilator_fire_1p"), 1.0F);
        for (var player : level.players())
        {
            if (player == pilot) continue;
            double distance = player.position().distanceTo(muzzle);
            long due = now + (long) (distance / 17.0D);
            for (var layer : EXTERIOR)
            {
                if (distance >= layer.volume() * 16.0D) continue;
                var sound = event(layer.event());
                if (due == now) send(player, muzzle, sound, layer.volume());
                else PENDING.computeIfAbsent(level, ignored -> new ArrayList<>()).add(
                        new Pending(player.getUUID(), muzzle, sound, layer.volume(), now, due));
            }
        }
    }

    /** Optional hook for actual rearm completion; never schedules the SBW 80-tick reload onto EVA. */
    public static void rearmed(ServerLevel level, Vec3 muzzle)
    {
        if (ModList.get().isLoaded("superbwarfare"))
            level.playSound(null, muzzle.x, muzzle.y, muzzle.z,
                    event("annihilator_reload"), SoundSource.PLAYERS, 1.0F, 1.0F);
    }

    private static SoundEvent event(String path)
    {
        // SBW resolves resource events dynamically; registry absence does not mean missing audio.
        return SoundEvent.createVariableRangeEvent(new ResourceLocation("superbwarfare", path));
    }

    private static void send(ServerPlayer player, Vec3 position, SoundEvent event, float volume)
    {
        player.connection.send(new ClientboundSoundPacket(Holder.direct(event), SoundSource.PLAYERS,
                position.x, position.y, position.z, volume, 1.0F, player.getRandom().nextLong()));
    }

    @SubscribeEvent
    public static void tick(TickEvent.LevelTickEvent tick)
    {
        if (tick.phase != TickEvent.Phase.END || !(tick.level instanceof ServerLevel level)) return;
        var pending = PENDING.get(level);
        if (pending == null) return;
        long now = level.getGameTime();
        pending.removeIf(sound ->
        {
            if (now < sound.queued()) return true;
            if (now < sound.due()) return false;
            var player = level.getServer().getPlayerList().getPlayer(sound.listener());
            if (player != null && player.level() == level)
                send(player, sound.position(), sound.event(), sound.volume());
            return true;
        });
        if (pending.isEmpty()) PENDING.remove(level);
    }

    private PositronAudioR45() {}
}

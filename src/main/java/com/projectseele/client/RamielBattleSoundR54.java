package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.network.ClientboundEncounterObserverPacket;
import com.projectseele.registry.ModSounds;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.UUID;

/** Audible mission shots beyond vanilla's 80-block sound broadcast range. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class RamielBattleSoundR54
{
    private static ClientLevel level;
    private static UUID session;
    private static long generation;
    private static boolean charging, firing;
    private static int sustainTicks;

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END) return;
        var mc = Minecraft.getInstance();
        if (mc.isPaused()) return;
        var view = EncounterObserverCacheR45.freshView().orElse(null);
        if (mc.level == null || mc.player == null || level != null && level != mc.level)
        { level = null; session = null; charging = firing = false; sustainTicks = 0; return; }
        if (view == null) return;
        var packet = view.current();
        var state = packet.snapshot();
        if (level != mc.level || !state.target().equals(session) || packet.generation() != generation)
        { level = mc.level; session = state.target(); generation = packet.generation(); charging = firing = false; sustainTicks = 0; }
        boolean nextCharge = (state.flags() & ClientboundEncounterObserverPacket.CHARGING) != 0;
        boolean nextFire = state.beamTicks() > 0;
        boolean distant = mc.player.distanceToSqr(state.position()) > 96 * 96;
        if (distant && nextCharge && !charging) play(state.position(), ModSounds.BEAM_CHARGE.get(), 1.15F, .75F);
        if (distant && nextFire && !firing)
        { play(state.beamEnd(), ModSounds.BEAM_FIRE.get(), 2.0F, .72F); sustainTicks = 0; }
        if (nextFire && state.beamTicks() > view.ageClientTicks() && ++sustainTicks % 20 == 0 && distant)
            play(state.beamEnd(), ModSounds.RAMIEL_HUM.get(), .85F, .55F);
        if (!nextFire) sustainTicks = 0;
        charging = nextCharge; firing = nextFire;
    }

    private static void play(Vec3 source, SoundEvent sound, float volume, float pitch)
    {
        var mc = Minecraft.getInstance();
        Vec3 ear = mc.gameRenderer.getMainCamera().getPosition(), delta = source.subtract(ear);
        // Preserve direction while keeping a kilometre-range battle audible at the firing position.
        Vec3 audible = ear.add(delta.normalize().scale(Math.min(8, delta.length())));
        mc.level.playLocalSound(audible.x, audible.y, audible.z, sound, SoundSource.HOSTILE, volume, pitch, false);
    }

    private RamielBattleSoundR54() {}
}

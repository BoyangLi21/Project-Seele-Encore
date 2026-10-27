package com.projectseele.client;

import com.projectseele.registry.ModSounds;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.client.Minecraft;
import net.minecraft.client.resources.sounds.AbstractSoundInstance;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.RandomSource;
import net.minecraft.world.phys.Vec3;

/** Pilot-only shot audio, dispatched by the existing authoritative tracer packet. */
public final class RifleShotAudioR53
{
    public static void confirmedShot(int entityId, Vec3 muzzle)
    {
        var minecraft = Minecraft.getInstance();
        if (minecraft.player == null || minecraft.level == null) return;
        var controlled = EvaPilotResolver.controlTarget(minecraft.player);
        if (controlled == null || controlled.getId() != entityId) return;

        boolean firstPerson = minecraft.options.getCameraType().isFirstPerson();
        var requested = new ResourceLocation("superbwarfare", firstPerson ? "ntw_20_fire_1p" : "ntw_20_fire_3p");
        var location = minecraft.getSoundManager().getSoundEvent(requested) != null
                ? requested : ModSounds.EVA_RIFLE_FIRE.get().getLocation();
        float pitch = .93F + minecraft.level.random.nextFloat() * .08F;
        minecraft.getSoundManager().play(new Shot(SoundEvent.createFixedRangeEvent(location, 512F),
                muzzle, firstPerson, pitch));
    }

    private static final class Shot extends AbstractSoundInstance
    {
        private Shot(SoundEvent sound, Vec3 muzzle, boolean firstPerson, float shotPitch)
        {
            super(sound, SoundSource.PLAYERS, RandomSource.create());
            this.relative = firstPerson;
            this.attenuation = firstPerson ? Attenuation.NONE : Attenuation.LINEAR;
            this.volume = firstPerson ? 1F : 12F;
            this.pitch = shotPitch;
            this.x = firstPerson ? 0 : muzzle.x;
            this.y = firstPerson ? 0 : muzzle.y;
            this.z = firstPerson ? 0 : muzzle.z;
        }
    }

    private RifleShotAudioR53() {}
}
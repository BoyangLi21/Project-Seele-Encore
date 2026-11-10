package com.projectseele.client.sound;

import com.mojang.blaze3d.audio.Channel;
import com.projectseele.ProjectSeele;
import com.projectseele.mixin.client.SoundChannelAccessorR61;
import net.minecraft.client.Minecraft;
import net.minecraft.client.resources.sounds.SimpleSoundInstance;
import net.minecraft.client.resources.sounds.SoundInstance;
import net.minecraft.client.sounds.SoundManager;
import net.minecraft.client.sounds.WeighedSoundEvents;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.sound.PlaySoundEvent;
import net.minecraftforge.client.event.sound.PlaySoundSourceEvent;
import net.minecraftforge.client.event.sound.PlayStreamingSourceEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.lwjgl.openal.AL10;
import org.lwjgl.openal.AL11;
import org.lwjgl.openal.ALC10;
import org.lwjgl.openal.EXTEfx;

/** Facility announcements take the acoustics of the space the listener is standing in. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class VenueReverbR61
{
    public enum Venue
    {
        OPEN(.55F, .60F, .40F, .55F, 3.2F, .60F, .30F, .120F, .85F, .10F, .25F, .30F),
        CAVERN(1F, .90F, .55F, .40F, 8.5F, .45F, .22F, .150F, 1.2F, .10F, .25F, 0F),
        HANGAR(1F, .95F, .60F, .55F, 5.2F, .55F, .55F, .060F, 1.4F, .06F, .25F, 0F),
        SHAFT(.75F, .55F, .55F, .65F, 4.2F, .70F, .75F, .030F, 1.2F, .04F, .12F, .25F),
        ROOM(.90F, 1F, .45F, .75F, 1.6F, .80F, .60F, .012F, 1F, .02F, .25F, 0F);

        final float density, diffusion, gain, gainHf, decay, decayHf, reflections, reflectionsDelay, late, lateDelay, echoTime, echoDepth;

        Venue(float density, float diffusion, float gain, float gainHf, float decay, float decayHf, float reflections,
              float reflectionsDelay, float late, float lateDelay, float echoTime, float echoDepth)
        {
            this.density = density;
            this.diffusion = diffusion;
            this.gain = gain;
            this.gainHf = gainHf;
            this.decay = decay;
            this.decayHf = decayHf;
            this.reflections = reflections;
            this.reflectionsDelay = reflectionsDelay;
            this.late = late;
            this.lateDelay = lateDelay;
            this.echoTime = echoTime;
            this.echoDepth = echoDepth;
        }
    }

    private static final String BAKED_PREFIX = "hangar_";
    private static final String BAKED_SUFFIX = "_r46";
    private static final float PROBE_RANGE = 128F;
    private static final float CAVERN_CEILING = -128F;
    private static final int[][] DIRECTIONS = directions();
    // Reverberant level falls off more slowly than the direct path, so a far
    // speaker reads as distant instead of simply quieter.
    private static final float WET_DISTANCE_ROLLOFF = .7F;

    private static volatile Venue current = Venue.OPEN;
    private static int tick;
    private static long context;
    private static int effect;
    private static int slot;
    private static Venue loaded;

    private static int[][] directions()
    {
        var result = new int[26][];
        int index = 0;
        for (int x = -1; x <= 1; x++)
        {
            for (int y = -1; y <= 1; y++)
            {
                for (int z = -1; z <= 1; z++)
                {
                    if (x != 0 || y != 0 || z != 0) result[index++] = new int[]{x, y, z};
                }
            }
        }
        return result;
    }

    public static Venue classify(boolean deepGeoFront, boolean skyVisible, float[] lengths, float range)
    {
        int open = 0;
        float total = 0, horizontal = 0;
        int horizontalCount = 0;
        float vertical = 0;
        for (int index = 0; index < lengths.length; index++)
        {
            float length = lengths[index];
            if (length >= range - .5F) open++;
            total += length;
            int[] direction = DIRECTIONS[index];
            if (direction[1] == 0)
            {
                horizontal += length;
                horizontalCount++;
            }
            else if (direction[0] == 0 && direction[2] == 0)
            {
                vertical = Math.max(vertical, length);
            }
        }
        float openness = open / (float) lengths.length;
        float mean = total / lengths.length;
        float wide = horizontal / horizontalCount;
        if (skyVisible && openness >= .4F) return Venue.OPEN;
        if (deepGeoFront && (openness >= .25F || mean >= 90F)) return Venue.CAVERN;
        if (vertical >= 72F && wide <= 26F) return Venue.SHAFT;
        return mean >= 24F ? Venue.HANGAR : Venue.ROOM;
    }

    @SubscribeEvent
    public static void clientTick(TickEvent.ClientTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END || ++tick % 20 != 0) return;
        var minecraft = Minecraft.getInstance();
        if (minecraft.level == null || minecraft.player == null) return;
        var player = minecraft.player;
        Vec3 ear = minecraft.gameRenderer.getMainCamera().getPosition();
        var lengths = new float[DIRECTIONS.length];
        for (int index = 0; index < lengths.length; index++)
        {
            int[] d = DIRECTIONS[index];
            var target = ear.add(new Vec3(d[0], d[1], d[2]).normalize().scale(PROBE_RANGE));
            var hit = minecraft.level.clip(new ClipContext(ear, target, ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, player));
            lengths[index] = hit.getType() == HitResult.Type.MISS ? PROBE_RANGE : (float) ear.distanceTo(hit.getLocation());
        }
        boolean deep = ear.y < CAVERN_CEILING && "projectseele:geofront".equals(minecraft.level.dimension().location().toString());
        current = classify(deep, minecraft.level.canSeeSky(BlockPos.containing(ear)), lengths, PROBE_RANGE);
    }

    /** The server keeps sending wet takes to hangars, so a client without EFX still hears the room. */
    @SubscribeEvent
    public static void replaceBakedTake(PlaySoundEvent event)
    {
        var baked = event.getOriginalSound();
        var id = baked.getLocation();
        String path = id.getPath();
        if (!ProjectSeele.MODID.equals(id.getNamespace()) || !path.startsWith(BAKED_PREFIX + "pa_") || !path.endsWith(BAKED_SUFFIX)) return;
        if (!ready() || baked.resolve(Minecraft.getInstance().getSoundManager()) == null) return;
        var dry = new ResourceLocation(ProjectSeele.MODID, path.substring(BAKED_PREFIX.length(), path.length() - BAKED_SUFFIX.length()));
        event.setSound(new DryTake(baked, dry));
    }

    @SubscribeEvent
    public static void staticSource(PlaySoundSourceEvent event)
    {
        attach(event.getSound(), event.getChannel());
    }

    @SubscribeEvent
    public static void streamedSource(PlayStreamingSourceEvent event)
    {
        attach(event.getSound(), event.getChannel());
    }

    private static boolean announcement(SoundInstance sound)
    {
        var id = sound.getLocation();
        return sound instanceof DryTake || ProjectSeele.MODID.equals(id.getNamespace()) && id.getPath().startsWith("pa_");
    }

    /** Called from the render thread for take selection and the sound thread for sends. */
    private static synchronized boolean ready()
    {
        long active = ALC10.alcGetCurrentContext();
        if (active == context) return slot != 0;
        context = active;
        slot = 0;
        loaded = null;
        if (active == 0L || !ALC10.alcIsExtensionPresent(ALC10.alcGetContextsDevice(active), "ALC_EXT_EFX"))
        {
            ProjectSeele.LOGGER.warn("OpenAL EFX is unavailable; hangars keep their recorded reverb, other announcements stay dry");
            return false;
        }
        AL10.alGetError();
        effect = EXTEfx.alGenEffects();
        EXTEfx.alEffecti(effect, EXTEfx.AL_EFFECT_TYPE, EXTEfx.AL_EFFECT_EAXREVERB);
        int created = EXTEfx.alGenAuxiliaryEffectSlots();
        int error = AL10.alGetError();
        if (error != AL10.AL_NO_ERROR)
        {
            ProjectSeele.LOGGER.warn("OpenAL EFX reverb rejected (0x{}); hangars keep their recorded reverb, other announcements stay dry", Integer.toHexString(error));
            return false;
        }
        slot = created;
        ProjectSeele.LOGGER.info("OpenAL EFX reverb ready for facility announcements");
        return true;
    }

    private static void load(Venue venue)
    {
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_DENSITY, venue.density);
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_DIFFUSION, venue.diffusion);
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_GAIN, venue.gain);
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_GAINHF, venue.gainHf);
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_GAINLF, 1F);
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_DECAY_TIME, venue.decay);
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_DECAY_HFRATIO, venue.decayHf);
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_DECAY_LFRATIO, 1F);
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_REFLECTIONS_GAIN, venue.reflections);
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_REFLECTIONS_DELAY, venue.reflectionsDelay);
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_LATE_REVERB_GAIN, venue.late);
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_LATE_REVERB_DELAY, venue.lateDelay);
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_ECHO_TIME, venue.echoTime);
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_ECHO_DEPTH, venue.echoDepth);
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_MODULATION_TIME, .25F);
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_MODULATION_DEPTH, 0F);
        EXTEfx.alEffectf(effect, EXTEfx.AL_EAXREVERB_AIR_ABSORPTION_GAINHF, .994F);
        EXTEfx.alEffecti(effect, EXTEfx.AL_EAXREVERB_DECAY_HFLIMIT, AL10.AL_TRUE);
        EXTEfx.alAuxiliaryEffectSloti(slot, EXTEfx.AL_EFFECTSLOT_EFFECT, effect);
        loaded = venue;
    }

    private static void attach(SoundInstance sound, Channel channel)
    {
        if (!announcement(sound) || !ready()) return;
        Venue venue = current;
        if (venue != loaded) load(venue);
        int source = ((SoundChannelAccessorR61) channel).seele$source();
        AL11.alSource3i(source, EXTEfx.AL_AUXILIARY_SEND_FILTER, slot, 0, EXTEfx.AL_FILTER_NULL);
        AL10.alSourcef(source, EXTEfx.AL_ROOM_ROLLOFF_FACTOR, WET_DISTANCE_ROLLOFF);
    }

    /** Keeps the baked event's name so the server's stop packets still reach it, but plays the dry recording. */
    private static final class DryTake extends SimpleSoundInstance
    {
        private final ResourceLocation dry;

        private DryTake(SoundInstance baked, ResourceLocation dry)
        {
            super(baked.getLocation(), baked.getSource(), baked.getVolume(), baked.getPitch(), SoundInstance.createUnseededRandom(),
                    baked.isLooping(), baked.getDelay(), baked.getAttenuation(), baked.getX(), baked.getY(), baked.getZ(), baked.isRelative());
            this.dry = dry;
        }

        @Override
        public WeighedSoundEvents resolve(SoundManager manager)
        {
            var events = manager.getSoundEvent(this.dry);
            this.sound = events == null ? SoundManager.EMPTY_SOUND : events.getSound(this.random);
            return events;
        }
    }

    private VenueReverbR61() { }
}

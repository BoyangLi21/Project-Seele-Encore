package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.client.Minecraft;
import net.minecraft.util.Mth;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ViewportEvent;
import net.minecraftforge.client.event.sound.PlaySoundEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * Weight in the pilot's view: every footfall of a sixty-metre body dips the
 * camera a fraction of a degree, and a positron shot punches the field of view.
 * Kicks never touch pitch while a sight or scope is up, so aim stays put.
 * <p>
 * Kicks add up (R63): a landing during a shot, a footfall under a blow each keep their own. One running kick
 * used to drop every weaker one that came while it lasted. Together they bend over towards a most and never pass
 * it, so no run of kicks turns into a spin; one kick alone is as large as it was.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class CameraKickR58
{
    /** Kicks that can run at once; a new one takes the place of the one that has died out furthest. */
    private static final int SLOTS = 4;
    private static final long[] startNanos = new long[SLOTS];
    private static final float[] pitchAmount = new float[SLOTS], rollAmount = new float[SLOTS], fovAmount = new float[SLOTS], decayTicks = new float[SLOTS];
    /** The most all kicks together turn the view (degrees) or widen it (fraction). */
    public static final float MOST_PITCH = 4F, MOST_ROLL = 3F, MOST_FOV = .12F;
    /** Up to this share of the most the kicks add up plainly; past it the sum bends over. */
    private static final float PLAIN = .7F;
    static
    {
        java.util.Arrays.fill(startNanos, Long.MIN_VALUE);
        java.util.Arrays.fill(decayTicks, 1F);
    }

    /** -Dprojectseele.poseDiag=true: every kick, and how many others were still running when it came, goes to the log. */
    static final boolean TOLD = Boolean.getBoolean("projectseele.poseDiag");

    private CameraKickR58() {}

    /** pitch/roll in degrees (positive pitch looks down), fov as a fraction, decay in ticks. */
    public static void kick(float pitch, float roll, float fov, float decay)
    {
        float scale = com.projectseele.config.SeeleConfig.FX_INTENSITY.get().floatValue();
        if (scale <= 0) return;
        int slot = 0;
        float weakest = Float.MAX_VALUE;
        for (int i = 0; i < SLOTS; i++)
        {
            float size = (Math.abs(pitchAmount[i]) + Math.abs(rollAmount[i]) + Math.abs(fovAmount[i]) * 20) * left(i);
            if (size < weakest) { weakest = size; slot = i; }
        }
        if (TOLD)
        {
            int running = 0;
            float pitchSum = Math.abs(pitch * scale), fovSum = Math.abs(fov * scale);
            for (int i = 0; i < SLOTS; i++)
            {
                if (i == slot || left(i) <= .05F) continue;
                running++; pitchSum += Math.abs(pitchAmount[i]) * left(i); fovSum += Math.abs(fovAmount[i]) * left(i);
            }
            ProjectSeele.LOGGER.info("R63KICK pitch {} roll {} fov {} decay {}: {} others running, together pitch {} (drawn {}) fov {} (drawn {})",
                    pitch * scale, roll * scale, fov * scale, decay, running, pitchSum, bend(pitchSum, MOST_PITCH), fovSum, bend(fovSum, MOST_FOV));
        }
        pitchAmount[slot] = pitch * scale; rollAmount[slot] = roll * scale; fovAmount[slot] = fov * scale; decayTicks[slot] = Math.max(1, decay);
        startNanos[slot] = System.nanoTime();
    }

    private static float age(int slot)
    {
        return startNanos[slot] == Long.MIN_VALUE ? 1e6F : (System.nanoTime() - startNanos[slot]) / 50_000_000F;
    }

    /** How much of a kick is left, 1 to 0. */
    private static float left(int slot)
    {
        float t = age(slot);
        return t > decayTicks[slot] * 8 ? 0 : (float) Math.exp(-t / decayTicks[slot]);
    }

    /** The sum of the running kicks, plain up to a share of the most and bent over towards the most past it. */
    private static float bend(float sum, float most)
    {
        float plain = most * PLAIN, size = Math.abs(sum);
        return size <= plain ? sum : Math.copySign(plain + (most - plain) * (float) Math.tanh((size - plain) / (most - plain)), sum);
    }

    private static EvaUnit01Entity piloted()
    {
        var mc = Minecraft.getInstance();
        if (mc.player == null || mc.getCameraEntity() != mc.player) return null;
        return EvaPilotResolver.controlTarget(mc.player);
    }

    @SubscribeEvent
    public static void footfall(PlaySoundEvent event)
    {
        var sound = event.getSound();
        if (sound == null) return;
        var id = sound.getLocation();
        if (!id.getNamespace().equals(ProjectSeele.MODID)) return;
        String path = id.getPath();
        boolean step = path.startsWith("eva_foot");
        boolean land = path.equals("eva_land");
        boolean blow = path.equals("eva_impact") || path.equals("eva_armor_impact") || path.equals("eva_core_break");
        if (!step && !land && !blow) return;
        var mc = Minecraft.getInstance();
        if (mc.player == null) return;
        var eva = EvaPilotResolver.controlTarget(mc.player);
        if (eva == null || eva.isNervLogisticsLocked()) return;
        double dx = sound.getX() - eva.getX(), dz = sound.getZ() - eva.getZ();
        if (dx * dx + dz * dz > 45 * 45) return;
        boolean ownView = mc.getCameraEntity() == mc.player;
        // Ordinary combat blows already shake the view through the combat
        // beats; the scripted finale has none, so its blows land here.
        if (blow)
        {
            if (eva.isFirstBattleActive())
            {
                boolean core = path.equals("eva_core_break");
                if (ownView) kick(core ? 2.6F : 1.7F, (dx > 0 ? 1 : -1) * .9F, .03F, 5);
                com.projectseele.client.fx.ClientFxManager.addImpactBurst(
                        new net.minecraft.world.phys.Vec3(sound.getX(), sound.getY(), sound.getZ()), core ? 1.6F : 1.1F);
            }
            return;
        }
        if (!ownView || eva.isFirstBattleActive() || dx * dx + dz * dz > 30 * 30) return;
        if (land) kick(1.6F, 0, .012F, 5);
        else kick(.32F, (float) Math.signum(dx * eva.getForward().z - dz * eva.getForward().x) * .12F, 0, 3.2F);
    }

    @SubscribeEvent
    public static void camera(ViewportEvent.ComputeCameraAngles event)
    {
        float pitch = 0, roll = 0;
        for (int i = 0; i < SLOTS; i++)
        {
            float envelope = left(i);
            if (envelope <= 0) continue;
            // Down first, a small rebound after: the body takes the load and recovers.
            float wave = envelope * Mth.cos(age(i) * 1.3F);
            pitch += pitchAmount[i] * wave; roll += rollAmount[i] * wave;
        }
        if (pitch == 0 && roll == 0) return;
        var eva = piloted();
        if (eva == null) return;
        boolean sighted = ClientForgeEvents.isRifleSightActive(eva) || ClientForgeEvents.isCannonScopeActive(eva);
        if (!sighted) event.setPitch(event.getPitch() + bend(pitch, MOST_PITCH));
        event.setRoll(event.getRoll() + bend(roll, MOST_ROLL));
    }

    @SubscribeEvent
    public static void fov(ViewportEvent.ComputeFov event)
    {
        float widen = 0;
        for (int i = 0; i < SLOTS; i++) widen += fovAmount[i] * left(i);
        if (widen == 0 || piloted() == null) return;
        event.setFOV(event.getFOV() * (1 + bend(widen, MOST_FOV)));
    }
}

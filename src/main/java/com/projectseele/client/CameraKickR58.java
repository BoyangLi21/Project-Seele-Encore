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
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class CameraKickR58
{
    private static long startNanos = Long.MIN_VALUE;
    private static float pitchAmount, rollAmount, fovAmount, decayTicks = 1;

    private CameraKickR58() {}

    /** pitch/roll in degrees (positive pitch looks down), fov as a fraction, decay in ticks. */
    public static void kick(float pitch, float roll, float fov, float decay)
    {
        float scale = com.projectseele.config.SeeleConfig.FX_INTENSITY.get().floatValue();
        if (scale <= 0) return;
        float t = age();
        float left = (float) Math.exp(-t / decayTicks);
        // A new kick replaces a weaker running one, never stacks into a spin.
        if (Float.isFinite(left) && Math.abs(pitchAmount * left) + Math.abs(rollAmount * left) + Math.abs(fovAmount * left) * 20
                > Math.abs(pitch * scale) + Math.abs(roll * scale) + Math.abs(fov * scale) * 20) return;
        pitchAmount = pitch * scale; rollAmount = roll * scale; fovAmount = fov * scale; decayTicks = Math.max(1, decay);
        startNanos = System.nanoTime();
    }

    private static float age()
    {
        return startNanos == Long.MIN_VALUE ? 1e6F : (System.nanoTime() - startNanos) / 50_000_000F;
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
        float t = age();
        if (t > decayTicks * 8) return;
        var eva = piloted();
        if (eva == null) return;
        float envelope = (float) Math.exp(-t / decayTicks);
        // Down first, a small rebound after: the body takes the load and recovers.
        float wave = envelope * Mth.cos(t * 1.3F);
        boolean sighted = ClientForgeEvents.isRifleSightActive(eva) || ClientForgeEvents.isCannonScopeActive(eva);
        if (!sighted) event.setPitch(event.getPitch() + pitchAmount * wave);
        event.setRoll(event.getRoll() + rollAmount * wave);
    }

    @SubscribeEvent
    public static void fov(ViewportEvent.ComputeFov event)
    {
        float t = age();
        if (fovAmount == 0 || t > decayTicks * 8) return;
        if (piloted() == null) return;
        float envelope = (float) Math.exp(-t / decayTicks);
        event.setFOV(event.getFOV() * (1 + fovAmount * envelope));
    }
}

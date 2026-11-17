package com.projectseele.client.cockpit;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.client.Minecraft;
import net.minecraft.core.particles.DustParticleOptions;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.util.RandomSource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Vector3f;

/**
 * R64: a capsule that leaves its Unit lets its LCL go, and anyone watching sees it: for two and a half seconds
 * from when it starts to rise on the crane or is thrown clear in the field, amber drops fall from its seams. Inside, the
 * pilot sees the level fall (PilotLclR64); this is the same moment from outside. Drawn only, with the game's own
 * particles; nothing is sent or changed.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class PlugLclSpillR64
{
    private static final int SPILL_TICKS = 50;
    private static final DustParticleOptions MIST = new DustParticleOptions(new Vector3f(1F, .52F, .12F), 1.1F);
    private static final class Seen { int stage = -1, left; boolean spilled; }
    private static final WeakIdentityMap<EntryPlugCarrierEntity, Seen> PLUGS = new WeakIdentityMap<>();

    private PlugLclSpillR64() {}

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event)
    {
        Minecraft mc = Minecraft.getInstance();
        if (!PilotCockpitR64.ON || event.phase != TickEvent.Phase.END || mc.level == null || mc.player == null || mc.isPaused()) return;
        RandomSource random = mc.level.random;
        for (EntryPlugCarrierEntity plug : mc.level.getEntitiesOfClass(EntryPlugCarrierEntity.class, mc.player.getBoundingBox().inflate(192)))
        {
            Seen seen = PLUGS.get(plug);
            if (seen == null) { seen = new Seen(); seen.stage = plug.getInsertionStage(); PLUGS.put(plug, seen); continue; }
            int stage = plug.getInsertionStage();
            // Out of the socket by its own charges: at once. Drawn out by the crane: the dorsal hatch opens first
            // with the capsule still seated, and the LCL goes when the capsule starts to rise.
            boolean thrown = seen.stage == EntryPlugCarrierEntity.STAGE_LOCKED && stage == EntryPlugCarrierEntity.STAGE_FIELD_EJECTING;
            boolean drawn = stage == EntryPlugCarrierEntity.STAGE_EJECTING && !seen.spilled && plug.getInsertionProgress() < 100;
            if (thrown || drawn) { seen.left = SPILL_TICKS; seen.spilled = true; }
            if (stage != EntryPlugCarrierEntity.STAGE_EJECTING && stage != EntryPlugCarrierEntity.STAGE_FIELD_EJECTING) seen.spilled = false;
            seen.stage = stage;
            if (seen.left <= 0 || !plug.hasCanonicalPose() || !plug.isShellVisible()) { if (seen.left > 0) seen.left--; continue; }
            float strength = seen.left-- / (float) SPILL_TICKS;
            // Not for the pilot looking out of this very capsule: the drops from the hatch seam fall through the cabin
            // (particles pass through a capsule), before the eyes of someone who already watches the level fall.
            if (mc.player.getVehicle() == plug && mc.getCameraEntity() == mc.player && mc.options.getCameraType().isFirstPerson()) continue;
            var frame = plug.getInterpolatedCanonicalTransform(1);
            int drops = 2 + Math.round(5 * strength);
            for (int i = 0; i < drops; i++)
            {
                // Along the cabin, from the hatch's seam and from the shell's underside.
                boolean seam = random.nextBoolean();
                Vec3 at = frame.transformPoint(new Vec3((random.nextDouble() - .5) * (seam ? 1.0 : 1.3), seam ? .78 : -.80, 3.4 + random.nextDouble() * 3.8));
                mc.level.addParticle(ParticleTypes.FALLING_HONEY, at.x, at.y, at.z, 0, 0, 0);
                if (i == 0) mc.level.addParticle(MIST, at.x, at.y, at.z, 0, -.02, 0);
            }
        }
    }
}

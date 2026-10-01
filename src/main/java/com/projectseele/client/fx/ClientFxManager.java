package com.projectseele.client.fx;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.UUID;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.ProjectSeele;
import com.projectseele.client.render.RibbonRenderer;
import com.projectseele.client.render.EvaUnit01Renderer;
import com.projectseele.network.ClientboundAtFieldRipplePacket;
import com.projectseele.network.ClientboundCannonBeamPacket;
import com.projectseele.network.ClientboundCrossExplosionPacket;
import com.projectseele.network.ClientboundRifleTracerPacket;
import com.projectseele.fx.TreeOfLifeLayout;
import com.projectseele.network.ClientboundThirdImpactPacket;
import com.projectseele.registry.ModSounds;
import net.minecraft.client.gui.Font;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.locale.Language;
import net.minecraft.sounds.SoundSource;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;
import org.joml.Vector3f;

/**
 * Owns every transient world-space visual that is not tied to an entity
 * renderer. Instances are spawned by S2C packets, aged by the client tick and
 * drawn after particles so they blend over the whole scene.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.FORGE, value = Dist.CLIENT)
public final class ClientFxManager
{
    private static final List<WorldFx> ACTIVE = new ArrayList<>();
    private static ClientLevel activeLevel;
    private static int nuclearFlashTicks;
    private static int nuclearFlashDuration;
    private static float nuclearFlashStrength;
    // Lightning's additive pass vanished entirely in actual framebuffer
    // captures on the current NVIDIA/Forge stack. The Tree needs a stable
    // position-colour quad pass; other transient energy FX keep lightning.
    private static final RenderType TREE_GEOMETRY = RenderType.debugQuads();

    private ClientFxManager() {}

    public static void addCrossExplosion(ClientboundCrossExplosionPacket packet)
    {
        // fxIntensity 0 disables the visual entirely; the sound still plays.
        if (com.projectseele.config.SeeleConfig.FX_INTENSITY.get() > 0.0D)
        {
            ACTIVE.add(new CrossExplosion(new Vec3(packet.x, packet.y, packet.z), packet.scale));
        }
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.level != null)
        {
            minecraft.level.playLocalSound(packet.x, packet.y, packet.z,
                    ModSounds.CROSS_EXPLOSION.get(), SoundSource.HOSTILE, 4.0F, 1.0F, false);
        }
    }

    public static void addAtFieldRipple(ClientboundAtFieldRipplePacket packet)
    {
        if (com.projectseele.config.SeeleConfig.FX_INTENSITY.get() > 0.0D)
        {
            ACTIVE.add(new AtFieldRipple(new Vec3(packet.x, packet.y, packet.z),
                    new Vector3f(packet.nx, packet.ny, packet.nz),packet.radius));
        }
    }

    public static void addCannonBeam(ClientboundCannonBeamPacket packet)
    {
        ACTIVE.add(new CannonBeam(new Vec3(packet.x1, packet.y1, packet.z1),
                new Vec3(packet.x2, packet.y2, packet.z2)));
    }

    public static void addNukeFx(com.projectseele.network.ClientboundNukeFxPacket packet)
    { addNukeFx(packet, true); }

    public static void addNukeFx(com.projectseele.network.ClientboundNukeFxPacket packet, boolean withSound)
    {
        Vec3 pos = new Vec3(packet.x, packet.y, packet.z);
        float configuredIntensity = fxIntensity();
        if (configuredIntensity > 0.0F)
        {
            ACTIVE.add(new NukeExplosion(pos, packet.scale));
            if (packet.angelCross)
            {
                ACTIVE.add(new CrossExplosion(pos, packet.scale * 0.5F));
            }
            // A strategic detonation should overexpose the entry-plug feed
            // even when the impact itself is just outside the camera. Scale
            // 3.6 covers the cannon packet radius; N2's exact 3x scale covers
            // its correspondingly larger audience. Distance still attenuates
            // the flash, and FX intensity 0 disables it entirely.
            Minecraft minecraft = Minecraft.getInstance();
            if (minecraft.getCameraEntity() != null)
            {
                double distance = minecraft.getCameraEntity().getEyePosition().distanceTo(pos);
                double visibleRadius = packet.scale * 60.0D;
                float distanceFactor = Mth.clamp((float) (1.0D - distance / visibleRadius),
                        0.0F, 1.0F);
                float strength = Mth.clamp((0.18F + distanceFactor * 0.82F)
                        * configuredIntensity, 0.0F, 1.0F);
                int duration = Mth.clamp(Math.round(12.0F + packet.scale * 0.9F), 14, 30);
                if (strength >= nuclearFlashStrength || nuclearFlashTicks <= 0)
                {
                    nuclearFlashDuration = duration;
                    nuclearFlashTicks = duration;
                    nuclearFlashStrength = strength;
                }
            }
        }
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.level != null && withSound)
        {
            minecraft.level.playLocalSound(packet.x, packet.y, packet.z,
                    packet.angelCross ? ModSounds.CROSS_EXPLOSION.get() : SoundEvents.GENERIC_EXPLODE,
                    packet.angelCross ? SoundSource.HOSTILE : SoundSource.PLAYERS,
                    5.0F, packet.angelCross ? 0.72F : 0.58F, false);
        }
    }

    public static void addThirdImpact(ClientboundThirdImpactPacket packet)
    {
        ensureActiveLevel();
        // The server dictates the facing so the light geometry lands exactly
        // on the Mass-Production Evas it parked on the Sephirot.
        Vec3 position = new Vec3(packet.x, packet.y, packet.z);
        // Resync the same server event in place. Replacing the Tree restarted
        // its reveal animation, while origin-only deduplication merged two
        // otherwise valid events staged at the same coordinates.
        for (WorldFx fx : ACTIVE)
        {
            if (fx instanceof KabbalahTree tree && tree.eventId.equals(packet.eventId))
            {
                tree.age = Math.max(tree.age,
                        Mth.clamp(packet.initialTreeAge, 0, KabbalahTree.LIFETIME - 1));
                return;
            }
        }
        ACTIVE.add(new KabbalahTree(packet.eventId, position, packet.yaw,
                packet.hasUnit, packet.initialTreeAge));
        if (Boolean.getBoolean("projectseele.visualCapture")
                && "impact".equals(System.getProperty("projectseele.visualCaptureUnit")))
        {
            com.projectseele.client.visual.VisualCaptureManager.startImpact(
                    new Vec3(packet.x, packet.y, packet.z), packet.yaw);
        }
    }

    public static void addRifleTracer(ClientboundRifleTracerPacket packet)
    {
        if(com.projectseele.visual.FactoryR20Review.R28_VISUAL)com.projectseele.visual.FieldR28Review.receivedRifleTracers++;
        Vec3 fallback = new Vec3(packet.x1, packet.y1, packet.z1);
        ACTIVE.add(new RifleTracer(packet.entityId, fallback,
                new Vec3(packet.x2, packet.y2, packet.z2)));
    }

    public static void clear()
    {
        ACTIVE.clear();
        activeLevel = null;
        nuclearFlashTicks = 0;
        nuclearFlashDuration = 0;
        nuclearFlashStrength = 0.0F;
    }

    /** 0..1 optical overexposure for the GUI pass, including a short afterimage. */
    public static float nuclearFlashOpacity(float partialTick)
    {
        if (nuclearFlashTicks <= 0 || nuclearFlashDuration <= 0)
        {
            return 0.0F;
        }
        float remaining = Mth.clamp((nuclearFlashTicks - partialTick)
                / nuclearFlashDuration, 0.0F, 1.0F);
        return Mth.clamp(nuclearFlashStrength * remaining * remaining, 0.0F, 1.0F);
    }

    @SubscribeEvent
    public static void onClientTick(TickEvent.ClientTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END || Minecraft.getInstance().isPaused())
        {
            return;
        }
        if (Minecraft.getInstance().level == null)
        {
            clear();
            return;
        }
        ensureActiveLevel();
        if (nuclearFlashTicks > 0)
        {
            nuclearFlashTicks--;
            if (nuclearFlashTicks == 0)
            {
                nuclearFlashStrength = 0.0F;
            }
        }
        Iterator<WorldFx> it = ACTIVE.iterator();
        while (it.hasNext())
        {
            WorldFx fx = it.next();
            if (++fx.age >= fx.lifetime())
            {
                it.remove();
            }
        }
    }

    private static void ensureActiveLevel()
    {
        ClientLevel level = Minecraft.getInstance().level;
        if (activeLevel == null)
        {
            activeLevel = level;
        }
        else if (activeLevel != level)
        {
            ACTIVE.clear();
            activeLevel = level;
        }
    }

    @SubscribeEvent
    public static void onRenderLevelStage(RenderLevelStageEvent event)
    {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_PARTICLES || ACTIVE.isEmpty())
        {
            return;
        }
        PoseStack poseStack = event.getPoseStack();
        Vec3 cam = event.getCamera().getPosition();
        MultiBufferSource.BufferSource buffer = Minecraft.getInstance().renderBuffers().bufferSource();

        for (WorldFx fx : ACTIVE)
        {
            poseStack.pushPose();
            poseStack.translate(fx.pos.x - cam.x, fx.pos.y - cam.y, fx.pos.z - cam.z);
            VertexConsumer target = fx instanceof KabbalahTree
                    ? buffer.getBuffer(TREE_GEOMETRY) : fx instanceof AtFieldRipple
                    ? buffer.getBuffer(com.projectseele.client.render.EnergyGlowR24.AT_FIELD) : fx instanceof CrossExplosion || fx instanceof NukeExplosion
                    // Vanilla lightning writes depth even for translucent
                    // rings, cutting a hard empty band through the smoke.
                    ? buffer.getBuffer(com.projectseele.client.render.EnergyGlowR24.CROSS) : buffer.getBuffer(RenderType.lightning());
            fx.render(poseStack, target, event.getPartialTick());
            poseStack.popPose();
        }
        buffer.endBatch(RenderType.lightning());
        buffer.endBatch(com.projectseele.client.render.EnergyGlowR24.CROSS);
        buffer.endBatch(com.projectseele.client.render.EnergyGlowR24.AT_FIELD);
        buffer.endBatch(TREE_GEOMETRY);

        // World-space lettering uses the same pose as the luminous geometry,
        // but a font render type. Keep it in a second pass so batching the
        // lightning ribbons cannot swallow or reorder the glyph quads.
        for (WorldFx fx : ACTIVE)
        {
            if (!(fx instanceof KabbalahTree tree))
            {
                continue;
            }
            poseStack.pushPose();
            poseStack.translate(fx.pos.x - cam.x, fx.pos.y - cam.y, fx.pos.z - cam.z);
            tree.renderLabels(poseStack, buffer, event.getPartialTick());
            poseStack.popPose();
        }
        buffer.endBatch();
    }

    private static float fxIntensity()
    {
        return com.projectseele.config.SeeleConfig.FX_INTENSITY.get().floatValue();
    }

    // =====================================================================

    /** A transient effect anchored at a world position. */
    private abstract static class WorldFx
    {
        final Vec3 pos;
        int age;

        WorldFx(Vec3 pos)
        {
            this.pos = pos;
        }

        abstract int lifetime();

        abstract void render(PoseStack poseStack, VertexConsumer consumer, float partialTick);
    }

    /**
     * The Angel signature: a tall vertical pillar of light with a shorter cross
     * arm, expanding out of the ground, holding, then dissolving — plus a
     * ground-level shockwave ring.
     */
    private static final class CrossExplosion extends WorldFx
    {
        static final int LIFETIME = 70;
        private static final int EXPAND_END = 10;
        private static final int HOLD_END = 34;

        final float scale;

        CrossExplosion(Vec3 pos, float scale)
        {
            super(pos);
            // Angel crosses are skyline-scale, not ordinary particle bursts.
            this.scale = scale * 5.0F;
        }

        @Override
        int lifetime()
        {
            return LIFETIME;
        }

        @Override
        void render(PoseStack poseStack, VertexConsumer consumer, float partialTick)
        {
            float t = this.age + partialTick;
            Matrix4f pose = poseStack.last().pose();

            float expand = easeOutCubic(Mth.clamp(t / EXPAND_END, 0.0F, 1.0F));
            float fade = t <= HOLD_END ? 1.0F
                    : Mth.clamp(1.0F - (t - HOLD_END) / (LIFETIME - HOLD_END), 0.0F, 1.0F);
            // Slight breathing while the cross holds.
            float pulse = 1.0F + 0.06F * Mth.sin(t * 0.6F);
            float alpha = fade * pulse * fxIntensity();
            float widthMul = (1.0F + 0.35F * (1.0F - fade)) * this.scale;

            float height = 26.0F * this.scale * expand;
            float armReach = 9.0F * this.scale * easeOutCubic(Mth.clamp((t - 4.0F) / EXPAND_END, 0.0F, 1.0F));
            float armY = height * 0.62F;

            // Vertical pillar: violet-white core in an orange sheath.
            Vector3f base = new Vector3f(0.0F, -2.0F * this.scale, 0.0F);
            Vector3f top = new Vector3f(0.0F, height, 0.0F);
            RibbonRenderer.drawSoftStarRibbon(pose, consumer, base, top,
                    2.0F * widthMul, 1.5F * widthMul, 1.0F, 0.55F, 0.22F, alpha * 0.5F);
            RibbonRenderer.drawSoftStarRibbon(pose, consumer, base, top,
                    0.9F * widthMul, 0.65F * widthMul, 1.0F, 0.97F, 0.90F, alpha * 0.95F);

            if (armReach > 0.05F)
            {
                Vector3f left = new Vector3f(-armReach, armY, 0.0F);
                Vector3f right = new Vector3f(armReach, armY, 0.0F);
                RibbonRenderer.drawSoftStarRibbon(pose, consumer, left, right,
                        1.5F * widthMul, 1.5F * widthMul, 1.0F, 0.55F, 0.22F, alpha * 0.5F);
                RibbonRenderer.drawSoftStarRibbon(pose, consumer, left, right,
                        0.7F * widthMul, 0.7F * widthMul, 1.0F, 0.97F, 0.90F, alpha * 0.95F);
            }

            // Shockwave ring racing outward along the ground.
            float ringT = Mth.clamp((t - 2.0F) / 28.0F, 0.0F, 1.0F);
            if (ringT < 1.0F && ringT > 0.0F)
            {
                float radius = 30.0F * this.scale * easeOutCubic(ringT);
                float ringAlpha = (1.0F - ringT) * 0.55F * fxIntensity();
                poseStack.pushPose();
                poseStack.translate(0.0D, 0.15D, 0.0D);
                RibbonRenderer.drawGroundRing(poseStack.last().pose(), consumer, radius,
                        1.0F * this.scale, 1.0F, 0.62F, 0.30F, ringAlpha);
                poseStack.popPose();
            }
        }
    }

    /**
     * A.T. Field cue: translucent octagonal bands in the event's world plane.
     */
    private static final class AtFieldRipple extends WorldFx
    {
        static final int LIFETIME = 18;

        private final Vector3f u;
        private final Vector3f v;
        private final float radius;

        AtFieldRipple(Vec3 pos, Vector3f normal,float radius)
        {
            super(pos);
            this.radius=radius;
            Vector3f[] basis = RibbonRenderer.planeBasis(normal);
            this.u = basis[0];
            this.v = basis[1];
        }

        @Override
        int lifetime()
        {
            return LIFETIME;
        }

        @Override
        void render(PoseStack poseStack, VertexConsumer consumer, float partialTick)
        {
            float t = (this.age + partialTick) / LIFETIME;
            com.projectseele.client.render.TvAtFieldSurfaceR44.impact(poseStack.last().pose(),consumer,this.u,this.v,t,fxIntensity(),this.radius);
        }
    }

    /**
     * Nuke-grade beam impact: a blinding radial flash, an expanding fireball
     * of light ribbons and a fast double shockwave. The mushroom smoke itself
     * is server-side particles. Angel callers may add a separate cross.
     */
    private static final class NukeExplosion extends WorldFx
    {
        static final int LIFETIME = 44;

        private static final Vector3f[] BURST_DIRS = buildBurstDirs();

        final float scale;

        NukeExplosion(Vec3 pos, float scale)
        {
            super(pos);
            this.scale = scale;
        }

        @Override
        int lifetime()
        {
            return LIFETIME;
        }

        @Override
        void render(PoseStack poseStack, VertexConsumer consumer, float partialTick)
        {
            float t = this.age + partialTick;
            Matrix4f pose = poseStack.last().pose();
            float intensity = fxIntensity();

            // Blinding radial flash for the first half second.
            if (t < 9.0F)
            {
                float flashT = t / 9.0F;
                float len = (6.0F + 14.0F * easeOutCubic(flashT)) * this.scale;
                float alpha = (1.0F - flashT) * 0.95F * intensity;
                for (Vector3f dir : BURST_DIRS)
                {
                    Vector3f end = new Vector3f(dir).mul(len);
                    RibbonRenderer.drawStarRibbon(pose, consumer, new Vector3f(0.0F, 0.0F, 0.0F), end,
                            1.3F * this.scale, 0.12F, 1.0F, 0.99F, 0.92F, alpha);
                }
            }

            // Rising fireball: stacked luminous rings swelling and lifting.
            float ballT = Mth.clamp(t / 30.0F, 0.0F, 1.0F);
            float ballAlpha = (1.0F - ballT) * 0.65F * intensity;
            if (ballAlpha > 0.01F)
            {
                float radius = (2.0F + 9.0F * easeOutCubic(ballT)) * this.scale;
                float lift = 6.0F * ballT * this.scale;
                Vector3f ux = new Vector3f(1.0F, 0.0F, 0.0F);
                Vector3f uz = new Vector3f(0.0F, 0.0F, 1.0F);
                for (int layer = -1; layer <= 1; layer++)
                {
                    float layerR = radius * (1.0F - 0.28F * Math.abs(layer));
                    poseStack.pushPose();
                    poseStack.translate(0.0D, lift + layer * radius * 0.45F, 0.0D);
                    RibbonRenderer.drawPolyRing(poseStack.last().pose(), consumer, ux, uz, 12,
                            layerR, layerR * 0.45F, 1.0F, 0.52F, 0.16F, ballAlpha);
                    poseStack.popPose();
                }
            }

            // Twin ground shockwaves racing outward.
            for (int wave = 0; wave < 2; wave++)
            {
                float waveT = Mth.clamp((t - wave * 5.0F) / 26.0F, 0.0F, 1.0F);
                if (waveT <= 0.0F || waveT >= 1.0F)
                {
                    continue;
                }
                float radius = 42.0F * this.scale * easeOutCubic(waveT);
                float alpha = (1.0F - waveT) * (0.5F - wave * 0.15F) * intensity;
                poseStack.pushPose();
                poseStack.translate(0.0D, 0.2D + wave * 0.5D, 0.0D);
                RibbonRenderer.drawGroundRing(poseStack.last().pose(), consumer, radius,
                        1.4F * this.scale, 1.0F, 0.72F, 0.35F, alpha);
                poseStack.popPose();
            }
        }

        private static Vector3f[] buildBurstDirs()
        {
            // 14 fixed directions: 6 axes + 8 diagonals, normalized.
            float d = 0.5774F;
            return new Vector3f[] {
                    new Vector3f(1, 0, 0), new Vector3f(-1, 0, 0),
                    new Vector3f(0, 1, 0), new Vector3f(0, -1, 0),
                    new Vector3f(0, 0, 1), new Vector3f(0, 0, -1),
                    new Vector3f(d, d, d), new Vector3f(-d, d, d),
                    new Vector3f(d, d, -d), new Vector3f(-d, d, -d),
                    new Vector3f(d, -d, d), new Vector3f(-d, -d, d),
                    new Vector3f(d, -d, -d), new Vector3f(-d, -d, -d)
            };
        }
    }

    /** One positron sniper shot: brilliant flash, quick fade. */
    private static final class CannonBeam extends WorldFx
    {
        static final int LIFETIME = 14;

        private final Vector3f end;

        CannonBeam(Vec3 from, Vec3 to)
        {
            super(from);
            this.end = new Vector3f((float) (to.x - from.x), (float) (to.y - from.y), (float) (to.z - from.z));
        }

        @Override
        int lifetime()
        {
            return LIFETIME;
        }

        @Override
        void render(PoseStack poseStack, VertexConsumer consumer, float partialTick)
        {
            float t = this.age + partialTick;
            float alpha = Mth.clamp(1.0F - t / LIFETIME, 0.0F, 1.0F);
            float flash = t < 2.0F ? 1.5F : 1.0F;
            Matrix4f pose = poseStack.last().pose();
            Vector3f start = new Vector3f(0.0F, 0.0F, 0.0F);
            RibbonRenderer.drawStarRibbon(pose, consumer, start, this.end,
                    0.65F * flash, 0.40F * flash, 0.55F, 0.80F, 1.0F, alpha * 0.5F);
            RibbonRenderer.drawStarRibbon(pose, consumer, start, this.end,
                    0.28F * flash, 0.16F * flash, 1.0F, 0.99F, 0.95F, alpha * 0.95F);
        }
    }

    /** Pallet-SMG pulse: thin, fast and deliberately free of impact fireballs. */
    private static final class RifleTracer extends WorldFx
    {
        static final int LIFETIME = 4;
        private final Vec3 destination;
        private final int entityId;
        private Vec3 visibleOrigin;
        private float firstRenderTime = -1;

        RifleTracer(int entityId, Vec3 from, Vec3 to)
        {
            super(from);
            this.entityId = entityId;
            this.destination = to;
        }

        @Override
        int lifetime()
        {
            return LIFETIME;
        }

        @Override
        void render(PoseStack poseStack, VertexConsumer consumer, float partialTick)
        {
            if (visibleOrigin == null)
            {
                visibleOrigin = EvaUnit01Renderer.rifleMuzzleOrFallback(entityId, pos);
                firstRenderTime = this.age + partialTick;
            }
            float t = Math.max(0, this.age + partialTick - firstRenderTime);
            Vec3 ray = destination.subtract(visibleOrigin);
            double distance = ray.length();
            if (distance < .01) return;
            Vec3 direction = ray.scale(1 / distance);
            double head = Math.min(distance, (t + .08) * 220);
            double tail = Math.max(0, head - 18);
            Vector3f start = visibleOrigin.subtract(pos).add(direction.scale(tail)).toVector3f();
            Vector3f end = visibleOrigin.subtract(pos).add(direction.scale(head)).toVector3f();
            float alpha = Mth.clamp(1 - t / 2.5F, 0, 1);
            if (t * 220 < distance + 18)
                RibbonRenderer.drawStarRibbon(poseStack.last().pose(), consumer,
                        start, end, .09F, .035F, 1, .78F, .35F, alpha);
            if (t < .7F)
            {
                Vector3f flash = visibleOrigin.subtract(pos).toVector3f();
                RibbonRenderer.drawStarRibbon(poseStack.last().pose(), consumer,
                        flash, new Vector3f(flash).add(direction.scale(1.6).toVector3f()),
                        .42F * (1 - t), .06F, 1, .92F, .65F, 1 - t);
            }
        }
    }

    /**
     * The End-of-Evangelion Sephirothic tree, sharing TreeOfLifeLayout with
     * the server: an inverted Golden Dawn diagram, ring-shaped Sephirot joined
     * by burning double lines and the 22 path letters. The outer rings frame
     * the real Mass-Production Eva entities; Tiferet carries the crucified
     * Unit-01 with wings of light.
     */
    private static final class KabbalahTree extends WorldFx
    {
        private static final int LIFETIME = 20 * 180;
        /** Node reveal cadence: Keter first, rising through the inverted tree. */
        private static final int NODE_LIGHT_INTERVAL = 9;
        private static final int NODE_LIGHT_TIME = 24;
        private static final int NODE_TICK_COUNT = 12;
        private static final int TIFERET = TreeOfLifeLayout.TIFERET;
        private static final float LABEL_ROTATION_DEGREES = 180.0F;
        private static final float DIAGRAM_TEXT_Z = -7.4F;
        private static final float EXTERNAL_NAME_Y = 5.5F;
        private static final float EXTERNAL_DIVINE_Y = 1.5F;
        private static final float EXTERNAL_ARCHANGEL_Y = -1.5F;
        private static final float EXTERNAL_CHOIR_Y = -5.5F;
        private static final float EXTERNAL_NAME_SCALE = 0.67F;
        private static final float EXTERNAL_DIVINE_SCALE = 0.47F;
        private static final float EXTERNAL_ARCHANGEL_SCALE = 0.37F;
        private static final float EXTERNAL_CHOIR_SCALE = 0.34F;
        private static final float PATH_LETTER_SCALE = 0.80F;
        private static final float INTERNAL_NAME_SCALE = 0.34F;
        private static final float INTERNAL_DIVINE_SCALE = 0.26F;
        private static final float INTERNAL_ARCHANGEL_SCALE = 0.24F;
        private static final float INTERNAL_CHOIR_SCALE = 0.20F;
        private static final float PATH_NUMBER_SCALE = 0.34F;
        private static final String[] SEPHIRA_NAMES = {
                "KETER", "CHOKMAH", "BINAH", "CHESED", "GEVURAH",
                "TIFERET", "NETZACH", "HOD", "YESOD", "MALKUTH"
        };
        private static final String[] SEPHIRA_HEBREW = {
                "\u05DB\u05EA\u05E8", "\u05D7\u05DB\u05DE\u05D4", "\u05D1\u05D9\u05E0\u05D4",
                "\u05D7\u05E1\u05D3", "\u05D2\u05D1\u05D5\u05E8\u05D4", "\u05EA\u05E4\u05D0\u05E8\u05EA",
                "\u05E0\u05E6\u05D7", "\u05D4\u05D5\u05D3", "\u05D9\u05E1\u05D5\u05D3", "\u05DE\u05DC\u05DB\u05D5\u05EA"
        };
        private static final String[] SEPHIRA_NUMERALS = {
                "\u05D0", "\u05D1", "\u05D2", "\u05D3", "\u05D4",
                "\u05D5", "\u05D6", "\u05D7", "\u05D8", "\u05D9"
        };
        /** Hermetic divine names traditionally printed beside the ten Sephirot. */
        private static final String[] SEPHIRA_DIVINE_NAMES = {
                "\u05D0\u05D4\u05D9\u05D4", "\u05D9\u05D4", "\u05D9\u05D4\u05D5\u05D4 \u05D0\u05DC\u05D4\u05D9\u05DD",
                "\u05D0\u05DC", "\u05D0\u05DC\u05D4\u05D9\u05DD \u05D2\u05D9\u05D1\u05D5\u05E8", "\u05D9\u05D4\u05D5\u05D4 \u05D0\u05DC\u05D5\u05D4 \u05D5\u05D3\u05E2\u05EA",
                "\u05D9\u05D4\u05D5\u05D4 \u05E6\u05D1\u05D0\u05D5\u05EA", "\u05D0\u05DC\u05D4\u05D9\u05DD \u05E6\u05D1\u05D0\u05D5\u05EA", "\u05E9\u05D3\u05D9 \u05D0\u05DC \u05D7\u05D9", "\u05D0\u05D3\u05E0\u05D9 \u05D4\u05D0\u05E8\u05E5"
        };
        /** Compact Hermetic correspondences used as backplate micro-engraving. */
        private static final String[] SEPHIRA_ARCHANGELS = {
                "\u05DE\u05D8\u05D8\u05E8\u05D5\u05DF", "\u05E8\u05D6\u05D9\u05D0\u05DC", "\u05E6\u05E4\u05E7\u05D9\u05D0\u05DC",
                "\u05E6\u05D3\u05E7\u05D9\u05D0\u05DC", "\u05DB\u05DE\u05D0\u05DC", "\u05E8\u05E4\u05D0\u05DC",
                "\u05D4\u05E0\u05D9\u05D0\u05DC", "\u05DE\u05D9\u05DB\u05D0\u05DC", "\u05D2\u05D1\u05E8\u05D9\u05D0\u05DC", "\u05E1\u05E0\u05D3\u05DC\u05E4\u05D5\u05DF"
        };
        private static final String[] SEPHIRA_CHOIRS = {
                "\u05D7\u05D9\u05D5\u05EA \u05D4\u05E7\u05D5\u05D3\u05E9", "\u05D0\u05D5\u05E4\u05E0\u05D9\u05DD", "\u05D0\u05E8\u05D0\u05DC\u05D9\u05DD",
                "\u05D7\u05E9\u05DE\u05DC\u05D9\u05DD", "\u05E9\u05E8\u05E4\u05D9\u05DD", "\u05DE\u05DC\u05D0\u05DB\u05D9\u05DD",
                "\u05D1\u05E0\u05D9 \u05D0\u05DC\u05D4\u05D9\u05DD", "\u05D0\u05DC\u05D4\u05D9\u05DD", "\u05DB\u05E8\u05D5\u05D1\u05D9\u05DD", "\u05D0\u05D9\u05E9\u05D9\u05DD"
        };
        // PATHS is arranged for geometry/label spacing rather than alphabetic
        // order.  Keep each letter beside its canonical Golden Dawn edge.
        private static final String[] PATH_LETTERS = {
                "\u05D0", "\u05D1", "\u05D2", "\u05D3", "\u05D5", "\u05D4", "\u05D7", "\u05D6",
                "\u05D8", "\u05D9", "\u05DB", "\u05DC", "\u05DE", "\u05E0", "\u05E2", "\u05E1",
                "\u05E4", "\u05E6", "\u05E8", "\u05E7", "\u05E9", "\u05EA"
        };
        /** Hebrew path numbers 11..32, ordered to match PATHS/PATH_LETTERS. */
        private static final String[] PATH_NUMERALS = {
                "\u05D9\u05F4\u05D0", "\u05D9\u05F4\u05D1", "\u05D9\u05F4\u05D2", "\u05D9\u05F4\u05D3",
                "\u05D8\u05F4\u05D6", "\u05D8\u05F4\u05D5", "\u05D9\u05F4\u05D7", "\u05D9\u05F4\u05D6",
                "\u05D9\u05F4\u05D8", "\u05DB\u05F3", "\u05DB\u05F4\u05D0", "\u05DB\u05F4\u05D1",
                "\u05DB\u05F4\u05D2", "\u05DB\u05F4\u05D3", "\u05DB\u05F4\u05D5", "\u05DB\u05F4\u05D4",
                "\u05DB\u05F4\u05D6", "\u05DB\u05F4\u05D7", "\u05DC\u05F3", "\u05DB\u05F4\u05D8",
                "\u05DC\u05F4\u05D0", "\u05DC\u05F4\u05D1"
        };
        /** Compact Hebrew labels stay outside the ritual bodies; centre labels alternate sides. */
        private static final float[] LABEL_X_OFFSETS = {
                -24.0F, -30.0F, 30.0F, -29.0F, 29.0F,
                68.0F, -35.0F, 28.0F, -63.0F, 28.0F
        };
        /** Collision-searched offsets from each path midpoint, in local tree space. */
        private static final float[][] PATH_LABEL_OFFSETS = {
                {1.0F,11.0F},{1.0F,-6.5F},{0.0F,0.0F},{0.0F,0.5F},
                {-15.5F,0.0F},{1.5F,0.0F},{-17.0F,0.0F},{-0.5F,-1.0F},
                {0.0F,-5.5F},{0.0F,-11.5F},{0.0F,1.0F},{-1.0F,-12.5F},
                {0.0F,1.0F},{-13.0F,5.0F},{13.0F,5.0F},{0.0F,0.5F},
                {-5.0F,-7.5F},{1.0F,-11.5F},{-1.0F,-11.5F},
                {-6.0F,0.0F},{1.5F,0.0F},{-16.5F,0.0F}
        };

        private final UUID eventId;
        private final float faceYaw;
        private final boolean hasUnit;

        KabbalahTree(UUID eventId, Vec3 pos, float faceYaw, boolean hasUnit, int initialAge)
        {
            super(pos);
            this.eventId = eventId;
            this.faceYaw = faceYaw;
            this.hasUnit = hasUnit;
            this.age = Mth.clamp(initialAge, 0, LIFETIME - 1);
        }

        private static Vector3f node(int index)
        {
            return new Vector3f(TreeOfLifeLayout.localX(index), TreeOfLifeLayout.localY(index), 0.0F);
        }

        @Override
        int lifetime()
        {
            return LIFETIME;
        }

        /** 0..1 ignition of one Sephira: Keter first through the inversion. */
        private static float nodeLight(float t, int index)
        {
            return Mth.clamp((t - 10.0F - index * NODE_LIGHT_INTERVAL) / NODE_LIGHT_TIME, 0.0F, 1.0F);
        }

        @Override
        void render(PoseStack poseStack, VertexConsumer consumer, float partialTick)
        {
            float t = this.age + partialTick;
            float endFade = Mth.clamp((LIFETIME - t) / 80.0F, 0.0F, 1.0F);
            float breathe = 0.80F + 0.14F * Mth.sin(t * 0.045F);
            float base = endFade * breathe * fxIntensity();
            if (base <= 0.003F)
            {
                return;
            }

            poseStack.pushPose();
            poseStack.mulPose(com.mojang.math.Axis.YP.rotation(this.faceYaw));
            // Keep the diagram as a luminous backplate. The ritual bodies sit
            // at local Z=0; a small negative offset stops the opaque stable
            // colour pass from painting over their silhouettes.
            poseStack.translate(0.0D, 0.0D, -8.0D);
            Matrix4f pose = poseStack.last().pose();

            // Paths: burning double lines, lit once both endpoints burn.
            for (int[] path : TreeOfLifeLayout.PATHS)
            {
                float lit = Math.min(nodeLight(t, path[0]), nodeLight(t, path[1]));
                if (lit <= 0.0F)
                {
                    continue;
                }
                Vector3f a = node(path[0]);
                Vector3f b = node(path[1]);
                Vector3f dir = new Vector3f(b).sub(a).normalize();
                // In-plane normal (the tree stands in local XY).
                Vector3f offset = new Vector3f(-dir.y, dir.x, 0.0F).mul(0.72F);
                Vector3f mid = new Vector3f(a).lerp(b, 0.5F);
                Vector3f grow = new Vector3f(b).sub(a).mul(0.5F * lit);
                Vector3f from = new Vector3f(mid).sub(grow);
                Vector3f to = new Vector3f(mid).add(grow);
                float alpha = base * lit;
                for (int s = -1; s <= 1; s += 2)
                {
                    Vector3f shift = new Vector3f(offset).mul(s);
                    RibbonRenderer.drawStarRibbon(pose, consumer,
                            new Vector3f(from).add(shift), new Vector3f(to).add(shift),
                            0.38F, 0.38F, 1.0F, 0.0F, 0.0F, alpha * 0.45F);
                    RibbonRenderer.drawStarRibbon(pose, consumer,
                            new Vector3f(from).add(shift), new Vector3f(to).add(shift),
                            0.12F, 0.12F, 1.0F, 0.0F, 0.0F, alpha * 0.82F);
                }
            }

            // Sephirot rings. The outer nodes frame the real Mass-Production
            // Eva entities parked there by the server; Tiferet carries the
            // crucified Unit-01 with wings of light (EoE staging).
            Vector3f axisX = new Vector3f(1.0F, 0.0F, 0.0F);
            Vector3f axisY = new Vector3f(0.0F, 1.0F, 0.0F);
            for (int i = 0; i < TreeOfLifeLayout.NODES.length; i++)
            {
                float lit = nodeLight(t, i);
                if (lit <= 0.0F)
                {
                    continue;
                }
                Vector3f c = node(i);
                boolean centre = i == TIFERET;
                float radius = (centre ? 16.5F : 13.5F) * (0.9F + 0.1F * lit)
                        * (1.0F + 0.045F * Mth.sin(t * 0.07F + i * 1.7F));
                float alpha = base * lit;
                poseStack.pushPose();
                poseStack.translate(c.x, c.y, c.z);
                Matrix4f nodePose = poseStack.last().pose();
                RibbonRenderer.drawPolyRing(nodePose, consumer, axisX, axisY, 32,
                        radius, 0.56F, 1.0F, 0.0F, 0.0F, alpha * 0.72F);
                RibbonRenderer.drawPolyRing(nodePose, consumer, axisX, axisY, 32,
                        radius * 0.72F, 0.18F, 1.0F, 0.0F, 0.0F, alpha * 0.82F);
                // Original procedural register marks add fine engraved-circle
                // density without copying the supplied reference frame.
                for (int tick = 0; tick < NODE_TICK_COUNT; tick++)
                {
                    float angle = Mth.TWO_PI * tick / NODE_TICK_COUNT;
                    float cos = Mth.cos(angle);
                    float sin = Mth.sin(angle);
                    Vector3f inner = new Vector3f(cos * radius * 0.79F,
                            sin * radius * 0.79F, 0.05F);
                    Vector3f outer = new Vector3f(cos * radius * 0.93F,
                            sin * radius * 0.93F, 0.05F);
                    RibbonRenderer.drawStarRibbon(nodePose, consumer, inner, outer,
                            0.09F, 0.09F, 1.0F, 0.0F, 0.0F, alpha * 0.56F);
                }
                if (centre)
                {
                    drawTiferetGlory(nodePose, consumer, t, alpha, this.hasUnit);
                }
                poseStack.popPose();

                // Short leaders make the displaced bilingual node labels
                // unambiguous without drawing text over an EVA silhouette.
                float labelOffset = LABEL_X_OFFSETS[i];
                float sign = Math.signum(labelOffset);
                float lineStart = radius + 0.8F;
                float lineEnd = Math.abs(labelOffset) - 3.0F;
                if (lineEnd > lineStart)
                {
                    RibbonRenderer.drawStarRibbon(pose, consumer,
                            new Vector3f(c.x + sign * lineStart, c.y, c.z + 0.2F),
                            new Vector3f(c.x + sign * lineEnd, c.y, c.z + 0.2F),
                            0.18F, 0.18F, 1.0F, 0.0F, 0.0F, alpha * 0.9F);
                }
            }
            poseStack.popPose();
        }

        /** Full-bright inverted Hebrew tableau: node names plus 22 letters/numbers. */
        void renderLabels(PoseStack poseStack, MultiBufferSource.BufferSource buffer, float partialTick)
        {
            float t = this.age + partialTick;
            float endFade = Mth.clamp((LIFETIME - t) / 80.0F, 0.0F, 1.0F);
            float base = endFade * fxIntensity();
            if (base <= 0.003F)
            {
                return;
            }

            poseStack.pushPose();
            poseStack.mulPose(com.mojang.math.Axis.YP.rotation(this.faceYaw));

            for (int i = 0; i < TreeOfLifeLayout.NODES.length; i++)
            {
                float lit = nodeLight(t, i);
                if (lit <= 0.0F)
                {
                    continue;
                }
                Vector3f c = node(i);
                float alpha = base * lit;
                float labelX = c.x + LABEL_X_OFFSETS[i];
                drawLabel(poseStack, buffer,
                        displayHebrew(SEPHIRA_NUMERALS[i] + "  " + SEPHIRA_HEBREW[i]),
                        new Vector3f(labelX, c.y + EXTERNAL_NAME_Y, 0.9F),
                        EXTERNAL_NAME_SCALE, alpha);
                drawLabel(poseStack, buffer, displayHebrew(SEPHIRA_DIVINE_NAMES[i]),
                        new Vector3f(labelX, c.y + EXTERNAL_DIVINE_Y, 0.9F),
                        EXTERNAL_DIVINE_SCALE, alpha * 0.82F);
                drawLabel(poseStack, buffer, displayHebrew(SEPHIRA_ARCHANGELS[i]),
                        new Vector3f(labelX, c.y + EXTERNAL_ARCHANGEL_Y, 0.9F),
                        EXTERNAL_ARCHANGEL_SCALE, alpha * 0.72F);
                drawLabel(poseStack, buffer, displayHebrew(SEPHIRA_CHOIRS[i]),
                        new Vector3f(labelX, c.y + EXTERNAL_CHOIR_Y, 0.9F),
                        EXTERNAL_CHOIR_SCALE, alpha * 0.64F);
                // These micro-inscriptions sit on the red backplate and are
                // depth-occluded by the real EVA parked inside the circle.
                drawDiagramLabel(poseStack, buffer, displayHebrew(SEPHIRA_HEBREW[i]),
                        new Vector3f(c.x, c.y + 9.4F, DIAGRAM_TEXT_Z),
                        INTERNAL_NAME_SCALE, alpha * 0.68F);
                drawDiagramLabel(poseStack, buffer, displayHebrew(SEPHIRA_ARCHANGELS[i]),
                        new Vector3f(c.x, c.y + 5.7F, DIAGRAM_TEXT_Z),
                        INTERNAL_ARCHANGEL_SCALE, alpha * 0.58F);
                drawDiagramLabel(poseStack, buffer, displayHebrew(SEPHIRA_CHOIRS[i]),
                        new Vector3f(c.x, c.y - 5.7F, DIAGRAM_TEXT_Z),
                        INTERNAL_CHOIR_SCALE, alpha * 0.52F);
                drawDiagramLabel(poseStack, buffer, displayHebrew(SEPHIRA_DIVINE_NAMES[i]),
                        new Vector3f(c.x, c.y - 9.4F, DIAGRAM_TEXT_Z),
                        INTERNAL_DIVINE_SCALE, alpha * 0.56F);
            }

            for (int i = 0; i < TreeOfLifeLayout.PATHS.length; i++)
            {
                int[] path = TreeOfLifeLayout.PATHS[i];
                float lit = Math.min(nodeLight(t, path[0]), nodeLight(t, path[1]));
                if (lit <= 0.0F)
                {
                    continue;
                }
                Vector3f a = node(path[0]);
                Vector3f b = node(path[1]);
                Vector3f letterPos = new Vector3f(a).lerp(b, 0.5F)
                        .add(PATH_LABEL_OFFSETS[i][0], PATH_LABEL_OFFSETS[i][1], 1.0F);
                drawLabel(poseStack, buffer, PATH_LETTERS[i], letterPos,
                        PATH_LETTER_SCALE, base * lit);
                drawDiagramLabel(poseStack, buffer, displayHebrew(PATH_NUMERALS[i]),
                        new Vector3f(letterPos.x + 3.5F, letterPos.y - 7.0F, DIAGRAM_TEXT_Z),
                        PATH_NUMBER_SCALE, base * lit * 0.62F);
            }
            poseStack.popPose();
        }

        /** Vanilla only applies bidi shaping when the selected UI language is RTL. */
        private static String displayHebrew(String logical)
        {
            return Language.getInstance().isDefaultRightToLeft()
                    ? logical : new StringBuilder(logical).reverse().toString();
        }

        private static void drawLabel(PoseStack poseStack, MultiBufferSource.BufferSource buffer,
                                      String text, Vector3f position, float scale, float alpha)
        {
            drawLabel(poseStack, buffer, text, position, scale, alpha,
                    Font.DisplayMode.SEE_THROUGH);
        }

        private static void drawDiagramLabel(PoseStack poseStack,
                                             MultiBufferSource.BufferSource buffer,
                                             String text, Vector3f position,
                                             float scale, float alpha)
        {
            drawLabel(poseStack, buffer, text, position, scale, alpha,
                    Font.DisplayMode.NORMAL);
        }

        private static void drawLabel(PoseStack poseStack, MultiBufferSource.BufferSource buffer,
                                      String text, Vector3f position, float scale, float alpha,
                                      Font.DisplayMode displayMode)
        {
            if (alpha <= 0.01F)
            {
                return;
            }
            Font font = Minecraft.getInstance().font;
            int colour = Mth.clamp((int) (alpha * 255.0F), 0, 255) << 24 | 0x00FF0000;
            poseStack.pushPose();
            poseStack.translate(position.x, position.y, position.z);
            poseStack.mulPose(com.mojang.math.Axis.ZP.rotationDegrees(
                    LABEL_ROTATION_DEGREES));
            poseStack.scale(scale, -scale, scale);
            font.drawInBatch(text, -font.width(text) * 0.5F, -4.0F, colour, false,
                    poseStack.last().pose(), buffer, displayMode,
                    0x00000000,
                    LightTexture.FULL_BRIGHT);
            poseStack.popPose();
        }

        /** Tiferet centrepiece: red wings of light; the cross body only when
         *  no real Unit-01 was nailed there by the scenario item. */
        private static void drawTiferetGlory(Matrix4f pose, VertexConsumer consumer,
                                             float t, float alpha, boolean hasUnit)
        {
            float s = 1.05F;
            float pr = 1.0F;
            float pg = 0.0F;
            float pb = 0.0F;
            // Wings of light first, so the body draws over them.
            float shimmer = 0.9F + 0.1F * Mth.sin(t * 0.06F);
            for (int side = -1; side <= 1; side += 2)
            {
                for (int f = 0; f < 3; f++)
                {
                    float ang = (28.0F + f * 22.0F) * Mth.DEG_TO_RAD;
                    float len = (20.0F - f * 4.0F) * shimmer * s;
                    Vector3f tip = new Vector3f(side * Mth.cos(ang) * len, 2.0F * s + Mth.sin(ang) * len, 0.4F);
                    RibbonRenderer.drawStarRibbon(pose, consumer, new Vector3f(0.0F, 2.0F * s, 0.4F), tip,
                            (1.55F - f * 0.32F) * s, 0.22F, 1.0F, 0.0F, 0.0F,
                            alpha * (0.30F - f * 0.05F));
                }
            }
            if (hasUnit)
            {
                return; // the real Unit-01 hangs here; wings only
            }
            // The cross pose: pure-red torso, outstretched arms, horned head.
            Vector3f hip = new Vector3f(0.0F, -4.6F * s, 0.0F);
            Vector3f neck = new Vector3f(0.0F, 3.4F * s, 0.0F);
            RibbonRenderer.drawStarRibbon(pose, consumer, hip, neck, 1.35F * s, 1.0F * s, pr, pg, pb, alpha);
            RibbonRenderer.drawStarRibbon(pose, consumer,
                    new Vector3f(-8.2F * s, 2.6F * s, 0.0F), new Vector3f(8.2F * s, 2.6F * s, 0.0F),
                    0.95F * s, 0.95F * s, pr, pg, pb, alpha);
            RibbonRenderer.drawStarRibbon(pose, consumer, neck,
                    new Vector3f(0.0F, 4.9F * s, 0.0F), 0.68F * s, 0.55F * s, pr, pg, pb, alpha);
            // The horn.
            RibbonRenderer.drawStarRibbon(pose, consumer,
                    new Vector3f(0.0F, 4.9F * s, -0.3F), new Vector3f(0.0F, 6.6F * s, -0.9F),
                    0.22F * s, 0.06F, 1.0F, 0.0F, 0.0F, alpha);
            // Legs together, crucified.
            RibbonRenderer.drawStarRibbon(pose, consumer, hip,
                    new Vector3f(0.0F, -9.6F * s, 0.0F), 0.9F * s, 0.5F * s, pr, pg, pb, alpha * 0.95F);
            // Core glow.
            RibbonRenderer.drawStarRibbon(pose, consumer,
                    new Vector3f(-0.9F * s, 0.8F * s, 0.5F), new Vector3f(0.9F * s, 0.8F * s, 0.5F),
                    0.8F * s, 0.8F * s, 1.0F, 0.0F, 0.0F, alpha);
        }
    }

    private static float easeOutCubic(float x)
    {
        float inv = 1.0F - x;
        return 1.0F - inv * inv * inv;
    }
}

package com.projectseele.client.fx;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

import com.mojang.blaze3d.platform.NativeImage;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.blaze3d.vertex.VertexFormat;
import com.projectseele.ProjectSeele;
import com.projectseele.client.render.RibbonRenderer;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.texture.DynamicTexture;
import net.minecraft.resources.ResourceLocation;
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
 * A.T. Field presentation: a planar octagonal field that answers each impact
 * with octagonal wavefronts racing out from the contact point, lighting the
 * field's standing rings as they pass. Impacts that land on an already
 * visible field re-energise it instead of stacking another plane, so
 * sustained pressure reads as one field under strain.
 *
 * Presentation only; damage and field cost live in the entity code.
 * Mirrored by tools/fx/at_field_preview.py for offline review.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class AtFieldEffects
{
    private static final float TICKS = 20.0F;
    /** Seconds a pulse keeps the field visible after it lands. */
    private static final float HOLD = 1.7F;
    private static final int FRONTS = 4;
    private static final float FRONT_GAP = 0.07F;
    private static final float FRONT_TRAVEL = 0.8F;
    private static final int STANDING_RINGS = 11;
    private static final int MAX_PULSES = 8;
    private static final int MAX_FIELDS = 24;
    private static final float CORNER = 1.0F / Mth.cos((float) (Math.PI / 8));

    private static final ResourceLocation PROFILE = new ResourceLocation(ProjectSeele.MODID, "fx/at_field_profile");
    private static boolean profileReady;

    private static final List<Field> FIELDS = new ArrayList<>();
    private static ClientLevel activeLevel;
    private static long clock;

    private AtFieldEffects() {}

    /** One impact on a field plane: point on the plane, plane normal (toward the attacker), radius in blocks. */
    public static void impact(Vec3 point, Vector3f normal, float radius, float intensity)
    {
        if (intensity <= 0.0F || radius <= 0.0F)
        {
            return;
        }
        ensureLevel();
        if (com.projectseele.client.visual.EvaConnectedActionReview.ENABLED)
        {
            ProjectSeele.LOGGER.info("AT FIELD impact tick {} at {} radius {} intensity {}", clock, point, radius, intensity);
        }
        Vector3f n = new Vector3f(normal);
        if (n.lengthSquared() < 1.0E-6F)
        {
            n.set(0.0F, 0.0F, 1.0F);
        }
        n.normalize();
        float now = clock;
        for (Field field : FIELDS)
        {
            if (field.accepts(point, n, radius, now))
            {
                field.pulse(point, radius, intensity, now);
                return;
            }
        }
        if (FIELDS.size() >= MAX_FIELDS)
        {
            FIELDS.remove(0);
        }
        Field field = new Field(point, n, radius);
        field.pulse(point, radius, intensity, now);
        FIELDS.add(field);
    }

    @SubscribeEvent
    public static void onClientTick(TickEvent.ClientTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END)
        {
            return;
        }
        ensureLevel();
        if (FIELDS.isEmpty())
        {
            return;
        }
        if (Minecraft.getInstance().isPaused())
        {
            return;
        }
        clock++;
        Iterator<Field> it = FIELDS.iterator();
        while (it.hasNext())
        {
            if (it.next().expired(clock))
            {
                it.remove();
            }
        }
    }

    @SubscribeEvent
    public static void onRenderLevelStage(RenderLevelStageEvent event)
    {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_PARTICLES || FIELDS.isEmpty())
        {
            return;
        }
        ensureProfile();
        float now = clock + event.getPartialTick();
        PoseStack stack = event.getPoseStack();
        Vec3 cam = event.getCamera().getPosition();
        MultiBufferSource.BufferSource buffers = Minecraft.getInstance().renderBuffers().bufferSource();
        VertexConsumer fill = buffers.getBuffer(Types.FILL);
        for (Field field : FIELDS)
        {
            stack.pushPose();
            stack.translate(field.center.x - cam.x, field.center.y - cam.y, field.center.z - cam.z);
            field.renderFill(stack.last().pose(), fill, now);
            stack.popPose();
        }
        buffers.endBatch(Types.FILL);
        for (boolean core : new boolean[] {false, true})
        {
            RenderType type = core ? Types.GLOW : Types.TINT;
            VertexConsumer out = buffers.getBuffer(type);
            for (Field field : FIELDS)
            {
                stack.pushPose();
                stack.translate(field.center.x - cam.x, field.center.y - cam.y, field.center.z - cam.z);
                field.renderRings(stack.last().pose(), out, now, core);
                stack.popPose();
            }
            buffers.endBatch(type);
        }
    }

    private static void ensureLevel()
    {
        ClientLevel level = Minecraft.getInstance().level;
        if (activeLevel != level)
        {
            FIELDS.clear();
            activeLevel = level;
        }
    }

    /** A 1D cross-section, white with a soft glow skirt around a sharp core; u = 0.5 is the peak. */
    private static void ensureProfile()
    {
        if (profileReady)
        {
            return;
        }
        int width = 128;
        NativeImage image = new NativeImage(width, 4, false);
        for (int x = 0; x < width; x++)
        {
            float t = Math.abs((x + 0.5F) / width - 0.5F) * 2.0F;
            float skirt = (float) Math.exp(-t * t * 5.0F) * (1.0F - t * t * t * t);
            float core = (float) Math.exp(-t * t * 70.0F);
            int alpha = Mth.clamp(Math.round(255.0F * Math.max(skirt * 0.55F, core)), 0, 255);
            for (int y = 0; y < 4; y++)
            {
                image.setPixelRGBA(x, y, (alpha << 24) | 0x00FFFFFF);
            }
        }
        Minecraft.getInstance().getTextureManager().register(PROFILE, new DynamicTexture(image));
        profileReady = true;
    }

    private static float easeOut(float x, float power)
    {
        return 1.0F - (float) Math.pow(1.0F - Mth.clamp(x, 0.0F, 1.0F), power);
    }

    private static float hash(long seed)
    {
        long h = seed * 0x9E3779B97F4A7C15L;
        h ^= h >>> 29;
        h *= 0xBF58476D1CE4E5B9L;
        h ^= h >>> 32;
        return (h & 0xFFFFFF) / (float) 0xFFFFFF;
    }

    private static final class Pulse
    {
        final float a;
        final float b;
        final float start;
        final float intensity;

        Pulse(float a, float b, float start, float intensity)
        {
            this.a = a;
            this.b = b;
            this.start = start;
            this.intensity = intensity;
        }
    }

    private static final class Field
    {
        final Vec3 center;
        final Vector3f normal;
        final Vector3f u;
        final Vector3f v;
        float radius;
        final List<Pulse> pulses = new ArrayList<>();
        float last;

        Field(Vec3 center, Vector3f normal, float radius)
        {
            this.center = center;
            this.normal = normal;
            Vector3f[] basis = RibbonRenderer.planeBasis(normal);
            this.u = basis[0];
            this.v = basis[1];
            this.radius = radius;
        }

        boolean accepts(Vec3 point, Vector3f n, float r, float now)
        {
            if ((now - this.last) / TICKS > 0.9F || this.normal.dot(n) < 0.85F)
            {
                return false;
            }
            Vec3 d = point.subtract(this.center);
            double off = d.x * this.normal.x + d.y * this.normal.y + d.z * this.normal.z;
            double plane = d.subtract(this.normal.x * off, this.normal.y * off, this.normal.z * off).length();
            return Math.abs(off) < this.radius * 0.25F && plane < this.radius * 0.5F;
        }

        void pulse(Vec3 point, float r, float intensity, float now)
        {
            Vec3 d = point.subtract(this.center);
            float a = (float) (d.x * this.u.x + d.y * this.u.y + d.z * this.u.z);
            float b = (float) (d.x * this.v.x + d.y * this.v.y + d.z * this.v.z);
            this.radius = Math.max(this.radius, r);
            if (this.pulses.size() >= MAX_PULSES)
            {
                this.pulses.remove(0);
            }
            this.pulses.add(new Pulse(a, b, now, Mth.clamp(intensity, 0.0F, 1.5F)));
            this.last = now;
        }

        boolean expired(float now)
        {
            return (now - this.last) / TICKS > HOLD;
        }

        /** Field presence: a fast rise after the first pulse, decaying after the last. */
        float presence(float now)
        {
            float first = this.pulses.isEmpty() ? now : this.pulses.get(0).start;
            float rise = easeOut((now - first) / TICKS / 0.06F, 2.0F);
            float since = (now - this.last) / TICKS;
            float fall = 1.0F - (float) Mth.smoothstep(Mth.clamp((since - 0.25F) / (HOLD - 0.25F), 0.0F, 1.0F));
            return rise * fall;
        }

        /** Brightness of the newest strike, for the membrane flash. */
        float flash(float now)
        {
            float best = 0.0F;
            for (Pulse p : this.pulses)
            {
                float t = (now - p.start) / TICKS;
                if (t >= 0.0F)
                {
                    best = Math.max(best, p.intensity * (float) Math.exp(-t * 7.0F));
                }
            }
            return best;
        }

        void renderFill(Matrix4f pose, VertexConsumer out, float now)
        {
            float presence = this.presence(now);
            if (presence <= 0.002F)
            {
                return;
            }
            float flash = this.flash(now);
            // Strong enough to read under a shader pack: golden centre, deep orange edge.
            float alpha = presence * (0.15F + 0.22F * flash);
            float r = this.radius * 1.04F * CORNER;
            for (int edge = 0; edge < 8; edge++)
            {
                float a0 = (float) (Math.PI / 8 + edge * Math.PI / 4);
                float a1 = a0 + (float) (Math.PI / 4);
                fillVertex(pose, out, 0.0F, 0.0F, 1.0F, 0.68F, 0.24F, alpha * 1.5F);
                fillVertex(pose, out, Mth.cos(a0) * r, Mth.sin(a0) * r, 1.0F, 0.38F, 0.05F, alpha * 0.75F);
                fillVertex(pose, out, Mth.cos(a1) * r, Mth.sin(a1) * r, 1.0F, 0.38F, 0.05F, alpha * 0.75F);
                fillVertex(pose, out, 0.0F, 0.0F, 1.0F, 0.68F, 0.24F, alpha * 1.5F);
            }
        }

        /**
         * Rings in two passes: an orange translucent tint (reads on a bright
         * sky, where additive light would only wash out to white) and a thin
         * additive white-hot core.
         */
        void renderRings(Matrix4f pose, VertexConsumer out, float now, boolean core)
        {
            float presence = this.presence(now);
            if (presence <= 0.002F)
            {
                return;
            }
            float flicker = 0.9F + 0.1F * hash((long) now + this.center.hashCode());
            float R = this.radius;
            // Standing rings of the field, lit as wavefronts pass through them.
            for (int ring = 0; ring < STANDING_RINGS; ring++)
            {
                float rr = R * (0.1F + 0.9F * ring / (STANDING_RINGS - 1));
                float lit = 0.0F;
                for (Pulse p : this.pulses)
                {
                    for (int f = 0; f < FRONTS; f++)
                    {
                        float t = (now - p.start) / TICKS - f * FRONT_GAP;
                        if (t <= 0.0F || t >= FRONT_TRAVEL)
                        {
                            continue;
                        }
                        float g = (rr - frontRadius(R, t / FRONT_TRAVEL)) / (R * 0.075F);
                        lit += p.intensity * (float) Math.exp(-g * g) * (1.0F - 0.2F * f);
                    }
                }
                lit = Math.min(lit, 1.0F);
                float edge = ring == STANDING_RINGS - 1 ? 1.35F : 1.0F;
                if (core)
                {
                    float width = R * 0.006F;
                    band(pose, out, 0.0F, 0.0F, rr - width, rr + width, 0.0F, 1.0F,
                            1.0F, 0.82F, 0.55F, presence * flicker * (0.10F + 0.9F * lit) * edge);
                }
                else
                {
                    float width = R * (0.02F + 0.012F * lit);
                    band(pose, out, 0.0F, 0.0F, rr - width, rr + width, 0.0F, 1.0F,
                            1.0F, 0.46F, 0.08F, presence * flicker * (0.24F + 0.55F * lit) * edge);
                }
            }
            // A crisp rim keeps the field's boundary readable on any sky.
            if (core)
            {
                band(pose, out, 0.0F, 0.0F, R * 0.985F, R * 1.005F, 0.0F, 1.0F, 1.0F, 0.88F, 0.62F, presence * flicker * 0.55F);
            }
            else
            {
                band(pose, out, 0.0F, 0.0F, R * 0.955F, R * 1.03F, 0.0F, 1.0F, 1.0F, 0.44F, 0.07F, presence * flicker * 0.42F);
            }
            // Wavefronts from every strike, then a hot contact flash.
            for (Pulse p : this.pulses)
            {
                float age = (now - p.start) / TICKS;
                if (age < 0.0F)
                {
                    continue;
                }
                for (int f = 0; f < FRONTS; f++)
                {
                    float t = age - f * FRONT_GAP;
                    if (t <= 0.0F || t >= FRONT_TRAVEL)
                    {
                        continue;
                    }
                    float progress = t / FRONT_TRAVEL;
                    float front = frontRadius(R, progress);
                    float beyond = 1.0F - (float) Mth.smoothstep(Mth.clamp((front / R - 0.9F) / 0.3F, 0.0F, 1.0F));
                    float bright = p.intensity * flicker * presence * (1.0F - 0.18F * f) * beyond
                            * (float) Math.pow(1.0F - progress, 1.4F) * Mth.clamp(progress / 0.04F, 0.0F, 1.0F);
                    float width = R * (0.008F + 0.022F * (1.0F - progress));
                    if (core)
                    {
                        band(pose, out, p.a, p.b, front - width, front + width, 0.0F, 1.0F, 1.0F, 0.9F, 0.68F, bright);
                    }
                    else
                    {
                        band(pose, out, p.a, p.b, front - width * 4.0F, front + width * 4.0F, 0.0F, 1.0F,
                                1.0F, 0.42F, 0.06F, bright * 0.75F);
                    }
                }
                float flash = p.intensity * (float) Math.exp(-age * 9.0F) * presence;
                if (flash > 0.01F)
                {
                    float disk = R * (0.08F + 0.16F * easeOut(age / 0.2F, 2.0F));
                    if (core)
                    {
                        band(pose, out, p.a, p.b, 0.0F, disk, 0.5F, 0.0F, 1.0F, 0.94F, 0.8F, flash);
                    }
                    else
                    {
                        band(pose, out, p.a, p.b, 0.0F, disk * 2.2F, 0.5F, 0.0F, 1.0F, 0.5F, 0.1F, flash * 0.75F);
                    }
                }
            }
        }

        private static float frontRadius(float R, float progress)
        {
            return R * (0.04F + 1.12F * easeOut(progress, 1.8F));
        }

        /** Octagonal band around (ca, cb): inner/outer flat-side radii mapped to profile u. */
        private void band(Matrix4f pose, VertexConsumer out, float ca, float cb, float inner, float outer,
                          float uInner, float uOuter, float red, float green, float blue, float alpha)
        {
            if (alpha <= 0.003F)
            {
                return;
            }
            float ri = Math.max(0.0F, inner) * CORNER;
            float ro = Math.max(0.0F, outer) * CORNER;
            float a = Mth.clamp(alpha, 0.0F, 1.0F);
            for (int edge = 0; edge < 8; edge++)
            {
                float a0 = (float) (Math.PI / 8 + edge * Math.PI / 4);
                float a1 = a0 + (float) (Math.PI / 4);
                float c0 = Mth.cos(a0), s0 = Mth.sin(a0), c1 = Mth.cos(a1), s1 = Mth.sin(a1);
                glowVertex(pose, out, ca + c0 * ri, cb + s0 * ri, uInner, red, green, blue, a);
                glowVertex(pose, out, ca + c0 * ro, cb + s0 * ro, uOuter, red, green, blue, a);
                glowVertex(pose, out, ca + c1 * ro, cb + s1 * ro, uOuter, red, green, blue, a);
                glowVertex(pose, out, ca + c1 * ri, cb + s1 * ri, uInner, red, green, blue, a);
            }
        }

        private void fillVertex(Matrix4f pose, VertexConsumer out, float x, float y, float red, float green, float blue, float alpha)
        {
            // The profile's peak texel is opaque white, so the fill takes the vertex colour alone.
            out.vertex(pose, this.u.x * x + this.v.x * y, this.u.y * x + this.v.y * y, this.u.z * x + this.v.z * y)
                    .color(red, green, blue, Mth.clamp(alpha, 0.0F, 0.7F)).uv(0.5F, 0.5F)
                    .uv2(LightTexture.FULL_BRIGHT).normal(0.0F, 1.0F, 0.0F).endVertex();
        }

        private void glowVertex(Matrix4f pose, VertexConsumer out, float x, float y, float texU,
                                float red, float green, float blue, float alpha)
        {
            out.vertex(pose, this.u.x * x + this.v.x * y, this.u.y * x + this.v.y * y, this.u.z * x + this.v.z * y)
                    .color(red, green, blue, alpha).uv(texU, 0.5F).uv2(LightTexture.FULL_BRIGHT).normal(0.0F, 1.0F, 0.0F).endVertex();
        }
    }

    /**
     * All three passes use the beacon beam's shader and vertex format. Shader packs draw that one
     * unlit and bright; with the plain position-colour shaders they lit the field like a solid
     * surface, so under the sun it washed out to a pale sheet and the rings vanished.
     */
    private abstract static class Types extends RenderType
    {
        static final RenderType FILL = create("seele_at_field_fill", DefaultVertexFormat.BLOCK,
                VertexFormat.Mode.QUADS, 16384, false, true, CompositeState.builder()
                        .setShaderState(RENDERTYPE_BEACON_BEAM_SHADER).setTextureState(new TextureStateShard(PROFILE, false, false))
                        .setTransparencyState(TRANSLUCENT_TRANSPARENCY)
                        .setCullState(NO_CULL).setDepthTestState(LEQUAL_DEPTH_TEST).setWriteMaskState(COLOR_WRITE)
                        .createCompositeState(false));
        static final RenderType TINT = create("seele_at_field_tint", DefaultVertexFormat.BLOCK,
                VertexFormat.Mode.QUADS, 131072, false, true, CompositeState.builder()
                        .setShaderState(RENDERTYPE_BEACON_BEAM_SHADER).setTextureState(new TextureStateShard(PROFILE, true, false))
                        .setTransparencyState(TRANSLUCENT_TRANSPARENCY).setCullState(NO_CULL)
                        .setDepthTestState(LEQUAL_DEPTH_TEST).setWriteMaskState(COLOR_WRITE)
                        .createCompositeState(false));
        static final RenderType GLOW = create("seele_at_field_glow", DefaultVertexFormat.BLOCK,
                VertexFormat.Mode.QUADS, 131072, false, true, CompositeState.builder()
                        .setShaderState(RENDERTYPE_BEACON_BEAM_SHADER).setTextureState(new TextureStateShard(PROFILE, true, false))
                        .setTransparencyState(LIGHTNING_TRANSPARENCY).setCullState(NO_CULL)
                        .setDepthTestState(LEQUAL_DEPTH_TEST).setWriteMaskState(COLOR_WRITE)
                        .createCompositeState(false));

        private Types()
        {
            super("seele_at_field_types", DefaultVertexFormat.POSITION_COLOR, VertexFormat.Mode.QUADS, 256, false, false, () -> {}, () -> {});
        }
    }
}

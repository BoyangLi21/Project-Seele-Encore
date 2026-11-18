package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.client.HangarCoolantVisualR52.Tank;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.LevelRenderer;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import org.joml.Vector3f;

/** One two-sided, depth-tested interface. Neighbouring patches share both height and lighting samples. */
@net.minecraftforge.fml.common.Mod.EventBusSubscriber(modid = "projectseele", value = net.minecraftforge.api.distmarker.Dist.CLIENT)
public final class HangarLclSurface
{
    private static final ResourceLocation WHITE = new ResourceLocation("minecraft", "textures/block/white_concrete.png");
    static final RenderType MATERIAL = RenderType.entityTranslucent(WHITE);
    private static final RenderType LIT_FILM = RenderType.entityTranslucentEmissive(WHITE);
    private static final MultiBufferSource.BufferSource WATER = MultiBufferSource.immediate(new com.mojang.blaze3d.vertex.BufferBuilder(262144));
    private static final int X = 13, Z = 14;
    private static final class Point
    {
        float x, y, z, nx, nz;
        int red, green, blue, alpha, light;
    }
    private static final Point[][] rows = new Point[2][X + 1];

    static
    {
        for (var row : rows) for (int i = 0; i < row.length; i++) row[i] = new Point();
    }

    private static final class Lighting
    {
        int[][] grid = new int[Z + 1][X + 1];
        int tick = -20, height = Integer.MIN_VALUE;
    }

    private static final java.util.Map<Tank, Lighting> lights = new java.util.WeakHashMap<>();

    @net.minecraftforge.eventbus.api.SubscribeEvent
    public static void renderLevel(net.minecraftforge.client.event.RenderLevelStageEvent event)
    {
        boolean shaders = ShaderShadowPassR44.enabled();
        var pass = shaders ? net.minecraftforge.client.event.RenderLevelStageEvent.Stage.AFTER_TRANSLUCENT_BLOCKS
                : net.minecraftforge.client.event.RenderLevelStageEvent.Stage.AFTER_ENTITIES;
        if (event.getStage() != pass
                || ShaderShadowPassR44.active()) return;
        var mc = Minecraft.getInstance();
        var camera = event.getCamera().getPosition();
        var poses = event.getPoseStack();
        var buffers = WATER;
        double range = mc.options.getEffectiveRenderDistance() * 16.0 + 36;
        boolean drew = false;
        for (int variant = 0; variant < 3; variant++)
        {
            var tank = com.projectseele.client.HangarCoolantVisualR52.tank(variant);
            if (tank == null || tank.gantry.level() != mc.level || tank.gantry.isRemoved()) continue;
            var b = tank.bounds;
            var box = new net.minecraft.world.phys.AABB(b.x() - 19, b.floor(), b.z() - 26, b.x() + 20, b.floor() + 44, b.z() + 27);
            if (box.distanceToSqr(camera) > range * range || !event.getFrustum().isVisible(box)) continue;
            poses.pushPose();
            try
            {
                poses.translate(tank.gantry.getX() - camera.x, tank.gantry.getY() - camera.y, tank.gantry.getZ() - camera.z);
                poses.mulPose(tank.gantry.declaredMachineRotationR52());
                render(tank, event.getPartialTick(), poses, buffers);
                drew = true;
            }
            finally { poses.popPose(); }
        }
        if (drew) buffers.endBatch();
    }

    private static void render(Tank tank, float partial, PoseStack poses, MultiBufferSource buffers)
    {
        if (ShaderShadowPassR44.active()) return;
        var entity = tank.gantry;
        float surface = tank.surface(partial);
        if (surface <= tank.bounds.floor() + .003F) return;
        float y = (float)(surface - entity.getY());
        float time = (entity.level().getGameTime() % 24000 + partial) * .05F;
        var toEye = Minecraft.getInstance().gameRenderer.getMainCamera().getPosition().subtract(entity.position());
        var inverse = entity.declaredMachineRotationR52().conjugate(new org.joml.Quaternionf());
        var eye = inverse.transform(new Vector3f((float)toEye.x, (float)toEye.y, (float)toEye.z));
        var rotation = entity.declaredMachineRotationR52();
        var world = new Vector3f();
        var at = new BlockPos.MutableBlockPos();
        boolean shaders = ShaderShadowPassR44.enabled();
        var out = buffers.getBuffer(shaders ? LIT_FILM : MATERIAL);
        var lighting = lights.computeIfAbsent(tank, ignored -> new Lighting());
        int height = Mth.floor(surface + .4F);
        boolean relight = lighting.height != height || entity.tickCount - lighting.tick >= 10;
        if (relight)
        {
            lighting.tick = entity.tickCount;
            lighting.height = height;
        }
        if (eye.y > y)
        {
            // Weak extinction within the volume: the lower plates of the EVA are seen through more
            // amber liquid than its shoulders. The same continuous height drives the lowest partial slice.
            final float spacing = 2F;
            float depth = surface - tank.bounds.floor();
            for (int layer = Mth.ceil(depth / spacing) - 1; layer >= 0; layer--)
            {
                float thickness = Math.min(spacing, depth - layer * spacing);
                float distance = (layer * spacing + thickness * .5F);
                float sliceY = y - distance;
                int alpha = Math.round((shaders ? 9 : 12) * thickness / spacing);
                int light = LevelRenderer.getLightColor(entity.level(), at.set(entity.getX(), entity.getY() + sliceY, entity.getZ()));
                for (int iz = 0; iz < 3; iz++) for (int ix = 0; ix < 3; ix++)
                {
                    float x0 = -19.5F + ix * 13, z0 = -26.5F + iz * (53F / 3);
                    float x1 = x0 + 13F, z1 = z0 + 53F / 3;
                    volume(out, poses.last(), x0, sliceY, z1, alpha, light, shaders);
                    volume(out, poses.last(), x1, sliceY, z1, alpha, light, shaders);
                    volume(out, poses.last(), x1, sliceY, z0, alpha, light, shaders);
                    volume(out, poses.last(), x0, sliceY, z0, alpha, light, shaders);
                }
            }
        }
        for (int iz = 0; iz <= Z; iz++)
        {
            Point[] row = rows[iz & 1], previous = rows[(iz + 1) & 1];
            for (int ix = 0; ix <= X; ix++)
            {
                float x = -19.5F + 39F * ix / X, z = -26.5F + 53F * iz / Z;
                float a = x * .30F + z * .16F + time * .72F, b = z * .39F - x * .11F - time * .53F;
                float wave = .028F * Mth.sin(a) + .018F * Mth.sin(b);
                float nx = -.0084F * Mth.cos(a) + .0020F * Mth.cos(b);
                float nz = -.0045F * Mth.cos(a) - .0070F * Mth.cos(b);
                float dx = eye.x - x, dz = eye.z - z, dy = eye.y - y;
                float length = Math.max(.001F, Mth.sqrt(dx * dx + dy * dy + dz * dz));
                float grazing = 1F - Mth.clamp(Math.abs((dy + nx * dx + nz * dz) / length), 0F, 1F);
                float reflect = grazing * grazing;
                // Soft reflections of the two long cage-side light banks in the disturbed normal.
                float bank = Math.abs(x + dx / length * 7 + nx * 90) - 15;
                float highlight = reflect * (float)Math.exp(-bank * bank * .10F);
                if (relight)
                {
                    rotation.transform(world.set(x, y + .4F, z));
                    at.set(entity.getX() + world.x, entity.getY() + world.y, entity.getZ() + world.z);
                    lighting.grid[iz][ix] = LevelRenderer.getLightColor(entity.level(), at);
                }
                var p = row[ix];
                p.x = x; p.y = y + wave * Mth.clamp(surface - tank.bounds.floor(), 0, 1); p.z = z;
                p.nx = nx; p.nz = nz; p.light = lighting.grid[iz][ix];
                if (shaders)
                {
                    // The face represents reflected lamp light. A submerged light sample on its own
                    // is nearly black after Complementary applies cave exposure to translucent entities.
                    p.light = net.minecraft.client.renderer.LightTexture.pack(
                            Math.max(11, net.minecraft.client.renderer.LightTexture.block(p.light)),
                            net.minecraft.client.renderer.LightTexture.sky(p.light));
                }
                p.red = (int)(shaders ? 121 + 60 * highlight : 224 + 25 * highlight);
                p.green = (int)(shaders ? 70 + 43 * highlight : 127 + 67 * highlight);
                p.blue = (int)(shaders ? 35 + 37 * highlight : 54 + 89 * highlight);
                p.alpha = (int)(103 + 69 * reflect + 28 * highlight);
                if (iz != 0 && ix != 0)
                {
                    vertex(out, poses.last(), row[ix - 1]); vertex(out, poses.last(), row[ix]);
                    vertex(out, poses.last(), previous[ix]); vertex(out, poses.last(), previous[ix - 1]);
                }
            }
        }
    }

    private static void volume(VertexConsumer out, PoseStack.Pose pose, float x, float y, float z, int alpha, int light, boolean shaders)
    {
        out.vertex(pose.pose(), x, y, z).color(shaders ? 71 : 185, shaders ? 34 : 89, shaders ? 16 : 37, alpha)
                .uv(.5F, .5F).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light)
                .normal(pose.normal(), 0, 1, 0).endVertex();
    }

    private static void vertex(VertexConsumer out, PoseStack.Pose pose, Point p)
    {
        out.vertex(pose.pose(), p.x, p.y, p.z).color(p.red, p.green, p.blue, p.alpha)
                .uv(.5F, .5F).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(p.light)
                .normal(pose.normal(), p.nx, 1, p.nz).endVertex();
    }

    private HangarLclSurface() {}
}
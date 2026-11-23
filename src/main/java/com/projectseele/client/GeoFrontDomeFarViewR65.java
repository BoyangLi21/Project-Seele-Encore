package com.projectseele.client;

import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.platform.NativeImage;
import java.util.List;
import net.minecraft.client.renderer.block.model.BakedQuad;
import net.minecraft.client.renderer.texture.TextureAtlasSprite;
import net.minecraft.core.Direction;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraftforge.client.model.data.ModelData;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.VertexBuffer;
import com.mojang.blaze3d.vertex.VertexFormat;
import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import com.projectseele.world.FacilitySchemaV2;
import java.io.BufferedInputStream;
import java.io.DataInputStream;
import java.io.EOFException;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.zip.GZIPInputStream;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.ShaderInstance;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LeavesBlock;
import net.minecraft.world.level.FoliageColor;
import net.minecraft.client.renderer.BiomeColors;
import net.minecraft.world.level.material.MapColor;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RegisterShadersEvent;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;
import org.lwjgl.opengl.GL11;

/**
 * R65: the GeoFront cavity's far view. Distant Horizons cannot hold the cavity: with the vertical quality the pack
 * uses each column keeps too few spans, so the dome breaks up, and the hanging towers get no sky light underground
 * and come out black. Inside the cavity this draws a silhouette baked from the real blocks instead (the floor, the
 * lake, the dome's inner surface and the hanging city, tools/bake_geofront_dome.py) and holds Distant Horizons back
 * (DhGeoFrontFarViewR65Mixin).
 * <p>
 * The silhouette is drawn right after the sky with a projection of its own reaching the far side of the cavity; the
 * depth it wrote is then cleared, so the real chunks draw over it as if it were sky. Its shader drops everything within
 * the vanilla render distance (horizontally), where the real chunks are, so the two never overlap. Faces take their
 * block's texture colour for that side (as Distant Horizons colours its far view; tinted faces the cavity biome's tint),
 * shaded by facing, and fade into the fog colour with distance.
 * <p>
 * The mesh is a private build product installed into the pack's jar; without it nothing changes.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class GeoFrontDomeFarViewR65
{
    private static final ResourceLocation MESH = new ResourceLocation(ProjectSeele.MODID, "geofront/dome_far_r65.bin.gz");
    /** The cavity (the R64 area maps' measured rim), and the band from its floor to under its roof. */
    private static final double CENTRE_X = 32, CENTRE_Z = 320, RADIUS = 1900, MIN_Y = -530, MAX_Y = 56;
    private static final float FAR = 6000F, NEAR = 8F, FOG_END = 5000F, FOG_STRENGTH = .7F;

    private static ShaderInstance shader;
    private static VertexBuffer buffer;
    private static boolean loaded, missing, failed;
    private static int quads;
    private static float originX, originY, originZ;
    private static boolean active;

    private GeoFrontDomeFarViewR65() {}

    @Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT, bus = Mod.EventBusSubscriber.Bus.MOD)
    public static final class Shaders
    {
        @SubscribeEvent
        public static void register(RegisterShadersEvent event) throws IOException
        {
            event.registerShader(new ShaderInstance(event.getResourceProvider(), new ResourceLocation(ProjectSeele.MODID, "geofront_dome_far"),
                    DefaultVertexFormat.POSITION_COLOR), instance -> shader = instance);
        }
    }

    /** True while the camera is inside the cavity and the silhouette stands in for the Distant Horizons far view. */
    public static boolean suppressDistantHorizons()
    {
        return active;
    }

    private static boolean inCavity(Minecraft mc, double x, double y, double z)
    {
        if (mc.level == null || !mc.level.dimension().equals(FacilitySchemaV2.DIMENSION)) return false;
        double dx = x - CENTRE_X, dz = z - CENTRE_Z;
        return y >= MIN_Y && y <= MAX_Y && dx * dx + dz * dz <= RADIUS * RADIUS;
    }

    @SubscribeEvent
    public static void render(RenderLevelStageEvent event)
    {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_SKY) return;
        Minecraft mc = Minecraft.getInstance();
        var camera = event.getCamera().getPosition();
        boolean wanted = !failed && !missing && SeeleConfig.CLIENT_SPEC.isLoaded() && SeeleConfig.GEOFRONT_FAR_VIEW.get()
                && inCavity(mc, camera.x, camera.y, camera.z);
        if (!wanted)
        {
            active = false;
            return;
        }
        if (com.projectseele.client.render.ShaderShadowPassR44.active()) return;
        try
        {
            if (!loaded) load(mc);
            if (buffer == null || shader == null)
            {
                active = false;
                return;
            }
            active = true;
            draw(event, mc, camera.x, camera.y, camera.z);
        }
        catch (IOException | RuntimeException problem)
        {
            failed = true;
            active = false;
            ProjectSeele.LOGGER.warn("GeoFront far view R65 off: {}", problem.toString(), problem);
        }
    }

    private static void draw(RenderLevelStageEvent event, Minecraft mc, double x, double y, double z)
    {
        float camX = (float) (x - originX), camY = (float) (y - originY), camZ = (float) (z - originZ);
        Matrix4f view = new Matrix4f(event.getPoseStack().last().pose()).translate(-camX, -camY, -camZ);
        // the frame's own projection (field of view, bobbing) with a depth range that reaches across the cavity
        Matrix4f projection = new Matrix4f(event.getProjectionMatrix());
        projection.m22((FAR + NEAR) / (NEAR - FAR));
        projection.m32(2F * FAR * NEAR / (NEAR - FAR));
        float nearCut = mc.options.getEffectiveRenderDistance() * 16F - 8F;
        float light = (float) (double) SeeleConfig.GEOFRONT_FAR_LIGHT.get();
        float fogStart = RenderSystem.getShaderFogStart(), fogEnd = RenderSystem.getShaderFogEnd();
        float[] fogColour = RenderSystem.getShaderFogColor().clone();
        shader.safeGetUniform("Camera").set(camX, camY, camZ);
        shader.safeGetUniform("NearCut").set(nearCut);
        RenderSystem.setShaderFogStart(nearCut);
        RenderSystem.setShaderFogEnd(FOG_END);
        RenderSystem.setShaderFogColor(fogColour[0], fogColour[1], fogColour[2], FOG_STRENGTH);
        RenderSystem.setShaderColor(light, light, light, 1F);
        RenderSystem.enableDepthTest();
        RenderSystem.depthFunc(GL11.GL_LEQUAL);
        RenderSystem.depthMask(true);
        RenderSystem.disableCull();
        RenderSystem.disableBlend();
        try
        {
            buffer.bind();
            buffer.drawWithShader(view, projection, shader);
            VertexBuffer.unbind();
        }
        finally
        {
            RenderSystem.setShaderColor(1F, 1F, 1F, 1F);
            RenderSystem.setShaderFogStart(fogStart);
            RenderSystem.setShaderFogEnd(fogEnd);
            RenderSystem.setShaderFogColor(fogColour[0], fogColour[1], fogColour[2], fogColour[3]);
            RenderSystem.enableCull();
            // the real chunks draw over the silhouette as over the sky
            RenderSystem.clear(GL11.GL_DEPTH_BUFFER_BIT, Minecraft.ON_OSX);
        }
    }

    private static void load(Minecraft mc) throws IOException
    {
        loaded = true;
        var resource = mc.getResourceManager().getResource(MESH);
        if (resource.isEmpty())
        {
            missing = true;
            ProjectSeele.LOGGER.info("GeoFront far view R65: no baked mesh in this jar ({}), Distant Horizons stays", MESH);
            return;
        }
        long began = System.nanoTime();
        try (InputStream raw = resource.get().open();
             DataInputStream in = new DataInputStream(new BufferedInputStream(new GZIPInputStream(raw), 1 << 16)))
        {
            byte[] magic = new byte[4];
            in.readFully(magic);
            if (!"SGDM".equals(new String(magic, StandardCharsets.US_ASCII))) throw new IOException("not a GeoFront far-view mesh");
            ByteBuffer head = little(in, 2 + 12 + 2);
            int version = head.get() & 0xFF, cell = head.get() & 0xFF;
            if (version != 1 || cell <= 0) throw new IOException("unknown mesh version " + version);
            originX = head.getInt();
            originY = head.getInt();
            originZ = head.getInt();
            int names = head.getShort() & 0xFFFF;
            // the cavity is one biome; its tints are read where the camera is, inside it
            var at = mc.gameRenderer.getMainCamera().getBlockPosition();
            int foliage = BiomeColors.getAverageFoliageColor(mc.level, at);
            int grass = BiomeColors.getAverageGrassColor(mc.level, at);
            int water = BiomeColors.getAverageWaterColor(mc.level, at);
            // per block: the colour of its top, its bottom and its sides
            int[][] colours = new int[3][names];
            for (int i = 0; i < names; i++)
            {
                int length = little(in, 2).getShort() & 0xFFFF;
                byte[] text = new byte[length];
                in.readFully(text);
                int[] three = colours(mc, new String(text, StandardCharsets.UTF_8), foliage, grass, water);
                for (int k = 0; k < 3; k++) colours[k][i] = three[k];
            }
            quads = little(in, 4).getInt();
            // the bake keeps to 250,000 (16 MB of vertices); anything far past that is not a mesh this was made for
            if (quads < 0 || quads > 400_000) throw new IOException("too many quads " + quads);
            // a builder of its own: the shared one left half-built by a bad file broke every later draw that used it
            BufferBuilder builder = new BufferBuilder(quads * 4 * DefaultVertexFormat.POSITION_COLOR.getVertexSize() + 256);
            builder.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.POSITION_COLOR);
            ByteBuffer quad = ByteBuffer.allocate(13).order(ByteOrder.LITTLE_ENDIAN);
            for (int i = 0; i < quads; i++)
            {
                quad.clear();
                in.readFully(quad.array());
                int x = quad.getShort(), y = quad.getShort(), z = quad.getShort();
                int du = quad.getShort() & 0xFFFF, dv = quad.getShort() & 0xFFFF, face = quad.get() & 0xFF;
                int index = quad.getShort() & 0xFFFF;
                int which = face == 3 ? 0 : face == 2 ? 1 : 2;
                emit(builder, face, x * cell, y * cell, z * cell, du * cell, dv * cell, cell, index < names ? colours[which][index] : 0x808080);
            }
            buffer = new VertexBuffer(VertexBuffer.Usage.STATIC);
            buffer.bind();
            buffer.upload(builder.end());
            VertexBuffer.unbind();
        }
        catch (EOFException truncated)
        {
            throw new IOException("truncated GeoFront far-view mesh", truncated);
        }
        ProjectSeele.LOGGER.info("GeoFront far view R65: {} quads ({} MB of vertices) ready in {} ms", quads,
                quads * 4L * DefaultVertexFormat.POSITION_COLOR.getVertexSize() / (1 << 20), (System.nanoTime() - began) / 1_000_000);
    }

    private static ByteBuffer little(DataInputStream in, int length) throws IOException
    {
        byte[] bytes = new byte[length];
        in.readFully(bytes);
        return ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
    }

    /**
     * The block's colours as its own textures show them (the average of the texture each side of its model uses, as
     * Distant Horizons colours its far view, so the silhouette meets the real blocks at the render distance without a
     * change of colour); faces the biome tints take the cavity's tint. Water has no model: its still texture and the
     * water tint. Anything unreadable falls back to the block's map colour.
     */
    private static int[] colours(Minecraft mc, String id, int foliage, int grass, int water)
    {
        ResourceLocation key = ResourceLocation.tryParse(id);
        Block block = key == null ? Blocks.AIR : BuiltInRegistries.BLOCK.get(key);
        if (block == Blocks.WATER)
        {
            int c = tint(average(mc, new ResourceLocation("minecraft", "block/water_still")), water);
            return new int[]{c, c, c};
        }
        BlockState state = block.defaultBlockState();
        int fallback = mapColour(block);
        int[] out = new int[3];
        Direction[] sides = {Direction.UP, Direction.DOWN, Direction.NORTH};
        var model = mc.getBlockRenderer().getBlockModel(state);
        RandomSource random = RandomSource.create(42L);
        for (int k = 0; k < 3; k++)
        {
            List<BakedQuad> quads = model.getQuads(state, sides[k], random, ModelData.EMPTY, null);
            if (quads.isEmpty()) quads = model.getQuads(state, null, random, ModelData.EMPTY, null);
            BakedQuad quad = quads.isEmpty() ? null : quads.get(0);
            TextureAtlasSprite sprite = quad != null ? quad.getSprite() : model.getParticleIcon(ModelData.EMPTY);
            int c = average(mc, sprite.contents().name());
            if (c < 0) c = fallback;
            else if (quad != null && quad.isTinted())
                c = tint(c, block instanceof LeavesBlock || block == Blocks.VINE ? leafTint(block, foliage) : grass);
            out[k] = c;
        }
        return out;
    }

    private static int leafTint(Block block, int foliage)
    {
        if (block == Blocks.SPRUCE_LEAVES) return FoliageColor.getEvergreenColor();
        if (block == Blocks.BIRCH_LEAVES) return FoliageColor.getBirchColor();
        return foliage;
    }

    private static int mapColour(Block block)
    {
        MapColor colour = block.defaultMapColor();
        if (colour == null || colour == MapColor.NONE || colour.col == 0) return 0x8C9CA4;
        return scale(colour.col, 220F / 255F);
    }

    /** The mean colour of a texture's opaque pixels (first frame of an animated one), or -1 when it cannot be read. */
    private static int average(Minecraft mc, ResourceLocation sprite)
    {
        ResourceLocation file = new ResourceLocation(sprite.getNamespace(), "textures/" + sprite.getPath() + ".png");
        try (InputStream in = mc.getResourceManager().open(file); NativeImage image = NativeImage.read(in))
        {
            int w = image.getWidth(), h = Math.min(image.getHeight(), image.getWidth());
            long r = 0, g = 0, b = 0, n = 0;
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                {
                    int abgr = image.getPixelRGBA(x, y);
                    if ((abgr >>> 24) < 128) continue;
                    r += abgr & 0xFF;
                    g += (abgr >> 8) & 0xFF;
                    b += (abgr >> 16) & 0xFF;
                    n++;
                }
            if (n == 0) return -1;
            return (int) (r / n) << 16 | (int) (g / n) << 8 | (int) (b / n);
        }
        catch (IOException | RuntimeException unreadable)
        {
            return -1;
        }
    }

    private static int tint(int rgb, int tint)
    {
        if (rgb < 0) return tint;
        return (((rgb >> 16) & 0xFF) * ((tint >> 16) & 0xFF) / 255) << 16 | (((rgb >> 8) & 0xFF) * ((tint >> 8) & 0xFF) / 255) << 8
                | ((rgb & 0xFF) * (tint & 0xFF) / 255);
    }

    private static int scale(int rgb, float f)
    {
        return ((int) (((rgb >> 16) & 0xFF) * f) << 16) | ((int) (((rgb >> 8) & 0xFF) * f) << 8) | (int) ((rgb & 0xFF) * f);
    }

    /** One face: x, y, z the solid cell's corner in blocks, du and dv its extent along the face's in-plane axes. */
    private static void emit(BufferBuilder out, int face, int x, int y, int z, int du, int dv, int cell, int rgb)
    {
        // facing shade, as the world's own blocks: lit from above, darker underneath and on the sides
        float shade = switch (face) { case 3 -> 1F; case 2 -> .62F; case 0, 1 -> .8F; default -> .72F; };
        int r = (int) (((rgb >> 16) & 0xFF) * shade), g = (int) (((rgb >> 8) & 0xFF) * shade), b = (int) ((rgb & 0xFF) * shade);
        switch (face)
        {
            case 0, 1 ->
            {
                float px = face == 1 ? x + cell : x;
                vertex(out, px, y, z, r, g, b);
                vertex(out, px, y + du, z, r, g, b);
                vertex(out, px, y + du, z + dv, r, g, b);
                vertex(out, px, y, z + dv, r, g, b);
            }
            case 2, 3 ->
            {
                float py = face == 3 ? y + cell : y;
                vertex(out, x, py, z, r, g, b);
                vertex(out, x, py, z + dv, r, g, b);
                vertex(out, x + du, py, z + dv, r, g, b);
                vertex(out, x + du, py, z, r, g, b);
            }
            default ->
            {
                float pz = face == 5 ? z + cell : z;
                vertex(out, x, y, pz, r, g, b);
                vertex(out, x + du, y, pz, r, g, b);
                vertex(out, x + du, y + dv, pz, r, g, b);
                vertex(out, x, y + dv, pz, r, g, b);
            }
        }
    }

    private static void vertex(BufferBuilder out, float x, float y, float z, int r, int g, int b)
    {
        out.vertex(x, y, z).color(r, g, b, 255).endVertex();
    }
}

package com.projectseele.client;

import com.mojang.blaze3d.pipeline.RenderTarget;
import com.mojang.blaze3d.pipeline.TextureTarget;
import com.mojang.blaze3d.platform.NativeImage;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.BufferUploader;
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
import java.nio.FloatBuffer;
import java.nio.IntBuffer;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.GZIPInputStream;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.BiomeColors;
import net.minecraft.client.renderer.block.model.BakedQuad;
import net.minecraft.client.renderer.texture.TextureAtlas;
import net.minecraft.client.renderer.texture.TextureAtlasSprite;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.FoliageColor;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LeavesBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.material.MapColor;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.client.model.data.ModelData;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.FrustumIntersection;
import org.joml.Matrix4f;
import org.lwjgl.BufferUtils;
import org.lwjgl.system.MemoryUtil;

import static org.lwjgl.opengl.GL11.*;
import static org.lwjgl.opengl.GL13.GL_ACTIVE_TEXTURE;
import static org.lwjgl.opengl.GL13.GL_TEXTURE0;
import static org.lwjgl.opengl.GL13.glActiveTexture;
import static org.lwjgl.opengl.GL15.*;
import static org.lwjgl.opengl.GL20.*;
import static org.lwjgl.opengl.GL30.*;
import static org.lwjgl.opengl.GL31.*;
import static org.lwjgl.opengl.GL33.glVertexAttribDivisor;
import static org.lwjgl.opengl.GL13.GL_TEXTURE1;

/**
 * R65: the GeoFront cavity's far view. Distant Horizons cannot hold the cavity: with the vertical quality the pack
 * uses each column keeps too few spans, so the dome breaks up, and the hanging towers get no sky light underground
 * and come out black. Inside the cavity this draws the cavity's own blocks instead and holds Distant Horizons back
 * (DhGeoFrontFarViewR65Mixin).
 * <p>
 * The bake (tools/java/BakeGeoFrontFarViewR65.java) keeps every block face that looks into the cavity at one, two and
 * four blocks, in 64x64 tiles. The client groups the tiles into 128x128 cells and draws each cell at the scale its
 * distance calls for (one block near, coarser far), with the texture that side of that block shows (tinted faces with
 * the cavity biome's tint; mostly see-through blocks such as glass as their average colour), shaded by facing, fading
 * into the fog colour with distance. Nothing within the vanilla render distance (in 3D) is drawn, where the real
 * chunks are. It is drawn after the level (under a shader pack, after the pack's last pass) into a multisampled target
 * of its own, resolved and laid over the picture only where nothing was drawn: four samples a pixel keep the one-block
 * seams between the dome's panels from flickering at a distance. Under a pack, water takes the lake's colour the pack
 * gives it. Everything is plain GL with programs of its own: while a pack is in use, Oculus turns colour and depth
 * writes off whenever a mod's shader instance is applied, and swaps the vanilla shaders for the pack's programs.
 * <p>
 * The mesh is a private build product installed into the pack's jar; without it nothing changes.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class GeoFrontDomeFarViewR65
{
    private static final ResourceLocation MESH = new ResourceLocation(ProjectSeele.MODID, "geofront/dome_far_r65.bin.gz");
    /** The cavity (the R64 area maps' measured rim), and the band from its floor to under its roof. */
    private static final double CENTRE_X = 32, CENTRE_Z = 320, RADIUS = 1900, MIN_Y = -530, MAX_Y = 56;
    private static final float FAR = 6000F, NEAR = 8F, FOG_END = 5000F, FOG_STRENGTH = .6F;
    /** Horizontal distance to a cell's nearest point under which it is drawn block by block, then at two blocks. */
    /** Horizontal distance to a cell's nearest point under which it is drawn block by block, then at two blocks. */
    private static final float FINE = 640F, MEDIUM = 1280F, KEEP = 192F;
    /** Under a shader pack the far view is drawn after the pack's lighting; water takes the colour the pack gives the
     *  lake (measured on the Distant Horizons far view of the same lake from the same place). */
    private static final float[] SHADER_WATER = {27 / 255F, 36 / 255F, 47 / 255F};
    /** One instance (16 bytes) per quad: u16 x, y, z (blocks from the cell origin, on the face plane), u16 extents,
     *  u8 face, u8 unused, u16 look (palette entry * 6 + face), u16 unused; the vertex shader makes the corners. */
    private static final int CELL = 128, BAND = 128, INSTANCE = 16, UPLOADS_PER_FRAME = 3;
    private static final long UPLOAD_NANOS = 4_000_000L;

    private record Tile(int x, int z, byte[][] quads, int[] counts) {}

    private static final class Cell
    {
        final int x, z;
        final List<Tile> tiles = new ArrayList<>();
        final int[] vao = new int[3], vbo = new int[3], count = new int[3];
        final boolean[] built = new boolean[3];
        float minY = Float.MAX_VALUE, maxY = -Float.MAX_VALUE;

        Cell(int x, int z) { this.x = x; this.z = z; }
    }

    private static boolean loaded, missing, failed, active;
    private static java.util.concurrent.CompletableFuture<Void> loading;
    private static int levelCount;
    private static int[] scales;
    private static final List<Cell> cells = new ArrayList<>();
    private static float originX, originY, originZ;
    /** Per look (palette entry * 6 + face): sprite rectangle u0, v0, u1, v1, then colour RGB and 1 when textured. */
    private static float[] looks;
    private static int lookBuffer, lookTexture;
    private static long totalQuads, vramBytes;
    private static int drawnCells;
    private static long drawnQuads;

    /** Under a shader pack: the frame's matrices, eye and fog colour from before the sky, drawn after the pack's passes. */
    private static Matrix4f pendingView, pendingProjection;
    private static float[] pendingCamera, pendingFog;
    private static TextureTarget target;
    private static int screenVao, screenVbo, farProgram, blitProgram;
    private static final FloatBuffer MATRIX = BufferUtils.createFloatBuffer(16);

    private GeoFrontDomeFarViewR65() {}

    /** True while the camera is inside the cavity and the far view stands in for the Distant Horizons far view. */
    public static boolean suppressDistantHorizons()
    {
        return active;
    }

    /** For the review log: cells and quads drawn last frame, and the far view's vertex memory. */
    public static String stats()
    {
        return String.format(java.util.Locale.ROOT, "%d cells, %d quads drawn, %d MB of vertices on the GPU", drawnCells, drawnQuads,
                vramBytes >> 20);
    }

    private static java.lang.invoke.MethodHandle dhInstance, dhTasks;
    private static boolean dhTasksMissing;

    /**
     * Distant Horizons' queued render-thread work (uploads and frees of its far-view buffers), which its skipped render
     * passes would have run. The compatibility plugin only lets the suppressing mixin in when this method is there.
     */
    public static void runDistantHorizonsTasks()
    {
        if (dhTasksMissing) return;
        try
        {
            if (dhTasks == null)
            {
                var lookup = java.lang.invoke.MethodHandles.publicLookup();
                Class<?> proxy = Class.forName("com.seibel.distanthorizons.core.render.glObject.GLProxy");
                dhInstance = lookup.findStatic(proxy, "getInstance", java.lang.invoke.MethodType.methodType(proxy));
                dhTasks = lookup.findVirtual(proxy, "runRenderThreadTasks", java.lang.invoke.MethodType.methodType(void.class));
            }
            dhTasks.invoke(dhInstance.invoke());
        }
        catch (Throwable problem)
        {
            // without them DH's far-view buffers pile up, so the far view gives way and DH draws again
            dhTasksMissing = true;
            failed = true;
            active = false;
            ProjectSeele.LOGGER.warn("GeoFront far view R65 off: Distant Horizons' render-thread tasks cannot run: {}", problem.toString());
        }
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
            if (!loaded)
            {
                // read and prepared off the render thread (about a second); Distant Horizons draws until it is ready
                if (loading == null)
                {
                    var at = mc.gameRenderer.getMainCamera().getBlockPosition();
                    int[] tints = {BiomeColors.getAverageFoliageColor(mc.level, at), BiomeColors.getAverageGrassColor(mc.level, at),
                            BiomeColors.getAverageWaterColor(mc.level, at)};
                    loading = java.util.concurrent.CompletableFuture.runAsync(() -> {
                        try
                        {
                            load(mc, tints);
                        }
                        catch (IOException problem)
                        {
                            throw new java.io.UncheckedIOException(problem);
                        }
                    }, net.minecraft.Util.backgroundExecutor());
                }
                if (!loading.isDone())
                {
                    active = false;
                    return;
                }
                loaded = true;
                try
                {
                    loading.join();
                }
                catch (java.util.concurrent.CompletionException problem)
                {
                    throw new IOException(problem.getCause());
                }
            }
            if (cells.isEmpty())
            {
                active = false;
                return;
            }
            active = true;
            float camX = (float) (camera.x - originX), camY = (float) (camera.y - originY), camZ = (float) (camera.z - originZ);
            Matrix4f view = new Matrix4f(event.getPoseStack().last().pose()).translate(-camX, -camY, -camZ);
            // the frame's own projection (field of view, bobbing) with a depth range that reaches across the cavity
            Matrix4f projection = new Matrix4f(event.getProjectionMatrix());
            projection.m22((FAR + NEAR) / (NEAR - FAR));
            projection.m32(2F * FAR * NEAR / (NEAR - FAR));
            float[] fog = RenderSystem.getShaderFogColor().clone();
            int vao = glGetInteger(GL_VERTEX_ARRAY_BINDING), arrayBuffer = glGetInteger(GL_ARRAY_BUFFER_BINDING);
            try
            {
                upload(mc, camX, camY, camZ);
            }
            finally
            {
                glBindVertexArray(vao);
                glBindBuffer(GL_ARRAY_BUFFER, arrayBuffer);
                BufferUploader.invalidate();
            }
            // drawn after the level in both modes (under a shader pack, after its last pass, which would otherwise light it
            // as a surface it knows nothing about or paint it over as sky), anti-aliased and laid where nothing was drawn
            pendingView = view;
            pendingProjection = projection;
            pendingCamera = new float[]{camX, camY, camZ};
            pendingFog = fog;
        }
        catch (IOException | RuntimeException problem)
        {
            failed = true;
            active = false;
            ProjectSeele.LOGGER.warn("GeoFront far view R65 off: {}", problem.toString(), problem);
        }
    }

    /**
     * Under a shader pack, right after the level (and the pack's composite and final passes) is drawn. The far view goes
     * into a target of its own, with its own depth, and is laid onto the picture only where the depth buffer the pack
     * shares with the main target still holds the cleared value: where no real block, entity or hand was drawn.
     */
    public static void afterLevel()
    {
        Matrix4f view = pendingView, projection = pendingProjection;
        float[] camera = pendingCamera, fog = pendingFog;
        pendingView = null;
        pendingProjection = null;
        pendingCamera = null;
        pendingFog = null;
        if (view == null || failed || cells.isEmpty()) return;
        Minecraft mc = Minecraft.getInstance();
        if (EvaCommandFeedClient.captureTargetOverride() != null) return;
        RenderTarget main = mc.getMainRenderTarget();
        if (target == null) target = new TextureTarget(main.width, main.height, true, Minecraft.ON_OSX);
        else if (target.width != main.width || target.height != main.height) target.resize(main.width, main.height, Minecraft.ON_OSX);
        drawWithState(mc, view, projection, camera, fog, main);
    }

    /** Reads the GL state touched, draws (into the main target, or through the far view's own target onto it), restores. */
    private static void drawWithState(Minecraft mc, Matrix4f view, Matrix4f projection, float[] camera, float[] fog, RenderTarget main)
    {
        boolean depthTest = glIsEnabled(GL_DEPTH_TEST), blend = glIsEnabled(GL_BLEND), cull = glIsEnabled(GL_CULL_FACE),
                scissor = glIsEnabled(GL_SCISSOR_TEST), depthMask = glGetBoolean(GL_DEPTH_WRITEMASK);
        int depthFunc = glGetInteger(GL_DEPTH_FUNC), program = glGetInteger(GL_CURRENT_PROGRAM), unit = glGetInteger(GL_ACTIVE_TEXTURE);
        int vao = glGetInteger(GL_VERTEX_ARRAY_BINDING), arrayBuffer = glGetInteger(GL_ARRAY_BUFFER_BINDING);
        ByteBuffer mask = BufferUtils.createByteBuffer(16);
        glGetBooleanv(GL_COLOR_WRITEMASK, mask);
        FloatBuffer clear = BufferUtils.createFloatBuffer(16);
        glGetFloatv(GL_COLOR_CLEAR_VALUE, clear);
        int blendSrc = glGetInteger(GL_BLEND_SRC_RGB), blendDst = glGetInteger(GL_BLEND_DST_RGB),
                blendSrcA = glGetInteger(GL_BLEND_SRC_ALPHA), blendDstA = glGetInteger(GL_BLEND_DST_ALPHA);
        glActiveTexture(GL_TEXTURE0);
        int texture = glGetInteger(GL_TEXTURE_BINDING_2D);
        try
        {
            if (farProgram == 0) programs();
            ensureMultisample(main.width, main.height);
            glColorMask(true, true, true, true);
            glDisable(GL_BLEND);
            glDisable(GL_CULL_FACE);
            glDisable(GL_SCISSOR_TEST);
            glEnable(GL_DEPTH_TEST);
            glDepthFunc(GL_LEQUAL);
            glDepthMask(true);
            // Four samples a pixel: a seam between the dome's panels one block wide is under a pixel from the floor, and
            // drawn with one sample it jumps from pixel to pixel as the camera moves; with four it is a steady soft line.
            glBindFramebuffer(GL_FRAMEBUFFER, multisampleFbo);
            glViewport(0, 0, main.width, main.height);
            glClearColor(0F, 0F, 0F, 0F);
            glClearDepth(1D);
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
            draw(mc, view, projection, camera, fog);
            glBindFramebuffer(GL_READ_FRAMEBUFFER, multisampleFbo);
            glBindFramebuffer(GL_DRAW_FRAMEBUFFER, target.frameBufferId);
            glBlitFramebuffer(0, 0, main.width, main.height, 0, 0, main.width, main.height, GL_COLOR_BUFFER_BIT, GL_NEAREST);
            main.bindWrite(true);
            glDepthMask(false);
            // the resolved colour is premultiplied (the cleared background is transparent black)
            glEnable(GL_BLEND);
            glBlendFuncSeparate(GL_ONE, GL_ONE_MINUS_SRC_ALPHA, GL_ZERO, GL_ONE);
            glUseProgram(blitProgram);
            glUniform1i(glGetUniformLocation(blitProgram, "Sampler0"), 0);
            glBindTexture(GL_TEXTURE_2D, target.getColorTextureId());
            glBindVertexArray(screenVao);
            glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
        }
        catch (IOException | RuntimeException problem)
        {
            failed = true;
            active = false;
            ProjectSeele.LOGGER.warn("GeoFront far view R65 off: {}", problem.toString(), problem);
            main.bindWrite(true);
        }
        finally
        {
            org.lwjgl.opengl.GL14.glBlendFuncSeparate(blendSrc, blendDst, blendSrcA, blendDstA);
            glBindVertexArray(vao);
            glBindBuffer(GL_ARRAY_BUFFER, arrayBuffer);
            BufferUploader.invalidate();
            glBindTexture(GL_TEXTURE_2D, texture);
            glActiveTexture(unit);
            glUseProgram(program);
            glClearColor(clear.get(0), clear.get(1), clear.get(2), clear.get(3));
            glColorMask(mask.get(0) != 0, mask.get(1) != 0, mask.get(2) != 0, mask.get(3) != 0);
            glDepthMask(depthMask);
            glDepthFunc(depthFunc);
            set(GL_DEPTH_TEST, depthTest);
            set(GL_BLEND, blend);
            set(GL_CULL_FACE, cull);
            set(GL_SCISSOR_TEST, scissor);
        }
    }

    private static int multisampleFbo, multisampleColour, multisampleDepth, multisampleWidth, multisampleHeight;

    private static void ensureMultisample(int width, int height)
    {
        if (multisampleFbo != 0 && width == multisampleWidth && height == multisampleHeight) return;
        if (multisampleFbo != 0)
        {
            glDeleteFramebuffers(multisampleFbo);
            glDeleteRenderbuffers(multisampleColour);
            glDeleteRenderbuffers(multisampleDepth);
        }
        int samples = Math.min(4, glGetInteger(GL_MAX_SAMPLES));
        int previous = glGetInteger(GL_RENDERBUFFER_BINDING);
        multisampleColour = glGenRenderbuffers();
        glBindRenderbuffer(GL_RENDERBUFFER, multisampleColour);
        glRenderbufferStorageMultisample(GL_RENDERBUFFER, samples, GL_RGBA8, width, height);
        multisampleDepth = glGenRenderbuffers();
        glBindRenderbuffer(GL_RENDERBUFFER, multisampleDepth);
        glRenderbufferStorageMultisample(GL_RENDERBUFFER, samples, GL_DEPTH_COMPONENT24, width, height);
        glBindRenderbuffer(GL_RENDERBUFFER, previous);
        multisampleFbo = glGenFramebuffers();
        glBindFramebuffer(GL_FRAMEBUFFER, multisampleFbo);
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, multisampleColour);
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, multisampleDepth);
        if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) throw new IllegalStateException("multisample target incomplete");
        multisampleWidth = width;
        multisampleHeight = height;
        ProjectSeele.LOGGER.info("GeoFront far view R65: {}x{} target with {} samples", width, height, samples);
    }

    private static void draw(Minecraft mc, Matrix4f view, Matrix4f projection, float[] camera, float[] fog)
    {
        float nearCut = mc.options.getEffectiveRenderDistance() * 16F - 8F;
        float light = (float) (double) SeeleConfig.GEOFRONT_FAR_LIGHT.get();
        glUseProgram(farProgram);
        glUniformMatrix4fv(glGetUniformLocation(farProgram, "ModelViewMat"), false, view.get(MATRIX));
        glUniformMatrix4fv(glGetUniformLocation(farProgram, "ProjMat"), false, projection.get(MATRIX));
        glUniform1f(glGetUniformLocation(farProgram, "Light"), light);
        boolean pack = com.projectseele.client.render.ShaderShadowPassR44.enabled();
        glUniform4f(glGetUniformLocation(farProgram, "Water"), SHADER_WATER[0], SHADER_WATER[1], SHADER_WATER[2], pack ? 1F : 0F);
        glUniform1f(glGetUniformLocation(farProgram, "FogStart"), nearCut);
        glUniform1f(glGetUniformLocation(farProgram, "FogEnd"), FOG_END);
        glUniform4f(glGetUniformLocation(farProgram, "FogColor"), fog[0], fog[1], fog[2], FOG_STRENGTH);
        glUniform3f(glGetUniformLocation(farProgram, "Camera"), camera[0], camera[1], camera[2]);
        glUniform1f(glGetUniformLocation(farProgram, "NearCut"), nearCut);
        glUniform1i(glGetUniformLocation(farProgram, "Sampler0"), 0);
        glUniform1i(glGetUniformLocation(farProgram, "Looks"), 1);
        int origin = glGetUniformLocation(farProgram, "CellOrigin");
        glBindTexture(GL_TEXTURE_2D, mc.getTextureManager().getTexture(TextureAtlas.LOCATION_BLOCKS).getId());
        glActiveTexture(GL_TEXTURE1);
        int buffer = glGetInteger(GL_TEXTURE_BINDING_BUFFER);
        glBindTexture(GL_TEXTURE_BUFFER, lookTexture);
        glActiveTexture(GL_TEXTURE0);
        FrustumIntersection frustum = new FrustumIntersection(new Matrix4f(projection).mul(view));
        int cellsDrawn = 0;
        long quadsDrawn = 0;
        for (Cell cell : cells)
        {
            float far = farthest(cell, camera[0], camera[1], camera[2]);
            if (far < nearCut) continue;
            if (!frustum.testAab(cell.x, cell.minY, cell.z, cell.x + CELL, cell.maxY, cell.z + CELL)) continue;
            int want = wanted(nearest(cell, camera[0], camera[1], camera[2]));
            int level = -1;
            for (int l = want; l < levelCount; l++) if (cell.built[l]) { level = l; break; }
            if (level < 0) for (int l = want - 1; l >= 0; l--) if (cell.built[l]) { level = l; break; }
            if (level < 0 || cell.count[level] == 0) continue;
            glUniform3f(origin, cell.x, 0F, cell.z);
            glBindVertexArray(cell.vao[level]);
            glDrawArraysInstanced(GL_TRIANGLE_STRIP, 0, 4, cell.count[level]);
            cellsDrawn++;
            quadsDrawn += cell.count[level];
        }
        glActiveTexture(GL_TEXTURE1);
        glBindTexture(GL_TEXTURE_BUFFER, buffer);
        glActiveTexture(GL_TEXTURE0);
        drawnCells = cellsDrawn;
        drawnQuads = quadsDrawn;
    }

    private static int wanted(float distance)
    {
        int level = distance < FINE ? 0 : distance < MEDIUM ? 1 : 2;
        return Math.min(level, levelCount - 1);
    }

    private static float nearest(Cell c, float x, float y, float z)
    {
        float dx = Math.max(Math.max(c.x - x, x - (c.x + CELL)), 0), dz = Math.max(Math.max(c.z - z, z - (c.z + CELL)), 0);
        float dy = Math.max(Math.max(c.minY - y, y - c.maxY), 0);
        return (float) Math.sqrt(dx * dx + dy * dy + dz * dz);
    }

    /** The farthest corner of a cell's box, in 3D: a cell is left out only when all of it lies within the real chunks' reach. */
    private static float farthest(Cell c, float x, float y, float z)
    {
        float dx = Math.max(Math.abs(c.x - x), Math.abs(c.x + CELL - x)), dz = Math.max(Math.abs(c.z - z), Math.abs(c.z + CELL - z));
        float dy = Math.max(Math.abs(c.minY - y), Math.abs(c.maxY - y));
        return (float) Math.sqrt(dx * dx + dy * dy + dz * dz);
    }

    /**
     * Builds the GPU buffers the camera needs, nearest first, a few a frame: every cell at its coarsest scale on the
     * first frame, then the finer scales as the camera comes near. A finer scale is freed once the camera is well past
     * the distance that wanted it.
     */
    private static void upload(Minecraft mc, float camX, float camY, float camZ)
    {
        long began = System.nanoTime();
        int coarsest = levelCount - 1;
        boolean first = false;
        for (Cell cell : cells)
            if (!cell.built[coarsest])
            {
                build(cell, coarsest);
                first = true;
            }
        if (first) ProjectSeele.LOGGER.info("GeoFront far view R65: coarsest scale of {} cells ready in {} ms", cells.size(),
                (System.nanoTime() - began) / 1_000_000);
        // cells wholly inside the vanilla render distance are never seen (the real chunks are there)
        float nearCut = mc.options.getEffectiveRenderDistance() * 16F - 8F;
        int done = 0;
        Cell best = null;
        while (done < UPLOADS_PER_FRAME && System.nanoTime() - began < UPLOAD_NANOS)
        {
            best = null;
            int bestLevel = -1;
            float bestDistance = Float.MAX_VALUE;
            for (Cell cell : cells)
            {
                float d = nearest(cell, camX, camY, camZ);
                int want = wanted(d);
                for (int l = 0; l < coarsest; l++)
                    if (cell.built[l] && l < want && d > (l == 0 ? FINE : MEDIUM) + KEEP) free(cell, l);
                if (!cell.built[want] && d < bestDistance && farthest(cell, camX, camY, camZ) >= nearCut)
                {
                    best = cell;
                    bestLevel = want;
                    bestDistance = d;
                }
            }
            if (best == null) break;
            build(best, bestLevel);
            done++;
        }
    }

    private static void free(Cell cell, int level)
    {
        glDeleteVertexArrays(cell.vao[level]);
        glDeleteBuffers(cell.vbo[level]);
        vramBytes -= (long) cell.count[level] * INSTANCE;
        cell.vao[level] = cell.vbo[level] = 0;
        cell.built[level] = false;
    }

    /** One cell at one scale: its quads as instances in a buffer. */
    private static void build(Cell cell, int level)
    {
        int scale = scales[level], quads = 0;
        for (Tile t : cell.tiles) quads += t.counts[level];
        cell.built[level] = true;
        cell.count[level] = quads;
        if (quads == 0) return;
        ByteBuffer out = MemoryUtil.memAlloc(quads * INSTANCE).order(ByteOrder.nativeOrder());
        try
        {
            for (Tile t : cell.tiles)
            {
                ByteBuffer in = ByteBuffer.wrap(t.quads[level]).order(ByteOrder.LITTLE_ENDIAN);
                int ox = t.x - cell.x, oz = t.z - cell.z;
                for (int i = 0; i < t.counts[level]; i++)
                {
                    int x = in.get() & 0xFF, y = in.getShort() & 0xFFFF, z = in.get() & 0xFF;
                    int du = in.getShort() & 0xFFFF, dv = in.getShort() & 0xFFFF, face = in.get() & 0xFF, pal = in.getShort() & 0xFFFF;
                    int bx = ox + x * scale, by = y * scale, bz = oz + z * scale;
                    // the face's own plane: a positive face lies on the far side of its cell
                    if (face == 1) bx += scale;
                    else if (face == 3) by += scale;
                    else if (face == 5) bz += scale;
                    out.putShort((short) bx).putShort((short) by).putShort((short) bz);
                    out.putShort((short) (du * scale)).putShort((short) (dv * scale));
                    out.put((byte) face).put((byte) 0).putShort((short) (pal * 6 + face)).putShort((short) 0);
                }
            }
            out.flip();
            int vao = glGenVertexArrays(), vbo = glGenBuffers();
            glBindVertexArray(vao);
            glBindBuffer(GL_ARRAY_BUFFER, vbo);
            glBufferData(GL_ARRAY_BUFFER, out, GL_STATIC_DRAW);
            glEnableVertexAttribArray(0);
            glVertexAttribPointer(0, 3, GL_UNSIGNED_SHORT, false, INSTANCE, 0L);
            glVertexAttribDivisor(0, 1);
            glEnableVertexAttribArray(1);
            glVertexAttribPointer(1, 2, GL_UNSIGNED_SHORT, false, INSTANCE, 6L);
            glVertexAttribDivisor(1, 1);
            glEnableVertexAttribArray(2);
            glVertexAttribIPointer(2, 1, GL_UNSIGNED_BYTE, INSTANCE, 10L);
            glVertexAttribDivisor(2, 1);
            glEnableVertexAttribArray(3);
            glVertexAttribIPointer(3, 1, GL_UNSIGNED_SHORT, INSTANCE, 12L);
            glVertexAttribDivisor(3, 1);
            glBindVertexArray(0);
            cell.vao[level] = vao;
            cell.vbo[level] = vbo;
            vramBytes += (long) quads * INSTANCE;
        }
        finally
        {
            MemoryUtil.memFree(out);
        }
    }

    // ------------------------------------------------------------------ programs

    private static void programs() throws IOException
    {
        farProgram = link("geofront_dome_far", "Base", "Extent", "Face", "Look");
        blitProgram = link("geofront_dome_blit", "Position");
        FloatBuffer table = MemoryUtil.memAllocFloat(looks.length);
        try
        {
            table.put(looks).flip();
            lookBuffer = glGenBuffers();
            glBindBuffer(GL_TEXTURE_BUFFER, lookBuffer);
            glBufferData(GL_TEXTURE_BUFFER, table, GL_STATIC_DRAW);
            glBindBuffer(GL_TEXTURE_BUFFER, 0);
            lookTexture = glGenTextures();
            glActiveTexture(GL_TEXTURE1);
            int previous = glGetInteger(GL_TEXTURE_BINDING_BUFFER);
            glBindTexture(GL_TEXTURE_BUFFER, lookTexture);
            glTexBuffer(GL_TEXTURE_BUFFER, GL_RGBA32F, lookBuffer);
            glBindTexture(GL_TEXTURE_BUFFER, previous);
            glActiveTexture(GL_TEXTURE0);
        }
        finally
        {
            MemoryUtil.memFree(table);
        }
        FloatBuffer corners = MemoryUtil.memAllocFloat(8);
        try
        {
            corners.put(new float[]{-1, -1, 1, -1, -1, 1, 1, 1}).flip();
            screenVao = glGenVertexArrays();
            screenVbo = glGenBuffers();
            glBindVertexArray(screenVao);
            glBindBuffer(GL_ARRAY_BUFFER, screenVbo);
            glBufferData(GL_ARRAY_BUFFER, corners, GL_STATIC_DRAW);
            glEnableVertexAttribArray(0);
            glVertexAttribPointer(0, 2, GL_FLOAT, false, 8, 0L);
            glBindVertexArray(0);
        }
        finally
        {
            MemoryUtil.memFree(corners);
        }
    }

    private static void set(int capability, boolean on)
    {
        if (on) glEnable(capability);
        else glDisable(capability);
    }

    /** A program from shaders/core/<name>.vsh and .fsh with the given attributes at locations 0, 1, ... */
    private static int link(String name, String... attributes) throws IOException
    {
        int vertex = compile(GL_VERTEX_SHADER, name + ".vsh"), fragment = compile(GL_FRAGMENT_SHADER, name + ".fsh");
        int linked = glCreateProgram();
        glAttachShader(linked, vertex);
        glAttachShader(linked, fragment);
        for (int i = 0; i < attributes.length; i++) glBindAttribLocation(linked, i, attributes[i]);
        glLinkProgram(linked);
        glDeleteShader(vertex);
        glDeleteShader(fragment);
        if (glGetProgrami(linked, GL_LINK_STATUS) == 0) throw new IOException(name + ": " + glGetProgramInfoLog(linked));
        return linked;
    }

    private static int compile(int kind, String file) throws IOException
    {
        String path = "/assets/projectseele/shaders/core/" + file;
        try (InputStream stream = GeoFrontDomeFarViewR65.class.getResourceAsStream(path))
        {
            if (stream == null) throw new IOException("missing " + path);
            int id = glCreateShader(kind);
            glShaderSource(id, new String(stream.readAllBytes(), StandardCharsets.UTF_8));
            glCompileShader(id);
            if (glGetShaderi(id, GL_COMPILE_STATUS) == 0)
            {
                String message = glGetShaderInfoLog(id);
                glDeleteShader(id);
                throw new IOException(file + ": " + message);
            }
            return id;
        }
    }

    // ------------------------------------------------------------------ loading

    private static void load(Minecraft mc, int[] tints) throws IOException
    {
        var resource = mc.getResourceManager().getResource(MESH);
        if (resource.isEmpty())
        {
            missing = true;
            ProjectSeele.LOGGER.info("GeoFront far view R65: no baked mesh in this jar ({}), Distant Horizons stays", MESH);
            return;
        }
        long began = System.nanoTime();
        try (InputStream raw = resource.get().open();
             DataInputStream in = new DataInputStream(new BufferedInputStream(new GZIPInputStream(raw, 1 << 16), 1 << 16)))
        {
            byte[] magic = new byte[4];
            in.readFully(magic);
            if (!"SGDM".equals(new String(magic, StandardCharsets.US_ASCII))) throw new IOException("not a GeoFront far-view mesh");
            int version = in.readUnsignedByte(), tile = in.readUnsignedByte();
            if (version != 2 || tile != 64) throw new IOException("unknown mesh version " + version);
            ByteBuffer head = little(in, 12 + 6 + 1);
            originX = head.getInt();
            originY = head.getInt();
            originZ = head.getInt();
            head.getShort();
            head.getShort();
            head.getShort();
            levelCount = head.get() & 0xFF;
            if (levelCount < 1 || levelCount > 3) throw new IOException("unknown level count " + levelCount);
            scales = new int[levelCount];
            for (int l = 0; l < levelCount; l++) scales[l] = in.readUnsignedByte();
            int names = little(in, 4).getInt();
            if (names < 0 || names > 65535) throw new IOException("bad palette " + names);
            List<String> palette = new ArrayList<>(names);
            for (int i = 0; i < names; i++)
            {
                byte[] text = new byte[little(in, 2).getShort() & 0xFFFF];
                in.readFully(text);
                palette.add(new String(text, StandardCharsets.UTF_8));
            }
            resolve(mc, palette, tints);
            int tileCount = little(in, 4).getInt();
            Map<Long, Cell> byKey = new HashMap<>();
            totalQuads = 0;
            for (int i = 0; i < tileCount; i++)
            {
                ByteBuffer id = little(in, 4);
                int tx = id.getShort() & 0xFFFF, tz = id.getShort() & 0xFFFF;
                byte[][] quads = new byte[levelCount][];
                int[] counts = new int[levelCount];
                for (int l = 0; l < levelCount; l++)
                {
                    counts[l] = little(in, 4).getInt();
                    if (counts[l] < 0 || counts[l] > 4_000_000) throw new IOException("bad tile " + counts[l]);
                    quads[l] = new byte[counts[l] * 11];
                    in.readFully(quads[l]);
                    totalQuads += counts[l];
                }
                // the tile's quads by height band: a cell is 128 x 128 and 128 high, so the scale follows the true distance
                // (the floor near, the dome far above)
                int bands = (600 + BAND - 1) / BAND + 1;
                java.io.ByteArrayOutputStream[][] split = new java.io.ByteArrayOutputStream[bands][levelCount];
                int[][] splitCounts = new int[bands][levelCount];
                float[] top = new float[bands];
                for (int l = 0; l < levelCount; l++)
                {
                    int s = scales[l];
                    for (int k = 0; k < counts[l]; k++)
                    {
                        int o = k * 11;
                        int y = ((quads[l][o + 1] & 0xFF) | (quads[l][o + 2] & 0xFF) << 8) * s;
                        int face = quads[l][o + 8] & 0xFF, axis = face / 2;
                        int du = ((quads[l][o + 4] & 0xFF) | (quads[l][o + 5] & 0xFF) << 8) * s;
                        int dv = ((quads[l][o + 6] & 0xFF) | (quads[l][o + 7] & 0xFF) << 8) * s;
                        int band = Math.min(bands - 1, y / BAND);
                        if (split[band][l] == null) split[band][l] = new java.io.ByteArrayOutputStream();
                        split[band][l].write(quads[l], o, 11);
                        splitCounts[band][l]++;
                        top[band] = Math.max(top[band], y + (axis == 0 ? du : axis == 2 ? dv : s));
                    }
                }
                int cx = (tx * 64) / CELL, cz = (tz * 64) / CELL;
                for (int b = 0; b < bands; b++)
                {
                    int any = 0;
                    byte[][] q = new byte[levelCount][];
                    for (int l = 0; l < levelCount; l++)
                    {
                        q[l] = split[b][l] == null ? new byte[0] : split[b][l].toByteArray();
                        any += splitCounts[b][l];
                    }
                    if (any == 0) continue;
                    int band = b;
                    long key = (((long) cx & 0xFFFFF) << 40) | (((long) cz & 0xFFFFF) << 20) | band;
                    Cell cell = byKey.computeIfAbsent(key, k -> new Cell(cx * CELL, cz * CELL));
                    cell.tiles.add(new Tile(tx * 64, tz * 64, q, splitCounts[b]));
                    cell.minY = Math.min(cell.minY, band * BAND);
                    cell.maxY = Math.max(cell.maxY, top[b]);
                }
            }
            cells.clear();
            for (Cell c : byKey.values())
            {
                if (c.minY > c.maxY) { c.minY = 0; c.maxY = 600; }
                cells.add(c);
            }
        }
        catch (EOFException truncated)
        {
            throw new IOException("truncated GeoFront far-view mesh", truncated);
        }
        ProjectSeele.LOGGER.info("GeoFront far view R65: {} cells, {} quads over {} scales, read in {} ms", cells.size(), totalQuads,
                levelCount, (System.nanoTime() - began) / 1_000_000);
    }

    private static ByteBuffer little(DataInputStream in, int length) throws IOException
    {
        byte[] bytes = new byte[length];
        in.readFully(bytes);
        return ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
    }

    private static final Direction[] FACES = {Direction.WEST, Direction.EAST, Direction.DOWN, Direction.UP, Direction.NORTH, Direction.SOUTH};

    /**
     * Per block state and face: the sprite that side shows in the block atlas, its tint, and whether it is drawn with
     * its texture (mostly see-through sprites such as glass are drawn as their average colour instead: the far view
     * has nothing behind a window).
     */
    private static void resolve(Minecraft mc, List<String> palette, int[] tints)
    {
        int n = palette.size();
        looks = new float[n * 6 * 8];
        int foliage = tints[0], grass = tints[1], water = tints[2];
        TextureAtlas atlas = (TextureAtlas) mc.getTextureManager().getTexture(TextureAtlas.LOCATION_BLOCKS);
        Map<ResourceLocation, int[]> sprites = new HashMap<>();
        RandomSource random = RandomSource.create(42L);
        for (int i = 0; i < n; i++)
        {
            BlockState state = parse(palette.get(i));
            Block block = state.getBlock();
            var model = mc.getBlockRenderer().getBlockModel(state);
            for (int f = 0; f < 6; f++)
            {
                TextureAtlasSprite sprite;
                boolean tinted;
                if (block == Blocks.WATER || block == Blocks.LAVA)
                {
                    sprite = atlas.getSprite(new ResourceLocation("minecraft", block == Blocks.WATER ? "block/water_still" : "block/lava_still"));
                    tinted = block == Blocks.WATER;
                }
                else
                {
                    List<BakedQuad> quads = model.getQuads(state, FACES[f], random, ModelData.EMPTY, null);
                    BakedQuad quad = quads.isEmpty() ? null : quads.get(0);
                    if (quad == null)
                        for (BakedQuad q : model.getQuads(state, null, random, ModelData.EMPTY, null))
                            if (quad == null || q.getDirection() == FACES[f]) quad = q;
                    sprite = quad != null ? quad.getSprite() : model.getParticleIcon(ModelData.EMPTY);
                    tinted = quad != null && quad.isTinted();
                }
                int[] look = sprites.computeIfAbsent(sprite.contents().name(), name -> look(mc, name));
                int tint = !tinted ? 0xFFFFFF : block == Blocks.WATER ? water
                        : block instanceof LeavesBlock || block == Blocks.VINE ? leafTint(block, foliage) : grass;
                int base = (i * 6 + f) * 8;
                // water is drawn flat (its own colour without a pack, the pack's lake colour under one: Water)
                boolean isWater = block == Blocks.WATER;
                boolean textured = !isWater && look[0] >= 0 && look[1] == 0;
                int rgb = textured ? tint : multiply(look[0] >= 0 ? look[0] : mapColour(block), tint);
                looks[base] = sprite.getU0();
                looks[base + 1] = sprite.getV0();
                looks[base + 2] = sprite.getU1();
                looks[base + 3] = sprite.getV1();
                looks[base + 4] = ((rgb >> 16) & 0xFF) / 255F;
                looks[base + 5] = ((rgb >> 8) & 0xFF) / 255F;
                looks[base + 6] = (rgb & 0xFF) / 255F;
                looks[base + 7] = isWater ? .5F : textured ? 1F : 0F;
            }
        }
    }

    private static BlockState parse(String key)
    {
        try
        {
            return BlockStateParser.parseForBlock(BuiltInRegistries.BLOCK.asLookup(), key, false).blockState();
        }
        catch (Exception unknown)
        {
            int bracket = key.indexOf('[');
            ResourceLocation id = ResourceLocation.tryParse(bracket < 0 ? key : key.substring(0, bracket));
            return (id == null ? Blocks.STONE : BuiltInRegistries.BLOCK.get(id)).defaultBlockState();
        }
    }

    private static int leafTint(Block block, int foliage)
    {
        if (block == Blocks.SPRUCE_LEAVES) return FoliageColor.getEvergreenColor();
        if (block == Blocks.BIRCH_LEAVES) return FoliageColor.getBirchColor();
        return foliage;
    }

    private static int mapColour(Block block)
    {
        MapColor c = block.defaultMapColor();
        return c == null || c == MapColor.NONE || c.col == 0 ? 0x8C9CA4 : c.col;
    }

    /** {average colour of the opaque pixels (or -1), 1 when most of the sprite is see-through} for a sprite's texture. */
    private static int[] look(Minecraft mc, ResourceLocation sprite)
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
            if (n == 0) return new int[]{-1, 1};
            int avg = (int) (r / n) << 16 | (int) (g / n) << 8 | (int) (b / n);
            return new int[]{avg, n * 2 < (long) w * h ? 1 : 0};
        }
        catch (IOException | RuntimeException unreadable)
        {
            return new int[]{-1, 0};
        }
    }

    private static int multiply(int rgb, int tint)
    {
        return (((rgb >> 16) & 0xFF) * ((tint >> 16) & 0xFF) / 255) << 16 | (((rgb >> 8) & 0xFF) * ((tint >> 8) & 0xFF) / 255) << 8
                | ((rgb & 0xFF) * (tint & 0xFF) / 255);
    }
}

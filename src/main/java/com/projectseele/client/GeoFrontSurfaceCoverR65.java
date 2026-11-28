package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.client.map.AreaMapAtlas;
import com.projectseele.client.map.AreaMapLayer;
import java.io.BufferedInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.lang.ref.WeakReference;
import java.nio.ByteBuffer;
import java.nio.FloatBuffer;
import java.util.concurrent.CompletableFuture;
import java.util.zip.GZIPInputStream;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.BiomeColors;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LeavesBlock;
import net.minecraft.world.level.material.MapColor;
import org.joml.FrustumIntersection;
import org.joml.Matrix4f;
import org.lwjgl.BufferUtils;
import org.lwjgl.system.MemoryUtil;

import static org.lwjgl.opengl.GL33C.*;

/** Coarse, measured surface behind holes in the native and DH meshes while either renderer is streaming. */
final class GeoFrontSurfaceCoverR65
{
    private static final ResourceLocation RESOURCE = new ResourceLocation(ProjectSeele.MODID, "geofront/surface_cover_r65.bin.gz");
    private static final int TILE = 64, INDEX_COUNT = TILE * TILE * 6;
    private static final int RANGE = 3072;
    private static final FloatBuffer MATRIX = BufferUtils.createFloatBuffer(16);
    private static CompletableFuture<Survey> loading;
    private static Survey survey;
    private static AreaMapLayer groundAtlas;
    private static boolean disabled;
    private static int program, vao, texture;
    private static long motionSampleAt = -1, handoffUntil;
    private static float sampleX, sampleY, sampleZ;
    private static WeakReference<ClientLevel> sampleLevel = new WeakReference<>(null);

    private record Survey(int x, int z, int width, int height, int step, int floor, ByteBuffer data) {}

    static boolean ready(Minecraft mc, BlockPos eye)
    {
        if (disabled) return false;
        if (survey == null)
        {
            if (loading == null)
            {
                var file = mc.getResourceManager().getResource(RESOURCE);
                if (file.isEmpty()) { disabled = true; return false; }
                int foliage = BiomeColors.getAverageFoliageColor(mc.level, eye), grass = BiomeColors.getAverageGrassColor(mc.level, eye);
                int water = BiomeColors.getAverageWaterColor(mc.level, eye);
                AreaMapLayer atlas = AreaMapAtlas.surface();
                var hangars = AreaMapAtlas.byId("un_hangars");
                groundAtlas = atlas;
                loading = CompletableFuture.supplyAsync(() -> {
                    try (var input = new DataInputStream(new BufferedInputStream(new GZIPInputStream(file.get().open()))))
                    {
                        return read(input, foliage, grass, water, atlas, hangars == null ? null : hangars.bounds());
                    }
                    catch (IOException e) { throw new java.io.UncheckedIOException(e); }
                }, net.minecraft.Util.backgroundExecutor());
            }
            if (!loading.isDone()) return false;
            try { survey = loading.join(); }
            catch (RuntimeException e) { disable(e); return false; }
            loading = null;
        }
        return eye.getX() >= survey.x - RANGE && eye.getX() < survey.x + survey.width * survey.step + RANGE
                && eye.getZ() >= survey.z - RANGE && eye.getZ() < survey.z + survey.height * survey.step + RANGE;
    }

    private static Survey read(DataInputStream in, int foliage, int grass, int water,
                               AreaMapLayer atlas, AreaMapLayer.Bounds hangars) throws IOException
    {
        if (in.readInt() != 0x53465331) throw new IOException("Unknown surface survey");
        int x = in.readInt(), z = in.readInt(), w = in.readInt(), h = in.readInt(), step = in.readInt(), floor = in.readInt();
        if (w <= 0 || h <= 0 || w > 8192 || h > 8192 || (long)w * h > 16_777_216 || step != 8)
            throw new IOException("Surface survey dimensions out of range");
        int[] colours = new int[in.readUnsignedShort() + 1];
        for (int i = 1; i < colours.length; i++)
        {
            var block = BuiltInRegistries.BLOCK.get(new ResourceLocation(in.readUTF()));
            MapColor tint = block.defaultMapColor();
            int colour = tint == null || tint == MapColor.NONE ? 0x868781 : tint.col;
            if (block instanceof LeavesBlock) colour = darken(GeoFrontDomeFarViewR65.leafTint(block, foliage), .60F);
            else if (block == Blocks.GRASS_BLOCK || block == Blocks.GRASS || block == Blocks.TALL_GRASS) colour = darken(grass, .76F);
            else if (block == Blocks.WATER) colour = darken(water, .72F);
            colours[i] = (colour >> 8 & 0xf800) | (colour >> 5 & 0x07e0) | (colour >> 3 & 31);
            var state = block.defaultBlockState();
            if (block instanceof LeavesBlock) colours[i] |= 0x10000;
            // An 8-block sample describes a column's uppermost block. A pole, roof or
            // gantry is real at that point, but cannot support terrain between columns.
            if (block instanceof LeavesBlock || state.is(BlockTags.DIRT) || state.is(BlockTags.SAND)
                    || state.is(BlockTags.BASE_STONE_OVERWORLD) || block == Blocks.GRAVEL || block == Blocks.WATER
                    || block == Blocks.SNOW || block == Blocks.SNOW_BLOCK || block == Blocks.GRASS
                    || block == Blocks.TALL_GRASS || block == Blocks.FERN || block == Blocks.LARGE_FERN)
                colours[i] |= 0x20000;
        }
        ByteBuffer data = MemoryUtil.memAlloc(w * h * 4);
        try
        {
            byte[] row = new byte[w * 4];
            for (int j = 0; j < h; j++)
            {
                in.readFully(row);
                for (int offset = 0; offset < row.length; offset += 4)
                {
                    int id = (row[offset + 2] & 255) * 256 + (row[offset + 3] & 255);
                    if (id >= colours.length) throw new IOException("Invalid surface material");
                    // The two upper bits mark canopy and terrain support in this GPU copy.
                    if ((colours[id] & 0x10000) != 0) row[offset] |= (byte)0x80;
                    if ((colours[id] & 0x20000) != 0) row[offset] |= 0x40;
                    row[offset + 2] = (byte)(colours[id] >> 8);
                    row[offset + 3] = (byte)colours[id];
                }
                // The area-map baker stores a median-filtered neighbourhood minimum 56
                // blocks below street level, independently of wires, roofs and canopies.
                // Use that measured lower surface whenever available, including in settled
                // gaps between native chunks and distant meshes. The colour comes from
                // the same state's georeferenced survey, preserving roads and shorelines.
                if (atlas != null && atlas.bottom() != null)
                {
                    var bounds = atlas.bounds();
                    var heights = atlas.bottom();
                    int worldZ = z + j * step + step / 2;
                    if (worldZ >= bounds.minZ() && worldZ < bounds.maxZ()) {
                        int mz = (worldZ - bounds.minZ()) * heights.height() / bounds.depth();
                        for (int column = 0; column < w; column++) {
                            int worldX = x + column * step + step / 2;
                            if (worldX < bounds.minX() || worldX >= bounds.maxX()) continue;
                            int mx = (worldX - bounds.minX()) * heights.width() / bounds.width();
                            int bottom = heights.values()[mz * heights.width() + mx];
                            int offset = column * 4;
                            if (bottom == Short.MIN_VALUE) continue;
                            // A wide warehouse can survive the atlas median filter. For
                            // a surveyed structure, use a neighbouring street elevation
                            // that can reach this position within a 1:1 grade. A deep
                            // shaft or sheer cliff does not satisfy this condition.
                            if ((row[offset] & 0x40) == 0 && (row[offset] != 0 || row[offset + 1] != 0))
                                bottom = buildingGrade(heights, bounds, mx, mz, bottom, step);
                            int surveyed = (row[offset] & 31) * 256 + (row[offset + 1] & 255);
                            if ((row[offset] & 0x40) != 0 && surveyed != 0 && surveyed + floor - (bottom + 56) > step * 8)
                                bottom = recoverRim(heights, bounds, mx, mz, bottom, surveyed + floor - 56, step);
                            // The apron continues beneath both moving hangar gates. A roof sample cannot
                            // interpolate through that opening, even if the adjacent sample is also a roof.
                            if (hangars != null && worldX >= hangars.minX() - step && worldX < hangars.maxX() + step
                                    && worldZ >= hangars.minZ() - step && worldZ < hangars.maxZ() + step)
                                bottom = Math.min(bottom, hangars.minY() - 56);
                            int top = bottom + 56 - floor;
                            if (top < 1 || top >= 8192) continue;
                            row[offset] = (byte)(0x60 | top >> 8);
                            row[offset + 1] = (byte)top;
                        }
                    }
                }
                data.put(row);
            }
            if (in.read() != -1) throw new IOException("Trailing survey data");
            return new Survey(x, z, w, h, step, floor, data.flip());
        }
        catch (IOException | RuntimeException error) { MemoryUtil.memFree(data); throw error; }
    }

    private static int buildingGrade(AreaMapLayer.Heights heights, AreaMapLayer.Bounds bounds,
                                     int x, int z, int centre, int step)
    {
        int grade = centre;
        for (int radius = step * 2; radius <= step * 8; radius *= 2) {
            int dx = Math.max(1, radius * heights.width() / bounds.width());
            int dz = Math.max(1, radius * heights.height() / bounds.depth());
            for (int oz = -1; oz <= 1; oz++) for (int ox = -1; ox <= 1; ox++) {
                int cx = x + ox * dx, cz = z + oz * dz;
                if (cx < 0 || cx >= heights.width() || cz < 0 || cz >= heights.height()) continue;
                int nearby = heights.values()[cz * heights.width() + cx];
                if (nearby >= centre - radius && nearby < grade) grade = nearby;
            }
        }
        return grade;
    }

    // The minimum filter used to split the map layers expands deep shafts onto their rims.
    // Recover a rim only when a nearby measured grade also agrees with this surveyed column.
    private static int recoverRim(AreaMapLayer.Heights heights, AreaMapLayer.Bounds bounds,
                                  int x, int z, int bottom, int surveyed, int step)
    {
        int rim = bottom;
        for (int radius = step; radius <= step * 4; radius *= 2) {
            int dx = Math.max(1, radius * heights.width() / bounds.width());
            int dz = Math.max(1, radius * heights.height() / bounds.depth());
            for (int oz = -1; oz <= 1; oz++) for (int ox = -1; ox <= 1; ox++) {
                int cx = x + ox * dx, cz = z + oz * dz;
                if (cx < 0 || cx >= heights.width() || cz < 0 || cz >= heights.height()) continue;
                int nearby = heights.values()[cz * heights.width() + cx];
                if (nearby >= surveyed - step * 2 && nearby <= surveyed && nearby - bottom > step * 8)
                    rim = Math.max(rim, nearby);
            }
        }
        return rim;
    }

    static void disable(Throwable e)
    {
        disabled = true;
        ProjectSeele.LOGGER.warn("GeoFront surface survey unavailable", e);
    }

    private static int darken(int rgb, float factor)
    {
        return (int)(((rgb >> 16) & 255) * factor) << 16 | (int)(((rgb >> 8) & 255) * factor) << 8 | (int)((rgb & 255) * factor);
    }

    static void leftSurface()
    {
        motionSampleAt = -1;
    }

    private static float handoffRange(float[] camera)
    {
        Minecraft mc = Minecraft.getInstance();
        if (sampleLevel.get() != mc.level)
        {
            sampleLevel = new WeakReference<>(mc.level);
            leftSurface();
        }
        long now = net.minecraft.Util.getMillis();
        float dx = camera[0] - sampleX, dy = camera[1] - sampleY, dz = camera[2] - sampleZ;
        double travel = Math.sqrt(dx * dx + dy * dy + dz * dz);
        long elapsed = now - motionSampleAt;
        if (motionSampleAt < 0 || elapsed >= 100 || travel > 16)
        {
            // A fast flight or dimension arrival can leave the receiving native sections
            // unmeshed. Ordinary walking, turning, and a settled distant skyline keep DH.
            if (motionSampleAt < 0 || travel > Math.max(4.0, Math.min(16.0, elapsed * .020)))
                handoffUntil = now + 1600;
            motionSampleAt = now;
            sampleX = camera[0];
            sampleY = camera[1];
            sampleZ = camera[2];
        }
        return now < handoffUntil ? mc.options.getEffectiveRenderDistance() * 16F : 0F;
    }

    static void draw(Matrix4f view, Matrix4f projection, Matrix4f sceneProjection, float[] camera, float[] fog,
                     int sceneDepth, RamielTerrainDepthR64.DepthSample dh) throws IOException
    {
        glActiveTexture(GL_TEXTURE3);
        int previousMap = glGetInteger(GL_TEXTURE_BINDING_2D), previousMapSampler = glGetInteger(GL_SAMPLER_BINDING);
        glActiveTexture(GL_TEXTURE2);
        int previous = glGetInteger(GL_TEXTURE_BINDING_2D), sampler = glGetInteger(GL_SAMPLER_BINDING);
        try
        {
            glActiveTexture(GL_TEXTURE3);
            if (groundAtlas != null) {
                int map = Minecraft.getInstance().getTextureManager().getTexture(groundAtlas.texture()).getId();
                glActiveTexture(GL_TEXTURE3);
                glBindTexture(GL_TEXTURE_2D, map);
                glBindSampler(3, 0);
            }
            glActiveTexture(GL_TEXTURE2);
            if (program == 0) upload();
            glUseProgram(program);
            glBindVertexArray(vao);
            glBindTexture(GL_TEXTURE_2D, texture);
            glBindSampler(2, 0);
            glActiveTexture(GL_TEXTURE1);
            glBindSampler(1, 0);
            glBindTexture(GL_TEXTURE_2D, dh == null ? 0 : dh.texture());
            glActiveTexture(GL_TEXTURE0);
            glBindSampler(0, 0);
            glBindTexture(GL_TEXTURE_2D, sceneDepth);
            glUniform1i(glGetUniformLocation(program, "HasDh"), dh != null ? 1 : 0);
            glUniform2f(glGetUniformLocation(program, "DhToScene"), dh == null ? 1 : dh.scale(), dh == null ? 0 : dh.offset());
            glUniform2f(glGetUniformLocation(program, "SceneZ"), sceneProjection.m22(), sceneProjection.m32());
            glUniform1f(glGetUniformLocation(program, "HandoffRange"), handoffRange(camera));
            glUniform1f(glGetUniformLocation(program, "NativeRange"), Minecraft.getInstance().options.getEffectiveRenderDistance() * 16F);
            Matrix4f clip = new Matrix4f(projection).mul(view);
            glUniformMatrix4fv(glGetUniformLocation(program, "Clip"), false, clip.get(MATRIX));
            glUniform3f(glGetUniformLocation(program, "Eye"), camera[0], camera[1], camera[2]);
            glUniform3f(glGetUniformLocation(program, "Haze"), fog[0], fog[1], fog[2]);
            int tile = glGetUniformLocation(program, "Tile");
            int side = TILE * survey.step;
            var frustum = new FrustumIntersection(clip);
            for (int iz = Math.max(0, Math.floorDiv((int)camera[2] - RANGE - survey.z, side)) * TILE;
                    iz < survey.height && survey.z + iz * survey.step <= camera[2] + RANGE; iz += TILE)
                for (int ix = Math.max(0, Math.floorDiv((int)camera[0] - RANGE - survey.x, side)) * TILE;
                        ix < survey.width && survey.x + ix * survey.step <= camera[0] + RANGE; ix += TILE)
                {
                    int x = survey.x + ix * survey.step, z = survey.z + iz * survey.step;
                    if (!frustum.testAab(x, survey.floor, z, x + side + survey.step, 321, z + side + survey.step)) continue;
                    glUniform2i(tile, ix, iz);
                    glDrawElements(GL_TRIANGLES, INDEX_COUNT, GL_UNSIGNED_SHORT, 0L);
                }
        }
        finally
        {
            glActiveTexture(GL_TEXTURE3);
            glBindTexture(GL_TEXTURE_2D, previousMap);
            glBindSampler(3, previousMapSampler);
            glActiveTexture(GL_TEXTURE2);
            glBindTexture(GL_TEXTURE_2D, previous);
            glBindSampler(2, sampler);
            glActiveTexture(GL_TEXTURE0);
        }
    }

    private static void upload() throws IOException
    {
        program = GeoFrontDomeFarViewR65.link("geofront_surface_cover");
        glUseProgram(program);
        texture = glGenTextures();
        glBindTexture(GL_TEXTURE_2D, texture);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8UI, survey.width, survey.height, 0, GL_RGBA_INTEGER, GL_UNSIGNED_BYTE, survey.data);
        MemoryUtil.memFree(survey.data);
        survey = new Survey(survey.x, survey.z, survey.width, survey.height, survey.step, survey.floor, null);
        vao = glGenVertexArrays();
        glBindVertexArray(vao);
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, glGenBuffers());
        var indices = MemoryUtil.memAllocShort(INDEX_COUNT);
        try
        {
            for (int z = 0; z < TILE; z++) for (int x = 0; x < TILE; x++)
            {
                int a = z * (TILE + 1) + x, b = a + TILE + 1;
                indices.put((short)a).put((short)b).put((short)(a + 1));
                indices.put((short)(a + 1)).put((short)b).put((short)(b + 1));
            }
            glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.flip(), GL_STATIC_DRAW);
        }
        finally { MemoryUtil.memFree(indices); }
        glUniform1i(glGetUniformLocation(program, "NativeDepth"), 0);
        glUniform1i(glGetUniformLocation(program, "DhDepth"), 1);
        glUniform1i(glGetUniformLocation(program, "Survey"), 2);
        glUniform1i(glGetUniformLocation(program, "GroundMap"), 3);
        if (groundAtlas != null) {
            var b = groundAtlas.bounds();
            glUniform4f(glGetUniformLocation(program, "MapBounds"), b.minX(), b.minZ(), b.width(), b.depth());
        }
        glUniform4i(glGetUniformLocation(program, "Grid"), survey.x, survey.z, survey.step, survey.floor);
        ProjectSeele.LOGGER.info("GeoFront surface cover R65 ready: {} x {}, {} blocks per sample", survey.width, survey.height, survey.step);
    }

    private GeoFrontSurfaceCoverR65() {}
}

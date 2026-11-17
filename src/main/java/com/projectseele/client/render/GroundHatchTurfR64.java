package com.projectseele.client.render;

import com.mojang.blaze3d.platform.NativeImage;
import com.mojang.blaze3d.platform.TextureUtil;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervSiloDoorEntity;
import com.projectseele.entity.SiloHatchMechanism;
import com.projectseele.registry.ModBlocks;
import com.projectseele.world.NervSiloHatchGeometryR52;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.BiomeColors;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.OutlineBufferSource;
import net.minecraft.client.renderer.texture.AbstractTexture;
import net.minecraft.client.renderer.texture.MipmapGenerator;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * The ground a flush hatch carries on its leaves while it moves. Closed, the hatch is covered by blocks
 * ({@link com.projectseele.world.GroundHatchBlockR64}) and nothing is drawn here. Once those are gone each leaf
 * shows the same grass in the same place, with the resource pack's own texture and the biome's tint, and keeps
 * its piece of ground while it sinks and slides away.
 */
public final class GroundHatchTurfR64
{
    private static final ResourceLocation SOURCE = new ResourceLocation("minecraft", "textures/block/grass_block_top.png");
    private static final ResourceLocation TILED = new ResourceLocation("projectseele", "dynamic/ground_hatch_turf_r64");
    /** Blocks along one side of the tiled sheet. Each has one of the four turns the terrain gives its grass. */
    private static final int BLOCKS = 16;
    /** Longest side of one drawn piece: the tint is looked up at its corners. */
    private static final double CELL = 16;
    /** The tint follows chunks that arrive later and a changed blend setting. */
    private static final int TINT_TICKS = 200;
    private static final int STRIDE = 7;

    /** Where a hatch shows a top, in its own frame with the leaves closed. */
    private record Leaf(double[] box, int side, int index) {}
    private record Layout(List<Leaf> leaves, double leafTop, float[] bounds) {}
    private static final class Cover
    {
        Level level;SiloHatchMechanism.Spec spec;Vec3 at;float yaw;long built;
        Layout layout;float[][] leaves;
        /** The top of the hatch's layer of cells, in its own frame: where the cover blocks' tops are. */
        double ground;BlockPos cell;
    }

    private static final Map<SiloHatchMechanism.Spec, Layout> LAYOUTS = new HashMap<>();
    private static final Map<UUID, Cover> COVERS = new HashMap<>();
    private static boolean attempted, ready;

    private GroundHatchTurfR64() {}

    /** The grass texture and the tints are read again after a resource reload. */
    public static void forget()
    {
        attempted = false;ready = false;
        COVERS.clear();
    }

    /** Whether the hatch's cover blocks are in place: then they are the ground, and its leaves lie inside them. */
    static boolean covered(NervSiloDoorEntity door, SiloHatchMechanism.Spec spec)
    {
        return door.level().getBlockState(cover(door, spec).cell).is(ModBlocks.NERV_GROUND_HATCH.get());
    }

    static void draw(PoseStack poses, MultiBufferSource buffers, NervSiloDoorEntity door,
            SiloHatchMechanism.Spec spec, float open, int light)
    {
        if (buffers instanceof OutlineBufferSource || covered(door, spec)) return;
        ResourceLocation texture = texture();
        if (texture == null) return;
        Cover cover = cover(door, spec);
        if (!ShaderShadowPassR44.active() && RigidMachineryPartR44.outsideClipR60(cover.layout.bounds(),
                RenderSystem.getProjectionMatrix(), RenderSystem.getModelViewMatrix(), poses.last().pose())) return;
        // One buffer for all of it: asking for another type in between would end this batch.
        VertexConsumer out = buffers.getBuffer(ModelRenderTypesR49.groundCover(texture));
        Matrix4f pose = poses.last().pose();
        Matrix3f normal = poses.last().normal();
        for (int n = 0; n < cover.leaves.length; n++)
        {
            Leaf leaf = cover.layout.leaves().get(n);
            var panel = SiloHatchMechanism.panel(leaf.index(), open, spec);
            emit(out, pose, normal, cover.leaves[n], (float)(leaf.side() * (panel.x() - leaf.index() * spec.panelWidth())),
                    (float)(cover.ground + panel.y()), light);
        }
    }

    private static void emit(VertexConsumer out, Matrix4f pose, Matrix3f normal, float[] v, float dx, float y, int light)
    {
        for (int i = 0; i < v.length; i += STRIDE)
            out.vertex(pose, v[i] + dx, y, v[i + 1]).color(v[i + 4], v[i + 5], v[i + 6], 1F).uv(v[i + 2], v[i + 3])
                    .overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light).normal(normal, 0F, 1F, 0F).endVertex();
    }

    private static Cover cover(NervSiloDoorEntity door, SiloHatchMechanism.Spec spec)
    {
        Level level = door.level();
        Cover cover = COVERS.get(door.getUUID());
        long now = level.getGameTime();
        if (cover != null && cover.level == level && cover.spec.equals(spec) && cover.at.equals(door.position())
                && cover.yaw == door.getYRot() && now >= cover.built && now - cover.built < TINT_TICKS) return cover;
        if (COVERS.size() > 16) COVERS.clear();
        cover = new Cover();
        cover.level = level;cover.spec = spec;cover.at = door.position();cover.yaw = door.getYRot();cover.built = now;
        cover.layout = LAYOUTS.computeIfAbsent(spec, key -> layout(door.declaredGeometryR52()));
        var frame = door.actualFrameR52();
        int layer = (int)Math.floor(cover.at.y + cover.layout.leafTop() - .5);
        cover.cell = BlockPos.containing(cover.at.x, layer, cover.at.z);
        cover.ground = layer + 1 - cover.at.y;
        // Texture coordinates stay small numbers wherever the hatch stands.
        double originX = Math.floor(cover.at.x / BLOCKS) * BLOCKS, originZ = Math.floor(cover.at.z / BLOCKS) * BLOCKS;
        cover.leaves = new float[cover.layout.leaves().size()][];
        for (int n = 0; n < cover.leaves.length; n++)
            cover.leaves[n] = pieces(level, frame, List.of(cover.layout.leaves().get(n).box()), cover.ground, originX, originZ);
        COVERS.put(door.getUUID(), cover);
        return cover;
    }

    /** Rectangles cut into pieces, each corner with the place on the tiled sheet and the tint of the ground there. */
    private static float[] pieces(Level level, com.projectseele.world.RigidTransform frame, List<double[]> boxes,
            double top, double originX, double originZ)
    {
        var out = new ArrayList<float[]>();
        var cursor = new BlockPos.MutableBlockPos();
        for (double[] box : boxes)
        {
            int nx = Math.max(1, (int)Math.ceil((box[1] - box[0]) / CELL)), nz = Math.max(1, (int)Math.ceil((box[3] - box[2]) / CELL));
            for (int ix = 0; ix < nx; ix++) for (int iz = 0; iz < nz; iz++)
            {
                double x0 = box[0] + (box[1] - box[0]) * ix / nx, x1 = box[0] + (box[1] - box[0]) * (ix + 1) / nx;
                double z0 = box[2] + (box[3] - box[2]) * iz / nz, z1 = box[2] + (box[3] - box[2]) * (iz + 1) / nz;
                // Counter-clockwise seen from above.
                double[][] corners = {{x0, z1}, {x1, z1}, {x1, z0}, {x0, z0}};
                float[] quad = new float[4 * STRIDE];
                for (int c = 0; c < 4; c++)
                {
                    Vec3 world = frame.transformPoint(new Vec3(corners[c][0], top, corners[c][1]));
                    int tint = BiomeColors.getAverageGrassColor(level, cursor.set(Math.floor(world.x), Math.floor(world.y), Math.floor(world.z)));
                    int o = c * STRIDE;
                    quad[o] = (float)corners[c][0];quad[o + 1] = (float)corners[c][1];
                    quad[o + 2] = (float)((world.x - originX) / BLOCKS);quad[o + 3] = (float)((world.z - originZ) / BLOCKS);
                    quad[o + 4] = (tint >> 16 & 255) / 255F;quad[o + 5] = (tint >> 8 & 255) / 255F;quad[o + 6] = (tint & 255) / 255F;
                }
                out.add(quad);
            }
        }
        float[] all = new float[out.size() * 4 * STRIDE];
        for (int n = 0; n < out.size(); n++) System.arraycopy(out.get(n), 0, all, n * 4 * STRIDE, 4 * STRIDE);
        return all;
    }

    /** Read from the hatch's own parts: each leaf's footprint, and the collar's top faces for where the leaves end. */
    private static Layout layout(NervSiloHatchGeometryR52 geometry)
    {
        var leaves = new ArrayList<Leaf>();
        var collar = new ArrayList<double[]>();
        double leafTop = Double.NEGATIVE_INFINITY, collarTop = Double.NEGATIVE_INFINITY;
        double width = geometry.spec().panelWidth();
        for (var piece : geometry.pieces(0F))
        {
            double[] v = piece.part().vertices();
            if (piece.moving())
            {
                double shift = piece.local().translation().x;
                double x0 = Double.POSITIVE_INFINITY, x1 = Double.NEGATIVE_INFINITY, z0 = x0, z1 = x1;
                for (int i = 0; i < v.length; i += 6)
                {
                    x0 = Math.min(x0, v[i] + shift);x1 = Math.max(x1, v[i] + shift);
                    z0 = Math.min(z0, v[i + 2]);z1 = Math.max(z1, v[i + 2]);
                    leafTop = Math.max(leafTop, v[i + 1]);
                }
                double centre = (x0 + x1) / 2;
                leaves.add(new Leaf(new double[]{x0, x1, z0, z1}, centre < 0 ? -1 : 1, (int)Math.floor(Math.abs(centre) / width)));
            }
            else if (collar.isEmpty() && piece.part().name().equals("frame"))
            {
                for (int i = 1; i < v.length; i += 6) collarTop = Math.max(collarTop, v[i]);
                // Both triangles of a top rectangle have its bounds.
                var faces = new LinkedHashSet<List<Double>>();
                for (int t = 0; t < v.length; t += 18)
                {
                    if (Math.abs(v[t + 1] - collarTop) > 1e-6 || Math.abs(v[t + 7] - collarTop) > 1e-6 || Math.abs(v[t + 13] - collarTop) > 1e-6) continue;
                    faces.add(List.of(Math.min(v[t], Math.min(v[t + 6], v[t + 12])), Math.max(v[t], Math.max(v[t + 6], v[t + 12])),
                            Math.min(v[t + 2], Math.min(v[t + 8], v[t + 14])), Math.max(v[t + 2], Math.max(v[t + 8], v[t + 14]))));
                }
                for (var face : faces) collar.add(new double[]{face.get(0), face.get(1), face.get(2), face.get(3)});
            }
        }
        if (leaves.isEmpty() || collar.isEmpty()) throw new IllegalStateException("A ground hatch needs its leaves and its collar");
        // The outermost leaf on each side also covers the slot between itself and the collar.
        double inner = Double.POSITIVE_INFINITY, outer = 0, depth = 0;
        for (double[] box : collar)
        {
            if (box[0] > 0) inner = Math.min(inner, box[0]);
            outer = Math.max(outer, Math.max(-box[0], box[1]));depth = Math.max(depth, Math.max(-box[2], box[3]));
        }
        for (Leaf leaf : leaves)
        {
            if (leaf.index() != SiloHatchMechanism.PANELS - 1 || inner == Double.POSITIVE_INFINITY) continue;
            if (leaf.side() > 0) leaf.box()[1] = Math.max(leaf.box()[1], inner);
            else leaf.box()[0] = Math.min(leaf.box()[0], -inner);
        }
        var spec = geometry.spec();
        double reach = Math.max(outer, spec.caseOuterX());
        float[] bounds = {(float)-reach, (float)(-spec.maximumTier() - 1), (float)-depth, (float)reach, (float)(collarTop + 1), (float)depth};
        return new Layout(List.copyOf(leaves), leafTop, bounds);
    }

    /** The pack's grass top, tiled with the terrain's four turns and mipmapped like the block atlas. */
    private static ResourceLocation texture()
    {
        if (attempted) return ready ? TILED : null;
        attempted = true;
        Minecraft minecraft = Minecraft.getInstance();
        try (var in = minecraft.getResourceManager().open(SOURCE);NativeImage tile = NativeImage.read(in))
        {
            int size = tile.getWidth();
            // An animated strip gives its first frame. Sizes that cannot be halved evenly are left alone.
            if (tile.getHeight() < size || Integer.bitCount(size) != 1 || size * BLOCKS > 4096)
                throw new IOException("Unusable grass texture " + size + "x" + tile.getHeight());
            int levels = Math.min(minecraft.options.mipmapLevels().get(), Integer.numberOfTrailingZeros(size));
            NativeImage sheet = new NativeImage(size * BLOCKS, size * BLOCKS, false);
            for (int bz = 0; bz < BLOCKS; bz++) for (int bx = 0; bx < BLOCKS; bx++)
            {
                int turn = turn(bx, bz);
                for (int y = 0; y < size; y++) for (int x = 0; x < size; x++)
                {
                    int sx = turn == 0 ? x : turn == 1 ? y : turn == 2 ? size - 1 - x : size - 1 - y;
                    int sy = turn == 0 ? y : turn == 1 ? size - 1 - x : turn == 2 ? size - 1 - y : x;
                    sheet.setPixelRGBA(bx * size + x, bz * size + y, tile.getPixelRGBA(sx, sy) | 0xFF000000);
                }
            }
            minecraft.getTextureManager().register(TILED, new Sheet(MipmapGenerator.generateMipLevels(new NativeImage[]{sheet}, levels)));
            ready = true;
        }
        catch (IOException | RuntimeException unusable)
        {
            ProjectSeele.LOGGER.warn("Ground hatch drawn without its grass: {}", unusable.toString());
        }
        return ready ? TILED : null;
    }

    private static int turn(int x, int z)
    {
        int hash = x * 73428767 ^ z * 912931;
        hash ^= hash >>> 13;hash *= 0x5bd1e995;
        return hash >>> 15 & 3;
    }

    /** A repeating texture with its own mip levels, which the stock dynamic texture does not have. */
    private static final class Sheet extends AbstractTexture
    {
        Sheet(NativeImage[] levels)
        {
            TextureUtil.prepareImage(getId(), levels.length - 1, levels[0].getWidth(), levels[0].getHeight());
            for (int level = 0; level < levels.length; level++)
                levels[level].upload(level, 0, 0, 0, 0, levels[level].getWidth(), levels[level].getHeight(), false, false, levels.length > 1, true);
        }

        @Override
        public void load(ResourceManager manager) {}
    }
}

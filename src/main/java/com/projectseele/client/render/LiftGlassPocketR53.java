package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.block.model.BakedQuad;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.client.resources.model.BakedModel;
import net.minecraft.core.Direction;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraftforge.client.RenderTypeHelper;
import net.minecraftforge.client.model.BakedModelWrapper;
import net.minecraftforge.client.model.data.ModelData;

/** The side cassette hides retracted glass; UVs continue moving with the full leaf. */
final class LiftGlassPocketR53
{
    private LiftGlassPocketR53() {}

    static void render(PoseStack poses, MultiBufferSource buffers, int light,
            double x, float width, int height, double half)
    {
        float low = (float)Math.max(0, (-half - x) / width);
        float high = (float)Math.min(1, (half - x) / width);
        if (high - low <= 1.0E-5F) return;
        var dispatcher = Minecraft.getInstance().getBlockRenderer();
        var state = Blocks.GLASS.defaultBlockState();
        var original = dispatcher.getBlockModel(state);
        BakedModel clipped = new BakedModelWrapper<BakedModel>(original)
        {
            @Override
            public List<BakedQuad> getQuads(BlockState block, Direction side,
                    RandomSource random, ModelData data, RenderType layer)
            {
                var result = new ArrayList<BakedQuad>();
                for (var quad : original.getQuads(block, side, random, data, layer))
                    clip(quad, low, high, result);
                return result;
            }
        };
        poses.pushPose();
        poses.translate(x, 0, -.04);
        poses.scale(width, height, .08F);
        for (var layer : original.getRenderTypes(state, RandomSource.create(42), ModelData.EMPTY))
            dispatcher.getModelRenderer().renderModel(poses.last(),
                    buffers.getBuffer(RenderTypeHelper.getEntityRenderType(layer, false)),
                    state, clipped, 1, 1, 1, light, OverlayTexture.NO_OVERLAY,
                    ModelData.EMPTY, layer);
        poses.popPose();
    }

    private static void clip(BakedQuad quad, float low, float high, List<BakedQuad> output)
    {
        int[] packed = quad.getVertices();
        int stride = packed.length / 4;
        var vertices = new ArrayList<int[]>();
        for (int i = 0; i < 4; i++)
            vertices.add(Arrays.copyOfRange(packed, i * stride, (i + 1) * stride));
        List<int[]> polygon = cut(cut(vertices, low, true), high, false);
        if (polygon.size() < 3) return;
        if (polygon.size() == 4)
        {
            int[] clipped = new int[stride * 4];
            for (int i = 0; i < 4; i++)
                System.arraycopy(polygon.get(i), 0, clipped, i * stride, stride);
            output.add(new BakedQuad(clipped, quad.getTintIndex(), quad.getDirection(),
                    quad.getSprite(), quad.isShade(), quad.hasAmbientOcclusion()));
            return;
        }
        // Clipping an arbitrary resource-pack quad can produce more than four vertices.
        for (int i = 1; i + 1 < polygon.size(); i++)
        {
            int[] triangle = new int[stride * 4];
            int[][] corners = {polygon.get(0), polygon.get(i), polygon.get(i + 1), polygon.get(i + 1)};
            for (int j = 0; j < 4; j++)
                System.arraycopy(corners[j], 0, triangle, j * stride, stride);
            output.add(new BakedQuad(triangle, quad.getTintIndex(), quad.getDirection(),
                    quad.getSprite(), quad.isShade(), quad.hasAmbientOcclusion()));
        }
    }

    private static List<int[]> cut(List<int[]> input, float plane, boolean above)
    {
        var output = new ArrayList<int[]>();
        if (input.isEmpty()) return output;
        int[] previous = input.get(input.size() - 1);
        boolean priorInside = inside(previous, plane, above);
        for (int[] current : input)
        {
            boolean currentInside = inside(current, plane, above);
            if (priorInside != currentInside)
            {
                float a = Float.intBitsToFloat(previous[0]);
                float b = Float.intBitsToFloat(current[0]);
                float fraction = (plane - a) / (b - a);
                int[] crossing = previous.clone();
                for (int component : new int[]{0, 1, 2, 4, 5})
                {
                    float from = Float.intBitsToFloat(previous[component]);
                    float to = Float.intBitsToFloat(current[component]);
                    crossing[component] = Float.floatToRawIntBits(from + (to - from) * fraction);
                }
                crossing[0] = Float.floatToRawIntBits(plane);
                output.add(crossing);
            }
            if (currentInside) output.add(current);
            previous = current;
            priorInside = currentInside;
        }
        return output;
    }

    private static boolean inside(int[] vertex, float plane, boolean above)
    {
        float x = Float.intBitsToFloat(vertex[0]);
        return above ? x >= plane : x <= plane;
    }
}

package com.projectseele.world;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;

/** Invocation-local section broadphase; all nonempty reads retain native collision context. */
public final class NativeCollisionShapesR53
{
    private static final double EPSILON = 1.0e-7;
    private record Section(int x, int y, int z) {}
    private static final Comparator<AABB> ORDER = Comparator.comparingDouble((AABB box) -> box.minX)
            .thenComparingDouble(box -> box.minY).thenComparingDouble(box -> box.minZ)
            .thenComparingDouble(box -> box.maxX).thenComparingDouble(box -> box.maxY)
            .thenComparingDouble(box -> box.maxZ);

    public static List<AABB> read(ServerLevel level, Entity actor, AABB query)
    {
        for (double value : new double[]{query.minX, query.minY, query.minZ,
                query.maxX, query.maxY, query.maxZ})
            if (!Double.isFinite(value) || Math.abs(value) > Integer.MAX_VALUE - 32D)
                return nativeRead(level, actor, query);
        if (query.minX >= query.maxX || query.minY >= query.maxY || query.minZ >= query.maxZ)
            return nativeRead(level, actor, query);

        Map<Section, Boolean> air = new HashMap<>();
        for (int x = first(query.minX); x <= last(query.maxX); x++)
        {
            for (int z = first(query.minZ); z <= last(query.maxZ); z++)
            {
                var chunk = level.getChunkSource().getChunkNow(x, z);
                // Unknown halo never introduces a new movement rejection or chunk load.
                if (chunk == null) return nativeRead(level, actor, query);
                var sections = chunk.getSections();
                for (int y = first(query.minY); y <= last(query.maxY); y++)
                {
                    int index = level.getSectionIndex(y * 16);
                    boolean empty = index < 0 || index >= sections.length || sections[index].hasOnlyAir();
                    // A mod may place an external/dynamic shape far from its source block.
                    // Such shapes cannot safely be discovered by partitioning the query.
                    if (!empty && sections[index].maybeHas(BlockState::hasLargeCollisionShape))
                        return nativeRead(level, actor, query);
                    air.put(new Section(x, y, z), empty);
                }
            }
        }

        var result = new ArrayList<AABB>();
        var seen = new TreeSet<AABB>(ORDER);
        for (int x = Mth.floor(query.minX) >> 4; x <= Mth.floor(query.maxX) >> 4; x++)
            for (int y = Mth.floor(query.minY) >> 4; y <= Mth.floor(query.maxY) >> 4; y++)
                for (int z = Mth.floor(query.minZ) >> 4; z <= Mth.floor(query.maxZ) >> 4; z++)
                {
                    var tile = new AABB(Math.max(query.minX, x * 16D), Math.max(query.minY, y * 16D), Math.max(query.minZ, z * 16D),
                            Math.min(query.maxX, x * 16D + 16), Math.min(query.maxY, y * 16D + 16), Math.min(query.maxZ, z * 16D + 16));
                    if (tile.minX >= tile.maxX || tile.minY >= tile.maxY || tile.minZ >= tile.maxZ || allAir(air, tile)) continue;
                    for (var shape : level.getBlockCollisions(actor, tile))
                        for (var box : shape.toAabbs()) if (seen.add(box)) result.add(box);
                }
        return result;
    }

    private static boolean allAir(Map<Section, Boolean> air, AABB query)
    {
        for (int x = first(query.minX); x <= last(query.maxX); x++)
            for (int y = first(query.minY); y <= last(query.maxY); y++)
                for (int z = first(query.minZ); z <= last(query.maxZ); z++)
                    if (!Boolean.TRUE.equals(air.get(new Section(x, y, z)))) return false;
        return true;
    }

    // Match BlockCollisions' cursor expansion, including neighbour source blocks.
    private static int first(double value) { return (Mth.floor(value - EPSILON) - 1) >> 4; }
    private static int last(double value) { return (Mth.floor(value + EPSILON) + 1) >> 4; }

    private static List<AABB> nativeRead(ServerLevel level, Entity actor, AABB query)
    {
        var result = new ArrayList<AABB>();
        for (var shape : level.getBlockCollisions(actor, query)) result.addAll(shape.toAabbs());
        return result;
    }

    private NativeCollisionShapesR53() {}
}
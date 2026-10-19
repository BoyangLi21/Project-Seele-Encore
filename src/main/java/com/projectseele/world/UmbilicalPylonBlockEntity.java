package com.projectseele.world;

import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

import com.projectseele.registry.ModBlockEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.Vec3;
import org.jetbrains.annotations.Nullable;

/**
 * Loaded-pylon index. EVA connection checks iterate this bounded set instead
 * of scanning hundreds of thousands of blocks around every active unit.
 */
public final class UmbilicalPylonBlockEntity extends BlockEntity
{
    private static final Map<ResourceKey<Level>, Set<BlockPos>> LOADED =
            new ConcurrentHashMap<>();

    public UmbilicalPylonBlockEntity(BlockPos pos, BlockState state)
    {
        super(ModBlockEntities.UMBILICAL_PYLON.get(), pos, state);
    }

    @Override
    public void onLoad()
    {
        super.onLoad();
        if (this.level instanceof ServerLevel server)
        {
            LOADED.computeIfAbsent(server.dimension(), key ->
                    ConcurrentHashMap.newKeySet()).add(this.worldPosition.immutable());
        }
    }

    @Override
    public void setRemoved()
    {
        if (this.level instanceof ServerLevel server)
        {
            Set<BlockPos> positions = LOADED.get(server.dimension());
            if (positions != null)
            {
                positions.remove(this.worldPosition);
                if (positions.isEmpty())
                {
                    LOADED.remove(server.dimension(), positions);
                }
            }
        }
        super.setRemoved();
    }

    @Nullable
    public static BlockPos findNearest(ServerLevel level, Vec3 centre, int range)
    {
        return findNearest(level,centre,range,Integer.MIN_VALUE);
    }

    @Nullable
    public static BlockPos findNearest(ServerLevel level, Vec3 centre, int range, int minimumY)
    {
        return findNearest(level,centre,range,minimumY,position->true);
    }

    @Nullable
    public static BlockPos findNearest(ServerLevel level, Vec3 centre, int range, int minimumY,
            java.util.function.Predicate<BlockPos> allowed)
    {
        Set<BlockPos> positions = LOADED.get(level.dimension());
        if (positions == null || positions.isEmpty())
        {
            return null;
        }

        double maximumDistanceSqr = (double) range * range;
        double bestDistanceSqr = maximumDistanceSqr;
        BlockPos nearest = null;
        for (BlockPos position : Set.copyOf(positions))
        {
            if(position.getY()<minimumY||!allowed.test(position))continue;
            if (!level.hasChunkAt(position)
                    || !(level.getBlockEntity(position) instanceof UmbilicalPylonBlockEntity))
            {
                positions.remove(position);
                continue;
            }
            double distanceSqr = centre.distanceToSqr(Vec3.atCenterOf(position));
            if (distanceSqr <= bestDistanceSqr)
            {
                bestDistanceSqr = distanceSqr;
                nearest = position;
            }
        }
        return nearest == null ? null : nearest.immutable();
    }
}

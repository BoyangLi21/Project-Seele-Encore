package com.projectseele.mixin;

import it.unimi.dsi.fastutil.longs.Long2LongOpenHashMap;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;
import java.util.EnumSet;
import net.minecraft.core.BlockPos;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.PathNavigationRegion;
import net.minecraft.world.level.pathfinder.BlockPathTypes;
import net.minecraft.world.level.pathfinder.NodeEvaluator;
import net.minecraft.world.level.pathfinder.WalkNodeEvaluator;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Ground pathfinding evaluates every block of a mob's footprint at every node
 * it visits. Sachiel's 19x61x19 footprint makes that ~22,000 block evaluations
 * per node, nearly all repeated by neighbouring nodes; one search froze the
 * server for 4-6 s. The node only needs the set of path types inside the
 * footprint plus the type at its origin, so per search each block is evaluated
 * once and each footprint column keeps the set of types over the mob's height
 * as a bit mask; a node ORs width x depth column masks. Within one search the
 * region, the mob position and its door abilities do not change, so the result
 * is the same set and the same path. Small mobs keep the original loop.
 */
@Mixin(WalkNodeEvaluator.class)
public abstract class WalkNodeEvaluatorBlockCacheMixin extends NodeEvaluator
{
    @Unique
    private final Long2ObjectOpenHashMap<BlockPathTypes> seele$blocks = new Long2ObjectOpenHashMap<>();
    @Unique
    private final Long2LongOpenHashMap seele$columns = new Long2LongOpenHashMap();
    @Unique
    private BlockPathTypes[] seele$types;
    @Unique
    private boolean seele$caching;
    @Unique
    private long seele$mobPos;
    @Unique
    private boolean seele$mobPosSet;

    @Shadow
    protected abstract BlockPathTypes evaluateBlockPathType(BlockGetter level, BlockPos mobPos, BlockPathTypes type);

    @Inject(method = "prepare", at = @At("TAIL"))
    private void seele$startSearch(PathNavigationRegion region, Mob mob, CallbackInfo callback)
    {
        this.seele$blocks.clear();
        this.seele$columns.clear();
        this.seele$mobPosSet = false;
        this.seele$types = BlockPathTypes.values();
        // Below this footprint the bookkeeping costs about what it saves.
        this.seele$caching = this.entityWidth * this.entityHeight * this.entityDepth >= 64
                && this.seele$types.length <= 64;
    }

    @Inject(method = "done", at = @At("HEAD"))
    private void seele$endSearch(CallbackInfo callback)
    {
        this.seele$caching = false;
        this.seele$blocks.clear();
        this.seele$columns.clear();
    }

    @Redirect(method = "getBlockPathType(Lnet/minecraft/world/level/BlockGetter;IIILnet/minecraft/world/entity/Mob;)Lnet/minecraft/world/level/pathfinder/BlockPathTypes;",
            at = @At(value = "INVOKE", target = "Lnet/minecraft/world/level/pathfinder/WalkNodeEvaluator;getBlockPathTypes(Lnet/minecraft/world/level/BlockGetter;IIILjava/util/EnumSet;Lnet/minecraft/world/level/pathfinder/BlockPathTypes;Lnet/minecraft/core/BlockPos;)Lnet/minecraft/world/level/pathfinder/BlockPathTypes;"))
    private BlockPathTypes seele$footprintTypes(WalkNodeEvaluator self, BlockGetter level, int x, int y, int z,
                                                EnumSet<BlockPathTypes> output, BlockPathTypes fallback, BlockPos mobPos)
    {
        long mob = mobPos.asLong();
        if (!this.seele$caching || level != this.level || this.seele$mobPosSet && mob != this.seele$mobPos)
            return self.getBlockPathTypes(level, x, y, z, output, fallback, mobPos);
        this.seele$mobPos = mob;
        this.seele$mobPosSet = true;
        long mask = 0L;
        for (int i = 0; i < this.entityWidth; i++)
            for (int k = 0; k < this.entityDepth; k++)
                mask |= this.seele$column(level, x + i, y, z + k, mobPos);
        for (int bit = 0; bit < this.seele$types.length; bit++)
            if ((mask & 1L << bit) != 0L) output.add(this.seele$types[bit]);
        return this.seele$evaluated(level, x, y, z, mobPos);
    }

    /** Set of evaluated types in blocks y .. y+height-1 of one footprint column. */
    @Unique
    private long seele$column(BlockGetter level, int x, int y, int z, BlockPos mobPos)
    {
        long key = BlockPos.asLong(x, y, z);
        long mask = this.seele$columns.get(key);
        if (mask != 0L) return mask;
        for (int j = 0; j < this.entityHeight; j++)
            mask |= 1L << this.seele$evaluated(level, x, y + j, z, mobPos).ordinal();
        this.seele$columns.put(key, mask);
        return mask;
    }

    @Unique
    private BlockPathTypes seele$evaluated(BlockGetter level, int x, int y, int z, BlockPos mobPos)
    {
        long key = BlockPos.asLong(x, y, z);
        BlockPathTypes type = this.seele$blocks.get(key);
        if (type == null)
        {
            type = this.evaluateBlockPathType(level, mobPos, this.getBlockPathType(level, x, y, z));
            this.seele$blocks.put(key, type);
        }
        return type;
    }
}

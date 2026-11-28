package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.minecraft.world.level.block.state.BlockState;

/** Passable blackout drape just outside the elevator opening; the car, doors and buttons stay reachable. */
public final class ReserveBlackoutCurtain extends Block
{
    public ReserveBlackoutCurtain()
    {
        super(BlockBehaviour.Properties.copy(Blocks.BLACK_WOOL).noCollission().noOcclusion().noLootTable());
    }

    @Override public int getLightBlock(BlockState state,BlockGetter level,BlockPos pos) { return 15; }
    @Override public boolean propagatesSkylightDown(BlockState state,BlockGetter level,BlockPos pos) { return false; }
}

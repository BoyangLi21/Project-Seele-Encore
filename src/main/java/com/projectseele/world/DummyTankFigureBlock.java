package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.LevelAccessor;
import net.minecraft.world.level.block.GlazedTerracottaBlock;
import net.minecraft.world.level.block.LiquidBlockContainer;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.material.Fluid;
import net.minecraft.world.level.material.FluidState;

/** A submerged display figure has no collision, but the surrounding LCL cannot displace it. */
public final class DummyTankFigureBlock extends GlazedTerracottaBlock implements LiquidBlockContainer
{
    public DummyTankFigureBlock(Properties properties) { super(properties); }

    @Override
    public boolean canPlaceLiquid(BlockGetter level, BlockPos pos, BlockState state, Fluid fluid) { return false; }

    @Override
    public boolean placeLiquid(LevelAccessor level, BlockPos pos, BlockState state, FluidState fluid) { return false; }
}

package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;

/**
 * The closed cover of a hatch that lies level with open ground: grass on top like the terrain around it, plating
 * underneath. A hatch is drawn by its door entity, and a player further away than the server's view distance has
 * no such entity, so a closed hatch has to be blocks to be there at all from a distance, in the far view and on a
 * map. Light passes through this block as through the barrier it stands in for: opening or closing 27,000 cells
 * over a deep shaft relights nothing.
 */
public final class GroundHatchBlockR64 extends Block
{
    public GroundHatchBlockR64(Properties properties)
    {
        super(properties);
    }

    @Override
    public boolean propagatesSkylightDown(BlockState state, BlockGetter level, BlockPos pos)
    {
        return true;
    }

    /** The cover is one sheet: no faces between its own cells. */
    @Override
    public boolean skipRendering(BlockState state, BlockState adjacent, Direction side)
    {
        return adjacent.is(this) || super.skipRendering(state, adjacent, side);
    }
}

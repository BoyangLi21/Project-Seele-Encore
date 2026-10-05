package com.projectseele.world;

import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;

/** Existing solid architectural light panels default to their historical on state. */
public final class FacilityStripLightR47 extends Block
{
    public FacilityStripLightR47(Properties properties)
    {
        super(properties);
        registerDefaultState(stateDefinition.any().setValue(BlockStateProperties.LIT, true));
    }

    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder)
    {
        builder.add(BlockStateProperties.LIT);
    }
}

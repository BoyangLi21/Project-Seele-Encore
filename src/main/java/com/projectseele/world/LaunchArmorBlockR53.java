package com.projectseele.world;

import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.IntegerProperty;

/** A continuous eight-by-sixteen metre plate; collision stays a full cube. */
public final class LaunchArmorBlockR53 extends Block
{
    public static final IntegerProperty COLUMN = IntegerProperty.create("column", 0, 7);
    public static final IntegerProperty ROW = IntegerProperty.create("row", 0, 15);

    public LaunchArmorBlockR53(Properties properties)
    {
        super(properties);
        registerDefaultState(stateDefinition.any().setValue(COLUMN, 0).setValue(ROW, 0));
    }

    @Override
    protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder)
    {
        builder.add(COLUMN, ROW);
    }
}

package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/** Classroom desk with an open student notebook computer. */
public final class SchoolDeskBlock extends Block {
    private static final VoxelShape SHAPE = Shapes.or(
            Block.box(1, 10, 2, 15, 12, 14), Block.box(2, 0, 3, 3, 10, 4),
            Block.box(13, 0, 3, 14, 10, 4), Block.box(2, 0, 12, 3, 10, 13),
            Block.box(13, 0, 12, 14, 10, 13), Block.box(4, 12, 4, 12, 16, 5));
    public SchoolDeskBlock(Properties properties) { super(properties); }

    @Override
    public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context) { return SHAPE; }
}

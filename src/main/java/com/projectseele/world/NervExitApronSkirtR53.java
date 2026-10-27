package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.VoxelShape;

/** Fixed south apron connection, outside the original hatch's fixed collar. */
public final class NervExitApronSkirtR53 extends Block
{
    // Same bounds as models/block/nerv_exit_apron_skirt_r53.json. The 5cm
    // panel-to-collar seam is north of this part and remains open.
    private static final VoxelShape SHAPE = box(0, 12, 10.4, 16, 16, 16);

    public NervExitApronSkirtR53(Properties properties)
    {
        super(properties);
    }

    @Override
    public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos,
            CollisionContext context)
    {
        return SHAPE;
    }

    @Override
    public VoxelShape getCollisionShape(BlockState state, BlockGetter level, BlockPos pos,
            CollisionContext context)
    {
        return SHAPE;
    }
}

package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.VoxelShape;

/** A compact flat moving walk for retained corridors too narrow for two MTR balustrades. */
public final class MovingWalkwayBlock extends HorizontalDirectionalBlock
{
    private static final VoxelShape SHAPE=Block.box(0,0,0,16,15,16);
    public MovingWalkwayBlock(Properties properties)
    {
        super(properties);registerDefaultState(stateDefinition.any().setValue(FACING,Direction.NORTH));
    }
    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> builder){builder.add(FACING);}
    @Override public BlockState getStateForPlacement(BlockPlaceContext context){return defaultBlockState().setValue(FACING,context.getHorizontalDirection());}
    @Override public VoxelShape getShape(BlockState state,BlockGetter level,BlockPos pos,CollisionContext context){return SHAPE;}
    @Override public boolean isPathfindable(BlockState state,BlockGetter level,BlockPos pos,
            net.minecraft.world.level.pathfinder.PathComputationType type)
    {return false;}
    @Override public void entityInside(BlockState state,Level level,BlockPos pos,Entity entity)
    {
        if(!(entity instanceof LivingEntity)||entity instanceof com.projectseele.entity.NervStaffEntity||entity.getBbWidth()>1.1F||entity.isPassenger()||entity.isShiftKeyDown())return;
        if(Math.floor(entity.getX())!=pos.getX()||Math.floor(entity.getZ())!=pos.getZ()||entity.getY()<pos.getY()+.8||entity.getY()>pos.getY()+1.05)return;
        Direction direction=state.getValue(FACING);
        // Add propulsion, like MTR's native flat steps, rather than setting
        // position or overriding a pedestrian's steering and braking.
        entity.push(direction.getStepX()*.075,0,direction.getStepZ()*.075);
    }
}

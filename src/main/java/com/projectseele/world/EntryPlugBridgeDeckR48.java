package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/** A continuous top plate and real under-deck steel, with exposed-edge warning fascia. */
public final class EntryPlugBridgeDeckR48 extends Block
{
    private static final VoxelShape BASE=Shapes.or(box(0,13.5,0,16,16,16),
            box(1,0,1,3,13.5,15),box(13,0,1,15,13.5,15),box(3,2,7,13,4,9));
    public EntryPlugBridgeDeckR48(Properties properties)
    {
        super(properties);
        registerDefaultState(FacilityEdgeRailR41.empty(this));
    }
    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> builder)
    {builder.add(FacilityEdgeRailR41.NORTH,FacilityEdgeRailR41.EAST,FacilityEdgeRailR41.SOUTH,FacilityEdgeRailR41.WEST);}
    @Override public VoxelShape getShape(BlockState state,BlockGetter level,BlockPos pos,CollisionContext context)
    {
        VoxelShape shape=BASE;
        if(state.getValue(FacilityEdgeRailR41.NORTH))shape=Shapes.or(shape,box(0,2,0,16,13.5,.8));
        if(state.getValue(FacilityEdgeRailR41.SOUTH))shape=Shapes.or(shape,box(0,2,15.2,16,13.5,16));
        if(state.getValue(FacilityEdgeRailR41.WEST))shape=Shapes.or(shape,box(0,2,0,.8,13.5,16));
        if(state.getValue(FacilityEdgeRailR41.EAST))shape=Shapes.or(shape,box(15.2,2,0,16,13.5,16));
        return shape;
    }
    @Override public boolean skipRendering(BlockState state,BlockState adjacent,Direction face)
    {return face.getAxis().isHorizontal()&&adjacent.getBlock()==this||super.skipRendering(state,adjacent,face);}
}

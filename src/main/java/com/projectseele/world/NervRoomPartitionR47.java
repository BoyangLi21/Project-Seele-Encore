package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.BooleanProperty;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/** Real thin room panels; corners retain both walls without consuming a metre of interior. */
public final class NervRoomPartitionR47 extends Block
{
    private static final BooleanProperty[] EDGES={BlockStateProperties.NORTH,BlockStateProperties.EAST,
            BlockStateProperties.SOUTH,BlockStateProperties.WEST};
    private static final VoxelShape[] SHAPES=new VoxelShape[16];
    static
    {
        VoxelShape[] edges={Block.box(0,0,0,16,16,2),Block.box(14,0,0,16,16,16),
                Block.box(0,0,14,16,16,16),Block.box(0,0,0,2,16,16)};
        for(int mask=0;mask<16;mask++)
        {
            VoxelShape shape=Shapes.empty();
            for(int edge=0;edge<4;edge++)if((mask&(1<<edge))!=0)shape=Shapes.or(shape,edges[edge]);
            SHAPES[mask]=shape.optimize();
        }
    }
    public NervRoomPartitionR47(Properties properties)
    {
        super(properties);var state=stateDefinition.any();
        for(var edge:EDGES)state=state.setValue(edge,false);
        registerDefaultState(state.setValue(BlockStateProperties.NORTH,true));
    }
    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> builder){builder.add(EDGES);}
    @Override public BlockState getStateForPlacement(BlockPlaceContext context)
    {
        var direction=context.getHorizontalDirection();var state=defaultBlockState();
        for(var edge:EDGES)state=state.setValue(edge,false);
        return state.setValue(switch(direction){case EAST->EDGES[1];case SOUTH->EDGES[2];case WEST->EDGES[3];default->EDGES[0];},true);
    }
    @Override public VoxelShape getShape(BlockState state,BlockGetter world,BlockPos pos,CollisionContext context)
    {
        int mask=0;for(int i=0;i<4;i++)if(state.getValue(EDGES[i]))mask|=1<<i;return SHAPES[mask];
    }
    @Override public BlockState rotate(BlockState state,net.minecraft.world.level.block.Rotation rotation)
    {
        var result=state;for(var edge:EDGES)result=result.setValue(edge,false);
        var directions=new net.minecraft.core.Direction[]{net.minecraft.core.Direction.NORTH,net.minecraft.core.Direction.EAST,
                net.minecraft.core.Direction.SOUTH,net.minecraft.core.Direction.WEST};
        for(int i=0;i<4;i++)for(int j=0;j<4;j++)if(rotation.rotate(directions[i])==directions[j])result=result.setValue(EDGES[j],state.getValue(EDGES[i]));
        return result;
    }
    @Override public BlockState mirror(BlockState state,net.minecraft.world.level.block.Mirror mirror)
    {
        var result=state;for(var edge:EDGES)result=result.setValue(edge,false);
        var directions=new net.minecraft.core.Direction[]{net.minecraft.core.Direction.NORTH,net.minecraft.core.Direction.EAST,
                net.minecraft.core.Direction.SOUTH,net.minecraft.core.Direction.WEST};
        for(int i=0;i<4;i++)for(int j=0;j<4;j++)if(mirror.mirror(directions[i])==directions[j])result=result.setValue(EDGES[j],state.getValue(EDGES[i]));
        return result;
    }
}

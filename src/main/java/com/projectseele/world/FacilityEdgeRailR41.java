package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Mirror;
import net.minecraft.world.level.block.Rotation;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.BooleanProperty;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/** Edge-mounted steel rails preserve the standing space in a narrow gallery. */
public final class FacilityEdgeRailR41 extends Block
{
    public static final BooleanProperty NORTH=BooleanProperty.create("north"),EAST=BooleanProperty.create("east"),
            SOUTH=BooleanProperty.create("south"),WEST=BooleanProperty.create("west");
    private static final BooleanProperty[] SIDES={NORTH,EAST,SOUTH,WEST};
    private static final VoxelShape[] SHAPES=new VoxelShape[16];
    static
    {
        VoxelShape north=Shapes.or(box(0,0,0,2,22,2),box(14,0,0,16,22,2),box(0,10,0,16,12,2),box(0,20,0,16,22,2));
        VoxelShape east=Shapes.or(box(14,0,0,16,22,2),box(14,0,14,16,22,16),box(14,10,0,16,12,16),box(14,20,0,16,22,16));
        VoxelShape south=Shapes.or(box(0,0,14,2,22,16),box(14,0,14,16,22,16),box(0,10,14,16,12,16),box(0,20,14,16,22,16));
        VoxelShape west=Shapes.or(box(0,0,0,2,22,2),box(0,0,14,2,22,16),box(0,10,0,2,12,16),box(0,20,0,2,22,16));
        VoxelShape[] sides={north,east,south,west};
        for(int mask=0;mask<16;mask++){VoxelShape shape=Shapes.empty();for(int i=0;i<4;i++)if((mask&(1<<i))!=0)shape=Shapes.or(shape,sides[i]);SHAPES[mask]=shape;}
    }
    public FacilityEdgeRailR41(Properties properties)
    {
        super(properties);registerDefaultState(stateDefinition.any().setValue(NORTH,true).setValue(EAST,false).setValue(SOUTH,false).setValue(WEST,false));
    }
    public static BooleanProperty side(Direction direction)
    {return switch(direction){case NORTH->NORTH;case EAST->EAST;case SOUTH->SOUTH;case WEST->WEST;default->throw new IllegalArgumentException("Horizontal rail side");};}
    public static BlockState empty(Block block)
    {return block.defaultBlockState().setValue(NORTH,false).setValue(EAST,false).setValue(SOUTH,false).setValue(WEST,false);}
    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> builder){builder.add(SIDES);}
    @Override public VoxelShape getShape(BlockState state,BlockGetter level,BlockPos pos,CollisionContext context)
    {int mask=0;for(int i=0;i<4;i++)if(state.getValue(SIDES[i]))mask|=1<<i;return SHAPES[mask];}
    @Override public net.minecraft.world.level.pathfinder.BlockPathTypes getBlockPathType(
            BlockState state,BlockGetter level,BlockPos pos,net.minecraft.world.entity.Mob mob)
    {
        // Empty stored rail states remain empty. A live 22/16 edge rail is
        // a fence, so native NPC paths use its real openings instead of its top.
        return getShape(state,level,pos,CollisionContext.empty()).isEmpty()?
                net.minecraft.world.level.pathfinder.BlockPathTypes.OPEN:
                net.minecraft.world.level.pathfinder.BlockPathTypes.FENCE;
    }
    @Override public BlockState getStateForPlacement(BlockPlaceContext context)
    {return empty(this).setValue(side(context.getHorizontalDirection()),true);}
    @Override public BlockState rotate(BlockState state,Rotation rotation)
    {BlockState result=empty(this);for(Direction d:Direction.Plane.HORIZONTAL)result=result.setValue(side(rotation.rotate(d)),state.getValue(side(d)));return result;}
    @Override public BlockState mirror(BlockState state,Mirror mirror)
    {BlockState result=empty(this);for(Direction d:Direction.Plane.HORIZONTAL)result=result.setValue(side(mirror.mirror(d)),state.getValue(side(d)));return result;}
}

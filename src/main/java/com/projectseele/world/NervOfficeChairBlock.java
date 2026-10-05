package com.projectseele.world;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.shapes.*;
/** Compact padded seating with its back and armrests inside the original furniture footprint. */
public final class NervOfficeChairBlock extends net.minecraft.world.level.block.HorizontalDirectionalBlock
{
    public NervOfficeChairBlock(Properties p){super(p);registerDefaultState(stateDefinition.any().setValue(FACING,Direction.NORTH));}
    @Override protected void createBlockStateDefinition(net.minecraft.world.level.block.state.StateDefinition.Builder<Block,BlockState> b){b.add(FACING);}
    @Override public BlockState getStateForPlacement(net.minecraft.world.item.context.BlockPlaceContext c){return defaultBlockState().setValue(FACING,c.getHorizontalDirection().getOpposite());}
    @Override public BlockState rotate(BlockState s,net.minecraft.world.level.block.Rotation r){return s.setValue(FACING,r.rotate(s.getValue(FACING)));}
    @Override public BlockState mirror(BlockState s,net.minecraft.world.level.block.Mirror m){return rotate(s,m.getRotation(s.getValue(FACING)));}
    @Override public net.minecraft.world.InteractionResult use(BlockState state,net.minecraft.world.level.Level level,BlockPos pos,net.minecraft.world.entity.player.Player player,net.minecraft.world.InteractionHand hand,net.minecraft.world.phys.BlockHitResult hit)
    {
        return sit(level,pos,player,state.getValue(FACING),-.1);
    }
    public static net.minecraft.world.InteractionResult sit(net.minecraft.world.level.Level level,BlockPos pos,net.minecraft.world.entity.player.Player player,Direction facing,double height)
    {
        if(player.isSecondaryUseActive()||player.isPassenger())return net.minecraft.world.InteractionResult.PASS;
        if(!level.isClientSide)
        {
            var seats=level.getEntitiesOfClass(com.projectseele.entity.NervCommandSeatEntity.class,new net.minecraft.world.phys.AABB(pos).inflate(.5),e->e.getTags().contains("seele_office_seat")
                    ||e.getType()==com.projectseele.registry.ModEntities.PILOT_REST_SEAT_R47.get());
            if(seats.stream().anyMatch(e->e.isVehicle()||e.getType()==com.projectseele.registry.ModEntities.PILOT_REST_SEAT_R47.get()))return net.minecraft.world.InteractionResult.CONSUME;
            var seat=com.projectseele.registry.ModEntities.NERV_COMMAND_SEAT.get().create(level);
            if(seat!=null)
            {
                seat.addTag("seele_office_seat");seat.getPersistentData().putLong("OfficeChair",pos.asLong());seat.moveTo(pos.getX()+.5,pos.getY()+height,pos.getZ()+.5,facing.toYRot(),0);level.addFreshEntity(seat);
                if(!player.startRiding(seat,true))seat.discard();
            }
        }
        return net.minecraft.world.InteractionResult.sidedSuccess(level.isClientSide);
    }
    @Override public VoxelShape getShape(BlockState s,BlockGetter l,BlockPos p,CollisionContext c)
    {
        VoxelShape base=Shapes.or(Block.box(4,0,4,12,9,12),Block.box(2,8,2,14,11,14));
        return Shapes.or(base,switch(s.getValue(FACING)){case NORTH->Block.box(2,9,12,14,19,15);case SOUTH->Block.box(2,9,1,14,19,4);case EAST->Block.box(1,9,2,4,19,14);default->Block.box(12,9,2,15,19,14);});
    }
}

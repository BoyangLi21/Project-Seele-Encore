package com.projectseele.world;

import com.projectseele.item.NervAccessCardR44;
import com.projectseele.registry.ModBlockEntities;
import net.minecraft.core.*;
import net.minecraft.world.*;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.*;
import net.minecraft.world.level.block.*;
import net.minecraft.world.level.block.entity.*;
import net.minecraft.world.level.block.state.*;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.block.state.properties.DirectionProperty;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.shapes.*;
import net.minecraft.world.item.context.BlockPlaceContext;

/** Wall-mounted reader; door geometry and ownership are explicit block-entity data. */
public final class NervAccessReaderR44 extends BaseEntityBlock
{
    public static final DirectionProperty FACING=BlockStateProperties.HORIZONTAL_FACING;
    public NervAccessReaderR44(Properties properties){super(properties);registerDefaultState(stateDefinition.any().setValue(FACING,Direction.NORTH));}
    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> builder){builder.add(FACING);}
    @Override public BlockState getStateForPlacement(BlockPlaceContext c){return defaultBlockState().setValue(FACING,c.getHorizontalDirection().getOpposite());}
    @Override public RenderShape getRenderShape(BlockState state){return RenderShape.MODEL;}
    @Override public VoxelShape getShape(BlockState state,BlockGetter level,BlockPos pos,CollisionContext context)
    {
        return switch(state.getValue(FACING))
        {case SOUTH->box(3,2,0,13,14,4);case WEST->box(12,2,3,16,14,13);case EAST->box(0,2,3,4,14,13);default->box(3,2,12,13,14,16);};
    }
    @Override public BlockEntity newBlockEntity(BlockPos pos,BlockState state){return new NervAccessReaderEntityR44(pos,state);}
    @Override public <T extends BlockEntity> BlockEntityTicker<T> getTicker(Level level,BlockState state,BlockEntityType<T> type)
    {return level.isClientSide?null:createTickerHelper(type,ModBlockEntities.NERV_ACCESS_READER.get(),NervAccessReaderEntityR44::tick);}
    @Override public InteractionResult use(BlockState state,Level level,BlockPos pos,Player player,InteractionHand hand,BlockHitResult hit)
    {
        if(!(level.getBlockEntity(pos) instanceof NervAccessReaderEntityR44 reader))return InteractionResult.PASS;
        ItemStack held=player.getItemInHand(hand);
        InteractionHand presentation=hand;
        if(!(held.getItem() instanceof NervAccessCardR44)&&player.getOffhandItem().getItem() instanceof NervAccessCardR44)
        {presentation=InteractionHand.OFF_HAND;held=player.getOffhandItem();}
        if(level.isClientSide)return InteractionResult.SUCCESS;
        reader.present(player,presentation,held.getItem() instanceof NervAccessCardR44 card?card.clearance():0);
        if(held.getItem() instanceof NervAccessCardR44)player.startUsingItem(presentation);
        player.swing(presentation,true);return InteractionResult.CONSUME;
    }
}

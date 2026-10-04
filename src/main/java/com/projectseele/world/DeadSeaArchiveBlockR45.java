package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.*;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.*;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.shapes.*;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.DistExecutor;

/** A physical archive stand; reading never grants permission or starts a mission. */
public final class DeadSeaArchiveBlockR45 extends HorizontalDirectionalBlock implements EntityBlock
{
    private static final VoxelShape SHAPE=Shapes.or(Shapes.box(.12,0,.15,.88,.11,.85),
            Shapes.box(.28,.11,.28,.72,1.03,.72),Shapes.box(.03,1.03,.14,.97,1.31,.88));
    public DeadSeaArchiveBlockR45(Properties properties)
    {super(properties);registerDefaultState(stateDefinition.any().setValue(FACING,Direction.NORTH));}
    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> builder){builder.add(FACING);}
    @Override public BlockState getStateForPlacement(BlockPlaceContext context){return defaultBlockState().setValue(FACING,context.getHorizontalDirection().getOpposite());}
    @Override public BlockState rotate(BlockState state,Rotation rotation){return state.setValue(FACING,rotation.rotate(state.getValue(FACING)));}
    @Override public BlockState mirror(BlockState state,Mirror mirror){return rotate(state,mirror.getRotation(state.getValue(FACING)));}
    @Override public VoxelShape getShape(BlockState state,BlockGetter level,BlockPos pos,CollisionContext context){return SHAPE;}
    @Override public RenderShape getRenderShape(BlockState state){return RenderShape.ENTITYBLOCK_ANIMATED;}
    @Override public BlockEntity newBlockEntity(BlockPos pos,BlockState state){return new DeadSeaArchiveEntityR45(pos,state);}
    @Override public InteractionResult use(BlockState state,Level level,BlockPos pos,Player player,InteractionHand hand,BlockHitResult hit)
    {
        if(hand!=InteractionHand.MAIN_HAND)return InteractionResult.PASS;
        if(level.isClientSide)DistExecutor.unsafeRunWhenOn(Dist.CLIENT,()->()->com.projectseele.client.DeadSeaArchiveScreenR45.open());
        return InteractionResult.sidedSuccess(level.isClientSide);
    }
}

package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.BooleanProperty;
import net.minecraft.world.phys.BlockHitResult;

/** Operator core embedded in each Tokyo-3 armoured building. */
public final class RetractableBuildingCoreBlock extends Block
{
    public static final BooleanProperty ARMED = BooleanProperty.create("armed");

    public RetractableBuildingCoreBlock(Properties properties)
    {
        super(properties);
        this.registerDefaultState(this.stateDefinition.any().setValue(ARMED, false));
    }

    @Override
    protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder)
    {
        builder.add(ARMED);
    }

    @Override
    public InteractionResult use(BlockState state, Level level, BlockPos position,
                                 Player player, InteractionHand hand, BlockHitResult hit)
    {
        if (hand != InteractionHand.MAIN_HAND)
        {
            return InteractionResult.PASS;
        }
        if (!(level instanceof ServerLevel serverLevel))
        {
            return InteractionResult.SUCCESS;
        }
        Tokyo3RetractionDirector.RequestResult result =
                Tokyo3RetractionDirector.toggleNearest(serverLevel, position);
        player.displayClientMessage(com.projectseele.world.OperationText.read(result.message()), false);
        return result.accepted() ? InteractionResult.CONSUME : InteractionResult.FAIL;
    }
}

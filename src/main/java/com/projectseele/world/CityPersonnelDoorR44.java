package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.world.*;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BlockSetType;
import net.minecraft.world.phys.BlockHitResult;

/** Public metal entrances have a real usable latch, rather than decorative iron-door pairs. */
public final class CityPersonnelDoorR44 extends DoorBlock
{
    public CityPersonnelDoorR44(Properties properties){super(properties,BlockSetType.IRON);}
    @Override public void setOpen(net.minecraft.world.entity.Entity actor,Level level,
                                  BlockState state,BlockPos pos,boolean opening)
    {
        if (!state.is(this) || state.getValue(OPEN) == opening) return;
        level.setBlock(pos, state.setValue(OPEN, opening), 10);
        if (!level.isClientSide)
        {
            level.playSound(null, pos, (opening
                    ? com.projectseele.registry.ModSounds.PERSONNEL_DOOR_OPEN
                    : com.projectseele.registry.ModSounds.PERSONNEL_DOOR_CLOSE).get(),
                    net.minecraft.sounds.SoundSource.BLOCKS, .65F, 1F);
            level.gameEvent(actor, opening ? net.minecraft.world.level.gameevent.GameEvent.BLOCK_OPEN
                    : net.minecraft.world.level.gameevent.GameEvent.BLOCK_CLOSE, pos);
        }
    }
    @Override public void neighborChanged(BlockState state,Level level,BlockPos pos,
                                         net.minecraft.world.level.block.Block block,BlockPos from,boolean moving)
    {
        if(level instanceof net.minecraft.server.level.ServerLevel server
                && (TvPersonnelPlatformInterlockR44.ownsManualDoor(server,pos)
                ||FacilityDoorControlsR49.ownsDoor(server,pos)))return;
        super.neighborChanged(state,level,pos,block,from,moving);
    }
    @Override public InteractionResult use(BlockState state,Level level,BlockPos pos,Player player,InteractionHand hand,BlockHitResult hit)
    {
        if(!level.isClientSide)
        {
            if(level instanceof net.minecraft.server.level.ServerLevel server
                    && TvPersonnelPlatformInterlockR44.handleUse(server,pos,player))
                return InteractionResult.CONSUME;
            setOpen(player,level,state,pos,!state.getValue(OPEN));
        }
        return InteractionResult.sidedSuccess(level.isClientSide);
    }
}

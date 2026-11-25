package com.projectseele.world;

import com.projectseele.entity.NervStaffEntity;
import com.projectseele.registry.ModBlockEntities;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.DoubleBlockHalf;
import net.minecraft.world.phys.AABB;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * The lower half of a NERV staff gate lane. Every fourth tick it looks at the lane and the block in front of its entry
 * side: a card lane opens for a player holding a NERV card (operators pass, as at every other card check) or for NERV
 * staff; a free lane opens for anyone. It stays open while somebody is in the lane and closes a second after it clears.
 * Nobody is ever shut in: a closed lane with a body in its doorway opens again.
 */
public final class NervStaffGateEntityR65 extends BlockEntity
{
    private static final int HOLD_TICKS = 20;
    private static final Map<UUID, Long> REFUSED_AT = new HashMap<>();
    private int clearFor;

    public NervStaffGateEntityR65(BlockPos pos, BlockState state)
    {
        super(ModBlockEntities.NERV_STAFF_GATE.get(), pos, state);
    }

    public static void tick(Level level, BlockPos pos, BlockState state, NervStaffGateEntityR65 gate)
    {
        if (!(level instanceof ServerLevel server) || (level.getGameTime() + pos.asLong()) % 4 != 0
                || state.getValue(NervStaffGateR65.HALF) != DoubleBlockHalf.LOWER)
        {
            return;
        }
        Direction travel = state.getValue(NervStaffGateR65.FACING);
        Direction back = travel.getOpposite();
        AABB lane = new AABB(pos).inflate(-0.05, 0, -0.05).expandTowards(0, 1, 0);
        // inside the closed leaves (which span 0.469-0.531): a body there is caught in the doorway, one pressing on them from the
        // entry side is not (it overlaps the lane cell but must still show a card)
        AABB doorway = travel.getAxis() == Direction.Axis.X
                ? new AABB(pos.getX() + 0.485, pos.getY(), pos.getZ() + 0.1, pos.getX() + 0.515, pos.getY() + 2, pos.getZ() + 0.9)
                : new AABB(pos.getX() + 0.1, pos.getY(), pos.getZ() + 0.485, pos.getX() + 0.9, pos.getY() + 2, pos.getZ() + 0.515);
        AABB approach = new AABB(pos.relative(back)).expandTowards(back.getStepX() * 0.5, 1, back.getStepZ() * 0.5).expandTowards(0, 1, 0);
        boolean card = state.getValue(NervStaffGateR65.CARD);
        boolean open = state.getValue(NervStaffGateR65.OPEN);
        boolean inLane = false, admitted = false;
        for (Entity e : server.getEntities((Entity) null, lane.minmax(approach), x -> x.isAlive() && !x.isSpectator()))
        {
            boolean inside = e.getBoundingBox().intersects(open ? lane : doorway);
            inLane |= inside;
            if (!(e instanceof ServerPlayer) && !(e instanceof NervStaffEntity))
            {
                continue;
            }
            if (!card || e instanceof NervStaffEntity || NervStaffDialogue.authorized((ServerPlayer) e))
            {
                admitted = true;
            }
            else if (!open && e instanceof ServerPlayer player)
            {
                long now = level.getGameTime();
                Long last = REFUSED_AT.get(player.getUUID());
                if (last == null || now - last > 40)
                {
                    REFUSED_AT.put(player.getUUID(), now);
                    player.displayClientMessage(Component.translatable("message.projectseele.surface.card").withStyle(ChatFormatting.RED), true);
                    level.playSound(null, pos, SoundEvents.NOTE_BLOCK_BASS.value(), SoundSource.BLOCKS, .35F, .75F);
                }
            }
        }
        if (admitted || inLane)
        {
            gate.clearFor = 0;
            if (!open)
            {
                set(server, pos, state, true);
                level.playSound(null, pos, SoundEvents.IRON_DOOR_OPEN, SoundSource.BLOCKS, .40F, 1.35F);
            }
        }
        else if (open && (gate.clearFor += 4) >= HOLD_TICKS)
        {
            gate.clearFor = 0;
            set(server, pos, state, false);
            level.playSound(null, pos, SoundEvents.IRON_DOOR_CLOSE, SoundSource.BLOCKS, .35F, 1.35F);
        }
    }

    private static void set(ServerLevel level, BlockPos pos, BlockState state, boolean open)
    {
        level.setBlock(pos, state.setValue(NervStaffGateR65.OPEN, open), 3);
        BlockPos up = pos.above();
        BlockState upper = level.getBlockState(up);
        if (upper.getBlock() instanceof NervStaffGateR65 && upper.getValue(NervStaffGateR65.HALF) == DoubleBlockHalf.UPPER)
        {
            level.setBlock(up, upper.setValue(NervStaffGateR65.OPEN, open), 3);
        }
    }
}

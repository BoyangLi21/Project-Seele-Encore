package com.projectseele.world;

import com.projectseele.entity.NervLiftDoorEntity;
import com.projectseele.registry.ModItems;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.AttachFace;
import net.minecraft.world.phys.Vec3;

import java.util.Collections;
import java.util.Map;
import java.util.WeakHashMap;

/** Five-wide staff checkpoint at the Tokyo-3 surface lift pavilion. */
public final class S20SurfaceAccessGate
{
    private static final int UPDATE =
            Block.UPDATE_CLIENTS | Block.UPDATE_KNOWN_SHAPE;
    private static final int GATE_X = S20SurfaceTransitDirector.AXIS_X - 14;
    private static final int Z_MIN = S20SurfaceTransitDirector.AXIS_Z - 2;
    private static final int Z_MAX = S20SurfaceTransitDirector.AXIS_Z + 2;
    private static final long OPEN_TICKS = 120L;
    private static final BlockState GATE =
            Blocks.BARRIER.defaultBlockState();
    private static final int VISUAL_DOOR_ID = 0x53414745;
    private static final Map<ServerLevel,Long> OPEN_UNTIL =
            Collections.synchronizedMap(new WeakHashMap<>());
    private static final Map<ServerLevel,Integer> GATE_AXES=new WeakHashMap<>();

    private static int gateX(ServerLevel level)
    {
        return GATE_AXES.computeIfAbsent(level,l->java.nio.file.Files.isRegularFile(
                l.getServer().getWorldPath(net.minecraft.world.level.storage.LevelResource.ROOT)
                        .resolve("surface_lift_access_r40.json"))?120:GATE_X);
    }

    private S20SurfaceAccessGate() {}

    public static void tick(ServerLevel level)
    {
        int walkY = S20PhysicalElevatorDirector.surfaceTransitLift(level)
                .upper().walkY();
        BlockPos reader = reader(level,walkY);
        if (!level.hasChunkAt(reader))
        {
            return;
        }
        if(level.getBlockEntity(reader) instanceof NervAccessReaderEntityR44)return;
        ensureReader(level, reader);
        ensureButton(level, insideButton(level,walkY), Direction.EAST);
        long now = level.getGameTime();
        boolean open = now < OPEN_UNTIL.getOrDefault(level, 0L);
        setOpen(level, walkY, open);
        NervLiftDoorEntity visual = NervLiftDoorEntity.reconcile(
                level, VISUAL_DOOR_ID, false, 5, 4,
                NervLiftDoorEntity.STYLE_NERV_BLACK,
                new Vec3(gateX(level) + 0.5D, walkY,
                        (Z_MIN + Z_MAX) * 0.5D + 0.5D));
        if (visual != null)
        {
            visual.setOpen(open);
        }
    }

    public static boolean handleUse(ServerPlayer player, BlockPos clicked)
    {
        ServerLevel level = player.serverLevel();
        int walkY = S20PhysicalElevatorDirector.surfaceTransitLift(level)
                .upper().walkY();
        if(level.getBlockEntity(reader(level,walkY)) instanceof NervAccessReaderEntityR44 upgraded)
        {
            // The physical inside button depresses normally; the reader ticks
            // its POWERED state. Do not swallow that use before ButtonBlock.
            return false;
        }
        if (clicked.equals(insideButton(level,walkY)))
        {
            OPEN_UNTIL.put(level, level.getGameTime() + OPEN_TICKS);
            setOpen(level, walkY, true);
            level.playSound(null, clicked, SoundEvents.IRON_DOOR_OPEN,
                    SoundSource.BLOCKS, 0.9F, 1.18F);
            return true;
        }
        if (!clicked.equals(reader(level,walkY)))
        {
            return false;
        }
        boolean employee = player.getMainHandItem().is(
                ModItems.NERV_EMPLOYEE_CARD.get())
                || player.getOffhandItem().is(
                ModItems.NERV_EMPLOYEE_CARD.get());
        boolean highest = player.getMainHandItem().is(
                ModItems.TERMINAL_DOGMA_ACCESS_CARD.get())
                || player.getOffhandItem().is(
                ModItems.TERMINAL_DOGMA_ACCESS_CARD.get());
        if (!employee && !highest)
        {
            player.displayClientMessage(Component.literal(
                    "ACCESS DENIED / NERV EMPLOYEE CARD REQUIRED")
                    .withStyle(ChatFormatting.RED), true);
            level.playSound(null, clicked, SoundEvents.IRON_DOOR_CLOSE,
                    SoundSource.BLOCKS, 0.9F, 0.72F);
            return true;
        }
        OPEN_UNTIL.put(level, level.getGameTime() + OPEN_TICKS);
        setOpen(level, walkY, true);
        player.displayClientMessage(Component.literal(
                "NERV STAFF ACCESS ACCEPTED")
                .withStyle(ChatFormatting.GREEN), true);
        level.playSound(null, clicked, SoundEvents.IRON_DOOR_OPEN,
                SoundSource.BLOCKS, 0.9F, 1.18F);
        return true;
    }

    private static BlockPos reader(ServerLevel level,int walkY)
    {
        return new BlockPos(gateX(level) - 1, walkY + 1, Z_MIN - 1);
    }

    private static BlockPos insideButton(ServerLevel level,int walkY)
    {
        return new BlockPos(gateX(level) + 1, walkY + 1, Z_MIN - 1);
    }

    private static void ensureReader(ServerLevel level, BlockPos position)
    {
        ensureButton(level, position, Direction.WEST);
    }

    private static void ensureButton(ServerLevel level, BlockPos position,
                                     Direction facing)
    {
        BlockState wanted = Blocks.POLISHED_BLACKSTONE_BUTTON
                .defaultBlockState()
                .setValue(ButtonBlock.FACE, AttachFace.WALL)
                .setValue(ButtonBlock.FACING, facing)
                .setValue(ButtonBlock.POWERED, false);
        BlockState current = level.getBlockState(position);
        if ((current.isAir()
                || current.is(Blocks.POLISHED_BLACKSTONE_BUTTON))
                && !current.equals(wanted))
        {
            level.setBlock(position, wanted, UPDATE);
        }
    }

    private static void setOpen(ServerLevel level, int walkY, boolean open)
    {
        BlockState wanted = open ? Blocks.AIR.defaultBlockState() : GATE;
        for (int y = walkY; y <= walkY + 3; y++)
        {
            for (int z = Z_MIN; z <= Z_MAX; z++)
            {
                BlockPos position = new BlockPos(gateX(level), y, z);
                BlockState current = level.getBlockState(position);
                // The audited R28 aperture is air. Once installed, this owner
                // only alternates its own full-collision glass and air; any human-authored
                // third state is left untouched.
                if ((current.isAir() || current.is(Blocks.IRON_BARS)
                        || current.is(Blocks.GRAY_STAINED_GLASS)
                        || current.is(Blocks.BLACK_CONCRETE)
                        || current.is(Blocks.BARRIER))
                        && !current.equals(wanted))
                {
                    level.setBlock(position, wanted, UPDATE);
                }
            }
        }
    }
}

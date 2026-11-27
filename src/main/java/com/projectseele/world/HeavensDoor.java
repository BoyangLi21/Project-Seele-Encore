package com.projectseele.world;

import com.projectseele.registry.ModBlocks;
import com.projectseele.registry.ModSounds;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.level.Level;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.AABB;

/** Two sliding leaves in the existing Terminal Dogma bulkhead. Width is recoverable from the saved blocks. */
public final class HeavensDoor
{
    private static final int WEST = 18, EAST = 42, WIDTH = EAST - WEST + 1;
    // The jambs are the pockets the leaves slide into: the outer two columns each side never open, and show the
    // leaf's red inner edge once it is fully retracted (the door's own geometry puts that edge at x 17 and 43).
    private static final int POCKET_WEST = WEST - 2, POCKET_EAST = EAST + 2;
    private static final int BOTTOM = -1230, TOP = -1202, NORTH = 258, SOUTH = 260;
    private static final int EVA_BOTTOM = -1264;
    private static final BlockPos EXTENSION = new BlockPos(16,-1265,258);
    private static int width, target;
    private static boolean moving;
    private static final int HINT_EVERY = 1200;
    private static final java.util.Map<java.util.UUID, Long> HINTED = new java.util.HashMap<>();

    private HeavensDoor() {}

    /** A click on a leaf, the frame, the lintel or one of the two plates. Pure geometry, so the client can use it too. */
    public static boolean controls(Level level, BlockPos hit)
    {
        if (!level.dimension().equals(FacilitySchemaV2.DIMENSION)
                || hit.getX() < WEST - 2 || hit.getX() > EAST + 2
                || hit.getY() < bottom(level) || hit.getY() > TOP + 3
                || hit.getZ() < NORTH - 1 || hit.getZ() > SOUTH + 1) return false;
        return hit.getZ() >= NORTH && hit.getZ() <= SOUTH || hit.getX() == 30 && hit.getY() == TOP + 3;
    }

    public static boolean use(ServerPlayer player, BlockPos hit)
    {
        ServerLevel level = player.serverLevel();
        if (player.isSpectator() || !controls(level, hit)) return false;
        // The basalt lintel marks an installed door; the jambs below it now move with the leaves.
        if (!loaded(level) || !level.getBlockState(new BlockPos(WEST, TOP + 2, NORTH)).is(Blocks.POLISHED_BASALT)
                || !level.getBlockState(new BlockPos(EAST, TOP + 2, SOUTH)).is(Blocks.POLISHED_BASALT)) return false;
        if (moving) target = target == WIDTH ? 0 : WIDTH;
        else
        {
            width = 0;
            for (int x = WEST; x <= EAST; x++)
                if (level.getBlockState(new BlockPos(x, TOP, NORTH)).isAir()) width++;
            target = width == WIDTH ? 0 : WIDTH;
        }
        moving = true;
        // Make the click read at once: the leaves take a few ticks to visibly move from where most people stand.
        player.displayClientMessage(Component.translatable(target == WIDTH ? "message.projectseele.heavens_door.opening"
                : "message.projectseele.heavens_door.closing"), true);
        sound(level, ModSounds.SURFACE_BULKHEAD_MOTION_R48.get());
        return true;
    }

    private static void sound(ServerLevel level, SoundEvent event)
    {
        level.playSound(null, 30.5, (BOTTOM + TOP) / 2.0, 259.5, event, SoundSource.BLOCKS, 1.6F, 0.7F);
    }

    public static void tick(ServerLevel level)
    {
        if (level.getGameTime() % 40 == 0) hint(level);
        if (level.getGameTime() % 10 == 0 && loaded(level) && bottom(level)==EVA_BOTTOM && (!moving || target==0))
        {
            var pilots=level.getEntitiesOfClass(com.projectseele.entity.EvaUnit01Entity.class,
                    new AABB(WEST,EVA_BOTTOM-3,NORTH-12,EAST+1,TOP+1,SOUTH+13),
                    eva -> eva.getControllingPassenger() instanceof net.minecraft.world.entity.player.Player);
            if (!pilots.isEmpty())
            {
                if (!moving)
                {
                    width=0;
                    for (int x=WEST;x<=EAST;x++)
                        if (level.getBlockState(new BlockPos(x,TOP,NORTH)).isAir()) width++;
                }
                if (width<WIDTH)
                {
                    target=WIDTH;
                    moving=true;
                    sound(level,ModSounds.SURFACE_BULKHEAD_MOTION_R48.get());
                }
            }
        }
        if (!moving || level.getGameTime() % 3 != 0) return;
        if (!loaded(level)) { moving = false; return; }
        int next = width + Integer.signum(target - width) * Math.min(2, Math.abs(target - width));
        // Like a door sensor: anyone in the opening, or a block in front of or behind it, sends the leaves back
        // open before they move, instead of letting them close right up to the body.
        if (next < width && width > 0)
        {
            int left = 30 - (width + 1) / 2, right = 31 + width / 2;
            if (!level.getEntities((Entity)null, new AABB(left + 1, bottom(level), NORTH - 1, right, TOP + 1, SOUTH + 2),
                    e -> !e.isSpectator() && e.isPickable()).isEmpty())
            {
                target = WIDTH;
                for (ServerPlayer near : level.getPlayers(p -> p.distanceToSqr(30.5, BOTTOM, 259.5) < 48 * 48))
                    near.displayClientMessage(Component.translatable("message.projectseele.heavens_door.held"), true);
                return;
            }
        }
        // Check the entire moving face before writing a step. A player modification leaves its surroundings intact.
        BlockPos.MutableBlockPos pos = new BlockPos.MutableBlockPos();
        for (int x = POCKET_WEST; x <= POCKET_EAST; x++)
            for (int y = bottom(level); y <= TOP; y++)
                for (int z = NORTH; z <= SOUTH; z++)
                    if (!level.getBlockState(pos.set(x, y, z)).is(material(x, y, z, width)))
                    {
                        moving = false;
                        return;
                    }
        for (int x = POCKET_WEST; x <= POCKET_EAST; x++)
            for (int y = bottom(level); y <= TOP; y++)
                for (int z = NORTH; z <= SOUTH; z++)
                {
                    Block to = material(x, y, z, next);
                    if (to != material(x, y, z, width)) level.setBlock(pos.set(x, y, z), to.defaultBlockState(), 2);
                }
        width = next;
        moving = width != target;
        if (!moving) sound(level, ModSounds.SURFACE_BULKHEAD_STOP_R48.get());
    }

    /** People walking up to the bulkhead are told it can be worked by hand: nothing on it looks like a switch. */
    private static void hint(ServerLevel level)
    {
        long now = level.getGameTime();
        for (ServerPlayer player : level.players())
        {
            if (player.isSpectator() || player.getX() < WEST - 4 || player.getX() > EAST + 5
                    || player.getY() < BOTTOM - 2 || player.getY() > TOP + 4
                    || player.getZ() < NORTH - 10 || player.getZ() > SOUTH + 11) continue;
            Long last = HINTED.get(player.getUUID());
            if (last != null && now - last < HINT_EVERY && now >= last) continue;
            HINTED.put(player.getUUID(), now);
            player.displayClientMessage(Component.translatable("message.projectseele.heavens_door.hint"), true);
        }
    }

    private static boolean loaded(ServerLevel level)
    {
        return level.hasChunkAt(new BlockPos(POCKET_WEST, TOP, NORTH)) && level.hasChunkAt(new BlockPos(POCKET_EAST, TOP, SOUTH));
    }

    private static int bottom(Level level)
    {
        return (!(level instanceof ServerLevel server) || DogmaInterlocks.released(server))
                && level.hasChunkAt(EXTENSION) && level.getBlockState(EXTENSION).is(Blocks.CHISELED_POLISHED_BLACKSTONE)
                ? EVA_BOTTOM : BOTTOM;
    }

    static void alignLowerLeaves(ServerLevel level)
    {
        int opening=0;
        for(int x=WEST;x<=EAST;x++) if(level.getBlockState(new BlockPos(x,TOP,NORTH)).isAir()) opening++;
        for(int x=POCKET_WEST;x<=POCKET_EAST;x++)
            for(int y=EVA_BOTTOM;y<BOTTOM;y++)
                for(int z=NORTH;z<=SOUTH;z++)
                    level.setBlock(new BlockPos(x,y,z),material(x,y,z,opening).defaultBlockState(),2);
    }

    private static Block material(int x, int y, int z, int opening)
    {
        if (y==-1231 && x>=18 && x<=20) return ModBlocks.NERV_FLOOR_PANEL.get();
        int left = 30 - (opening + 1) / 2, right = 31 + opening / 2;
        if (x > left && x < right) return Blocks.AIR;
        int templateX = x <= left ? x + 26 - left : x + 34 - right;
        if (templateX == 26 || templateX == 34) return Blocks.RED_CONCRETE;
        if (y >= -1217 && y <= -1215 || y >= -1249 && y <= -1247) return Blocks.BLACK_CONCRETE;
        if ((z == NORTH || z == SOUTH) && (y == -1227 || y == -1206 || y == -1261 || y == -1241)
                && (templateX == 20 || templateX == 24 || templateX == 36 || templateX == 40)) return Blocks.IRON_BLOCK;
        return ModBlocks.NERV_STRUCTURAL_PANEL.get();
    }

    public static void reset() { moving = false; HINTED.clear(); }
}

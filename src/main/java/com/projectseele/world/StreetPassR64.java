package com.projectseele.world;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.network.ClientboundStreetPassR64;
import com.projectseele.network.SeeleNetwork;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.entity.player.PlayerEvent;
import net.minecraftforge.event.server.ServerStoppedEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.network.PacketDistributor;

/**
 * Street furniture a giant walks through (R64): the cells listed in the world's street_pass_r64.json, made with
 * tools/street_pass_cells.py from the map's own lists (utility poles and their wires, transformer boxes, sirens,
 * shelter kiosks, traffic lights, and a few small things on an Angel's route). A Unit or an Angel does not collide
 * with them at any height; people, vehicles and everything else do. Nothing in the world is changed.
 *
 * Without it a Unit steps onto a pole (its step is 21) and is then held on the wires about seven blocks above the
 * street: EvaObstacleCollision lets it through thin things only within 1.75 of its feet, and that band moves with
 * the feet, so the same pole is solid one tick and passable the next. An Angel steps only two and is stopped.
 *
 * A listed cell counts only while it holds one of the blocks the file lists, so a cell the map later builds over
 * becomes solid again. A piloted Unit moves on its pilot's client, so the server sends the list to each player as
 * they come into a level.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class StreetPassR64
{
    public static final String FILE = "street_pass_r64.json";
    public static final String SCHEMA = "projectseele.r64.street-pass.v1";

    private record Table(StreetPassCellsR64 cells, Set<Block> blocks, List<String> names)
    {
        static final Table NONE = new Table(StreetPassCellsR64.EMPTY, Set.of(), List.of());

        boolean passes(BlockPos pos, BlockState state)
        {
            return !cells.isEmpty() && cells.contains(pos.getX(), pos.getY(), pos.getZ()) && blocks.contains(state.getBlock());
        }
    }

    // Read by every collision sweep; the levels are let go when the server stops.
    private static final Map<ServerLevel, Table> SERVER = new ConcurrentHashMap<>();
    // The client's own level: written on the client's main thread when the list arrives, read by its collision and
    // its drawing of the feet.
    private static volatile ResourceKey<Level> clientDimension;
    private static volatile Table clientTable = Table.NONE;

    private StreetPassR64()
    {
    }

    /** Whether a giant moving in this level passes through the block at pos. */
    public static boolean passes(Level level, BlockPos pos, BlockState state)
    {
        if (level instanceof ServerLevel server) return server(server).passes(pos, state);
        Table table = clientTable;
        return level.isClientSide && table != Table.NONE && level.dimension().equals(clientDimension) && table.passes(pos, state);
    }

    public static int size(ServerLevel level)
    {
        return server(level).cells().size();
    }

    private static Table server(ServerLevel level)
    {
        Table table = SERVER.get(level);
        return table != null ? table : SERVER.computeIfAbsent(level, StreetPassR64::load);
    }

    private static Table load(ServerLevel level)
    {
        Path file = level.getServer().getWorldPath(LevelResource.ROOT).resolve(FILE);
        if (!Files.isRegularFile(file)) return Table.NONE;
        try
        {
            JsonObject root = JsonParser.parseString(Files.readString(file)).getAsJsonObject();
            if (!SCHEMA.equals(root.get("schema").getAsString()))
                throw new IllegalStateException("schema " + root.get("schema").getAsString());
            if (!level.dimension().location().toString().equals(root.get("dimension").getAsString())) return Table.NONE;
            List<String> names = new ArrayList<>();
            for (var name : root.getAsJsonArray("blocks")) names.add(name.getAsString());
            var array = root.getAsJsonArray("cells");
            int[] xyz = new int[array.size()];
            for (int i = 0; i < xyz.length; i++) xyz[i] = array.get(i).getAsInt();
            Table table = new Table(StreetPassCellsR64.of(xyz), blocks(names), List.copyOf(names));
            ProjectSeele.LOGGER.info("R64 STREET PASS {} cells in {} sections, {} kinds of block, level {}", table.cells().size(), table.cells().sections(),
                    table.blocks().size(), level.dimension().location());
            return table;
        }
        catch (Exception failure)
        {
            // A broken list is not a reason to let giants through anything: they collide as before.
            ProjectSeele.LOGGER.error("R64 street pass list {} unreadable; giants collide with everything", file, failure);
            return Table.NONE;
        }
    }

    private static Set<Block> blocks(List<String> names)
    {
        Set<Block> blocks = Collections.newSetFromMap(new IdentityHashMap<>());
        for (String name : names)
        {
            ResourceLocation id = ResourceLocation.tryParse(name);
            Block block = id == null ? Blocks.AIR : BuiltInRegistries.BLOCK.get(id);
            // An unknown name maps to air in the registry; air never collides, so it is simply left out.
            if (block != Blocks.AIR) blocks.add(block);
        }
        return blocks;
    }

    private static void send(ServerPlayer player)
    {
        ServerLevel level = player.serverLevel();
        Table table = server(level);
        byte[] cells = table.cells().encode();
        if (cells.length > StreetPassCellsR64.MAX_ENCODED)
        {
            ProjectSeele.LOGGER.error("R64 street pass list of {} cells is {} bytes, too large to send; {}'s client keeps colliding", table.cells().size(),
                    cells.length, player.getGameProfile().getName());
            cells = new byte[0];
        }
        SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(() -> player),
                new ClientboundStreetPassR64(level.dimension().location(), table.names(), cells));
    }

    /** Client main thread: the list for the level the player is now in. */
    public static void receive(ResourceLocation dimension, List<String> names, byte[] cells)
    {
        StreetPassCellsR64 set;
        try
        {
            set = StreetPassCellsR64.decode(cells);
        }
        catch (IllegalArgumentException failure)
        {
            ProjectSeele.LOGGER.error("R64 street pass list from the server unreadable", failure);
            set = StreetPassCellsR64.EMPTY;
        }
        clientDimension = ResourceKey.create(Registries.DIMENSION, dimension);
        clientTable = set.isEmpty() ? Table.NONE : new Table(set, blocks(names), List.copyOf(names));
        if (!set.isEmpty()) ProjectSeele.LOGGER.info("R64 STREET PASS client {} cells for {}", set.size(), dimension);
    }

    @SubscribeEvent
    public static void loggedIn(PlayerEvent.PlayerLoggedInEvent event)
    {
        if (event.getEntity() instanceof ServerPlayer player) send(player);
    }

    @SubscribeEvent
    public static void changedLevel(PlayerEvent.PlayerChangedDimensionEvent event)
    {
        if (event.getEntity() instanceof ServerPlayer player) send(player);
    }

    @SubscribeEvent
    public static void respawned(PlayerEvent.PlayerRespawnEvent event)
    {
        if (event.getEntity() instanceof ServerPlayer player) send(player);
    }

    @SubscribeEvent
    public static void stopped(ServerStoppedEvent event)
    {
        SERVER.clear();
    }
}

package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.block.state.properties.AttachFace;
import net.minecraft.world.level.storage.LevelResource;

import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.WeakHashMap;

/** Installed, physically reachable wet-cage controls; no automatic map writer. */
public final class HangarOperationsR44
{
    public enum Action { PREPARE, STATUS, CANCEL }
    public record Control(int variant, Action action, BlockPos position) {}

    private static final String MANIFEST = "r44_hangar_operator_interfaces.json";
    private static final Map<MinecraftServer, List<Control>> INSTALLED = new WeakHashMap<>();

    public static Optional<Control> match(ServerLevel level, BlockPos clicked)
    {
        if (!level.dimension().equals(FacilitySchemaV2.DIMENSION))
        {
            return Optional.empty();
        }
        for (Control control : INSTALLED.computeIfAbsent(level.getServer(),
                HangarOperationsR44::load))
        {
            if (!control.position().equals(clicked))
            {
                continue;
            }
            BlockPos back = clicked.west();
            if (!level.hasChunkAt(back))
            {
                return Optional.empty();
            }
            var state = level.getBlockState(clicked);
            if (!state.is(Blocks.POLISHED_BLACKSTONE_BUTTON)
                    || state.getValue(ButtonBlock.FACE) != AttachFace.WALL
                    || state.getValue(ButtonBlock.FACING) != Direction.EAST
                    || !level.getBlockState(back).isFaceSturdy(
                            level, back, Direction.EAST))
            {
                return Optional.empty();
            }
            return Optional.of(control);
        }
        return Optional.empty();
    }

    private static List<Control> load(MinecraftServer server)
    {
        var path = server.getWorldPath(LevelResource.ROOT).resolve(MANIFEST);
        if (!Files.isRegularFile(path))
        {
            return List.of();
        }
        try
        {
            var document = JsonParser.parseString(Files.readString(path)).getAsJsonObject();
            if (document.get("schema").getAsInt() != 44
                    || !document.get("dimension").getAsString().equals("projectseele:geofront"))
            {
                throw new IllegalArgumentException("Wrong installed hangar control contract");
            }
            var result = new ArrayList<Control>();
            for (var entry : document.getAsJsonArray("controls"))
            {
                var row = entry.getAsJsonObject();
                int variant = row.get("variant").getAsInt();
                Action action = Action.valueOf(row.get("action").getAsString());
                var point = row.getAsJsonArray("position");
                if (variant < 0 || variant > 2 || point.size() != 3)
                {
                    throw new IllegalArgumentException("Invalid hangar control identity");
                }
                BlockPos position = new BlockPos(point.get(0).getAsInt(),
                        point.get(1).getAsInt(), point.get(2).getAsInt());
                int cx = new int[] {-12, 30, 72}[variant];
                BlockPos expected = new BlockPos(cx - 19, -393,
                        -254 + 2 * action.ordinal());
                if (!position.equals(expected)
                        || result.stream().anyMatch(c -> c.position().equals(position)))
                {
                    throw new IllegalArgumentException("Control differs from the measured work-layer interface");
                }
                result.add(new Control(variant, action, position));
            }
            if (result.size() != 9)
            {
                throw new IllegalArgumentException("All three actual wet-cage controls are required per bay");
            }
            return List.copyOf(result);
        }
        catch (Exception failure)
        {
            ProjectSeele.LOGGER.error("Installed R44 hangar controls unavailable; no replacement or automatic operation", failure);
            return List.of();
        }
    }

    private HangarOperationsR44() {}
}

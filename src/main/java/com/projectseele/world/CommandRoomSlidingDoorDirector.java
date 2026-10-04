package com.projectseele.world;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervSlidingDoorEntity;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Runtime owner for the reviewed 3x2 command-room sliding doors. */
public final class CommandRoomSlidingDoorDirector
{
    public static final String MARKER =
            ".projectseele_command_sliding_doors_r01.json";
    private static final Map<MinecraftServer, CachedConfig> CONFIG =
            new WeakHashMap<>();
    private static final Map<ServerLevel, Set<Integer>> OWNERSHIP_FAULTS = new WeakHashMap<>();
    private static final Map<ServerLevel,Map<Integer,Long>> PENDING_OPEN=new WeakHashMap<>();
    private static final List<DoorSpec> DOORS = List.of(
            door(0, 8, -429, 282, Direction.NORTH),
            door(1, 13, -429, 282, Direction.NORTH),
            door(2, 43, -429, 282, Direction.NORTH),
            door(3, 48, -429, 282, Direction.NORTH),
            door(4, 28, -424, 286, Direction.SOUTH),
            door(5, 24, -423, 254, Direction.WEST),
            door(6, 11, -423, 268, Direction.NORTH),
            door(7, 17, -423, 268, Direction.NORTH),
            door(8, 39, -423, 268, Direction.NORTH),
            door(9, 45, -423, 268, Direction.NORTH),
            door(10, 20, -423, 278, Direction.EAST),
            door(11, 36, -423, 278, Direction.EAST),
            door(12, 21, -422, 283, Direction.NORTH),
            door(13, 35, -422, 283, Direction.NORTH),
            door(14, 24, -418, 254, Direction.WEST),
            door(15, 28, -413, 284, Direction.SOUTH),
            door(16, 24, -409, 270, Direction.NORTH),
            door(17, 32, -409, 270, Direction.NORTH),
            door(18, 28, -406, 272, Direction.NORTH));

    private CommandRoomSlidingDoorDirector() {}

    private static DoorSpec door(int id, int x, int y, int z,
                                 Direction facing)
    {
        return new DoorSpec(id, new BlockPos(x, y, z), facing);
    }

    public static void tick(ServerLevel level)
    {
        if (!enabled(level) || level.getGameTime() % 2L != 0L)
        {
            return;
        }
        for (DoorSpec spec : DOORS)
        {
            if (!config(level).doorIds().contains(spec.id()))
            {
                continue;
            }
            if (!level.hasChunkAt(spec.lower())||!level.isPositionEntityTicking(spec.lower()))
            {
                continue;
            }
            if (!ownedAperture(level, spec)) continue;
            NervSlidingDoorEntity door = NervSlidingDoorEntity.reconcile(
                    level, spec.id(), spec.axisX(), spec.centre());
            var pending=PENDING_OPEN.get(level);
            if(door!=null&&pending!=null&&pending.containsKey(spec.id()))
            {
                long until=pending.remove(spec.id());if(until>=level.getGameTime())door.requestOpen();
            }
            if (door != null && spec.redstonePowered(level))
            {
                door.requestRedstoneOpen();
            }
            if(door!=null&&spec.id()==18&&!level.getEntitiesOfClass(ServerPlayer.class,spec.apertureBounds().inflate(2.2,.15,2.2),p->!p.isSpectator()).isEmpty())
                door.requestRedstoneOpen();
        }
    }

    public static boolean handleUse(ServerPlayer player, BlockPos position)
    {
        ServerLevel level = player.serverLevel();
        if (!enabled(level)
                || !(level.getBlockState(position).getBlock()
                instanceof ButtonBlock))
        {
            return false;
        }
        Integer doorId = config(level).buttons().get(position);
        DoorSpec spec = doorId == null ? null : spec(doorId);
        if (spec == null)
        {
            return false;
        }
        var input = level.getBlockState(position);
        if (!ownedAperture(level, spec) || !input.canSurvive(level, position)
                || !fixedInputReady(level, position)
                || spec.aperture().contains(position)) return false;
        if (input.hasProperty(net.minecraft.world.level.block.state.properties.BlockStateProperties.ATTACH_FACE))
        {
            var face = input.getValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.ATTACH_FACE);
            BlockPos support = switch (face)
            {
                case FLOOR -> position.below();
                case CEILING -> position.above();
                case WALL -> position.relative(input.getValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.HORIZONTAL_FACING).getOpposite());
            };
            if (spec.aperture().contains(support) || level.getBlockState(support).is(Blocks.BARRIER)) return false;
        }
        // Block data can arrive before the non-saving door entity can tick.
        // Retain the press across that attachment boundary instead of losing it.
        PENDING_OPEN.computeIfAbsent(level,l->new HashMap<>()).put(spec.id(),level.getGameTime()+200);
        if(!level.isPositionEntityTicking(spec.lower()))return true;
        NervSlidingDoorEntity door = NervSlidingDoorEntity.reconcile(
                level, spec.id(), spec.axisX(), spec.centre());
        if (door == null)
        {
            return false;
        }
        door.requestOpen();
        return true;
    }

    private static boolean fixedInputReady(ServerLevel level, BlockPos position)
    {
        FixedInput contract = config(level).fixedInputs().get(position);
        if (contract == null) return true;
        var input = level.getBlockState(position);
        return level.hasChunkAt(contract.support())
                && input.getBlock() instanceof ButtonBlock
                && input.canSurvive(level, position)
                && level.getBlockEntity(position) == null
                && level.getBlockEntity(contract.support()) == null
                && BlockStateParser.serialize(input).replace("powered=true", "powered=false")
                    .equals(contract.state().replace("powered=true", "powered=false"))
                && BlockStateParser.serialize(level.getBlockState(contract.support())).equals(contract.supportState());
    }

    public static void maintainCollision(ServerLevel level, int doorId,
                                         boolean closed)
    {
        DoorSpec spec = spec(doorId);
        if (spec == null || !enabled(level) || !config(level).doorIds().contains(doorId)
                || !level.hasChunkAt(spec.lower()) || !ownedAperture(level, spec))
        {
            return;
        }
        for (BlockPos position : spec.aperture())
        {
            if (closed)
            {
                if (level.getBlockState(position).isAir())
                {
                    level.setBlock(position, Blocks.BARRIER.defaultBlockState(),
                            net.minecraft.world.level.block.Block.UPDATE_CLIENTS);
                }
            }
            else if (level.getBlockState(position).is(Blocks.BARRIER))
            {
                level.setBlock(position, Blocks.AIR.defaultBlockState(),
                        net.minecraft.world.level.block.Block.UPDATE_CLIENTS);
            }
        }
    }
    private static boolean ownedAperture(ServerLevel level, DoorSpec spec)
    {
        for (BlockPos position : spec.aperture())
        {
            var state = level.getBlockState(position);
            if (!level.hasChunkAt(position) || level.getBlockEntity(position) != null
                    || !state.isAir() && !state.is(Blocks.BARRIER))
            {
                if (OWNERSHIP_FAULTS.computeIfAbsent(level, ignored -> new HashSet<>()).add(spec.id()))
                    ProjectSeele.LOGGER.warn("Command door {} held at foreign complete state/NBT {}; no partial aperture writes", spec.id(), position);
                return false;
            }
        }
        var faults = OWNERSHIP_FAULTS.get(level);
        if (faults != null) faults.remove(spec.id());
        return true;
    }
    public static boolean passageReady(ServerLevel level,BlockPos button)
    {
        Integer id=config(level).buttons().get(button);DoorSpec spec=id==null?null:spec(id);
        if(spec==null||!enabled(level)||!config(level).doorIds().contains(id)
                ||!level.isPositionEntityTicking(spec.lower())||!ownedAperture(level,spec))return false;
        var door=level.getEntitiesOfClass(NervSlidingDoorEntity.class,spec.apertureBounds().inflate(3),e->e.getDoorId()==id)
                .stream().min(java.util.Comparator.comparingInt(Entity::getId)).orElse(null);
        if(door==null||door.getOpenProgress(1)<.82)return false;
        return spec.aperture().stream().allMatch(p->level.getBlockState(p).getCollisionShape(level,p).isEmpty());
    }

    public static boolean apertureOccupied(ServerLevel level, int doorId)
    {
        DoorSpec spec = spec(doorId);
        if (spec == null)
        {
            return false;
        }
        return !level.getEntities((Entity)null, spec.apertureBounds(),
                entity -> entity.isAlive()
                        && !(entity instanceof NervSlidingDoorEntity)).isEmpty();
    }

    public static void resetRuntime()
    {
        synchronized (CONFIG)
        {
            CONFIG.clear();
            PENDING_OPEN.clear();
            OWNERSHIP_FAULTS.clear();
        }
    }

    private static DoorSpec spec(int id)
    {
        return id >= 0 && id < DOORS.size() ? DOORS.get(id) : null;
    }

    private static boolean enabled(ServerLevel level)
    {
        if (level.dimension() != FacilitySchemaV2.DIMENSION)
        {
            return false;
        }
        MinecraftServer server = level.getServer();
        return config(level).enabled();
    }

    private static RuntimeConfig config(ServerLevel level)
    {
        MinecraftServer server = level.getServer();
        synchronized (CONFIG)
        {
            int tick = server.getTickCount();
            CachedConfig cached = CONFIG.get(server);
            if (cached != null && tick >= cached.tick() && tick - cached.tick() < 20) return cached.value();
            Path marker = server.getWorldPath(LevelResource.ROOT).resolve(MARKER);
            RuntimeConfig value = new RuntimeConfig(false, Map.of(), Set.of(), Map.of());
            String digest = "missing";
            try
            {
                if (Files.isRegularFile(marker))
                {
                    byte[] bytes = Files.readAllBytes(marker);
                    digest = java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes));
                    if (cached != null && cached.digest().equals(digest))
                    {
                        CONFIG.put(server, new CachedConfig(tick, digest, cached.value()));
                        return cached.value();
                    }
                    JsonObject root = JsonParser.parseString(
                            new String(bytes, java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
                    Map<BlockPos, Integer> buttons = new HashMap<>();
                    Set<Integer> doorIds = new HashSet<>();
                    Map<BlockPos, FixedInput> fixedInputs = new HashMap<>();
                    Set<BlockPos> excluded = new HashSet<>();
                    if (root.has("excludedOriginalDoors"))
                        for (JsonElement element : root.getAsJsonArray("excludedOriginalDoors"))
                            if (!excluded.add(markerPosition(element.getAsJsonObject().getAsJsonArray("lower"))))
                                throw new IllegalArgumentException("Duplicate retired original door");
                    if (!excluded.equals(Set.of(DOORS.get(5).lower(), DOORS.get(14).lower())))
                        throw new IllegalArgumentException("Both complete original shaft doors must remain retired from sliding ownership");
                    JsonArray doors = root.getAsJsonArray("doors");
                    if (doors == null) throw new IllegalArgumentException("Complete command-door array is missing");
                    for (JsonElement element : doors)
                    {
                        JsonObject door = element.getAsJsonObject();
                        int id = door.get("id").getAsInt();
                        DoorSpec spec = spec(id);
                        if (spec == null || !doorIds.add(id) || excluded.contains(spec.lower())
                                || !markerPosition(door.getAsJsonArray("lower")).equals(spec.lower())
                                || !door.get("facing").getAsString().equals(spec.facing().getName())
                                || !door.get("axis").getAsString().equals(spec.axisX() ? "x" : "z"))
                            throw new IllegalArgumentException("Foreign, duplicate or retired command-door owner: " + id);
                        Set<BlockPos> aperture = new HashSet<>();
                        for (JsonElement cell : door.getAsJsonArray("aperture"))
                            if (!aperture.add(markerPosition(cell.getAsJsonArray())))
                                throw new IllegalArgumentException("Duplicate command-door aperture cell: " + id);
                        if (!aperture.equals(Set.copyOf(spec.aperture())))
                            throw new IllegalArgumentException("Full command-door aperture differs from its source owner: " + id);
                        for (JsonElement buttonElement : door.getAsJsonArray("buttons"))
                        {
                            BlockPos button = markerPosition(buttonElement.getAsJsonArray());
                            if (spec.aperture().contains(button)
                                    || Math.abs(button.getX() - spec.lower().getX()) > 8
                                    || Math.abs(button.getZ() - spec.lower().getZ()) > 8
                                    || button.getY() < spec.lower().getY() - 1 || button.getY() > spec.lower().getY() + 4
                                    || buttons.putIfAbsent(button, id) != null)
                                throw new IllegalArgumentException("Foreign, moving-mask or duplicate command input: " + button);
                        }
                        if (door.has("fixedInputContractsR45"))
                        {
                            Set<BlockPos> declared = new HashSet<>();
                            Set<Integer> sides = new HashSet<>();
                            for (JsonElement inputElement : door.getAsJsonArray("fixedInputContractsR45"))
                            {
                                JsonObject input = inputElement.getAsJsonObject();
                                BlockPos position = markerPosition(input.getAsJsonArray("pos"));
                                JsonObject supportImage = input.getAsJsonObject("fixed_support");
                                BlockPos support = markerPosition(supportImage.getAsJsonArray("pos"));
                                Direction facing = Direction.byName(input.get("facing").getAsString());
                                int side = input.get("side").getAsInt();
                                int normalOffset = (position.getX() - spec.lower().getX()) * spec.facing().getStepX()
                                        + (position.getZ() - spec.lower().getZ()) * spec.facing().getStepZ();
                                if (!Integer.valueOf(id).equals(buttons.get(position)) || !declared.add(position)
                                        || facing == null || facing.getAxis() == Direction.Axis.Y
                                        || !support.equals(position.relative(facing.getOpposite()))
                                        || side != 1 && side != -1 || normalOffset * side <= 0
                                        || !supportImage.get("full_nbt").isJsonNull()
                                        || DOORS.stream().anyMatch(owner -> owner.aperture().contains(support)))
                                    throw new IllegalArgumentException("Foreign complete fixed input/support contract: " + position);
                                sides.add(side);
                                FixedInput fixed = new FixedInput(input.get("state_after").getAsString(),
                                        support, supportImage.get("state").getAsString());
                                if (fixedInputs.putIfAbsent(position, fixed) != null)
                                    throw new IllegalArgumentException("Duplicate fixed input contract: " + position);
                            }
                            Set<BlockPos> actualButtons = new HashSet<>();
                            for (JsonElement buttonElement : door.getAsJsonArray("buttons"))
                                actualButtons.add(markerPosition(buttonElement.getAsJsonArray()));
                            if (!declared.equals(actualButtons) || !sides.equals(Set.of(-1, 1)))
                                throw new IllegalArgumentException("Incomplete fixed input contract on both normal sides: " + id);
                        }
                    }
                    Set<Integer> expectedIds = new HashSet<>();
                    for (DoorSpec owner : DOORS)
                        if (!excluded.contains(owner.lower())) expectedIds.add(owner.id());
                    if (!doorIds.equals(expectedIds))
                        throw new IllegalArgumentException("Incomplete reviewed command-door owner set");
                    if (!fixedInputs.isEmpty() && !fixedInputs.keySet().equals(buttons.keySet()))
                        throw new IllegalArgumentException("Mixed legacy and partial complete fixed-input ownership");
                    ProjectSeele.LOGGER.info(
                            "NERV command-room sliding doors enabled: count={} buttons={}",
                            doorIds.size(), buttons.size());
                    value = new RuntimeConfig(true, Map.copyOf(buttons),
                            Set.copyOf(doorIds), Map.copyOf(fixedInputs));
                }
            }
            catch (Exception exception)
            {
                ProjectSeele.LOGGER.error("Cannot read complete command-room sliding door marker {}; keep actual full states and NBT", marker, exception);
            }
            CONFIG.put(server, new CachedConfig(tick, digest, value));
            return value;
        }
    }

    private static BlockPos markerPosition(JsonArray value)
    {
        if (value == null || value.size() != 3) throw new IllegalArgumentException("An exact command-door position requires three coordinates");
        int[] xyz = new int[3];
        for (int i = 0; i < 3; i++)
        {
            double number = value.get(i).getAsDouble();
            if (!Double.isFinite(number) || number != Math.rint(number) || number < Integer.MIN_VALUE || number > Integer.MAX_VALUE)
                throw new IllegalArgumentException("Non-integral command-door coordinate");
            xyz[i] = (int)number;
        }
        return new BlockPos(xyz[0], xyz[1], xyz[2]);
    }

    private record DoorSpec(int id, BlockPos lower, Direction facing)
    {
        boolean axisX()
        {
            return this.facing.getAxis() == Direction.Axis.Z;
        }

        Vec3 centre()
        {
            return new Vec3(this.lower.getX() + 0.5D,
                    this.lower.getY(), this.lower.getZ() + 0.5D);
        }

        List<BlockPos> aperture()
        {
            java.util.ArrayList<BlockPos> result = new java.util.ArrayList<>(6);
            for (int vertical = 0; vertical < 2; vertical++)
            {
                for (int width = -1; width <= 1; width++)
                {
                    result.add(this.axisX()
                            ? this.lower.offset(width, vertical, 0)
                            : this.lower.offset(0, vertical, width));
                }
            }
            return result;
        }

        AABB apertureBounds()
        {
            if (this.axisX())
            {
                return new AABB(this.lower.getX() - 1.0D,
                        this.lower.getY(), this.lower.getZ(),
                        this.lower.getX() + 2.0D,
                        this.lower.getY() + 2.0D,
                        this.lower.getZ() + 1.0D);
            }
            return new AABB(this.lower.getX(), this.lower.getY(),
                    this.lower.getZ() - 1.0D,
                    this.lower.getX() + 1.0D,
                    this.lower.getY() + 2.0D,
                    this.lower.getZ() + 2.0D);
        }

        boolean redstonePowered(ServerLevel level)
        {
            RuntimeConfig current = config(level);
            if (!current.fixedInputs().isEmpty())
            {
                // New owner contracts bind redstone to the actual fixed input.
                // A foreign replacement or an unrelated nearby circuit cannot
                // impersonate a reviewed command-door button.
                for (var entry : current.buttons().entrySet())
                {
                    BlockPos position = entry.getKey();
                    if (entry.getValue() != this.id || !fixedInputReady(level, position)) continue;
                    var state = level.getBlockState(position);
                    if (state.hasProperty(net.minecraft.world.level.block.state.properties.BlockStateProperties.POWERED)
                            && state.getValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.POWERED)) return true;
                }
                return false;
            }
            for (int vertical = 0; vertical <= 2; vertical++)
            {
                for (int width = -4; width <= 4; width++)
                {
                    BlockPos sensor = this.axisX()
                            ? this.lower.offset(width, vertical, 0)
                            : this.lower.offset(0, vertical, width);
                    if (level.hasNeighborSignal(sensor))
                    {
                        return true;
                    }
                }
            }
            return false;
        }
    }

    private record RuntimeConfig(boolean enabled,
                                 Map<BlockPos, Integer> buttons,
                                 Set<Integer> doorIds,
                                 Map<BlockPos, FixedInput> fixedInputs) {}
    private record FixedInput(String state, BlockPos support, String supportState) {}
    private record CachedConfig(int tick, String digest, RuntimeConfig value) {}
}

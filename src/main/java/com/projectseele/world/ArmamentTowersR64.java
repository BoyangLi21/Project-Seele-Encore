package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.NervArmamentStationEntity;
import com.projectseele.registry.ModEntities;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.WeakHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.server.ServerStoppingEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * The spare-weapon towers of Tokyo-3 (the A-1 armament buildings): one armament station per tower, bound to it.
 *
 * <p>The towers come from {@code r64_armament_towers.json} in the world's root; without that file nothing here
 * runs. A tower hands out its rifle through its door while the city is raised and through the lot's hatch while
 * the city is lowered, and does neither while the city moves: a call made then is kept until the city rests.</p>
 *
 * <p>The door and the hatch are real blocks while shut. A run takes them out once and puts them back once. What
 * was taken is written to disk before the first block goes, so a save, a stop or a crash with a door open leaves
 * the means to put it back; a run itself never outlives a reload. The city lift checks the hatch and scans the
 * building when a trip begins, so a trip waits until every tower is in and its blocks are back.</p>
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class ArmamentTowersR64
{
    private static final String FILE = "r64_armament_towers.json";
    private static final String SCHEMA = "projectseele.r64.armament-towers.v1";
    private static final String DATA = "projectseele_armament_towers_r64";
    /** To clients, and no shape updates: the neighbours of a door must be the same blocks after it as before. */
    private static final int SWAP = Block.UPDATE_CLIENTS | Block.UPDATE_KNOWN_SHAPE;

    private record Plan(int tower, int facing) {}
    private record Table(List<Plan> towers, ArmamentTowerLogicR64.Door door, int bayDepth)
    {
        static final Table EMPTY = new Table(List.of(), new ArmamentTowerLogicR64.Door(15, 38, 1), 5);
    }
    private record Site(BlockPos centre, int height) {}
    private record City(long tick, int mode, boolean waiting) {}

    private static final Map<ServerLevel, Table> TABLES = new WeakHashMap<>();
    private static final Map<ServerLevel, Map<Integer, Site>> SITES = new WeakHashMap<>();
    private static final Map<ServerLevel, City> CITY = new WeakHashMap<>();
    private static final Map<ServerLevel, Map<Integer, Long>> REFUSED = new WeakHashMap<>();

    public static final class State extends SavedData
    {
        final Map<Integer, UUID> stations = new HashMap<>();
        /** Per tower, the blocks a run has out: position and exact state. */
        final Map<Integer, ListTag> out = new HashMap<>();
        /** Towers called while they could not start: the city was moving, or they were on their way in. */
        final Set<Integer> wanted = new HashSet<>();

        public static State load(CompoundTag tag)
        {
            State state = new State();
            CompoundTag stations = tag.getCompound("Stations");
            for (String name : stations.getAllKeys()) if (stations.hasUUID(name)) state.stations.put(Integer.parseInt(name), stations.getUUID(name));
            CompoundTag out = tag.getCompound("Out");
            for (String name : out.getAllKeys()) state.out.put(Integer.parseInt(name), out.getList(name, Tag.TAG_COMPOUND));
            for (int tower : tag.getIntArray("Wanted")) state.wanted.add(tower);
            return state;
        }

        @Override public CompoundTag save(CompoundTag tag)
        {
            CompoundTag names = new CompoundTag();
            stations.forEach((tower, id) -> names.putUUID(Integer.toString(tower), id));
            tag.put("Stations", names);
            CompoundTag taken = new CompoundTag();
            out.forEach((tower, cells) -> taken.put(Integer.toString(tower), cells));
            tag.put("Out", taken);
            tag.putIntArray("Wanted", wanted.stream().mapToInt(Integer::intValue).sorted().toArray());
            return tag;
        }
    }

    private static State state(ServerLevel level)
    {
        return level.getDataStorage().computeIfAbsent(State::load, State::new, DATA);
    }

    private static Table table(ServerLevel level)
    {
        return TABLES.computeIfAbsent(level, world ->
        {
            if (!world.dimension().location().toString().equals("projectseele:geofront")) return Table.EMPTY;
            var file = world.getServer().getWorldPath(LevelResource.ROOT).resolve(FILE);
            if (!Files.isRegularFile(file)) return Table.EMPTY;
            try
            {
                var data = JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                if (!SCHEMA.equals(data.get("schema").getAsString())) throw new IllegalStateException("Unknown armament tower table");
                var door = data.getAsJsonObject("door");
                var shape = new ArmamentTowerLogicR64.Door(door.get("width").getAsInt(), door.get("height").getAsInt(), door.get("bottom").getAsInt());
                int bay = data.get("bay_depth").getAsInt();
                if (bay < 1 || bay > ArmamentTowerLogicR64.HALF - 2) throw new IllegalStateException("The weapon bay must fit between the wall and the core");
                List<Plan> towers = new ArrayList<>();
                for (var value : data.getAsJsonArray("towers"))
                {
                    var row = value.getAsJsonObject();
                    int facing = switch (row.get("facing").getAsString())
                    {
                        case "south" -> 0;
                        case "west" -> 1;
                        case "north" -> 2;
                        case "east" -> 3;
                        default -> throw new IllegalStateException("A door faces south, west, north or east");
                    };
                    towers.add(new Plan(row.get("tower").getAsInt(), facing));
                }
                return new Table(List.copyOf(towers), shape, bay);
            }
            catch (Exception error)
            {
                ProjectSeele.LOGGER.error("Armament tower table {} is not usable; no tower is armed", file, error);
                return Table.EMPTY;
            }
        });
    }

    /** The lot of a planned tower from the city's own table; null until the city is installed, or if the lot is not 19 by 19. */
    private static Site site(ServerLevel level, int index)
    {
        Map<Integer, Site> known = SITES.computeIfAbsent(level, world -> new HashMap<>());
        Site site = known.get(index);
        if (site != null) return site;
        try
        {
            var towers = CityRigidTopologyR45.towers(level, IntegratedNervMapBuilder.tokyo3Origin(level));
            if (index < 0 || index >= towers.size()) return null;
            var tower = towers.get(index);
            int half = ArmamentTowerLogicR64.HALF;
            if (tower.minX() != -half || tower.maxX() != half || tower.minZ() != -half || tower.maxZ() != half)
            {
                refuse(level, index, "its lot is not 19 by 19");
                return null;
            }
            site = new Site(tower.centre().immutable(), tower.height());
            known.put(index, site);
            return site;
        }
        catch (RuntimeException notInstalled)
        {
            return null;
        }
    }

    private static City city(ServerLevel level)
    {
        City seen = CITY.get(level);
        if (seen != null && seen.tick() == level.getGameTime()) return seen;
        int mode = ArmamentTowerLogicR64.NONE;
        boolean waiting = false;
        try
        {
            var status = Tokyo3RetractionDirector.status(level, IntegratedNervMapBuilder.tokyo3Origin(level));
            if (status != null)
            {
                mode = ArmamentTowerLogicR64.cityMode(status.phase(), status.depth(), status.maximumDepth());
                waiting = ArmamentTowerLogicR64.tripWaiting(status.phase());
            }
        }
        catch (RuntimeException unavailable)
        {
            mode = ArmamentTowerLogicR64.NONE;
        }
        seen = new City(level.getGameTime(), mode, waiting);
        CITY.put(level, seen);
        return seen;
    }

    /** One line in the log per tower and reason, at most every ten seconds. */
    private static void refuse(ServerLevel level, int index, String why)
    {
        Map<Integer, Long> last = REFUSED.computeIfAbsent(level, world -> new HashMap<>());
        Long at = last.get(index);
        if (at != null && level.getGameTime() - at < 200) return;
        last.put(index, level.getGameTime());
        ProjectSeele.LOGGER.warn("Armament tower {} does not open: {}", index, why);
    }

    private static boolean refusedLately(ServerLevel level, int index)
    {
        Long at = REFUSED.computeIfAbsent(level, world -> new HashMap<>()).get(index);
        return at != null && level.getGameTime() - at < 100;
    }

    private static NervArmamentStationEntity loaded(ServerLevel level, State state, int index)
    {
        UUID id = state.stations.get(index);
        return id != null && level.getEntity(id) instanceof NervArmamentStationEntity station && station.isAlive() ? station : null;
    }

    /** Whether this world has armed towers at all; the command room and the pilots use them instead of the old lift then. */
    public static boolean active(ServerLevel level)
    {
        return !table(level).towers().isEmpty() && !state(level).stations.isEmpty();
    }

    @SubscribeEvent
    public static void tick(TickEvent.LevelTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END || !(event.level instanceof ServerLevel level) || level.getGameTime() % 20 != 7) return;
        Table table = table(level);
        if (table.towers().isEmpty()) return;
        State state = state(level);
        City city = city(level);
        for (Plan plan : table.towers())
        {
            Site site = site(level, plan.tower());
            if (site == null) continue;
            UUID id = state.stations.get(plan.tower());
            NervArmamentStationEntity station = loaded(level, state, plan.tower());
            if (station == null)
            {
                // An idle tower whose chunk is not loaded needs nothing. One that is owed something is brought in.
                if (id != null && !state.out.containsKey(plan.tower()) && !state.wanted.contains(plan.tower())) continue;
                NervArmamentStationEntity.keepCommandStationLoaded(level, site.centre());
                station = loaded(level, state, plan.tower());
                if (station == null && id == null)
                {
                    // Never a second station for a tower: one is made only where none was ever recorded.
                    var made = ModEntities.NERV_ARMAMENT_STATION.get().create(level);
                    if (made == null) continue;
                    made.setPos(site.centre().getX() + .5, site.centre().getY(), site.centre().getZ() + .5);
                    made.setPayloadR47(EvaUnit01Entity.WEAPON_RIFLE);
                    made.bindTowerR64(plan.tower(), plan.facing(), site.height(), table.door());
                    if (level.addFreshEntity(made))
                    {
                        state.stations.put(plan.tower(), made.getUUID());
                        state.setDirty();
                        station = made;
                        ProjectSeele.LOGGER.info("Armament tower {} armed at {}", plan.tower(), site.centre().toShortString());
                    }
                }
                if (station == null) continue;
            }
            station.bindTowerR64(plan.tower(), plan.facing(), site.height(), table.door());
            if (station.getStationState() != NervArmamentStationEntity.STOWED)
            {
                NervArmamentStationEntity.keepCommandStationLoaded(level, site.centre());
                continue;
            }
            station.showCityModeR64(city.mode());
            // Stowed with blocks still out: a run that ended without its last step (a crash, or someone stood in the way).
            if (state.out.containsKey(plan.tower()) && !giveBack(level, state, plan.tower(), false)) continue;
            if (state.wanted.contains(plan.tower())) start(level, state, table, station);
        }
    }

    /** Begins a run if the city rests and the tower's blocks are as they should be. */
    private static boolean start(ServerLevel level, State state, Table table, NervArmamentStationEntity station)
    {
        int index = station.towerR64();
        City city = city(level);
        if (city.mode() == ArmamentTowerLogicR64.NONE || station.getStationState() != NervArmamentStationEntity.STOWED
                || state.out.containsKey(index) || refusedLately(level, index)) return false;
        var lot = station.towerLotR64();
        var cells = ArmamentTowerLogicR64.cells(city.mode(), lot, station.towerFacingR64(), table.door());
        var pos = new BlockPos.MutableBlockPos();
        int solid = 0;
        for (int[] cell : cells)
        {
            pos.set(cell[0], cell[1], cell[2]);
            if (!level.isLoaded(pos)) { NervArmamentStationEntity.keepCommandStationLoaded(level, station.blockPosition()); return false; }
            if (level.getBlockEntity(pos) != null) { refuse(level, index, "a block entity stands in the " + (city.mode() == ArmamentTowerLogicR64.RAISED ? "door" : "hatch")); return false; }
            if (!level.getBlockState(pos).isAir()) solid++;
        }
        if (city.mode() == ArmamentTowerLogicR64.LOWERED && solid * 10 < cells.size() * 9)
        {
            refuse(level, index, "the lot's hatch is not there (" + solid + " of " + cells.size() + " cells)");
            state.wanted.remove(index); state.setDirty();
            return false;
        }
        if (city.mode() == ArmamentTowerLogicR64.RAISED)
        {
            // Only a building made for it: a door to lift, and an empty bay behind the door for the weapon.
            int empty = 0;
            var bay = ArmamentTowerLogicR64.bayCells(lot, station.towerFacingR64(), table.door(), table.bayDepth());
            for (int[] cell : bay) if (level.getBlockState(pos.set(cell[0], cell[1], cell[2])).isAir()) empty++;
            if (solid * 2 < cells.size() || empty * 20 < bay.size() * 19)
            {
                refuse(level, index, "the building has no weapon door and bay (door " + solid + " of " + cells.size() + " cells, bay " + empty + " of " + bay.size() + " empty)");
                state.wanted.remove(index); state.setDirty();
                return false;
            }
        }
        if (!station.beginTowerRunR64(city.mode())) return false;
        if (state.wanted.remove(index)) state.setDirty();
        return true;
    }

    /** {@link NervArmamentStationEntity#deploy()} of a tower. True if the tower starts or the call is kept. */
    public static boolean requestDeploy(NervArmamentStationEntity station)
    {
        if (!(station.level() instanceof ServerLevel level)) return false;
        int index = station.towerR64(), phase = station.getStationState();
        if (phase == NervArmamentStationEntity.READY || phase == NervArmamentStationEntity.OPENING
                || phase == NervArmamentStationEntity.RISING || phase == NervArmamentStationEntity.DOOR_OPENING) return false;
        State state = state(level);
        if (phase != NervArmamentStationEntity.STOWED)
        {
            // On its way in: it comes out again once it is stowed.
            if (state.wanted.add(index)) state.setDirty();
            return true;
        }
        if (start(level, state, table(level), station)) return true;
        if (city(level).mode() == ArmamentTowerLogicR64.NONE)
        {
            // The city is moving or about to: remembered until it rests.
            if (state.wanted.add(index)) state.setDirty();
            return true;
        }
        return false;
    }

    /** {@link NervArmamentStationEntity#recall()} of a tower: drops a kept call and brings the tower in. */
    public static boolean requestRecall(NervArmamentStationEntity station)
    {
        if (!(station.level() instanceof ServerLevel level)) return false;
        State state = state(level);
        boolean kept = state.wanted.remove(station.towerR64());
        if (kept) state.setDirty();
        return station.recallTowerR64() || kept;
    }

    /** The command room's two buttons: every tower out, or every tower in. Returns how many took the order. */
    public static int commandAll(ServerLevel level, boolean deploy)
    {
        Table table = table(level);
        State state = state(level);
        int taken = 0;
        for (Plan plan : table.towers())
        {
            if (!state.stations.containsKey(plan.tower())) continue;
            NervArmamentStationEntity station = loaded(level, state, plan.tower());
            if (station != null)
            {
                if (deploy ? station.deploy() : station.recall()) taken++;
            }
            else if (deploy ? state.wanted.add(plan.tower()) : state.wanted.remove(plan.tower()))
            {
                // Not loaded: the next pass loads its chunk and starts it.
                state.setDirty();
                taken++;
            }
        }
        return taken;
    }

    /** The nearest loaded tower to a point. Every tower restocks when it comes in, so none is left out for being empty. */
    public static NervArmamentStationEntity nearest(ServerLevel level, Vec3 point)
    {
        Table table = table(level);
        State state = state(level);
        List<NervArmamentStationEntity> stations = new ArrayList<>();
        for (Plan plan : table.towers())
        {
            NervArmamentStationEntity station = loaded(level, state, plan.tower());
            if (station != null) stations.add(station);
        }
        double[][] positions = new double[stations.size()][];
        boolean[] usable = new boolean[stations.size()];
        for (int i = 0; i < positions.length; i++)
        {
            positions[i] = new double[]{stations.get(i).getX(), stations.get(i).getZ()};
            usable[i] = true;
        }
        int best = ArmamentTowerLogicR64.nearest(point.x, point.z, positions, usable);
        return best < 0 ? null : stations.get(best);
    }

    public record Display(String state, boolean stocked, int percent) {}

    /** For the command room's wall. */
    public static Display display(ServerLevel level)
    {
        Table table = table(level);
        State state = state(level);
        int[] states = new int[table.towers().size()];
        boolean stocked = false;
        int percent = 0, waiting = 0;
        for (int i = 0; i < states.length; i++)
        {
            int tower = table.towers().get(i).tower();
            NervArmamentStationEntity station = loaded(level, state, tower);
            if (state.wanted.contains(tower)) waiting++;
            if (station == null) { states[i] = NervArmamentStationEntity.STOWED; stocked = true; continue; }
            states[i] = station.getStationState();
            stocked |= station.isStocked();
            percent = Math.max(percent, station.towerShownPercentR64());
        }
        return new Display(ArmamentTowerLogicR64.summary(states, waiting), stocked, percent);
    }

    /**
     * Asked by the city lift while a trip waits to begin. Towers that are out are brought in and called again for
     * after the trip; the answer is yes only when every tower is stowed and has its blocks back.
     */
    public static boolean stowedForCityTrip(ServerLevel level)
    {
        Table table = table(level);
        if (table.towers().isEmpty()) return true;
        State state = state(level);
        boolean clear = true;
        for (Plan plan : table.towers())
        {
            if (state.out.containsKey(plan.tower())) clear = false;
            NervArmamentStationEntity station = loaded(level, state, plan.tower());
            if (station == null || station.getStationState() == NervArmamentStationEntity.STOWED) continue;
            clear = false;
            if (station.recallTowerR64() && station.isStocked() && state.wanted.add(plan.tower())) state.setDirty();
        }
        return clear;
    }

    /**
     * Before each mechanical tick of a tower's station: takes the blocks out when the run reaches the phase that
     * needs them out, puts them back when it leaves it, and ends a run that has lost its footing. False holds the
     * station where it is for this tick.
     */
    public static boolean beforeMechanicalTick(NervArmamentStationEntity station)
    {
        int index = station.towerR64();
        if (index < 0 || !(station.level() instanceof ServerLevel level)) return true;
        int phase = station.getStationState();
        if (phase == NervArmamentStationEntity.STOWED) return true;
        State state = state(level);
        int run = station.towerRunR64();
        City city = city(level);
        if (!station.towerRunLiveR64() || run == ArmamentTowerLogicR64.NONE || city.mode() != run && !city.waiting())
        {
            // A run does not outlive a reload, and means nothing once the city has left the end it began at.
            abort(level, state, station);
            return false;
        }
        boolean out = ArmamentTowerLogicR64.cellsOut(run, phase);
        if (out && !state.out.containsKey(index))
        {
            if (!take(level, state, index, ArmamentTowerLogicR64.cells(run, station.towerLotR64(), station.towerFacingR64(), station.towerDoorR64())))
            {
                refuse(level, index, "its blocks could not be taken out");
                abort(level, state, station);
                return false;
            }
        }
        else if (!out && state.out.containsKey(index) && !giveBack(level, state, index, false)) return false;
        boolean combat = CityBattlefieldR29.combatActive(level);
        if (ArmamentTowerLogicR64.idleRecall(station.towerReadyTicksR64(combat), SeeleConfig.ARMAMENT_TOWER_IDLE_RECALL_SECONDS.get() * 20, combat))
            station.recallTowerR64();
        return true;
    }

    /** At the end of the last phase: the tower is stowed only once its blocks are back. */
    public static boolean finishRun(NervArmamentStationEntity station)
    {
        return !(station.level() instanceof ServerLevel level) || giveBack(level, state(level), station.towerR64(), false);
    }

    private static void abort(ServerLevel level, State state, NervArmamentStationEntity station)
    {
        int index = station.towerR64();
        boolean again = station.isStocked() && station.getStationState() != NervArmamentStationEntity.EMPTY;
        giveBack(level, state, index, true);
        station.resetTowerRunR64();
        if (again && state.wanted.add(index)) state.setDirty();
    }

    /** Writes down what stands in the cells, to disk, and only then clears them. */
    private static boolean take(ServerLevel level, State state, int index, List<int[]> cells)
    {
        ListTag record = new ListTag();
        var pos = new BlockPos.MutableBlockPos();
        for (int[] cell : cells)
        {
            pos.set(cell[0], cell[1], cell[2]);
            if (!level.isLoaded(pos) || level.getBlockEntity(pos) != null) return false;
            CompoundTag entry = new CompoundTag();
            entry.putLong("Pos", pos.asLong());
            entry.put("State", NbtUtils.writeBlockState(level.getBlockState(pos)));
            record.add(entry);
        }
        state.out.put(index, record);
        state.setDirty();
        level.getDataStorage().save();
        for (int[] cell : cells) level.setBlock(pos.set(cell[0], cell[1], cell[2]), Blocks.AIR.defaultBlockState(), SWAP);
        return true;
    }

    /** Puts a tower's blocks back exactly. Waits while someone stands in the opening unless forced. */
    private static boolean giveBack(ServerLevel level, State state, int index, boolean force)
    {
        ListTag record = state.out.get(index);
        if (record == null) return true;
        if (!force)
        {
            AABB opening = null;
            for (Tag value : record)
            {
                AABB cell = new AABB(BlockPos.of(((CompoundTag)value).getLong("Pos")));
                opening = opening == null ? cell : opening.minmax(cell);
            }
            if (opening != null && !level.getEntitiesOfClass(LivingEntity.class, opening, actor -> actor.isAlive() && !actor.isSpectator()).isEmpty())
                return false;
        }
        var blocks = level.holderLookup(Registries.BLOCK);
        for (Tag value : record)
        {
            CompoundTag entry = (CompoundTag)value;
            BlockPos pos = BlockPos.of(entry.getLong("Pos"));
            level.getChunkAt(pos);
            level.setBlock(pos, NbtUtils.readBlockState(blocks, entry.getCompound("State")), SWAP);
        }
        state.out.remove(index);
        state.setDirty();
        level.getDataStorage().save();
        return true;
    }

    /** A stop with a door open: every tower in at once and its blocks back, before the world is saved. */
    @SubscribeEvent
    public static void stopping(ServerStoppingEvent event)
    {
        for (ServerLevel level : event.getServer().getAllLevels())
        {
            Table table = table(level);
            if (table.towers().isEmpty()) continue;
            State state = state(level);
            for (Plan plan : table.towers())
            {
                NervArmamentStationEntity station = loaded(level, state, plan.tower());
                if (station != null && station.getStationState() != NervArmamentStationEntity.STOWED) abort(level, state, station);
                else if (state.out.containsKey(plan.tower())) giveBack(level, state, plan.tower(), true);
            }
        }
    }

    private ArmamentTowersR64() {}
}

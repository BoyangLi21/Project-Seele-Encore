package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.function.BooleanSupplier;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.*;

/** Explicit installed equipment trays. Missing source or cells never enables a refit. */
public final class CarrierBayTrayR53
{
    public static final String RESOURCE = "facility/r53_carrier_bay_trays.json";
    public record Cell(BlockPos at, String state, BlockState expected)
    {
        public Cell(BlockPos at, String state) { this(at, state, expectedState(state)); }
    }
    public record Bay(int variant, UUID eva, RigidTransform root, BlockPos logicalBed,
                      BlockPos marker, List<Cell> cells, List<NervLegacyCarrierRideR52.Piece> rails) { }
    private static volatile List<Bay> selected;
    private static volatile Map<BlockPos, BlockState> retainedGuards;
    private static final Map<String, BlockState> EXPECTED_STATES = new HashMap<>();
    private static final Map<Bay, List<ChunkPos>> REQUIRED_CHUNKS = new IdentityHashMap<>();

    private static synchronized BlockState expectedState(String source)
    {
        var known = EXPECTED_STATES.get(source);if (known != null) return known;
        try
        {
            var parsed = BlockStateParser.parseForBlock(net.minecraft.core.registries.BuiltInRegistries.BLOCK.asLookup(),source,false).blockState();
            if (!BlockStateParser.serialize(parsed).equals(source))
                throw new IllegalArgumentException("Canonical tray state required: " + source);
            EXPECTED_STATES.put(source, parsed);return parsed;
        }
        catch (com.mojang.brigadier.exceptions.CommandSyntaxException invalid)
        { throw new IllegalArgumentException("Invalid tray state: " + source, invalid); }
    }

    static BlockState retainedGuardStateR53(NervAssemblyOwnerR52.Cell cell)
    {
        if (!cell.closed().is(com.projectseele.registry.ModBlocks.LCL_BLOCK.get())) return null;
        var guards = retainedGuards;
        if (guards == null) guards = loadRetainedGuards();
        return guards.get(cell.at());
    }

    private static synchronized Map<BlockPos, BlockState> loadRetainedGuards()
    {
        if (retainedGuards != null) return retainedGuards;
        var guards = new HashMap<BlockPos, BlockState>();
        for (var bay : selected()) for (var source : bay.cells())
            if (source.state().startsWith("projectseele:nerv_edge_rail[")) guards.put(source.at(), source.expected());
        return retainedGuards = Map.copyOf(guards);
    }

    /** Only an explicitly installed guard may replace an original liquid cell. */
    public static boolean retainsLiquidCell(Level level, NervAssemblyOwnerR52.Cell cell)
    {
        var state = retainedGuardStateR53(cell);
        return state != null && level.dimension().equals(FacilitySchemaV2.DIMENSION)
                && level.hasChunkAt(cell.at()) && level.getBlockEntity(cell.at()) == null
                && state.equals(level.getBlockState(cell.at()));
    }

    public static List<Bay> selected()
    {
        var current = selected;return current == null ? loadSelected() : current;
    }

    private static synchronized List<Bay> loadSelected()
    {
        if (selected != null) return selected;
        try (var stream = CarrierBayTrayR53.class.getResourceAsStream("/assets/projectseele/" + RESOURCE))
        {
            if (stream == null) return selected = List.of();
            var doc = JsonParser.parseString(new String(stream.readAllBytes(), StandardCharsets.UTF_8)).getAsJsonObject();
            if (!"projectseele.r53.carrier-bay-trays.v1".equals(doc.get("schema").getAsString()))
                throw new IllegalArgumentException("Explicit shallow tray source required");
            var result = new ArrayList<Bay>();var variants = new HashSet<Integer>();
            for (var raw : doc.getAsJsonArray("bays"))
            {
                var row = raw.getAsJsonObject();int variant = row.get("variant").getAsInt();
                if (variant < 0 || variant > 2 || !variants.add(variant)) throw new IllegalArgumentException("Distinct original bay required");
                var root = new RigidTransform(vector(row.getAsJsonArray("root")), 0, 1, 0, 0);
                var cells = new ArrayList<Cell>();var positions = new HashSet<BlockPos>();
                for (var entry : row.getAsJsonArray("cells"))
                {
                    var cell = entry.getAsJsonObject();var at = block(cell.getAsJsonArray("pos"));
                    if (!positions.add(at)) throw new IllegalArgumentException("One tray expectation per cell required");
                    cells.add(new Cell(at, cell.get("state").getAsString()));
                }
                var rails = new ArrayList<NervLegacyCarrierRideR52.Piece>();
                for (var entry : row.getAsJsonArray("rails"))
                {
                    var rail = entry.getAsJsonObject();var values = rail.getAsJsonArray("triangles_rgb");
                    double[] rgb = new double[values.size()], xyz = new double[values.size() / 2];
                    if (rgb.length != 216) throw new IllegalArgumentException("Complete twelve-face rail box required");
                    for (int i = 0, n = 0; i < rgb.length; i += 6)
                    { for (int k = 0; k < 6; k++) rgb[i + k] = values.get(i + k).getAsDouble();for (int k = 0; k < 3; k++) xyz[n++] = rgb[i + k]; }
                    var mesh = new NervRigidMeshSweepR52(xyz);
                    if (!CarrierRearLateralR53.rectangular(mesh)) throw new IllegalArgumentException("Closed finite rail faces required");
                    rails.add(new NervLegacyCarrierRideR52.Piece("tray/" + variant + "/" + rail.get("name").getAsString(),
                            mesh, rgb, root, "tray_rail"));
                }
                if (cells.isEmpty() || rails.size() != 2 && rails.size() != 6) throw new IllegalArgumentException("Measured tray with two bay rails and optional four bank seats required");
                result.add(new Bay(variant, UUID.fromString(row.get("eva").getAsString()), root,
                        block(row.getAsJsonArray("logical_bed")), block(row.getAsJsonArray("physical_marker")),
                        List.copyOf(cells), List.copyOf(rails)));
            }
            if (variants.size() != 3) throw new IllegalArgumentException("All three original equipment bays must be declared");
            return selected = List.copyOf(result);
        }
        catch (IOException failure) { throw new IllegalStateException("Explicit shallow tray unavailable", failure); }
    }

    public static Bay bay(NervCarrierPlatformEntity carrier)
    {
        if (!NervOriginalCarrierR52.declared(carrier)) return null;
        var id = carrier.originalCarrierStateR52().getUUID("OriginalEva");
        return selected().stream().filter(b -> b.variant() == carrier.getUnitVariant() && b.eva().equals(id)).findFirst().orElse(null);
    }

    /** Earlier maintenance resets refilled original liquid cells over installed guards. */
    public static void restoreResetGuardsR53(ServerLevel level,NervCarrierPlatformEntity carrier,
                                            List<List<NervAssemblyOwnerR52.Cell>> liquid)
    {
        var bay=bay(carrier);
        if(bay==null||!CarrierMountProfileR53.read(carrier,1).shallowBay()
                ||!NervAirTransportManifestR52.same(NervOriginalCarrierR52.actualRoot(carrier,1),bay.root()))return;
        var affected=new HashSet<BlockPos>();
        for(var layer:liquid)for(var cell:layer)
            if(cell.closed().is(com.projectseele.registry.ModBlocks.LCL_BLOCK.get()))affected.add(cell.at());
        int restored=0;
        for(var source:bay.cells())
        {
            if(!affected.contains(source.at())||!source.state().startsWith("projectseele:nerv_edge_rail[")
                    ||!level.hasChunkAt(source.at())||level.getBlockEntity(source.at())!=null
                    ||!level.getBlockState(source.at()).is(com.projectseele.registry.ModBlocks.LCL_BLOCK.get()))continue;
            if(level.setBlock(source.at(),source.expected(),2))restored++;
        }
        if(restored>0)com.projectseele.ProjectSeele.LOGGER.info("Restored {} installed bay guards overwritten by legacy EVA reset, variant={}",restored,bay.variant());
    }

    /** Immutable source footprint used by the owning preparation/return job. */
    public static synchronized List<ChunkPos> requiredChunks(Bay bay)
    {
        if (bay == null) return List.of();
        var known = REQUIRED_CHUNKS.get(bay);if (known != null) return known;
        var chunks = new LinkedHashSet<ChunkPos>();
        for (var cell : bay.cells()) if (!cell.state().equals("minecraft:air")) chunks.add(new ChunkPos(cell.at()));
        for (var rail : bay.rails())
        {
            var box = rail.mesh().envelope(rail.frame(), rail.frame());int y = (int)Math.floor(box.minY - .001);
            for (int x = (int)Math.floor(box.minX); x < Math.ceil(box.maxX); x++)
                for (int z = (int)Math.floor(box.minZ); z < Math.ceil(box.maxZ); z++)
                    chunks.add(new ChunkPos(new BlockPos(x, y, z)));
        }
        known = List.copyOf(chunks);REQUIRED_CHUNKS.put(bay, known);return known;
    }

    public static boolean ready(Level level, Bay bay)
    {
        return ready(level, bay, false);
    }

    /** A tracked original carrier supplies installation state where client chunks are absent. */
    public static boolean readyForRender(Level level, Bay bay, NervCarrierPlatformEntity carrier)
    {
        boolean declared = level.isClientSide && bay != null && carrier != null && carrier.level() == level
                && bay(carrier) == bay && CarrierMountProfileR53.read(carrier, 1).shallowBay()
                && NervAirTransportManifestR52.same(NervOriginalCarrierR52.actualRoot(carrier, 1), bay.root());
        return ready(level, bay, declared);
    }

    private static boolean ready(Level level, Bay bay, boolean allowUnloadedInstalledCells)
    {
        if (bay == null || !level.dimension().equals(FacilitySchemaV2.DIMENSION)) return false;
        var retired=CarrierBayLiftRailsR54.retiredSupports(bay);
        for (var cell : bay.cells())
        {
            // Installation air is not bearing structure; normal LCL refill changes it.
            // Doors, liquid layers and moving assemblies validate their own occupancy.
            if (cell.state().equals("minecraft:air")) continue;
            if (!level.hasChunkAt(cell.at()))
            {
                if (allowUnloadedInstalledCells) continue;
                return false;
            }
            var actual = level.getBlockState(cell.at());
            // These declared mast openings are non-bearing wet-bay volume.
            // Refill may occupy them with actual LCL without restoring the retired slab.
            if (CarrierBayLiftSlotsR54.contains(cell.at())
                    && (actual.isAir() || actual.is(com.projectseele.registry.ModBlocks.LCL_BLOCK.get()))
                    && level.getBlockEntity(cell.at()) == null
                    && actual.getCollisionShape(level, cell.at()).isEmpty()) continue;
            if (!actual.equals(cell.expected()) || level.getBlockEntity(cell.at()) != null) return false;
        }
        for (var rail : bay.rails())
        {
            var box = rail.mesh().envelope(rail.frame(), rail.frame());int y = (int)Math.floor(box.minY - .001);
            for (int x = (int)Math.floor(box.minX); x < Math.ceil(box.maxX); x++)
                for (int z = (int)Math.floor(box.minZ); z < Math.ceil(box.maxZ); z++)
                {
                    var at = new BlockPos(x, y, z);boolean top = false;
                    if (!level.hasChunkAt(at))
                    {
                        if (allowUnloadedInstalledCells) continue;
                        return false;
                    }
                    if(retired.contains(at))
                    {
                        if(level.getBlockEntity(at)!=null||!level.getBlockState(at).getCollisionShape(level,at).isEmpty())return false;
                        continue;
                    }
                    for (var shape : level.getBlockState(at).getCollisionShape(level, at).toAabbs())
                        if (Math.abs(shape.maxY + y - box.minY) < .00001 && shape.minX == 0 && shape.maxX == 1
                                && shape.minZ == 0 && shape.maxZ == 1) top = true;
                    if (!top) return false;
                }
        }
        return true;
    }

    public static List<NervLegacyCarrierRideR52.Piece> railsAt(Bay bay,float rise)
    { return CarrierBayLiftRailsR54.at(bay,rise); }

    /** The logical launch datum retains bed+1. Its real marker belongs to the tray bottom. */
    public static BlockPos launchBed(EvaUnit01Entity eva)
    {
        var carrier = EvaMechanicalFrameR52.originalCarrierControllerR52(eva);
        if (carrier == null || !CarrierMountProfileR53.read(carrier, 1).shallowBay()) return null;
        var bay = bay(carrier);var level = eva.level();
        if (bay == null || !bay.eva().equals(eva.getUUID()) || Math.abs(eva.getY() - bay.root().translation().y) > .01
                || eva.position().distanceToSqr(bay.root().translation()) > 14 * 14
                || !level.hasChunkAt(bay.marker()) || !level.getBlockState(bay.marker()).is(Blocks.LODESTONE)
                || !level.getBlockState(bay.logicalBed()).isAir()) return null;
        return bay.logicalBed();
    }

    public static CarrierRearLateralR53.Prepared prepare(ServerLevel level, NervCarrierPlatformEntity carrier,
                                                        Set<UUID> own, BooleanSupplier ownerCurrent) throws IOException
    {
        var from = CarrierMountProfileR53.read(carrier, 1);var bay = bay(carrier);
        if (from.shallowBay() || from.aboveFloor() || !ready(level, bay) || !ownerCurrent.getAsBoolean()
                || NervOriginalCarrierR52.progress(carrier, 1) != 1 || !own.contains(carrier.getUUID())) return null;
        var to = new CarrierMountProfileR53.State(false, 0, from.transverse(), true);
        var proof = CarrierBayMotionR53.check(level, carrier, 1, 1, to, own);
        if (!proof.clear()) return null;
        var before = carrier.originalCarrierStateR52();var mount = carrier.carrierMountProfileR53();long at = level.getGameTime();
        BooleanSupplier current = () ->
        {
            if (at != level.getGameTime() || !ownerCurrent.getAsBoolean() || !before.equals(carrier.originalCarrierStateR52())
                    || !mount.equals(carrier.carrierMountProfileR53()) || !ready(level, bay)) return false;
            try { return CarrierBayMotionR53.check(level, carrier, 1, 1, to, own).clear(); }
            catch (IOException missing) { return false; }
        };
        return new CarrierRearLateralR53.Prepared(new CarrierMountProfileR53.PreparedUpdate(carrier,
                CarrierRearGuideR53.selected().fingerprint(), before.getLong("Epoch"), from, to, current), proof.envelopes());
    }

    static boolean parkedInstallationCurrent(NervCarrierPlatformEntity carrier)
    {
        if (!(carrier.level() instanceof ServerLevel level)) return false;
        var bay = bay(carrier);var saved = NervRouteRuntimeR52.installationStateR52(level);
        var job = saved == null ? null : saved.job(carrier.getUnitVariant());
        if (bay == null || job == null || job.phase() != NervRouteRuntimeStateR52.Phase.PARKED
                || !job.waiting().isEmpty() || !job.snapshot().original().eva().equals(bay.eva())
                || !(level.getEntity(bay.eva()) instanceof EvaUnit01Entity eva)
                || eva.carrierRiseProgress(1) != 0 || eva.getDeltaMovement().lengthSqr() != 0
                || eva.position().distanceToSqr(bay.root().translation()) > 1e-8
                || NervOriginalCarrierR52.progress(carrier, 1) != 0
                || !NervAirTransportManifestR52.same(NervOriginalCarrierR52.actualRoot(carrier, 1), bay.root())) return false;
        return ready(level, bay);
    }

    /** Explicit equipment installation, never an animation or a route reset.
     * First fit the source deck and finite pads, then withdraw the old shoulders
     * on their real actuator before installing the complete upright mast;
     * the original EVA, plug, task, controller datum and clocks are untouched. */
    public static boolean commissionParked(ServerLevel level, NervCarrierPlatformEntity carrier) throws IOException
    {
        if (!parkedInstallationCurrent(carrier)) return false;
        var from = CarrierMountProfileR53.read(carrier, 1);
        if (from.shallowBay()) return true;
        if (from.aboveFloor() || from.elevation() != 0) return false;
        var job = NervRouteRuntimeR52.installationStateR52(level).job(carrier.getUnitVariant());
        var own = new HashSet<>(TransportMembershipR52.members(job.snapshot().original(), job.snapshot().kind()));
        own.add(carrier.getUUID());var owners = Set.copyOf(own);
        var context = NervRouteRuntimeR52.flightContext(level);
        if (context == null || !(context.owner() instanceof NervAssemblyOwnerR52 owner)) return false;
        if (from.supportOnly() && !owner.withdrawCommissionShouldersR53(level, carrier, owners)) return false;
        var installation=carrier.getPersistentData();
        if(from.supportOnly()&&installation.getLong("CarrierCommissionRetryAtR53")>level.getGameTime())return false;
        installation.putLong("CarrierCommissionRetryAtR53",level.getGameTime()+20);
        var to = from.supportOnly() ? new CarrierMountProfileR53.State(false, 0, from.transverse(), true)
                : new CarrierMountProfileR53.State(false, 0, from.transverse(), false, true);
        var before = carrier.originalCarrierStateR52();var mounted = carrier.carrierMountProfileR53();
        BooleanSupplier current = () ->
        {
            if (!parkedInstallationCurrent(carrier) || !before.equals(carrier.originalCarrierStateR52())
                    || !mounted.equals(carrier.carrierMountProfileR53())) return false;
            try { var result=CarrierBayMotionR53.check(level, carrier, 0, 0, to, owners);
                installation.putString("CarrierCommissionHoldR53",result.clear()?"":result.rejection());return result.clear(); }
            catch (IOException missing) { return false; }
        };
        if (!current.getAsBoolean()) return false;
        var proof = new CarrierMountProfileR53.PreparedUpdate(carrier, CarrierRearGuideR53.selected().fingerprint(),
                before.getLong("Epoch"), from, to, current, true);
        carrier.acceptCarrierMountProfileR53(proof);
        return to.shallowBay() && CarrierMountProfileR53.read(carrier, 1).equals(to);
    }

    /** All four existing finite bottom facets must overlap real rail top faces. */
    public static boolean bears(Bay bay, RigidTransform controller)
    { return bears(bay,controller,1); }

    public static boolean bears(Bay bay,RigidTransform controller,float rise)
    {
        if (bay == null || controller.rotationErrorDegrees(bay.root()) > .000001) return false;
        var inverse = bay.root().inverse();
        var relative = inverse.compose(controller);var areas = new double[4];
        // These are source-only bounds for this exact actuator sample. Reuse
        // them across sole triangles, never across a world or motion update.
        var railBounds = railsAt(bay,rise).stream().map(rail ->
                NervRigidMeshSweepR52.transformed(rail.mesh().bounds(),inverse.compose(rail.frame()))).toList();
        var source = CarrierAssemblyR53.selected().parts().get("deck").positions();
        for (int i = 0; i < source.length; i += 9)
        {
            var points = List.of(vertex(source, i), vertex(source, i + 3), vertex(source, i + 6));
            if (points.stream().anyMatch(v -> Math.abs(v.y + 4.0078125) > .00001)) continue;
            int group = (points.get(0).x < 0 ? 0 : 1) + (points.get(0).z < 0 ? 0 : 2);
            for (var bounds : railBounds)
            {
                List<Vec3> polygon = new ArrayList<>(points.stream().map(relative::transformPoint).toList());
                if (polygon.stream().anyMatch(v -> Math.abs(v.y - bounds.maxY) > .00001)) continue;
                polygon = clip(polygon, 0, bounds.minX, true);polygon = clip(polygon, 0, bounds.maxX, false);
                polygon = clip(polygon, 2, bounds.minZ, true);polygon = clip(polygon, 2, bounds.maxZ, false);
                if (polygon.size() >= 3) for (int k = 1; k + 1 < polygon.size(); k++)
                    areas[group] += Math.abs(polygon.get(k).subtract(polygon.get(0)).cross(polygon.get(k + 1).subtract(polygon.get(0))).y) / 2;
            }
        }
        return Arrays.stream(areas).allMatch(a -> a > .1);
    }

    public static boolean railContact(NervOriginalCarrierR52.Part part, RigidTransform end, Bay bay,
                                      RigidTransform controller, RigidTransform endController)
    {
        return part.name().equals("deck") && part.frame().equals(controller) && end.equals(endController)
                && bears(bay, controller) && bears(bay, endController);
    }

    private static List<Vec3> clip(List<Vec3> polygon, int axis, double plane, boolean greater)
    {
        if (polygon.isEmpty()) return polygon;var out = new ArrayList<Vec3>();var before = polygon.get(polygon.size() - 1);
        double old = value(before, axis) - plane;if (!greater) old = -old;
        for (var now : polygon)
        {
            double next = value(now, axis) - plane;if (!greater) next = -next;
            if ((old >= 0) != (next >= 0)) out.add(before.add(now.subtract(before).scale(old / (old - next))));
            if (next >= 0) out.add(now);before = now;old = next;
        }
        return out;
    }
    private static double value(Vec3 v, int axis) { return axis == 0 ? v.x : v.z; }
    private static Vec3 vertex(double[] v, int i) { return new Vec3(v[i], v[i + 1], v[i + 2]); }
    private static Vec3 vector(JsonArray a) { return new Vec3(a.get(0).getAsDouble(), a.get(1).getAsDouble(), a.get(2).getAsDouble()); }
    private static BlockPos block(JsonArray a) { return BlockPos.containing(vector(a)); }
    private CarrierBayTrayR53() { }
}

package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.NervHangarDoorEntity;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.Level;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.*;

/** Installed first-leg rail source; retracting gate spans retain their full steel. */
public final class CarrierTransferRailsR53
{
    public static final String RESOURCE = "facility/r53_carrier_transfer_rails.json";
    public record Gate(String resource, UUID visual, RigidTransform frame) { }
    public record Source(String directory, List<CarrierRearGuideR53.Fixed> fixed,
                         List<CarrierRearGuideR53.Anchor> anchors, Map<Gate, List<CarrierRearGuideR53.Fixed>> bridges,
                         Map<String, String> motions) { }
    private static volatile boolean checked;
    private static Source selected;

    /** The original incline is a ramp-profile leg, absent from the outer
     * centre-curve guide table. Its contact identity comes from this installed
     * steel source and the directory's exact forward/reverse pair. */
    static String canonicalPath(DirectoryTrajectoryR52 path)
    {
        var source = selected();var directory = path.directory();var leg = path.leg();
        if (source == null || !source.directory().equals(directory.fingerprint())
                || !leg.equals(directory.leg(leg.id()))) return null;
        String name = leg.id().endsWith("/reverse")
                ? leg.id().substring(0, leg.id().length() - "/reverse".length()) : leg.id();
        var forward = directory.leg(name);var reverse = directory.leg(name + "/reverse");
        if (forward == null || reverse == null
                || forward.motion() != NervRouteDirectoryR52.Motion.ORIGINAL_UPRIGHT_TRANSFER
                || reverse.motion() != forward.motion()
                || !reverse.from().equals(forward.to()) || !reverse.to().equals(forward.from())
                || !reverse.rails().equals(forward.rails())
                || !leg.equals(forward) && !leg.equals(reverse)) return null;
        for (String mount : List.of("rear_l", "rear_r"))
            if (source.fixed().stream().noneMatch(p -> p.leg().equals(name)
                    && p.mount().equals(mount) && p.component().equals("head"))) return null;
        return name;
    }

    public static Source selected()
    {
        if (checked) return selected;
        var hardware = CarrierRearGuideR53.selected();
        return load(hardware, CarrierRearGuideR53.actualHardwareSourceR53());
    }

    private static synchronized Source load(CarrierRearGuideR53.Hardware hardware, String hardwareSource)
    {
        if (checked) return selected;
        try (var stream = CarrierTransferRailsR53.class.getResourceAsStream("/assets/projectseele/" + RESOURCE))
        {
            if (stream == null) { checked = true;return null; }
            var doc = JsonParser.parseString(new String(stream.readAllBytes(), StandardCharsets.UTF_8)).getAsJsonObject();
            require(doc.get("schema").getAsString().equals("projectseele.r53.carrier-transfer-rails.v1")
                    && doc.get("ready_to_install").getAsBoolean(), "Only completed explicit transfer equipment may be installed");
            require(hardware != null && hardwareSource.equals(doc.get("hardware_sha256").getAsString()),
                    "Transfer rails must retain the selected real rear hardware");
            require(doc.get("bridge_inward_m").getAsDouble() == .8 && doc.get("bridge_slide_m").getAsDouble() == 12,
                    "Explicit transverse disengagement and longitudinal storage stroke required");
            var motions = new HashMap<String, String>();
            var gates = new HashMap<String, Gate>();var bridges = new LinkedHashMap<Gate, List<CarrierRearGuideR53.Fixed>>();
            for (var raw : doc.getAsJsonArray("gates"))
            {
                var row = raw.getAsJsonObject();var f = row.getAsJsonObject("frame");var q = f.getAsJsonArray("quaternion");
                var gate = new Gate(row.get("resource").getAsString(), UUID.fromString(row.get("visual").getAsString()),
                        new RigidTransform(point(f.getAsJsonArray("position")), q.get(0).getAsFloat(), q.get(1).getAsFloat(), q.get(2).getAsFloat(), q.get(3).getAsFloat()));
                require(gates.put(gate.resource(), gate) == null, "Distinct original gate required");bridges.put(gate, new ArrayList<>());
            }
            require(gates.size() == 3, "All three original gate bridges required");
            var fixed = new ArrayList<CarrierRearGuideR53.Fixed>();var names = new HashSet<String>();
            for (var raw : doc.getAsJsonArray("pieces"))
            {
                var row = raw.getAsJsonObject();var values = row.getAsJsonArray("triangles_rgb");
                require(values.size() > 0 && values.size() % 18 == 0, "Complete finite source triangles required");
                double[] rgb = new double[values.size()], xyz = new double[values.size() / 2];
                for (int i = 0, n = 0; i < rgb.length; i += 6)
                {
                    for (int k = 0; k < 6; k++) { rgb[i + k] = values.get(i + k).getAsDouble();require(Double.isFinite(rgb[i + k]), "Finite rail source required"); }
                    for (int k = 0; k < 3; k++) xyz[n++] = rgb[i + k];
                }
                String name = row.get("name").getAsString(), component = row.get("component").getAsString();
                require(names.add(name) && Set.of("head", "web", "support").contains(component), "Named actual rail member required");
                var steel = new NervLegacyCarrierRideR52.Piece(name, new NervRigidMeshSweepR52(xyz), rgb,
                        new RigidTransform(point(row.getAsJsonArray("origin")), 0, 0, 0, 1), component);
                var part = new CarrierRearGuideR53.Fixed(name, row.get("leg").getAsString(), row.get("mount").getAsString(), component, steel);
                if (row.has("bridge_gate") && !row.get("bridge_gate").isJsonNull())
                {
                    var gate = gates.get(row.get("bridge_gate").getAsString());require(gate != null, "Rail bridge must belong to its original gate");
                    String motion = row.get("motion").getAsString();require(Set.of("head", "carriage").contains(motion), "Actual bridge slide source required");
                    motions.put(name, motion);
                    bridges.get(gate).add(part);
                }
                else fixed.add(part);
            }
            var anchors = new ArrayList<CarrierRearGuideR53.Anchor>();
            for (var raw : doc.getAsJsonArray("sockets"))
            {
                var row = raw.getAsJsonObject();var a = row.getAsJsonObject("anchor");var normal = point(a.getAsJsonArray("normal"));
                require(normal.equals(new Vec3(0, 1, 0)), "Actual native upper bearing plane required");
                anchors.add(new CarrierRearGuideR53.Anchor(row.get("leg").getAsString(), row.get("mount").getAsString(),
                        BlockPos.containing(point(a.getAsJsonArray("at"))), a.get("state").getAsString(), point(a.getAsJsonArray("bearing")), normal));
            }
            require(!fixed.isEmpty() && anchors.size() >= 6 && bridges.values().stream().allMatch(p -> !p.isEmpty()),
                    "Complete three-channel fixed seats and moving gate steel required");
            bridges.replaceAll((gate, parts) -> List.copyOf(parts));
            selected = new Source(doc.get("directory").getAsString(), List.copyOf(fixed), List.copyOf(anchors), Map.copyOf(bridges), Map.copyOf(motions));
            checked = true;return selected;
        }
        catch (IOException failure) { throw new IllegalStateException("Installed transfer rail source unavailable", failure); }
    }

    private static double remaining(float progress, double begin)
    {
        require(Float.isFinite(progress) && progress >= 0 && progress <= 1, "Bounded actual gate clock required");
        return 1 - Math.max(0, Math.min(1, (progress - begin) / .05));
    }

    public static List<CarrierRearGuideR53.Fixed> bridgeParts(NervHangarDoorEntity door, float progress)
    {
        var source = selected();if (source == null) return List.of();
        for (var entry : source.bridges().entrySet()) if (entry.getKey().visual().equals(door.getUUID()))
        {
            require(NervAirTransportManifestR52.same(entry.getKey().frame(), door.actualFrameR52()), "Original gate frame changed");
            return entry.getValue().stream().map(p -> {
                double x = source.motions().get(p.name()).equals("head")
                        ? -Math.signum(p.bounds().getCenter().x - entry.getKey().frame().translation().x) * .8 * remaining(progress, .95) : 0;
                var shift = new RigidTransform(new Vec3(x, 0, 12 * remaining(progress, .9)), 0, 0, 0, 1);
                return new CarrierRearGuideR53.Fixed(p.name(), p.leg(), p.mount(), p.component(),
                    new NervLegacyCarrierRideR52.Piece(p.name(), p.steel().mesh(), p.steel().rgb(), shift.compose(p.steel().frame()), p.component()));
            }).toList();
        }
        return List.of();
    }

    public static List<CarrierRearGuideR53.Fixed> actualBridges(Level level, AABB bounds)
    {
        var source = selected();if (source == null) return List.of();var result = new ArrayList<CarrierRearGuideR53.Fixed>();
        for (var gate : source.bridges().keySet())
        {
            if (!bounds.inflate(40).contains(gate.frame().translation())) continue;
            NervHangarDoorEntity door = level instanceof ServerLevel server && server.getEntity(gate.visual()) instanceof NervHangarDoorEntity d ? d :
                    level.getEntitiesOfClass(NervHangarDoorEntity.class, new AABB(gate.frame().translation(), gate.frame().translation()).inflate(80),
                            e -> e.getUUID().equals(gate.visual())).stream().findFirst().orElse(null);
            require(door != null, "Original transfer gate is not loaded");
            for (var part : bridgeParts(door, door.actualOpenProgressR52())) if (part.bounds().intersects(bounds)) result.add(part);
        }
        return List.copyOf(result);
    }

    static List<CarrierRearGuideR53.Fixed> nearby(Level level, AABB bounds)
    {
        var parts = new ArrayList<>(CarrierRearGuideR53.fixed().index().query(bounds));
        parts.addAll(actualBridges(level, bounds));return parts;
    }

    private static List<CarrierRearGuideR53.Anchor> gateSupportAnchors(Source source,RigidTransform frame)
    {return source.anchors().stream().filter(a->a.point().distanceToSqr(frame.translation())<45*45).toList();}

    static Set<net.minecraft.world.level.ChunkPos> gateSupportChunks(RigidTransform frame)
    {
        var source=selected();if(source==null)return Set.of();
        var chunks=new HashSet<net.minecraft.world.level.ChunkPos>();
        for(var anchor:gateSupportAnchors(source,frame))chunks.add(new net.minecraft.world.level.ChunkPos(anchor.at()));
        return Set.copyOf(chunks);
    }

    /** Gate and rail bridge share one actual clock and one continuous admission. */
    public static boolean clearGateSweep(ServerLevel level, NervHangarDoorEntity door, float from, float to,
                                         Set<UUID> own, Set<BlockPos> moving, Set<BlockPos> supports)
    {
        var source = selected();if (source == null) return true;
        if (door.actualOpenProgressR52() != from) return false;
        var a0 = bridgeParts(door, from);if (a0.isEmpty()) return true;
        var knots = new ArrayList<Float>();knots.add(from);
        for (float k : new float[]{.9F, .95F}) if (k > Math.min(from, to) && k < Math.max(from, to)) knots.add(k);
        knots.add(to);knots.sort(from <= to ? Comparator.naturalOrder() : Comparator.reverseOrder());
        var geo = door.declaredGeometryR52();var gateFrame = door.actualFrameR52();
        var fixed = CarrierRearGuideR53.fixed();
        for (var anchor : gateSupportAnchors(source,gateFrame))
            if (!CarrierRearGuideR53.anchorBears(level, anchor)) return false;
        for (var rail : fixed.index().query(geo.sweptBounds(gateFrame, from, to)))
            if (geo.intersects(gateFrame, from, to, rail.steel().mesh(), rail.steel().frame())) return false;
        for (int k = 0; k + 1 < knots.size(); k++)
        {
            float p = knots.get(k), q = knots.get(k + 1);
            var a = bridgeParts(door, p);var b = bridgeParts(door, q);
            if (!bridgeBearings(source, a) || !bridgeBearings(source, b)) return false;
            for (int i = 0; i < a.size(); i++)
            {
                var first = a.get(i).steel();var last = b.get(i).steel();
                var bounds = first.mesh().envelope(first.frame(), last.frame());
                if (!EntryPlugEjectionR48.loaded(level, bounds)
                        || geo.intersects(gateFrame, p, q, first.mesh(), first.frame(), last.frame())) return false;
                for (var at : BlockPos.betweenClosed(BlockPos.containing(bounds.minX, bounds.minY, bounds.minZ),
                                                     BlockPos.containing(bounds.maxX, bounds.maxY, bounds.maxZ)))
                {
                    if (moving.contains(at)) continue;
                    for (var box : level.getBlockState(at).getCollisionShape(level, at, CollisionContext.of(door)).toAabbs())
                        if (first.mesh().intersects(first.frame(), last.frame(), box.move(at), .003)) return false;
                }
                for (var actor : level.getEntities(door, bounds.inflate(100), e -> e.isAlive() && !e.isSpectator()))
                {
                    var meshes = NervFlightProofR52.actualObstacleMeshes(actor);
                    if (meshes == null || meshes.isEmpty())
                    { if (first.mesh().intersects(first.frame(), last.frame(), actor.getBoundingBox(), .003)) return false; }
                    else for (var mesh : meshes)
                        if (first.mesh().intersects(first.frame(), last.frame(), mesh.mesh(), mesh.frame(), mesh.endFrame(), .003, Vec3.ZERO)) return false;
                }
                for (var rail : fixed.index().query(bounds.inflate(.003)))
                    if (!separated(first, last, rail.steel(), rail.steel())
                            && first.mesh().intersects(first.frame(), last.frame(), rail.steel().mesh(), rail.steel().frame(), rail.steel().frame(), .003, Vec3.ZERO)) return false;
                for (int j = i + 1; j < a.size(); j++)
                {
                    var r = a.get(j).steel();var s = b.get(j).steel();
                    if (NervAirTransportManifestR52.same(first.frame().inverse().compose(r.frame()), last.frame().inverse().compose(s.frame()))) continue;
                    if (!separated(first, last, r, s)
                            && first.mesh().intersects(first.frame(), last.frame(), r.mesh(), r.frame(), s.frame(), .003, Vec3.ZERO)) return false;
                }
            }
        }
        return true;
    }

    private static boolean bridgeBearings(Source source, List<CarrierRearGuideR53.Fixed> parts)
    {
        int arms = 0, shoes = 0;
        for (var part : parts)
        {
            if (part.name().endsWith("/slide/arm"))
            {
                String runner = part.name().substring(0, part.name().length() - 3) + "runner";
                var fixed = source.fixed().stream().filter(f -> f.name().equals(runner)).findFirst().orElse(null);
                if (fixed == null || !CarrierRearLateralR53.rectangular(part.steel().mesh())
                        || !CarrierRearLateralR53.rectangular(fixed.steel().mesh())
                        || CarrierRearLateralR53.faceArea(part.bounds(), fixed.bounds(), 1) <= 1) return false;
                arms++;
            }
            else if (part.name().contains("/slide/cross_shoe_"))
            {
                String armName = part.name().substring(0, part.name().indexOf("/cross_shoe_")) + "/arm";
                var arm = parts.stream().filter(f -> f.name().equals(armName)).findFirst().orElse(null);
                if (arm == null || !CarrierRearLateralR53.rectangular(part.steel().mesh())
                        || CarrierRearLateralR53.faceArea(part.bounds(), arm.bounds(), 1) <= .1) return false;
                shoes++;
            }
        }
        // Contact normals remain fixed; overlap along either affine stroke
        // is a concave interval length, so positive endpoint minima suffice.
        return arms == 2 && shoes == 4;
    }

    // Every bridge member translates affinely on each split clock interval.
    // A common separating plane at both ends therefore separates all source
    // vertices throughout, including the shared finite sliding bearing face.
    private static boolean separated(NervLegacyCarrierRideR52.Piece a, NervLegacyCarrierRideR52.Piece b,
                                     NervLegacyCarrierRideR52.Piece c, NervLegacyCarrierRideR52.Piece d)
    {
        var A = a.mesh().envelope(a.frame(), a.frame());var B = b.mesh().envelope(b.frame(), b.frame());
        var C = c.mesh().envelope(c.frame(), c.frame());var D = d.mesh().envelope(d.frame(), d.frame());
        return A.maxX <= C.minX + 1e-8 && B.maxX <= D.minX + 1e-8 || C.maxX <= A.minX + 1e-8 && D.maxX <= B.minX + 1e-8
                || A.maxY <= C.minY + 1e-8 && B.maxY <= D.minY + 1e-8 || C.maxY <= A.minY + 1e-8 && D.maxY <= B.minY + 1e-8
                || A.maxZ <= C.minZ + 1e-8 && B.maxZ <= D.minZ + 1e-8 || C.maxZ <= A.minZ + 1e-8 && D.maxZ <= B.minZ + 1e-8;
    }

    private static Vec3 point(JsonArray a) { return new Vec3(a.get(0).getAsDouble(), a.get(1).getAsDouble(), a.get(2).getAsDouble()); }
    private static void require(boolean condition, String message) { if (!condition) throw new IllegalArgumentException(message); }
    private CarrierTransferRailsR53() { }
}

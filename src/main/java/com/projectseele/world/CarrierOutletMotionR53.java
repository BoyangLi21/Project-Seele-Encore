package com.projectseele.world;

import com.projectseele.entity.*;
import java.io.IOException;
import java.util.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.*;
import net.minecraft.world.phys.*;

/** The empty rack uses the existing final vertical rail in either direction, with its
 * complete installed source and independent jaw release kept in the proof. */
public final class CarrierOutletMotionR53
{
    private static CarrierRearGuideMotionR53.Result no(String reason)
    { return new CarrierRearGuideMotionR53.Result(List.of(), "outlet/" + reason); }

    static RigidTransform physicalRoot(RigidTransform outlet, float rise)
    { return outlet.compose(new RigidTransform(new Vec3(0, NervR50CarrierModeR53.launchDeckDropR53(outlet, rise), 0), 0, 0, 0, 1)); }

    static CarrierRearGuideMotionR53.Result check(ServerLevel level, NervCarrierPlatformEntity carrier,
            DirectoryTrajectoryR52 guide, float from, float to, NervBallisticHandoffR52.StepR53 payload, Set<UUID> own) throws IOException
    {
        var mounting = CarrierMountProfileR53.read(carrier, 1);
        var root = NervOriginalCarrierR52.actualRoot(carrier, 1);
        var direction = NervOriginalCarrierR52.uprightDirectionR52(carrier, 1);
        String leg = CarrierRearGuideR53.canonicalPath(guide);
        if (!mounting.shallowBay() || mounting.aboveFloor() || mounting.supportOnly()
                || mounting.elevation() != 0 || mounting.transverse() != 0
                || NervR50CarrierModeR53.launchDeckDropR53(root, 0) != -64
                || direction.distanceTo(new Vec3(0, 1, 0)) > 1e-7
                || CarrierRearGuideR53.actualLift(carrier, 1) != 0
                || NervOriginalCarrierR52.headSlideR53(carrier, 1) != 0
                || leg == null || !guide.pureTranslation()
                || !NervUprightGuidewayR52.enabledForDirectoryR52(level, guide.directory()))
            return no("actual_vertical_source_missing");
        var hardware = CarrierRearGuideR53.selected();var fixed = CarrierRearGuideR53.fixed();
        if (hardware == null || fixed == null || !fixed.directory().equals(guide.directory().fingerprint())
                || !fixed.legacySource().equals(NervRouteRuntimeR52.uprightGuideSourceR52(level)))
            return no("actual_guide_binding_changed");
        // The helper accepts only a LINE tail. Both physical endpoints must be
        // exactly those of its bounded segment; no alternative return path.
        if (!NervAirTransportManifestR52.same(guide.sample(0).evaRoot(), physicalRoot(root, Math.min(from, to)))
                || !NervAirTransportManifestR52.same(guide.sample(1).evaRoot(), physicalRoot(root, Math.max(from, to))))
            return no("actual_vertical_endpoints_changed");
        for (double t : new double[]{0, .5, 1})
            if (!CarrierRearGuideR53.finiteTransferCapture(level, guide.sample(t).evaRoot(), direction, leg, 0, mounting))
                return no("finite_rear_bearing_missing");

        var times = new ArrayList<Float>();times.add(from);
        for (float knot : new float[]{.5F, .75F})
            if (Math.min(from, to) < knot && Math.max(from, to) > knot) times.add(knot);
        times.add(to);times.sort(from <= to ? Comparator.naturalOrder() : Comparator.reverseOrder());
        var boxes = new ArrayList<AABB>();
        var originalRails = new NervStaticSpatialIndexR52<>(NervLegacyCarrierRideR52.fixedPartsR52(),
                p -> p.mesh().envelope(p.frame(), p.frame()));
        var query = new NervRigidMeshSweepR52.PairQuery();
        for (int segment = 0; segment + 1 < times.size(); segment++)
        {
            query.nextInterval();
            float start = times.get(segment), end = times.get(segment + 1);
            var a = parts(carrier, root, start, mounting);var b = parts(carrier, root, end, mounting);
            var firstRoot = physicalRoot(root, start);var lastRoot = physicalRoot(root, end);
            var rearA = new HashMap<String, NervLegacyCarrierRideR52.Piece>();
            var rearB = new HashMap<String, NervLegacyCarrierRideR52.Piece>();
            hardware.partsAt(firstRoot, 1, direction, 0, 0, mounting).forEach(p -> rearA.put(p.name(), p));
            hardware.partsAt(lastRoot, 1, direction, 0, 0, mounting).forEach(p -> rearB.put(p.name(), p));
            // Rise .5 separates translation from release; rise .75 separates
            // the two jaw axes. Every interval is an actual affine movement.
            var nativeFailure = NervOriginalCarrierR52.nativeBlockRejectionR53(a, b, 0,
                    bound -> EntryPlugEjectionR48.loaded(level, bound), bound ->
                    { var shapes = new ArrayList<AABB>();for (var shape : level.getBlockCollisions(carrier, bound)) shapes.addAll(shape.toAabbs());return shapes; });
            if (nativeFailure != null) return no(nativeFailure);
            AABB area = null;var bounds = new ArrayList<AABB>();
            for (int i = 0; i < a.size(); i++)
            {
                var bound = a.get(i).mesh().envelope(a.get(i).frame(), b.get(i).frame());
                bounds.add(bound);boxes.add(bound);area = area == null ? bound : area.minmax(bound);
            }
            for (var anchor : fixed.anchorIndex().query(area.inflate(32)))
                if (!CarrierRearGuideR53.anchorBears(level, anchor)) return no("native_support_changed=" + anchor.at());
            for (var actor : level.getEntities((Entity)null, area.inflate(100), e -> e.isAlive() && e != carrier
                    && (e instanceof LivingEntity || e.canBeCollidedWith() || e instanceof NervCarrierPlatformEntity
                        || e instanceof EntryPlugCarrierEntity || e instanceof NervHangarDoorEntity
                        || e instanceof NervSiloDoorEntity || e instanceof UNTransportEntity)))
            {
                // The caller supplies the actual final-approach handoff group.
                // Raising its receiver must remain possible until full bearing.
                if (!NervTraversalPolicyR53.strict(level)
                        && payload == null && own.contains(actor.getUUID())) continue;
                boolean movingPilot = payload != null && actor.getUUID().equals(payload.original().pilot());
                var carried = payload == null ? null : payload.actorMeshes(actor.getUUID());
                var meshes = carried == null ? NervFlightProofR52.actualObstacleMeshes(actor) : carried;
                double alpha = from == to ? 0 : (start - from) / (double)(to - from);
                double beta = from == to ? 1 : (end - from) / (double)(to - from);
                if (meshes == null) return no("unknown_actor=" + actor.getUUID());
                var permittedFeet = dockingSoles(carrier, actor, a, b, end >= start ? lastRoot : firstRoot, mounting);
                for (int i = 0; i < a.size(); i++)
                {
                    var p = a.get(i);var q = b.get(i);
                    if (movingPilot)
                    { if (p.mesh().intersects(p.frame(), q.frame(), payload.pilotSweep(), .003)) return no(p.name() + " / moving original pilot");continue; }
                    if (meshes.isEmpty())
                    { if (p.mesh().intersects(p.frame(), q.frame(), actor.getBoundingBox(), .003)) return no(p.name() + " / actor " + actor.getUUID());continue; }
                    // The same-tick ballistic token supplies the actual independent
                    // payload motion. All other actors keep their native frames.
                    for (var mesh : meshes)
                    {
                        if (permittedFeet.getOrDefault(p.name(), Set.of()).contains(mesh.mesh())) continue;
                        var meshFrom = carried == null ? mesh.frame() : mesh.frame().interpolate(mesh.endFrame(), alpha);
                        var meshTo = carried == null ? mesh.endFrame() : mesh.frame().interpolate(mesh.endFrame(), beta);
                        if (hit(p, q, bounds.get(i), mesh.mesh(), meshFrom, meshTo, query))
                            return no(p.name() + " / actor mesh " + actor.getUUID());
                    }
                }
            }
            for (int i = 0; i < a.size(); i++)
            {
                var p = a.get(i);var q = b.get(i);var bound = bounds.get(i);
                for (int j = i + 1; j < a.size(); j++)
                {
                    var r = a.get(j);var s = b.get(j);
                    if (NervAirTransportManifestR52.same(p.frame().inverse().compose(r.frame()), q.frame().inverse().compose(s.frame()))) continue;
                    if (hit(p, q, bound, r.mesh(), r.frame(), s.frame(), query)) return no(p.name() + " / moving rack member " + r.name());
                }
                for (var rail : originalRails.query(bound))
                    if (hit(p, q, bound, rail.mesh(), rail.frame(), rail.frame(), query)) return no(p.name() + " / original rail " + rail.name());
                for (var rail : CarrierTransferRailsR53.nearby(level, bound))
                {
                    if (rearA.containsKey(p.name()) && CarrierRearGuideR53.namedContact(rearA.get(p.name()), rearB.get(p.name()), rail, leg, 0)) continue;
                    var steel = rail.steel();
                    if (hit(p, q, bound, steel.mesh(), steel.frame(), steel.frame(), query)) return no(p.name() + " / " + rail.name());
                }
            }
        }
        return new CarrierRearGuideMotionR53.Result(List.copyOf(boxes), null);
    }

    private static Map<String, Set<NervRigidMeshSweepR52>> dockingSoles(NervCarrierPlatformEntity carrier,
            Entity actor, List<NervOriginalCarrierR52.Part> from, List<NervOriginalCarrierR52.Part> to,
            RigidTransform physicalRoot, CarrierMountProfileR53.State mounting)
    {
        var result = new HashMap<String, Set<NervRigidMeshSweepR52>>();
        if (!(actor instanceof EvaUnit01Entity eva) || !EvaMechanicalFrameR52.active(eva)
                || NervOriginalCarrierR52.attachedTo(carrier, eva)
                || !carrier.originalCarrierStateR52().getUUID("OriginalEva").equals(eva.getUUID())) return result;
        var body = EvaMechanicalFrameR52.capturedGeometry(eva);var solids = NervObstacleMeshesR53.body(body);
        var soles = CarrierFootBearingR53.selected();if (soles == null) return result;
        for (int i = 0; i < from.size(); i++)
        {
            var p = from.get(i);var q = to.get(i);if (p.role() != NervOriginalCarrierR52.Role.SOLE_BEARING) continue;
            var movement = q.frame().translation().subtract(p.frame().translation());
            if (movement.horizontalDistanceSqr() > 1e-18 || p.frame().rotationErrorDegrees(q.frame()) != 0
                    || p.frame().transformVector(new Vec3(0, 1, 0)).distanceTo(new Vec3(0, 1, 0)) > 1e-8) continue;
            // Upward docking is bounded by the certified final foot plane;
            // downward release is bounded by the certified initial plane.
            // All intermediate vertical positions lie below that same plane.
            var contact = movement.y >= 0 ? q : p;
            var pad = soles.variant(carrier.getUnitVariant()).stream().filter(s -> s.name().equals(p.name())).findFirst().orElse(null);
            if (pad == null || !CarrierFootBearingR53.permitsContact(soles, body, NervOwnerPlacementR52.actualRoot(eva),
                    physicalRoot, mounting, CarrierAssemblyR53.selected(), pad.bone(), new NervFlightProofR52.ObstacleMesh(contact.mesh(), contact.frame()))) continue;
            var feet = new HashSet<NervRigidMeshSweepR52>();
            for (int n = 0; n < body.parts().size(); n++) if (body.parts().get(n).bone().equals(pad.bone())) feet.add(solids.get(n));
            result.put(p.name(), Set.copyOf(feet));
        }
        return result;
    }

    private static List<NervOriginalCarrierR52.Part> parts(NervCarrierPlatformEntity carrier, RigidTransform root,
            float rise, CarrierMountProfileR53.State mounting) throws IOException
    { return NervOriginalCarrierR52.partsAtR53(carrier.getUnitVariant(), root, rise, NervOriginalCarrierR52.guideUp(carrier),
            NervOriginalCarrierR52.actualRidePoseR52(carrier), NervOriginalCarrierR52.uprightDirectionR52(carrier, 1), 0, 0, mounting); }

    private static boolean hit(NervOriginalCarrierR52.Part a, NervOriginalCarrierR52.Part b, AABB bounds,
            NervRigidMeshSweepR52 mesh, RigidTransform from, RigidTransform to, NervRigidMeshSweepR52.PairQuery query)
    { return bounds.intersects(mesh.envelope(from, to)) && a.mesh().intersects(a.frame(), b.frame(), mesh, from, to, .003, Vec3.ZERO, query); }

    private CarrierOutletMotionR53() { }
}

package com.projectseele.world;

import com.projectseele.entity.*;
import java.io.IOException;
import java.util.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.*;
import net.minecraft.world.phys.*;

/** Full supplied carrier admission for the explicitly installed short bay stroke. */
public final class CarrierBayMotionR53
{
    private static final NervRigidPairMemoR53 SOURCE_PAIRS = new NervRigidPairMemoR53(2048);
    private static CarrierRearGuideMotionR53.Result no(String reason)
    { return new CarrierRearGuideMotionR53.Result(List.of(), reason); }

    public static CarrierRearGuideMotionR53.Result check(ServerLevel level, NervCarrierPlatformEntity carrier,
            float from, float to, CarrierMountProfileR53.State mounting, Set<UUID> own) throws IOException
    {
        var root = NervOriginalCarrierR52.actualRoot(carrier, 1);
        return check(level, carrier, root, root, from, to, mounting, own);
    }

    public static CarrierRearGuideMotionR53.Result translation(ServerLevel level, NervCarrierPlatformEntity carrier,
            DirectoryTrajectoryR52 path, Set<UUID> own) throws IOException
    {
        if (!path.pureTranslation() || CarrierTransferRailsR53.selected() == null
                || !CarrierTransferRailsR53.selected().directory().equals(path.directory().fingerprint()))
            return no("shallow_tray_actual_route_equipment_source_missing");
        var mounting = CarrierMountProfileR53.read(carrier, 1);var boxes = new ArrayList<AABB>();
        var budget = CarrierRearGuideMotionR53.continuousBudget(path.translationSecondDerivativeBound(), path.samplingErrorBound());
        String leg = CarrierRearGuideR53.canonicalPath(path);
        for (int i = 0; i < budget.divisions(); i++)
        {
            double a = i / (double)budget.divisions(), b = (i + 1D) / budget.divisions();
            var result = check(level, carrier, path.sample(a).evaRoot(), path.sample(b).evaRoot(), 1, 1, mounting, own,
                    NervOuterCarrierGuideR52.direction(path, a), NervOuterCarrierGuideR52.direction(path, b), leg, budget.error());
            if (!result.clear()) return result;boxes.addAll(result.envelopes());
        }
        return new CarrierRearGuideMotionR53.Result(List.copyOf(boxes), null);
    }

    private static CarrierRearGuideMotionR53.Result check(ServerLevel level, NervCarrierPlatformEntity carrier,
            RigidTransform root, RigidTransform endRoot, float from, float to,
            CarrierMountProfileR53.State mounting, Set<UUID> own) throws IOException
    { return check(level, carrier, root, endRoot, from, to, mounting, own, null, null, null, 0); }

    private static CarrierRearGuideMotionR53.Result check(ServerLevel level, NervCarrierPlatformEntity carrier,
            RigidTransform root, RigidTransform endRoot, float from, float to,
            CarrierMountProfileR53.State mounting, Set<UUID> own,
            Vec3 directionFrom, Vec3 directionTo, String leg, double error) throws IOException
    {
        var bay = CarrierBayTrayR53.bay(carrier);
        if ((!mounting.shallowBay() && !mounting.supportOnly()) || mounting.aboveFloor() || mounting.elevation() != 0
                || !Float.isFinite(from + to) || from < 0 || from > 1 || to < 0 || to > 1
                || !own.contains(carrier.getUUID()) || bay == null)
            return no("shallow_tray_source_or_finite_load_bearing_missing");
        if(from!=to&&mounting.shallowBay()&&CarrierRearGuideR53.actualLift(carrier,1)!=CarrierRearGuideR53.STOW_LIFT)
            return no("shallow_tray_receiver_must_reach_independent_upper_stop_before_mast_stroke");
        if ((directionFrom == null || NervTraversalPolicyR53.strict(level))
                && !supportedPair(level, carrier, bay, root, endRoot, directionFrom, directionTo, leg, mounting,from,to))
            return no("shallow_tray_source_or_finite_load_bearing_missing");
        var times = new ArrayList<Float>();times.add(from);
        for(float knot : CarrierMountProfileR53.BAY_ACTUATOR_KNOTS)
            if (Math.min(from, to) < knot && Math.max(from, to) > knot) times.add(knot);
        times.sort(from <= to ? Comparator.naturalOrder() : Comparator.reverseOrder());
        times.add(to);var boxes = new ArrayList<AABB>();
        var soles = CarrierFootBearingR53.selected();if (soles == null) return no("shallow_tray_finite_sole_source_missing");
        var source = CarrierAssemblyR53.selected();
        var actualRoot = NervOriginalCarrierR52.actualRoot(carrier, 1);
        var movementFrom = root.compose(actualRoot.inverse());
        var movementTo = endRoot.compose(actualRoot.inverse());
        for (int segment = 0; segment + 1 < times.size(); segment++)
        {
            var a = parts(carrier, root, times.get(segment), mounting);
            var b = parts(carrier, endRoot, times.get(segment + 1), mounting);
            // Rear head orientation follows the actual route tangent and is
            // admitted by CarrierRearGuideMotionR53 on the same source window.
            if (directionFrom != null)
            { a = a.stream().filter(p -> p.role() != NervOriginalCarrierR52.Role.GUIDE).toList();b = b.stream().filter(p -> p.role() != NervOriginalCarrierR52.Role.GUIDE).toList(); }
            // Fixed bay endpoints stay at the bay. Only the two bridge pieces
            // follow the final tenth of the same reversible actuator clock.
            var withRailsA=new ArrayList<>(a);var withRailsB=new ArrayList<>(b);
            for(var rail:CarrierBayTrayR53.railsAt(bay,times.get(segment)))
                if(!rail.name().contains("/bank_foot_"))withRailsA.add(new NervOriginalCarrierR52.Part(rail.name(),NervOriginalCarrierR52.Role.STRUCTURE,rail.mesh(),rail.frame()));
            for(var rail:CarrierBayTrayR53.railsAt(bay,times.get(segment+1)))
                if(!rail.name().contains("/bank_foot_"))withRailsB.add(new NervOriginalCarrierR52.Part(rail.name(),NervOriginalCarrierR52.Role.STRUCTURE,rail.mesh(),rail.frame()));
            a=List.copyOf(withRailsA);b=List.copyOf(withRailsB);
            // Authored service motion may intersect its surroundings. Keep
            // source clocks, support sequencing and loaded-region bounds.
            if(!NervTraversalPolicyR53.strict(level))
            {
                for(int i=0;i<a.size();i++)
                {
                    var bounds=a.get(i).mesh().envelope(a.get(i).frame(),b.get(i).frame()).inflate(error);
                    if(!EntryPlugEjectionR48.loaded(level,bounds))return no("shallow_tray_unloaded="+bounds);
                    boxes.add(bounds);
                }
                continue;
            }
            var failure = NervOriginalCarrierR52.nativeBlockRejectionR53(a, b, error,
                    bound -> EntryPlugEjectionR48.loaded(level, bound), bound ->
                    { var shapes = new ArrayList<AABB>();for (var shape : level.getBlockCollisions(carrier, bound)) shapes.addAll(shape.toAabbs());return shapes; });
            if (failure != null) return no("shallow_tray_" + failure);
            AABB total = null;
            for (int i = 0; i < a.size(); i++)
            {
                var bounds = a.get(i).mesh().envelope(a.get(i).frame(), b.get(i).frame()).inflate(error);
                boxes.add(bounds);total = total == null ? bounds : total.minmax(bounds);
            }
            for (var actor : level.getEntities((Entity)null, total.inflate(100), e -> e.isAlive() && e != carrier
                    && (e instanceof LivingEntity || e.canBeCollidedWith() || e instanceof NervCarrierPlatformEntity
                        || e instanceof EntryPlugCarrierEntity || e instanceof NervHangarDoorEntity
                        || e instanceof NervSiloDoorEntity || e instanceof UNTransportEntity)))
            {
                // Route and actuator docking share the same owned assembly.
                // Full sole bearing is required before releasing the air load.
                if (!NervTraversalPolicyR53.strict(level) && own.contains(actor.getUUID())) continue;
                var meshes = NervFlightProofR52.actualObstacleMeshes(actor);
                if (meshes == null) return no("shallow_tray_unknown_actor=" + actor.getUUID());
                EvaOriginalMeshGeometryR52.Geometry body = null;
                if (actor instanceof EvaUnit01Entity eva && own.contains(eva.getUUID()))
                {
                    body = EvaMechanicalFrameR52.active(eva) ? EvaMechanicalFrameR52.capturedGeometry(eva)
                            : EvaMechanicalFrameR52.serviceSourceHeldR52(eva) ? EvaMechanicalFrameR52.serviceGeometryR52(eva) : null;
                    if (body == null || !CarrierFootBearingR53.bears(soles, body, movementFrom.compose(NervOwnerPlacementR52.actualRoot(eva)), root, mounting, source))
                        return no("shallow_tray_original_sole_bearing_missing");
                }
                boolean coupled = own.contains(actor.getUUID());
                for (int i = 0; i < a.size(); i++)
                {
                    var p = a.get(i);var q = b.get(i);
                    if (meshes.isEmpty())
                    { var bounds = actor.getBoundingBox();if (coupled) bounds = bounds.move(movementFrom.translation()).minmax(bounds.move(movementTo.translation()));if (p.mesh().intersects(p.frame(), q.frame(), bounds.inflate(error), .003)) return no(p.name() + " / bay actor " + actor.getUUID());continue; }
                    if (body != null && p.role() == NervOriginalCarrierR52.Role.SOLE_BEARING
                            && NervAirTransportManifestR52.same(p.frame().inverse().compose(root), q.frame().inverse().compose(endRoot)))
                    {
                        var pad = soles.variant(carrier.getUnitVariant()).stream().filter(s -> s.name().equals(p.name())).findFirst().orElse(null);
                        if (pad != null && CarrierFootBearingR53.permitsContact(soles, body,
                                movementFrom.compose(NervOwnerPlacementR52.actualRoot((EvaUnit01Entity)actor)), root, mounting, source,
                                pad.bone(), new NervFlightProofR52.ObstacleMesh(p.mesh(), p.frame()))) continue;
                    }
                    for (var m : meshes) if (hit(p, q, m.mesh(), coupled ? movementFrom.compose(m.frame()) : m.frame(), coupled ? movementTo.compose(m.frame()) : m.endFrame(), coupled ? 0 : error))
                        return no(p.name() + " / bay actor mesh " + actor.getUUID());
                }
            }
            for (int i = 0; i < a.size(); i++)
            {
                var p = a.get(i);var q = b.get(i);
                for (int j = i + 1; j < a.size(); j++)
                {
                    var r = a.get(j);var s = b.get(j);
                    // Rigid source joins retain their original relationship. A
                    // changing relationship is checked with both full surfaces.
                    if (NervAirTransportManifestR52.same(p.frame().inverse().compose(r.frame()), q.frame().inverse().compose(s.frame()))) continue;
                    if(CarrierBayLiftRailsR54.deckSeat(p,q,r,s,bay,root,endRoot)
                            ||CarrierBayLiftRailsR54.deckSeat(r,s,p,q,bay,root,endRoot))continue;
                    if (hit(p, q, r.mesh(), r.frame(), s.frame())) return no(p.name() + " / moving bay member " + r.name());
                }
                // Authored route translation uses the same diagnostic policy
                // as the rear guide. Independent bay actuators retain this check.
                if (directionFrom == null || NervTraversalPolicyR53.strict(level))
                {
                    for(var rail:bay.rails())if(rail.name().contains("/bank_foot_"))
                    {
                        if(CarrierBayTrayR53.railContact(p,q.frame(),bay,root,endRoot))continue;
                        if(hit(p,q,rail.mesh(),rail.frame(),rail.frame(),error))return no(p.name()+" / tray rail "+rail.name());
                    }
                    for (var fixed : NervLegacyCarrierRideR52.fixedPartsR52())
                        if (hit(p, q, fixed.mesh(), fixed.frame(), fixed.frame(), error)) return no(p.name() + " / original fixed rail " + fixed.name());
                    for (var fixed : CarrierTransferRailsR53.nearby(level, p.mesh().envelope(p.frame(), q.frame()).inflate(error)))
                    {
                        var steel = fixed.steel();
                        if (hit(p, q, steel.mesh(), steel.frame(), steel.frame(), error)) return no(p.name() + " / rear fixed rail " + fixed.name());
                    }
                }
            }
        }
        return new CarrierRearGuideMotionR53.Result(List.copyOf(boxes), null);
    }

    private static boolean supportedPair(ServerLevel level, NervCarrierPlatformEntity carrier, CarrierBayTrayR53.Bay bay,
            RigidTransform root, RigidTransform endRoot, Vec3 directionFrom, Vec3 directionTo,
            String leg, CarrierMountProfileR53.State mounting,float from,float to)
    {
        boolean same = root.equals(endRoot) && Objects.equals(directionFrom, directionTo);
        boolean firstBears = CarrierBayTrayR53.bears(bay, root,from);
        boolean lastBears = same&&from==to ? firstBears : CarrierBayTrayR53.bears(bay, endRoot,to);
        // Only this uninterrupted read-only call shares the tray readback.
        // Every later sweep/commit still sees current blocks and block entities.
        boolean trayReady = (firstBears || lastBears) && CarrierBayTrayR53.ready(level, bay);
        if (!supported(level, carrier, root, directionFrom, leg, mounting, firstBears && trayReady)) return false;
        return same&&from==to || supported(level, carrier, endRoot, directionTo, leg, mounting, lastBears && trayReady);
    }

    private static boolean supported(ServerLevel level, NervCarrierPlatformEntity carrier,
            RigidTransform root, Vec3 direction, String leg, CarrierMountProfileR53.State mounting, boolean trayReady)
    {
        return trayReady || leg != null && direction != null
                && CarrierRearGuideR53.finiteTransferCapture(level, root, direction, leg,
                        CarrierRearGuideR53.actualLift(carrier, 1), mounting);
    }

    private static List<NervOriginalCarrierR52.Part> parts(NervCarrierPlatformEntity carrier, RigidTransform root,
                                                          float rise, CarrierMountProfileR53.State mounting) throws IOException
    {
        return NervOriginalCarrierR52.partsAtR53(carrier.getUnitVariant(), root, rise,
                NervOriginalCarrierR52.guideUp(carrier), NervOriginalCarrierR52.actualRidePoseR52(carrier),
                NervOriginalCarrierR52.uprightDirectionR52(carrier, 1), NervOriginalCarrierR52.headSlideR53(carrier, 1),
                CarrierRearGuideR53.actualLift(carrier, 1), mounting);
    }

    private static boolean hit(NervOriginalCarrierR52.Part a, NervOriginalCarrierR52.Part b,
                               NervRigidMeshSweepR52 mesh, RigidTransform from, RigidTransform to)
    { return hit(a, b, mesh, from, to, 0); }

    private static boolean hit(NervOriginalCarrierR52.Part a, NervOriginalCarrierR52.Part b,
                               NervRigidMeshSweepR52 mesh, RigidTransform from, RigidTransform to, double error)
    {
        return a.mesh().envelope(a.frame(), b.frame()).inflate(error).intersects(mesh.envelope(from, to))
                && SOURCE_PAIRS.intersects(a.mesh(), a.frame(), b.frame(), mesh, from, to,
                        .003, new Vec3(error, error, error), null);
    }
    private CarrierBayMotionR53() { }
}

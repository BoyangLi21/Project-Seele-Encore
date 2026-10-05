package com.projectseele.world;

import com.projectseele.entity.EvaScale;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EvaDorsalProfile;
import com.projectseele.entity.EvaAirTransportR31;
import com.projectseele.entity.EvaBodyPose;
import com.projectseele.entity.EvaRifleKinematics;
import com.projectseele.entity.EvaShutdownR30;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Vector3f;

/**
 * Single coordinate authority for the canonical entry-plug and dorsal socket.
 *
 * <p>Plug frame P: +X right, +Y hatch/top, +Z from insertion tip toward the
 * occupied body, and -Z insertion. Socket frame S uses the same axes with +Z
 * pointing out of the EVA's back. Every marker and route is expressed in one
 * of these two frames; no screen-space yaw/pitch patches belong here.</p>
 */
public final class EntryPlugKinematics
{
    public static final double MODEL_TO_BLOCK =
            EvaScale.ENTRY_PLUG_RENDER_SCALE / 16.0D;
    /**
     * Final travel down the vertical dorsal socket.  The capsule body is ten
     * blocks long in P-space.  An 11-block lock travel seats the complete
     * body and its lower collar just inside the dorsal mouth; the old 9.25
     * value left roughly three quarters of a block visibly hanging outside.
     * The raked socket still leaves the insertion tip behind the torso centre
     * plane, so the extra travel cannot cross the front armour.
     */
    public static final double LOCK_DEPTH_BLOCKS = 11.0D;
    public static final double DOCK_PHASE_END = 0.45D;
    public static final double ALIGN_PHASE_END = 0.75D;
    /** Opposed pressure leaves hinge upward instead of floating sideways. */
    public static final float HATCH_OPEN_ANGLE_DEGREES = 82.0F;
    public static final float HATCH_LEAF_HALF_WIDTH_MODEL = 2.5F;

    public static final Vec3 BODY_OBB_CENTRE_P =
            new Vec3(0.0D, 0.0D, 5.0D);
    public static final Vec3 BODY_OBB_HALF_EXTENTS =
            new Vec3(1.2D, 1.2D, 5.15D);
    public static final Vec3 HATCH_PORTAL_HALF_EXTENTS_P =
            modelMarker(2.5D, 0.4D, 7.0D);
    public static final Vec3 HATCH_PORTAL_CENTRE_P =
            modelMarker(0.0D, 4.0D, 29.0D);
    public static final Vec3 PILOT_SEAT_P =
            modelMarker(0.0D, -2.0D, 31.0D);
    public static final Vec3 PILOT_EYE_P =
            modelMarker(0.0D, 0.8D, 34.5D);
    /**
     * The backrest rises towards the tail; feet point towards the insertion
     * tip. View and visible torso use this same seat-to-eye basis, including
     * when the crane turns the capsule away from its horizontal boarding pose.
     */
    public static final Vec3 PILOT_VIEW_FORWARD_P =
            new Vec3(0.0D, 3.5D, -2.8D).normalize();

    public static float pilotReclineRadiansR48()
    {
        Vec3 backrest=PILOT_EYE_P.subtract(PILOT_SEAT_P);
        return (float)Math.atan2(backrest.z,backrest.y);
    }
    public static final Vec3 PILOT_DISMOUNT_LEFT_P =
            modelMarker(-6.4D, 5.2D, 29.0D);
    public static final Vec3 PILOT_DISMOUNT_RIGHT_P =
            modelMarker(6.4D, 5.2D, 29.0D);
    /**
     * Crane eye slightly inside the capsule tail.  The 0.3-block overlap lets
     * the physical clamp visibly grip the shell instead of ending at a
     * mathematically coincident face that can render as a gap.
     */
    public static final Vec3 CRANE_ATTACHMENT_P =
            modelMarker(0.0D, 0.0D, 48.5D);

    /** Unit-01 compatibility values; per-airframe code uses its complete profile. */
    public static final double SOCKET_HEIGHT_BLOCKS = EvaDorsalProfile.byVariant(1).centreBlocks().y;
    public static final double SOCKET_REAR_BLOCKS = EvaDorsalProfile.byVariant(1).centreBlocks().z;
    private static final Vec3 WORLD_UP = new Vec3(0.0D, 1.0D, 0.0D);
    /** The bridge cradle holds the capsule almost horizontal (15 degrees). */
    private static final double DOCK_REAR_AXIS =
            0.9659258262890683D;
    private static final double DOCK_UP_AXIS = 0.25881904510252074D;
    /**
     * The production socket is vertical-dominant, not mathematically vertical.
     * A thirty-degree rearward rake follows the reviewed dorsal guide line.
     * The matching rear anchor keeps the aggressively inserted tip behind the
     * torso centre plane instead of allowing it to cross the chest.
     */

    private EntryPlugKinematics() {}

    public static RigidTransform socketTransform(EvaUnit01Entity unit)
    {return socketTransform(unit,1F);}

    /** Only the locked aerial assembly samples its shared render-time body frame. */
    public static RigidTransform socketTransform(EvaUnit01Entity unit,float partial)
    {
        if(EvaAirTransportR31.active(unit)||EvaShutdownR30.displayed(unit))return posedSocketTransform(unit,unit.level().isClientSide?Mth.clamp(partial,0,1):1F);
        // The retained NERV plant is rendered in its surveyed rail heading.
        // Looking around inside the capsule must not yaw the insertion axis.
        Vec3 rear = !unit.isExperimentalUnit()&&unit.isNervLogisticsLocked()
                ?rearDirectionForYaw(EvaUnit01Entity.SILO_BAY_YAW):unit.getRearDirection();
        var profile=EvaDorsalProfile.of(unit);Vec3 marker=profile.centreBlocks();
        RigidTransform orientation = verticalSocketOrientation(rear,profile);
        Vec3 origin = unit.position()
                .add(rear.scale(marker.z))
                .add(rear.cross(WORLD_UP).scale(marker.x))
                .add(0.0D, marker.y, 0.0D);
        RigidTransform normal=new RigidTransform(origin,
                orientation.qx(), orientation.qy(),
                orientation.qz(), orientation.qw());
        if(unit.isFirstBattleActive()&&com.projectseele.entity.FirstBattleClip.ready())
        {
            var signals=unit.firstBattleSignals();var spec=signals.spec(unit);float t=signals.time(unit,1);
            Vec3 p=com.projectseele.entity.FirstBattleClip.point(spec,true,"socket_blocks",t);
            Vec3 outward=com.projectseele.entity.FirstBattleClip.point(spec,true,"socket_outward_blocks",t).subtract(p).normalize();
            Vec3 up=com.projectseele.entity.FirstBattleClip.point(spec,true,"socket_up_blocks",t).subtract(p).normalize();
            RigidTransform authored=RigidTransform.fromAxes(p,up.cross(outward).normalize(),up,outward);
            return authored.interpolate(normal,com.projectseele.entity.FirstBattleClip.smooth((t-21.6F)/1.4F));
        }
        return normal;
    }

    public static RigidTransform posedSocketTransform(EvaUnit01Entity unit,float partial)
    {
        var profile=EvaDorsalProfile.of(unit);
        var body=EvaBodyPose.sample(unit,partial);
        Matrix4f chest=EvaRifleKinematics.world(unit,partial).mul(body.matrix("torso_upper"));
        Vec3 centre=profile.centreModel(),out=profile.outwardModel(),hinge=profile.hingeAxisModel();
        // Profile coordinates are Gecko model units. The shared pose uses
        // reflected X and 1/16 units; world() applies RENDER_SCALE exactly once.
        Vector3f point=chest.transformPosition(new Vector3f((float)-centre.x,(float)centre.y,(float)centre.z).div(16));
        Vector3f axis=chest.transformDirection(new Vector3f((float)-out.x,(float)out.y,(float)out.z)).normalize();
        Vector3f hatchUp=chest.transformDirection(new Vector3f((float)-hinge.x,(float)hinge.y,(float)hinge.z)).normalize();
        Vec3 outward=new Vec3(axis.x,axis.y,axis.z),up=new Vec3(hatchUp.x,hatchUp.y,hatchUp.z);
        return RigidTransform.fromAxes(new Vec3(point.x,point.y,point.z),up.cross(outward),up,outward);
    }

    /**
     * Authored cage pose whose hatch marker, not entity centre, lands at the
     * boarding point.  The insertion tip points toward the EVA while the
     * booster/tail points outward and only slightly upward.  The hatch face is
     * the orthogonal upper side, so the capsule lies nearly flat on the bridge
     * and its two doors lift above the pilot instead of opening sideways.
     */
    public static RigidTransform dockTransform(EvaUnit01Entity unit,
                                                Vec3 hatchCentreWorld)
    {
        return dockTransform(hatchCentreWorld, unit.getRearDirection());
    }

    /** UN bridges have their own saved yaw; a parked cradle never follows live body interpolation. */
    public static RigidTransform dockTransform(Vec3 hatchCentreWorld,float fixedYaw)
    {
        return dockTransform(hatchCentreWorld,rearDirectionForYaw(fixedYaw));
    }

    /**
     * Authored wet-cage dock.  Unlike the compatibility overload above this
     * frame does not read the airframe's live head/body interpolation.  The
     * crane, bridge and pressure hatch are civil works fixed at the reviewed
     * silo yaw, so allowing even a fraction of a degree of entity yaw into
     * this transform makes a parked capsule visibly roll around its cable.
     */
    public static RigidTransform cageDockTransform(Vec3 hatchCentreWorld)
    {
        return dockTransform(hatchCentreWorld,
                rearDirectionForYaw(EvaUnit01Entity.SILO_BAY_YAW));
    }

    private static RigidTransform dockTransform(Vec3 hatchCentreWorld,
                                                 Vec3 hatchFacing)
    {
        Vec3 rear = hatchFacing.multiply(1.0D, 0.0D, 1.0D)
                .normalize();
        RigidTransform orientation = dockOrientation(rear);
        Vec3 tip = hatchCentreWorld.subtract(
                orientation.transformVector(HATCH_PORTAL_CENTRE_P));
        return new RigidTransform(tip,
                orientation.qx(), orientation.qy(),
                orientation.qz(), orientation.qw());
    }

    /** Stable near-horizontal bridge cradle, independent of the live EVA. */
    private static RigidTransform dockOrientation(Vec3 rear)
    {
        Vec3 outward = rear.scale(DOCK_REAR_AXIS)
                .add(WORLD_UP.scale(DOCK_UP_AXIS)).normalize();
        Vec3 hatchUp = WORLD_UP.subtract(
                outward.scale(WORLD_UP.dot(outward))).normalize();
        Vec3 right = hatchUp.cross(outward).normalize();
        return RigidTransform.fromAxes(
                Vec3.ZERO, right, hatchUp, outward);
    }

    /**
     * Dorsal insertion frame. +Z points upward with a slight rearward rake,
     * therefore the plug's -Z insertion tip travels down and forward through
     * the two guide points behind the head. The horizontal rear vector fixes
     * roll, so all three cages present the hatch on the same side.
     */
    private static RigidTransform verticalSocketOrientation(Vec3 rear,EvaDorsalProfile.Profile profile)
    {
        Vec3 horizontalRear = rear.multiply(1.0D, 0.0D, 1.0D).normalize();
        Vec3 outward = horizontalRear.scale(profile.outwardModel().z)
                .add(WORLD_UP.scale(profile.outwardModel().y)).normalize();
        Vec3 hatchUp = WORLD_UP.subtract(
                outward.scale(WORLD_UP.dot(outward))).normalize();
        Vec3 right = hatchUp.cross(outward).normalize();
        return RigidTransform.fromAxes(
                Vec3.ZERO, right, hatchUp, outward);
    }

    /**
     * Evaluates the complete SUSPENDED -> APPROACH -> MOUTH -> LOCKED route.
     * Translation and rotation are both authored in socket space.
     */
    public static RigidTransform insertionTransform(
            EvaUnit01Entity unit, Vec3 hatchCentreWorld, double progress)
    {
        return insertionTransform(unit,
                dockTransform(unit, hatchCentreWorld), progress);
    }

    /**
     * Evaluates insertion from an already-authoritative world-space dock.
     * Wet-cage logistics uses {@link #cageDockTransform(Vec3)} here so the
     * start frame cannot be re-parented to a moving EVA before socket lock.
     */
    public static RigidTransform insertionTransform(
            EvaUnit01Entity unit, RigidTransform dockWorld, double progress)
    {
        return insertionTransform(unit, dockWorld, progress, progress);
    }

    /**
     * Evaluates one insertion pose.  The second clock remains in the method
     * signature for saved-state compatibility; the physical route now uses a
     * single continuous clock so translation and standing rotation cannot
     * fight each other or create a one-frame pivot kick.
     */
    public static RigidTransform insertionTransform(
            EvaUnit01Entity unit, RigidTransform dockWorld,
            double translationProgress, double rotationProgress)
    {
        double linear = Mth.clamp(translationProgress, 0.0D, 1.0D);
        RigidTransform socket = socketTransform(unit);
        RigidTransform dockInSocket = socket.inverse().compose(
                dockWorld);
        /*
         * Once upright, three blocks above the mouth give the lower insertion
         * tip a visible lead-in while keeping the 10-block capsule below the
         * wet-cage roof.  Interpolation from dockInSocket also performs the
         * one continuous flat-to-vertical presentation; there is no discrete
         * face flip at the mouth.
         */
        RigidTransform approachInSocket = new RigidTransform(
                new Vec3(0.0D, 0.0D, 3.0D),
                0.0F, 0.0F, 0.0F, 1.0F);
        RigidTransform mouthInSocket = RigidTransform.identity();
        RigidTransform plugInSocket;
        if (linear <= DOCK_PHASE_END)
        {
            double phase = smoothstep(linear / DOCK_PHASE_END);
            plugInSocket = dockInSocket.interpolate(
                    approachInSocket, phase);
        }
        else if (linear <= ALIGN_PHASE_END)
        {
            double phase = smoothstep((linear - DOCK_PHASE_END)
                    / (ALIGN_PHASE_END - DOCK_PHASE_END));
            plugInSocket = approachInSocket.interpolate(
                    mouthInSocket, phase);
        }
        else
        {
            double phase = smoothstep((linear - ALIGN_PHASE_END)
                    / (1.0D - ALIGN_PHASE_END));
            plugInSocket = new RigidTransform(
                    new Vec3(0.0D, 0.0D,
                            -LOCK_DEPTH_BLOCKS * phase),
                    0.0F, 0.0F, (float)Math.sin(Math.PI*phase), (float)Math.cos(Math.PI*phase));
        }
        return socket.compose(plugInSocket);
    }

    /** Horizontal rear vector matching vanilla yaw without reading an entity. */
    private static Vec3 rearDirectionForYaw(float yawDegrees)
    {
        double yaw = Math.toRadians(yawDegrees);
        return new Vec3(Math.sin(yaw), 0.0D, -Math.cos(yaw)).normalize();
    }

    public static RigidTransform lockedTransform(EvaUnit01Entity unit)
    {return lockedTransform(unit,1F);}

    public static RigidTransform lockedTransform(EvaUnit01Entity unit,float partial)
    {
        RigidTransform socket=EvaShutdownR30.displayed(unit)
                ?posedSocketTransform(unit,unit.level().isClientSide?Mth.clamp(partial,0,1):1F)
                :socketTransform(unit,partial);
        return socket.compose(new RigidTransform(
                new Vec3(0.0D, 0.0D, -LOCK_DEPTH_BLOCKS),
                0.0F, 0.0F, 0.0F, 1.0F));
    }

    /**
     * Conservative world AABB of one oriented local-space box. The renderer
     * still uses the exact quaternion; this envelope exists only for server
     * interlocks and deliberately errs on the side of stopping machinery.
     */
    public static AABB worldBounds(RigidTransform transform, Vec3 centre,
                                   Vec3 halfExtents)
    {
        double minX = Double.POSITIVE_INFINITY;
        double minY = Double.POSITIVE_INFINITY;
        double minZ = Double.POSITIVE_INFINITY;
        double maxX = Double.NEGATIVE_INFINITY;
        double maxY = Double.NEGATIVE_INFINITY;
        double maxZ = Double.NEGATIVE_INFINITY;
        for (int sx : new int[] {-1, 1})
        {
            for (int sy : new int[] {-1, 1})
            {
                for (int sz : new int[] {-1, 1})
                {
                    Vec3 corner = transform.transformPoint(centre.add(
                            halfExtents.x * sx, halfExtents.y * sy,
                            halfExtents.z * sz));
                    minX = Math.min(minX, corner.x);
                    minY = Math.min(minY, corner.y);
                    minZ = Math.min(minZ, corner.z);
                    maxX = Math.max(maxX, corner.x);
                    maxY = Math.max(maxY, corner.y);
                    maxZ = Math.max(maxZ, corner.z);
                }
            }
        }
        return new AABB(minX, minY, minZ, maxX, maxY, maxZ);
    }

    /** Samples rotation as well as translation, so a turning capsule cannot
     * cut a corner outside the two endpoint AABBs. */
    public static AABB sweptBodyBounds(RigidTransform from,
                                       RigidTransform to)
    {
        AABB sweep = worldBounds(from, BODY_OBB_CENTRE_P,
                BODY_OBB_HALF_EXTENTS);
        for (int sample = 1; sample <= 4; sample++)
        {
            RigidTransform pose = from.interpolate(to, sample / 4.0D);
            sweep = sweep.minmax(worldBounds(pose, BODY_OBB_CENTRE_P,
                    BODY_OBB_HALF_EXTENTS));
        }
        return sweep;
    }

    /** Conservative volume swept by both upward-hinged pressure leaves. */
    public static AABB hatchClosingSweep(RigidTransform transform)
    {
        double rise = (HATCH_LEAF_HALF_WIDTH_MODEL + 0.5D)
                * MODEL_TO_BLOCK;
        Vec3 expanded = new Vec3(
                HATCH_PORTAL_HALF_EXTENTS_P.x + 0.25D,
                HATCH_PORTAL_HALF_EXTENTS_P.y + rise,
                HATCH_PORTAL_HALF_EXTENTS_P.z);
        return worldBounds(transform, HATCH_PORTAL_CENTRE_P, expanded);
    }

    private static Vec3 modelMarker(double x, double y, double z)
    {
        return new Vec3(x * MODEL_TO_BLOCK,
                y * MODEL_TO_BLOCK, z * MODEL_TO_BLOCK);
    }

    private static double smoothstep(double value)
    {
        double clamped = Mth.clamp(value, 0.0D, 1.0D);
        return clamped * clamped * (3.0D - 2.0D * clamped);
    }
}

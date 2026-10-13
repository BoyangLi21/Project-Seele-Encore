package com.projectseele.world;

import java.util.Map;
import java.util.List;
import java.util.WeakHashMap;

import com.projectseele.registry.ModFluids;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.Mth;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.AttachFace;
import net.minecraft.world.phys.Vec3;

/**
 * Runtime anchors and bounded moving scenery for the three S19 EVA lines.
 *
 * <p>The immutable cage/silo plans own civil construction. This class may
 * change only the explicitly swept bridge, LCL and carrier cells inside a
 * completed unit owner. It never derives coordinates from the retired
 * integrated-map origin.</p>
 */
public final class FacilityV2EvaRuntime
{
    public static final int BRIDGE_SEGMENTS = 9;
    public static final int LCL_SHOULDER_LAYERS = 44;
    public static final int CARRIER_HALF_EXTENT = 14;

    private static final int[] LINE_X = {-389, 0, 389};
    private static final int CAGE_Z = 804;
    private static final int CARRIER_Y = -465;
    private static final int SILO_Z = 968;
    private static final int LCL_BOTTOM_Y = -464;
    private static final int LCL_TOP_Y = -424;
    private static final int BRIDGE_Y = -409;
    private static final int OBSERVATION_WALK_Y = -408;
    private static final int BRIDGE_MIN_Z = 820;
    private static final int BRIDGE_MAX_Z = 832;
    private static final int BRIDGE_MAX_X = 58;
    private static final int CRANE_TROLLEY_Y = -343;
    /** Visible hoist recovery speed after the capsule locks into the EVA. */
    private static final int CRANE_STOW_BLOCKS_PER_TICK = 2;
    private static final int CRANE_MIN_Y = -430;
    private static final int CRANE_MIN_Z_OFFSET = 2;
    private static final int CRANE_MAX_Z_OFFSET = 30;
    private static final int CRANE_HALF_SPAN = 6;
    private static final int CRANE_DEPTH = 1;
    /** Width used by the retired full-span trolley persisted in older saves. */
    private static final int CRANE_LEGACY_HALF_SPAN = 23;
    private static final int CRANE_CABLE_X = 3;

    private static final BlockState AIR = Blocks.AIR.defaultBlockState();
    private static final BlockState FLOOR =
            Blocks.POLISHED_DEEPSLATE.defaultBlockState();
    private static final BlockState LIGHT =
            Blocks.SEA_LANTERN.defaultBlockState();
    private static final BlockState RAIL =
            Blocks.IRON_BARS.defaultBlockState();
    private static final BlockState CARRIER =
            Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState();
    private static final BlockState CARRIER_RIM =
            Blocks.IRON_BLOCK.defaultBlockState();
    private static final BlockState CRANE_BEAM =
            Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState();
    private static final BlockState CRANE_CABLE =
            Blocks.CHAIN.defaultBlockState();
    private static final BlockState CONTROL_BUTTON =
            Blocks.STONE_BUTTON.defaultBlockState()
                    .setValue(ButtonBlock.FACE, AttachFace.FLOOR)
                    .setValue(ButtonBlock.FACING, Direction.SOUTH);
    private static final String[] RUNTIME_OWNER_SUFFIXES = {
            "_CAGE", "_CARRIER", "_SWITCHYARD", "_SILO", "_SURFACE_HEAD"
    };
    private static final Map<ServerLevel, CraneFrame[]> CRANE_FRAMES =
            new WeakHashMap<>();

    private FacilityV2EvaRuntime() {}

    public static boolean ready(ServerLevel level, int variant)
    {
        if(NervRouteRuntimeR52.claimed(level))return false;
        if (!FacilityWorldPolicy.isCleanRebuild(level.getServer())
                || variant < 0 || variant >= LINE_X.length)
        {
            return false;
        }
        FacilityV2SavedData data = FacilityV2SavedData.get(level);
        if (!data.commissioned())
        {
            return false;
        }
        String unit = unit(variant);
        return complete(data, List.of(
                "MECH_ACCESS_SPINE",
                "MECH_AIRLOCK_LINK",
                "MECH_PERSONNEL_TRUNK",
                "MECH_OBS_LINK_" + unit,
                "UNIT" + unit + "_CAGE",
                "UNIT" + unit + "_CARRIER",
                "UNIT" + unit + "_SWITCHYARD",
                "UNIT" + unit + "_SILO",
                "UNIT" + unit + "_SURFACE_HEAD"));
    }

    /**
     * The crane is a transient entity visual and does not depend on every
     * civil-zone receipt being complete.  A clean S20 rebuild must never fall
     * back to the retired block-painting crane merely because one unrelated
     * facility zone is still awaiting commissioning.
     */
    public static boolean supportsPlugCrane(ServerLevel level, int variant)
    {
        if(NervRouteRuntimeR52.claimed(level))return false;
        return FacilityWorldPolicy.isCleanRebuild(level.getServer())
                && variant >= 0 && variant < LINE_X.length;
    }

    public static boolean readyAll(ServerLevel level)
    {
        return ready(level, 0) && ready(level, 1) && ready(level, 2);
    }

    public static BlockPos hangarBed(ServerLevel level, int variant)
    {
        FacilitySchemaV2.ResolvedManifest manifest = manifest(level);
        return manifest.centre().offset(
                lineX(variant), CARRIER_Y, CAGE_Z);
    }

    public static BlockPos lowerLiftBed(ServerLevel level, int variant)
    {
        FacilitySchemaV2.ResolvedManifest manifest = manifest(level);
        return manifest.centre().offset(
                lineX(variant), CARRIER_Y, SILO_Z);
    }

    public static BlockPos surfaceLiftBed(ServerLevel level, int variant)
    {
        FacilitySchemaV2.ResolvedManifest manifest = manifest(level);
        return manifest.centre().offset(
                lineX(variant), manifest.surfaceY(), SILO_Z);
    }

    /**
     * World-space centre of the open hatch while the capsule is suspended.
     * It meets the retractable rear bridge at human eye height.
     */
    public static Vec3 plugRestPosition(ServerLevel level, int variant)
    {
        BlockPos bed = hangarBed(level, variant);
        return new Vec3(bed.getX() + 0.5D, -405.8D,
                bed.getZ() + 28.5D);
    }

    public static BlockPos prepareControl(ServerLevel level, int variant)
    {
        BlockPos bed = hangarBed(level, variant);
        return new BlockPos(bed.getX() - 2, -407,
                bed.getZ() - 46);
    }

    public static BlockPos statusControl(ServerLevel level, int variant)
    {
        BlockPos bed = hangarBed(level, variant);
        return new BlockPos(bed.getX() + 2, -407,
                bed.getZ() - 46);
    }

    public static BlockPos cancelControl(ServerLevel level, int variant)
    {
        BlockPos bed = hangarBed(level, variant);
        return new BlockPos(bed.getX(), -407,
                bed.getZ() - 46);
    }

    public static BlockPos powerPylon(ServerLevel level, int variant)
    {
        return hangarBed(level, variant).offset(54, 41, 4);
    }

    public static BlockPos boardingPosition(ServerLevel level, int variant)
    {
        BlockPos bed = hangarBed(level, variant);
        return new BlockPos(bed.getX() + 2, -408, bed.getZ() + 27);
    }

    public static BlockPos rescueFootPosition(
            ServerLevel level, int variant)
    {
        return statusControl(level, variant).above();
    }

    /**
     * Installs the tiny dynamic control surface separately from the immutable
     * cage shell. This also upgrades an already-built a1 cage without
     * repainting or rebuilding its authored interior.
     */
    public static void ensureControls(ServerLevel level, int variant)
    {
        if(NervRouteRuntimeR52.claimed(level))return;
        if (!supportsPlugCrane(level, variant))
        {
            return;
        }
        FacilitySchemaV2.IntBox[] owners = owners(level, variant);
        BlockPos[] controls = {
                prepareControl(level, variant),
                cancelControl(level, variant),
                statusControl(level, variant)
        };
        for (int index = 0; index < controls.length; index++)
        {
            BlockPos control = controls[index];
            setOwned(level, owners, control.below(),
                    index == 1
                            ? Blocks.RED_CONCRETE.defaultBlockState()
                            : Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState());
            setOwned(level, owners, control, CONTROL_BUTTON);
            if (level.getBlockState(control.above()).getBlock()
                    instanceof ButtonBlock)
            {
                setOwned(level, owners, control.above(), AIR);
            }
        }
        ensureBoardingDoor(level, variant, owners);
    }

    /**
     * Backports the a3 observation-room opening into an already commissioned
     * a1/a2 cage.  This is deliberately seven columns by seven air cells,
     * not a zone rebuild: the immutable room, bridge and receipt remain
     * untouched while their missing physical connection is restored.
     */
    private static void ensureBoardingDoor(
            ServerLevel level, int variant,
            FacilitySchemaV2.IntBox[] owners)
    {
        BlockPos bed = hangarBed(level, variant);
        int wallZ = bed.getZ() - 29;
        for (int dx = 44; dx <= 50; dx++)
        {
            BlockPos floor = new BlockPos(
                    bed.getX() + dx, OBSERVATION_WALK_Y - 1, wallZ);
            setOwned(level, owners, floor, FLOOR);
            setOwned(level, owners, floor.south(), FLOOR);
            for (int y = OBSERVATION_WALK_Y;
                 y <= OBSERVATION_WALK_Y + 6; y++)
            {
                setOwned(level, owners,
                        new BlockPos(bed.getX() + dx, y, wallZ), AIR);
            }
        }
    }

    public static boolean isInsideAssignedCage(
            ServerLevel level, Vec3 position, int variant)
    {
        if (!supportsPlugCrane(level, variant))
        {
            return false;
        }
        FacilitySchemaV2.IntBox owner = manifest(level)
                .requireZone("UNIT" + unit(variant) + "_CAGE").owner();
        return position.x >= owner.minX() + 2
                && position.x < owner.maxX() - 2
                && position.y >= owner.minY() + 1
                && position.y < owner.maxY() - 1
                && position.z >= owner.minZ() + 2
                && position.z < owner.maxZ() - 2;
    }

    public static int lclLevel(ServerLevel level, int variant)
    {
        if(NervRouteRuntimeR52.claimed(level))return -1;
        BlockPos bed = hangarBed(level, variant);
        int visible = 0;
        for (int y = LCL_BOTTOM_Y; y <= LCL_TOP_Y; y++)
        {
            if (!level.getFluidState(new BlockPos(
                    bed.getX(), y, bed.getZ())).isEmpty())
            {
                visible++;
            }
        }
        if (visible == 0)
        {
            return 0;
        }
        return Math.min(LCL_SHOULDER_LAYERS,
                visible + (LCL_SHOULDER_LAYERS
                        - (LCL_TOP_Y - LCL_BOTTOM_Y + 1)));
    }

    public static void setLclLayer(ServerLevel level, int variant,
                                   int layer, boolean filled)
    {
        if(NervRouteRuntimeR52.claimed(level))return;
        int y = LCL_BOTTOM_Y + layer - 1;
        if (!ready(level, variant) || y < LCL_BOTTOM_Y || y > LCL_TOP_Y)
        {
            return;
        }
        BlockPos bed = hangarBed(level, variant);
        FacilitySchemaV2.IntBox[] owners = owners(level, variant);
        BlockState state = filled
                ? ModFluids.LCL_SOURCE.get().defaultFluidState()
                        .createLegacyBlock()
                : AIR;
        for (int dx = -44; dx <= 44; dx++)
        {
            for (int dz = -32; dz <= 32; dz++)
            {
                double basin = square(dx / 44.0D)
                        + square(dz / 32.0D);
                if (basin <= 1.0D)
                {
                    setOwned(level, owners,
                            new BlockPos(bed.getX() + dx, y,
                                    bed.getZ() + dz), state);
                }
            }
        }
    }

    public static int drainLclEnvelope(ServerLevel level, int variant)
    {
        if(NervRouteRuntimeR52.claimed(level))return -1;
        int remaining = 0;
        for (int layer = LCL_SHOULDER_LAYERS; layer >= 1; layer--)
        {
            int y = LCL_BOTTOM_Y + layer - 1;
            if (y > LCL_TOP_Y)
            {
                continue;
            }
            BlockPos bed = hangarBed(level, variant);
            if (!level.getFluidState(new BlockPos(
                    bed.getX(), y, bed.getZ())).isEmpty())
            {
                setLclLayer(level, variant, layer, false);
                remaining = layer - 1;
                break;
            }
        }
        return remaining;
    }

    /**
     * Restores the physical wet-cage basin after an explicit canonical reset
     * or a safe PARKED-receipt repair. The logical 44-step gauge includes
     * three timing-only shoulder steps above the 41-block-deep basin, so this
     * method writes the real fluid envelope directly instead of pretending
     * those extra steps are world layers.
     */
    public static void restoreLclEnvelope(ServerLevel level, int variant)
    {
        if(NervRouteRuntimeR52.claimed(level))return;
        if (!ready(level, variant))
        {
            return;
        }
        BlockPos bed = hangarBed(level, variant);
        boolean visiblyFull = true;
        for (int sampleY = LCL_BOTTOM_Y;
             sampleY <= LCL_TOP_Y && visiblyFull; sampleY++)
        {
            for (int[] sample : new int[][] {
                    {0, 0}, {-20, 0}, {20, 0}, {0, -16}, {0, 16}})
            {
                if (level.getFluidState(bed.offset(
                        sample[0], sampleY - bed.getY(),
                        sample[1])).isEmpty())
                {
                    visiblyFull = false;
                    break;
                }
            }
        }
        if (visiblyFull)
        {
            return;
        }
        FacilitySchemaV2.IntBox[] owners = owners(level, variant);
        BlockState lcl = ModFluids.LCL_SOURCE.get().defaultFluidState()
                .createLegacyBlock();
        for (int y = LCL_BOTTOM_Y; y <= LCL_TOP_Y; y++)
        {
            for (int dx = -44; dx <= 44; dx++)
            {
                for (int dz = -32; dz <= 32; dz++)
                {
                    double basin = square(dx / 44.0D)
                            + square(dz / 32.0D);
                    if (basin <= 1.0D)
                    {
                        setOwned(level, owners,
                                new BlockPos(bed.getX() + dx, y,
                                        bed.getZ() + dz), lcl);
                    }
                }
            }
        }
    }

    public static void setBoardingBridgeExtension(
            ServerLevel level, int variant, int segments)
    {
        if(NervRouteRuntimeR52.claimed(level))return;
        if (!ready(level, variant))
        {
            return;
        }
        int wanted = Math.max(0, Math.min(BRIDGE_SEGMENTS, segments));
        BlockPos bed = hangarBed(level, variant);
        FacilitySchemaV2.ResolvedManifest manifest = manifest(level);
        FacilitySchemaV2.IntBox[] owners = owners(manifest, variant);
        for (int localX = 0; localX <= BRIDGE_MAX_X; localX++)
        {
            int segment = Math.min(BRIDGE_SEGMENTS - 1,
                    localX * BRIDGE_SEGMENTS / (BRIDGE_MAX_X + 1));
            boolean present = segment < wanted;
            for (int localZ = BRIDGE_MIN_Z; localZ <= BRIDGE_MAX_Z; localZ++)
            {
                int worldZ = manifest.centre().getZ() + localZ;
                BlockPos floor = new BlockPos(
                        bed.getX() + localX, BRIDGE_Y, worldZ);
                BlockState floorState = Math.floorMod(
                        localX + worldZ, 10) <= 1 ? LIGHT : FLOOR;
                // The canonical capsule is 1.6 blocks wide, and each hatch
                // leaf travels another 0.92 blocks while open. Keep a true
                // five-block service well around it instead of letting the
                // bridge floor cut through the shell and moving doors.
                boolean capsuleWell = localX <= 2
                        && worldZ >= bed.getZ() + 26
                        && worldZ <= bed.getZ() + 30;
                setOwned(level, owners, floor,
                        present && !capsuleWell ? floorState : AIR);
                boolean edge = localZ == BRIDGE_MIN_Z
                        || localZ == BRIDGE_MAX_Z;
                if (edge)
                {
                    setOwned(level, owners, floor.above(),
                            present ? RAIL : AIR);
                }
                setOwned(level, owners, floor.above(2), AIR);
            }
        }
    }

    public static void setCarrier(ServerLevel level, int variant,
                                  BlockPos centre, boolean present)
    {
        if(NervRouteRuntimeR52.claimed(level))return;
        if (!ready(level, variant))
        {
            return;
        }
        FacilitySchemaV2.IntBox[] owners = owners(level, variant);
        for (int dx = -CARRIER_HALF_EXTENT;
             dx <= CARRIER_HALF_EXTENT; dx++)
        {
            for (int dz = -CARRIER_HALF_EXTENT;
                 dz <= CARRIER_HALF_EXTENT; dz++)
            {
                boolean rim = Math.abs(dx) == CARRIER_HALF_EXTENT
                        || Math.abs(dz) == CARRIER_HALF_EXTENT;
                BlockState platform = dx == 0 && dz == 0
                        ? Blocks.LODESTONE.defaultBlockState()
                        : (rim ? CARRIER_RIM : CARRIER);
                setOwned(level, owners, centre.offset(dx, 0, dz),
                        present ? platform
                                : carrierTrackState(dx, dz));
            }
        }
    }

    /** Mechanical guideway left visible whenever the transfer deck departs. */
    private static BlockState carrierTrackState(int dx, int dz)
    {
        if (Math.abs(dx) == 5)
        {
            return Math.floorMod(dz, 8) == 0
                    ? LIGHT : Blocks.IRON_BLOCK.defaultBlockState();
        }
        if (Math.abs(dx) <= 10 && Math.floorMod(dz, 6) == 0)
        {
            return Blocks.CUT_COPPER.defaultBlockState();
        }
        if (dx == 0)
        {
            return Blocks.POLISHED_BLACKSTONE.defaultBlockState();
        }
        return FLOOR;
    }

    public static void restoreStaticCarrier(ServerLevel level, int variant,
                                            BlockPos centre)
    {
        if(NervRouteRuntimeR52.claimed(level))return;
        setCarrier(level, variant, centre, true);
    }

    /** Floor-only guideway upgrade for already-commissioned clean worlds. */
    public static void ensureTransportGuideway(ServerLevel level, int variant,
                                               BlockPos start, BlockPos end)
    {
        if(NervRouteRuntimeR52.claimed(level))return;
        if (!ready(level, variant) || start.getX() != end.getX()
                || start.getY() != end.getY())
        {
            return;
        }
        FacilitySchemaV2.IntBox[] owners = owners(level, variant);
        int minZ = Math.min(start.getZ(), end.getZ());
        int maxZ = Math.max(start.getZ(), end.getZ());
        for (int z = minZ; z <= maxZ; z++)
        {
            int relativeZ = z - start.getZ();
            boolean sleeper = Math.floorMod(relativeZ, 6) == 0;
            for (int dx = -10; dx <= 10; dx++)
            {
                if (Math.abs(dx) != 5 && dx != 0 && !sleeper)
                {
                    continue;
                }
                BlockState state;
                if (Math.abs(dx) == 5)
                {
                    state = Math.floorMod(relativeZ, 8) == 0
                            ? LIGHT : Blocks.IRON_BLOCK.defaultBlockState();
                }
                else if (sleeper)
                {
                    state = Blocks.CUT_COPPER.defaultBlockState();
                }
                else
                {
                    state = Blocks.POLISHED_BLACKSTONE.defaultBlockState();
                }
                setOwned(level, owners,
                        new BlockPos(start.getX() + dx, start.getY(), z), state);
            }
        }
        setOwned(level, owners, start, Blocks.LODESTONE.defaultBlockState());
        setOwned(level, owners, end, Blocks.LODESTONE.defaultBlockState());
    }

    /**
     * The S19 civil plan deliberately leaves a full-height clear portal. The
     * first playable slice keeps that portal open rather than synthesising a
     * giant instant shutter; the later moving-door entity will own this hook.
     */
    public static void setGate(ServerLevel level, int variant, boolean open)
    {
        // Intentionally no block write.
    }

    /**
     * Drives the visible bridge crane inside the cage's reserved overhead
     * volume. The authored rails remain immutable; only one cross-trolley and
     * two chain drops move. Updating a frame changes roughly one hundred
     * blocks rather than repainting the complete 60-block-high mechanism.
     */
    public static void setPlugCrane(ServerLevel level, int variant,
                                    double craneEyeY, double craneEyeZ,
                                    boolean travelling)
    {
        if(NervRouteRuntimeR52.claimed(level))return;
        if (!ready(level, variant))
        {
            return;
        }
        BlockPos bed = hangarBed(level, variant);
        // A block occupies [floor(n), floor(n)+1). Snapping upward put the
        // bottom clamp beside the model-space tail marker and left a visible
        // air seam. Floor both axes so the marker is physically inside the
        // terminal clamp/collar volume.
        int trolleyZ = Mth.clamp(Mth.floor(craneEyeZ),
                bed.getZ() + CRANE_MIN_Z_OFFSET,
                bed.getZ() + CRANE_MAX_Z_OFFSET);
        int cableBottomY = Mth.clamp(Mth.floor(craneEyeY),
                CRANE_MIN_Y, CRANE_TROLLEY_Y - 1);
        CraneFrame[] frames = CRANE_FRAMES.computeIfAbsent(
                level, ignored -> new CraneFrame[LINE_X.length]);
        CraneFrame previous = frames[variant];
        if (previous == null)
        {
            sweepOrphanCrane(level, variant);
        }
        CraneFrame wanted = new CraneFrame(trolleyZ, cableBottomY);
        frames[variant] = wanted;
        NervCarrierVisuals.updatePlugCrane(level, variant,
                bed.getX(), CRANE_TROLLEY_Y, wanted.z(), wanted.bottomY());
    }

    public static void stowPlugCrane(ServerLevel level, int variant)
    {
        if(NervRouteRuntimeR52.claimed(level))return;
        if (!ready(level, variant))
        {
            return;
        }
        CraneFrame[] frames = CRANE_FRAMES.computeIfAbsent(
                level, ignored -> new CraneFrame[LINE_X.length]);
        CraneFrame previous = frames[variant];
        if (previous == null)
        {
            /*
             * A save can contain more than one pre-upgrade yoke while the
             * process-local frame table is empty.  Recovering only the first
             * one left its siblings in place and then painted another frame.
             * Sweep the complete dedicated crane lane once and publish one
             * canonical compact trolley instead.
             */
            previous = findPersistedCraneFrame(level, variant);
            sweepOrphanCrane(level, variant);
            if (previous == null)
            {
                CraneFrame compact = new CraneFrame(
                        hangarBed(level, variant).getZ()
                                + CRANE_MAX_Z_OFFSET,
                        CRANE_TROLLEY_Y - 2);
                frames[variant] = compact;
                NervCarrierVisuals.updatePlugCrane(level, variant,
                        hangarBed(level, variant).getX(), CRANE_TROLLEY_Y,
                        compact.z(), compact.bottomY());
                return;
            }
            frames[variant] = previous;
        }
        int nextBottomY = Math.min(CRANE_TROLLEY_Y - 2,
                previous.bottomY() + CRANE_STOW_BLOCKS_PER_TICK);
        CraneFrame stowed = new CraneFrame(previous.z(), nextBottomY);
        if (stowed.equals(previous))
        {
            NervCarrierVisuals.updatePlugCrane(level, variant,
                    hangarBed(level, variant).getX(), CRANE_TROLLEY_Y,
                    previous.z(), previous.bottomY());
            return;
        }
        // Move the visible yoke upward in small deterministic steps.  The
        // logistics PLUG_LOCKING phase calls this every tick, so the hoist
        // clears the transfer lane continuously instead of teleporting from
        // the seated capsule to its ceiling frame.
        frames[variant] = stowed;
        NervCarrierVisuals.updatePlugCrane(level, variant,
                hangarBed(level, variant).getX(), CRANE_TROLLEY_Y,
                stowed.z(), stowed.bottomY());
    }

    /**
     * Reconstructs the moving frame after a server/runtime reload.  The
     * centre of the authored lower yoke is the only copper-block cell on the
     * centre actuator column, so it is an unambiguous persisted bottom pose.
     * Recovering it lets the normal two-block-per-tick retraction continue;
     * the former null-cache path erased the full crane and drew the ceiling
     * frame in one tick.
     */
    private static CraneFrame findPersistedCraneFrame(ServerLevel level,
                                                       int variant)
    {
        BlockPos bed = hangarBed(level, variant);
        for (int z = bed.getZ() + CRANE_MIN_Z_OFFSET;
             z <= bed.getZ() + CRANE_MAX_Z_OFFSET; z++)
        {
            for (int y = CRANE_MIN_Y; y <= CRANE_TROLLEY_Y - 2; y++)
            {
                BlockState centre = level.getBlockState(
                        new BlockPos(bed.getX(), y, z));
                BlockState left = level.getBlockState(new BlockPos(
                        bed.getX() - CRANE_CABLE_X, y, z));
                BlockState right = level.getBlockState(new BlockPos(
                        bed.getX() + CRANE_CABLE_X, y, z));
                boolean legacyCable = left.is(Blocks.CHAIN)
                        || right.is(Blocks.CHAIN);
                boolean joinedCrosshead = left.is(Blocks.EXPOSED_COPPER)
                        && right.is(Blocks.EXPOSED_COPPER);
                BlockState upperLeft = level.getBlockState(new BlockPos(
                        bed.getX() - CRANE_CABLE_X, y + 1, z));
                BlockState upperRight = level.getBlockState(new BlockPos(
                        bed.getX() + CRANE_CABLE_X, y + 1, z));
                boolean newSpreader = (centre.is(Blocks.ORANGE_CONCRETE)
                        || centre.is(Blocks.PURPLE_CONCRETE)
                        || centre.is(Blocks.RED_CONCRETE)
                        || PrivateModVisuals.is(centre, "create", "brass_casing"))
                        && (PrivateModVisuals.is(upperLeft, "create",
                                    "pulley_magnet")
                                || upperLeft.is(Blocks.EXPOSED_COPPER))
                        && (PrivateModVisuals.is(upperRight, "create",
                                    "pulley_magnet")
                                || upperRight.is(Blocks.EXPOSED_COPPER));
                if ((centre.is(Blocks.COPPER_BLOCK)
                        && (legacyCable || joinedCrosshead)) || newSpreader)
                {
                    return new CraneFrame(z, y);
                }
            }
        }
        return null;
    }

    public static void resetRuntime()
    {
        CRANE_FRAMES.clear();
    }

    private static void paintCraneFrame(
            ServerLevel level, int variant,
            CraneFrame frame, boolean present)
    {
        BlockPos bed = hangarBed(level, variant);
        FacilitySchemaV2.IntBox[] owners = owners(level, variant);
        BlockState accent = switch (variant)
        {
            case 0 -> Blocks.ORANGE_CONCRETE.defaultBlockState();
            case 2 -> Blocks.RED_CONCRETE.defaultBlockState();
            default -> Blocks.PURPLE_CONCRETE.defaultBlockState();
        };
        BlockState girder = Blocks.POLISHED_DEEPSLATE.defaultBlockState();
        BlockState casing = Blocks.COPPER_BLOCK.defaultBlockState();
        BlockState brassCasing = Blocks.CUT_COPPER.defaultBlockState();
        BlockState carriage = Blocks.POLISHED_BLACKSTONE.defaultBlockState();
        BlockState pulley = Blocks.PISTON.defaultBlockState()
                .setValue(net.minecraft.world.level.block.piston.PistonBaseBlock.FACING,
                        Direction.DOWN);
        BlockState magnet = Blocks.EXPOSED_COPPER.defaultBlockState();

        // A real rectangular bridge trolley: two parallel structural girders,
        // end ties and a central carriage. The old single row of unrelated
        // copper blocks read as floating debris from every oblique view.
        for (int dz : new int[] {-CRANE_DEPTH, CRANE_DEPTH})
        {
            for (int dx = -CRANE_HALF_SPAN; dx <= CRANE_HALF_SPAN; dx++)
            {
                setOwned(level, owners,
                        new BlockPos(bed.getX() + dx, CRANE_TROLLEY_Y,
                                frame.z() + dz),
                        present ? girder : AIR);
            }
        }
        for (int dx : new int[] {-CRANE_HALF_SPAN, CRANE_HALF_SPAN})
        {
            for (int dz = -CRANE_DEPTH; dz <= CRANE_DEPTH; dz++)
            {
                setOwned(level, owners,
                        new BlockPos(bed.getX() + dx, CRANE_TROLLEY_Y,
                                frame.z() + dz),
                        present ? girder : AIR);
            }
        }
        setOwned(level, owners,
                new BlockPos(bed.getX(), CRANE_TROLLEY_Y, frame.z()),
                present ? carriage : AIR);

        // The underside crosshead visibly carries two rope pulleys.  Both
        // suspension lines terminate in magnets on the lower spreader, so no
        // cable or piston is left hovering beside the capsule.
        for (int dx = -4; dx <= 4; dx++)
        {
            BlockState crosshead = Math.abs(dx) == CRANE_CABLE_X
                    ? pulley : girder;
            setOwned(level, owners,
                    new BlockPos(bed.getX() + dx, CRANE_TROLLEY_Y - 1,
                            frame.z()), present ? crosshead : AIR);
        }
        for (int dx : new int[] {-CRANE_CABLE_X, CRANE_CABLE_X})
        {
            for (int y = frame.bottomY() + 2;
                  y < CRANE_TROLLEY_Y - 1; y++)
            {
                setOwned(level, owners,
                        new BlockPos(bed.getX() + dx, y, frame.z()),
                        present ? CRANE_CABLE : AIR);
            }
        }
        for (int dx : new int[] {-CRANE_CABLE_X, CRANE_CABLE_X})
        {
            setOwned(level, owners,
                    new BlockPos(bed.getX() + dx, frame.bottomY() + 1,
                            frame.z()), present ? magnet : AIR);
        }

        // Four-sided lower spreader.  Its centre collar touches the entry-plug
        // crane marker while the rectangular frame remains legible from the
        // gallery and from either side of the cage.
        for (int dz : new int[] {-CRANE_DEPTH, CRANE_DEPTH})
        {
            for (int dx = -4; dx <= 4; dx++)
            {
                setOwned(level, owners,
                        new BlockPos(bed.getX() + dx, frame.bottomY(),
                                frame.z() + dz),
                        present ? girder : AIR);
            }
        }
        for (int dx : new int[] {-4, 4})
        {
            for (int dz = -CRANE_DEPTH; dz <= CRANE_DEPTH; dz++)
            {
                setOwned(level, owners,
                        new BlockPos(bed.getX() + dx, frame.bottomY(),
                                frame.z() + dz),
                        present ? girder : AIR);
            }
        }
        for (int dx = -2; dx <= 2; dx++)
        {
            BlockState collar = dx == 0 ? accent
                    : Math.abs(dx) == 1 ? brassCasing : casing;
            setOwned(level, owners,
                    new BlockPos(bed.getX() + dx, frame.bottomY(), frame.z()),
                    present ? collar : AIR);
        }
    }

    /** Exact persisted crane volume, independent of the process-local cache. */
    public static boolean isPlugCraneCell(ServerLevel level, int variant,
                                          double craneEyeY,
                                          double craneEyeZ,
                                          BlockPos position)
    {
        if (!ready(level, variant))
        {
            return false;
        }
        BlockPos bed = hangarBed(level, variant);
        int trolleyZ = Mth.clamp(Mth.floor(craneEyeZ),
                bed.getZ() + CRANE_MIN_Z_OFFSET,
                bed.getZ() + CRANE_MAX_Z_OFFSET);
        int bottomY = Mth.clamp(Mth.floor(craneEyeY),
                CRANE_MIN_Y, CRANE_TROLLEY_Y - 1);
        int dx = position.getX() - bed.getX();
        int dz = position.getZ() - trolleyZ;
        if (Math.abs(dz) > CRANE_DEPTH)
        {
            return false;
        }
        int y = position.getY();
        boolean topBridge = y == CRANE_TROLLEY_Y
                && (Math.abs(dz) == CRANE_DEPTH
                        && Math.abs(dx) <= CRANE_HALF_SPAN
                        || Math.abs(dx) == CRANE_HALF_SPAN
                        && Math.abs(dz) <= CRANE_DEPTH
                        || dx == 0 && dz == 0);
        boolean topCrosshead = y == CRANE_TROLLEY_Y - 1
                && dz == 0 && Math.abs(dx) <= 4;
        boolean suspension = dz == 0
                && Math.abs(dx) == CRANE_CABLE_X
                && y > bottomY && y < CRANE_TROLLEY_Y - 1;
        boolean lowerFrame = y == bottomY
                && (Math.abs(dz) == CRANE_DEPTH && Math.abs(dx) <= 4
                        || Math.abs(dx) == 4 && Math.abs(dz) <= CRANE_DEPTH
                        || dz == 0 && Math.abs(dx) <= 2);
        return topBridge || topCrosshead || suspension || lowerFrame;
    }

    /**
     * A clean restart has no process-local previous frame. Remove only the
     * three movable crane materials from their dedicated air volume, never
     * civil shell/rail blocks.
     */
    private static void sweepOrphanCrane(ServerLevel level, int variant)
    {
        BlockPos bed = hangarBed(level, variant);
        FacilitySchemaV2.IntBox[] owners = owners(level, variant);
        for (int z = bed.getZ() + CRANE_MIN_Z_OFFSET - CRANE_DEPTH;
             z <= bed.getZ() + CRANE_MAX_Z_OFFSET + CRANE_DEPTH; z++)
        {
            // Save-upgrade cleanup for the retired 47-block trolley.  Only its
            // exact ceiling plane and known crane palette are eligible; civil
            // shell cells elsewhere in the owner remain untouched.
            for (int dx = -CRANE_LEGACY_HALF_SPAN;
                 dx <= CRANE_LEGACY_HALF_SPAN; dx++)
            {
                BlockPos trolley = new BlockPos(
                        bed.getX() + dx, CRANE_TROLLEY_Y, z);
                BlockState state = level.getBlockState(trolley);
                if (isCraneTrolleyMaterial(state))
                {
                    setOwned(level, owners, trolley, AIR);
                }
            }
            // The moving mechanism owns a narrow nine-block-wide air shaft.
            // Sweep the complete legacy palette here, including pistons and
            // polished blackstone omitted by the old cleaner; those omissions
            // are the source of the detached blocks seen after restart.
            for (int dx = -CRANE_HALF_SPAN;
                 dx <= CRANE_HALF_SPAN; dx++)
            {
                for (int y = CRANE_MIN_Y; y < CRANE_TROLLEY_Y; y++)
                {
                    BlockPos hardware = new BlockPos(
                            bed.getX() + dx, y, z);
                    if (isCraneMovingMaterial(level.getBlockState(hardware)))
                    {
                        setOwned(level, owners, hardware, AIR);
                    }
                }
            }
        }
    }

    private static boolean isCraneTrolleyMaterial(BlockState state)
    {
        return state.is(Blocks.POLISHED_DEEPSLATE)
                || state.is(Blocks.LIGHT_GRAY_CONCRETE)
                || state.is(Blocks.ORANGE_CONCRETE)
                || state.is(Blocks.PURPLE_CONCRETE)
                || state.is(Blocks.RED_CONCRETE)
                || state.is(Blocks.POLISHED_BLACKSTONE)
                || state.is(Blocks.PISTON)
                || state.is(Blocks.COPPER_BLOCK)
                || state.is(Blocks.EXPOSED_COPPER)
                || isCreateCraneMaterial(state);
    }

    private static boolean isCraneMovingMaterial(BlockState state)
    {
        return state.is(Blocks.POLISHED_DEEPSLATE)
                || state.is(Blocks.CHAIN)
                || state.is(Blocks.COPPER_BLOCK)
                || state.is(Blocks.EXPOSED_COPPER)
                || state.is(Blocks.WEATHERED_COPPER)
                || state.is(Blocks.OXIDIZED_COPPER)
                || state.is(Blocks.PISTON)
                || state.is(Blocks.POLISHED_BLACKSTONE)
                || isCreateCraneMaterial(state);
    }

    private static boolean isCreateCraneMaterial(BlockState state)
    {
        return PrivateModVisuals.is(state, "create", "metal_girder")
                || PrivateModVisuals.is(state, "create", "andesite_casing")
                || PrivateModVisuals.is(state, "create", "brass_casing")
                || PrivateModVisuals.is(state, "create", "gantry_carriage")
                || PrivateModVisuals.is(state, "create", "rope_pulley")
                || PrivateModVisuals.is(state, "create", "pulley_magnet")
                || PrivateModVisuals.is(state, "create",
                        "piston_extension_pole");
    }

    private static boolean complete(FacilityV2SavedData data,
                                    List<String> zoneIds)
    {
        for (String zoneId : zoneIds)
        {
            FacilityV2SavedData.ZoneRecord receipt =
                    data.requireZone(zoneId);
            if (receipt.state() != FacilityV2SavedData.ZoneState.COMPLETE
                    || receipt.generatorVersion().isBlank()
                    || receipt.buildPlanHash().isBlank())
            {
                return false;
            }
        }
        return true;
    }

    private static FacilitySchemaV2.ResolvedManifest manifest(
            ServerLevel level)
    {
        FacilityV2SavedData data = FacilityV2SavedData.get(level);
        if (!data.commissioned())
        {
            throw new IllegalStateException(
                    "Facility v2 has no commissioned manifest");
        }
        return data.manifest();
    }

    private static FacilitySchemaV2.IntBox[] owners(
            ServerLevel level, int variant)
    {
        return owners(manifest(level), variant);
    }

    private static FacilitySchemaV2.IntBox[] owners(
            FacilitySchemaV2.ResolvedManifest manifest, int variant)
    {
        String unit = unit(variant);
        FacilitySchemaV2.IntBox[] result =
                new FacilitySchemaV2.IntBox[RUNTIME_OWNER_SUFFIXES.length];
        for (int index = 0; index < RUNTIME_OWNER_SUFFIXES.length; index++)
        {
            result[index] = manifest.requireZone(
                    "UNIT" + unit + RUNTIME_OWNER_SUFFIXES[index]).owner();
        }
        return result;
    }

    private static void setOwned(ServerLevel level,
                                 FacilitySchemaV2.IntBox[] owners,
                                 BlockPos position, BlockState state)
    {
        if(NervRouteRuntimeR52.claimed(level))return;
        boolean owned = false;
        for (FacilitySchemaV2.IntBox owner : owners)
        {
            if (contains(owner, position))
            {
                owned = true;
                break;
            }
        }
        if (!owned || level.getBlockState(position).equals(state))
        {
            return;
        }
        level.setBlock(position, state,
                Block.UPDATE_CLIENTS | Block.UPDATE_KNOWN_SHAPE);
        PerformanceCounters.recordWorldBlockWrites(1);
    }

    private static boolean contains(FacilitySchemaV2.IntBox box,
                                    BlockPos position)
    {
        return position.getX() >= box.minX()
                && position.getX() < box.maxX()
                && position.getY() >= box.minY()
                && position.getY() < box.maxY()
                && position.getZ() >= box.minZ()
                && position.getZ() < box.maxZ();
    }

    private static int lineX(int variant)
    {
        if (variant < 0 || variant >= LINE_X.length)
        {
            throw new IllegalArgumentException(
                    "Unsupported EVA variant " + variant);
        }
        return LINE_X[variant];
    }

    private static String unit(int variant)
    {
        return String.format("%02d", variant);
    }

    private static double square(double value)
    {
        return value * value;
    }

    private record CraneFrame(int z, int bottomY) {}
}

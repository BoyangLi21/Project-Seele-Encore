package com.projectseele.world;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;

/**
 * Immutable spatial contract for the clean GeoFront v2 region.
 *
 * <p>This class is deliberately geometry-only. It does not load chunks,
 * place blocks, repair legacy rooms or create receipts. Builders consume a
 * resolved, audited manifest after an administrator commissions an epoch.</p>
 */
public final class FacilitySchemaV2
{
    public static final int SCHEMA_VERSION = 5;
    public static final int COORDINATE_CONTRACT_VERSION = 4;
    public static final int EPOCH = 5;
    public static final String REGION_ID = "geofront-s19-clean-r2";
    public static final String GENERATOR_VERSION =
            "facility-s19-r1+" + GeoFrontBoundedChunkGenerator.GENERATOR_VERSION;
    public static final ResourceKey<Level> DIMENSION = ResourceKey.create(
            Registries.DIMENSION,
            new ResourceLocation(ProjectSeele.MODID, "geofront"));

    public static final int REGION_HALF_SIZE = 1024;
    public static final int REGION_MIN_Y = -672;
    public static final int REGION_MAX_Y_EXCLUSIVE = 320;
    public static final int MIN_SURFACE_Y = 64;
    public static final int MAX_SURFACE_Y = 212;
    public static final int SURFACE_ALIGNMENT = 4;
    /**
     * Epoch 2 commits one worldgen candidate before any target chunk exists.
     * The remaining coordinates are future clean candidates, not additional
     * caverns in the same world.
     */
    public static final int ACTIVE_CANDIDATE_INDEX = 0;
    /**
     * S22 coastal rebuild datum.  The approved R28 archive keeps its stored
     * surface receipt at 96; generators explicitly accept that legacy value
     * so restoring the archive does not reinterpret its coordinates.
     */
    public static final int WORLDGEN_SURFACE_DATUM = 68;
    public static final int R28_LEGACY_SURFACE_DATUM = 96;
    /** Selected coastal anchor for the separate-seed S24 rebuild. */
    public static final BlockPos S24_COASTAL_CENTRE =
            new BlockPos(-1970, 0, -760);

    public static final int GF_FLOOR_Y = -360;

    public static final int EVA_STANDING_MIN_HEIGHT = 60;
    public static final int EVA_SURFACE_SWEEP_HEIGHT = 80;

    public static final List<BlockPos> CANDIDATE_CENTRES = List.of(
            // Rescue epoch deliberately shares X/Z with the complete legacy
            // GeoFront.  V2 occupies the upper civil decks while the proven
            // three-cage/three-silo mechanical plant remains physically below.
            new BlockPos(30, 0, 296),
            new BlockPos(12288, 0, 8192),
            new BlockPos(8192, 0, 12288),
            new BlockPos(12288, 0, 12288));

    public static final Set<String> APPROVED_ROOF_PENETRATIONS = Set.of(
            "PUBLIC_LIFT_SHAFT",
            "UNIT00_SILO", "UNIT01_SILO", "UNIT02_SILO");

    private FacilitySchemaV2() {}

    public static ResolvedManifest resolve(int candidateIndex, int surfaceY)
    {
        if (candidateIndex < 0 || candidateIndex >= CANDIDATE_CENTRES.size())
        {
            throw new IllegalArgumentException(
                    "Invalid FacilitySchema candidate index " + candidateIndex);
        }
        if (surfaceY < MIN_SURFACE_Y || surfaceY > MAX_SURFACE_Y
                || Math.floorMod(surfaceY, SURFACE_ALIGNMENT) != 0)
        {
            throw new IllegalArgumentException(
                    "Surface datum must be four-aligned within 64..212: "
                            + surfaceY);
        }

        BlockPos centre = candidateIndex == ACTIVE_CANDIDATE_INDEX
                && surfaceY == WORLDGEN_SURFACE_DATUM
                ? S24_COASTAL_CENTRE
                : CANDIDATE_CENTRES.get(candidateIndex);
        IntBox region = new IntBox(
                centre.getX() - REGION_HALF_SIZE, REGION_MIN_Y,
                centre.getZ() - REGION_HALF_SIZE,
                centre.getX() + REGION_HALF_SIZE,
                REGION_MAX_Y_EXCLUSIVE,
                centre.getZ() + REGION_HALF_SIZE);

        List<ZoneSpec> zones = new ArrayList<>();
        add(zones, centre, "TOKYO3_APRON",
                box(-64, surfaceY - 16, 372, 64, surfaceY + 48, 436),
                "Future city-side station approach");
        add(zones, centre, "SURFACE_TRANSIT",
                box(-64, surfaceY - 16, 244, 64, surfaceY + 48, 372),
                "Tokyo-3 H-01 surface station");
        add(zones, centre, "PUBLIC_LIFT_SHAFT",
                box(-12, -368, 220, 12, surfaceY + 16, 244),
                "Persistent surface/GeoFront lift");
        add(zones, centre, "GEOFRONT_TRANSIT",
                box(-64, -368, 184, 64, -320, 220),
                "H-01 GeoFront landing");
        add(zones, centre, "NERV_FOYER",
                box(-72, -368, 96, 72, -320, 184),
                "South/rear security foyer");
        add(zones, centre, "H01_CV_CONNECTOR",
                box(-8, -340, 76, 8, -324, 96),
                "Owned L2 foyer/CommandVolume join");
        add(zones, centre, "COMMAND_VOLUME",
                box(-56, -368, -76, 56, -304, 76),
                "One continuous command volume");
        add(zones, centre, "COMMAND_MODULE_CAP",
                box(-28, -304, -64, 28, -291, 65),
                "Owned cap for the authored command-module crown");
        add(zones, centre, "CMD_LIFT_SPINE",
                box(56, -352, -32, 72, -304, 56),
                "Command lift, secure spine and emergency stair");
        add(zones, centre, "COMMAND_SUITE",
                box(72, -344, -56, 128, -312, 56),
                "Office, conversation room and vestibule");
        add(zones, centre, "STAFF_LIFT_SHAFT",
                box(56, -416, 56, 72, -304, 72),
                "Persistent staff lift at L2 south-east");
        add(zones, centre, "STAFF_SERVICE_CONNECTOR",
                box(-160, -416, 56, 56, -400, 72),
                "Low service route from staff lift");
        add(zones, centre, "WEST_SERVICE_SPINE",
                box(-160, -352, 56, -56, -340, 72),
                "Registered L0/L1 west service exit");
        add(zones, centre, "WEST_SUPPORT",
                box(-208, -416, -64, -160, -304, 88),
                "Future support owner");
        add(zones, centre, "EAST_SERVICE_SPINE",
                box(72, -352, 56, 160, -340, 72),
                "Terminated east maintenance spur");
        add(zones, centre, "MAGI_CORE",
                box(-40, -400, -40, 40, -368, 40),
                "Visible MAGI core below command room");
        add(zones, centre, "MAGI_DOGMA_SPINE",
                box(24, -400, 40, 40, -388, 160),
                "Restricted horizontal approach");
        add(zones, centre, "DOGMA_LIFT_SHAFT",
                box(24, -632, 160, 40, -388, 184),
                "Persistent high-security lift");
        add(zones, centre, "DOGMA_SPINE",
                box(-40, -656, 184, 80, -520, 320),
                "Central/Terminal Dogma approach");
        add(zones, centre, "LILITH_CHAMBER",
                box(-112, -668, 320, 112, -572, 544),
                "Terminal datum and Lilith chamber");
        /*
         * S19 moves the complete three-line mechanical plant into the solid
         * south rock beyond the GeoFront ellipsoid. The old rescue layout put
         * one line beside command and shared its X/Z with legacy geometry.
         */
        add(zones, centre, "MECH_ACCESS_SPINE",
                box(56, -416, 72, 128, -400, 660),
                "Restricted HQ-to-mechanical rock tunnel");
        add(zones, centre, "MECH_AIRLOCK_LINK",
                box(56, -432, 660, 128, -400, 690),
                "Double interlocked south rock airlock");
        add(zones, centre, "MECH_PERSONNEL_TRUNK",
                box(-600, -432, 690, 600, -400, 721),
                "Personnel and plug-crew trunk outside EVA swept volumes");
        addEvaLineZones(zones, centre, "00", -389, surfaceY);
        addEvaLineZones(zones, centre, "01", 0, surfaceY);
        addEvaLineZones(zones, centre, "02", 389, surfaceY);
        add(zones, centre, "S02_REVIEW_DECK",
                box(800, surfaceY - 16, -24, 848, surfaceY + 9, 24),
                "Isolated optional review construction");

        Map<String, ZoneSpec> byId = new LinkedHashMap<>();
        for (ZoneSpec zone : zones)
        {
            if (byId.put(zone.id(), zone) != null)
            {
                throw new IllegalStateException("Duplicate zone " + zone.id());
            }
        }
        List<PortSpec> ports = resolvePorts(centre, surfaceY);
        Map<String, PortSpec> portsById = new LinkedHashMap<>();
        for (PortSpec port : ports)
        {
            String key = port.key();
            if (portsById.put(key, port) != null)
            {
                throw new IllegalStateException("Duplicate port " + key);
            }
        }
        ResolvedManifest manifest = new ResolvedManifest(candidateIndex, centre,
                surfaceY, region, List.copyOf(zones), Map.copyOf(byId),
                List.copyOf(ports), Map.copyOf(portsById));
        ManifestAudit audit = manifest.audit();
        if (!audit.valid())
        {
            throw new IllegalStateException(audit.summary());
        }
        return manifest;
    }

    private static IntBox box(int minX, int minY, int minZ,
                              int maxX, int maxY, int maxZ)
    {
        return new IntBox(minX, minY, minZ, maxX, maxY, maxZ);
    }

    private static void add(List<ZoneSpec> zones, BlockPos centre, String id,
                            IntBox relative, String purpose)
    {
        zones.add(new ZoneSpec(id,
                relative.offset(centre.getX(), 0, centre.getZ()), purpose));
    }

    private static void addEvaLineZones(
            List<ZoneSpec> zones, BlockPos centre,
            String unit, int lineX, int surfaceY)
    {
        String prefix = "UNIT" + unit;
        add(zones, centre, "MECH_OBS_LINK_" + unit,
                box(lineX - 94, -432, 721,
                        lineX + 94, -400, 737),
                "Protected observation and boarding approach for " + prefix);
        add(zones, centre, prefix + "_CAGE",
                box(lineX - 94, -504, 737,
                        lineX + 94, -320, 862),
                prefix + " wet cage, observation and plug crane");
        add(zones, centre, prefix + "_CARRIER",
                box(lineX - 40, -504, 862,
                        lineX + 40, -384, 886),
                prefix + " straight carrier branch");
        add(zones, centre, prefix + "_SWITCHYARD",
                box(lineX - 53, -504, 886,
                        lineX + 53, -384, 930),
                prefix + " carrier alignment and launch interlock");
        add(zones, centre, prefix + "_SILO",
                box(lineX - 53, -504, 930,
                        lineX + 53, surfaceY, 1007),
                prefix + " exclusive vertical launch and recovery volume");
        add(zones, centre, prefix + "_SURFACE_HEAD",
                box(lineX - 53, surfaceY, 930,
                        lineX + 53, surfaceY + 80, 1007),
                prefix + " interlocked surface head and complete EVA sweep");
    }

    private static List<PortSpec> resolvePorts(BlockPos centre, int surfaceY)
    {
        List<PortSpec> ports = new ArrayList<>();
        pair(ports, centre, "TOKYO3_APRON", "T3A-ST",
                0, surfaceY, 372, Direction.NORTH,
                "SURFACE_TRANSIT", "ST-CITY",
                0, surfaceY, 371, Direction.SOUTH,
                "HUMAN", "H7x6");
        pair(ports, centre, "SURFACE_TRANSIT", "ST-LIFT",
                0, surfaceY, 244, Direction.NORTH,
                "PUBLIC_LIFT_SHAFT", "LIFT-SURFACE",
                0, surfaceY, 243, Direction.SOUTH,
                "HUMAN", "H7x6");
        pair(ports, centre, "PUBLIC_LIFT_SHAFT", "LIFT-GF",
                0, -352, 220, Direction.NORTH,
                "GEOFRONT_TRANSIT", "GFT-LIFT",
                0, -352, 219, Direction.SOUTH,
                "HUMAN", "H7x6");
        pair(ports, centre, "GEOFRONT_TRANSIT", "GFT-FOYER",
                0, -356, 184, Direction.NORTH,
                "NERV_FOYER", "FOYER-GFT",
                0, -356, 183, Direction.SOUTH,
                "HUMAN", "H7x6");
        pair(ports, centre, "NERV_FOYER", "FOYER-CV",
                0, -332, 96, Direction.NORTH,
                "H01_CV_CONNECTOR", "H01-FOYER",
                0, -332, 95, Direction.SOUTH,
                "HUMAN", "H7x6");
        pair(ports, centre, "H01_CV_CONNECTOR", "H01-CV",
                0, -332, 76, Direction.NORTH,
                "COMMAND_VOLUME", "CV-H01-ENTRY",
                0, -332, 75, Direction.SOUTH,
                "HUMAN", "H7x6");
        pair(ports, centre, "COMMAND_VOLUME", "CV-EL-CMD",
                55, -324, 48, Direction.EAST,
                "CMD_LIFT_SPINE", "CMDLIFT-CV",
                56, -324, 48, Direction.WEST,
                "HUMAN_SECURE", "H7x7");
        pair(ports, centre, "COMMAND_VOLUME", "CV-OFFICE",
                55, -332, 24, Direction.EAST,
                "CMD_LIFT_SPINE", "CMDOFFICE-CV",
                56, -332, 24, Direction.WEST,
                "HUMAN_SECURE", "H7x7");
        pair(ports, centre, "CMD_LIFT_SPINE", "CMD-SUITE",
                71, -324, 0, Direction.EAST,
                "COMMAND_SUITE", "SUITE-CMD",
                72, -324, 0, Direction.WEST,
                "HUMAN_SECURE", "H7x7");
        pair(ports, centre, "COMMAND_VOLUME", "CV-EL-STAFF",
                55, -332, 64, Direction.EAST,
                "STAFF_LIFT_SHAFT", "STAFFLIFT-CV",
                56, -332, 64, Direction.WEST,
                "HUMAN", "H7x6");
        pair(ports, centre, "STAFF_LIFT_SHAFT", "STAFFLIFT-SERVICE",
                56, -408, 64, Direction.WEST,
                "STAFF_SERVICE_CONNECTOR", "STAFFSERVICE-LIFT",
                55, -408, 64, Direction.EAST,
                "HUMAN", "H7x6");
        pair(ports, centre, "STAFF_SERVICE_CONNECTOR",
                "STAFFSERVICE-WEST", -160, -408, 64, Direction.WEST,
                "WEST_SUPPORT", "WEST-STAFFSERVICE",
                -161, -408, 64, Direction.EAST,
                "HUMAN", "H7x6");
        pair(ports, centre, "COMMAND_VOLUME", "CV-SERVICE-W",
                -56, -348, 64, Direction.WEST,
                "WEST_SERVICE_SPINE", "SERVICEW-CV",
                -57, -348, 64, Direction.EAST,
                "SERVICE", "H7x6");
        pair(ports, centre, "WEST_SERVICE_SPINE", "SERVICEW-SUPPORT",
                -160, -348, 64, Direction.WEST,
                "WEST_SUPPORT", "WEST-SERVICEW",
                -161, -348, 64, Direction.EAST,
                "SERVICE", "H7x6");
        pair(ports, centre, "COMMAND_VOLUME", "CV-SERVICE-E",
                55, -348, 64, Direction.EAST,
                "STAFF_LIFT_SHAFT", "SERVICEE-CV",
                56, -348, 64, Direction.WEST,
                "SERVICE", "H7x6");
        pair(ports, centre, "STAFF_LIFT_SHAFT", "SERVICEE-OUT",
                71, -348, 64, Direction.EAST,
                "EAST_SERVICE_SPINE", "SERVICEE-LIFT",
                72, -348, 64, Direction.WEST,
                "SERVICE", "H7x6");
        pair(ports, centre, "COMMAND_VOLUME", "CV-MAGI-VIEW",
                0, -368, 0, Direction.DOWN,
                "MAGI_CORE", "MAGI-VIEW-CV",
                0, -369, 0, Direction.UP,
                "VIEW", "V16x16");
        pair(ports, centre, "COMMAND_VOLUME", "CV-MAGI-SECURE",
                28, -368, 24, Direction.DOWN,
                "MAGI_CORE", "MAGI-CV-SECURE",
                28, -369, 24, Direction.UP,
                "HUMAN_SECURE", "H7x7");
        pair(ports, centre, "MAGI_CORE", "MAGI-DOGMA",
                32, -395, 39, Direction.SOUTH,
                "MAGI_DOGMA_SPINE", "DOGMASPINE-MAGI",
                32, -395, 40, Direction.NORTH,
                "RESTRICTED", "H7x7");
        pair(ports, centre, "MAGI_DOGMA_SPINE", "DOGMASPINE-LIFT",
                32, -395, 159, Direction.SOUTH,
                "DOGMA_LIFT_SHAFT", "DOGMALIFT-SPINE",
                32, -395, 160, Direction.NORTH,
                "RESTRICTED", "H7x7");
        pair(ports, centre, "DOGMA_LIFT_SHAFT", "DOGMALIFT-DOGMA",
                32, -576, 183, Direction.SOUTH,
                "DOGMA_SPINE", "DOGMA-HIGH-SECURITY-IN",
                32, -576, 184, Direction.NORTH,
                "RESTRICTED", "H7x7");
        pair(ports, centre, "DOGMA_SPINE", "DOGMA-LILITH",
                0, -612, 319, Direction.SOUTH,
                "LILITH_CHAMBER", "LILITH-DOGMA",
                0, -612, 320, Direction.NORTH,
                "RESTRICTED", "H9x9");
        pair(ports, centre, "STAFF_LIFT_SHAFT", "STAFFLIFT-MECH",
                64, -408, 71, Direction.SOUTH,
                "MECH_ACCESS_SPINE", "MECH-HQ",
                64, -408, 72, Direction.NORTH,
                "HUMAN_SECURE", "H7x6");
        pair(ports, centre, "MECH_ACCESS_SPINE", "MECH-AIRLOCK",
                92, -408, 659, Direction.SOUTH,
                "MECH_AIRLOCK_LINK", "AIRLOCK-HQ",
                92, -408, 660, Direction.NORTH,
                "HUMAN_SECURE", "H7x6");
        pair(ports, centre, "MECH_AIRLOCK_LINK", "AIRLOCK-TRUNK",
                92, -408, 689, Direction.SOUTH,
                "MECH_PERSONNEL_TRUNK", "TRUNK-AIRLOCK",
                92, -408, 690, Direction.NORTH,
                "HUMAN_SECURE", "H7x6");
        addEvaLinePorts(ports, centre, "00", -389, surfaceY);
        addEvaLinePorts(ports, centre, "01", 0, surfaceY);
        addEvaLinePorts(ports, centre, "02", 389, surfaceY);
        return List.copyOf(ports);
    }

    private static void addEvaLinePorts(
            List<PortSpec> ports, BlockPos centre,
            String unit, int lineX, int surfaceY)
    {
        String prefix = "UNIT" + unit;
        String observation = "MECH_OBS_LINK_" + unit;
        pair(ports, centre, "MECH_PERSONNEL_TRUNK",
                "TRUNK-OBS-" + unit,
                lineX, -408, 720, Direction.SOUTH,
                observation, "OBS-" + unit + "-TRUNK",
                lineX, -408, 721, Direction.NORTH,
                "HUMAN_SECURE", "H7x6");
        pair(ports, centre, observation, "OBS-" + unit + "-CAGE",
                lineX, -408, 736, Direction.SOUTH,
                prefix + "_CAGE", "CAGE-" + unit + "-OBS",
                lineX, -408, 737, Direction.NORTH,
                "HUMAN_SERVICE", "H7x6");
        pair(ports, centre, prefix + "_CAGE", "CAGE-" + unit + "-EVA",
                lineX, -464, 861, Direction.SOUTH,
                prefix + "_CARRIER", "CARRIER-" + unit + "-CAGE",
                lineX, -464, 862, Direction.NORTH,
                "EVA", "EVA2X_STRAIGHT");
        pair(ports, centre, prefix + "_CARRIER",
                "CARRIER-" + unit + "-SWITCH",
                lineX, -464, 885, Direction.SOUTH,
                prefix + "_SWITCHYARD",
                "SWITCH-" + unit + "-CARRIER",
                lineX, -464, 886, Direction.NORTH,
                "EVA", "EVA2X_STRAIGHT");
        pair(ports, centre, prefix + "_SWITCHYARD",
                "SWITCH-" + unit + "-SILO",
                lineX, -464, 929, Direction.SOUTH,
                prefix + "_SILO", "SILO-" + unit + "-EVA",
                lineX, -464, 930, Direction.NORTH,
                "EVA", "EVA2X_TURN");
        pair(ports, centre, prefix + "_SILO",
                "SILO-" + unit + "-SURFACE",
                lineX, surfaceY - 1, 968, Direction.UP,
                prefix + "_SURFACE_HEAD",
                "SURFACE-" + unit + "-SILO",
                lineX, surfaceY, 968, Direction.DOWN,
                "EVA", "EVA2X_VERTICAL");
    }

    private static void pair(List<PortSpec> ports, BlockPos centre,
                             String zoneA, String idA,
                             int xA, int yA, int zA, Direction facingA,
                             String zoneB, String idB,
                             int xB, int yB, int zB, Direction facingB,
                             String type, String profile)
    {
        BlockPos positionA = centre.offset(xA, yA, zA);
        BlockPos positionB = centre.offset(xB, yB, zB);
        ports.add(new PortSpec(idA, zoneA, positionA, facingA, type,
                profile, aperture(positionA, facingA, profile), zoneB, idB));
        ports.add(new PortSpec(idB, zoneB, positionB, facingB, type,
                profile, aperture(positionB, facingB, profile), zoneA, idA));
    }

    private static IntBox aperture(BlockPos anchor, Direction facing,
                                   String profile)
    {
        int negative;
        int positive;
        int verticalNegative;
        int verticalPositive;
        boolean bottomAnchored = false;
        switch (profile)
        {
            case "H7x6" ->
            {
                negative = 3;
                positive = 4;
                verticalNegative = 0;
                verticalPositive = 6;
                bottomAnchored = true;
            }
            case "H7x7" ->
            {
                negative = 3;
                positive = 4;
                verticalNegative = 0;
                verticalPositive = 7;
                bottomAnchored = true;
            }
            case "H9x9" ->
            {
                negative = 4;
                positive = 5;
                verticalNegative = 0;
                verticalPositive = 9;
                bottomAnchored = true;
            }
            case "V16x16" ->
            {
                negative = 8;
                positive = 8;
                verticalNegative = 8;
                verticalPositive = 8;
            }
            case "EVA2X_STRAIGHT" ->
            {
                negative = 28;
                positive = 28;
                verticalNegative = 40;
                verticalPositive = 72;
            }
            case "EVA2X_TURN" ->
            {
                negative = 40;
                positive = 40;
                verticalNegative = 40;
                verticalPositive = 72;
            }
            case "EVA2X_VERTICAL" ->
            {
                negative = 32;
                positive = 32;
                verticalNegative = 32;
                verticalPositive = 32;
            }
            default -> throw new IllegalArgumentException(
                    "Unknown facility port profile " + profile);
        }

        int x = anchor.getX();
        int y = anchor.getY();
        int z = anchor.getZ();
        if (facing.getAxis() == Direction.Axis.Y)
        {
            return new IntBox(x - negative, y, z - negative,
                    x + positive, y + 1, z + positive);
        }
        int minY = bottomAnchored ? y : y - verticalNegative;
        int maxY = bottomAnchored ? y + verticalPositive
                : y + verticalPositive;
        if (facing.getAxis() == Direction.Axis.X)
        {
            return new IntBox(x, minY, z - negative,
                    x + 1, maxY, z + positive);
        }
        return new IntBox(x - negative, minY, z,
                x + positive, maxY, z + 1);
    }

    public record IntBox(int minX, int minY, int minZ,
                         int maxX, int maxY, int maxZ)
    {
        public IntBox
        {
            if (minX >= maxX || minY >= maxY || minZ >= maxZ)
            {
                throw new IllegalArgumentException("Invalid half-open box");
            }
        }

        public IntBox offset(int x, int y, int z)
        {
            return new IntBox(minX + x, minY + y, minZ + z,
                    maxX + x, maxY + y, maxZ + z);
        }

        public boolean contains(IntBox other)
        {
            return minX <= other.minX && minY <= other.minY
                    && minZ <= other.minZ && maxX >= other.maxX
                    && maxY >= other.maxY && maxZ >= other.maxZ;
        }

        public boolean intersects(IntBox other)
        {
            return maxX > other.minX && minX < other.maxX
                    && maxY > other.minY && minY < other.maxY
                    && maxZ > other.minZ && minZ < other.maxZ;
        }

        public int sizeX()
        {
            return maxX - minX;
        }

        public int sizeY()
        {
            return maxY - minY;
        }

        public int sizeZ()
        {
            return maxZ - minZ;
        }

        public long volume()
        {
            return (long) sizeX() * sizeY() * sizeZ();
        }

        public BlockPos positionAt(long index)
        {
            long volume = volume();
            if (index < 0L || index >= volume)
            {
                throw new IndexOutOfBoundsException(
                        "AABB cursor " + index + " outside 0.." + volume);
            }
            int x = (int) (index % sizeX());
            long yz = index / sizeX();
            int z = (int) (yz % sizeZ());
            int y = (int) (yz / sizeZ());
            return new BlockPos(minX + x, minY + y, minZ + z);
        }

        public AABB toAabb()
        {
            return new AABB(minX, minY, minZ, maxX, maxY, maxZ);
        }
    }

    public record ZoneSpec(String id, IntBox owner, String purpose) {}

    public record PortSpec(String id, String zoneId, BlockPos position,
                           Direction facing, String type, String clearProfile,
                           IntBox aperture, String peerZoneId,
                           String peerPortId)
    {
        public String key()
        {
            return this.zoneId + ":" + this.id;
        }

        public String peerKey()
        {
            return this.peerZoneId + ":" + this.peerPortId;
        }
    }

    public record ResolvedManifest(int candidateIndex, BlockPos centre,
                                   int surfaceY, IntBox region,
                                   List<ZoneSpec> zones,
                                   Map<String, ZoneSpec> zonesById,
                                   List<PortSpec> ports,
                                   Map<String, PortSpec> portsById)
    {
        public ResolvedManifest
        {
            zones = List.copyOf(zones);
            zonesById = Map.copyOf(zonesById);
            ports = List.copyOf(ports);
            portsById = Map.copyOf(portsById);
        }

        public ZoneSpec requireZone(String id)
        {
            ZoneSpec zone = zonesById.get(id);
            if (zone == null)
            {
                throw new IllegalArgumentException("Unknown facility zone " + id);
            }
            return zone;
        }

        public PortSpec requirePort(String zoneId, String portId)
        {
            PortSpec port = this.portsById.get(zoneId + ":" + portId);
            if (port == null)
            {
                throw new IllegalArgumentException(
                        "Unknown facility port " + zoneId + ":" + portId);
            }
            return port;
        }

        public ManifestAudit audit()
        {
            List<String> faults = new ArrayList<>();
            if (zones.size() != 42)
            {
                faults.add("owner count=" + zones.size() + " expected=42");
            }
            for (ZoneSpec zone : zones)
            {
                if (!region.contains(zone.owner()))
                {
                    faults.add(zone.id() + " outside region");
                }
            }
            for (int i = 0; i < zones.size(); i++)
            {
                for (int j = i + 1; j < zones.size(); j++)
                {
                    ZoneSpec a = zones.get(i);
                    ZoneSpec b = zones.get(j);
                    if (a.owner().intersects(b.owner()))
                    {
                        faults.add(a.id() + " overlaps " + b.id());
                    }
                }
            }
            if (ports.size() != 86)
            {
                faults.add("port count=" + ports.size() + " expected=86");
            }
            for (PortSpec port : ports)
            {
                ZoneSpec owner = zonesById.get(port.zoneId());
                PortSpec peer = portsById.get(port.peerKey());
                if (owner == null)
                {
                    faults.add(port.key() + " has unknown owner");
                }
                else if (!owner.owner().contains(port.aperture()))
                {
                    faults.add(port.key() + " aperture outside owner");
                }
                if (peer == null)
                {
                    faults.add(port.key() + " has no reciprocal peer");
                }
                else if (!peer.peerKey().equals(port.key())
                        || peer.facing() != port.facing().getOpposite()
                        || !peer.type().equals(port.type())
                        || !peer.clearProfile().equals(port.clearProfile()))
                {
                    faults.add(port.key() + " reciprocal contract mismatch");
                }
                else
                {
                    BlockPos expectedPeerPosition =
                            port.position().relative(port.facing());
                    IntBox expectedPeerAperture = port.aperture().offset(
                            port.facing().getStepX(),
                            port.facing().getStepY(),
                            port.facing().getStepZ());
                    if (!peer.position().equals(expectedPeerPosition)
                            || !peer.aperture().equals(expectedPeerAperture))
                    {
                        faults.add(port.key()
                                + " reciprocal aperture is not face-adjacent");
                    }
                }
            }
            IntBox command = requireZone("COMMAND_VOLUME").owner();
            if (command.sizeX() != 112 || command.sizeY() != 64
                    || command.sizeZ() != 152)
            {
                faults.add("CommandVolume gross dimensions changed");
            }
            for (String unit : List.of("00", "01", "02"))
            {
                IntBox surfaceHead =
                        requireZone("UNIT" + unit + "_SURFACE_HEAD").owner();
                if (surfaceHead.sizeY() < EVA_SURFACE_SWEEP_HEIGHT
                        || surfaceHead.sizeY()
                        < EVA_STANDING_MIN_HEIGHT)
                {
                    faults.add("UNIT" + unit
                            + " surface head cannot contain a complete EVA");
                }
            }
            return new ManifestAudit(faults.isEmpty(), List.copyOf(faults));
        }
    }

    public record ManifestAudit(boolean valid, List<String> faults)
    {
        public ManifestAudit
        {
            faults = List.copyOf(faults);
        }

        public String summary()
        {
            return valid ? "FacilitySchema v2 manifest valid"
                    : "FacilitySchema v2 manifest invalid: "
                            + String.join("; ", faults);
        }
    }
}

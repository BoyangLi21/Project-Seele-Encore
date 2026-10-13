package com.projectseele.world;

import java.util.List;

import com.projectseele.ProjectSeele;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;

/**
 * Advances an administrator-authorized sequence one bounded owner at a time.
 *
 * <p>This replaces error-prone manual invocation of nine independent build
 * commands. It never commissions a region and never repairs or rewrites a
 * completed owner.</p>
 */
public final class FacilityV2ProgrammeDirector
{
    public static final String PUBLIC_BACKBONE = "public-backbone-a2";
    public static final String COMMAND_CORE = "command-core-a1";
    public static final String EXTERIOR_LOOP = "exterior-loop-a1";
    public static final String DOGMA_BACKBONE = "dogma-backbone-a1";
    public static final String UNIT01_BACKBONE = "unit01-backbone-a1";
    public static final String EVA_BACKBONE = "eva-backbone-s19-a1";

    private static final List<String> COMMAND_CORE_ZONES = List.of(
            "NERV_FOYER",
            "H01_CV_CONNECTOR",
            "COMMAND_VOLUME",
            "COMMAND_MODULE_CAP",
            "CMD_LIFT_SPINE",
            "COMMAND_SUITE",
            "MAGI_CORE");
    private static final List<String> EXTERIOR_LOOP_ZONES = List.of(
            "WEST_SERVICE_SPINE",
            "WEST_SUPPORT");
    private static final List<String> PUBLIC_BACKBONE_ZONES = List.of(
            "TOKYO3_APRON",
            "SURFACE_TRANSIT",
            "PUBLIC_LIFT_SHAFT",
            "GEOFRONT_TRANSIT",
            "NERV_FOYER",
            "H01_CV_CONNECTOR",
            "COMMAND_VOLUME",
            "COMMAND_MODULE_CAP",
            "CMD_LIFT_SPINE",
            "COMMAND_SUITE",
            "STAFF_LIFT_SHAFT",
            "WEST_SERVICE_SPINE",
            "WEST_SUPPORT",
            "EAST_SERVICE_SPINE",
            "STAFF_SERVICE_CONNECTOR");
    private static final List<String> DOGMA_BACKBONE_ZONES = List.of(
            "MAGI_CORE",
            "MAGI_DOGMA_SPINE",
            "DOGMA_LIFT_SHAFT",
            "DOGMA_SPINE",
            "LILITH_CHAMBER");
    private static final List<String> UNIT01_BACKBONE_ZONES = List.of(
            "MECH_ACCESS_SPINE",
            "MECH_AIRLOCK_LINK",
            "MECH_PERSONNEL_TRUNK",
            "MECH_OBS_LINK_00",
            "UNIT00_CAGE",
            "UNIT00_CARRIER",
            "UNIT00_SWITCHYARD",
            "UNIT00_SILO",
            "UNIT00_SURFACE_HEAD",
            "MECH_OBS_LINK_01",
            "UNIT01_CAGE",
            "UNIT01_CARRIER",
            "UNIT01_SWITCHYARD",
            "UNIT01_SILO",
            "UNIT01_SURFACE_HEAD",
            "MECH_OBS_LINK_02",
            "UNIT02_CAGE",
            "UNIT02_CARRIER",
            "UNIT02_SWITCHYARD",
            "UNIT02_SILO",
            "UNIT02_SURFACE_HEAD");

    private FacilityV2ProgrammeDirector() {}

    public static void startCommandCore(ServerLevel level)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        requireClean(level, "startCommandCore");
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        if (!facility.commissioned())
        {
            throw new IllegalStateException(
                    "Facility v2 is not commissioned");
        }
        FacilityV2ProgrammeSavedData.get(level).start(COMMAND_CORE);
    }

    public static void startPublicBackbone(ServerLevel level)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        requireClean(level, "startPublicBackbone");
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        if (!facility.commissioned())
        {
            throw new IllegalStateException(
                    "Facility v2 is not commissioned");
        }
        FacilityV2ProgrammeSavedData.get(level).start(PUBLIC_BACKBONE);
    }

    public static void startExteriorLoop(ServerLevel level)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        requireClean(level, "startExteriorLoop");
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        if (!facility.commissioned())
        {
            throw new IllegalStateException(
                    "Facility v2 is not commissioned");
        }
        FacilityV2ProgrammeSavedData.get(level).start(EXTERIOR_LOOP);
    }

    public static void startDogmaBackbone(ServerLevel level)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        requireClean(level, "startDogmaBackbone");
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        if (!facility.commissioned())
        {
            throw new IllegalStateException(
                    "Facility v2 is not commissioned");
        }
        FacilityV2ProgrammeSavedData.get(level).start(DOGMA_BACKBONE);
    }

    public static void startUnit01Backbone(ServerLevel level)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        startEvaBackbone(level);
    }

    public static void startEvaBackbone(ServerLevel level)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        requireClean(level, "startEvaBackbone");
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        if (!facility.commissioned())
        {
            throw new IllegalStateException(
                    "Facility v2 is not commissioned");
        }
        FacilityV2ProgrammeSavedData.get(level).start(EVA_BACKBONE);
    }

    public static void tick(MinecraftServer server)
    {
        if (NervLegacyGenerationGuardR52.retired(server)) return;
        if (!FacilityWorldPolicy.isCleanRebuild(server))
        {
            return;
        }
        ServerLevel level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null)
        {
            return;
        }
        FacilityV2ProgrammeSavedData programme =
                FacilityV2ProgrammeSavedData.get(level);
        if (!programme.active())
        {
            return;
        }
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        if (!facility.commissioned() || facility.activeZone().isPresent())
        {
            return;
        }
        List<String> zones;
        if (COMMAND_CORE.equals(programme.programme()))
        {
            zones = COMMAND_CORE_ZONES;
        }
        else if (EXTERIOR_LOOP.equals(programme.programme()))
        {
            zones = EXTERIOR_LOOP_ZONES;
        }
        else if (PUBLIC_BACKBONE.equals(programme.programme()))
        {
            zones = PUBLIC_BACKBONE_ZONES;
        }
        else if (DOGMA_BACKBONE.equals(programme.programme()))
        {
            zones = DOGMA_BACKBONE_ZONES;
        }
        else if (UNIT01_BACKBONE.equals(programme.programme())
                || EVA_BACKBONE.equals(programme.programme()))
        {
            if(NervLegacyGenerationGuardR52.retired(level))return;
            zones = UNIT01_BACKBONE_ZONES;
        }
        else
        {
            programme.fail("unknown programme " + programme.programme());
            return;
        }

        while (programme.index() < zones.size())
        {
            String zoneId = zones.get(programme.index());
            FacilityV2SavedData.ZoneState state =
                    facility.requireZone(zoneId).state();
            if (state == FacilityV2SavedData.ZoneState.COMPLETE)
            {
                programme.advance();
                continue;
            }
            if (state != FacilityV2SavedData.ZoneState.EMPTY)
            {
                programme.fail(zoneId + " is " + state);
                return;
            }
            try
            {
                FacilityV2BuildDirector.start(level,
                        FacilityV2Plans.resolve(
                                facility.manifest(), zoneId));
            }
            catch (RuntimeException exception)
            {
                programme.fail(zoneId + ": " + exception.getMessage());
            }
            return;
        }

        programme.complete();
        FacilityV2RouteGateDirector.refresh(level, facility);
        ProjectSeele.LOGGER.info(
                "FacilitySchema v2 programme {} completed",
                programme.programme());
    }

    private static void requireClean(ServerLevel level, String operation)
    {
        FacilityWorldPolicy.requireCleanRebuild(level.getServer(),
                "FacilityV2ProgrammeDirector." + operation);
    }
}

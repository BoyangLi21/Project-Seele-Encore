package com.projectseele.visual;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.mojang.brigadier.exceptions.SimpleCommandExceptionType;
import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilityV2BootstrapDirector;
import com.projectseele.world.FacilityV2BuildDirector;
import com.projectseele.world.FacilityV2Plans;
import com.projectseele.world.FacilityV2ProgrammeDirector;
import com.projectseele.world.FacilityV2ProgrammeSavedData;
import com.projectseele.world.FacilityV2SavedData;
import com.projectseele.world.FacilitySchemaV2;
import com.projectseele.world.GeoFrontFabricDirector;
import com.projectseele.world.GeoFrontFabricPlan;
import com.projectseele.world.GeoFrontFabricSavedData;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Explicit administrator controls for the isolated FacilitySchema v2 region. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID,
        bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class FacilityV2Commands
{
    private static final SimpleCommandExceptionType GEOFRONT_UNAVAILABLE =
            new SimpleCommandExceptionType(Component.literal(
                    "GeoFront dimension is unavailable"));

    private FacilityV2Commands() {}

    @SubscribeEvent
    public static void register(RegisterCommandsEvent event)
    {
        if(!DevelopmentCommandsR43.enabled())return;
        CommandDispatcher<CommandSourceStack> dispatcher =
                event.getDispatcher();
        dispatcher.register(Commands.literal("seele")
                .requires(source -> source.hasPermission(2))
                .then(Commands.literal("facility_v2")
                        .then(Commands.literal("bootstrap")
                                .executes(context -> bootstrap(
                                        context.getSource())))
                        .then(Commands.literal("status")
                                .executes(context -> status(
                                        context.getSource())))
                        .then(Commands.literal("visit")
                                .then(Commands.literal("foyer_start")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "NERV_FOYER",
                                                0, -356, 176,
                                                180.0F, 0.0F)))
                                .then(Commands.literal("command_entry")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "COMMAND_VOLUME",
                                                0, -332, 68,
                                                180.0F, 0.0F)))
                                .then(Commands.literal("command_staff_route")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "COMMAND_VOLUME",
                                                30, -332, 70,
                                                -90.0F, 0.0F)))
                                .then(Commands.literal("staff_lift_b4")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "STAFF_LIFT_SHAFT",
                                                58, -408, 64,
                                                -90.0F, 0.0F)))
                                .then(Commands.literal("mechanical_access")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "MECH_ACCESS_SPINE",
                                                64, -408, 84,
                                                180.0F, 0.0F)))
                                .then(Commands.literal("command_high")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "COMMAND_VOLUME",
                                                0, -324, 52,
                                                180.0F, 8.0F)))
                                .then(Commands.literal("command_rear")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "COMMAND_VOLUME",
                                                1, -308, 22,
                                                180.0F, 0.0F)))
                                .then(Commands.literal("command_secure_lift")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "COMMAND_VOLUME",
                                                52, -324, 48,
                                                -90.0F, 0.0F)))
                                .then(Commands.literal("command_suite")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "COMMAND_SUITE",
                                                100, -325, 20,
                                                0.0F, 0.0F)))
                                .then(Commands.literal("command_office")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "COMMAND_SUITE",
                                                108, -327, -25,
                                                180.0F, 0.0F)))
                                .then(Commands.literal("magi_ring")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "MAGI_CORE",
                                                12, -360, 0,
                                                90.0F, 18.0F)))
                                .then(Commands.literal("west_entry")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "WEST_SUPPORT",
                                                -176, -348, 64,
                                                180.0F, 0.0F)))
                                .then(Commands.literal("west_seam")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "WEST_SUPPORT",
                                                -198, -360, 32,
                                                90.0F, 0.0F)))
                                .then(Commands.literal("exterior_ring")
                                        .executes(context -> visitFabric(
                                                context.getSource(),
                                                GeoFrontFabricPlan.Feature
                                                        .ROAD_NETWORK,
                                                -220, -360, 32,
                                                0.0F, 0.0F)))
                                .then(Commands.literal("lake_overlook")
                                        .executes(context -> visitFabric(
                                                context.getSource(),
                                                GeoFrontFabricPlan.Feature
                                                        .LANDSCAPE,
                                                -288, -360, 40,
                                                90.0F, 4.0F)))
                                .then(Commands.literal("garden")
                                        .executes(context -> visitFabric(
                                                context.getSource(),
                                                GeoFrontFabricPlan.Feature
                                                        .LANDSCAPE,
                                                -228, -360, 180,
                                                90.0F, 6.0F)))
                                .then(Commands.literal("pyramid_plaza")
                                        .executes(context -> visitFabric(
                                                context.getSource(),
                                                GeoFrontFabricPlan.Feature
                                                        .PYRAMID_PLAZA,
                                                0, -360, 212,
                                                180.0F, -8.0F)))
                                .then(Commands.literal("logistics_yard")
                                        .executes(context -> visitFabric(
                                                context.getSource(),
                                                GeoFrontFabricPlan.Feature
                                                        .LOGISTICS,
                                                360, -360, 232,
                                                180.0F, 2.0F)))
                                .then(Commands.literal("lcl_overlook")
                                        .executes(context -> visitFabric(
                                                context.getSource(),
                                                GeoFrontFabricPlan.Feature
                                                        .LANDSCAPE,
                                                0, -360, -204,
                                                180.0F, 8.0F)))
                                .then(Commands.literal("mechanical_trunk")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "MECH_PERSONNEL_TRUNK",
                                                0, -408, 706,
                                                180.0F, 0.0F)))
                                .then(Commands.literal("unit00_cage")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "UNIT00_CAGE",
                                                -389, -408, 760,
                                                180.0F, 5.0F)))
                                .then(Commands.literal("unit01_cage")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "UNIT01_CAGE",
                                                0, -408, 760,
                                                180.0F, 5.0F)))
                                .then(Commands.literal("unit02_cage")
                                        .executes(context -> visit(
                                                context.getSource(),
                                                "UNIT02_CAGE",
                                                389, -408, 760,
                                                180.0F, 5.0F))))
                        .then(Commands.literal("programme")
                                .then(Commands.literal("command_core")
                                        .executes(context ->
                                                startCommandCore(
                                                        context.getSource())))
                                .then(Commands.literal("public_backbone")
                                        .executes(context ->
                                                startPublicBackbone(
                                                        context.getSource())))
                                .then(Commands.literal("exterior_loop")
                                        .executes(context ->
                                                startExteriorLoop(
                                                        context.getSource())))
                                .then(Commands.literal("dogma_backbone")
                                        .executes(context ->
                                                startDogmaBackbone(
                                                        context.getSource())))
                                .then(Commands.literal("unit01_backbone")
                                        .executes(context ->
                                                startUnit01Backbone(
                                                        context.getSource())))
                                .then(Commands.literal("eva_backbone")
                                        .executes(context ->
                                                startEvaBackbone(
                                                        context.getSource()))))
                        .then(Commands.literal("fabric")
                                .then(Commands.literal("commit")
                                        .executes(context -> commitFabric(
                                                context.getSource())))
                                .then(Commands.literal("build_all")
                                        .executes(context -> startFabricAll(
                                                context.getSource())))
                                .then(Commands.literal(
                                                "cavern_surface_finish")
                                        .executes(context -> startFabric(
                                                context.getSource(),
                                                GeoFrontFabricPlan.Feature
                                                        .CAVERN_SURFACE_FINISH)))
                                .then(Commands.literal("pyramid_plaza")
                                        .executes(context -> startFabric(
                                                context.getSource(),
                                                GeoFrontFabricPlan.Feature
                                                        .PYRAMID_PLAZA)))
                                .then(Commands.literal("road_network")
                                        .executes(context -> startFabric(
                                                context.getSource(),
                                                GeoFrontFabricPlan.Feature
                                                        .ROAD_NETWORK)))
                                .then(Commands.literal("landscape")
                                        .executes(context -> startFabric(
                                                context.getSource(),
                                                GeoFrontFabricPlan.Feature
                                                        .LANDSCAPE)))
                                .then(Commands.literal("logistics")
                                        .executes(context -> startFabric(
                                                context.getSource(),
                                                GeoFrontFabricPlan.Feature
                                                        .LOGISTICS)))
                                .then(Commands.literal("lighting")
                                        .executes(context -> startFabric(
                                                context.getSource(),
                                                GeoFrontFabricPlan.Feature
                                                        .LIGHTING)))
                                .then(Commands.literal("west_seam")
                                        .executes(context -> startFabric(
                                                context.getSource(),
                                                GeoFrontFabricPlan.Feature
                                                        .WEST_SEAM))))
                        .then(Commands.literal("build")
                                .then(Commands.literal("tokyo3_apron")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "TOKYO3_APRON")))
                                .then(Commands.literal("h01_connector")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "H01_CV_CONNECTOR")))
                                .then(Commands.literal("nerv_foyer")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "NERV_FOYER")))
                                .then(Commands.literal("geofront_transit")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "GEOFRONT_TRANSIT")))
                                .then(Commands.literal("public_lift_shaft")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "PUBLIC_LIFT_SHAFT")))
                                .then(Commands.literal("surface_transit")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "SURFACE_TRANSIT")))
                                .then(Commands.literal("command_volume")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "COMMAND_VOLUME")))
                                .then(Commands.literal("command_spine")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "CMD_LIFT_SPINE")))
                                .then(Commands.literal("command_suite")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "COMMAND_SUITE")))
                                .then(Commands.literal("staff_lift")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "STAFF_LIFT_SHAFT")))
                                .then(Commands.literal("west_service")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "WEST_SERVICE_SPINE")))
                                .then(Commands.literal("west_support")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "WEST_SUPPORT")))
                                .then(Commands.literal("east_service")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "EAST_SERVICE_SPINE")))
                                .then(Commands.literal("staff_service")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "STAFF_SERVICE_CONNECTOR")))
                                .then(Commands.literal("magi_core")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "MAGI_CORE")))
                                .then(Commands.literal("magi_dogma_spine")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "MAGI_DOGMA_SPINE")))
                                .then(Commands.literal("dogma_lift")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "DOGMA_LIFT_SHAFT")))
                                .then(Commands.literal("dogma_spine")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "DOGMA_SPINE")))
                                .then(Commands.literal("lilith_chamber")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "LILITH_CHAMBER")))
                                .then(Commands.literal("mechanical_access")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "MECH_ACCESS_SPINE")))
                                .then(Commands.literal("mechanical_airlock")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "MECH_AIRLOCK_LINK")))
                                .then(Commands.literal("mechanical_trunk")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "MECH_PERSONNEL_TRUNK")))
                                .then(Commands.literal("unit00_cage")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "UNIT00_CAGE")))
                                .then(Commands.literal("unit01_cage")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "UNIT01_CAGE")))
                                .then(Commands.literal("unit02_cage")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "UNIT02_CAGE")))
                                .then(Commands.literal("unit01_carrier")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "UNIT01_CARRIER")))
                                .then(Commands.literal("unit01_switchyard")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "UNIT01_SWITCHYARD")))
                                .then(Commands.literal("unit01_silo")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "UNIT01_SILO")))
                                .then(Commands.literal("unit01_surface_head")
                                        .executes(context -> build(
                                                context.getSource(),
                                                "UNIT01_SURFACE_HEAD"))))));
    }

    private static int bootstrap(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerLevel level = requireGeoFront(source);
        FacilityV2BootstrapDirector.StartResult result =
                FacilityV2BootstrapDirector.start(level);
        if (!result.accepted())
        {
            source.sendFailure(Component.literal(result.message()));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(
                "FacilitySchema v2 zero-write preflight started. "
                        + "Use /seele facility_v2 status; no legacy builder "
                        + "will run."), false);
        return 1;
    }

    private static int status(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerLevel level = requireGeoFront(source);
        FacilityV2SavedData data = FacilityV2SavedData.get(level);
        source.sendSuccess(() -> Component.literal(
                "Facility v2: " + data.summary() + " | preflight="
                        + FacilityV2BootstrapDirector.status(
                        source.getServer()) + " | "
                        + FacilityV2ProgrammeSavedData.get(level).summary()
                        + " | fabric="
                        + GeoFrontFabricSavedData.get(level).summary()),
                false);
        return 1;
    }

    private static int commitFabric(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerLevel level = requireGeoFront(source);
        try
        {
            GeoFrontFabricDirector.commit(level);
        }
        catch (IllegalStateException exception)
        {
            source.sendFailure(Component.literal(exception.getMessage()));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(
                "GeoFrontFabric revision "
                        + GeoFrontFabricPlan.FABRIC_REVISION
                        + " committed without changing any "
                        + "FacilitySchema owner. Use build_all to start its "
                        + "budgeted one-time construction."), true);
        return 1;
    }

    private static int startFabricAll(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerLevel level = requireGeoFront(source);
        try
        {
            GeoFrontFabricDirector.startAll(level);
        }
        catch (IllegalStateException exception)
        {
            source.sendFailure(Component.literal(exception.getMessage()));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(
                "GeoFrontFabric programme started. It writes authored "
                        + "surfaces only, loads at most one new chunk per "
                        + "tick, and never enters a facility owner."), true);
        return 1;
    }

    private static int startFabric(
            CommandSourceStack source,
            GeoFrontFabricPlan.Feature feature)
            throws CommandSyntaxException
    {
        ServerLevel level = requireGeoFront(source);
        try
        {
            GeoFrontFabricDirector.start(level, feature);
        }
        catch (IllegalStateException exception)
        {
            source.sendFailure(Component.literal(exception.getMessage()));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(
                "GeoFrontFabric queued " + feature.id()
                        + " work=" + feature.authoredWork()), true);
        return 1;
    }

    private static int startPublicBackbone(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerLevel level = requireGeoFront(source);
        try
        {
            FacilityV2ProgrammeDirector.startPublicBackbone(level);
        }
        catch (IllegalStateException exception)
        {
            source.sendFailure(Component.literal(exception.getMessage()));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(
                "Facility v2 public backbone programme started. "
                        + "Owners will build sequentially and unfinished "
                        + "destinations remain physically sealed."), true);
        return 1;
    }

    private static int startCommandCore(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerLevel level = requireGeoFront(source);
        try
        {
            FacilityV2ProgrammeDirector.startCommandCore(level);
        }
        catch (RuntimeException exception)
        {
            source.sendFailure(Component.literal(exception.getMessage()));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(
                "Facility v2 command-core slice started. Foyer, H-01, "
                        + "continuous command volume, secure lift, suite and "
                        + "MAGI observation will build sequentially; "
                        + "unfinished routes remain physically sealed."),
                true);
        return 1;
    }

    private static int startExteriorLoop(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerLevel level = requireGeoFront(source);
        try
        {
            FacilityV2ProgrammeDirector.startExteriorLoop(level);
        }
        catch (RuntimeException exception)
        {
            source.sendFailure(Component.literal(exception.getMessage()));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(
                "Facility v2 exterior-loop slice started. The west service "
                        + "spine and supported exterior landing will build "
                        + "sequentially; the civil seam stays sealed until "
                        + "the exterior fabric receipts are complete."),
                true);
        return 1;
    }

    private static int startDogmaBackbone(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerLevel level = requireGeoFront(source);
        try
        {
            FacilityV2ProgrammeDirector.startDogmaBackbone(level);
        }
        catch (IllegalStateException exception)
        {
            source.sendFailure(Component.literal(exception.getMessage()));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(
                "Facility v2 MAGI/Dogma programme started. "
                        + "Lilith will be installed only after the sealed "
                        + "chamber receives its completion receipt."), true);
        return 1;
    }

    private static int startUnit01Backbone(CommandSourceStack source)
            throws CommandSyntaxException
    {
        return startEvaBackbone(source);
    }

    private static int startEvaBackbone(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerLevel level = requireGeoFront(source);
        try
        {
            FacilityV2ProgrammeDirector.startEvaBackbone(level);
        }
        catch (IllegalStateException exception)
        {
            source.sendFailure(Component.literal(exception.getMessage()));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(
                "Facility v2 three-line EVA programme started: restricted "
                        + "access, three wet cages, three straight carriers "
                        + "and three independent launch shafts."), true);
        return 1;
    }

    private static int build(CommandSourceStack source, String zoneId)
            throws CommandSyntaxException
    {
        ServerLevel level = requireGeoFront(source);
        FacilityV2SavedData data = FacilityV2SavedData.get(level);
        if (!data.commissioned())
        {
            source.sendFailure(Component.literal(
                    "Facility v2 is not commissioned. Run "
                            + "/seele facility_v2 bootstrap first."));
            return 0;
        }
        try
        {
            FacilityV2BuildDirector.start(level,
                    FacilityV2Plans.resolve(data.manifest(), zoneId));
        }
        catch (IllegalStateException | IllegalArgumentException exception)
        {
            source.sendFailure(Component.literal(exception.getMessage()));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(
                "Facility v2 queued " + zoneId
                        + " as a clean owner build."), true);
        return 1;
    }

    private static int visit(
            CommandSourceStack source, String requiredZone,
            int relativeX, int y, int relativeZ, float yaw, float pitch)
            throws CommandSyntaxException
    {
        ServerLevel level = requireGeoFront(source);
        FacilityV2SavedData data = FacilityV2SavedData.get(level);
        if (!data.commissioned()
                || data.requireZone(requiredZone).state()
                != FacilityV2SavedData.ZoneState.COMPLETE)
        {
            source.sendFailure(Component.literal(
                    "Facility v2 destination is not complete: "
                            + requiredZone));
            return 0;
        }
        FacilitySchemaV2.ResolvedManifest manifest = data.manifest();
        ServerPlayer player = source.getPlayerOrException();
        player.teleportTo(level,
                manifest.centre().getX() + relativeX + 0.5D,
                y,
                manifest.centre().getZ() + relativeZ + 0.5D,
                yaw, pitch);
        source.sendSuccess(() -> Component.literal(
                "Facility v2 visual checkpoint: " + requiredZone), false);
        return 1;
    }

    private static int visitFabric(
            CommandSourceStack source,
            GeoFrontFabricPlan.Feature requiredFeature,
            int relativeX, int y, int relativeZ, float yaw, float pitch)
            throws CommandSyntaxException
    {
        ServerLevel level = requireGeoFront(source);
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        GeoFrontFabricSavedData fabric =
                GeoFrontFabricSavedData.get(level);
        if (!facility.commissioned()
                || !fabric.validFor(facility)
                || fabric.requireFeature(requiredFeature).state()
                != GeoFrontFabricSavedData.FeatureState.COMPLETE)
        {
            source.sendFailure(Component.literal(
                    "GeoFront fabric destination is not complete: "
                            + requiredFeature.id()));
            return 0;
        }
        FacilitySchemaV2.ResolvedManifest manifest = facility.manifest();
        ServerPlayer player = source.getPlayerOrException();
        player.teleportTo(level,
                manifest.centre().getX() + relativeX + 0.5D,
                y,
                manifest.centre().getZ() + relativeZ + 0.5D,
                yaw, pitch);
        source.sendSuccess(() -> Component.literal(
                "GeoFront exterior checkpoint: "
                        + requiredFeature.id()), false);
        return 1;
    }

    private static ServerLevel requireGeoFront(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerLevel level = source.getServer().getLevel(
                com.projectseele.world.FacilitySchemaV2.DIMENSION);
        if (level == null)
        {
            throw GEOFRONT_UNAVAILABLE.create();
        }
        return level;
    }
}

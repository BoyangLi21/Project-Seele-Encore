package com.projectseele.visual;

import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.registry.ModEntities;
import com.projectseele.world.EvaHangarBuilder;
import com.projectseele.world.GeoFrontBuilder;
import com.projectseele.world.EvaLogisticsDirector;
import com.projectseele.world.FacilityWorldPolicy;
import com.projectseele.world.GeoFrontBuilder.GeoFrontAudit;
import com.projectseele.world.IntegratedNervMapBuilder;
import com.projectseele.world.IntegratedNervMapBuilder.IntegratedAudit;
import com.projectseele.world.IntegratedNervMapBuilder.LiftLink;
import com.projectseele.world.LocalMapAssetLoader;
import com.projectseele.world.NervOperationsCentreBuilder;
import com.projectseele.world.S24CoordinateTransform;
import com.projectseele.world.TerminalDogmaBuilder;
import com.projectseele.world.ThirdTokyoSurfaceBuilder;
import com.projectseele.world.Tokyo3RetractionDirector;
import com.projectseele.world.Tokyo3RetractionDirector.RequestResult;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.event.entity.player.PlayerEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Builds and operates the physically continuous Tokyo-3 / GeoFront world. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class GeoFrontCommands
{
    public static final ResourceKey<Level> GEOFRONT = ResourceKey.create(
            Registries.DIMENSION,
            new ResourceLocation(ProjectSeele.MODID, "geofront"));
    public static final BlockPos ORIGIN = IntegratedNervMapBuilder.GEOFRONT_ORIGIN;
    public static final BlockPos TOKYO3_ORIGIN = IntegratedNervMapBuilder.TOKYO3_ORIGIN;

    private static final String RETURN_DIMENSION = "SeeleGeoFrontReturnDimension";
    private static final String RETURN_X = "SeeleGeoFrontReturnX";
    private static final String RETURN_Y = "SeeleGeoFrontReturnY";
    private static final String RETURN_Z = "SeeleGeoFrontReturnZ";
    private static final int SORTIE_CHUNK_RADIUS = 4;
    private static final double SORTIE_ENTITY_RADIUS = 72.0D;
    /** Measured, read-only S22 review landings; never repair geometry here. */
    private static final BlockPos S22_MAIN_ENTRANCE_FEET =
            new BlockPos(-80, -443, 210);
    private static final BlockPos S22_LAKE_TERMINAL_FEET =
            new BlockPos(-220, -460, 120);
    private static final BlockPos S22_EVA_DOCK_FEET =
            new BlockPos(-140, -450, 151);
    private static final Set<UUID> VISUAL_SORTIE_UNITS = new HashSet<>();
    private static boolean visualLinkInProgress;

    private GeoFrontCommands() {}

    @SubscribeEvent
    public static void register(RegisterCommandsEvent event)
    {
        if(!DevelopmentCommandsR43.enabled())return;
        CommandDispatcher<CommandSourceStack> dispatcher = event.getDispatcher();
        dispatcher.register(Commands.literal("seele")
                .requires(source -> source.hasPermission(2))
                .then(Commands.literal("geofront")
                        .then(Commands.literal("setup")
                                .executes(context -> setup(context.getSource())))
                        .then(Commands.literal("rebuild")
                                .executes(context -> rebuild(context.getSource())))
                        .then(Commands.literal("enter")
                                .executes(context -> enter(context.getSource())))
                        .then(Commands.literal("link")
                                .executes(context -> link(context.getSource())))
                        .then(Commands.literal("sortie_audit")
                                .executes(context -> sortieAudit(context.getSource())))
                        .then(Commands.literal("surface")
                                .executes(context -> surface(context.getSource())))
                        .then(Commands.literal("exit")
                                .executes(context -> exit(context.getSource())))
                        .then(Commands.literal("audit")
                                .executes(context -> audit(context.getSource())))
                        .then(Commands.literal("operations")
                                .executes(context -> operations(context.getSource())))
                        .then(Commands.literal("dogma")
                                .executes(context -> dogma(context.getSource())))
                        .then(Commands.literal("overview")
                                .executes(context -> overview(context.getSource())))
                        .then(Commands.literal("coastal")
                                .then(Commands.literal("entrance")
                                        .executes(context -> coastalLanding(
                                                context.getSource(),
                                                S22_MAIN_ENTRANCE_FEET,
                                                "NERV main entrance", 90.0F, 0.0F)))
                                .then(Commands.literal("lake")
                                        .executes(context -> coastalLanding(
                                                context.getSource(),
                                                S22_LAKE_TERMINAL_FEET,
                                                "GeoFront underground-lake terminal",
                                                -90.0F, 0.0F)))
                                .then(Commands.literal("dock")
                                        .executes(context -> coastalLanding(
                                                context.getSource(),
                                                S22_EVA_DOCK_FEET,
                                                "three-berth EVA docking apron",
                                                90.0F, 0.0F))))));
    }

    /**
     * The private evaluation save is copied from an empty Visual Lab template.
     * Its inherited overworld player position sits four blocks above the world
     * minimum, so a first manual login can fall before the user runs setup.
     */
    @SubscribeEvent
    public static void rescueStagedWorldLogin(PlayerEvent.PlayerLoggedInEvent event)
    {
        if (!(event.getEntity() instanceof ServerPlayer player))
        {
            return;
        }
        restoreManualPlayerPhysics(player);
        ServerLevel current = player.serverLevel();
        if (unsafeOverviewLogin(player, current))
        {
            if (teleportToLoadedSafeCell(player, current,
                    current.getSharedSpawnPos()))
            {
                ProjectSeele.LOGGER.info(
                        "Moved {} from an unsafe retired-GeoFront position to "
                                + "the already-loaded dimension spawn",
                        player.getGameProfile().getName());
            }
            else
            {
                player.displayClientMessage(Component.literal(
                        "Retired GeoFront position is unsafe and no loaded safe "
                                + "cell is available; an administrator must "
                                + "commission FacilitySchema v2."), false);
            }
            return;
        }
        if (!current.dimension().equals(Level.OVERWORLD)
                || !LocalMapAssetLoader.stagedEvaWorld(current)
                || player.getY() > current.getMinBuildHeight() + 8.0D)
        {
            return;
        }
        if (teleportToLoadedSafeCell(player, current,
                current.getSharedSpawnPos()))
        {
            ProjectSeele.LOGGER.info(
                    "Moved staged-world player {} from the empty template "
                            + "floor to its already-loaded spawn without "
                            + "building the retired GeoFront",
                    player.getGameProfile().getName());
        }
        else
        {
            player.displayClientMessage(Component.literal(
                    "FacilitySchema v2 is not commissioned. Login will not "
                            + "build or repair the retired GeoFront."), false);
        }
    }

    private static boolean teleportToLoadedSafeCell(ServerPlayer player,
                                                    ServerLevel level,
                                                    BlockPos feet)
    {
        if (!level.hasChunkAt(feet))
        {
            return false;
        }
        BlockPos floor = feet.below();
        BlockState floorState = level.getBlockState(floor);
        if (!level.getFluidState(feet).isEmpty()
                || !level.getFluidState(feet.above()).isEmpty()
                || floorState.isAir()
                || !floorState.getFluidState().isEmpty()
                || floorState.getCollisionShape(level, floor).isEmpty()
                || !level.getBlockState(feet).getCollisionShape(level, feet).isEmpty()
                || !level.getBlockState(feet.above())
                        .getCollisionShape(level, feet.above()).isEmpty())
        {
            return false;
        }
        player.teleportTo(level, feet.getX() + 0.5D, feet.getY(),
                feet.getZ() + 0.5D, player.getYRot(), player.getXRot());
        player.resetFallDistance();
        return true;
    }

    static int setup(CommandSourceStack source) throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "setup"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel level = geoFront(player);
        if (level == null)
        {
            source.sendFailure(Component.literal(
                    "GeoFront dimension is unavailable; verify the Project SEELE datapack."));
            return 0;
        }
        saveReturn(player);
        IntegratedAudit result = IntegratedNervMapBuilder.ensure(level);
        Tokyo3RetractionDirector.register(level,
                IntegratedNervMapBuilder.tokyo3Origin(level));
        logIntegratedAudit("setup", result);
        if (!result.valid())
        {
            source.sendFailure(Component.literal(
                    "The connected Tokyo-3 / GeoFront map failed audit: "
                            + result.summary()));
            return 0;
        }
        teleportOverview(player, level);
        source.sendSuccess(() -> Component.literal(
                "Connected Tokyo-3 / GeoFront map ready: three physical "
                        + IntegratedNervMapBuilder.ascentDistance() + "-block shafts. "
                        + "Run /seele geofront link to prepare Unit-00/01/02."),
                false);
        return 1;
    }

    /** Fixed build used by the unattended GeoFront screenshot target. */
    /**
     * Forces a complete physical rebuild, unlike {@link #setup} which reuses an
     * already-installed map and only repairs the audited fragments. This is the
     * developer path for applying geometry code changes (LCL fill, hangar
     * stairs, gallery concourse, cavern carve) that the incremental audit does
     * not detect. It is heavy but one-shot; the EVA fleet persists in saved
     * data and is untouched.
     */
    static int rebuild(CommandSourceStack source) throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "rebuild"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel level = geoFront(player);
        if (level == null)
        {
            source.sendFailure(Component.literal(
                    "GeoFront dimension is unavailable; verify the Project SEELE datapack."));
            return 0;
        }
        saveReturn(player);
        source.sendSuccess(() -> Component.literal(
                "Forcing a complete GeoFront rebuild (LCL fill, hangar stairs, "
                        + "gallery concourse, cavern shell). This can take a moment..."),
                false);
        IntegratedAudit result = IntegratedNervMapBuilder.build(level);
        Tokyo3RetractionDirector.register(level,
                IntegratedNervMapBuilder.tokyo3Origin(level));
        logIntegratedAudit("rebuild", result);
        if (!result.valid())
        {
            source.sendFailure(Component.literal(
                    "Rebuild finished but the map audit still failed: " + result.summary()));
            return 0;
        }
        teleportOverview(player, level);
        source.sendSuccess(() -> Component.literal(
                "GeoFront fully rebuilt: LCL, hangar stairs, gallery concourse and "
                        + "cavern shell refreshed."), false);
        return 1;
    }

    static int setupVisualCapture(CommandSourceStack source) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel level = geoFront(player);
        if (level == null)
        {
            throw new IllegalStateException("GeoFront visual dimension is unavailable");
        }
        // A previous manual session may have saved the automation player in
        // Unit-01.  Release that stale passenger relation before the strict
        // three-airframe canonicalization gate runs.
        restoreManualPlayerPhysics(player);
        level.setDayTime(6000L);
        level.setWeatherParameters(12000, 0, false, false);
        // Visual captures must not inherit a CITY ARMOUR state left by a
        // previous manual session. Restore the physical tower volumes before
        // the fixed-camera audit; changing SavedData alone can leave a valid
        // looking marker set above an empty skyline.
        RequestResult cityReset = Tokyo3RetractionDirector.forceDepth(level,
                IntegratedNervMapBuilder.tokyo3Origin(level), false);
        if (cityReset.accepted())
        {
            throw new IllegalStateException(
                    "Tokyo-3 restoration is running as a bounded transaction; "
                            + "rerun the visual capture after the skyline reaches DEPLOYED");
        }
        IntegratedAudit result = IntegratedNervMapBuilder.ensure(level);
        logIntegratedAudit("visual-setup", result);
        if (!result.valid())
        {
            throw new IllegalStateException(
                    "Integrated GeoFront visual setup failed audit: " + result.summary());
        }
        List<EvaUnit01Entity> linked = ensureContinuousSortieUnits(level);
        SortieAudit sortie = inspectLinkedUnits(player.getServer(), level, linked);
        if (!sortie.valid())
        {
            // Unattended captures are a destructive development fixture, not
            // a player command. Recover all three canonical units when an old
            // run left one deployed or its UUID in another dimension; normal
            // login and readiness checks continue to preserve deployed EVAs.
            ProjectSeele.LOGGER.warn(
                    "Visual GeoFront fixture repairing incomplete fleet: {}",
                    sortie.summary());
            for (int variant = 0; variant < 3; variant++)
            {
                EvaLogisticsDirector.forceReset(level, variant);
            }
            linked = ensureContinuousSortieUnits(level);
            sortie = inspectLinkedUnits(player.getServer(), level, linked);
        }
        logSortieAudit("geofront-visual", sortie);
        if (!sortie.valid())
        {
            throw new IllegalStateException(
                    "GeoFront visual launch bays failed audit after canonical reset: "
                            + sortie.summary());
        }
        // Exercise the same public navigation paths used during manual QA.
        // This catches unsafe overview landings and operations-route audit
        // regressions before the client starts jumping between camera rigs.
        if (overview(source) != 1 || operations(source) != 1)
        {
            throw new IllegalStateException(
                    "GeoFront overview/operations navigation smoke test failed");
        }
        ProjectSeele.LOGGER.info(
                "GeoFront navigation smoke test passed: overview landing is dry and operations routes are valid");
        BlockPos hiddenPlatform = IntegratedNervMapBuilder
                .geoFrontOrigin(level).offset(0, 3, 0);
        level.setBlock(hiddenPlatform, net.minecraft.world.level.block.Blocks.BARRIER
                .defaultBlockState(), net.minecraft.world.level.block.Block.UPDATE_CLIENTS);
        player.teleportTo(level, hiddenPlatform.getX() + 0.5D,
                hiddenPlatform.getY() + 1.0D, hiddenPlatform.getZ() + 0.5D,
                180.0F, 0.0F);
        return 1;
    }

    private static int enter(CommandSourceStack source) throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "enter"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel level = geoFront(player);
        if (level == null)
        {
            source.sendFailure(Component.literal("GeoFront dimension is unavailable."));
            return 0;
        }
        if (!IntegratedNervMapBuilder.isInstalled(level))
        {
            source.sendFailure(Component.literal(
                    "The connected map is not installed. "
                            + "Run /seele geofront setup first."));
            return 0;
        }
        saveReturn(player);
        teleportOverview(player, level);
        return 1;
    }

    /** Prepares three EVAs at the physical lower stations; no transfer occurs. */
    static int link(CommandSourceStack source) throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "link"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        if (player.isPassenger())
        {
            source.sendFailure(Component.literal(
                    "Dismount before linking the GeoFront sortie terminals."));
            return 0;
        }
        ServerLevel geoFront = geoFront(player);
        if (geoFront == null)
        {
            source.sendFailure(Component.literal("GeoFront dimension is unavailable."));
            return 0;
        }
        IntegratedNervMapBuilder.RuntimeAudit mapAudit =
                IntegratedNervMapBuilder.prepareRuntime(geoFront);
        Tokyo3RetractionDirector.register(geoFront,
                IntegratedNervMapBuilder.tokyo3Origin(geoFront));
        if (!mapAudit.launchReady())
        {
            source.sendFailure(Component.literal(
                    "Connected sortie route failed its runtime gate: "
                            + mapAudit.summary()));
            return 0;
        }
        List<EvaUnit01Entity> linked;
        try
        {
            linked = ensureContinuousSortieUnits(geoFront);
        }
        catch (IllegalStateException exception)
        {
            source.sendFailure(Component.literal(exception.getMessage()));
            return 0;
        }

        if (visualLinkInProgress)
        {
            VISUAL_SORTIE_UNITS.clear();
            linked.forEach(unit -> VISUAL_SORTIE_UNITS.add(unit.getUUID()));
        }

        SortieAudit result = inspectLinkedUnits(player.getServer(), geoFront,
                linked);
        logSortieAudit("link", result);
        if (!result.valid())
        {
            source.sendFailure(Component.literal(
                    "Physical sortie link failed audit: " + result.summary()));
            return 0;
        }

        if (!player.serverLevel().dimension().equals(GEOFRONT))
        {
            saveReturn(player);
        }
        BlockPos centralTerminal = IntegratedNervMapBuilder.lowerLiftBed(
                geoFront, 1);
        player.teleportTo(geoFront, centralTerminal.getX() + 0.5D,
                centralTerminal.getY() + 27.0D,
                centralTerminal.getZ() + 6.5D, 180.0F, -8.0F);
        source.sendSuccess(() -> Component.literal(
                "Physical sortie ready: Unit-00/01/02 are registered in their individual wet cages. "
                        + "Launch travels the same "
                        + IntegratedNervMapBuilder.ascentDistance()
                        + "-block shaft into Tokyo-3; no portal or EVA teleport."), false);
        return 1;
    }

    public static List<EvaUnit01Entity> ensureContinuousSortieUnits(ServerLevel level)
    {
        return EvaLogisticsDirector.ensureFleet(level);
    }
    /** Dedicated-world reset before the unattended cross-dimension sortie. */
    static void preloadVisualSortie(ServerPlayer player)
    {
        ServerLevel geoFront = geoFront(player);
        if (geoFront == null)
        {
            throw new IllegalStateException("GeoFront visual sortie dimension is unavailable");
        }
        // A linked-sortie capture is a launch-system test, not a city-motion
        // test. Normalize an interrupted or half-travelled skyline first so
        // the surface frame cannot inherit a previous retraction session and
        // report misleading 56/66 tower counts.
        RequestResult cityReset = Tokyo3RetractionDirector.forceDepth(
                geoFront, IntegratedNervMapBuilder.tokyo3Origin(geoFront),
                false);
        if (cityReset.accepted())
        {
            throw new IllegalStateException(
                    "Tokyo-3 restoration is still running; retry the sortie preload after DEPLOYED");
        }
        IntegratedNervMapBuilder.RuntimeAudit audit =
                IntegratedNervMapBuilder.prepareRuntime(geoFront);
        if (!audit.launchReady())
        {
            throw new IllegalStateException(
                    "GeoFront visual sortie runtime gate failed: "
                            + audit.summary());
        }
        if (!audit.valid())
        {
            ProjectSeele.LOGGER.warn(
                    "Visual sortie proceeding on a safe launch route while non-sortie facility audit remains incomplete: {}",
                    audit.summary());
        }
        loadSortieChunks(geoFront);
        restoreManualPlayerPhysics(player);
        BlockPos origin = IntegratedNervMapBuilder.geoFrontOrigin(geoFront);
        player.teleportTo(geoFront,
                origin.getX() + 0.5D,
                origin.getY() + GeoFrontBuilder.OBSERVATION_Y + 1.0D,
                origin.getZ() + GeoFrontBuilder.OBSERVATION_Z + 0.5D,
                180.0F, 0.0F);
        ProjectSeele.LOGGER.info(
                "Visual GeoFront sortie preloaded the three launch-bay chunk columns "
                        + "and entered them to activate persistent entities");
    }

    /** Dedicated-world reset before the unattended cross-dimension sortie. */
    static int linkVisualCapture(CommandSourceStack source) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel geoFront = geoFront(player);
        if (geoFront == null)
        {
            throw new IllegalStateException("GeoFront visual sortie dimension is unavailable");
        }
        int staleUnits = clearVisualSortieEntities(geoFront);
        ProjectSeele.LOGGER.info(
                "Visual GeoFront sortie cleanup removed {} persistent EVA entities",
                staleUnits);
        player.teleportTo(player.getServer().overworld(),
                0.5D, 97.0D, 0.5D, 180.0F, 0.0F);
        visualLinkInProgress = true;
        try
        {
            return link(player.createCommandSourceStack());
        }
        finally
        {
            visualLinkInProgress = false;
        }
    }

    /** Loads only the launch-bay neighbourhood before querying parked EVAs. */
    private static int clearVisualSortieEntities(ServerLevel geoFront)
    {
        loadSortieChunks(geoFront);

        BlockPos centre = IntegratedNervMapBuilder.lowerLiftBed(geoFront, 1);
        List<EvaUnit01Entity> stale = geoFront.getEntitiesOfClass(
                EvaUnit01Entity.class,
                new AABB(centre).inflate(SORTIE_ENTITY_RADIUS,
                        384.0D, SORTIE_ENTITY_RADIUS));
        // Reset through the fleet director so SavedData and the three new
        // UUIDs move together. Directly discarding entities leaves PARKED
        // canonical UUIDs pointing at nothing on the next launch.
        for (int variant = 0; variant < 3; variant++)
        {
            EvaLogisticsDirector.forceReset(geoFront, variant);
        }
        return stale.size();
    }

    private static void loadSortieChunks(ServerLevel geoFront)
    {
        BlockPos centre = IntegratedNervMapBuilder.lowerLiftBed(geoFront, 1);
        int originChunkX = centre.getX() >> 4;
        int originChunkZ = centre.getZ() >> 4;
        int chunkRadius = SORTIE_CHUNK_RADIUS;
        for (int chunkX = originChunkX - chunkRadius;
             chunkX <= originChunkX + chunkRadius; chunkX++)
        {
            for (int chunkZ = originChunkZ - chunkRadius;
                 chunkZ <= originChunkZ + chunkRadius; chunkZ++)
            {
                geoFront.getChunk(chunkX, chunkZ);
            }
        }
    }

    private static int sortieAudit(CommandSourceStack source) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel geoFront = geoFront(player);
        if (geoFront == null)
        {
            return 0;
        }
        SortieAudit result = inspectSortie(player.getServer(), geoFront);
        logSortieAudit("command", result);
        Component report = Component.literal(result.summary());
        if (result.valid())
        {
            source.sendSuccess(() -> report, false);
            return 1;
        }
        source.sendFailure(report);
        return 0;
    }

    static SortieAudit inspectSortie(net.minecraft.server.MinecraftServer server,
                                     ServerLevel geoFront)
    {
        List<EvaUnit01Entity> units = EvaLogisticsDirector.ensureFleet(geoFront);
        return inspectLinkedUnits(server, geoFront, units);
    }

    private static SortieAudit inspectLinkedUnits(
            net.minecraft.server.MinecraftServer server,
            ServerLevel geoFront, List<EvaUnit01Entity> units)
    {
        int linked = 0;
        int validDestinations = 0;
        for (EvaUnit01Entity unit : units)
        {
            if (!unit.hasSortieDestination())
            {
                continue;
            }
            linked++;
            ServerLevel destination = server.getLevel(unit.getSortieDestinationDimension());
            BlockPos bed = unit.getSortieDestinationBed();
            if (destination != null && bed != null
                    && destination.getBlockState(bed).is(
                            net.minecraft.world.level.block.Blocks.LODESTONE))
            {
                validDestinations++;
            }
        }
        boolean variants = hasAllVariants(units);
        // The current 2x logistics layout boards from the three wet-cage
        // bridge/crane rigs. GeoFrontBuilder.gantries() describes the removed
        // small prototype decks beside the shaft beds and must not veto a
        // fleet whose runtime hangar gate has already passed.
        boolean gantries = EvaHangarBuilder.runtimeInfrastructurePresent(
                geoFront, IntegratedNervMapBuilder.geoFrontOrigin(geoFront));
        boolean valid = units.size() == 3 && linked == 3 && validDestinations == 3
                && variants && gantries;
        return new SortieAudit(valid, units.size(), linked, validDestinations,
                variants, gantries);
    }

    /** Removes persistent entities from earlier unattended runs after the
     * destination dimension has activated its entity index. */
    static int pruneVisualSortieDuplicates(ServerLevel geoFront)
    {
        if (VISUAL_SORTIE_UNITS.size() != 3)
        {
            throw new IllegalStateException(
                    "Visual GeoFront sortie did not retain exactly three linked UUIDs");
        }
        List<EvaUnit01Entity> loaded = geoFront.getEntitiesOfClass(
                EvaUnit01Entity.class,
                new AABB(IntegratedNervMapBuilder.lowerLiftBed(
                        geoFront, 1)).inflate(
                        SORTIE_ENTITY_RADIUS, 384.0D, SORTIE_ENTITY_RADIUS));
        int removed = 0;
        for (EvaUnit01Entity unit : loaded)
        {
            if (!VISUAL_SORTIE_UNITS.contains(unit.getUUID()))
            {
                unit.discard();
                removed++;
            }
        }
        ProjectSeele.LOGGER.info(
                "Visual GeoFront sortie retained 3 linked UUIDs and removed {} stale entities",
                removed);
        return removed;
    }

    private static boolean hasAllVariants(List<EvaUnit01Entity> units)
    {
        boolean has00 = units.stream().anyMatch(
                unit -> unit.getUnitVariant() == EvaUnit01Entity.UNIT_00);
        boolean has01 = units.stream().anyMatch(
                unit -> unit.getUnitVariant() == EvaUnit01Entity.UNIT_01);
        boolean has02 = units.stream().anyMatch(
                unit -> unit.getUnitVariant() == EvaUnit01Entity.UNIT_02);
        return has00 && has01 && has02;
    }

    private static void logSortieAudit(String stage, SortieAudit result)
    {
        if (result.valid())
        {
            ProjectSeele.LOGGER.info("GeoFront sortie audit [{}]: {}", stage, result.summary());
        }
        else
        {
            ProjectSeele.LOGGER.error("GEOFRONT SORTIE INVALID [{}]: {}", stage,
                    result.summary());
        }
    }

    static record SortieAudit(boolean valid, int units, int linked,
                              int destinations, boolean variants, boolean gantries)
    {
        String summary()
        {
            return String.format(Locale.ROOT,
                    "valid=%s units=%d linked=%d destinations=%d/3 "
                            + "variants00/01/02=%s gantries=%s",
                    this.valid, this.units, this.linked, this.destinations,
                    this.variants, this.gantries);
        }
    }

    private static int surface(CommandSourceStack source) throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "surface"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel destination = geoFront(player);
        if (destination == null)
        {
            source.sendFailure(Component.literal("GeoFront dimension is unavailable."));
            return 0;
        }
        if (!IntegratedNervMapBuilder.isInstalled(destination))
        {
            source.sendFailure(Component.literal(
                    "The connected map is not installed. Run /seele geofront setup first."));
            return 0;
        }
        if (!player.serverLevel().dimension().equals(GEOFRONT))
        {
            saveReturn(player);
        }
        prepareSurfaceLanding(destination);
        restoreManualPlayerPhysics(player);
        BlockPos surfaceOrigin =
                IntegratedNervMapBuilder.tokyo3Origin(destination);
        player.teleportTo(destination,
                surfaceOrigin.getX() + 0.5D,
                surfaceOrigin.getY()
                        + ThirdTokyoSurfaceBuilder.OBSERVATION_Y + 1.0D,
                surfaceOrigin.getZ()
                        + ThirdTokyoSurfaceBuilder.OBSERVATION_Z + 0.5D,
                180.0F, 18.0F);
        source.sendSuccess(() -> Component.literal(
                "Tokyo-3 skyline deck. Normal EVA sorties reach this surface through "
                        + "the physical shaft; this command is only a developer camera shortcut."), false);
        return 1;
    }

    /**
     * Teleports only onto an already measured S22 walking cell.  Unlike the
     * retired overview shortcuts this path never creates a deck, clears a
     * volume or repairs a facility, so visual review cannot mutate the map.
     */
    private static int coastalLanding(CommandSourceStack source,
                                      BlockPos feet, String label,
                                      float yaw, float pitch)
            throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        if (!FacilityWorldPolicy.isS22Coastal(source.getServer()))
        {
            source.sendFailure(Component.literal(
                    "Coastal review shortcuts are available only in "
                            + "SEELE_S22_COASTAL."));
            return 0;
        }
        ServerLevel level = geoFront(player);
        if (level == null)
        {
            source.sendFailure(Component.literal(
                    "GeoFront dimension is unavailable."));
            return 0;
        }
        feet = S24CoordinateTransform.apply(source.getServer(), feet);
        level.getChunkAt(feet);
        if (!player.serverLevel().dimension().equals(GEOFRONT))
        {
            saveReturn(player);
        }
        restoreManualPlayerPhysics(player);
        if (!teleportToLoadedSafeCell(player, level, feet))
        {
            source.sendFailure(Component.literal(
                    "S22 review landing is no longer safe at "
                            + feet.toShortString() + "; no blocks were changed."));
            return 0;
        }
        player.setYRot(yaw);
        player.setXRot(pitch);
        source.sendSuccess(() -> Component.literal(
                "S22 visual review: " + label + "."), false);
        return 1;
    }

    private static int exit(CommandSourceStack source) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        CompoundTag data = player.getPersistentData();
        ServerLevel destination = player.getServer().overworld();
        double x = destination.getSharedSpawnPos().getX() + 0.5D;
        double y = destination.getSharedSpawnPos().getY() + 1.0D;
        double z = destination.getSharedSpawnPos().getZ() + 0.5D;
        if (data.contains(RETURN_DIMENSION))
        {
            ResourceLocation location = ResourceLocation.tryParse(
                    data.getString(RETURN_DIMENSION));
            if (location != null)
            {
                ServerLevel stored = player.getServer().getLevel(ResourceKey.create(
                        Registries.DIMENSION, location));
                if (stored != null)
                {
                    destination = stored;
                    x = data.getDouble(RETURN_X);
                    y = data.getDouble(RETURN_Y);
                    z = data.getDouble(RETURN_Z);
                }
            }
        }
        restoreManualPlayerPhysics(player);
        player.teleportTo(destination, x, y, z, player.getYRot(), player.getXRot());
        source.sendSuccess(() -> Component.literal(
                "Exited the combined Tokyo-3 / GeoFront development world."), false);
        return 1;
    }

    private static int audit(CommandSourceStack source) throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "audit"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel level = geoFront(player);
        if (level == null)
        {
            source.sendFailure(Component.literal("GeoFront dimension is unavailable."));
            return 0;
        }
        IntegratedAudit result = IntegratedNervMapBuilder.inspect(level);
        logIntegratedAudit("command", result);
        if (!result.valid())
        {
            source.sendFailure(Component.literal(result.summary()));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(result.summary()), false);
        return 1;
    }

    private static int overview(CommandSourceStack source) throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "overview"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel level = geoFront(player);
        if (level == null)
        {
            return 0;
        }
        if (!IntegratedNervMapBuilder.isInstalled(level))
        {
            source.sendFailure(Component.literal(
                    "The connected map is not installed. Run /seele geofront setup first."));
            return 0;
        }
        if (!player.serverLevel().dimension().equals(GEOFRONT))
        {
            saveReturn(player);
        }
        teleportOverview(player, level);
        return 1;
    }

    private static int operations(CommandSourceStack source) throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "operations"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel level = geoFront(player);
        if (level == null)
        {
            source.sendFailure(Component.literal("GeoFront dimension is unavailable."));
            return 0;
        }
        if (!IntegratedNervMapBuilder.isInstalled(level))
        {
            source.sendFailure(Component.literal(
                    "The connected map is not installed. Run /seele geofront setup first."));
            return 0;
        }
        BlockPos origin = IntegratedNervMapBuilder.geoFrontOrigin(level);
        NervOperationsCentreBuilder.OperationsAudit result =
                NervOperationsCentreBuilder.repairRuntimeAccess(level, origin);
        if (!result.runtimePhysicalValid())
        {
            source.sendFailure(Component.literal(
                    "NERV operations centre failed its structural audit: "
                            + result.summary()));
            return 0;
        }
        if (!player.serverLevel().dimension().equals(GEOFRONT))
        {
            saveReturn(player);
        }
        prepareOperationsLanding(level);
        restoreManualPlayerPhysics(player);
        player.teleportTo(level, origin.getX() + 0.5D,
                origin.getY() + 8.0D,
                origin.getZ() + 18.5D, 180.0F, 0.0F);
        source.sendSuccess(() -> Component.literal(
                "NERV operations centre: tactical command level."), false);
        return 1;
    }

    private static int dogma(CommandSourceStack source) throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "dogma"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel level = geoFront(player);
        if (level == null)
        {
            source.sendFailure(Component.literal("GeoFront dimension is unavailable."));
            return 0;
        }
        BlockPos origin = IntegratedNervMapBuilder.geoFrontOrigin(level);
        GeoFrontAudit result = GeoFrontBuilder.inspect(level, origin);
        if (!result.terminalDogma().valid())
        {
            source.sendFailure(Component.literal(
                    "Terminal Dogma failed its physical-route audit: "
                            + result.terminalDogma().summary()));
            return 0;
        }
        if (!player.serverLevel().dimension().equals(GEOFRONT))
        {
            saveReturn(player);
        }
        restoreManualPlayerPhysics(player);
        player.teleportTo(level, origin.getX() + 0.5D,
                origin.getY() + TerminalDogmaBuilder.FACILITY_Y_OFFSET
                        + TerminalDogmaBuilder.OBSERVATION_Y + 1.0D,
                origin.getZ() + TerminalDogmaBuilder.OBSERVATION_Z + 0.5D,
                180.0F, 0.0F);
        source.sendSuccess(() -> Component.literal(
                "Terminal Dogma observation gallery. This is a developer camera shortcut; "
                        + "the real route begins at the east end of the NERV lower concourse "
                        + "and descends the physical Central Dogma ladder shaft."), false);
        return 1;
    }

    public static ServerLevel geoFront(ServerPlayer player)
    {
        return player.getServer().getLevel(GEOFRONT);
    }

    private static void teleportOverview(ServerPlayer player, ServerLevel level)
    {
        prepareOverviewLanding(level);
        restoreManualPlayerPhysics(player);
        BlockPos origin = IntegratedNervMapBuilder.geoFrontOrigin(level);
        player.teleportTo(level,
                origin.getX() + 0.5D,
                origin.getY() + GeoFrontBuilder.OBSERVATION_Y + 1.0D,
                origin.getZ() + GeoFrontBuilder.OBSERVATION_Z + 0.5D,
                180.0F, 16.0F);
    }

    /**
     * Clears detached-camera state before returning control to a person.
     * Visual Lab intentionally uses no-gravity tracking positions, but that
     * flag is persistent entity data and must never survive into manual play.
     */
    public static void restoreManualPlayerPhysics(ServerPlayer player)
    {
        boolean cameraResidue = player.isNoGravity();
        player.stopRiding();
        player.setNoGravity(false);
        player.setDeltaMovement(Vec3.ZERO);
        player.fallDistance = 0.0F;
        if (cameraResidue && player.getAbilities().flying)
        {
            player.getAbilities().flying = false;
            player.onUpdateAbilities();
        }
    }

    private static void prepareOverviewLanding(ServerLevel level)
    {
        BlockPos floor = IntegratedNervMapBuilder.geoFrontOrigin(level).offset(
                0, GeoFrontBuilder.OBSERVATION_Y,
                GeoFrontBuilder.OBSERVATION_Z);
        prepareSafeLanding(level, floor, 4,
                Blocks.SMOOTH_STONE.defaultBlockState(), true);
        setIfDifferent(level, floor, Blocks.LODESTONE.defaultBlockState());
    }

    private static boolean unsafeOverviewLogin(ServerPlayer player,
                                               ServerLevel level)
    {
        if (!level.dimension().equals(GEOFRONT))
        {
            return false;
        }
        BlockPos expectedFloor = IntegratedNervMapBuilder
                .geoFrontOrigin(level).offset(0,
                GeoFrontBuilder.OBSERVATION_Y,
                GeoFrontBuilder.OBSERVATION_Z);
        if (Math.abs(player.getX() - (expectedFloor.getX() + 0.5D)) > 12.0D
                || Math.abs(player.getZ() - (expectedFloor.getZ() + 0.5D)) > 12.0D
                || Math.abs(player.getY() - (expectedFloor.getY() + 1.0D)) > 12.0D)
        {
            return false;
        }
        BlockPos feet = player.blockPosition();
        BlockPos floor = feet.below();
        BlockState floorState = level.getBlockState(floor);
        return !level.getFluidState(feet).isEmpty()
                || floorState.isAir()
                || !floorState.getFluidState().isEmpty()
                || floorState.getCollisionShape(level, floor).isEmpty();
    }

    private static void prepareSurfaceLanding(ServerLevel level)
    {
        BlockPos floor = IntegratedNervMapBuilder.tokyo3Origin(level).offset(0,
                ThirdTokyoSurfaceBuilder.OBSERVATION_Y,
                ThirdTokyoSurfaceBuilder.OBSERVATION_Z);
        prepareSafeLanding(level, floor, 2,
                Blocks.SMOOTH_STONE.defaultBlockState(), true);
        setIfDifferent(level, floor, Blocks.LODESTONE.defaultBlockState());
    }

    private static void prepareOperationsLanding(ServerLevel level)
    {
        BlockPos floor = IntegratedNervMapBuilder.geoFrontOrigin(level).offset(0,
                NervOperationsCentreBuilder.OPERATIONS_FLOOR_Y,
                NervOperationsCentreBuilder.OPERATIONS_ENTRY_Z);
        prepareSafeLanding(level, floor, 1,
                Blocks.POLISHED_BLACKSTONE.defaultBlockState(), false);
    }

    private static void prepareSafeLanding(ServerLevel level, BlockPos floor,
                                           int halfWidth,
                                           BlockState replacementFloor,
                                           boolean replaceDeck)
    {
        for (int x = -halfWidth; x <= halfWidth; x++)
        {
            for (int z = -halfWidth; z <= halfWidth; z++)
            {
                BlockPos deck = floor.offset(x, 0, z);
                level.getChunkAt(deck);
                BlockState current = level.getBlockState(deck);
                if (replaceDeck || current.isAir()
                        || !current.getFluidState().isEmpty()
                        || current.getCollisionShape(level, deck).isEmpty())
                {
                    setIfDifferent(level, deck, replacementFloor);
                }
                for (int y = 1; y <= 4; y++)
                {
                    setIfDifferent(level, deck.above(y),
                            Blocks.AIR.defaultBlockState());
                }
            }
        }
    }

    private static void setIfDifferent(ServerLevel level, BlockPos position,
                                       BlockState state)
    {
        if (!level.getBlockState(position).equals(state))
        {
            level.setBlock(position, state, Block.UPDATE_CLIENTS);
        }
    }

    private static void saveReturn(ServerPlayer player)
    {
        if (player.serverLevel().dimension().equals(GEOFRONT))
        {
            return;
        }
        CompoundTag data = player.getPersistentData();
        data.putString(RETURN_DIMENSION,
                player.serverLevel().dimension().location().toString());
        data.putDouble(RETURN_X, player.getX());
        data.putDouble(RETURN_Y, player.getY());
        data.putDouble(RETURN_Z, player.getZ());
    }

    private static boolean rejectRetiredAliasInCleanWorld(
            CommandSourceStack source, String alias)
    {
        boolean s19 = FacilityWorldPolicy.isCleanRebuild(source.getServer());
        boolean s20 = FacilityWorldPolicy.isS20Rebuild(source.getServer());
        if (!s19 && !s20)
        {
            return false;
        }
        source.sendFailure(Component.literal(
                "/seele geofront " + alias
                        + " belongs to the retired overlapping map pipeline "
                        + "and is disabled in "
                        + (s20 ? "SEELE_S20_REBUILD" : "SEELE_S19_CLEAN")
                        + ". Use the bounded S20 directors or "
                        + "/seele facility_v2 status for S19."));
        return true;
    }

    private static void logAudit(String stage, GeoFrontAudit result)
    {
        if (result.valid())
        {
            ProjectSeele.LOGGER.info("GeoFront audit [{}]: {}", stage, result.summary());
        }
        else
        {
            ProjectSeele.LOGGER.error("GEOFRONT INVALID [{}]: {}", stage, result.summary());
        }
    }

    private static void logIntegratedAudit(String stage, IntegratedAudit result)
    {
        if (result.valid())
        {
            ProjectSeele.LOGGER.info("Integrated NERV map audit [{}]: {}",
                    stage, result.summary());
        }
        else
        {
            ProjectSeele.LOGGER.error("INTEGRATED NERV MAP INVALID [{}]: {}",
                    stage, result.summary());
        }
    }
}

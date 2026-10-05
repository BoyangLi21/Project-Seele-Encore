package com.projectseele.visual;

import java.util.List;
import java.util.Locale;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.event.AngelSiegeDirector;
import com.projectseele.event.Tokyo3RamielBattleDirector;
import com.projectseele.event.Tokyo3RamielBattleDirector.BattleResult;
import com.projectseele.event.Tokyo3RamielBattleDirector.BattleStatus;
import com.projectseele.world.ThirdTokyoSurfaceBuilder;
import com.projectseele.world.ThirdTokyoSurfaceBuilder.DistrictAudit;
import com.projectseele.world.IntegratedNervMapBuilder;
import com.projectseele.world.EvaLogisticsDirector;
import com.projectseele.world.FacilityWorldPolicy;
import com.projectseele.world.Tokyo3RetractionDirector;
import com.projectseele.world.Tokyo3RetractionDirector.RequestResult;
import com.projectseele.world.Tokyo3RetractionDirector.Status;
import com.projectseele.world.Tokyo3RetractionSavedData;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Builds and audits the connected NERV-to-Tokyo-3 sortie battlefield. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class ThirdTokyoCommands
{
    private ThirdTokyoCommands() {}

    @SubscribeEvent
    public static void register(RegisterCommandsEvent event)
    {
        CommandDispatcher<CommandSourceStack> dispatcher = event.getDispatcher();
        if(!DevelopmentCommandsR43.enabled())
        {
            dispatcher.register(Commands.literal("seele").requires(s->s.hasPermission(2))
                    .then(Commands.literal("tokyo3")
                            .then(Commands.literal("status").executes(c->status(c.getSource())))
                            .then(Commands.literal("retract").executes(c->setRetraction(c.getSource(),true)))
                            .then(Commands.literal("restore").executes(c->setRetraction(c.getSource(),false)))));
            return;
        }
        dispatcher.register(Commands.literal("seele")
                .requires(source -> source.hasPermission(2))
                .then(Commands.literal("tokyo3")
                        .then(Commands.literal("setup")
                                .executes(context -> setup(context.getSource())))
                        .then(Commands.literal("audit")
                                .executes(context -> audit(context.getSource())))
                        .then(Commands.literal("retract")
                                .executes(context -> setRetraction(
                                        context.getSource(), true)))
                        .then(Commands.literal("restore")
                                .executes(context -> setRetraction(
                                        context.getSource(), false)))
                        .then(Commands.literal("retract_now")
                                .executes(context -> forceRetraction(
                                        context.getSource(), true)))
                        .then(Commands.literal("restore_now")
                                .executes(context -> forceRetraction(
                                        context.getSource(), false)))                        .then(Commands.literal("status")
                                .executes(context -> status(context.getSource())))
                        .then(Commands.literal("ramiel")
                                .executes(context -> ramielStart(context.getSource()))
                                .then(Commands.literal("start")
                                        .executes(context -> ramielStart(
                                                context.getSource())))
                                .then(Commands.literal("status")
                                        .executes(context -> ramielStatus(
                                                context.getSource())))
                                .then(Commands.literal("abort")
                                        .executes(context -> ramielAbort(
                                                context.getSource()))))
                        .then(Commands.literal("overview")
                                .executes(context -> overview(context.getSource()))))
                .then(Commands.literal("siege")
                        .then(Commands.literal("status")
                                .executes(context -> siegeStatus(
                                        context.getSource())))
                        .then(Commands.literal("abort")
                                .executes(context -> siegeAbort(
                                        context.getSource())))));
    }

    static int setup(CommandSourceStack source) throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "setup"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        if (player.isPassenger())
        {
            source.sendFailure(Component.literal(
                    "Dismount before constructing the Tokyo-3 sortie district."));
            return 0;
        }
        if (GeoFrontCommands.setup(source) != 1)
        {
            return 0;
        }
        teleportOverview(player,
                IntegratedNervMapBuilder.tokyo3Origin(player.serverLevel()));
        source.sendSuccess(() -> Component.literal(
                "Tokyo-3 skyline ready above the same GeoFront dimension. "
                        + "Run /seele geofront link, then board from the lower gantry."), false);
        return 1;
    }

    /** Fixed-world setup used by the unattended map screenshot target. */
    static int setupVisualCapture(CommandSourceStack source) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel level = player.getServer().getLevel(GeoFrontCommands.GEOFRONT);
        if (level == null)
        {
            throw new IllegalStateException("GeoFront dimension is unavailable");
        }
        player.stopRiding();
        BlockPos origin = IntegratedNervMapBuilder.tokyo3Origin(level);
        level.setDayTime(6000L);
        level.setWeatherParameters(12000, 0, false, false);
        // Do not let a prior manual CITY ARMOUR toggle make this fixed
        // visual fixture audit a different skyline on the next run.
        RequestResult cityReset = Tokyo3RetractionDirector.forceDepth(
                level, origin, false);
        if (cityReset.accepted())
        {
            throw new IllegalStateException(
                    "Tokyo-3 restoration is running as a bounded transaction; "
                            + "rerun the visual capture after /seele tokyo3 status reports DEPLOYED");
        }
        IntegratedNervMapBuilder.IntegratedAudit mapAudit =
                IntegratedNervMapBuilder.ensure(level);
        if (!mapAudit.valid())
        {
            throw new IllegalStateException(
                    "Integrated Tokyo-3 visual map failed audit: "
                            + mapAudit.summary());
        }
        List<EvaUnit01Entity> units = new java.util.ArrayList<>(3);
        for (int variant = 0; variant < 3; variant++)
        {
            units.add(EvaLogisticsDirector.forceReset(level, variant));
        }
        for (EvaUnit01Entity unit : units)
        {
            IntegratedNervMapBuilder.LiftLink lift =
                    IntegratedNervMapBuilder.lift(
                            level, unit.getUnitVariant());
            BlockPos bed = lift.surfaceBed();
            unit.clearSortieDestination();
            unit.moveTo(bed.getX() + 0.5D, bed.getY() + 1.0D,
                    bed.getZ() + 0.5D, EvaUnit01Entity.SILO_BAY_YAW, 0.0F);
            unit.setYRot(EvaUnit01Entity.SILO_BAY_YAW);
            unit.setYBodyRot(EvaUnit01Entity.SILO_BAY_YAW);
            unit.setYHeadRot(EvaUnit01Entity.SILO_BAY_YAW);
            unit.setDeltaMovement(net.minecraft.world.phys.Vec3.ZERO);
            unit.setNoGravity(true);
            unit.setNoAi(true);
            EvaLogisticsDirector.markDeployedForVisual(level, unit);
        }
        ProjectSeele.LOGGER.info(
                "Tokyo-3 integrated visual setup: map={} surfaceUnits={}",
                mapAudit.summary(), units.size());
        // The real player remains high over the city centre so all imported
        // chunks stay tracked while the independent camera visits each view.
        player.teleportTo(level, origin.getX() + 0.5D, origin.getY() + 50.0D,
                origin.getZ() + 0.5D, 180.0F, 0.0F);
        return 1;
    }

    static BlockPos fixedVisualOrigin(ServerLevel level)
    {
        // S22 is an authored coastal migration whose surface is valid before
        // the legacy integrated-map receipt becomes valid.  Falling back to
        // (0, 96, 0) made visual capture photograph unrelated seed terrain.
        if (FacilityWorldPolicy.isS22Coastal(level.getServer()))
        {
            return IntegratedNervMapBuilder.tokyo3Origin(level);
        }
        if (level.dimension().equals(GeoFrontCommands.GEOFRONT)
                && IntegratedNervMapBuilder.inspect(level).valid())
        {
            return IntegratedNervMapBuilder.tokyo3Origin(level);
        }
        return new BlockPos(0,
                Math.max(level.getMinBuildHeight() + 36,
                        Math.min(level.getMaxBuildHeight() - 48, 96)),
                0);
    }

    private static int audit(CommandSourceStack source) throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "audit"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        BlockPos origin = findOrigin(player);
        int depth = Tokyo3RetractionDirector.depth(player.serverLevel(), origin);
        TokyoAudit result = inspect(player.serverLevel(), origin, depth, false);
        logAudit("command", result);
        Component report = Component.literal(result.summary());
        if (result.valid())
        {
            source.sendSuccess(() -> report, false);
            return 1;
        }
        source.sendFailure(report);
        return 0;
    }

    /** Runtime gate used after the unattended GeoFront sortie reaches Tokyo-3. */
    static int auditVisualCapture(CommandSourceStack source) throws CommandSyntaxException
    {
        return audit(source);
    }

    private static int setRetraction(CommandSourceStack source, boolean retract)
            throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(
                source, retract ? "retract" : "restore"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        BlockPos origin = findOrigin(player);
        RequestResult result = Tokyo3RetractionDirector.request(
                player.serverLevel(), origin, retract);
        source.sendSuccess(() -> Component.literal(result.message()), false);
        return result.accepted() ? 1 : 0;
    }

    private static int forceRetraction(CommandSourceStack source, boolean retract)
            throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(
                source, retract ? "retract_now" : "restore_now"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        BlockPos origin = findOrigin(player);
        RequestResult result = Tokyo3RetractionDirector.forceDepth(
                player.serverLevel(), origin, retract);
        source.sendSuccess(() -> Component.literal(result.message()), false);
        return result.accepted() ? 1 : 0;
    }
    private static int status(CommandSourceStack source) throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "status"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        BlockPos origin = findOrigin(player);
        Status status = Tokyo3RetractionDirector.status(player.serverLevel(), origin);
        source.sendSuccess(() -> Component.literal(String.format(Locale.ROOT,
                "%s 城市状态=%s，事务终点=%d/%d，目标终点=%d（终点编号不代表实际米数）。",
                status.motionReport(),
                status.phase(), status.depth(), status.maximumDepth(),
                status.targetDepth())), false);
        return 1;
    }

    private static int ramielStart(CommandSourceStack source)
            throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "ramiel start"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel level = player.serverLevel();
        if (!level.dimension().equals(GeoFrontCommands.GEOFRONT))
        {
            source.sendFailure(Component.literal(
                    "Enter the integrated GeoFront/Tokyo-3 dimension first."));
            return 0;
        }
        IntegratedNervMapBuilder.RuntimeAudit audit =
                IntegratedNervMapBuilder.prepareRuntime(level);
        if (!audit.valid())
        {
            source.sendFailure(Component.literal(
                    "Operation Yashima refused: live sortie route failed: "
                            + audit.summary()));
            return 0;
        }
        BattleResult result = Tokyo3RamielBattleDirector.start(level,
                IntegratedNervMapBuilder.tokyo3Origin(level), player);
        if (!result.accepted())
        {
            source.sendFailure(Component.literal(result.message()));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(result.message()), false);
        return 1;
    }

    private static int ramielStatus(CommandSourceStack source)
            throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "ramiel status"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        BattleStatus status = Tokyo3RamielBattleDirector.status(
                player.serverLevel(), IntegratedNervMapBuilder.tokyo3Origin(
                        player.serverLevel()));
        source.sendSuccess(() -> Component.literal(status.summary()), false);
        return 1;
    }

    private static int ramielAbort(CommandSourceStack source)
            throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "ramiel abort"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        BattleResult result = Tokyo3RamielBattleDirector.abort(
                player.serverLevel(), IntegratedNervMapBuilder.tokyo3Origin(
                        player.serverLevel()));
        if (!result.accepted())
        {
            source.sendFailure(Component.literal(result.message()));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(result.message()), false);
        return 1;
    }

    private static int siegeStatus(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        AngelSiegeDirector.SiegeStatus status = AngelSiegeDirector.status(
                player.serverLevel(), player.blockPosition());
        source.sendSuccess(() -> Component.literal(status.summary()), false);
        return status.active() ? 1 : 0;
    }

    private static int siegeAbort(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        AngelSiegeDirector.OperationResult result = AngelSiegeDirector.abort(
                player.serverLevel(), player.blockPosition());
        if (!result.accepted())
        {
            source.sendFailure(Component.literal(result.message()));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(result.message()), false);
        return 1;
    }

    private static int overview(CommandSourceStack source) throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "overview"))
        {
            return 0;
        }
        ServerPlayer player = source.getPlayerOrException();
        BlockPos origin = findOrigin(player);
        player.stopRiding();
        teleportOverview(player, origin);
        source.sendSuccess(() -> Component.literal(
                "Tokyo-3 skyline observation deck."), false);
        return 1;
    }

    private static void teleportOverview(ServerPlayer player, BlockPos origin)
    {
        player.teleportTo(player.serverLevel(),
                origin.getX() + 0.5D,
                origin.getY() + ThirdTokyoSurfaceBuilder.OBSERVATION_Y + 1.0D,
                origin.getZ() + ThirdTokyoSurfaceBuilder.OBSERVATION_Z + 0.5D,
                180.0F, 18.0F);
    }

    private static BlockPos findOrigin(ServerPlayer player)
    {
        /*
         * The integrated dimension has one immutable Tokyo-3 datum.  Do not
         * derive it from a deployed EVA's launch bed when a tower is moving or
         * a visual audit is temporarily incomplete: that turned a surface bed
         * at Y=79 into a second, bogus city origin at Y=109.
         */
        if (player.serverLevel().dimension().equals(GeoFrontCommands.GEOFRONT))
        {
            return IntegratedNervMapBuilder.tokyo3Origin(
                    player.serverLevel());
        }
        AABB area = player.getBoundingBox().inflate(220.0D, 128.0D, 220.0D);
        EvaUnit01Entity centreUnit = player.serverLevel()
                .getEntitiesOfClass(EvaUnit01Entity.class, area,
                        unit -> unit.isAlive()
                                && unit.getUnitVariant() == EvaUnit01Entity.UNIT_01
                                && unit.findLaunchBed() != null).stream()
                .min((left, right) -> Double.compare(
                        left.distanceToSqr(player), right.distanceToSqr(player)))
                .orElse(null);
        if (centreUnit != null)
        {
            return centreUnit.findLaunchBed().above(30);
        }
        return Tokyo3RetractionSavedData.get(player.serverLevel())
                .nearest(player.blockPosition(), 320.0D)
                .map(Tokyo3RetractionSavedData.StoredDistrict::origin)
                .orElseThrow(() -> new IllegalStateException(
                        "No registered Tokyo-3 district within 320 blocks."));
    }

    private static TokyoAudit inspect(ServerLevel level, BlockPos origin, int depth,
                                      boolean requireParkedFormation)
    {
        DistrictAudit district = ThirdTokyoSurfaceBuilder.inspect(level, origin, depth);
        List<EvaUnit01Entity> units = level.getEntitiesOfClass(EvaUnit01Entity.class,
                new AABB(origin).inflate(80.0D, 64.0D, 80.0D),
                unit -> unit.isAlive() && unit.findLaunchBed() != null);
        boolean has00 = units.stream().anyMatch(
                unit -> unit.getUnitVariant() == EvaUnit01Entity.UNIT_00);
        boolean has01 = units.stream().anyMatch(
                unit -> unit.getUnitVariant() == EvaUnit01Entity.UNIT_01);
        boolean has02 = units.stream().anyMatch(
                unit -> unit.getUnitVariant() == EvaUnit01Entity.UNIT_02);
        boolean variants = has00 && has01 && has02;
        boolean parkedFormation = units.size() == 3 && variants;
        return new TokyoAudit(district.valid()
                        && (!requireParkedFormation || parkedFormation),
                district, units.size(), variants, parkedFormation,
                requireParkedFormation);
    }

    private static boolean rejectRetiredAliasInCleanWorld(
            CommandSourceStack source, String alias)
    {
        if (!FacilityWorldPolicy.isCleanRebuild(source.getServer()))
        {
            return false;
        }
        source.sendFailure(Component.literal(
                "/seele tokyo3 " + alias
                        + " belongs to the retired overlapping map pipeline "
                        + "and is disabled in SEELE_S19_CLEAN."));
        return true;
    }

    private static void logAudit(String stage, TokyoAudit result)
    {
        if (result.valid())
        {
            ProjectSeele.LOGGER.info("Tokyo-3 district audit [{}]: {}",
                    stage, result.summary());
        }
        else
        {
            ProjectSeele.LOGGER.error("TOKYO-3 DISTRICT INVALID [{}]: {}",
                    stage, result.summary());
        }
    }

    private record TokyoAudit(boolean valid, DistrictAudit district,
                              int units, boolean variants,
                              boolean parkedFormation,
                              boolean parkedFormationRequired)
    {
        String summary()
        {
            return String.format(Locale.ROOT,
                    "valid=%s sortie=%s units=%d variants00/01/02=%s "
                            + "parkedRequired=%s | %s",
                    this.valid, this.parkedFormation ? "PARKED" : "DEPLOYED_OR_AWAY",
                    this.units, this.variants, this.parkedFormationRequired,
                    this.district.summary());
        }
    }
}

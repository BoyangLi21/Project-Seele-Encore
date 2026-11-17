package com.projectseele.visual;

import java.util.List;
import java.util.Locale;

import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.mojang.brigadier.exceptions.SimpleCommandExceptionType;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.event.AngelSiegeDirector;
import com.projectseele.event.Tokyo3RamielBattleDirector;
import com.projectseele.event.Tokyo3RamielBattleDirector.BattleResult;
import com.projectseele.event.Tokyo3RamielBattleDirector.BattleStatus;
import com.projectseele.world.CityCreateDistrictR45;
import com.projectseele.world.ThirdTokyoSurfaceBuilder;
import com.projectseele.world.ThirdTokyoSurfaceBuilder.DistrictAudit;
import com.projectseele.world.IntegratedNervMapBuilder;
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
import net.minecraft.world.phys.AABB;

/** Builds and audits the connected NERV-to-Tokyo-3 sortie battlefield and moves the city. */
public final class ThirdTokyoCommands
{
    private ThirdTokyoCommands() {}

    /** Lower sinks the armour towers into the GeoFront (the old "retract"); raise returns them to street level. */
    public static LiteralArgumentBuilder<CommandSourceStack> cityCommand()
    {
        return Commands.literal("city")
                .then(Commands.literal("status").executes(c -> status(c.getSource())))
                .then(Commands.literal("raise").executes(c -> setRetraction(c.getSource(), false)))
                .then(Commands.literal("lower").executes(c -> setRetraction(c.getSource(), true)))
                .then(Commands.literal("recover").executes(c -> recover(c.getSource())));
    }

    public static LiteralArgumentBuilder<CommandSourceStack> devCityCommand()
    {
        return Commands.literal("city")
                .then(Commands.literal("setup")
                        .executes(context -> setup(context.getSource())))
                .then(Commands.literal("audit")
                        .executes(context -> audit(context.getSource())))
                .then(Commands.literal("lower_now")
                        .executes(context -> forceRetraction(
                                context.getSource(), true)))
                .then(Commands.literal("raise_now")
                        .executes(context -> forceRetraction(
                                context.getSource(), false)))
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
                        .executes(context -> overview(context.getSource())));
    }

    public static LiteralArgumentBuilder<CommandSourceStack> siegeCommand()
    {
        return Commands.literal("siege")
                .then(Commands.literal("status")
                        .executes(context -> siegeStatus(
                                context.getSource())))
                .then(Commands.literal("abort")
                        .executes(context -> siegeAbort(
                                context.getSource())));
    }

    static int setup(CommandSourceStack source) throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "/seele dev city setup"))
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
                        + "Run /seele dev geofront link, then board from the lower gantry."), false);
        return 1;
    }



    private static int audit(CommandSourceStack source) throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "/seele dev city audit"))
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


    private static int setRetraction(CommandSourceStack source, boolean retract)
            throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(
                source, retract ? "/seele city lower" : "/seele city raise"))
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

    /**
     * A lift that was cut off (a crash, a power cut) is held as a fault when the world is opened again, because the
     * buildings on disk and the ledger no longer agree. This takes the lift up again from the start of the step it
     * was in: the street openings are checked, the buildings are put back on their carriers and the move runs again.
     */
    private static int recover(CommandSourceStack source) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        BlockPos origin = findOrigin(player);
        RequestResult result = CityCreateDistrictR45.recover(player.serverLevel(), origin, false);
        String text = result.accepted() ? "已重新接管被中断的城市升降，从中断的那一步重做。"
                : result.message().startsWith("No held transaction fault") ? "城市升降没有故障，不需要恢复。"
                : "无法恢复：" + result.message();
        source.sendSuccess(() -> Component.literal(text), false);
        return result.accepted() ? 1 : 0;
    }

    private static int forceRetraction(CommandSourceStack source, boolean retract)
            throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(
                source, retract ? "/seele dev city lower_now" : "/seele dev city raise_now"))
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
        if (rejectRetiredAliasInCleanWorld(source, "/seele city status"))
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
        if (status.phase().contains("FAULT"))
        {
            source.sendSuccess(() -> Component.literal("升降被中断后停在故障状态：用 /seele city recover 从中断的那一步重做。"), false);
        }
        return 1;
    }

    private static int ramielStart(CommandSourceStack source)
            throws CommandSyntaxException
    {
        if (rejectRetiredAliasInCleanWorld(source, "/seele dev city ramiel start"))
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
        if (rejectRetiredAliasInCleanWorld(source, "/seele dev city ramiel status"))
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
        if (rejectRetiredAliasInCleanWorld(source, "/seele dev city ramiel abort"))
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
        if (rejectRetiredAliasInCleanWorld(source, "/seele dev city overview"))
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

    private static BlockPos findOrigin(ServerPlayer player) throws CommandSyntaxException
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
                .orElseThrow(() -> new SimpleCommandExceptionType(Component.literal(
                        "附近 320 格内没有已登记的第三新东京市街区，请到城区再试。")).create());
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
            CommandSourceStack source, String command)
    {
        if (!FacilityWorldPolicy.isCleanRebuild(source.getServer()))
        {
            return false;
        }
        source.sendFailure(Component.literal(
                command + " 属于已退役的重叠地图流程，在 SEELE_S19_CLEAN 存档中不可用。"));
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

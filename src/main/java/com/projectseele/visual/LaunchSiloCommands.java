package com.projectseele.visual;

import java.util.List;
import java.util.Locale;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.item.NervConstructionKitItem;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Deterministic setup and boarding helpers for the NERV launch-silo prototype. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class LaunchSiloCommands
{
    private LaunchSiloCommands() {}

    @SubscribeEvent
    public static void register(RegisterCommandsEvent event)
    {
        if(!DevelopmentCommandsR43.enabled())return;
        CommandDispatcher<CommandSourceStack> dispatcher = event.getDispatcher();
        dispatcher.register(Commands.literal("seele")
                .requires(source -> source.hasPermission(2))
                .then(Commands.literal("silo")
                        .then(Commands.literal("setup")
                                .executes(context -> setup(context.getSource())))
                        .then(Commands.literal("board")
                                .executes(context -> board(context.getSource())))
                        .then(Commands.literal("status")
                                .executes(context -> status(context.getSource())))
                        .then(Commands.literal("audit")
                                .executes(context -> audit(context.getSource())))));
    }

    static int setup(CommandSourceStack source) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel level = player.serverLevel();
        if (player.isPassenger())
        {
            source.sendFailure(Component.literal("Dismount before constructing a launch complex."));
            return 0;
        }
        int minSurface = level.getMinBuildHeight() + 52;
        // The 60-block frame and carrier require the shaft through origin+22.
        int maxSurface = level.getMaxBuildHeight() - 72;
        if (maxSurface < minSurface)
        {
            source.sendFailure(Component.literal("This dimension is too shallow for the launch complex."));
            return 0;
        }
        int surfaceY = Math.max(minSurface, Math.min(maxSurface, player.blockPosition().getY() - 1));
        BlockPos origin = new BlockPos(player.blockPosition().getX(), surfaceY, player.blockPosition().getZ());
        AABB buildArea = new AABB(origin).inflate(80.0D, 64.0D, 80.0D);
        boolean existingComplex = !level.getEntitiesOfClass(EvaUnit01Entity.class, buildArea,
                unit -> unit.isAlive() && unit.findLaunchBed() != null).isEmpty();
        if (existingComplex)
        {
            source.sendFailure(Component.literal(
                    "A launch complex already exists here; move at least 60 blocks before setup."));
            return 0;
        }
        NervConstructionKitItem.buildComplex(level, origin);
        SiloAudit setupAudit = inspectComplex(level, origin);
        logAudit("setup", setupAudit);
        if (!setupAudit.valid())
        {
            source.sendFailure(Component.literal(
                    "Launch complex was built but failed its structural audit: "
                            + setupAudit.summary()));
            return 0;
        }

        // Unit-01 is the centre bay. Leave the tester on its high dorsal
        // gantry, not at the launch bed forty-five blocks below ground.
        player.teleportTo(level, origin.getX() + 0.5D, origin.getY() + 4.0D,
                origin.getZ() + 14.5D, 180.0F, 16.0F);
        source.sendSuccess(() -> Component.literal(
                "NERV launch complex ready. Use /seele silo board to start insertion."), false);
        return 1;
    }

    /** Rebuilds one fixed complex so unattended screenshot runs are repeatable. */
    static int setupVisualCapture(CommandSourceStack source) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel level = player.serverLevel();
        player.stopRiding();
        int minSurface = level.getMinBuildHeight() + 52;
        int maxSurface = level.getMaxBuildHeight() - 72;
        int surfaceY = Math.max(minSurface, Math.min(maxSurface, 96));
        BlockPos origin = new BlockPos(0, surfaceY, 0);

        // Visual regression frames must expose the machinery, not inherit a
        // persisted world's midnight storm. This changes only the dedicated
        // unattended test world used by setupVisualCapture.
        level.setDayTime(6000L);
        level.setWeatherParameters(12000, 0, false, false);

        // The quick-play world persists between runs. Remove only old EVA
        // airframes in the fixed test envelope; buildComplex overwrites every
        // shaft/carrier block at the same origin without touching the rest of
        // the user's world.
        level.getEntitiesOfClass(EvaUnit01Entity.class,
                new AABB(origin).inflate(80.0D, 80.0D, 80.0D)).forEach(EvaUnit01Entity::discard);
        NervConstructionKitItem.buildComplex(level, origin);
        SiloAudit setupAudit = inspectComplex(level, origin);
        logAudit("visual-setup", setupAudit);
        if (!setupAudit.valid())
        {
            throw new IllegalStateException(
                    "Visual launch complex failed structural audit: " + setupAudit.summary());
        }
        player.teleportTo(level, origin.getX() + 0.5D, origin.getY() + 4.0D,
                origin.getZ() + 14.5D, 180.0F, 16.0F);
        source.sendSuccess(() -> Component.literal(
                "Repeatable NERV launch complex ready for visual capture."), false);
        return 1;
    }

    static int board(CommandSourceStack source) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        if (player.isPassenger())
        {
            source.sendFailure(Component.literal("Already riding an entity; dismount before silo boarding."));
            return 0;
        }
        EvaUnit01Entity unit = nearestCagedUnit(player);
        BlockPos bed = unit.findLaunchBed();
        if (bed == null)
        {
            throw new IllegalStateException("Nearest EVA is not on a NERV launch bed");
        }

        // The floor is bed+48 and the pilot stands at bed+49 beside the
        // Tiger synthetic plug pivot. The command bypasses only the aim cone;
        // physical rear/height/distance/line-of-sight gates still run.
        player.teleportTo(player.serverLevel(), bed.getX() + 0.5D,
                bed.getY() + 49.0D, bed.getZ() + 16.5D,
                180.0F, -8.0F);
        unit.tryEnterFromPlug(player, false);
        if (player.getVehicle() != unit)
        {
            source.sendFailure(Component.literal("Entry-plug boarding failed; check the gantry and launch bed."));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(
                "Entry plug inserted. Catapult launches after the synchronization sequence."), false);
        return 1;
    }

    private static int status(CommandSourceStack source) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        EvaUnit01Entity unit = player.getVehicle() instanceof EvaUnit01Entity ridden
                ? ridden : nearestCagedUnit(player);
        String phase = switch (unit.getLaunchPhase())
        {
            case EvaUnit01Entity.LAUNCH_LOCKED -> "LOCKED";
            case EvaUnit01Entity.LAUNCH_ASCENT -> "ASCENT";
            case EvaUnit01Entity.LAUNCH_CLEAR -> "SURFACE_CLEAR";
            default -> "IDLE";
        };
        BlockPos armedBed = unit.getLaunchBedPosition();
        BlockPos bed = armedBed != null ? armedBed : unit.findLaunchBed();
        String carrier = unit.getLaunchCarrierY() == Integer.MIN_VALUE
                ? "parked" : Integer.toString(unit.getLaunchCarrierY());
        source.sendSuccess(() -> Component.literal(String.format(Locale.ROOT,
                "Silo %s | ticks %d | y %.2f | carrier %s | bed %s", phase, unit.getLaunchTicks(),
                unit.getY(), carrier, bed == null ? "none" : bed.toShortString())), false);
        return 1;
    }

    /** Read-only structural check for the three launch beds and high gantries. */
    private static int audit(CommandSourceStack source) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        SiloAudit audit = inspectComplex(player.serverLevel(), player.blockPosition());
        logAudit("command", audit);
        Component report = Component.literal(audit.summary());
        if (audit.valid())
        {
            source.sendSuccess(() -> report, false);
            return 1;
        }
        source.sendFailure(report);
        return 0;
    }

    private static SiloAudit inspectComplex(ServerLevel level, BlockPos centre)
    {
        AABB area = new AABB(centre).inflate(80.0D, 64.0D, 80.0D);
        List<EvaUnit01Entity> units = level.getEntitiesOfClass(EvaUnit01Entity.class, area,
                unit -> unit.isAlive() && unit.findLaunchBed() != null);
        boolean has00 = false;
        boolean has01 = false;
        boolean has02 = false;
        int validBeds = 0;
        int validHighGantries = 0;
        int clearShafts = 0;
        for (EvaUnit01Entity unit : units)
        {
            BlockPos bed = unit.findLaunchBed();
            if (bed == null)
            {
                continue;
            }
            switch (unit.getUnitVariant())
            {
                case EvaUnit01Entity.UNIT_00 -> has00 = true;
                case EvaUnit01Entity.UNIT_02 -> has02 = true;
                default -> has01 = true;
            }
            if (level.getBlockState(bed).is(net.minecraft.world.level.block.Blocks.LODESTONE)
                    && Math.abs(unit.getY() - bed.getY() - 1.0D) < 0.25D)
            {
                validBeds++;
            }

            // Bed is origin-45. The catwalk floor is origin+3 (bed+48),
            // with the player standing at bed+49 and the lift spanning +5..49.
            boolean gantryFloor = !level.getBlockState(
                    bed.offset(0, 48, 16)).isAir();
            boolean ladderContinuous = true;
            BlockPos firstMissingLadder = null;
            for (int y = 5; y <= 49; y++)
            {
                if (!level.getBlockState(bed.offset(0, y, 30))
                        .is(net.minecraft.world.level.block.Blocks.LADDER))
                {
                    ladderContinuous = false;
                    firstMissingLadder = bed.offset(0, y, 30);
                    break;
                }
            }
            if (gantryFloor && ladderContinuous)
            {
                validHighGantries++;
            }
            else
            {
                ProjectSeele.LOGGER.error(
                        "NERV gantry invalid: variant={} bed={} floor={} firstMissingLadder={} state={}",
                        unit.getUnitVariant(), bed.toShortString(), gantryFloor,
                        firstMissingLadder == null ? "none" : firstMissingLadder.toShortString(),
                        firstMissingLadder == null ? "n/a"
                                : level.getBlockState(firstMissingLadder).toString());
            }

            boolean clear = true;
            // Audit the complete 29x29 moving carrier, not just the airframe,
            // for the full rise to the surface deck.
            for (int y = 1; y <= 64 && clear; y++)
            {
                for (int x = -14; x <= 14 && clear; x++)
                {
                    for (int z = -14; z <= 14; z++)
                    {
                        if (!level.getBlockState(bed.offset(x, y, z)).isAir())
                        {
                            clear = false;
                            break;
                        }
                    }
                }
            }
            if (clear)
            {
                clearShafts++;
            }
        }
        boolean variants = has00 && has01 && has02;
        boolean valid = units.size() == 3 && variants && validBeds == 3
                && validHighGantries == 3 && clearShafts == 3;
        return new SiloAudit(valid, units.size(), variants, validBeds,
                validHighGantries, clearShafts);
    }

    private static void logAudit(String stage, SiloAudit audit)
    {
        if (audit.valid())
        {
            ProjectSeele.LOGGER.info("NERV silo audit [{}]: {}", stage, audit.summary());
        }
        else
        {
            ProjectSeele.LOGGER.error("NERV SILO INVALID [{}]: {}", stage, audit.summary());
        }
    }

    private record SiloAudit(boolean valid, int units, boolean variants,
                             int beds, int highGantries, int clearShafts)
    {
        String summary()
        {
            return String.format(Locale.ROOT,
                    "valid=%s units=%d variants00/01/02=%s beds=%d highGantries=%d clearShafts=%d",
                    this.valid, this.units, this.variants, this.beds,
                    this.highGantries, this.clearShafts);
        }
    }

    static EvaUnit01Entity nearestCagedUnit(ServerPlayer player)
    {
        AABB area = player.getBoundingBox().inflate(160.0D, 96.0D, 160.0D);
        return player.serverLevel().getEntitiesOfClass(EvaUnit01Entity.class, area,
                        unit -> unit.isAlive() && unit.findLaunchBed() != null).stream()
                .min((left, right) -> Double.compare(left.distanceToSqr(player), right.distanceToSqr(player)))
                .orElseThrow(() -> new IllegalStateException("No EVA on a NERV launch bed within 160 blocks"));
    }
}

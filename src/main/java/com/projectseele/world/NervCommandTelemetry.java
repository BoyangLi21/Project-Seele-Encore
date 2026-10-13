package com.projectseele.world;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.Angel;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.RamielEntity;
import com.projectseele.entity.TrainingPilotEntity;
import com.projectseele.event.AngelSiegeDirector;
import com.projectseele.network.ServerboundEvaVideoFramePacket;
import com.projectseele.registry.ModBlocks;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Display;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.tags.BlockTags;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;

/** Live MAGI-style telemetry projected inside the NERV command room. */
public final class NervCommandTelemetry
{
    public static final int SCREEN_COUNT = 5;
    public static final int REFRESH_INTERVAL_TICKS = 40;
    private static final int SENSOR_WIDTH = 20;
    private static final int SENSOR_HEIGHT = 10;
    private static final double SENSOR_RANGE = 160.0D;
    private static final double SENSOR_TAN_HALF_FOV_X =
            Math.tan(Math.toRadians(35.0D));
    private static final double SENSOR_TAN_HALF_FOV_Y =
            Math.tan(Math.toRadians(23.0D));

    private static final ResourceKey<Level> GEOFRONT = ResourceKey.create(
            Registries.DIMENSION,
            new ResourceLocation(ProjectSeele.MODID, "geofront"));
    private static final String SCREEN_TAG_PREFIX =
            "projectseele.nerv_telemetry.";
    private static final String[] SCREEN_IDS = {
            "unit00", "unit01", "unit02", "strategic", "sensor"
    };
    private static final int[][] SCREEN_OFFSETS = {
            {-12, 0, 0}, {0, 0, 0}, {12, 0, 0},
            {-12, 12, 0}, {12, 12, 0}
    };
    private static final Map<UUID, String> LAST_TEXT = new HashMap<>();

    private NervCommandTelemetry() {}

    public static void tick(MinecraftServer server)
    {
        if (NervLegacyGenerationGuardR52.retired(server)) return;
        if (FacilityWorldPolicy.isS20Rebuild(server))
        {
            // S20 renders its live feeds directly on the two measured sloped
            // screen planes.  The legacy five TextDisplay wall lives almost
            // one hundred blocks behind those planes and must not be spawned
            // into the clean command master.
            return;
        }
        ServerLevel level = server.getLevel(GEOFRONT);
        if (level == null || level.players().isEmpty())
        {
            return;
        }
        BlockPos origin = IntegratedNervMapBuilder.GEOFRONT_ORIGIN;
        BlockPos anchor = screenAnchor(level, origin);
        if (!level.hasChunkAt(anchor) || !operationsPresent(level, origin))
        {
            return;
        }
        // No player can see these entities outside the command complex. Avoid
        // five display queries, global angel scans and text synchronization
        // merely because somebody is idling elsewhere in GeoFront.
        if (!ServerboundEvaVideoFramePacket.hasCommandViewers(level))
        {
            return;
        }
        // The physical console is repaired by map setup/runtime gates. Do not
        // rebuild its platform here: this method runs every 40 ticks and the
        // old call rewrote more than a thousand command-room blocks each pass,
        // reducing the integrated server to roughly two TPS and making the
        // EVA carrier state machine appear completely frozen.
        install(level, origin);
    }

    /** Creates missing screens and refreshes every value from live entities. */
    public static void install(ServerLevel level, BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        if (FacilityWorldPolicy.isS20Rebuild(level.getServer()))
        {
            return;
        }
        // Explicit installs (map setup and the operations shortcut) must work
        // even when the player starts in another dimension. The regular tick
        // path already checks hasChunkAt(), so it never keeps this chunk alive.
        level.getChunkAt(origin);
        BlockPos anchor = screenAnchor(level, origin);
        level.getChunkAt(anchor);

        List<EvaUnit01Entity> units = evaUnits(level, origin);
        Component[] text = {
                unitPanel(level, findVariant(level, units, EvaUnit01Entity.UNIT_00),
                        EvaUnit01Entity.UNIT_00),
                unitPanel(level, findVariant(level, units, EvaUnit01Entity.UNIT_01),
                        EvaUnit01Entity.UNIT_01),
                unitPanel(level, findVariant(level, units, EvaUnit01Entity.UNIT_02),
                        EvaUnit01Entity.UNIT_02),
                strategicPanel(level, units, origin),
                sensorPanel(level, units)
        };

        int created = 0;
        for (int index = 0; index < SCREEN_COUNT; index++)
        {
            String screenTag = SCREEN_TAG_PREFIX + SCREEN_IDS[index];
            List<Display.TextDisplay> matches = displays(level, origin,
                    screenTag);
            Display.TextDisplay display;
            boolean pendingAdd = false;
            if (matches.isEmpty())
            {
                display = EntityType.TEXT_DISPLAY.create(level);
                if (display == null)
                {
                    continue;
                }
                display.addTag(screenTag);
                display.setNoGravity(true);
                display.setInvulnerable(true);
                display.setSilent(true);
                pendingAdd = true;
                created++;
            }
            else
            {
                display = matches.get(0);
                for (int duplicate = 1; duplicate < matches.size(); duplicate++)
                {
                    LAST_TEXT.remove(matches.get(duplicate).getUUID());
                    matches.get(duplicate).discard();
                }
            }

            int[] offset = SCREEN_OFFSETS[index];
            Vec3 position = Vec3.atCenterOf(anchor.offset(
                    offset[0], offset[1], offset[2]));
            updateDisplay(display, position, text[index]);
            if (pendingAdd)
            {
                level.addFreshEntity(display);
            }
        }
        if (created > 0)
        {
            ProjectSeele.LOGGER.info(
                    "NERV command telemetry installed: created={} screens={}/{} anchor={}",
                    created, countScreens(level, origin), SCREEN_COUNT,
                    anchor.toShortString());
        }
    }

    public static int countScreens(ServerLevel level, BlockPos origin)
    {
        level.getChunkAt(origin);
        level.getChunkAt(screenAnchor(level, origin));
        int count = 0;
        for (String id : SCREEN_IDS)
        {
            if (!displays(level, origin, SCREEN_TAG_PREFIX + id).isEmpty())
            {
                count++;
            }
        }
        return count;
    }

    public static void reset()
    {
        LAST_TEXT.clear();
    }

    private static boolean operationsPresent(ServerLevel level,
                                             BlockPos origin)
    {
        return LocalMapAssetLoader.commandMarkersPresent(level, origin)
                || level.getBlockState(origin.offset(0, 8, 0))
                .is(Blocks.BEACON);
    }

    private static BlockPos screenAnchor(ServerLevel level, BlockPos origin)
    {
        // The downloaded command module's open bridge is 58 blocks north of
        // the integration origin. The clean-room fallback uses its own
        // tactical wall at z=-20.
        return LocalMapAssetLoader.commandMarkersPresent(level, origin)
                ? origin.offset(0, 17, 58)
                : origin.offset(0, 7, NervOperationsCentreBuilder.DISPLAY_Z + 1);
    }

    private static List<Display.TextDisplay> displays(ServerLevel level,
                                                       BlockPos origin,
                                                       String tag)
    {
        AABB bounds = AABB.ofSize(Vec3.atCenterOf(origin.offset(0, 18, 20)),
                256.0D, 160.0D, 256.0D);
        List<Display.TextDisplay> result = new ArrayList<>(
                level.getEntitiesOfClass(Display.TextDisplay.class, bounds,
                        display -> display.getTags().contains(tag)));
        result.sort(Comparator.comparingInt(Entity::getId));
        return result;
    }

    private static List<EvaUnit01Entity> evaUnits(ServerLevel level,
                                                   BlockPos origin)
    {
        AABB bounds = new AABB(origin.getX() - 300.0D,
                level.getMinBuildHeight(), origin.getZ() - 300.0D,
                origin.getX() + 300.0D, level.getMaxBuildHeight(),
                origin.getZ() + 300.0D);
        return new ArrayList<>(level.getEntitiesOfClass(
                EvaUnit01Entity.class, bounds, Entity::isAlive));
    }

    private static EvaUnit01Entity findVariant(ServerLevel level,
                                                List<EvaUnit01Entity> units,
                                                int variant)
    {
        BlockPos station = IntegratedNervMapBuilder.lowerLiftBed(level, variant);
        Vec3 stationCentre = Vec3.atCenterOf(station);
        return units.stream()
                .filter(unit -> unit.getUnitVariant() == variant)
                .min(Comparator.comparingDouble(unit ->
                        unit.position().distanceToSqr(stationCentre)))
                .orElse(null);
    }

    private static Component unitPanel(ServerLevel level, EvaUnit01Entity unit,
                                       int variant)
    {
        String label = String.format(Locale.ROOT, "EVA-%02d", variant);
        MutableComponent result = Component.literal(label + " / "
                        + switch (variant)
                        {
                            case EvaUnit01Entity.UNIT_00 -> "PROTOTYPE";
                            case EvaUnit01Entity.UNIT_02 -> "PRODUCTION";
                            default -> "TEST TYPE";
                        })
                .withStyle(variant == EvaUnit01Entity.UNIT_00
                        ? ChatFormatting.GOLD
                        : variant == EvaUnit01Entity.UNIT_02
                                ? ChatFormatting.RED : ChatFormatting.LIGHT_PURPLE);
        if (unit == null)
        {
            return result.append(Component.literal("\nLINK OFFLINE\nNO AIRFRAME DATA")
                    .withStyle(ChatFormatting.DARK_RED));
        }

        float health = unit.getHealth();
        float at = unit.getAtFieldEnergy();
        float atMax = Math.max(1.0F, unit.getAtFieldCapacity());
        result.append(Component.literal(String.format(Locale.ROOT,
                        "\nSYNC %05.1f%%   HP %03.0f/%03.0f",
                        unit.getSynchronizationRatio(0.0F), health,
                        unit.getMaxHealth()))
                .withStyle(ChatFormatting.AQUA));
        boolean videoLive = ServerboundEvaVideoFramePacket.isFeedActive(
                level, variant);
        result.append(Component.literal(videoLive
                        ? unit.isTrainingPilotActive()
                                ? "\nCOCKPIT VIDEO: TRAINING LIVE"
                                : "\nCOCKPIT VIDEO: LIVE"
                        : "\nCOCKPIT VIDEO: STANDBY")
                .withStyle(videoLive ? ChatFormatting.GREEN
                        : ChatFormatting.DARK_GRAY));
        result.append(Component.literal(String.format(Locale.ROOT,
                        "\nA.T. %03.0f/%03.0f  %s", at, atMax,
                        unit.isAtFieldOn() ? "DEPLOYED" : "STANDBY"))
                .withStyle(unit.isAtFieldOn()
                        ? ChatFormatting.GREEN : ChatFormatting.GRAY));
        result.append(Component.literal("\n" + weaponName(unit.getWeapon())
                        + " / " + stanceName(unit))
                .withStyle(ChatFormatting.WHITE));
        if (unit.isBerserk())
        {
            result.append(Component.literal(String.format(Locale.ROOT,
                            "\nBERSERK / AUTONOMOUS  %03ds",
                            Math.max(0, unit.getBerserkTicks() / 20)))
                    .withStyle(ChatFormatting.RED, ChatFormatting.BOLD));
        }
        else if (unit.getBerserkRecoveryTicks() > 0)
        {
            result.append(Component.literal(String.format(Locale.ROOT,
                            "\nFORCED SHUTDOWN  %03ds",
                            Math.max(0, unit.getBerserkRecoveryTicks() / 20)))
                    .withStyle(ChatFormatting.GOLD));
        }
        result.append(Component.literal("\n" + launchReadout(level, unit, variant))
                .withStyle(unit.getLaunchPhase() == EvaUnit01Entity.LAUNCH_ASCENT
                        ? ChatFormatting.YELLOW : ChatFormatting.GRAY));
        return result;
    }

    private static Component strategicPanel(ServerLevel level,
                                             List<EvaUnit01Entity> units,
                                             BlockPos origin)
    {
        List<Entity> angels = new ArrayList<>();
        RamielEntity ramiel = null;
        PerformanceCounters.recordGlobalEntityScan();
        for (Entity entity : level.getAllEntities())
        {
            if (entity.isAlive() && entity instanceof Angel)
            {
                angels.add(entity);
                if (ramiel == null && entity instanceof RamielEntity found)
                {
                    ramiel = found;
                }
            }
        }

        MutableComponent result = Component.literal(
                "NERV / MAGI LIVE TACTICAL NETWORK")
                .withStyle(ChatFormatting.GOLD);
        if (ramiel != null)
        {
            result.append(Component.literal(String.format(Locale.ROOT,
                            "\nANGEL: RAMIEL  HP %.0f/%.0f  A.T. %.0f/%.0f  CORE %s",
                            ramiel.getHealth(), ramiel.getMaxHealth(),
                            ramiel.getAtFieldEnergy(), ramiel.getAtFieldMax(),
                            ramiel.isExposed() ? "EXPOSED" : "SEALED"))
                    .withStyle(ramiel.isExposed()
                            ? ChatFormatting.YELLOW : ChatFormatting.RED));
        }
        else
        {
            result.append(Component.literal("\nANGEL MONITOR: "
                            + (angels.isEmpty() ? "CLEAR" : angels.size() + " ACTIVE"))
                    .withStyle(angels.isEmpty()
                            ? ChatFormatting.GREEN : ChatFormatting.RED));
        }

        AngelSiegeDirector.SiegeStatus siege = AngelSiegeDirector.status(
                level, IntegratedNervMapBuilder.tokyo3Origin(level));
        if (siege.active())
        {
            result.append(Component.literal(String.format(Locale.ROOT,
                            "\nNERV BEACON: WAVE %d/3  INTEGRITY %04d/%04d  HOSTILES %d",
                            siege.wave(), siege.integrity(),
                            siege.maximumIntegrity(), siege.aliveAngels()))
                    .withStyle(siege.integrity() * 4 < siege.maximumIntegrity()
                            ? ChatFormatting.RED : ChatFormatting.YELLOW));
        }
        EvaUnit01Entity feed = units.stream()
                .filter(unit -> activePilot(unit) != null)
                .findFirst().orElse(findVariant(level, units,
                        EvaUnit01Entity.UNIT_01));
        LivingEntity pilot = activePilot(feed);
        if (feed != null && pilot != null)
        {
            result.append(Component.literal(String.format(Locale.ROOT,
                            "\nPILOT SENSOR FEED EVA-%02d  HDG %03d  PITCH %+03d",
                            feed.getUnitVariant(), heading(pilot.getYRot()),
                            Math.round(pilot.getXRot())))
                    .withStyle(ChatFormatting.AQUA));
            result.append(Component.literal(String.format(Locale.ROOT,
                            "\nPOSITION X%+.0f Y%.0f Z%+.0f  %s",
                            feed.getX() - origin.getX(), feed.getY(),
                            feed.getZ() - origin.getZ(), stanceName(feed)))
                    .withStyle(ChatFormatting.WHITE));
            result.append(Component.literal(String.format(Locale.ROOT,
                            "\nPOWER %s  %04d/%04d",
                            feed.isUmbilicalConnected() ? "UMBILICAL" : "INTERNAL",
                            feed.getPowerTicks(), feed.getPowerCapacityTicks()))
                    .withStyle(feed.isPowerDepleted()
                            ? ChatFormatting.RED : feed.isUmbilicalConnected()
                                ? ChatFormatting.GREEN : ChatFormatting.GOLD));
        }
        else
        {
            result.append(Component.literal(
                            "\nPILOT SENSOR FEED: NO ACTIVE ENTRY PLUG LINK")
                    .withStyle(ChatFormatting.DARK_GRAY));
        }
        result.append(Component.literal("\nGEOFRONT > TOKYO-3 PHYSICAL ROUTE: "
                        + IntegratedNervMapBuilder.ascentDistance()
                        + " BLOCKS / CONNECTED")
                .withStyle(ChatFormatting.GREEN));
        Tokyo3RetractionDirector.Status city =
                Tokyo3RetractionDirector.status(level,
                        IntegratedNervMapBuilder.tokyo3Origin(level));
        result.append(Component.literal(String.format(Locale.ROOT,
                        "\nCITY ARMOUR: %s %02d/%02d",
                        city.phase(), city.depth(), city.maximumDepth()))
                .withStyle(city.targetDepth() > 0
                        ? ChatFormatting.YELLOW : ChatFormatting.AQUA));
        result.append(Component.literal("\n"
                        + NervOperationsConsole.statusLine(level))
                .withStyle(ChatFormatting.GOLD));
        NervCrewSavedData.CrewOverview crew = NervCrewSavedData
                .get(level.getServer()).overview(level.getServer());
        result.append(Component.literal(String.format(Locale.ROOT,
                        "\nCREW %d/6  ONLINE %d  READY %d/%d",
                        crew.assigned(), crew.online(), crew.onlineReady(),
                        crew.assigned()))
                .withStyle(crew.allAssignedOnlineReady()
                        ? ChatFormatting.GREEN : ChatFormatting.YELLOW));
        return result;
    }

    /**
     * Low-resolution optical feed sampled from the actual mounted player's
     * eye, yaw and pitch.  This avoids a recursive client world render while
     * still making the command-room image respond to what the pilot sees.
     */
    private static Component sensorPanel(ServerLevel level,
                                         List<EvaUnit01Entity> units)
    {
        EvaUnit01Entity feed = units.stream()
                .filter(unit -> activePilot(unit) != null)
                .findFirst().orElse(null);
        MutableComponent result = Component.literal(
                "ENTRY PLUG / LIVE OPTICAL SENSOR")
                .withStyle(ChatFormatting.GOLD);
        LivingEntity pilot = activePilot(feed);
        if (feed == null || pilot == null)
        {
            result.append(Component.literal(
                            "\nNO ACTIVE PILOT LINK\n\n"
                                    + "....................\n".repeat(8)
                                    + "....................")
                    .withStyle(ChatFormatting.DARK_GRAY));
            return result;
        }

        result.append(Component.literal(String.format(Locale.ROOT,
                        "\nEVA-%02d  %s  HDG %03d  PITCH %+03d",
                        feed.getUnitVariant(),
                        pilot instanceof TrainingPilotEntity ? "DUMMY" : "PILOT",
                        heading(pilot.getYRot()), Math.round(pilot.getXRot())))
                .withStyle(ChatFormatting.AQUA));

        Vec3 eye = pilot.getEyePosition();
        Vec3 forward = Vec3.directionFromRotation(
                pilot.getXRot(), pilot.getYRot()).normalize();
        Vec3 right = forward.cross(new Vec3(0.0D, 1.0D, 0.0D));
        if (right.lengthSqr() < 1.0E-6D)
        {
            right = new Vec3(1.0D, 0.0D, 0.0D);
        }
        else
        {
            right = right.normalize();
        }
        Vec3 up = right.cross(forward).normalize();

        char[][] pixels = new char[SENSOR_HEIGHT][SENSOR_WIDTH];
        ChatFormatting[][] colours =
                new ChatFormatting[SENSOR_HEIGHT][SENSOR_WIDTH];
        for (int row = 0; row < SENSOR_HEIGHT; row++)
        {
            double vertical = (1.0D - (row + 0.5D)
                    / SENSOR_HEIGHT * 2.0D) * SENSOR_TAN_HALF_FOV_Y;
            for (int column = 0; column < SENSOR_WIDTH; column++)
            {
                double horizontal = ((column + 0.5D)
                        / SENSOR_WIDTH * 2.0D - 1.0D)
                        * SENSOR_TAN_HALF_FOV_X;
                Vec3 direction = forward
                        .add(right.scale(horizontal))
                        .add(up.scale(vertical)).normalize();
                BlockHitResult hit = level.clip(new ClipContext(
                        eye, eye.add(direction.scale(SENSOR_RANGE)),
                        ClipContext.Block.COLLIDER,
                        ClipContext.Fluid.ANY, pilot));
                pixels[row][column] = '█';
                if (hit.getType() == HitResult.Type.MISS)
                {
                    colours[row][column] = ChatFormatting.DARK_BLUE;
                }
                else
                {
                    BlockState state = level.getBlockState(hit.getBlockPos());
                    colours[row][column] = sensorColour(state,
                            eye.distanceTo(hit.getLocation()));
                }
            }
        }

        int centreRow = SENSOR_HEIGHT / 2;
        int centreColumn = SENSOR_WIDTH / 2;
        pixels[centreRow][centreColumn] = '+';
        colours[centreRow][centreColumn] = ChatFormatting.YELLOW;
        markNearestAngel(level, pilot, eye, forward, right, up,
                pixels, colours);

        for (int row = 0; row < SENSOR_HEIGHT; row++)
        {
            result.append(Component.literal("\n"));
            int start = 0;
            while (start < SENSOR_WIDTH)
            {
                ChatFormatting colour = colours[row][start];
                int end = start + 1;
                while (end < SENSOR_WIDTH
                        && colours[row][end] == colour)
                {
                    end++;
                }
                result.append(Component.literal(
                                new String(pixels[row], start, end - start))
                        .withStyle(colour));
                start = end;
            }
        }
        return result;
    }

    private static void markNearestAngel(ServerLevel level,
                                         LivingEntity pilot,
                                         Vec3 eye, Vec3 forward,
                                         Vec3 right, Vec3 up,
                                         char[][] pixels,
                                         ChatFormatting[][] colours)
    {
        Entity nearest = null;
        double nearestDistance = Double.MAX_VALUE;
        PerformanceCounters.recordGlobalEntityScan();
        for (Entity entity : level.getAllEntities())
        {
            if (!(entity instanceof Angel) || !entity.isAlive())
            {
                continue;
            }
            double distance = entity.distanceToSqr(pilot);
            if (distance < nearestDistance)
            {
                nearestDistance = distance;
                nearest = entity;
            }
        }
        if (nearest == null)
        {
            return;
        }
        Vec3 toTarget = nearest.getBoundingBox().getCenter()
                .subtract(eye);
        double depth = toTarget.dot(forward);
        if (depth <= 0.1D)
        {
            return;
        }
        double normalizedX = toTarget.dot(right)
                / (depth * SENSOR_TAN_HALF_FOV_X);
        double normalizedY = toTarget.dot(up)
                / (depth * SENSOR_TAN_HALF_FOV_Y);
        if (Math.abs(normalizedX) > 1.0D
                || Math.abs(normalizedY) > 1.0D)
        {
            return;
        }
        int column = Mth.clamp(Mth.floor((normalizedX + 1.0D)
                * 0.5D * SENSOR_WIDTH), 0, SENSOR_WIDTH - 1);
        int row = Mth.clamp(Mth.floor((1.0D - normalizedY)
                * 0.5D * SENSOR_HEIGHT), 0, SENSOR_HEIGHT - 1);
        pixels[row][column] = 'X';
        colours[row][column] = ChatFormatting.RED;
    }

    private static LivingEntity activePilot(EvaUnit01Entity unit)
    {
        if (unit == null)
        {
            return null;
        }
        LivingEntity pilot = EvaPilotResolver.pilot(unit);
        return pilot instanceof ServerPlayer
                || pilot instanceof TrainingPilotEntity ? pilot : null;
    }

    private static ChatFormatting sensorColour(BlockState state,
                                                double distance)
    {
        if (state.is(ModBlocks.LCL_BLOCK.get()))
        {
            return ChatFormatting.GOLD;
        }
        if (state.getFluidState().is(FluidTags.WATER))
        {
            return ChatFormatting.BLUE;
        }
        if (state.is(BlockTags.LEAVES)
                || state.is(Blocks.GRASS_BLOCK)
                || state.is(Blocks.MOSS_BLOCK))
        {
            return ChatFormatting.GREEN;
        }
        if (state.is(Blocks.SNOW)
                || state.is(Blocks.SNOW_BLOCK)
                || state.is(Blocks.QUARTZ_BLOCK))
        {
            return ChatFormatting.WHITE;
        }
        if (state.is(Blocks.GLASS)
                || state.is(Blocks.GRAY_STAINED_GLASS)
                || state.is(Blocks.ORANGE_STAINED_GLASS))
        {
            return ChatFormatting.AQUA;
        }
        if (state.is(Blocks.LAVA)
                || state.is(Blocks.FIRE)
                || state.is(Blocks.REDSTONE_BLOCK))
        {
            return ChatFormatting.RED;
        }
        if (distance < 30.0D)
        {
            return ChatFormatting.WHITE;
        }
        if (distance < 80.0D)
        {
            return ChatFormatting.GRAY;
        }
        return ChatFormatting.DARK_GRAY;
    }

    private static String launchReadout(ServerLevel level,
                                        EvaUnit01Entity unit, int variant)
    {
        BlockPos lower = IntegratedNervMapBuilder.lowerLiftBed(level, variant);
        BlockPos upper = IntegratedNervMapBuilder.surfaceLiftBed(level, variant);
        int progress = Mth.clamp(Math.round((float) ((unit.getY()
                - (lower.getY() + 1.0D))
                / Math.max(1.0D, upper.getY() - lower.getY())) * 100.0F), 0, 100);
        return switch (unit.getLaunchPhase())
        {
            case EvaUnit01Entity.LAUNCH_LOCKED ->
                    "SILO LOCKED / ENTRY PLUG SYNCHRONIZING";
            case EvaUnit01Entity.LAUNCH_ASCENT ->
                    String.format(Locale.ROOT, "MAGLEV ASCENT %03d%% / Y %.1f",
                            progress, unit.getY());
            case EvaUnit01Entity.LAUNCH_CLEAR ->
                    "SURFACE CLEAR / CONTROL TRANSFER";
            default -> unit.getY() >= upper.getY()
                    ? "TOKYO-3 SURFACE / READY"
                    : "GEOFRONT BAY / STANDBY";
        };
    }

    private static String weaponName(int weapon)
    {
        return switch (weapon)
        {
            case EvaUnit01Entity.WEAPON_KNIFE -> "PROGRESSIVE KNIFE";
            case EvaUnit01Entity.WEAPON_CANNON -> "POSITRON CANNON";
            case EvaUnit01Entity.WEAPON_LANCE -> "LANCE OF LONGINUS";
            case EvaUnit01Entity.WEAPON_RIFLE -> "PALLET RIFLE";
            case EvaUnit01Entity.WEAPON_N2 -> "N2 SELF-DESTRUCT";
            default -> "BARE HANDS";
        };
    }

    private static String stanceName(EvaUnit01Entity unit)
    {
        if (unit.isPilotProne())
        {
            return "PRONE";
        }
        if (unit.isPilotCrouching())
        {
            return unit.isShieldBraced() ? "SHIELD BRACE" : "KNEEL";
        }
        if (unit.isPilotSprinting())
        {
            return "SPRINT";
        }
        return "UPRIGHT";
    }

    private static int heading(float yaw)
    {
        return Math.floorMod(Math.round(yaw), 360);
    }

    private static void updateDisplay(Display.TextDisplay display,
                                      Vec3 position, Component component)
    {
        String json = Component.Serializer.toJson(component);
        if (!json.equals(LAST_TEXT.get(display.getUUID())))
        {
            CompoundTag tag = display.saveWithoutId(new CompoundTag());
            tag.putString("text", json);
            tag.putInt("line_width", 260);
            tag.putInt("background", 0xB0101418);
            tag.putByte("text_opacity", (byte) -1);
            tag.putBoolean("shadow", true);
            // The imported command module may leave a glass or trim voxel in
            // front of a display plane. Keep the live glyph layer readable
            // through that physical panel while the black backing remains a
            // real part of the room.
            tag.putBoolean("see_through", true);
            tag.putBoolean("default_background", false);
            tag.putString("alignment", "left");
            // The imported bridge is normally viewed from +Z, but crew can
            // approach the upper diagnostic wings from either aisle. A centre
            // billboard also migrates legacy fixed panels whose saved
            // 180-degree yaw exposed only the black backing surface.
            tag.putString("billboard", "center");
            tag.putFloat("view_range", 4.0F);
            tag.putFloat("width", 9.0F);
            tag.putFloat("height", 5.5F);
            tag.putInt("glow_color_override", 0xFFFF8000);
            CompoundTag brightness = new CompoundTag();
            brightness.putInt("block", 15);
            brightness.putInt("sky", 15);
            tag.put("brightness", brightness);
            display.load(tag);
            LAST_TEXT.put(display.getUUID(), json);
        }
        if (display.position().distanceToSqr(position) > 1.0E-6D)
        {
            display.setPos(position.x, position.y, position.z);
        }
        if (Math.abs(Mth.wrapDegrees(display.getYRot())) > 0.01F)
        {
            display.setYRot(0.0F);
        }
        if (Math.abs(display.getXRot()) > 0.01F)
        {
            display.setXRot(0.0F);
        }
    }
}

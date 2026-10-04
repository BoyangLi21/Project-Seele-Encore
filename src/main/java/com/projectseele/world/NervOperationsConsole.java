package com.projectseele.world;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.NervArmamentStationEntity;
import com.projectseele.event.Tokyo3RamielBattleDirector;
import com.projectseele.event.Tokyo3RamielBattleDirector.BattleResult;
import com.projectseele.visual.GeoFrontCommands;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Display;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.block.StairBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.AttachFace;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/**
 * Seven physical controls inside the imported NERV command module.
 *
 * <p>The console never bypasses the entry-plug passenger or launch-bed
 * interlocks.  A commander may release a synchronized occupied airframe, but
 * cannot launch an empty or unlinked EVA.</p>
 */
public final class NervOperationsConsole
{
    private static final ThreadLocal<Boolean> STAFF_REPORT=ThreadLocal.withInitial(()->false);
    public static boolean handleStaffUse(ServerPlayer player,BlockPos position)
    {
        boolean previous=STAFF_REPORT.get();STAFF_REPORT.set(true);
        try{return handleUse(player,position);}finally{STAFF_REPORT.set(previous);}
    }
    public static final int CONTROL_COUNT = 7;
    public static final int S20_CONTROL_COUNT = 21;

    /**
     * Exact controls physically authored by the human on the S20 glass dais.
     * The map positions, coloured unit glass and button types are authority;
     * no runtime installer is allowed to move or replace these blocks.
     */
    private static final BlockPos[] S20_CONTROLS = {
            new BlockPos(28, -405, 277), // city rise
            new BlockPos(29, -405, 277), // city lower
            new BlockPos(28, -407, 288), // EVA-00 screen
            new BlockPos(29, -407, 288), // EVA-01 screen
            new BlockPos(30, -407, 288), // EVA-02 screen
            new BlockPos(31, -407, 288), // lower tactical screen
            new BlockPos(31, -406, 286), // EVA-02 prepare, red
            new BlockPos(30, -406, 286), // EVA-01 prepare, purple
            new BlockPos(29, -406, 286), // EVA-00 prepare, yellow
            new BlockPos(31, -407, 286), // EVA-02 launch, red
            new BlockPos(30, -407, 286), // EVA-01 launch, purple
            new BlockPos(29, -407, 286), // EVA-00 launch, yellow
            new BlockPos(28, -407, 286), // EVA-02 recover, red
            new BlockPos(27, -407, 286), // EVA-01 recover, purple
            new BlockPos(26, -407, 286)  // EVA-00 recover, yellow
    };
    /**
     * Current physical controls on the human-authored glass command dais.
     *
     * <p>The dais was rebuilt by hand after the original coordinate contract
     * above was recorded.  The blocks themselves are now the authority: two
     * city keys, four display keys and three three-key EVA banks.  Keep the
     * former coordinates as compatibility aliases, but bind these real
     * buttons without moving or regenerating a single map block.</p>
     */
    private static final BlockPos[] S20_AUTHORED_CONTROLS = {
            new BlockPos(26, -405, 277), // city rise, warped
            new BlockPos(30, -405, 277), // city lower, crimson
            /*
             * The display keys moved one course down and one block in, to the
             * row the operator can reach from the chair at (28,-409,288).  The
             * user rebuilt the same five button types in the same x order, so
             * the mapping carries over unchanged; the old row at y=-408 z=290
             * is still physically there but is no longer bound to anything.
             */
            new BlockPos(30, -409, 289), // EVA-00 screen, oak
            new BlockPos(29, -409, 289), // EVA-01 screen, warped
            new BlockPos(27, -409, 289), // EVA-02 screen, crimson
            new BlockPos(26, -409, 289), // lower tactical screen, bamboo
            new BlockPos(32, -408, 285), // EVA-02 prepare
            new BlockPos(32, -408, 286), // EVA-01 prepare
            new BlockPos(32, -408, 287), // EVA-00 prepare
            new BlockPos(32, -407, 285), // EVA-02 launch
            new BlockPos(32, -407, 286), // EVA-01 launch
            new BlockPos(32, -407, 287), // EVA-00 launch
            new BlockPos(24, -408, 285), // EVA-02 recover
            new BlockPos(24, -408, 286), // EVA-01 recover
            new BlockPos(24, -408, 287)  // EVA-00 recover
    };
    /**
     * Human-authored cancel-sortie row. It is ordered EVA-02, EVA-01,
     * EVA-00 along +Z, matching the adjacent prepare/launch banks.
     * These are aliases only; runtime must never replace the map blocks.
     */
    private static final BlockPos[] S20_CANCEL_CONTROLS = {
            new BlockPos(24, -407, 285), // EVA-02 cancel launch
            new BlockPos(24, -407, 286), // EVA-01 cancel launch
            new BlockPos(24, -407, 287)  // EVA-00 cancel launch
    };
    /**
     * Human-added fifth display key, a stone button dropped in the middle of
     * the four screen keys.  It is kept out of the two parallel control arrays
     * on purpose: actions 6..14 are positional, so appending a sixteenth entry
     * there would renumber the whole EVA bank.
     */
    private static final BlockPos S20_CITY_SCREEN_CONTROL =
            new BlockPos(28, -409, 289);
    private static final BlockPos S20_ARMAMENT_DEPLOY_CONTROL =
            new BlockPos(30, -408, 290);
    private static final BlockPos S20_ARMAMENT_RECALL_CONTROL =
            new BlockPos(26, -408, 290);
    private static final int S20_CITY_SCREEN_ACTION = 15;
    private static final int S20_CANCEL_UNIT02_ACTION = 16;
    private static final int S20_CANCEL_UNIT01_ACTION = 17;
    private static final int S20_CANCEL_UNIT00_ACTION = 18;
    private static final int S20_ARMAMENT_DEPLOY_ACTION = 19;
    private static final int S20_ARMAMENT_RECALL_ACTION = 20;
    private static final String[] S20_IDS = {
            "city_rise", "city_lower",
            "screen_unit00", "screen_unit01", "screen_unit02",
            "screen_tactical",
            "unit02_prepare", "unit01_prepare", "unit00_prepare",
            "unit02_launch", "unit01_launch", "unit00_launch",
            "unit02_recover", "unit01_recover", "unit00_recover"
    };

    private static final int UPDATE_CLIENTS = Block.UPDATE_CLIENTS;
    private static final int CONTROL_Y = 15;
    // The imported screen plane is z=58 and the main gallery approaches from
    // positive Z.  Put the operator row in front of that plane, not behind it.
    private static final int CONTROL_Z = 64;
    private static final int LEGACY_CONTROL_Z = 52;
    private static final int FIRST_CONTROL_X = -12;
    private static final int CONTROL_SPACING = 4;
    /*
     * Seven real polished-blackstone switches already present on the three
     * operator desks in nerv_command_left.nbt.  Keeping the semantic controls
     * on these authored consoles avoids the floating coloured test plinth
     * that the first Facility-v2 adapter produced.
     */
    private static final int[][] IMPORTED_V2_CONTROL_LOCAL = {
            {25, 43, 64}, // sortie preparation
            {15, 43, 68}, // Unit-00 launch
            {25, 43, 68}, // Unit-01 launch
            {37, 43, 68}, // Unit-02 launch
            {27, 43, 64}, // facility navigation / status
            {22, 43, 71}, // battle start
            {30, 43, 71}  // battle abort
    };
    private static final String LABEL_TAG_PREFIX =
            "projectseele.nerv_control.";
    private static final String[] IDS = {
            "system", "unit00", "unit01", "unit02",
            "armour", "yashima", "abort"
    };
    private static final String[] LABELS = {
            "MAGI\nCHECK", "EVA-00\nRELEASE", "EVA-01\nRELEASE",
            "EVA-02\nRELEASE", "CITY\nARMOUR", "YASHIMA\nSTART",
            "BATTLE\nABORT"
    };
    private static final BlockState[] BASES = {
            Blocks.CYAN_CONCRETE.defaultBlockState(),
            Blocks.ORANGE_CONCRETE.defaultBlockState(),
            Blocks.PURPLE_CONCRETE.defaultBlockState(),
            Blocks.RED_CONCRETE.defaultBlockState(),
            Blocks.YELLOW_CONCRETE.defaultBlockState(),
            Blocks.LIME_CONCRETE.defaultBlockState(),
            Blocks.BLACK_CONCRETE.defaultBlockState()
    };
    private static final ChatFormatting[] LABEL_COLOURS = {
            ChatFormatting.AQUA, ChatFormatting.GOLD,
            ChatFormatting.LIGHT_PURPLE, ChatFormatting.RED,
            ChatFormatting.YELLOW, ChatFormatting.GREEN,
            ChatFormatting.RED
    };

    private static String lastAction = "COMMAND BUS: STANDBY";
    private static long lastActionAt = Long.MIN_VALUE;

    private NervOperationsConsole() {}

    /** Backfills the console into both local-map and clean-room command halls. */
    public static void install(ServerLevel level, BlockPos origin)
    {
        level.getChunkAt(controlPosition(origin, 0));
        removeLegacyRow(level, origin);
        buildControlPlatform(level, origin);
        int createdControls = 0;
        int createdLabels = 0;
        BlockState button = Blocks.STONE_BUTTON.defaultBlockState()
                .setValue(ButtonBlock.FACE, AttachFace.FLOOR)
                .setValue(ButtonBlock.FACING, Direction.NORTH);
        for (int index = 0; index < CONTROL_COUNT; index++)
        {
            BlockPos position = controlPosition(origin, index);
            BlockPos base = position.below();
            BlockPos support = base.below();
            setIfDifferent(level, support,
                    Blocks.POLISHED_BLACKSTONE.defaultBlockState(),
                    UPDATE_CLIENTS);
            if (!level.getBlockState(base).equals(BASES[index]))
            {
                setIfDifferent(level, base, BASES[index], UPDATE_CLIENTS);
            }
            if (!level.getBlockState(position).is(Blocks.STONE_BUTTON))
            {
                setIfDifferent(level, position, button, UPDATE_CLIENTS);
                createdControls++;
            }

            String tag = LABEL_TAG_PREFIX + IDS[index];
            List<Display.TextDisplay> matches = labels(level, origin, tag);
            Display.TextDisplay label;
            boolean pendingAdd = false;
            if (matches.isEmpty())
            {
                label = EntityType.TEXT_DISPLAY.create(level);
                if (label == null)
                {
                    continue;
                }
                label.addTag(tag);
                label.setNoGravity(true);
                label.setInvulnerable(true);
                label.setSilent(true);
                pendingAdd = true;
                createdLabels++;
            }
            else
            {
                label = matches.get(0);
                for (int duplicate = 1; duplicate < matches.size(); duplicate++)
                {
                    matches.get(duplicate).discard();
                }
            }
            updateLabel(label, position, index);
            if (pendingAdd)
            {
                level.addFreshEntity(label);
            }
        }
        if (createdControls > 0 || createdLabels > 0)
        {
            ProjectSeele.LOGGER.info(
                    "NERV operations console installed: controls={}/{} labels={}/{} createdControls={} createdLabels={}",
                    countControls(level, origin), CONTROL_COUNT,
                    countLabels(level, origin), CONTROL_COUNT,
                    createdControls, createdLabels);
        }
    }

    /**
     * Binds seven controls already authored into the 1:1 imported command
     * module.  The asset is rotated 180 degrees and raised by 97 blocks, so
     * listening at the retired coordinates made every visible key inert.
     *
     * <p>This deliberately does not build another platform: the imported
     * Gendo/operator dais remains the visual authority.</p>
     */
    public static void installImportedV2Controls(ServerLevel level,
                                                 BlockPos centre)
    {
        BlockState button = Blocks.POLISHED_BLACKSTONE_BUTTON
                .defaultBlockState()
                .setValue(ButtonBlock.FACE, AttachFace.FLOOR)
                .setValue(ButtonBlock.FACING, Direction.SOUTH);
        for (int index = 0; index < CONTROL_COUNT; index++)
        {
            BlockPos position = importedV2ControlPosition(centre, index);
            BlockPos support = position.below();
            if (!(level.getBlockState(position).getBlock()
                    instanceof ButtonBlock))
            {
                if (level.getBlockState(support).isAir())
                {
                    setIfDifferent(level, support,
                            Blocks.POLISHED_BLACKSTONE.defaultBlockState(),
                            UPDATE_CLIENTS);
                }
                setIfDifferent(level, position, button, UPDATE_CLIENTS);
            }

            String tag = LABEL_TAG_PREFIX + "v2." + IDS[index];
            List<Display.TextDisplay> matches = importedLabels(
                    level, centre, tag);
            Display.TextDisplay label;
            boolean created = matches.isEmpty();
            if (created)
            {
                label = EntityType.TEXT_DISPLAY.create(level);
                if (label == null)
                {
                    continue;
                }
                label.addTag(tag);
                label.setNoGravity(true);
                label.setInvulnerable(true);
                label.setSilent(true);
            }
            else
            {
                label = matches.get(0);
                for (int duplicate = 1; duplicate < matches.size();
                     duplicate++)
                {
                    matches.get(duplicate).discard();
                }
            }
            updateLabel(label, position, index);
            if (created)
            {
                level.addFreshEntity(label);
            }
        }
    }

    /** Continuous supported dais and stair approach for every command key. */
    private static void buildControlPlatform(ServerLevel level, BlockPos origin)
    {
        int minX = FIRST_CONTROL_X - 2;
        int maxX = FIRST_CONTROL_X + (CONTROL_COUNT - 1) * CONTROL_SPACING + 2;
        int floorY = CONTROL_Y - 2;
        for (int x = minX; x <= maxX; x++)
        {
            for (int z = CONTROL_Z - 3; z <= CONTROL_Z + 3; z++)
            {
                boolean controlColumn = isControlColumn(x, z);
                BlockState floor = controlColumn
                        ? Blocks.POLISHED_BLACKSTONE.defaultBlockState()
                        : Math.floorMod(x + z, 9) == 0
                        ? Blocks.SEA_LANTERN.defaultBlockState()
                        : Blocks.POLISHED_BLACKSTONE.defaultBlockState();
                setIfDifferent(level, origin.offset(x, floorY, z), floor,
                        UPDATE_CLIENTS);
                for (int y = floorY + 1; y <= floorY + 5; y++)
                {
                    // Preserve the seven real bases and buttons. The old code
                    // deleted and recreated them on every repair/install pass.
                    if (controlColumn && (y == CONTROL_Y - 1 || y == CONTROL_Y))
                    {
                        continue;
                    }
                    setIfDifferent(level, origin.offset(x, y, z),
                            Blocks.AIR.defaultBlockState(), UPDATE_CLIENTS);
                }
            }
        }

        // Five real support bents make the elevated row read as a platform,
        // not seven disconnected cubes hanging in the command hall.
        for (int x = minX; x <= maxX; x += 7)
        {
            for (int y = 8; y < floorY; y++)
            {
                setIfDifferent(level, origin.offset(x, y, CONTROL_Z),
                        Blocks.POLISHED_BLACKSTONE_BRICKS.defaultBlockState(),
                        UPDATE_CLIENTS);
            }
        }

        BlockState stair = Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS
                .defaultBlockState().setValue(StairBlock.FACING, Direction.NORTH);
        for (int step = 0; step < 5; step++)
        {
            int z = CONTROL_Z + 8 - step;
            int y = 8 + step;
            for (int x = -3; x <= 3; x++)
            {
                setIfDifferent(level, origin.offset(x, y, z), stair,
                        UPDATE_CLIENTS);
                for (int head = 1; head <= 3; head++)
                {
                    setIfDifferent(level, origin.offset(x, y + head, z),
                            Blocks.AIR.defaultBlockState(), UPDATE_CLIENTS);
                }
            }
        }
        railPlatformEdges(level, origin, minX, maxX, floorY);
    }

    /**
     * Rails and skirts the command dais.
     *
     * <p>The dais is an elevated deck with a seven-wide approach stair; the
     * rest of its rim was an unguarded five-block drop, which is why walking
     * off the back of the operator row dropped the player out of the room.
     * Only rim cells that have no floor of their own are closed, so the
     * imported command module's own geometry is never overwritten.
     */
    private static void railPlatformEdges(ServerLevel level, BlockPos origin,
                                           int minX, int maxX, int floorY)
    {
        int minZ = CONTROL_Z - 3;
        int maxZ = CONTROL_Z + 3;
        for (int x = minX - 1; x <= maxX + 1; x++)
        {
            for (int z = minZ - 1; z <= maxZ + 1; z++)
            {
                boolean onDeck = x >= minX && x <= maxX && z >= minZ && z <= maxZ;
                boolean adjacent = x >= minX - 1 && x <= maxX + 1
                        && z >= minZ - 1 && z <= maxZ + 1;
                if (onDeck || !adjacent)
                {
                    continue;
                }
                // The authored approach stair is the one intended way off.
                if (z == maxZ + 1 && Math.abs(x) <= 3)
                {
                    continue;
                }
                BlockPos rim = origin.offset(x, floorY, z);
                if (level.getBlockState(rim).isFaceSturdy(level, rim, Direction.UP))
                {
                    continue;
                }
                for (int y = 1; y <= 2; y++)
                {
                    setIfDifferent(level, rim.above(y),
                            Blocks.IRON_BARS.defaultBlockState(), UPDATE_CLIENTS);
                }
                // Skirt the exposed underside so the dais reads as built into
                // the room rather than as a slab hanging in mid-air.
                for (int y = 0; y >= -4; y--)
                {
                    BlockPos skirt = rim.above(y);
                    if (!level.getBlockState(skirt).isAir())
                    {
                        break;
                    }
                    setIfDifferent(level, skirt,
                            Blocks.POLISHED_BLACKSTONE_BRICKS.defaultBlockState(),
                            UPDATE_CLIENTS);
                }
            }
        }
    }

    private static boolean isControlColumn(int relativeX, int relativeZ)
    {
        if (relativeZ != CONTROL_Z)
        {
            return false;
        }
        int delta = relativeX - FIRST_CONTROL_X;
        return delta >= 0 && delta % CONTROL_SPACING == 0
                && delta / CONTROL_SPACING < CONTROL_COUNT;
    }

    /** Returns true only for one of the seven exact NERV command buttons. */
    public static BlockPos staffControl(ServerLevel level,String operation,int variant)
    {
        if(FacilityWorldPolicy.isS20Rebuild(level.getServer()) && (operation.equals("city_rise") || operation.equals("city_lower")))
            return S24CoordinateTransform.apply(level.getServer(),S20_AUTHORED_CONTROLS[operation.equals("city_rise")?0:1]);
        if(variant<0||variant>2||!FacilityWorldPolicy.isS20Rebuild(level.getServer()))return null;
        int offset=switch(operation){case "prepare"->6;case "launch"->9;case "recover"->12;default->-1;};
        return offset<0?null:S24CoordinateTransform.apply(level.getServer(),S20_AUTHORED_CONTROLS[offset+2-variant]);
    }

    public record ControlOutcome(long tick, java.util.UUID requester,
                                 BlockPos button, boolean accepted, String message) {}
    private static final java.util.Map<ServerLevel, ControlOutcome> LAST_OUTCOMES = new java.util.WeakHashMap<>();

    /** Read immediately after a physical press; handled does not mean accepted. */
    public static ControlOutcome lastOutcome(ServerLevel level, ServerPlayer requester, BlockPos button)
    {
        ControlOutcome result = LAST_OUTCOMES.get(level);
        return result != null && result.tick() == level.getGameTime()
                && result.requester().equals(requester.getUUID()) && result.button().equals(button) ? result : null;
    }

    /** Returns true only for one of the exact physical NERV command buttons. */
    public static boolean handleUse(ServerPlayer player, BlockPos position)
    {
        if (!player.serverLevel().dimension().equals(GeoFrontCommands.GEOFRONT))
        {
            return false;
        }
        ServerLevel level = player.serverLevel();
        if (FacilityWorldPolicy.isS20Rebuild(level.getServer()))
        {
            int s20Action = s20ActionAt(S24CoordinateTransform.inverse(
                    level.getServer(), position));
            if (s20Action >= 0)
            {
                return handleS20Action(player, level, s20Action, position);
            }
        }
        /*
         * The imported command asset is placed relative to Facility-v2's
         * manifest centre (Y=0), not the legacy mechanical origin (Y=-444).
         * X/Z happen to match, which concealed this as a pure vertical
         * 444-block miss and made every correctly rendered desk switch inert.
         */
        BlockPos origin = FacilityWorldPolicy.isCleanRebuild(
                level.getServer())
                ? FacilityV2SavedData.get(level).manifest().centre()
                : IntegratedNervMapBuilder.geoFrontOrigin(level);
        int action = actionAt(level, origin, position);
        if (action < 0)
        {
            return false;
        }

        FacilityReadinessService.Operation operation = switch (action)
        {
            case 0 -> FacilityReadinessService.Operation.PREPARE;
            case 1, 2, 3 -> FacilityReadinessService.Operation.LAUNCH;
            case 4 -> FacilityReadinessService.Operation.NAVIGATE;
            case 5 -> FacilityReadinessService.Operation.BATTLE_START;
            case 6 -> FacilityReadinessService.Operation.BATTLE_ABORT;
            default -> FacilityReadinessService.Operation.NAVIGATE;
        };
        int variant = action >= 1 && action <= 3 ? action - 1 : -1;
        if (variant >= 0
                && FacilityWorldPolicy.isS20Rebuild(level.getServer()))
        {
            /*
             * A command-room operator is several chunks away from the compact
             * plant. Resolve the requested line before the read-only gate
             * checks its canonical UUID; otherwise a correctly parked or
             * silo-locked EVA looks missing only because its chunk slept.
             */
            EvaLogisticsDirector.loadControlTarget(level, variant);
        }
        FacilityReadinessService.FacilityReadiness readiness =
                FacilityReadinessService.read(level, operation, variant);
        if (!readiness.accepted())
        {
            ActionResult result = new ActionResult(false,
                    readiness.faultCode() + ": " + readiness.message());
            record(level, IDS[action] + ": " + result.message());
            player.displayClientMessage(Component.literal(
                    "[NERV] " + result.message())
                    .withStyle(ChatFormatting.RED), false);
            ProjectSeele.LOGGER.info(
                    "Retired NERV console rejected action: player={} action={} "
                            + "fault={} position={}",
                    player.getGameProfile().getName(), IDS[action],
                    readiness.faultCode(), position.toShortString());
            return true;
        }

        ActionResult result = switch (action)
        {
            case 0 -> prepareSortie(level);
            case 1 -> releaseUnit(level, EvaUnit01Entity.UNIT_00);
            case 2 -> releaseUnit(level, EvaUnit01Entity.UNIT_01);
            case 3 -> releaseUnit(level, EvaUnit01Entity.UNIT_02);
            case 4 -> toggleArmour(level);
            case 5 -> startYashima(level, player);
            case 6 -> abortYashima(level);
            default -> new ActionResult(false, "Unknown MAGI control address.");
        };
        record(level, IDS[action] + ": " + result.message());
        player.displayClientMessage(Component.literal("[NERV] " + result.message())
                .withStyle(result.accepted()
                        ? ChatFormatting.GREEN : ChatFormatting.RED), false);
        ProjectSeele.LOGGER.info(
                "NERV console action: player={} action={} accepted={} position={} result={}",
                player.getGameProfile().getName(), IDS[action],
                result.accepted(), position.toShortString(), result.message());
        return true;
    }

    private static int s20ActionAt(BlockPos position)
    {
        if (S20_ARMAMENT_DEPLOY_CONTROL.equals(position))
        {
            return S20_ARMAMENT_DEPLOY_ACTION;
        }
        if (S20_ARMAMENT_RECALL_CONTROL.equals(position))
        {
            return S20_ARMAMENT_RECALL_ACTION;
        }
        if (S20_CITY_SCREEN_CONTROL.equals(position))
        {
            return S20_CITY_SCREEN_ACTION;
        }
        for (int index = 0; index < S20_CANCEL_CONTROLS.length;
             index++)
        {
            if (S20_CANCEL_CONTROLS[index].equals(position))
            {
                // The physical row follows EVA-02, EVA-01, EVA-00 along +Z.
                return S20_CANCEL_UNIT02_ACTION + index;
            }
        }
        for (int index = 0; index < S20_CONTROLS.length; index++)
        {
            if (S20_CONTROLS[index].equals(position)
                    || S20_AUTHORED_CONTROLS[index].equals(position))
            {
                return index;
            }
        }
        return -1;
    }

    private static boolean handleS20Action(ServerPlayer player,
                                           ServerLevel level,
                                           int action,
                                           BlockPos position)
    {
        ActionResult result;
        if (action == 0 || action == 1)
        {
            if(FacilitySourceAdmissionR45.cityRequestsProhibited(level))
            {player.displayClientMessage(Component.literal("本次为当前source设施专测；城市仍为原始未放置状态，城市变更请求已禁用。"),false);return true;}
            boolean retract = action == 1;
            Tokyo3RetractionDirector.RequestResult city =
                    Tokyo3RetractionDirector.request(level,
                            IntegratedNervMapBuilder.tokyo3Origin(level),
                            retract);
            result = new ActionResult(city.accepted(), city.message());
        }
        else if ((action >= 2 && action <= 5)
                || action == S20_CITY_SCREEN_ACTION)
        {
            int screen = action == S20_CITY_SCREEN_ACTION
                    ? NervCommandDisplayState.CITY_SCREEN : action - 2;
            NervCommandDisplayState displays =
                    NervCommandDisplayState.get(level.getServer());
            boolean visible = displays.toggle(screen);
            displays.broadcast(level);
            String label = switch (screen)
            {
                case 0, 1, 2 -> "EVA-0" + screen + " cockpit screen";
                case 3 -> "lower tactical screen";
                default -> "Tokyo-3 city status wall";
            };
            result = new ActionResult(true,
                    label + (visible ? " powering on." : " shutting down."));
        }
        else if (action >= S20_CANCEL_UNIT02_ACTION
                && action <= S20_CANCEL_UNIT00_ACTION)
        {
            int variant = switch (action)
            {
                case S20_CANCEL_UNIT02_ACTION -> EvaUnit01Entity.UNIT_02;
                case S20_CANCEL_UNIT01_ACTION -> EvaUnit01Entity.UNIT_01;
                default -> EvaUnit01Entity.UNIT_00;
            };
            EvaLogisticsDirector.loadControlTarget(level, variant);
            EvaLogisticsDirector.ActionResult requested =
                    EvaLogisticsDirector.requestCancel(level, variant);
            result = new ActionResult(requested.accepted(),
                    requested.message());
        }
        else if (action == S20_ARMAMENT_DEPLOY_ACTION
                || action == S20_ARMAMENT_RECALL_ACTION)
        {
            NervArmamentStationEntity station =
                    NervArmamentStationEntity.commandStation(level);
            if (station == null)
            {
                result = new ActionResult(false,
                        "No loaded NERV armament building is linked.");
            }
            else
            {
                boolean deploy = action == S20_ARMAMENT_DEPLOY_ACTION;
                boolean changed = deploy ? station.deploy() : station.recall();
                result = new ActionResult(changed,
                        changed ? deploy
                                ? "Armament building deploying."
                                : "Armament building returning underground."
                                : "Armament building rejected the command in "
                                + station.stateName() + ".");
            }
        }
        else
        {
            int variant = switch (action)
            {
                case 6, 9, 12 -> EvaUnit01Entity.UNIT_02;
                case 7, 10, 13 -> EvaUnit01Entity.UNIT_01;
                case 8, 11, 14 -> EvaUnit01Entity.UNIT_00;
                default -> throw new IllegalStateException(
                        "Unknown S20 unit action " + action);
            };
            int operationIndex = action <= 8 ? 0 : action <= 11 ? 1 : 2;
            EvaLogisticsDirector.loadControlTarget(level, variant);
            FacilityReadinessService.Operation operation =
                    switch (operationIndex)
                    {
                        case 0 -> FacilityReadinessService.Operation.PREPARE;
                        case 1 -> FacilityReadinessService.Operation.LAUNCH;
                        default -> FacilityReadinessService.Operation.RECOVERY;
                    };
            FacilityReadinessService.FacilityReadiness readiness =
                    FacilityReadinessService.read(level, operation, variant);
            if (!readiness.accepted())
            {
                result = new ActionResult(false,
                        readiness.faultCode() + ": "
                                + readiness.message());
            }
            else if (operationIndex == 0)
            {
                EvaLogisticsDirector.ActionResult requested =
                        EvaLogisticsDirector.requestPrepare(level, variant);
                result = new ActionResult(requested.accepted(),
                        requested.message());
            }
            else if (operationIndex == 1)
            {
                EvaLogisticsDirector.ActionResult requested =
                        EvaLogisticsDirector.requestLaunch(level, variant);
                result = new ActionResult(requested.accepted(),
                        requested.message());
            }
            else
            {
                EvaLogisticsDirector.ActionResult requested =
                        EvaLogisticsDirector.requestRecovery(level, variant);
                result = new ActionResult(requested.accepted(),
                        requested.message());
            }
        }

        String id = switch (action)
        {
            case S20_CITY_SCREEN_ACTION -> "screen_city";
            case S20_CANCEL_UNIT02_ACTION -> "unit02_cancel_launch";
            case S20_CANCEL_UNIT01_ACTION -> "unit01_cancel_launch";
            case S20_CANCEL_UNIT00_ACTION -> "unit00_cancel_launch";
            case S20_ARMAMENT_DEPLOY_ACTION -> "armament_deploy";
            case S20_ARMAMENT_RECALL_ACTION -> "armament_recall";
            default -> S20_IDS[action];
        };
        LAST_OUTCOMES.put(level, new ControlOutcome(level.getGameTime(), player.getUUID(),
                position.immutable(), result.accepted(), result.message()));
        record(level, id + ": " + result.message());
        if(!STAFF_REPORT.get())player.displayClientMessage(Component.literal(
                        "[NERV S20] " + result.message())
                .withStyle(result.accepted()
                        ? ChatFormatting.GREEN : ChatFormatting.RED), false);
        ProjectSeele.LOGGER.info(
                "S20 command control: player={} action={} accepted={} "
                        + "position={} result={}",
                player.getGameProfile().getName(), id, result.accepted(),
                position.toShortString(), result.message());
        return true;
    }

    public static ConsoleAudit inspect(ServerLevel level, BlockPos origin)
    {
        level.getChunkAt(controlPosition(origin, 0));
        int controls = countControls(level, origin);
        int bases = 0;
        for (int index = 0; index < CONTROL_COUNT; index++)
        {
            if (level.getBlockState(controlPosition(origin, index).below())
                    .equals(BASES[index]))
            {
                bases++;
            }
        }
        int labels = countLabels(level, origin);
        int supports = 0;
        for (int index = 0; index < CONTROL_COUNT; index++)
        {
            if (!level.getBlockState(controlPosition(origin, index)
                    .below(2)).isAir())
            {
                supports++;
            }
        }
        int platformTiles = 0;
        int minX = FIRST_CONTROL_X - 2;
        int maxX = FIRST_CONTROL_X + (CONTROL_COUNT - 1) * CONTROL_SPACING + 2;
        int expectedPlatformTiles = (maxX - minX + 1) * 7;
        for (int x = minX; x <= maxX; x++)
        {
            for (int z = CONTROL_Z - 3; z <= CONTROL_Z + 3; z++)
            {
                BlockState floor = level.getBlockState(
                        origin.offset(x, CONTROL_Y - 2, z));
                if (floor.is(Blocks.POLISHED_BLACKSTONE)
                        || floor.is(Blocks.SEA_LANTERN))
                {
                    platformTiles++;
                }
            }
        }
        int approachSteps = 0;
        for (int step = 0; step < 5; step++)
        {
            int z = CONTROL_Z + 8 - step;
            int y = 8 + step;
            for (int x = -3; x <= 3; x++)
            {
                if (level.getBlockState(origin.offset(x, y, z))
                        .is(Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS))
                {
                    approachSteps++;
                }
            }
        }
        return new ConsoleAudit(controls == CONTROL_COUNT
                && bases == CONTROL_COUNT && labels == CONTROL_COUNT
                && supports == CONTROL_COUNT
                && platformTiles == expectedPlatformTiles
                && approachSteps == 35,
                controls, bases, labels, supports, platformTiles,
                expectedPlatformTiles, approachSteps);
    }

    public static String statusLine(ServerLevel level)
    {
        if (lastActionAt == Long.MIN_VALUE
                || level.getGameTime() - lastActionAt > 600L)
        {
            return "COMMAND BUS: STANDBY";
        }
        return "LAST COMMAND: " + lastAction;
    }

    public static void reset()
    {
        lastAction = "COMMAND BUS: STANDBY";
        lastActionAt = Long.MIN_VALUE;
    }

    private static ActionResult prepareSortie(ServerLevel level)
    {
        boolean modern = FacilityWorldPolicy.isCleanRebuild(
                level.getServer());
        boolean compact = FacilityWorldPolicy.isS20Rebuild(
                level.getServer());
        boolean plantReady = compact
                ? EvaHangarBuilder.runtimeInfrastructurePresent(
                        level, RegionalFacilityLayout.evaOrigin(level))
                : modern ? FacilityV2EvaRuntime.readyAll(level)
                : IntegratedNervMapBuilder.prepareRuntime(level).launchReady();
        if (!plantReady)
        {
            return new ActionResult(false,
                    "MAGI sortie gate failed: the three-line plant "
                            + "has not completed its facility receipts.");
        }
        try
        {
            List<EvaUnit01Entity> units = modern || compact
                    ? EvaLogisticsDirector.ensureFleet(level)
                    : GeoFrontCommands.ensureContinuousSortieUnits(level);
            int started = 0;
            for (int variant = 0; variant < 3; variant++)
            {
                EvaLogisticsDirector.ActionResult transfer =
                        EvaLogisticsDirector.requestPrepare(level, variant);
                if (transfer.accepted())
                {
                    started++;
                }
            }
            if (units.size() != 3)
            {
                return new ActionResult(false,
                        "MAGI check found only " + units.size()
                                + "/3 canonical airframes.");
            }
            if (started == 0)
            {
                return new ActionResult(false,
                        "MAGI check complete; no insertion sequence started. "
                                + "Board a suspended entry plug first.");
            }
            return new ActionResult(true,
                    "MAGI check complete; insertion/transfer started for "
                            + started + "/3 EVA airframes. Remaining cages "
                            + "require a boarded pilot.");
        }
        catch (IllegalStateException exception)
        {
            return new ActionResult(false, exception.getMessage());
        }
    }

    private static ActionResult releaseUnit(ServerLevel level, int variant)
    {
        boolean compact = FacilityWorldPolicy.isS20Rebuild(
                level.getServer());
        if (compact
                ? !compactLaunchMarkersPresent(level, variant)
                : FacilityWorldPolicy.isCleanRebuild(level.getServer())
                ? !FacilityV2EvaRuntime.ready(level, variant)
                : !IntegratedNervMapBuilder.ensureLowerSortieInterface(
                        level, variant))
        {
            return new ActionResult(false,
                    String.format(Locale.ROOT,
                            "EVA-%02d release inhibited: lower carrier route is obstructed.",
                            variant));
        }
        /*
         * Release the SavedData-authoritative airframe only.  Searching the
         * whole map and sorting by distance let a retired duplicate absorb a
         * perfectly valid command-room launch after a save migration.
         */
        EvaUnit01Entity unit =
                EvaLogisticsDirector.canonicalUnit(level, variant);
        if (unit == null)
        {
            return new ActionResult(false,
                    String.format(Locale.ROOT,
                            "EVA-%02d is not linked to the command network.", variant));
        }
        if (!unit.releaseLaunchFromCommand())
        {
            return new ActionResult(false,
                    String.format(Locale.ROOT,
                            "EVA-%02d release inhibited: insert a pilot and complete launch lock.",
                            variant));
        }
        return new ActionResult(true,
                String.format(Locale.ROOT,
                        "EVA-%02d catapult release authorized.", variant));
    }

    private static ActionResult toggleArmour(ServerLevel level)
    {
        if (FacilityWorldPolicy.isS20Rebuild(level.getServer()))
        {
            return new ActionResult(false,
                    "S20 preserves the approved Tokyo-3 city blocks; its "
                            + "retraction actuator has not been recommissioned.");
        }
        if (FacilityWorldPolicy.isCleanRebuild(level.getServer()))
        {
            /*
             * Tokyo3RetractionDirector still owns the retired integrated-map
             * coordinate frame.  Calling it from S19 would paint the old city
             * into the clean world.  Keep the physical key fail-closed until
             * the S19 surface-head/city contract gains its own moving owners.
             */
            return new ActionResult(false,
                    "S19 city-armour actuators are not commissioned yet; "
                            + "no legacy geometry was changed.");
        }
        Tokyo3RetractionDirector.Status status =
                Tokyo3RetractionDirector.status(level,
                        IntegratedNervMapBuilder.tokyo3Origin(level));
        Tokyo3RetractionDirector.RequestResult result =
                Tokyo3RetractionDirector.request(level,
                        IntegratedNervMapBuilder.tokyo3Origin(level),
                        status.targetDepth() == 0);
        return new ActionResult(result.accepted(), result.message());
    }

    private static ActionResult startYashima(ServerLevel level,
                                             ServerPlayer commander)
    {
        if (FacilityWorldPolicy.isS20Rebuild(level.getServer()))
        {
            return new ActionResult(false,
                    "Operation Yashima is held until the compact plant's "
                            + "Tokyo-3 battle anchor is recommissioned.");
        }
        if (FacilityWorldPolicy.isCleanRebuild(level.getServer()))
        {
            return new ActionResult(false,
                    "Operation Yashima is waiting for its S19 Tokyo-3 battle "
                            + "anchor; the retired battlefield was not spawned.");
        }
        boolean launchReady = FacilityV2RescueDirector.isTargetWorld(
                level.getServer())
                ? IntegratedNervMapBuilder.rescueMechanicalReady(level)
                : IntegratedNervMapBuilder.prepareRuntime(level).launchReady();
        if (!launchReady)
        {
            return new ActionResult(false,
                    "Operation Yashima inhibited: live sortie route failed its gate.");
        }
        BattleResult result = Tokyo3RamielBattleDirector.start(level,
                IntegratedNervMapBuilder.tokyo3Origin(level), commander);
        return new ActionResult(result.accepted(), result.message());
    }

    private static ActionResult abortYashima(ServerLevel level)
    {
        if (FacilityWorldPolicy.isS20Rebuild(level.getServer()))
        {
            return new ActionResult(false,
                    "No S20 Yashima operation is active.");
        }
        if (FacilityWorldPolicy.isCleanRebuild(level.getServer()))
        {
            return new ActionResult(false,
                    "No S19 Yashima operation is active.");
        }
        BattleResult result = Tokyo3RamielBattleDirector.abort(level,
                IntegratedNervMapBuilder.tokyo3Origin(level));
        return new ActionResult(result.accepted(), result.message());
    }

    private static List<EvaUnit01Entity> evaUnits(ServerLevel level)
    {
        BlockPos centre = IntegratedNervMapBuilder.tokyo3Origin(level);
        AABB map = new AABB(centre.getX() - 320.0D,
                level.getMinBuildHeight(), centre.getZ() - 320.0D,
                centre.getX() + 320.0D, level.getMaxBuildHeight(),
                centre.getZ() + 320.0D);
        return level.getEntitiesOfClass(EvaUnit01Entity.class, map,
                Entity::isAlive);
    }

    private static void record(ServerLevel level, String action)
    {
        lastAction = action.length() > 92
                ? action.substring(0, 92) : action;
        lastActionAt = level.getGameTime();
    }

    private static int actionAt(ServerLevel level, BlockPos origin,
                                BlockPos position)
    {
        boolean s20 = FacilityWorldPolicy.isS20Rebuild(
                level.getServer());
        boolean imported = FacilityWorldPolicy.isCleanRebuild(
                level.getServer());
        for (int index = 0; index < CONTROL_COUNT; index++)
        {
            int[] local = IMPORTED_V2_CONTROL_LOCAL[index];
            BlockPos expected = s20
                    ? S20CommandPresentationDirector.authoredLocalToWorld(
                            new BlockPos(local[0], local[1], local[2]))
                    : imported
                    ? importedV2ControlPosition(origin, index)
                    : controlPosition(origin, index);
            if (s20)
            {
                expected = S24CoordinateTransform.apply(
                        level.getServer(), expected);
            }
            /*
             * The authored command desks use a two-block-high switch bank:
             * each selected local coordinate has an otherwise identical real
             * button directly below it. Listening only to the upper half made
             * the visible control appear randomly dead depending on which
             * pixel the operator clicked.
             */
            if (expected.equals(position)
                    || (imported || s20)
                    && expected.below().equals(position))
            {
                return index;
            }
        }
        return -1;
    }

    private static boolean compactLaunchMarkersPresent(
            ServerLevel level, int variant)
    {
        return level.getBlockState(
                        IntegratedNervMapBuilder.lowerLiftBed(level, variant))
                .is(Blocks.LODESTONE)
                && level.getBlockState(
                        IntegratedNervMapBuilder.surfaceLiftBed(level, variant))
                .is(Blocks.LODESTONE);
    }

    private static void setIfDifferent(ServerLevel level, BlockPos position,
                                       BlockState state, int flags)
    {
        if (!level.getBlockState(position).equals(state))
        {
            level.setBlock(position, state, flags);
            PerformanceCounters.recordWorldBlockWrites(1);
        }
    }
    private static void removeLegacyRow(ServerLevel level, BlockPos origin)
    {
        for (int index = 0; index < CONTROL_COUNT; index++)
        {
            int x = FIRST_CONTROL_X + index * CONTROL_SPACING;
            BlockPos legacy = origin.offset(x, CONTROL_Y,
                    LEGACY_CONTROL_Z);
            if (level.getBlockState(legacy).is(Blocks.STONE_BUTTON))
            {
                setIfDifferent(level, legacy, Blocks.AIR.defaultBlockState(),
                        UPDATE_CLIENTS);
            }
            BlockState oldBase = level.getBlockState(legacy.below());
            for (BlockState state : BASES)
            {
                if (oldBase.equals(state))
                {
                    setIfDifferent(level, legacy.below(),
                            Blocks.AIR.defaultBlockState(), UPDATE_CLIENTS);
                    break;
                }
            }
        }
    }

    public static BlockPos controlPosition(BlockPos origin, int index)
    {
        if (index < 0 || index >= CONTROL_COUNT)
        {
            throw new IllegalArgumentException(
                    "NERV control index must be within 0.."
                            + (CONTROL_COUNT - 1));
        }
        return origin.offset(FIRST_CONTROL_X + index * CONTROL_SPACING,
                CONTROL_Y, CONTROL_Z);
    }

    /**
     * Exact transform of an authored NBT-local operator-console switch through
     * nerv_command_left.nbt's Facility-v2 CLOCKWISE_180 placement.
     */
    public static BlockPos importedV2ControlPosition(BlockPos centre,
                                                      int index)
    {
        if (index < 0 || index >= CONTROL_COUNT)
        {
            throw new IllegalArgumentException(
                    "NERV control index must be within 0.."
                            + (CONTROL_COUNT - 1));
        }
        int[] local = IMPORTED_V2_CONTROL_LOCAL[index];
        return centre.offset(27 - local[0],
                -368 + local[1], 64 - local[2]);
    }

    private static int countControls(ServerLevel level, BlockPos origin)
    {
        int count = 0;
        for (int index = 0; index < CONTROL_COUNT; index++)
        {
            if (level.getBlockState(controlPosition(origin, index))
                    .is(Blocks.STONE_BUTTON))
            {
                count++;
            }
        }
        return count;
    }

    private static int countLabels(ServerLevel level, BlockPos origin)
    {
        int count = 0;
        for (String id : IDS)
        {
            if (!labels(level, origin, LABEL_TAG_PREFIX + id).isEmpty())
            {
                count++;
            }
        }
        return count;
    }

    private static List<Display.TextDisplay> labels(ServerLevel level,
                                                    BlockPos origin,
                                                    String tag)
    {
        AABB bounds = AABB.ofSize(
                Vec3.atCenterOf(origin.offset(0, CONTROL_Y + 1, CONTROL_Z)),
                80.0D, 32.0D, 40.0D);
        List<Display.TextDisplay> result = new ArrayList<>(
                level.getEntitiesOfClass(Display.TextDisplay.class, bounds,
                        display -> display.getTags().contains(tag)));
        result.sort(Comparator.comparingInt(Entity::getId));
        return result;
    }

    private static List<Display.TextDisplay> importedLabels(
            ServerLevel level, BlockPos centre, String tag)
    {
        AABB bounds = AABB.ofSize(
                Vec3.atCenterOf(centre.offset(0, -325, -4)),
                96.0D, 40.0D, 96.0D);
        List<Display.TextDisplay> result = new ArrayList<>(
                level.getEntitiesOfClass(Display.TextDisplay.class, bounds,
                        display -> display.getTags().contains(tag)));
        result.sort(Comparator.comparingInt(Entity::getId));
        return result;
    }

    private static void updateLabel(Display.TextDisplay label,
                                    BlockPos button, int index)
    {
        Component text = Component.literal(LABELS[index])
                .withStyle(LABEL_COLOURS[index], ChatFormatting.BOLD);
        CompoundTag tag = label.saveWithoutId(new CompoundTag());
        tag.putString("text", Component.Serializer.toJson(text));
        tag.putInt("line_width", 120);
        tag.putInt("background", 0xB0101418);
        tag.putByte("text_opacity", (byte) -1);
        tag.putBoolean("shadow", true);
        tag.putBoolean("see_through", false);
        tag.putBoolean("default_background", false);
        tag.putString("alignment", "center");
        tag.putString("billboard", "vertical");
        tag.putFloat("view_range", 3.0F);
        tag.putFloat("width", 3.5F);
        tag.putFloat("height", 1.4F);
        tag.putInt("glow_color_override", 0xFFFF8000);
        CompoundTag brightness = new CompoundTag();
        brightness.putInt("block", 15);
        brightness.putInt("sky", 15);
        tag.put("brightness", brightness);
        label.load(tag);
        label.setPos(button.getX() + 0.5D, button.getY() + 1.35D,
                button.getZ() + 0.5D);
        label.setYRot(180.0F);
        label.setXRot(0.0F);
    }

    private record ActionResult(boolean accepted, String message) {}

    public record ConsoleAudit(boolean valid, int controls,
                               int bases, int labels, int supports,
                               int platformTiles, int expectedPlatformTiles,
                               int approachSteps)
    {
        public boolean physicalValid()
        {
            return this.controls == CONTROL_COUNT && this.bases == CONTROL_COUNT
                    && this.supports == CONTROL_COUNT
                    && this.platformTiles == this.expectedPlatformTiles
                    && this.approachSteps == 35;
        }

        public String summary()
        {
            return String.format(Locale.ROOT,
                    "valid=%s controls=%d/%d bases=%d/%d labels=%d/%d "
                            + "supports=%d/%d platform=%d/%d stairs=%d/35",
                    this.valid, this.controls, CONTROL_COUNT,
                    this.bases, CONTROL_COUNT, this.labels, CONTROL_COUNT,
                    this.supports, CONTROL_COUNT, this.platformTiles,
                    this.expectedPlatformTiles, this.approachSteps);
        }
    }
}

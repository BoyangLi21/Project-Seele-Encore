package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.mixin.MovingElevatorRemoteAccessor;
import com.projectseele.registry.ModItems;
import com.supermartijn642.movingelevators.MovingElevators;
import com.supermartijn642.movingelevators.blocks.CamoBlockEntity;
import com.supermartijn642.movingelevators.blocks.ControllerBlock;
import com.supermartijn642.movingelevators.blocks.ControllerBlockEntity;
import com.supermartijn642.movingelevators.blocks.RemoteControllerBlockEntity;
import com.supermartijn642.movingelevators.elevator.ElevatorGroup;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.DyeColor;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.AttachFace;
import net.minecraft.world.phys.Vec3;

import java.util.HashSet;
import java.util.HashMap;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.WeakHashMap;

/**
 * Adopts the already approved S20 five-by-five personnel cars into Moving
 * Elevators.  It does not build shafts or rooms: controllers occupy the
 * audited air cell three blocks west of each car centre, and remote panels
 * replace only existing lift buttons (or air reserved for their displays).
 */
public final class S20MovingElevatorsAdapter
{
    private static final int CAGE_HORIZONTAL = 5;
    private static final int SURFACE_CAGE_HORIZONTAL = 7;
    private static final int CAGE_VERTICAL = 6;
    private static final double TARGET_SPEED = 0.85D;
    /** Human-approved half-speed setting for the three-stop x=93 hangar lift. */
    private static final double COMPACT_CAGE_TARGET_SPEED = 0.425D;
    private static final double SURFACE_TARGET_SPEED = 0.85D;
    private static final int UPDATE =
            Block.UPDATE_CLIENTS | Block.UPDATE_KNOWN_SHAPE;
    private static final long ACCESS_WINDOW_TICKS = 600L;
    private static final Map<String,Long> ACCESS_UNTIL = new HashMap<>();
    private static final Set<String> REPORTED_AUTHORED_CONTROLS =
            new HashSet<>();
    private static final Set<String> REPORTED_CONTROLLER_CONFLICTS =
            new HashSet<>();
    private static final Map<ServerLevel,Set<String>> NORMALIZED_CAGES =
            Collections.synchronizedMap(new WeakHashMap<>());
    private static final Map<ServerLevel,Set<String>> FLOOR_REPAIR_HOLDS =
            Collections.synchronizedMap(new WeakHashMap<>());
    /**
     * A control press closes the authored doors just before Moving Elevators
     * captures the cage.  Keep that interlock closed for the short hand-off;
     * once the physical cage is stationary again its actual block footprint,
     * rather than the dependency's offset currentY value, owns the open door.
     */
    private static final Map<ServerLevel,Map<String,Long>>
            DEPARTURE_DOOR_CLOSE_UNTIL =
            Collections.synchronizedMap(new WeakHashMap<>());
    private static final long DEPARTURE_DOOR_CLOSE_TICKS = 40L;
    /**
     * Human-approved remote calls which intentionally sit beyond the normal
     * landing jamb.  They are explicit coordinates, not proximity guesses.
     */
    private static final Map<BlockPos,RemoteCall> REMOTE_CALLS = Map.of();

    private S20MovingElevatorsAdapter() {}

    /** Reconciles one lift and returns true once the old stepwise driver must stop. */
    public static boolean reconcile(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec)
    {
        if (!allStopsLoaded(level, spec))
        {
            return false;
        }
        boolean alreadyOwned = owns(level, spec);
        Set<String> normalized = NORMALIZED_CAGES.computeIfAbsent(level,
                ignored -> new HashSet<>());
        if(alreadyOwned&&(!normalized.contains(spec.id())||level.getServer().getTickCount()%20==0))
        {
            var base=controller(level,controllerPosition(spec,spec.lower()));
            if(base!=null&&base.hasGroup()&&!base.getGroup().isMoving())
            {
                var held=FLOOR_REPAIR_HOLDS.computeIfAbsent(level,l->new HashSet<>());
                if(!repairIdentifiedCabinFloor(level,spec))
                {
                    if(held.add(spec.id()))ProjectSeele.LOGGER.error("Native lift {} held for an ambiguous/unsafe damaged cabin; no shaft clear, floor fill or car rebuild",spec.id());
                    return true;
                }
                held.remove(spec.id());
            }
        }
        /*
         * Once the official controllers and normalized cage own a shaft, the
         * migration scans are finished for this server run.  The old ordering
         * called retireRelocatedCompactCage before this fast path: it read
         * 4,500 cells every tick and deleted the live in-car display, which
         * the reconciler then recreated.  That caused both the server stalls
         * and the view-dependent flashing button.
         */
        if (alreadyOwned && normalized.contains(spec.id()))
        {
            ControllerBlockEntity base = controller(level,
                    controllerPosition(spec, spec.lower()));
            if (base != null && base.hasGroup())
            {
                ElevatorGroup group = base.getGroup();
                if (!group.isMoving())
                {
                    configureTargetSpeed(spec, group);
                }
                if (!group.isMoving()
                        && level.getServer().getTickCount() % 20 == 0
                        && !hasCabinSelectorAtRest(level, spec))
                {
                    ensureCabinPanel(level, spec,
                            controllerPosition(spec, spec.lower()));
                }
                synchronizeDoorsFromPhysicalCage(level, spec,
                        group);
                return true;
            }
        }

        if (!retireRelocatedCompactCage(level, spec))
        {
            return false;
        }
        if (!retireInventedDeepServiceStop(level, spec))
        {
            return false;
        }
        if (!alreadyOwned)
        {
            boolean cabinPresent = false;
            for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
            {
                cabinPresent |= S20PhysicalElevatorDirector.hasAuthoredCabinAt(
                        level, landing.cabinCentre());
            }
            if (!cabinPresent && !requiresEmptyShaftRecovery(spec))
            {
                return false;
            }
        }

        if (!retireSupersededControllers(level, spec))
        {
            return alreadyOwned;
        }
        boolean controllersReady = true;
        for (int index = 0; index < spec.stops().size(); index++)
        {
            S20PhysicalElevatorDirector.Landing landing =
                    spec.stops().get(index);
            BlockPos controllerPos = controllerPosition(spec, landing);
            if (!ensureController(level, controllerPos,
                    controllerFacing(spec)))
            {
                controllersReady = false;
                continue;
            }
            configureController(level, spec, landing, controllerPos, index);
            ensureLandingPanel(level, spec, landing, controllerPos);
        }

        if (!controllersReady)
        {
            return false;
        }

        ControllerBlockEntity base = controller(level,
                controllerPosition(spec, spec.lower()));
        if (base == null || !base.hasGroup())
        {
            // The official block entity joins its group on its first tick.
            return true;
        }
        configureGroup(spec, base.getGroup());
        if (!normalizeLiftCage(level, spec, base.getGroup()))
        {
            return true;
        }
        ensureCabinPanel(level, spec,
                controllerPosition(spec, spec.lower()));
        synchronizeDoorsFromPhysicalCage(level, spec, base.getGroup());
        return true;
    }

    public static boolean isMovingElevatorsBlock(BlockState state)
    {
        return state.is(MovingElevators.elevator_block)
                || state.is(MovingElevators.button_block)
                || state.is(MovingElevators.display_block);
    }

    /** Hidden technical input beneath the visible in-car floor selector. */
    public static boolean isCabinBackingControl(
            ServerLevel level, BlockPos clicked)
    {
        for (S20PhysicalElevatorDirector.LiftSpec spec
                : S20PhysicalElevatorDirector.s20Lifts(level))
        {
            if (!owns(level, spec))
            {
                continue;
            }
            Direction fixedExit = spec.lower().exit();
            for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
            {
                if (clicked.equals(cabinPanelPosition(
                        spec, landing.cabinCentre(), fixedExit)))
                {
                    return true;
                }
            }
        }
        return false;
    }

    /** Card-gates the official controls without replacing its motion code. */
    public static boolean handleSecureUse(
            ServerPlayer player, BlockPos clicked)
    {
        ServerLevel level = player.serverLevel();
        // A physical display click selects a particular native row. Consuming
        // it as a card swipe (including an offhand card) suppressed every real
        // selection while the card was held. The existing group-level guard
        // validates the selected destination and accepts that same held card.
        if (level.getBlockState(clicked).is(MovingElevators.display_block))
        {
            return false;
        }
        for (S20PhysicalElevatorDirector.LiftSpec spec
                : S20PhysicalElevatorDirector.s20Lifts(level))
        {
            if (!owns(level, spec) || !isSecureLift(spec)
                    || !panelBelongsTo(spec, clicked))
            {
                continue;
            }
            boolean hasCard = hasHighestClearanceCard(player);
            if (hasCard)
            {
                ACCESS_UNTIL.put(accessKey(level, spec),
                        level.getGameTime() + ACCESS_WINDOW_TICKS);
                player.displayClientMessage(Component.literal(
                        "NERV CLEARANCE ACCEPTED / FLOORS UNLOCKED")
                        .withStyle(ChatFormatting.GREEN), true);
                level.playSound(null, clicked,
                        SoundEvents.EXPERIENCE_ORB_PICKUP,
                        SoundSource.BLOCKS, 0.8F, 1.65F);
                return true;
            }
            // Empty-hand use always opens the normal floor selector.  The
            // exact selected destination is checked inside ElevatorGroup.
            return false;
        }
        return false;
    }

    /** True once this lift's official controller stack owns the shaft. */
    public static boolean owns(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec)
    {
        for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
        {
            if (controller(level, controllerPosition(spec, landing)) == null)
            {
                return false;
            }
        }
        return true;
    }

    private static boolean allStopsLoaded(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec)
    {
        for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
        {
            if (!level.hasChunkAt(landing.cabinCentre()))
            {
                return false;
            }
        }
        return true;
    }

    /** Removes the unapproved y=-488 stop without touching its shaft shell. */
    private static boolean retireInventedDeepServiceStop(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec)
    {
        if (!spec.id().equals(
                S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID))
        {
            return true;
        }
        BlockPos oldController = new BlockPos(9, -488, 253);
        if (level.getBlockState(oldController)
                .is(MovingElevators.elevator_block))
        {
            ControllerBlockEntity old = controller(level, oldController);
            if (old == null || !old.hasGroup() || old.getGroup().isMoving())
            {
                return false;
            }
            // x=9 is the measured reinforced-deepslate shaft wall on every
            // adjacent Y level; restore that exact continuation.
            level.setBlock(oldController,
                    com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState(), UPDATE);
        }
        for (int y = -488; y <= -486; y++)
        {
            for (int x = 10; x <= 14; x++)
            {
                BlockPos glass = new BlockPos(x, y, 257);
                if (level.getBlockState(glass)
                        .is(Blocks.GRAY_STAINED_GLASS))
                {
                    level.setBlock(glass, Blocks.AIR.defaultBlockState(),
                            UPDATE);
                }
            }
        }
        for (BlockPos residue : new BlockPos[]{
                new BlockPos(9, -487, 257),
                new BlockPos(9, -487, 258)})
        {
            BlockState state = level.getBlockState(residue);
            if (state.is(Blocks.BLACK_CONCRETE)
                    || state.getBlock() instanceof ButtonBlock)
            {
                level.setBlock(residue, Blocks.AIR.defaultBlockState(),
                        UPDATE);
            }
        }
        return true;
    }

    public static BlockPos controllerPosition(
            S20PhysicalElevatorDirector.LiftSpec spec,
            S20PhysicalElevatorDirector.Landing landing)
    {
        if(spec.id().equals(NervLiftPassengerSync.GATEWAY))return RegionalGatewayDirector.controllerPos(landing.walkY());
        /*
         * The controller must never share a plane with either landing door.
         * The previous hard-coded west position was inside every WEST-facing
         * doorway; closing that door replaced the controller with glass and
         * Moving Elevators then dereferenced a missing group in onRemove().
         * Put the complete controller stack on one fixed perpendicular wall
         * instead.  Facing it back toward the cabin preserves the exact cage
         * centre for every door orientation and for two-sided cars.
         */
        return landing.cabinCentre().relative(controllerSide(spec),
                controllerDistance(spec));
    }

    private static Direction controllerSide(
            S20PhysicalElevatorDirector.LiftSpec spec)
    {
        if (spec.id().equals(
                S20PhysicalElevatorDirector.OBSERVATION_HANGAR_LIFT_ID))
        {
            // The upper landing now opens north into the human-authored B-49
            // interchange.  Keep both controllers on the east wall, clear of
            // the lower west door and the upper north door.
            return Direction.EAST;
        }
        if (spec.id().equals(
                S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID))
        {
            // Human-authored B-49 circulation occupies the west side.  Keep
            // all three controller/locator blocks on the opposite east wall:
            // x=96 for the x=93 lift axis.
            return Direction.EAST;
        }
        return spec.lower().exit().getClockWise();
    }

    private static Direction controllerFacing(
            S20PhysicalElevatorDirector.LiftSpec spec)
    {
        if(spec.id().equals(NervLiftPassengerSync.GATEWAY))return Direction.EAST;
        return controllerSide(spec).getOpposite();
    }

    private static int controllerDistance(
            S20PhysicalElevatorDirector.LiftSpec spec)
    {
        return (isSurfaceLift(spec)
                ? SURFACE_CAGE_HORIZONTAL : CAGE_HORIZONTAL) / 2 + 1;
    }

    private static boolean ensureController(
            ServerLevel level, BlockPos position, Direction facing)
    {
        BlockState current = level.getBlockState(position);
        if (!replaceableControllerCell(current))
        {
            String key = level.dimension().location() + ":" + position.asLong();
            if (REPORTED_CONTROLLER_CONFLICTS.add(key))
            {
                ProjectSeele.LOGGER.error(
                        "Moving Elevators migration refused occupied controller cell {} ({})",
                        position.toShortString(), current);
            }
            return false;
        }
        if (!current.is(MovingElevators.elevator_block))
        {
            BlockState controller = MovingElevators.elevator_block
                    .defaultBlockState()
                    .setValue(ControllerBlock.FACING, facing);
            level.setBlock(position, controller, UPDATE);
        }
        return controller(level, position) != null;
    }

    private static boolean replaceableControllerCell(BlockState state)
    {
        // Controllers are deliberately embedded in the audited shaft wall.
        // Treating that wall as a collision made every lift except the one
        // half-migrated compact cage silently fail installation every tick.
        return state.isAir()
                || state.is(MovingElevators.elevator_block)
                || state.is(com.projectseele.world.NervMaterials.STRUCTURAL_SHELL)
                || state.is(Blocks.DEEPSLATE_BRICKS)
                || state.is(Blocks.DEEPSLATE_TILES)
                || state.is(Blocks.POLISHED_DEEPSLATE)
                || state.is(Blocks.POLISHED_BLACKSTONE)
                || state.is(Blocks.SEA_LANTERN)
                || state.is(Blocks.GRAY_STAINED_GLASS)
                || state.is(Blocks.LIGHT_GRAY_STAINED_GLASS)
                || state.is(Blocks.BLACK_CONCRETE);
    }

    private static ControllerBlockEntity controller(
            ServerLevel level, BlockPos position)
    {
        BlockEntity entity = level.getBlockEntity(position);
        return entity instanceof ControllerBlockEntity controller
                ? controller : null;
    }

    private static void configureController(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec,
            S20PhysicalElevatorDirector.Landing landing,
            BlockPos position, int floor)
    {
        ControllerBlockEntity controller = controller(level, position);
        if (controller == null)
        {
            return;
        }
        // Security belongs to the selected destination.  Hiding a floor name
        // or locking the whole in-car panel made every ordinary return trip
        // look forbidden.
        String label = switch(landing.label())
        {
            case "TERMINAL DOGMA" -> "终极教条 / TERMINAL DOGMA";
            case "LOWER INTERCHANGE" -> "总部主环廊";
            case "COMMAND BRIDGE" -> "指挥桥下层";
            case "REAR SERVICE" -> "指挥桥中层";
            case "COMMAND GALLERY" -> "指挥桥上层";
            case "GEOFRONT TRANSIT" -> "地下交通层";
            case "TOKYO-3 SURFACE" -> "地面联络厅";
            case "COMMAND ACCESS" -> "总指挥接待层";
            default -> landing.label();
        };
        if (!Objects.equals(controller.getFloorName(), label))
        {
            controller.setFloorName(label);
        }
        DyeColor color = floor == 0
                ? DyeColor.ORANGE : DyeColor.LIGHT_BLUE;
        if (controller.getDisplayLabelColor() != color)
        {
            controller.setDisplayLabelColor(color);
        }
        if (controller.shouldShowButtons())
        {
            controller.toggleShowButtons();
        }
        camouflage(controller, Blocks.BLACK_CONCRETE.defaultBlockState());
        removePanelDecoration(level, position.above());
        removePanelDecoration(level, position.above(2));
    }

    private static void configureGroup(
            S20PhysicalElevatorDirector.LiftSpec spec, ElevatorGroup group)
    {
        if (group.isMoving())
        {
            return;
        }
        int horizontal = isSurfaceLift(spec)
                ? SURFACE_CAGE_HORIZONTAL : CAGE_HORIZONTAL;
        while (group.getCageWidth() < horizontal
                && group.canIncreaseCageWidth())
        {
            group.increaseCageWidth();
        }
        while (group.getCageWidth() > horizontal
                && group.canDecreaseCageWidth())
        {
            group.decreaseCageWidth();
        }
        while (group.getCageDepth() < horizontal
                && group.canIncreaseCageDepth())
        {
            group.increaseCageDepth();
        }
        while (group.getCageDepth() > horizontal
                && group.canDecreaseCageDepth())
        {
            group.decreaseCageDepth();
        }
        while (group.getCageHeight() < CAGE_VERTICAL
                && group.canIncreaseCageHeight())
        {
            group.increaseCageHeight();
        }
        while (group.getCageHeight() > CAGE_VERTICAL
                && group.canDecreaseCageHeight())
        {
            group.decreaseCageHeight();
        }
        while (group.getCageSideOffset() < 0
                && group.canIncreaseCageSideOffset())
        {
            group.increaseCageSideOffset();
        }
        while (group.getCageSideOffset() > 0
                && group.canDecreaseCageSideOffset())
        {
            group.decreaseCageSideOffset();
        }
        while (group.getCageDepthOffset() > 0
                && group.canDecreaseCageDepthOffset())
        {
            group.decreaseCageDepthOffset();
        }
        while (group.getCageDepthOffset() < 0
                && group.canIncreaseCageDepthOffset())
        {
            group.increaseCageDepthOffset();
        }
        while (group.getCageHeightOffset() < -1
                && group.canIncreaseCageHeightOffset())
        {
            group.increaseCageHeightOffset();
        }
        while (group.getCageHeightOffset() > -1
                && group.canDecreaseCageHeightOffset())
        {
            group.decreaseCageHeightOffset();
        }
        configureTargetSpeed(spec, group);
    }

    private static void configureTargetSpeed(
            S20PhysicalElevatorDirector.LiftSpec spec, ElevatorGroup group)
    {
        double speed = isSurfaceLift(spec)
                ? SURFACE_TARGET_SPEED
                : spec.id().equals(
                        S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID)
                ? COMPACT_CAGE_TARGET_SPEED : TARGET_SPEED;
        if (Math.abs(group.getTargetSpeed() - speed) > 0.001D)
        {
            group.setTargetSpeed(speed);
        }
    }

    private static void ensureLandingPanel(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec,
            S20PhysicalElevatorDirector.Landing landing,
            BlockPos controllerPos)
    {
        BlockPos wall = S20PhysicalElevatorDirector
                .movingElevatorLandingPanelPosition(landing);
        BlockPos call = S20PhysicalElevatorDirector
                .exteriorCallPosition(landing);
        if (!replaceablePanelCell(level.getBlockState(wall))
                || !replaceablePanelCell(level.getBlockState(call)))
        {
            String key = level.dimension().location() + ":" + wall.asLong();
            if (REPORTED_AUTHORED_CONTROLS.add(key))
            {
                ProjectSeele.LOGGER.info(
                        "Moving Elevators kept human-authored landing control at {}",
                        wall.toShortString());
            }
            return;
        }
        /*
         * Moving Elevators' remote block contains two directional arrows.
         * It is useful as the hidden backing for a car selector, but it is
         * the wrong exterior contract: every landing has exactly one summon
         * control.  Restore the audited wall cell and put one ordinary wall
         * button at the original call coordinate; handleExternalCall routes
         * that one input straight to this floor through the official group.
         */
        if (!level.getBlockState(wall).is(Blocks.BLACK_CONCRETE))
        {
            level.setBlock(wall, Blocks.BLACK_CONCRETE.defaultBlockState(),
                    UPDATE);
        }
        BlockState callState = Blocks.POLISHED_BLACKSTONE_BUTTON
                .defaultBlockState()
                .setValue(ButtonBlock.FACE, AttachFace.WALL)
                .setValue(ButtonBlock.FACING,
                        S20PhysicalElevatorDirector.exteriorCallFacing(landing))
                .setValue(ButtonBlock.POWERED, false);
        if (!level.getBlockState(call).equals(callState))
        {
            level.setBlock(call, callState, UPDATE);
        }
        removePanelDecoration(level, wall.above());
        removePanelDecoration(level, wall.above(2));
        removePanelDecoration(level, call.above());
        removePanelDecoration(level, call.above(2));
        removeRetiredLandingPanel(level, landing, call);
    }

    /** Routes the single exterior wall button to its exact authored floor. */
    public static boolean handleExternalCall(
            ServerPlayer player, BlockPos clicked)
    {
        ServerLevel level = player.serverLevel();
        for (S20PhysicalElevatorDirector.LiftSpec spec
                : S20PhysicalElevatorDirector.s20Lifts(level))
        {
            S20PhysicalElevatorDirector.Landing landing =
                    landingForExternalCall(spec, clicked);
            if (landing == null)
            {
                continue;
            }
            // Calling the car from inside the restricted landing is egress.
            // Requiring the admission card here trapped occupants who had
            // already arrived in Dogma and then put the card away.
            boolean leavingRestrictedLanding = localLandingEgress(player, landing);
            if (isSecureLift(spec) && restrictedLanding(spec, landing)
                    && !leavingRestrictedLanding
                    && !accessUnlocked(level, spec))
            {
                boolean hasCard = hasHighestClearanceCard(player);
                if (!hasCard)
                {
                    player.displayClientMessage(Component.literal(
                            "ACCESS DENIED / NERV ACCESS CARD REQUIRED")
                            .withStyle(ChatFormatting.RED), true);
                    level.playSound(null, clicked,
                            SoundEvents.IRON_DOOR_CLOSE,
                            SoundSource.BLOCKS, 0.8F, 0.72F);
                    return true;
                }
                ACCESS_UNTIL.put(accessKey(level, spec),
                        level.getGameTime() + ACCESS_WINDOW_TICKS);
                player.displayClientMessage(Component.literal(
                        "NERV CLEARANCE ACCEPTED / FLOOR UNLOCKED")
                        .withStyle(ChatFormatting.GREEN), true);
            }
            // The x=96 controller and x=93 car belong to adjacent chunks.
            // A remote first call can load the controller without the car;
            // reconcile only after the actual cage footprint is available.
            for(var stop:spec.stops())level.getChunkAt(stop.cabinCentre());
            boolean reconciledForCall=reconcile(level,spec);
            if(!callControllersReadyR43(level,spec.id()))
            {
                NativeLiftCallRetryR43.external(player,spec.id(),clicked);
                return true;
            }
            ControllerBlockEntity target = controller(level,
                    controllerPosition(spec, landing));
            if (target == null || !target.hasGroup())
            {
                player.displayClientMessage(Component.literal(
                        "NERV LIFT INITIALIZING / PRESS AGAIN")
                        .withStyle(ChatFormatting.YELLOW), true);
                return true;
            }
            ElevatorGroup group = target.getGroup();
            if(Boolean.getBoolean("projectseele.r43LiftCallTrace"))
            {
                var floors=new java.util.ArrayList<Integer>();for(int i=0;i<group.getFloorCount();i++)floors.add(group.getFloorYLevel(i));
                ProjectSeele.LOGGER.info("R43 native lift call: id={} reconciled={} target={} nativeFloors={} moving={} currentY={}",
                        spec.id(),reconciledForCall,target.getFloorLevel(),floors,group.isMoving(),group.getCurrentY());
            }
            BlockState physicalButton = level.getBlockState(clicked);
            if (physicalButton.getBlock() instanceof ButtonBlock)
            {
                physicalButton.use(level, player, net.minecraft.world.InteractionHand.MAIN_HAND,
                        new net.minecraft.world.phys.BlockHitResult(Vec3.atCenterOf(clicked), landing.exit(), clicked, false));
            }
            if (!group.isMoving()
                    && S20PhysicalElevatorDirector.hasAuthoredCabinAt(
                    level, landing.cabinCentre()))
            {
                /*
                 * A landing call is not a door toggle.  Passing a same-floor
                 * request to Moving Elevators briefly captures/releases the
                 * car and makes the opposite door flash into existence.
                 */
                clearDepartureDoorInterlock(level, spec);
                S20PhysicalElevatorDirector.synchronizeMovingElevatorDoors(
                        level, spec, landing.walkY(), false);
                player.displayClientMessage(Component.literal("电梯已在本层 / LIFT HERE"), true);
                return true;
            }
            synchronizeDoorsForDeparture(level, spec);
            group.onDisplayPress(target.getFloorLevel(), 0, player);
            player.displayClientMessage(Component.literal(group.isMoving()
                    ? "呼梯已受理，请在层门外等候 / LIFT CALLED"
                    : "电梯尚未出发，请检查层门与轿厢状态 / LIFT NOT READY"), true);
            level.playSound(null, clicked, SoundEvents.STONE_BUTTON_CLICK_ON,
                    SoundSource.BLOCKS, 0.65F, 1.35F);
            return true;
        }
        return false;
    }

    static boolean callControllersReadyR43(ServerLevel level,String liftId)
    {
        for(var spec:S20PhysicalElevatorDirector.s20Lifts(level))if(spec.id().equals(liftId))
        {
            for(var landing:spec.stops())
            {
                var controller=controller(level,controllerPosition(spec,landing));
                if(controller==null||!controller.hasGroup())return false;
            }
            return true;
        }
        return false;
    }

    private static S20PhysicalElevatorDirector.Landing landingForExternalCall(
            S20PhysicalElevatorDirector.LiftSpec spec, BlockPos clicked)
    {
        for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
        {
            if (clicked.equals(S20PhysicalElevatorDirector
                    .exteriorCallPosition(landing)))
            {
                return landing;
            }
        }
        RemoteCall remote = REMOTE_CALLS.get(clicked);
        if (remote != null && remote.liftId().equals(spec.id())
                && remote.stopIndex() >= 0
                && remote.stopIndex() < spec.stops().size())
        {
            return spec.stops().get(remote.stopIndex());
        }
        return null;
    }

    private static void removePanelDecoration(
            ServerLevel level, BlockPos position)
    {
        BlockState state = level.getBlockState(position);
        if (state.is(MovingElevators.display_block)
                || state.is(MovingElevators.button_block)
                || state.getBlock() instanceof ButtonBlock)
        {
            level.setBlock(position, Blocks.AIR.defaultBlockState(), UPDATE);
        }
    }

    /**
     * Closes both sides before Moving Elevators captures a physical cage.
     * This runs at Forge HIGHEST priority, ahead of the dependency's input
     * handler, so neither observation nor hangar cars can move with one side
     * left open from their previous landing.
     */
    public static void prepareDoorsBeforeUse(
            ServerPlayer player, BlockPos clicked)
    {
        ServerLevel level = player.serverLevel();
        for (S20PhysicalElevatorDirector.LiftSpec spec
                : S20PhysicalElevatorDirector.s20Lifts(level))
        {
            if (!owns(level, spec) || !panelBelongsTo(spec, clicked))
            {
                continue;
            }
            synchronizeDoorsForDeparture(level, spec);
            return;
        }
    }

    private static void synchronizeDoorsForDeparture(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec)
    {
        DEPARTURE_DOOR_CLOSE_UNTIL.computeIfAbsent(
                level, ignored -> new HashMap<>()).put(spec.id(),
                level.getGameTime() + DEPARTURE_DOOR_CLOSE_TICKS);
        S20PhysicalElevatorDirector.synchronizeMovingElevatorDoors(
                level, spec, Double.NaN, true);
    }

    private static void clearDepartureDoorInterlock(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec)
    {
        Map<String,Long> interlocks = DEPARTURE_DOOR_CLOSE_UNTIL.get(level);
        if (interlocks != null)
        {
            interlocks.remove(spec.id());
        }
    }

    /**
     * Moving Elevators reports a controller-relative currentY for several
     * migrated R28 shafts.  Comparing that value to walkY made a same-floor
     * call open for one tick and immediately close again.  The five-by-five
     * cage floor is the authoritative arrival sensor: it moves with the car
     * and exists at exactly one stop.
     */
    private static void synchronizeDoorsFromPhysicalCage(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec,
            ElevatorGroup group)
    {
        Map<String,Long> interlocks = DEPARTURE_DOOR_CLOSE_UNTIL.get(level);
        long closeUntil = interlocks == null ? 0L
                : interlocks.getOrDefault(spec.id(), 0L);
        if (group.isMoving() || level.getGameTime() < closeUntil)
        {
            S20PhysicalElevatorDirector.synchronizeMovingElevatorDoors(
                    level, spec, Double.NaN, true);
            return;
        }
        if (interlocks != null)
        {
            interlocks.remove(spec.id());
        }
        for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
        {
            if (S20PhysicalElevatorDirector.hasAuthoredCabinAt(
                    level, landing.cabinCentre()))
            {
                S20PhysicalElevatorDirector.synchronizeMovingElevatorDoors(
                        level, spec, landing.walkY(), false);
                return;
            }
        }
        S20PhysicalElevatorDirector.synchronizeMovingElevatorDoors(
                level, spec, group.getCurrentY(), false);
    }

    private static void ensureCabinPanel(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec,
            BlockPos baseController)
    {
        for (int floorIndex = 0;
             floorIndex < spec.stops().size(); floorIndex++)
        {
            S20PhysicalElevatorDirector.Landing landing =
                    spec.stops().get(floorIndex);
            BlockPos centre = landing.cabinCentre();
            if (!S20PhysicalElevatorDirector.hasAuthoredCabinAt(level, centre))
            {
                continue;
            }
            Direction fixedExit = spec.lower().exit();
            Direction side = cabinPanelSide(spec, fixedExit);
            BlockPos input = cabinPanelPosition(spec, centre, fixedExit);
            if (!replaceablePanelCell(level.getBlockState(input)))
            {
                return;
            }
            ControllerBlockEntity actualBase = controller(level, baseController);
            int nativeFloorCount = actualBase != null && actualBase.getGroup() != null
                    ? actualBase.getGroup().getFloorCount() : spec.stops().size();
            removeRetiredCabinButtons(level, spec, centre, fixedExit, input, nativeFloorCount);
            bindRemote(level, input, side.getOpposite(), baseController,
                    floorIndex);
            ensureDisplays(level, input, fixedExit,
                    Blocks.BLACK_CONCRETE.defaultBlockState(), nativeFloorCount);
            return;
        }
    }

    private static boolean hasCabinSelectorAtRest(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec)
    {
        Direction exit = spec.lower().exit();
        for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
        {
            if (!S20PhysicalElevatorDirector.hasAuthoredCabinAt(
                    level, landing.cabinCentre()))
            {
                continue;
            }
            BlockPos input = cabinPanelPosition(
                    spec, landing.cabinCentre(), exit);
            return level.getBlockState(input)
                    .is(MovingElevators.button_block)
                    && level.getBlockState(input.above())
                    .is(MovingElevators.display_block);
        }
        return false;
    }

    private static void removeRetiredCabinButtons(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec,
            BlockPos centre, Direction exit, BlockPos officialPanel, int nativeFloorCount)
    {
        for (int index = 0; index < spec.stops().size(); index++)
        {
            BlockPos position = S20PhysicalElevatorDirector
                    .interiorButtonPosition(centre, exit, index);
            if (!position.equals(officialPanel)
                    && level.getBlockState(position).getBlock()
                    instanceof ButtonBlock)
            {
                level.setBlock(position, Blocks.AIR.defaultBlockState(), UPDATE);
            }
        }
        Set<Direction> exits = new HashSet<>();
        for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
        {
            exits.add(landing.exit());
        }
        for (Direction candidateExit : exits)
        {
            for (int index = 0; index < spec.stops().size(); index++)
            {
                BlockPos position = S20PhysicalElevatorDirector
                        .interiorButtonPosition(
                                centre, candidateExit, index);
                removeRetiredPanelBlock(level, position, officialPanel);
                removeRetiredPanelBlock(level, position.above(), officialPanel);
                removeRetiredPanelBlock(level, position.above(2), officialPanel);
            }
        }

        /*
         * Old iterations left remote arrows at arbitrary cells inside the
         * moving cage (for example 93,-418,242).  Scan only the measured car
         * envelope, retain the one technical input and its labelled selector
         * (two vertical tiles when actual floors>7), and remove every other
         * elevator control or legacy button.
         * No shaft, corridor or authored console is touched by this pass.
         */
        int radius = isSurfaceLift(spec)
                ? SURFACE_CAGE_HORIZONTAL / 2 : CAGE_HORIZONTAL / 2;
        for (int dx = -radius; dx <= radius; dx++)
        {
            for (int dz = -radius; dz <= radius; dz++)
            {
                for (int dy = -1; dy < CAGE_VERTICAL - 1; dy++)
                {
                    BlockPos position = centre.offset(dx, dy, dz);
                    if (position.equals(officialPanel)
                            || position.equals(officialPanel.above())
                            || nativeFloorCount > 7 && position.equals(officialPanel.above(2)))
                    {
                        continue;
                    }
                    BlockState state = level.getBlockState(position);
                    if (state.is(MovingElevators.button_block)
                            || state.is(MovingElevators.display_block)
                            || state.getBlock() instanceof ButtonBlock)
                    {
                        level.setBlock(position,
                                Blocks.AIR.defaultBlockState(), UPDATE);
                    }
                }
            }
        }
    }

    private static void removeRetiredLandingPanel(
            ServerLevel level,
            S20PhysicalElevatorDirector.Landing landing,
            BlockPos officialPanel)
    {
        BlockPos old = S20PhysicalElevatorDirector
                .legacyExteriorCallPosition(landing);
        removeRetiredPanelBlock(level, old, officialPanel);
        removeRetiredPanelBlock(level, old.above(), officialPanel);
        removeRetiredPanelBlock(level, old.above(2), officialPanel);
    }

    private static void removeRetiredPanelBlock(
            ServerLevel level, BlockPos position, BlockPos officialPanel)
    {
        if (position.equals(officialPanel)
                || position.equals(officialPanel.above())
                || position.equals(officialPanel.above(2)))
        {
            return;
        }
        BlockState state = level.getBlockState(position);
        if (isMovingElevatorsBlock(state)
                || state.getBlock() instanceof ButtonBlock)
        {
            level.setBlock(position, Blocks.AIR.defaultBlockState(), UPDATE);
        }
    }

    private static boolean replaceablePanelCell(BlockState state)
    {
        return state.isAir()
                || state.getBlock() instanceof ButtonBlock
                || isMovingElevatorsBlock(state)
                || state.is(com.projectseele.registry.ModBlocks
                        .CLEAR_GLASS.get())
                || state.is(com.projectseele.world.NervMaterials.STRUCTURAL_SHELL)
                || state.is(com.projectseele.registry.ModBlocks.NERV_WALL_PANEL.get())
                || state.is(com.projectseele.registry.ModBlocks.NERV_WALL_DATUM.get())
                || state.is(com.projectseele.registry.ModBlocks.TV_STAFF_LIFT_PANEL_R45.get())
                || state.is(com.projectseele.registry.ModBlocks.TV_STAFF_LIFT_BAND_R45.get())
                || state.is(com.projectseele.registry.ModBlocks.TV_UTILITY_LIFT_CEILING_R45.get())
                || state.is(Blocks.BLACK_CONCRETE)
                || state.is(Blocks.ORANGE_CONCRETE)
                || state.is(Blocks.IRON_BLOCK)
                || S20PhysicalElevatorDirector.isCabinFloor(state);
    }

    private static boolean isSurfaceLift(
            S20PhysicalElevatorDirector.LiftSpec spec)
    {
        return spec.id().equals(
                S20PhysicalElevatorDirector.SURFACE_TRANSIT_LIFT_ID);
    }

    /** Safely retires every controller from the broken west-only layout. */
    private static boolean retireSupersededControllers(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec)
    {
        Set<BlockPos> retired = new LinkedHashSet<>();
        int scanRadius = controllerDistance(spec) + 1;
        Direction expectedFacing = controllerFacing(spec);
        for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
        {
            BlockPos official = controllerPosition(spec, landing);
            for (int dx = -scanRadius; dx <= scanRadius; dx++)
            {
                for (int dz = -scanRadius; dz <= scanRadius; dz++)
                {
                    BlockPos candidate = landing.cabinCentre()
                            .offset(dx, 0, dz);
                    BlockState state = level.getBlockState(candidate);
                    if (!state.is(MovingElevators.elevator_block))
                    {
                        continue;
                    }
                    boolean correct = candidate.equals(official)
                            && state.hasProperty(ControllerBlock.FACING)
                            && state.getValue(ControllerBlock.FACING)
                            == expectedFacing;
                    if (!correct)
                    {
                        retired.add(candidate.immutable());
                    }
                }
            }
        }

        /*
         * ControllerBlockEntity.onRemove assumes its capability group exists.
         * Validate the complete retirement set before changing one block, so
         * a newly loaded or moving group can finish a tick without a partial
         * migration and without the dependency's null-group crash.
         */
        for (BlockPos old : retired)
        {
            ControllerBlockEntity entity = controller(level, old);
            if (entity != null && !entity.hasGroup())
            {
                // Moving Elevators registers a freshly loaded controller in
                // its capability on the following tick.  Its onRemove path
                // assumes that registration already exists, so removing this
                // half-initialised block would throw inside the dependency.
                return false;
            }
            if (entity != null && entity.hasGroup()
                    && entity.getGroup().isMoving())
            {
                return false;
            }
        }
        for (BlockPos old : retired)
        {
            if (level.getBlockState(old).is(MovingElevators.elevator_block))
            {
                level.removeBlock(old, false);
            }
        }
        return true;
    }

    /**
     * Retires the two commissioned controllers and their cosmetic panels from
     * the superseded x=108/z=192 axis.  This must happen through the live mod
     * API: deleting ControllerBlockEntity NBT offline leaves a stale elevator
     * group and reproduces the dependency's null-group onRemove crash.
     */
    private static boolean retireRelocatedCompactCage(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec)
    {
        // The regional cold migration already retired this old site and moved
        // both native groups. Loading the new car must not depend on old chunks.
        if (RegionalFacilityLayout.migrated(level.getServer())) return true;
        if (!spec.id().equals(
                S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID))
        {
            return true;
        }
        BlockPos[] oldControllers = {
                new BlockPos(105, -442, 192),
                new BlockPos(105, -394, 192),
                new BlockPos(86, -442, 204),
                new BlockPos(86, -370, 204),
        };
        for (BlockPos old : oldControllers)
        {
            if (!level.hasChunkAt(old))
            {
                return false;
            }
            ControllerBlockEntity entity = controller(level, old);
            if (entity != null && (!entity.hasGroup()
                    || entity.getGroup().isMoving()))
            {
                return false;
            }
        }
        for (BlockPos old : oldControllers)
        {
            if (level.getBlockState(old).is(MovingElevators.elevator_block))
            {
                level.removeBlock(old, false);
            }
        }
        for (int[] oldAxis : new int[][] {
                {108, -442, 192}, {108, -394, 192},
                {89, -442, 204}, {89, -370, 204}})
        {
            for (int x = oldAxis[0] - 7; x <= oldAxis[0] + 7; x++)
            {
                for (int y = oldAxis[1] - 1; y <= oldAxis[1] + 3; y++)
                {
                    for (int z = oldAxis[2] - 7;
                         z <= oldAxis[2] + 7; z++)
                    {
                        BlockPos position = new BlockPos(x, y, z);
                        if (insideCurrentCage(spec, position))
                        {
                            continue;
                        }
                        BlockState state = level.getBlockState(position);
                        if (state.is(MovingElevators.button_block)
                                || state.is(MovingElevators.display_block))
                        {
                            level.removeBlock(position, false);
                        }
                    }
                }
            }
        }
        return true;
    }

    private static boolean insideCurrentCage(
            S20PhysicalElevatorDirector.LiftSpec spec, BlockPos position)
    {
        int radius = isSurfaceLift(spec)
                ? SURFACE_CAGE_HORIZONTAL / 2 : CAGE_HORIZONTAL / 2;
        for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
        {
            BlockPos centre = landing.cabinCentre();
            if (Math.abs(position.getX() - centre.getX()) <= radius
                    && Math.abs(position.getZ() - centre.getZ()) <= radius
                    && position.getY() >= centre.getY() - 1
                    && position.getY()
                    < centre.getY() + CAGE_VERTICAL - 1)
            {
                return true;
            }
        }
        return false;
    }

    /**
     * Moving Elevators needs exactly one cage in a group and completely empty
     * capture volumes at every other floor.  Old S20 migrations left partial
     * cars and controls at several stops, which made every destination report
     * as obstructed.  Normalize each shaft once per loaded world, using only
     * the dependency's exact cage cuboids.
     */
    private static boolean normalizeLiftCage(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec,
            ElevatorGroup group)
    {
        Set<String> normalized = NORMALIZED_CAGES.computeIfAbsent(
                level, ignored -> new HashSet<>());
        if (normalized.contains(spec.id()))
        {
            return true;
        }
        if (group.isMoving())
        {
            return false;
        }

        /*
         * A healthy stopped cage is already durable in the Moving Elevators
         * world capability.  Re-clearing the complete shaft on every client
         * launch dirtied tens of thousands of cells, caused the 8-12 second
         * startup catch-up, and made the next pause-save expensive.  Adopt
         * exactly one persisted cage when every anchor still matches; broken,
         * duplicate or missing cages continue through the recovery rebuild.
         */
        if (adoptPersistedCage(level, spec, group, normalized))
        {
            return true;
        }

        S20PhysicalElevatorDirector.Landing source = null;
        int bestFloorScore = 0;
        for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
        {
            BlockPos anchor = group.getCageAnchorBlockPos(landing.walkY());
            if (!captureMatchesLanding(group, anchor, landing.cabinCentre()))
            {
                ProjectSeele.LOGGER.error(
                        "Moving Elevators cage anchor mismatch for {} at {}",
                        spec.id(), anchor.toShortString());
                return false;
            }
            int score = 0;
            for (int dx = 0; dx < group.getCageSizeX(); dx++)
            {
                for (int dz = 0; dz < group.getCageSizeZ(); dz++)
                {
                    if (S20PhysicalElevatorDirector.isCabinFloor(
                            level.getBlockState(anchor.offset(dx, 0, dz))))
                    {
                        score++;
                    }
                }
            }
            if (score > bestFloorScore)
            {
                bestFloorScore = score;
                source = landing;
            }
        }
        if (source == null)
        {
            source = recoverySource(spec);
            if (source == null)
            {
                return false;
            }
        }

        // Fail closed before changing a voxel if an unexpected controller is
        // inside a capture volume.  Official controllers are one block beyond
        // these cuboids and must never pass through Moving Elevators.onRemove.
        for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
        {
            BlockPos anchor = group.getCageAnchorBlockPos(landing.walkY());
            for (int dx = 0; dx < group.getCageSizeX(); dx++)
            {
                for (int dy = 0; dy < group.getCageSizeY(); dy++)
                {
                    for (int dz = 0; dz < group.getCageSizeZ(); dz++)
                    {
                        if (level.getBlockState(anchor.offset(dx, dy, dz))
                                .is(MovingElevators.elevator_block))
                        {
                            ProjectSeele.LOGGER.error(
                                    "Moving Elevators refused to normalize {}: controller inside cage at {}",
                                    spec.id(), anchor.offset(dx, dy, dz)
                                            .toShortString());
                            return false;
                        }
                    }
                }
            }
        }

        clearShaftInterior(level, group, spec);
        buildCanonicalCage(level, spec, group, source);
        /*
         * Moving Elevators snapshots the complete cage only when motion
         * starts.  Install the selector before its first availability scan,
         * otherwise the dependency can capture the old glass wall and place
         * it back over our panel at the next stop (the view-dependent
         * button/glass flicker reported in the compact cage).
         */
        ensureCabinPanel(level, spec,
                controllerPosition(spec, spec.lower()));
        for (int floor = 0; floor < group.getFloorCount(); floor++)
        {
            group.isCageAvailableAt(floor, true, null);
        }
        normalized.add(spec.id());
        ProjectSeele.LOGGER.info(
                "Moving Elevators normalized {}: one cage at {}, {} empty destinations",
                spec.id(), source.cabinCentre().toShortString(),
                spec.stops().size() - 1);
        return true;
    }

    private static boolean adoptPersistedCage(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec,
            ElevatorGroup group, Set<String> normalized)
    {
        S20PhysicalElevatorDirector.Landing occupied = null;
        for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
        {
            BlockPos anchor = group.getCageAnchorBlockPos(landing.walkY());
            if (!captureMatchesLanding(group, anchor,
                    landing.cabinCentre()))
            {
                return false;
            }
            if (!S20PhysicalElevatorDirector.hasAuthoredCabinAt(
                    level, landing.cabinCentre()))
            {
                continue;
            }
            if (occupied != null)
            {
                return false;
            }
            occupied = landing;
        }
        if (occupied == null)
        {
            return false;
        }

        ensureCabinPanel(level, spec,
                controllerPosition(spec, spec.lower()));
        if (!hasCabinSelectorAtRest(level, spec))
        {
            return false;
        }
        for (int floor = 0; floor < group.getFloorCount(); floor++)
        {
            group.isCageAvailableAt(floor, true, null);
        }
        normalized.add(spec.id());
        ProjectSeele.LOGGER.info(
                "Moving Elevators adopted persisted {} cage at {}; shaftWrites=0",
                spec.id(), occupied.cabinCentre().toShortString());
        return true;
    }

    /**
     * The bridge and rear-service stops are only four blocks apart, while
     * the capture box is six high. Native availability accepts any movable
     * block, so a call from below otherwise mistakes the bottom two layers
     * of the service car for a second car at the bridge and tears it apart.
     * Restrict only this authored group; other/player-built lifts retain the
     * dependency's normal rules. Run inside its availability calculation so
     * both the selected source and the synced floor indicators agree.
     */
    public static boolean validCommandCageSource(
            Level level, ElevatorGroup group, BlockPos anchor)
    {
        if (!(level instanceof ServerLevel serverLevel)
                || !level.dimension().location().toString().equals("projectseele:geofront"))
        {
            return true;
        }
        S20PhysicalElevatorDirector.LiftSpec spec = NervLiftPassengerSync.managedLifts(serverLevel).stream()
                .filter(candidate -> {
                    BlockPos base = controllerPosition(candidate,candidate.lower());
                    return group.x==base.getX() && group.z==base.getZ()
                            && group.facing==controllerFacing(candidate);
                }).findFirst().orElse(null);
        if(spec==null)return true;
        if(FLOOR_REPAIR_HOLDS.getOrDefault(serverLevel,Set.of()).contains(spec.id()))return false;
        for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
        {
            if (!captureMatchesLanding(group, anchor, landing.cabinCentre()))
            {
                continue;
            }
            for (int dx = 0; dx < group.getCageSizeX(); dx++)
            {
                for (int dz = 0; dz < group.getCageSizeZ(); dz++)
                {
                    BlockState floor = level.getBlockState(anchor.offset(dx,0,dz));
                    if (!S20PhysicalElevatorDirector.isCabinFloor(floor)
                            && !(group.getCageSizeX()>7 && floor.is(Blocks.SMOOTH_STONE)))
                    {
                        return false;
                    }
                }
            }
            return true;
        }
        return false;
    }

    private static boolean captureMatchesLanding(
            ElevatorGroup group, BlockPos anchor, BlockPos centre)
    {
        return anchor.getX() + group.getCageSizeX() / 2 == centre.getX()
                && anchor.getY() == centre.getY() - 1
                && anchor.getZ() + group.getCageSizeZ() / 2
                == centre.getZ();
    }

    /** A nearly intact parked car is identifiable by its floor, roof and
     * registered landing. Repair missing tiles without rebuilding its body,
     * controller, inventory-bearing blocks or a moving cage. */
    private static boolean repairIdentifiedCabinFloor(ServerLevel level,S20PhysicalElevatorDirector.LiftSpec spec)
    {
        int radius=isSurfaceLift(spec)?3:2,area=(radius*2+1)*(radius*2+1);
        var repairCells=new java.util.ArrayList<BlockPos>();
        BlockState repairMaterial=null;int identifiedCars=0;boolean unsafe=false;
        for(var landing:spec.stops())
        {
            var missing=new java.util.ArrayList<BlockPos>();var materials=new java.util.HashMap<BlockState,Integer>();boolean foreign=false;
            for(int x=-radius;x<=radius;x++)for(int z=-radius;z<=radius;z++)
            {
                var at=landing.cabinCentre().offset(x,-1,z);var state=level.getBlockState(at);
                if(state.isAir())missing.add(at);
                else if(S20PhysicalElevatorDirector.isCabinFloor(state))materials.merge(state,1,Integer::sum);
                else foreign=true;
            }
            // Requiring a completely intact floor here made this repair
            // unreachable for the one missing tile it was intended to fix.
            // A complete roof and this car's untouched native selector are
            // independent identity evidence; a bare stop/platform is not.
            boolean roof=true;
            for(int x=-radius;x<=radius;x++)for(int z=-radius;z<=radius;z++)
                roof&=TvLiftFinishR45.recognizedCabinRoof(level,spec,level.getBlockState(landing.cabinCentre().offset(x,CAGE_VERTICAL-2,z)));
            var input=cabinPanelPosition(spec,landing.cabinCentre(),spec.lower().exit());
            var linked=level.getBlockEntity(input);boolean selector=false;
            if(linked!=null&&level.getBlockState(input).is(MovingElevators.button_block)
                    &&level.getBlockState(input.above()).is(MovingElevators.display_block))
            {
                var data=linked.saveWithoutMetadata().getCompound("data");
                var controller=controllerPosition(spec,spec.lower());
                selector=data.contains("controllerX")&&data.contains("controllerY")&&data.contains("controllerZ")
                        &&data.getInt("controllerX")==controller.getX()&&data.getInt("controllerZ")==controller.getZ()
                        &&spec.stops().stream().anyMatch(s->controllerPosition(spec,s).getY()==data.getInt("controllerY"));
            }
            boolean interior=missing.size()==1&&Math.abs(missing.get(0).getX()-landing.cabinCentre().getX())<radius
                    &&Math.abs(missing.get(0).getZ()-landing.cabinCentre().getZ())<radius;
            boolean doorway=floorRepairDoorwayClear(level,spec,landing,radius);
            if(roof&&selector)identifiedCars++;
            boolean damaged=!missing.isEmpty()||foreign;
            if(!damaged)
            {
                if(selector&&(!roof||!doorway))unsafe=true;
                continue;
            }
            // Even an unlinked/blocked nearly intact body must not fall into
            // the old whole-shaft normalization and be silently rebuilt.
            if(materials.values().stream().mapToInt(Integer::intValue).sum()>area/2
                    &&!TvLiftFinishR45.mayRepairSingleInteriorFloorHole(missing.size(),roof,selector,doorway,foreign,interior))
                unsafe=true;
            if(materials.isEmpty()||!TvLiftFinishR45.mayRepairSingleInteriorFloorHole(missing.size(),roof,selector,
                    doorway,foreign,interior))continue;
            var floor=materials.entrySet().stream().max(java.util.Map.Entry.comparingByValue()).orElseThrow().getKey();
            repairCells.addAll(missing);repairMaterial=floor;
        }
        if(unsafe||!repairCells.isEmpty()&&(identifiedCars!=1||repairCells.size()!=1))return false;
        if(!repairCells.isEmpty())
        {
            level.setBlock(repairCells.get(0),repairMaterial,Block.UPDATE_ALL);
            ProjectSeele.LOGGER.info("Repaired exactly one independent interior floor hole in native lift {} at {}; original cabin/hardware retained",spec.id(),repairCells.get(0));
        }
        return true;
    }

    private static boolean floorRepairDoorwayClear(ServerLevel level,S20PhysicalElevatorDirector.LiftSpec spec,
            S20PhysicalElevatorDirector.Landing landing,int radius)
    {
        for(var exit:spec.stops().stream().map(S20PhysicalElevatorDirector.Landing::exit).distinct().toList())
            // Unused opposite car leaves stay closed against the shaft wall;
            // only this floor's declared exit has a public landing throat.
            for(int distance=radius;distance<=(exit==landing.exit()?4:radius);distance++)for(int across=-1;across<=1;across++)for(int dy=0;dy<3;dy++)
            {
                var at=landing.cabinCentre().relative(exit,distance).relative(exit.getClockWise(),across).above(dy);
                var state=level.getBlockState(at);
                boolean doorCell=distance==radius||distance==4;
                if(!state.isAir()&&!(doorCell&&(state.is(Blocks.LIGHT_GRAY_STAINED_GLASS)
                        ||state.is(Blocks.GRAY_STAINED_GLASS)||state.is(com.projectseele.registry.ModBlocks.CLEAR_GLASS.get())
                        ||distance==4&&state.is(Blocks.BARRIER))))return false;
            }
        return true;
    }

    /**
     * Clears only the exact moving-cage prism from the lowest capture floor to
     * the highest capture roof.  This removes old cars, obsolete in-shaft
     * buttons and the polished-deepslate plugs which produced the repeated
     * obstruction at (10,-445,251), without touching the shaft walls or any
     * corridor outside the five-by-five owner volume.
     */
    private static void clearShaftInterior(
            ServerLevel level, ElevatorGroup group,
            S20PhysicalElevatorDirector.LiftSpec spec)
    {
        int minWalkY = spec.stops().stream()
                .mapToInt(S20PhysicalElevatorDirector.Landing::walkY)
                .min().orElseThrow();
        int maxWalkY = spec.stops().stream()
                .mapToInt(S20PhysicalElevatorDirector.Landing::walkY)
                .max().orElseThrow();
        BlockPos anchor = group.getCageAnchorBlockPos(minWalkY);
        int minY = anchor.getY();
        int maxY = group.getCageAnchorBlockPos(maxWalkY).getY()
                + group.getCageSizeY() - 1;
        for (int dx = 0; dx < group.getCageSizeX(); dx++)
        {
            for (int dz = 0; dz < group.getCageSizeZ(); dz++)
            {
                for (int y = minY; y <= maxY; y++)
                {
                    BlockPos position = new BlockPos(
                            anchor.getX() + dx, y, anchor.getZ() + dz);
                    if (!level.getBlockState(position).isAir())
                    {
                        level.setBlock(position,
                                Blocks.AIR.defaultBlockState(), UPDATE);
                    }
                }
            }
        }
    }

    private static void buildCanonicalCage(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec,
            ElevatorGroup group,
            S20PhysicalElevatorDirector.Landing source)
    {
        BlockPos centre = source.cabinCentre();
        BlockPos anchor = group.getCageAnchorBlockPos(source.walkY());
        Set<Direction> exits = new HashSet<>();
        for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
        {
            exits.add(landing.exit());
        }
        for (int dx = 0; dx < group.getCageSizeX(); dx++)
        {
            for (int dy = 0; dy < group.getCageSizeY(); dy++)
            {
                for (int dz = 0; dz < group.getCageSizeZ(); dz++)
                {
                    BlockPos position = anchor.offset(dx, dy, dz);
                    BlockState state = Blocks.AIR.defaultBlockState();
                    if (dy == 0)
                    {
                        state = Blocks.POLISHED_DEEPSLATE.defaultBlockState();
                    }
                    else if (dy == group.getCageSizeY() - 1)
                    {
                        state = TvLiftFinishR45.cabinRoof(level,spec,Blocks.SMOOTH_QUARTZ.defaultBlockState());
                    }
                    else if (dx == 0 || dz == 0
                            || dx == group.getCageSizeX() - 1
                            || dz == group.getCageSizeZ() - 1)
                    {
                        if (spec.id().equals(S20PhysicalElevatorDirector
                                .COMPACT_CAGE_LIFT_ID))
                        {
                            state = com.projectseele.registry.ModBlocks
                                    .CLEAR_GLASS.get().defaultBlockState();
                        }
                        else
                        {
                            state = isCabinDoorCell(position, centre, exits)
                                    ? Blocks.LIGHT_GRAY_STAINED_GLASS
                                            .defaultBlockState()
                                    : Blocks.IRON_BLOCK.defaultBlockState();
                        }
                        if(!isCabinDoorCell(position,centre,exits))
                            state=TvLiftFinishR45.cabinWall(level,spec,dy-1,state);
                    }
                    level.setBlock(position, state, UPDATE);
                }
            }
        }

        if (spec.id().equals(
                S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID))
        {
            /*
             * The retained compact car is otherwise transparent on all four
             * sides.  Give its selector one real, opaque 3x4 console wall so
             * the moving clear-glass shell cannot depth-fight the display.
             * North/south remain the two approved doors.
             */
            Direction exit = spec.lower().exit();
            Direction side = cabinPanelSide(spec, exit);
            BlockPos wallCentre = centre.relative(side,
                    CAGE_HORIZONTAL / 2);
            for (int across = -1; across <= 1; across++)
            {
                for (int dy = 0; dy <= 3; dy++)
                {
                    level.setBlock(wallCentre.relative(exit, across)
                                    .above(dy),
                            Blocks.BLACK_CONCRETE.defaultBlockState(),
                            UPDATE);
                }
            }
        }
    }

    private static boolean isCabinDoorCell(
            BlockPos position, BlockPos centre, Set<Direction> exits)
    {
        int dy = position.getY() - centre.getY();
        if (dy < 0 || dy > 2)
        {
            return false;
        }
        for (Direction exit : exits)
        {
            int forward = (position.getX() - centre.getX()) * exit.getStepX()
                    + (position.getZ() - centre.getZ()) * exit.getStepZ();
            int lateral = Math.abs((position.getX() - centre.getX())
                    * exit.getStepZ() - (position.getZ() - centre.getZ())
                    * exit.getStepX());
            if (forward > 0 && lateral <= 1)
            {
                return true;
            }
        }
        return false;
    }

    private static boolean isSecureLift(
            S20PhysicalElevatorDirector.LiftSpec spec)
    {
        return spec.id().equals(
                S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID)
                || spec.id().equals(
                S20PhysicalElevatorDirector.CENTRAL_DOGMA_LIFT_ID)
                || spec.id().equals(
                S20PhysicalElevatorDirector.COMMANDER_OFFICE_LIFT_ID);
    }

    private static boolean restrictedLanding(
            S20PhysicalElevatorDirector.LiftSpec spec,
            S20PhysicalElevatorDirector.Landing landing)
    {
        // Access policy follows the registered lift/stop identity, never its
        // translated display name.
        return (spec.id().equals(S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID)
                ||spec.id().equals(S20PhysicalElevatorDirector.CENTRAL_DOGMA_LIFT_ID))
                &&landing.walkY()==spec.lower().walkY()
                || spec.id().equals(
                S20PhysicalElevatorDirector.COMMANDER_OFFICE_LIFT_ID)
                && landing.equals(spec.upper());
    }

    private static boolean accessUnlocked(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec)
    {
        return ACCESS_UNTIL.getOrDefault(accessKey(level, spec), 0L)
                >= level.getGameTime();
    }

    private static boolean hasHighestClearanceCard(Player player)
    {
        return player != null && (player.getMainHandItem().is(
                ModItems.TERMINAL_DOGMA_ACCESS_CARD.get())
                || player.getOffhandItem().is(
                ModItems.TERMINAL_DOGMA_ACCESS_CARD.get()));
    }

    private static boolean localLandingEgress(Player player,
            S20PhysicalElevatorDirector.Landing landing)
    {
        return player != null && Math.abs(player.getY() - landing.walkY()) < 5.0D
                && player.position().distanceToSqr(Vec3.atBottomCenterOf(landing.cabinCentre())) < 144.0D;
    }

    /**
     * Checks the floor selected on the Moving Elevators display.  Ordinary
     * floors, including the downward return from Ikari's office, never need a
     * card; only entry into the named restricted destination is gated.
     */
    public static boolean allowDisplayPress(
            ElevatorGroup group, int floorLevel, int floorOffset,
            Player player)
    {
        if (!(player instanceof ServerPlayer serverPlayer)
                || !(player.level() instanceof ServerLevel level))
        {
            return true;
        }
        int targetY = floorLevel;
        if (floorOffset != 0)
        {
            int sourceIndex = group.getFloorNumber(floorLevel);
            int targetIndex = sourceIndex + floorOffset;
            if (sourceIndex < 0 || targetIndex < 0
                    || targetIndex >= group.getFloorCount())
            {
                return true;
            }
            targetY = group.getFloorYLevel(targetIndex);
        }
        for (S20PhysicalElevatorDirector.LiftSpec spec
                : S20PhysicalElevatorDirector.s20Lifts(level))
        {
            BlockPos controller = controllerPosition(spec, spec.lower());
            if (group.x != controller.getX()
                    || group.z != controller.getZ()
                    || group.facing != controllerFacing(spec))
            {
                continue;
            }
            for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
            {
                if (landing.walkY() != targetY
                        || !restrictedLanding(spec, landing))
                {
                    continue;
                }
                // The native group mixin repeats this guard after the fixed
                // call button has accepted it. Admit only the same local
                // egress request; do not open a global access window.
                if (floorOffset == 0 && localLandingEgress(player, landing))
                {
                    return true;
                }
                if (hasHighestClearanceCard(player))
                {
                    ACCESS_UNTIL.put(accessKey(level, spec),
                            level.getGameTime() + ACCESS_WINDOW_TICKS);
                }
                if (accessUnlocked(level, spec))
                {
                    return true;
                }
                serverPlayer.displayClientMessage(Component.literal(
                        "ACCESS DENIED / HIGHEST CLEARANCE REQUIRED")
                        .withStyle(ChatFormatting.RED), true);
                level.playSound(null, serverPlayer.blockPosition(),
                        SoundEvents.IRON_DOOR_CLOSE, SoundSource.BLOCKS,
                        0.8F, 0.72F);
                return false;
            }
            return true;
        }
        return true;
    }

    private static String accessKey(
            ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec)
    {
        return level.dimension().location() + ":" + spec.id();
    }

    private static boolean panelBelongsTo(
            S20PhysicalElevatorDirector.LiftSpec spec, BlockPos clicked)
    {
        Direction fixedExit = spec.lower().exit();
        for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
        {
            BlockPos wall = S20PhysicalElevatorDirector
                    .movingElevatorLandingPanelPosition(landing);
            BlockPos old = S20PhysicalElevatorDirector
                    .exteriorCallPosition(landing);
            BlockPos cabin = cabinPanelPosition(
                    spec, landing.cabinCentre(), fixedExit);
            for (int dy = 0; dy <= 2; dy++)
            {
                if (clicked.equals(wall.above(dy))
                        || clicked.equals(old.above(dy))
                        || clicked.equals(cabin.above(dy)))
                {
                    return true;
                }
            }
        }
        return false;
    }

    private static BlockPos cabinPanelPosition(
            S20PhysicalElevatorDirector.LiftSpec spec, BlockPos centre,
            Direction fixedExit)
    {
        /*
         * DisplayBlock is the selector the passenger actually presses.  The
         * dependency still requires an ElevatorInputBlockEntity immediately
         * below it, so keep that technical cell inside the wall at y+1 and
         * camouflage it as the same solid console.  Its arrow renderer is
         * suppressed by MovingElevatorPanelMixin; the car therefore exposes
         * one display face and no second button, including in the all-glass
         * compact cage.
         */
        int radius = isSurfaceLift(spec)
                ? SURFACE_CAGE_HORIZONTAL / 2 : CAGE_HORIZONTAL / 2;
        return centre.relative(cabinPanelSide(spec, fixedExit), radius)
                .above();
    }

    private static Direction cabinPanelSide(
            S20PhysicalElevatorDirector.LiftSpec spec, Direction fixedExit)
    {
        if (spec.id().equals(
                S20PhysicalElevatorDirector.OBSERVATION_HANGAR_LIFT_ID))
        {
            return Direction.EAST;
        }
        return spec.id().equals(
                S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID)
                ? fixedExit.getCounterClockWise()
                : fixedExit.getClockWise();
    }

    private static boolean unrestrictedLandingPanel(
            S20PhysicalElevatorDirector.LiftSpec spec, BlockPos clicked)
    {
        for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
        {
            if (restrictedLanding(spec, landing))
            {
                continue;
            }
            BlockPos wall = S20PhysicalElevatorDirector
                    .movingElevatorLandingPanelPosition(landing);
            BlockPos old = S20PhysicalElevatorDirector
                    .exteriorCallPosition(landing);
            for (int dy = 0; dy <= 2; dy++)
            {
                if (clicked.equals(wall.above(dy))
                        || clicked.equals(old.above(dy)))
                {
                    return true;
                }
            }
        }
        return false;
    }

    private static void bindRemote(
            ServerLevel level, BlockPos position, Direction facing,
            BlockPos controllerPos, int cabinFloorIndex)
    {
        if (!level.getBlockState(position).is(MovingElevators.button_block))
        {
            level.setBlock(position,
                    MovingElevators.button_block.defaultBlockState(), UPDATE);
        }
        BlockEntity entity = level.getBlockEntity(position);
        if (entity instanceof RemoteControllerBlockEntity remote)
        {
            BlockState controllerState = level.getBlockState(controllerPos);
            Direction controllerFacing = controllerState.hasProperty(
                    ControllerBlock.FACING)
                    ? controllerState.getValue(ControllerBlock.FACING)
                    : facing;
            /*
             * setValues() calls dataChanged().  Calling it every server tick
             * generated a continuous block-entity packet/render rebuild
             * stream around the six-stop Dogma lift.  Only publish when the
             * durable controller contract actually changed.
             */
            if (remote.getFacing() != facing
                    || !Objects.equals(remote.getControllerPos(),
                    controllerPos) || !remote.hasGroup())
            {
                remote.setValues(facing, controllerPos, controllerFacing);
            }
            /*
             * Moving Elevators recalculates these private fields only every
             * forty ticks.  A migrated selector can therefore arrive on a
             * new floor while still reporting the lower controller's Y,
             * producing "No cabin at the current floor" for every other
             * destination.  The actual cage footprint above selected this
             * exact landing, so publish that measured index immediately.
             */
            MovingElevatorRemoteAccessor accessor =
                    (MovingElevatorRemoteAccessor) remote;
            accessor.projectSeele$setInCabin(true);
            accessor.projectSeele$setCabinFloorIndex(cabinFloorIndex);
            camouflage(remote, Blocks.BLACK_CONCRETE.defaultBlockState());
        }
    }

    private static void ensureDisplays(
            ServerLevel level, BlockPos input, Direction widthDirection,
            BlockState camouflage, int nativeFloorCount)
    {
        BlockPos position = input.above();
        BlockState current = level.getBlockState(position);
        if (!current.is(MovingElevators.elevator_block))
        {
            if (!current.is(MovingElevators.display_block))
            {
                level.setBlock(position,
                        MovingElevators.display_block.defaultBlockState(), UPDATE);
            }
            BlockEntity entity = level.getBlockEntity(position);
            if (entity instanceof CamoBlockEntity camo)
            {
                camouflage(camo, camouflage);
            }
        }

        // One selector owns one display.  The former companion rendered the
        // same floor text in the same plane and produced view-dependent
        // flicker; remove it instead of maintaining a duplicate.
        BlockPos companion = wideDisplayCompanion(input, widthDirection);
        BlockState companionState = level.getBlockState(companion);
        if (companionState.is(MovingElevators.display_block)
                || companionState.is(MovingElevators.button_block)
                || companionState.getBlock() instanceof ButtonBlock)
        {
            level.setBlock(companion, Blocks.AIR.defaultBlockState(), UPDATE);
        }

        // A single official display exposes at most seven rows. The eight-
        // stop East lift lost its bottom destination at the highest landing
        // because this method unconditionally retired its second vertical
        // tile. The native two-tile category2/3 is one selector, up to15 rows;
        // it is not the coplanar companion removed above for z-fighting.
        BlockPos retiredTop = input.above(2);
        BlockState topState = level.getBlockState(retiredTop);
        if (nativeFloorCount > 7)
        {
            if (!replaceablePanelCell(topState)
                    || topState.is(MovingElevators.elevator_block))
            {
                ProjectSeele.LOGGER.error("Native {}-floor car selector has another component at {}; no foreign device overwritten",
                        nativeFloorCount, retiredTop.toShortString());
                return;
            }
            if (!topState.is(MovingElevators.display_block))
            {
                level.setBlock(retiredTop, MovingElevators.display_block.defaultBlockState(), UPDATE);
            }
            if (level.getBlockEntity(retiredTop) instanceof CamoBlockEntity camo)
            {
                camouflage(camo, camouflage);
            }
        }
        else if (topState.is(MovingElevators.display_block)
                || topState.is(MovingElevators.button_block)
                || topState.getBlock() instanceof ButtonBlock)
        {
            level.setBlock(retiredTop, Blocks.AIR.defaultBlockState(), UPDATE);
        }
    }

    private static BlockPos wideDisplayCompanion(
            BlockPos input, Direction widthDirection)
    {
        return input.above().relative(widthDirection.getOpposite());
    }

    private static boolean requiresEmptyShaftRecovery(
            S20PhysicalElevatorDirector.LiftSpec spec)
    {
        // Secure shafts may legitimately retain all commissioned controllers
        // while a broken migration has lost the one physical cage.  Leaving
        // those groups controller-only makes every floor selector report
        // "No cabin at the current floor" forever.
        return isSecureLift(spec) || spec.id().equals(
                S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID);
    }

    private static S20PhysicalElevatorDirector.Landing recoverySource(
            S20PhysicalElevatorDirector.LiftSpec spec)
    {
        if (!requiresEmptyShaftRecovery(spec))
        {
            return null;
        }
        for (S20PhysicalElevatorDirector.Landing landing : spec.stops())
        {
            if (spec.id().equals(
                    S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID)
                    && landing.walkY() == -448)
            {
                return landing;
            }
        }
        return spec.lower();
    }

    private record RemoteCall(String liftId, int stopIndex) {}

    private static void camouflage(
            CamoBlockEntity entity, BlockState state)
    {
        if (!entity.hasCamoState()
                || !entity.getCamoState().equals(state))
        {
            entity.setCamoState(state);
        }
    }
}

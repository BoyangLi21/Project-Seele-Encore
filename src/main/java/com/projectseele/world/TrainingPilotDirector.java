package com.projectseele.world;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.HashSet;
import java.util.Set;
import java.util.Optional;
import java.util.zip.CRC32;
import java.util.zip.DeflaterOutputStream;

import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.TrainingPilotEntity;
import com.projectseele.network.ServerboundEvaVideoFramePacket;
import com.projectseele.registry.ModEntities;
import com.projectseele.registry.ModFluids;
import com.projectseele.visual.GeoFrontCommands;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.tags.BlockTags;
import net.minecraft.tags.FluidTags;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;

/** Drives visible dummy boarding and a server-rendered training optical feed. */
public final class TrainingPilotDirector
{
    private static final int FEED_INTERVAL_TICKS = 40;
    // Ray-cast grid, upscaled to the transmitted frame. Four times the pixels
    // of the original 40x23 thumbnail; the cost is bounded because this only
    // runs for dummy-piloted airframes while somebody is watching a screen.
    private static final int SAMPLE_WIDTH = 40;
    private static final int SAMPLE_HEIGHT = 23;
    private static final double FEED_RANGE = 160.0D;
    private static final double TAN_HALF_FOV_X = Math.tan(Math.toRadians(35.0D));
    private static final double TAN_HALF_FOV_Y = Math.tan(Math.toRadians(22.0D));
    private static final int[] UNIT_COLOURS = {
            0xE88F26, 0x903ECD, 0xD22D34
    };
    private static final int BOARDING_STALL_TICKS = 120;
    private static final Map<Integer, Double> CLOSEST_APPROACH = new HashMap<>();
    private static final Map<Integer, Integer> STALLED_TICKS = new HashMap<>();
    private static final Map<Integer, Integer> BOARDING_LEG = new HashMap<>();
    private static final Map<Integer, List<BlockPos>> BOARDING_ROUTES =
            new HashMap<>();
    private static final Map<Integer, BlockPos> LAST_SAFE_FEET = new HashMap<>();
    private static final Set<Integer> ACTIVE_REMOTE_PILOTS = new HashSet<>();
    private static final Set<Integer> RETURNING_PILOTS = new HashSet<>();
    private static final Set<Integer> PENDING_NATIVE_PREFLIGHT_R47=new HashSet<>();
    private static java.lang.reflect.Method nativeCanUpdateMethodR47;
    private static boolean nativeCanUpdateLookupFailedR47;
    private static final net.minecraft.server.level.TicketType<net.minecraft.world.level.ChunkPos> ORIGINAL_PILOT_TICKET_R47=
            net.minecraft.server.level.TicketType.create("r47_original_pilot_route",java.util.Comparator.comparingLong(net.minecraft.world.level.ChunkPos::toLong),100);

    private TrainingPilotDirector() {}

    public static ActionResult start(ServerLevel level, int variant)
    {
        if(PilotRestroomsR47.configured(level)&&PilotRestroomsR47.plan(level,variant).isEmpty())
            return new ActionResult(false,"原驾驶员待命室元数据未接通，登机保持原位。");
        if(!parkedR45(level,variant))
            return new ActionResult(false,"机体尚未在机库停稳，请先完成回收，驾驶员保持原位。");
        boolean compactS20 = FacilityWorldPolicy.isS20Rebuild(
                level.getServer());
        /*
         * A parked S20 line releases its chunk ticket. Dispatching a dummy
         * from command therefore loads only this line before the read-only
         * readiness gate resolves its UUID. Never manufacture a replacement
         * here: the canonical entity section may still be streaming in.
         */
        if (compactS20)
        {
            /*
             * The approved S20 save deliberately freezes static world writers.
             * Its old phase receipts live in a remote marker chunk, so using
             * S20EvaPlantDirector.installed() as a runtime gate makes a healthy
             * authored cage appear unfinished whenever that chunk is unloaded.
             * Fleet UUID + loaded canonical entity are the runtime authority.
             */
            EvaLogisticsDirector.loadControlTarget(level, variant);
        }
        FacilityReadinessService.FacilityReadiness readiness =
                FacilityReadinessService.read(level,
                        FacilityReadinessService.Operation.DUMMY_DISPATCH,
                        variant);
        if (!readiness.accepted())
        {
            return new ActionResult(false,
                    readiness.faultCode() + ": " + readiness.message());
        }
        boolean modern = FacilityV2EvaRuntime.ready(level, variant);
        if (!modern && !compactS20)
        {
            EvaHangarBuilder.ensure(
                    level, RegionalFacilityLayout.evaOrigin(level));
        }
        if (!compactS20)
        {
            EvaLogisticsDirector.ensureFleet(level);
        }
        EvaUnit01Entity unit = EvaLogisticsDirector.canonicalUnit(level, variant);
        if (unit == null || !unit.isAlive())
        {
            return new ActionResult(false, label(variant) + " is not loaded.");
        }
        if(com.projectseele.entity.EvaShutdownR30.wreck(unit)||unit.getHealth()<=0
                ||com.projectseele.entity.EvaBayRepairR33.active(unit))
            return new ActionResult(false,"原机体仍有损毁或检修，驾驶员保持原位，等待真实整备完成。");
        level.getChunkAt(requestedStandby(level,variant));
        TrainingPilotEntity pilot = existingPilotR45(level,variant);
        if (pilot == null)
            return new ActionResult(false,"还没有确认驾驶员的位置，暂时不能安排登机。");
        if(RETURNING_PILOTS.contains(variant))
            return new ActionResult(false,"驾驶员正在返回待命，请等待离栓流程结束。");
        if(PilotRadioR28.occupiedUnit(pilot)==unit)
            return new ActionResult(true,"驾驶员已在对应机体内，保持现有乘坐关系。");
        if(pilot.getVehicle() instanceof EntryPlugCarrierEntity current
                &&current==EntryPlugDirector.canonical(level,variant)
                &&current.getAssignedVariant()==variant)
            return new ActionResult(true,"驾驶员已进入对应插入栓，等待机库联锁。");
        if(PilotRestroomsR47.isSeated(level,pilot)&&!PilotRestroomsR47.standUp(level,pilot))
            return new ActionResult(false,"待命室离座干点暂不可用，驾驶员保持原座位。");
        if(pilot.getVehicle()!=null)
            return new ActionResult(false,"驾驶员还在另一台设备内，请先让驾驶员返回待命。");
        pilot.setNoAi(false);pilot.setNoGravity(false);
        if(ACTIVE_REMOTE_PILOTS.contains(variant))
            return new ActionResult(true,"登机指令正在执行，驾驶员继续沿原通道行走。");
        boolean parked = EvaFleetSavedData.get(level.getServer())
                .entry(variant)
                .map(entry -> entry.phase()
                        == EvaFleetSavedData.Phase.PARKED)
                .orElse(false);
        if (parked)
        {
            EntryPlugDirector.releaseEmptyTrainingPlugAtDock(
                    level, variant, unit);
        }
        EntryPlugCarrierEntity plug = EntryPlugDirector.ensureSuspended(level,
                variant, unit);
        if (unit.getFirstPassenger() != null
                || plug != null && plug.getFirstPassenger() != null)
        {
            return new ActionResult(false, label(variant)
                    + " already has an entry-plug occupant.");
        }
        if (plug == null)
        {
            return new ActionResult(false, label(variant)
                    + " external entry plug is unavailable.");
        }
        var gateFault=openPilotRouteDoorsR47(level,pilot);
        if(gateFault.isPresent())return new ActionResult(false,gateFault.get());
        List<BlockPos> route = validatedBoardingRoute(level, variant, modern);
        if (route.isEmpty())
        {
            TvPersonnelPlatformInterlockR44.finishPilotDoorUseR46(level,pilot);
            return new ActionResult(false, label(variant)
                    + " boarding route has an unsupported anchor.");
        }
        if(!safeActualFeetR46(level,pilot.position())
                ||pilot.position().distanceToSqr(Vec3.atBottomCenterOf(route.get(0)))>2.75D*2.75D)
        {
            TvPersonnelPlatformInterlockR44.finishPilotDoorUseR46(level,pilot);
            return new ActionResult(false,"驾驶员尚未到达登机通道起点，请先返回待命。");
        }
        boolean ready=nativeCanUpdateR47(pilot);
        if(ready&&!actualNativeRouteR46(level,pilot,route))
        {
            TvPersonnelPlatformInterlockR44.finishPilotDoorUseR46(level,pilot);
            return new ActionResult(false,"登机通道还不能通过，驾驶员先在原地待命。");
        }
        BOARDING_ROUTES.put(variant, route);
        if(!ready)PENDING_NATIVE_PREFLIGHT_R47.add(variant);else PENDING_NATIVE_PREFLIGHT_R47.remove(variant);
        BOARDING_LEG.put(variant, Math.min(1, route.size() - 1));
        BlockPos start = route.get(0);
        LAST_SAFE_FEET.put(variant, start);
        pilot.assignVariant(variant);
        pilot.setNoAi(false);pilot.setNoGravity(false);
        pilot.setTrainingStage(TrainingPilotEntity.STAGE_WALKING);
        pilot.getPersistentData().putString("SeelePilotRouteR30","board");
        pilot.getPersistentData().putString("SeelePilotRouteMissionR45",AutoSortieR32.missionToken(level));
        // The operations room lies outside the wet-cage simulation distance.
        // Keep this one route resident while its synthetic pilot is active;
        // otherwise remote command makes the walking pilot freeze at spawn.
        ACTIVE_REMOTE_PILOTS.add(variant);
        RETURNING_PILOTS.remove(variant);
        ProjectSeele.LOGGER.info(
                "NERV training pilot dispatched: eva={} pilot={} start={}",
                variant, pilot.getStringUUID(), start.toShortString());
        return new ActionResult(true,ready?label(variant)+" dummy is walking to the dorsal boarding bridge."
                :"驾驶员正在落定，确认通道后继续登机。");
    }

    public static boolean parkedR45(ServerLevel level,int variant)
    {
        if(variant<0||variant>2)return false;
        return EvaFleetSavedData.get(level.getServer()).entry(variant)
                .map(entry->entry.phase()==EvaFleetSavedData.Phase.PARKED).orElse(false);
    }

    /** A missing/unloaded or duplicate NPC is never replaced by a dispatch. */
    public static TrainingPilotEntity existingPilotR45(ServerLevel level,int variant)
    {
        if(PilotRestroomsR47.configured(level))
        {
            var plan=PilotRestroomsR47.plan(level,variant);if(plan.isEmpty())return null;
            var actual=level.getEntity(plan.get().pilot());
            return actual instanceof TrainingPilotEntity pilot&&PilotRestroomsR47.original(plan.get(),pilot)?pilot:null;
        }
        var sortie=TvCampaignSavedData.get(level).sorties.get(variant);
        if(sortie!=null&&sortie.npc&&sortie.pilotR45!=null)
        {
            var actual=level.getEntity(sortie.pilotR45);
            return actual instanceof TrainingPilotEntity pilot&&pilot.isAlive()
                    &&pilot.getAssignedVariant()==variant?pilot:null;
        }
        var candidates=pilots(level).stream().filter(p->p.isAlive()&&p.getAssignedVariant()==variant).toList();
        return candidates.size()==1?candidates.get(0):null;
    }

    /** Request original known actor/route sections; never dispatch, spawn or move an actor. */
    public static void retainOriginalPilotR47(ServerLevel level,int variant)
    {
        if(variant<0||variant>2||!level.dimension().equals(GeoFrontCommands.GEOFRONT))return;
        EvaLogisticsDirector.loadControlTarget(level,variant);
        var points=new java.util.LinkedHashSet<BlockPos>();
        points.add(requestedStandby(level,variant));
        if(PilotRestroomsR47.configured(level))
        {
            var room=PilotRestroomsR47.plan(level,variant);if(room.isEmpty())return;
            room.get().route().forEach(p->points.add(BlockPos.containing(p)));
            var original=existingPilotR45(level,variant);
            if(original==null||!PilotRestroomsR47.EPOCH.equals(original.getPersistentData().getString("SeelePilotRestroomEpochR47")))
                points.add(EvaHangarBuilder.pilotStandbyPosition(RegionalFacilityLayout.evaOrigin(level),variant));
        }
        else points.addAll(TvPersonnelPlatformInterlockR44.boardingApproachR47(level,variant));
        points.add(FacilityV2EvaRuntime.ready(level,variant)?FacilityV2EvaRuntime.boardingPosition(level,variant)
                :EvaHangarBuilder.boardingPosition(RegionalFacilityLayout.evaOrigin(level),variant));
        var route=BOARDING_ROUTES.get(variant);if(route!=null)points.addAll(route);
        var sortie=TvCampaignSavedData.get(level).sorties.get(variant);
        if(sortie!=null&&sortie.pilotR45!=null
                &&level.getEntity(sortie.pilotR45) instanceof TrainingPilotEntity original
                &&original.getAssignedVariant()==variant)points.add(original.blockPosition());
        var chunks=new java.util.HashSet<net.minecraft.world.level.ChunkPos>();
        for(var point:points)chunks.add(new net.minecraft.world.level.ChunkPos(point));
        for(var chunk:chunks)
        {
            level.getChunkSource().addRegionTicket(ORIGINAL_PILOT_TICKET_R47,chunk,2,chunk);
            level.getChunkSource().getChunkFuture(chunk.x,chunk.z,net.minecraft.world.level.chunk.ChunkStatus.FULL,true);
        }
    }

    public static int stop(ServerLevel level, int variant)
    {
        int returning=0;
        for(int candidate=0;candidate<3;candidate++)
        {
            if(variant>=0&&candidate!=variant)continue;
            var pilot=existingPilotR45(level,candidate);
            if(pilot==null){ProjectSeele.LOGGER.warn("NERV original pilot return rejected: eva={} first=original_actor_unloaded_or_invalid",candidate);continue;}
            if(!parkedR45(level,candidate)){rejectPilotReturnR47(level,pilot,"stop:not_parked",null);continue;}
            var order=StaffCommandBookR24.unitOrder(level,candidate);
            if(order!=null){rejectPilotReturnR47(level,pilot,"stop:unit_order="+order,null);continue;}
            if(!beginReturnOrReset(level,pilot))continue;
            pilot.getPersistentData().remove("SeelePilotReturnRejectR47");
            AutoSortieR32.clearAutomatic(level,candidate);
            var eva=EvaLogisticsDirector.canonicalUnit(level,candidate);
            if(eva!=null)
            {
                eva.getPersistentData().putString("R43AutoMission",AutoSortieR32.missionToken(level));
                eva.getPersistentData().putBoolean("R32AutoCancelled",true);
            }
            returning++;
        }
        return returning;
    }

    public static boolean requiresRouteTicket(int variant)
    {
        return ACTIVE_REMOTE_PILOTS.contains(variant)
                || RETURNING_PILOTS.contains(variant);
    }

    public static List<TrainingPilotEntity> pilots(ServerLevel level)
    {
        PerformanceCounters.recordGlobalEntityScan();
        List<TrainingPilotEntity> result = new ArrayList<>();
        for (Entity entity : level.getAllEntities())
        {
            if (entity instanceof TrainingPilotEntity pilot && pilot.isAlive())
            {
                result.add(pilot);
            }
        }
        return result;
    }

    public static void tickPilot(TrainingPilotEntity pilot)
    {
        if (!(pilot.level() instanceof ServerLevel level)
                || !level.dimension().equals(GeoFrontCommands.GEOFRONT))
        {
            return;
        }
        int variant = pilot.getAssignedVariant();
        TvPersonnelPlatformInterlockR44.tickPilotDoorClosureR46(level,pilot);
        if(pilot.getVehicle() instanceof EntryPlugCarrierEntity savedPlug&&savedPlug.getAssignedVariant()==variant
                ||pilot.getVehicle() instanceof EvaUnit01Entity savedEva&&savedEva.getUnitVariant()==variant)
            ACTIVE_REMOTE_PILOTS.add(variant);
        if(!ACTIVE_REMOTE_PILOTS.contains(variant)&&!RETURNING_PILOTS.contains(variant))resumeSavedRouteR30(level,pilot);
        if(pilot.getVehicle()==null&&pilot.getPersistentData().getString("SeelePilotRouteR30").equals("board")
                &&!StaffPilotOrdersR25.missionContextCurrentR45(pilot.getPersistentData().getString("SeelePilotRouteMissionR45"),AutoSortieR32.missionToken(level)))
            holdRouteR45(pilot,"mission_changed");
        if (!ACTIVE_REMOTE_PILOTS.contains(variant)
                && !RETURNING_PILOTS.contains(variant))
        {
            holdAtStandby(level, pilot);
            return;
        }
        if (pilot.getVehicle() instanceof EntryPlugCarrierEntity plug)
        {
            if (plug.getAssignedVariant() != variant)
            {
                pilot.stopRiding();
                return;
            }
            pilot.setInvisible(plug.isLockedToEva());
            EvaUnit01Entity linked = plug.getLinkedEva();
            if (linked != null&&plug.isLockedToEva())
            {
                pilot.setTrainingStage(TrainingPilotEntity.STAGE_LINKED);
                if(!NervPilotCombatR30.controls(linked))
                {
                    float yaw = linked.getYRot();pilot.setYRot(yaw);pilot.setXRot(linked.getXRot());pilot.yBodyRot=yaw;pilot.yHeadRot=yaw;
                }
            }
            else
            {
                pilot.setTrainingStage(TrainingPilotEntity.STAGE_IN_PLUG);
            }
            return;
        }
        if (pilot.getVehicle() instanceof EvaUnit01Entity unit)
        {
            if (unit.getUnitVariant() != variant)
            {
                pilot.stopRiding();
                return;
            }
            pilot.setInvisible(true);
            pilot.setTrainingStage(TrainingPilotEntity.STAGE_LINKED);
            // A synthetic pilot looks where the airframe looks. The former
            // +/-34 degree sine sweep made the command-room feed pan
            // continuously, which reads as a camera fault rather than as a
            // pilot.
            if(!NervPilotCombatR30.controls(unit))
            {
                float yaw=unit.getYRot();pilot.setYRot(yaw);pilot.setXRot(unit.getXRot());pilot.yBodyRot=yaw;pilot.yHeadRot=yaw;
            }
            return;
        }

        if (RETURNING_PILOTS.contains(variant))
        {
            tickReturn(level, pilot);
            return;
        }


        pilot.setInvisible(false);
        pilot.setTrainingStage(TrainingPilotEntity.STAGE_WALKING);
        EvaUnit01Entity unit = EvaLogisticsDirector.canonicalUnit(level, variant);
        EntryPlugCarrierEntity plug = unit == null ? null
                : EntryPlugDirector.ensureSuspended(level, variant, unit);
        if (unit == null || !unit.isAlive() || unit.getFirstPassenger() != null
                || plug == null || plug.getFirstPassenger() != null)
        {
            pilot.getNavigation().stop();
            return;
        }
        List<BlockPos> route = BOARDING_ROUTES.get(variant);
        if (route == null || route.size() < 2)
        {
            parkPilot(level, pilot);
            return;
        }
        RouteStep step = tickWalkingRoute(level, pilot, route);
        if (step == RouteStep.FAILED)
        {
            holdRouteR45(pilot,"boarding_route_failed");
            return;
        }
        if (step == RouteStep.ARRIVED)
        {
            BlockPos target = route.get(route.size() - 1);
            pilot.getNavigation().stop();
            if (plug.boardPassenger(pilot))
            {
                TvPersonnelPlatformInterlockR44.finishPilotDoorUseR46(level,pilot);
                PilotRestroomsR47.closeDoorWhenClear(level,pilot);
                BOARDING_LEG.remove(variant);
                CLOSEST_APPROACH.remove(variant);
                STALLED_TICKS.remove(variant);
                LAST_SAFE_FEET.remove(variant);
                pilot.setInvisible(plug.isLockedToEva());
                pilot.setTrainingStage(TrainingPilotEntity.STAGE_IN_PLUG);
                level.playSound(null, target, SoundEvents.IRON_DOOR_CLOSE,
                        SoundSource.BLOCKS, 1.4F, 0.78F);
                ProjectSeele.LOGGER.info(
                        "NERV training pilot boarded external plug: eva={} pilot={} bridge={}",
                        variant, pilot.getStringUUID(), target.toShortString());
            }
            return;
        }
        pilot.getLookControl().setLookAt(unit, 25.0F, 25.0F);
    }

    /** Keeps one visible off-duty pilot on each EVA face-side observation deck. */
    public static void ensureStandby(ServerLevel level, int variant)
    {
        if (ACTIVE_REMOTE_PILOTS.contains(variant)
                || RETURNING_PILOTS.contains(variant))
        {
            return;
        }
        level.getChunkAt(requestedStandby(level,variant));
        TrainingPilotEntity keeper=existingPilotR45(level,variant);
        if(keeper!=null&&keeper.getVehicle()==null)holdAtStandby(level,keeper);
    }

    public static TrainingPilotEntity resetToStandby(ServerLevel level,
                                                       int variant)
    {
        if(PilotRestroomsR47.configured(level))
        {
            var original=existingPilotR45(level,variant);
            if(original!=null)beginReturnOrReset(level,original);
            return original;
        }
        BlockPos standby = requestedStandby(level, variant);
        level.getChunkAt(standby);
        if (!level.areEntitiesLoaded(net.minecraft.world.level.ChunkPos.asLong(standby)))
        {
            return null;
        }
        BlockPos safeStandby=nearestSafeFeet(level,standby);
        if(safeStandby==null)return null;
        clearRouteState(variant);
        TrainingPilotEntity keeper = null;
        for (TrainingPilotEntity pilot : pilots(level))
        {
            if (pilot.getAssignedVariant() != variant)
            {
                continue;
            }
            if (keeper == null)
            {
                keeper = pilot;
            }
            else
            {
                pilot.stopRiding();
                pilot.discard();
            }
        }
        if (keeper == null)
        {
            keeper = ModEntities.TRAINING_PILOT.get().create(level);
            if (keeper == null)
            {
                return null;
            }
            keeper.assignVariant(variant);
            if (!level.addFreshEntity(keeper))
            {
                return null;
            }
        }
        keeper.stopRiding();
        keeper.moveTo(safeStandby.getX()+.5D,safeStandby.getY(),safeStandby.getZ()+.5D,0,0);
        parkPilot(level, keeper);
        return keeper;
    }

    private static boolean beginReturnOrReset(ServerLevel level,TrainingPilotEntity pilot)
    {
        int variant=pilot.getAssignedVariant();
        if(!parkedR45(level,variant))return rejectPilotReturnR47(level,pilot,"begin:not_parked",null);
        PENDING_NATIVE_PREFLIGHT_R47.remove(variant);
        if(RETURNING_PILOTS.contains(variant))return true;
        if(PilotRestroomsR47.isSeated(level,pilot))return true;
        if(PilotRestroomsR47.configured(level)&&pilot.getVehicle()==null)
        {
            boolean boarding=ACTIVE_REMOTE_PILOTS.remove(variant);
            boolean accepted=requestRestroomReturnR47(level,pilot);
            if(!accepted&&boarding)ACTIVE_REMOTE_PILOTS.add(variant);
            return accepted;
        }
        if(pilot.getVehicle()==null){pilot.setNoAi(false);pilot.setNoGravity(false);}
        if(pilot.getVehicle()==null&&atStandbyFeetR47(level,pilot))
        {TvPersonnelPlatformInterlockR44.finishPilotDoorUseR46(level,pilot);parkPilot(level,pilot);return true;}
        var initialGate=openPilotRouteDoorsR47(level,pilot);
        if(initialGate.isPresent())return rejectPilotReturnR47(level,pilot,"begin:gate="+initialGate.get(),null);
        var outbound=BOARDING_ROUTES.get(variant);
        if(outbound==null||outbound.size()<2)
            outbound=validatedBoardingRoute(level,variant,FacilityV2EvaRuntime.ready(level,variant));
        if(outbound.size()<2)return rejectPilotReturnR47(level,pilot,"begin:no_valid_outbound_anchors",null);
        var route=new ArrayList<>(outbound);java.util.Collections.reverse(route);
        Vec3 feet=pilot.position();
        boolean acquireLower=pilot.getVehicle()==null&&commissionedLowerAcquisitionR47(level,pilot);
        if(pilot.getVehicle()!=null)
        {
            if(!(pilot.getVehicle() instanceof EntryPlugCarrierEntity plug)
                    ||plug!=EntryPlugDirector.canonical(level,variant)||plug.isLockedToEva()
                    ||!Set.of(EntryPlugCarrierEntity.STAGE_SUSPENDED,EntryPlugCarrierEntity.STAGE_OCCUPIED,
                            EntryPlugCarrierEntity.STAGE_ABORT_DOCKED).contains(plug.getInsertionStage()))return rejectPilotReturnR47(level,pilot,"begin:vehicle_not_safe_original_docked_plug",null);
            feet=plug.getDismountLocationForPassenger(pilot);
        }
        int leg=nearestRouteLegR45(feet,route);
        if(leg<0&&!acquireLower)return rejectPilotReturnR47(level,pilot,"begin:dismount_outside_declared_route feet="+feet,null);
        if(!safeActualFeetR46(level,feet))return rejectPilotReturnR47(level,pilot,"begin:unsupported_or_body_blocked_dismount feet="+feet,BlockPos.containing(feet));
        var gateFault=openPilotRouteDoorsR47(level,pilot);
        if(gateFault.isPresent())return rejectPilotReturnR47(level,pilot,"begin:gate="+gateFault.get(),null);
        // The real capsule chooses its safe dismount; no route-start teleport.
        if(pilot.getVehicle()!=null)pilot.stopRiding();
        if(!safeActualFeetR46(level,pilot.position())){holdRouteR45(pilot,"dismount_not_on_catwalk");return false;}
        leg=acquireLower?acquireLowerRouteLegR47(level,pilot,route):nearestRouteLegR45(pilot.position(),route);
        if(leg<0){holdRouteR45(pilot,acquireLower?"lower_floor_no_native_acquisition":"dismount_outside_return_route");return false;}
        pilot.getNavigation().stop();pilot.setInvisible(false);
        pilot.setTrainingStage(TrainingPilotEntity.STAGE_WALKING);
        ACTIVE_REMOTE_PILOTS.remove(variant);RETURNING_PILOTS.add(variant);
        pilot.getPersistentData().putString("SeelePilotRouteR30","return");
        pilot.getPersistentData().remove("SeelePilotRouteMissionR45");
        BOARDING_ROUTES.put(variant,List.copyOf(route));BOARDING_LEG.put(variant,leg);
        saveRestroomReturnRouteR47(level,pilot,route);
        if(PilotRestroomsR47.configured(level))PENDING_NATIVE_PREFLIGHT_R47.add(variant);
        LAST_SAFE_FEET.put(variant,pilot.blockPosition());CLOSEST_APPROACH.remove(variant);STALLED_TICKS.remove(variant);
        ProjectSeele.LOGGER.info("NERV original pilot returning without reset: eva={} pilot={} at={} leg={}",variant,pilot.getStringUUID(),pilot.blockPosition(),leg);
        return true;
    }

    private static Optional<String> openPilotRouteDoorsR47(ServerLevel level,TrainingPilotEntity pilot)
    {
        return PilotRestroomsR47.configured(level)?PilotRestroomsR47.openDoor(level,pilot)
                :TvPersonnelPlatformInterlockR44.openForOriginalBoardingPilotR46(level,pilot);
    }

    private static boolean rejectPilotReturnR47(ServerLevel level,TrainingPilotEntity pilot,String reason,BlockPos node)
    {
        String detail="first="+reason+" uuid="+pilot.getStringUUID()+" actualFeet="+pilot.position()
                +" stage="+pilot.getTrainingStage()+" route="+pilot.getPersistentData().getString("SeelePilotRouteR30")
                +" parked="+parkedR45(level,pilot.getAssignedVariant())+" actualFootSupport="+safeActualFeetR46(level,pilot.position());
        if(node!=null)detail+=" node="+node+" declaredFoot="+safeFeetPositionR47(level,node)
                +" nativeFoot="+nativeNodeFeetR47(level,node)+" nativeAbove="+nativeNodeFeetR47(level,node.above())
                +" block="+level.getBlockState(node)+" below="+level.getBlockState(node.below())+" head="+level.getBlockState(node.above());
        if(!detail.equals(pilot.getPersistentData().getString("SeelePilotReturnRejectR47")))
            ProjectSeele.LOGGER.warn("NERV original pilot return rejected: {}",detail);
        pilot.getPersistentData().putString("SeelePilotReturnRejectR47",detail);return false;
    }

    public static boolean requestRestroomReturnR47(ServerLevel level,TrainingPilotEntity pilot)
    {
        int v=pilot.getAssignedVariant();var optional=PilotRestroomsR47.plan(level,v);
        if(optional.isEmpty())return rejectPilotReturnR47(level,pilot,"room:metadata_plan_absent",null);
        if(!PilotRestroomsR47.original(optional.get(),pilot))return rejectPilotReturnR47(level,pilot,"room:foreign_or_dead_actor",null);
        if(!parkedR45(level,v))return rejectPilotReturnR47(level,pilot,"room:not_parked",null);
        if(pilot.getVehicle()!=null)return rejectPilotReturnR47(level,pilot,"room:actor_still_passenger",null);
        if(ACTIVE_REMOTE_PILOTS.contains(v))return rejectPilotReturnR47(level,pilot,"room:active_dispatch",null);
        if(RETURNING_PILOTS.contains(v))return rejectPilotReturnR47(level,pilot,"room:return_already_active",null);
        if(!safeActualFeetR46(level,pilot.position()))return rejectPilotReturnR47(level,pilot,"room:actual_sole_or_body_not_safe",pilot.blockPosition());
        var p=optional.get();if(PilotRestroomsR47.atStand(level,p,pilot)){parkPilot(level,pilot);return true;}
        var roomGate=openPilotRouteDoorsR47(level,pilot);
        if(roomGate.isPresent())return rejectPilotReturnR47(level,pilot,"room:gate="+roomGate.get(),p.doorLower());
        var route=new ArrayList<BlockPos>();
        route.add(new BlockPos(Mth.floor(pilot.getX()),Mth.ceil(pilot.getY()-1e-7),Mth.floor(pilot.getZ())));
        if(!PilotRestroomsR47.EPOCH.equals(pilot.getPersistentData().getString("SeelePilotRestroomEpochR47"))
                &&pilot.getZ() < -240)
        {
            // The one initial reassignment starts at the original front post.
            // Include its measured side aisle/ramp in both the physical course
            // and the bounded search domain; the room-only box cannot reach it.
            var original=TvPersonnelPlatformInterlockR44.boardingApproachR47(level,v);
            if(original.isEmpty())return rejectPilotReturnR47(level,pilot,"migration:original_approach_absent",null);
            var gate=TvPersonnelPlatformInterlockR44.openForOriginalBoardingPilotR46(level,pilot);
            if(gate.isPresent())return rejectPilotReturnR47(level,pilot,"migration:original_gate="+gate.get(),null);
            for(BlockPos q:original)
            {
                // The metadata reader floors fractional quarter soles. Query
                // the same measured column's two possible native ceilings;
                // both retain complete real support/body/liquid predicates.
                Vec3 sole=nativeNodeFeetR47(level,q);
                if(sole==null)sole=nativeNodeFeetR47(level,q.above());
                if(sole==null)return rejectPilotReturnR47(level,pilot,"migration:original_approach_no_native_sole",q);
                var nativeFoot=new BlockPos(q.getX(),Mth.ceil(sole.y-1e-7),q.getZ());
                if(!route.get(route.size()-1).equals(nativeFoot))route.add(nativeFoot);
            }
        }
        if(!route.get(route.size()-1).equals(p.goal()))route.add(p.goal());
        var reversed=new ArrayList<>(p.route());java.util.Collections.reverse(reversed);
        for(Vec3 point:reversed)
        {
            BlockPos q=new BlockPos(Mth.floor(point.x),Mth.ceil(point.y-1e-7),Mth.floor(point.z));
            if(!route.get(route.size()-1).equals(q))route.add(q);
        }
        for(BlockPos q:route)if(nativeNodeFeetR47(level,q)==null)return rejectPilotReturnR47(level,pilot,"room:final_course_no_native_sole",q);
        pilot.getNavigation().stop();pilot.setNoAi(false);pilot.setNoGravity(false);pilot.setInvisible(false);
        pilot.setTrainingStage(TrainingPilotEntity.STAGE_WALKING);RETURNING_PILOTS.add(v);ACTIVE_REMOTE_PILOTS.remove(v);
        BOARDING_ROUTES.put(v,List.copyOf(route));BOARDING_LEG.put(v,1);
        PENDING_NATIVE_PREFLIGHT_R47.add(v);LAST_SAFE_FEET.put(v,pilot.blockPosition());CLOSEST_APPROACH.remove(v);STALLED_TICKS.remove(v);
        pilot.getPersistentData().putString("SeelePilotRouteR30","return");
        saveRestroomReturnRouteR47(level,pilot,route);
        pilot.getPersistentData().remove("SeelePilotReturnRejectR47");
        ProjectSeele.LOGGER.info("NERV original pilot assigned normal room return: uuid={} room={} from={} stand={}",pilot.getStringUUID(),p.id(),pilot.position(),p.stand());
        return true;
    }

    private static void saveRestroomReturnRouteR47(ServerLevel level,TrainingPilotEntity pilot,List<BlockPos> route)
    {
        if(!PilotRestroomsR47.configured(level))return;
        var rows=new net.minecraft.nbt.ListTag();
        for(BlockPos q:route)rows.add(new net.minecraft.nbt.IntArrayTag(new int[]{q.getX(),q.getY(),q.getZ()}));
        pilot.getPersistentData().put("SeelePilotRestroomReturnRouteR47",rows);
        pilot.getPersistentData().putString("SeelePilotRestroomReturnEpochR47",PilotRestroomsR47.EPOCH);
    }

    private static List<BlockPos> savedRestroomReturnRouteR47(ServerLevel level,TrainingPilotEntity pilot)
    {
        var plan=PilotRestroomsR47.plan(level,pilot.getAssignedVariant());var data=pilot.getPersistentData();
        if(plan.isEmpty()||!PilotRestroomsR47.original(plan.get(),pilot)
                ||!PilotRestroomsR47.EPOCH.equals(data.getString("SeelePilotRestroomReturnEpochR47")))return List.of();
        var rows=data.getList("SeelePilotRestroomReturnRouteR47",net.minecraft.nbt.Tag.TAG_INT_ARRAY);
        if(rows.size()<2||rows.size()>32)return List.of();
        var route=new ArrayList<BlockPos>();int offset=42*pilot.getAssignedVariant();
        for(var row:rows)
        {
            int[] xyz=((net.minecraft.nbt.IntArrayTag)row).getAsIntArray();if(xyz.length!=3)return List.of();
            var q=new BlockPos(xyz[0],xyz[1],xyz[2]);
            if(q.getX() < -35+offset||q.getX()>10+offset||q.getY() < -394||q.getY()>-390
                    ||q.getZ() < -273||q.getZ()>-216||nativeNodeFeetR47(level,q)==null)return List.of();
            route.add(q);
        }
        return route.get(route.size()-1).equals(BlockPos.containing(plan.get().stand()))?List.copyOf(route):List.of();
    }

    private static boolean commissionedLowerAcquisitionR47(ServerLevel level,TrainingPilotEntity pilot)
    {
        int variant=pilot.getAssignedVariant();
        if(FacilityV2EvaRuntime.ready(level,variant)||!pilot.onGround()
                ||!safeActualFeetR46(level,pilot.position()))return false;
        List<BlockPos> declared=TvPersonnelPlatformInterlockR44.boardingApproachR47(level,variant);
        if(declared.isEmpty())return false;
        Vec3 lower=safeFeetPositionR47(level,requestedStandby(level,variant));
        if(lower==null||Math.abs(pilot.getY()-lower.y)>.08)return false;
        // This is the original commissioned cage/entrance, not an invitation
        // to acquire a route from arbitrary lower floors across the facility.
        BlockPos dock=EvaHangarBuilder.boardingPosition(RegionalFacilityLayout.evaOrigin(level),variant);
        if(pilot.position().distanceToSqr(Vec3.atBottomCenterOf(dock))<=9.0D*9.0D)return true;
        for(BlockPos entry:declared)
        {
            Vec3 sole=safeFeetPositionR47(level,entry);
            if(sole!=null&&Math.abs(sole.y-lower.y)<=.08
                    &&pilot.position().distanceToSqr(sole)<=2.75D*2.75D)return true;
        }
        return false;
    }

    private static int acquireLowerRouteLegR47(ServerLevel level,TrainingPilotEntity pilot,List<BlockPos> reverseRoute)
    {
        List<BlockPos> declared=TvPersonnelPlatformInterlockR44.boardingApproachR47(level,pilot.getAssignedVariant());
        if(reverseRoute.size()!=declared.size()+2)return -1;
        var candidates=new ArrayList<Integer>();
        for(int sourceIndex=0;sourceIndex<declared.size();sourceIndex++)
        {
            int originalIndex=reverseRoute.size()-2-sourceIndex;
            Vec3 sole=nativeNodeFeetR47(level,reverseRoute.get(originalIndex));
            Vec3 commissioned=safeFeetPositionR47(level,declared.get(sourceIndex));
            if(sole!=null&&commissioned!=null&&Math.abs(sole.y-pilot.getY())<=.08
                    &&Math.abs(commissioned.y-pilot.getY())<=.08
                    &&sole.distanceToSqr(commissioned)<=2.75D*2.75D
                    &&sole.distanceToSqr(pilot.position())<=96.0D*96.0D)candidates.add(originalIndex);
        }
        candidates.sort(java.util.Comparator.comparingDouble(i->
                pilot.position().distanceToSqr(Vec3.atBottomCenterOf(reverseRoute.get(i)))));
        String firstFailure=null;
        for(int index:candidates)
        {
            BlockPos target=reverseRoute.get(index);
            var path=createPilotDeclaredPathR47(pilot,reverseRoute,target);
            boolean complete=path!=null&&path.canReach();
            if(complete)for(int n=0;n<path.getNodeCount();n++)
            {
                var node=path.getNode(n);
                if(nativeNodeFeetR47(level,new BlockPos(node.x,node.y,node.z))==null){complete=false;break;}
            }
            if(!complete)
            {
                if(firstFailure==null)firstFailure=attemptedPathTraceR47(level,pilot,path,target);
                continue;
            }
            String acquisition="originalIndex="+index+" target="+target+" sole="+nativeNodeFeetR47(level,target)
                    +" nodes="+path.getNodeCount()+" from="+pilot.position();
            pilot.getPersistentData().putString("SeelePilotLowerAcquisitionR47",acquisition);
            ProjectSeele.LOGGER.info("NERV original pilot acquiring commissioned lower entrance: eva={} uuid={} {}",
                    pilot.getAssignedVariant(),pilot.getStringUUID(),acquisition);
            return index;
        }
        ProjectSeele.LOGGER.warn("NERV original pilot lower acquisition unavailable: eva={} uuid={} candidates={} firstFailure={}",
                pilot.getAssignedVariant(),pilot.getStringUUID(),candidates.size(),firstFailure);
        return -1;
    }

    private static int nearestRouteLegR45(Vec3 point,List<BlockPos> route)
    {
        int leg=-1;double best=36.0D;
        for(int i=1;i<route.size();i++)
        {
            Vec3 a=Vec3.atBottomCenterOf(route.get(i-1)),b=Vec3.atBottomCenterOf(route.get(i)),ab=b.subtract(a);
            double t=ab.lengthSqr()<1e-8?1:Mth.clamp(point.subtract(a).dot(ab)/ab.lengthSqr(),0,1);
            double distance=point.distanceToSqr(a.add(ab.scale(t)));
            if(distance<=best){best=distance;leg=i;}
        }
        return leg;
    }

    private static void holdRouteR45(TrainingPilotEntity pilot,String reason)
    {
        if(pilot.level() instanceof ServerLevel actual)
            pilot.getPersistentData().putString("SeelePilotLastRouteFaultR47",reason+" "+routeTraceR47(actual,pilot));
        if(pilot.level() instanceof ServerLevel level)TvPersonnelPlatformInterlockR44.finishPilotDoorUseR46(level,pilot);
        clearRouteState(pilot.getAssignedVariant());pilot.getNavigation().stop();
        pilot.getPersistentData().putString("SeelePilotRouteR30","hold");
        pilot.setInvisible(false);pilot.setTrainingStage(TrainingPilotEntity.STAGE_STANDBY);
        ProjectSeele.LOGGER.warn("NERV original pilot route held in place: eva={} pilot={} at={} reason={}",pilot.getAssignedVariant(),pilot.getStringUUID(),pilot.blockPosition(),reason);
    }

    private static void tickReturn(ServerLevel level,
                                   TrainingPilotEntity pilot)
    {
        int variant = pilot.getAssignedVariant();
        pilot.setInvisible(false);
        pilot.setTrainingStage(TrainingPilotEntity.STAGE_WALKING);
        List<BlockPos> route = BOARDING_ROUTES.get(variant);
        if (route == null || route.size() < 2)
        {
            parkPilot(level, pilot);
            return;
        }
        RouteStep step = tickWalkingRoute(level, pilot, route);
        if(step==RouteStep.ARRIVED)
        {
            TvPersonnelPlatformInterlockR44.finishPilotDoorUseR46(level,pilot);
            parkPilot(level,pilot);
        }
        else if(step==RouteStep.FAILED)holdRouteR45(pilot,"return_route_failed");
    }

    private static RouteStep tickWalkingRoute(ServerLevel level,
                                               TrainingPilotEntity pilot,
                                               List<BlockPos> route)
    {
        // Older display-only pilots can carry NoAI in their saved entity data.
        // A real boarding/return order must restore native navigation and gravity.
        pilot.setNoAi(false);pilot.setNoGravity(false);
        int variant = pilot.getAssignedVariant();
        BlockPos finalTarget = route.get(route.size() - 1);
        Vec3 finalFeet = safeFeetPositionR47(level, finalTarget);
        if (finalFeet != null && !PENDING_NATIVE_PREFLIGHT_R47.contains(variant)
                && nativeCanUpdateR47(pilot)&&safeActualFeetR46(level,pilot.position())
                && pilot.position().multiply(1,0,1)
                .distanceToSqr(finalFeet.multiply(1,0,1)) <= .65D * .65D
                && Math.abs(pilot.getY()-finalFeet.y) <= .45D)
        {
            return RouteStep.ARRIVED;
        }

        int leg = Mth.clamp(BOARDING_LEG.getOrDefault(variant, 1),
                1, route.size() - 1);
        int previousLeg = leg;
        while (leg < route.size() - 1
                && pilot.position().distanceToSqr(
                Vec3.atBottomCenterOf(route.get(leg))) <= 2.0D * 2.0D)
        {
            leg++;
        }
        BOARDING_LEG.put(variant, leg);
        if (leg != previousLeg)
        {
            CLOSEST_APPROACH.remove(variant);
            STALLED_TICKS.remove(variant);
        }

        BlockPos routeTarget = route.get(leg);
        Vec3 destination = safeFeetPositionR47(level,routeTarget);
        if(destination==null)return RouteStep.FAILED;
        BlockPos feet = pilot.blockPosition();
        if (pilot.onGround() && safeActualFeetR46(level,pilot.position()))
        {
            LAST_SAFE_FEET.put(variant, feet.immutable());
        }
        BlockPos lastSafe = LAST_SAFE_FEET.get(variant);
        boolean submerged = pilot.isInWater()
                || pilot.level().getFluidState(feet)
                        .getFluidType() == ModFluids.LCL_TYPE.get();
        boolean fallen = pilot.fallDistance > 2.0F
                || lastSafe != null && pilot.getY() < lastSafe.getY() - 2.0D;
        if (submerged || fallen)
        {
            ProjectSeele.LOGGER.warn(
                    "NERV dummy route abandoned after fall: eva={} at={} leg={}",
                    variant, feet.toShortString(), leg);
            return RouteStep.FAILED;
        }

        // GroundPathNavigation deliberately returns null while the restored
        // real actor is falling/jumping. Null then is not an unreachable floor.
        // Keep gravity/real route/own gates; never reset position or OnGround.
        if(!nativeCanUpdateR47(pilot))
        {
            if(pilot.getNavigation().getPath()!=null)
                pilot.getPersistentData().putString("SeelePilotLastAirPathR47",routeTraceR47(level,pilot));
            // An old path otherwise keeps issuing MOVE_TO/JUMP while this
            // planner cannot refresh it. Stop that path, then let real gravity
            // land the actor before normal replanning; no velocity/pose reset.
            pilot.getNavigation().stop();
            int waiting=STALLED_TICKS.merge(variant,1,Integer::sum);
            if(waiting==1)ProjectSeele.LOGGER.info("NERV original pilot awaiting native landing: {}",routeTraceR47(level,pilot));
            if(waiting>=BOARDING_STALL_TICKS)
            {ProjectSeele.LOGGER.warn("NERV original pilot native landing timed out: {}",routeTraceR47(level,pilot));return RouteStep.FAILED;}
            return RouteStep.MOVING;
        }
        if(PENDING_NATIVE_PREFLIGHT_R47.remove(variant)&&!actualNativeRouteR46(level,pilot,route))
            return RouteStep.FAILED;

        if (leg != previousLeg || pilot.tickCount % 20 == 1 || pilot.getNavigation().isDone())
        {
            var path=createPilotDeclaredPathR47(pilot,route,routeTarget);
            if(path==null||!path.canReach())
            {
                pilot.getPersistentData().putString("SeelePilotNativePathFailureR47",routeTraceR47(level,pilot)
                        +" "+attemptedPathTraceR47(level,pilot,path,routeTarget));
                ProjectSeele.LOGGER.warn("NERV original pilot native path cannot reach: eva={} from={} leg={} {}",
                        variant,pilot.position(),leg,attemptedPathTraceR47(level,pilot,path,routeTarget));
                return RouteStep.FAILED;
            }
            pilot.getNavigation().moveTo(path,1.05D);
        }
        // A valid path around a railing can initially move away from the
        // final waypoint. Remaining native-path length measures real progress.
        double remaining = remainingNativePathR47(pilot,destination);
        Double best = CLOSEST_APPROACH.get(variant);
        if (best == null || remaining < best - 0.05D)
        {
            CLOSEST_APPROACH.put(variant, remaining);
            STALLED_TICKS.put(variant, 0);
        }
        else if (STALLED_TICKS.merge(variant, 1, Integer::sum)
                >= BOARDING_STALL_TICKS)
        {
            ProjectSeele.LOGGER.warn(
                    "NERV dummy route abandoned after stall: eva={} at={} leg={} target={}",
                    variant, feet.toShortString(), leg,
                    routeTarget.toShortString());
            return RouteStep.FAILED;
        }
        return RouteStep.MOVING;
    }

    private static double remainingNativePathR47(TrainingPilotEntity pilot,Vec3 destination)
    {
        var path=pilot.getNavigation().getPath();
        if(path==null||path.isDone())return pilot.position().distanceTo(destination);
        Vec3 cursor=pilot.position();double metres=0;
        for(int i=path.getNextNodeIndex();i<path.getNodeCount();i++)
        {
            Vec3 next=path.getEntityPosAtNode(pilot,i);metres+=cursor.distanceTo(next);cursor=next;
        }
        return metres;
    }

    /** Actual protected native readiness, resolved by its stable abstract ABI. */
    private static boolean nativeCanUpdateR47(TrainingPilotEntity pilot)
    {
        if(!nativeCanUpdateLookupFailedR47)
        {
            try
            {
                if(nativeCanUpdateMethodR47==null)
                {
                    for(var method:net.minecraft.world.entity.ai.navigation.PathNavigation.class.getDeclaredMethods())
                        if(java.lang.reflect.Modifier.isAbstract(method.getModifiers())&&method.getParameterCount()==0&&method.getReturnType()==boolean.class)
                        {if(nativeCanUpdateMethodR47!=null)throw new IllegalStateException("Ambiguous native navigation readiness ABI");nativeCanUpdateMethodR47=method;}
                    if(nativeCanUpdateMethodR47==null)throw new IllegalStateException("Native navigation readiness ABI absent");
                    nativeCanUpdateMethodR47.setAccessible(true);
                }
                return (boolean)nativeCanUpdateMethodR47.invoke(pilot.getNavigation());
            }
            catch(Exception failure)
            {nativeCanUpdateLookupFailedR47=true;ProjectSeele.LOGGER.warn("Native navigation readiness unavailable; retained vanilla ground predicate: {}",failure.toString());}
        }
        return !(pilot.getNavigation() instanceof net.minecraft.world.entity.ai.navigation.GroundPathNavigation)
                ||pilot.onGround()||pilot.isInWaterOrBubble()||pilot.isInLava()||pilot.isPassenger();
    }
    /** Normal status read only: no path creation, ticket, movement or mutation. */
    private static String attemptedPathTraceR47(ServerLevel level,TrainingPilotEntity pilot,
            net.minecraft.world.level.pathfinder.Path path,BlockPos goal)
    {
        String end="none";var polyline=new StringBuilder("[");double gridLength=0,soleLength=0;
        boolean soleComplete=true;Vec3 previousSole=null;net.minecraft.world.level.pathfinder.Node previousNode=null;
        if(path!=null)for(int i=0;i<path.getNodeCount();i++)
        {
            var node=path.getNode(i);var sole=nativeNodeFeetR47(level,new BlockPos(node.x,node.y,node.z));
            if(i>0)polyline.append(',');
            polyline.append('[').append(node.x).append(',').append(node.y).append(',').append(node.z)
                    .append(';').append(node.type).append(";walked=").append(node.walkedDistance)
                    .append(";g=").append(node.g).append(";sole=").append(sole).append(']');
            if(previousNode!=null)
            {
                double dx=node.x-previousNode.x,dy=node.y-previousNode.y,dz=node.z-previousNode.z;
                gridLength+=Math.sqrt(dx*dx+dy*dy+dz*dz);
                if(previousSole!=null&&sole!=null)soleLength+=previousSole.distanceTo(sole);else soleComplete=false;
            }
            if(sole==null)soleComplete=false;
            previousNode=node;previousSole=sole;
        }
        polyline.append(']');
        if(path!=null&&path.getNodeCount()>0)
        {
            var node=path.getNode(path.getNodeCount()-1);var at=new BlockPos(node.x,node.y,node.z);
            end="xyz="+at+" type="+node.type+" sole="+nativeNodeFeetR47(level,at)
                    +" walkedDistance="+node.walkedDistance+" g="+node.g+" h="+node.h+" f="+node.f+" costMalus="+node.costMalus
                    +" block="+level.getBlockState(at)+" below="+level.getBlockState(at.below())
                    +" head="+level.getBlockState(at.above());
        }
        return "attemptedTarget="+goal+" attemptedNodes="+(path==null?0:path.getNodeCount())
                +" attemptedCanReach="+(path!=null&&path.canReach())+" attemptedEnd={"+end+"}"
                +" goalSole="+nativeNodeFeetR47(level,goal)+" goalRawNativeType="
                +new net.minecraft.world.level.pathfinder.WalkNodeEvaluator().getBlockPathType(level,goal.getX(),goal.getY(),goal.getZ())
                +" goalBlock="+level.getBlockState(goal)+" goalBelow="+level.getBlockState(goal.below())
                +" goalHead="+level.getBlockState(goal.above())+" nativeGridPolylineLength="+gridLength
                +" realSolePolylineLength="+(soleComplete?Double.toString(soleLength):"unsupported")
                +" sameReturnedPolyline="+polyline+" search={"
                +(pilot.getNavigation() instanceof com.projectseele.entity.TrainingPilotNavigationR47 exact
                ?exact.lastSearchEvidenceR47():"other_native_navigation")+"}";
    }

    /** Normal status read only: no path creation, ticket, movement or mutation. */
    public static String routeTraceR47(ServerLevel level,TrainingPilotEntity pilot)
    {
        int v=pilot.getAssignedVariant(),leg=BOARDING_LEG.getOrDefault(v,-1);var route=BOARDING_ROUTES.get(v);
        BlockPos target=route!=null&&leg>=0&&leg<route.size()?route.get(leg):null;
        Vec3 dest=target==null?null:safeFeetPositionR47(level,target);var path=pilot.getNavigation().getPath();
        String remaining=dest==null?"none":String.format(Locale.ROOT,"%.3f",remainingNativePathR47(pilot,dest));
        String details="none";
        if(path!=null&&!path.isDone()&&path.getNextNodeIndex()<path.getNodeCount())
        {
            var node=path.getNode(path.getNextNodeIndex());var at=new BlockPos(node.x,node.y,node.z);
            details="node="+at+" type="+node.type+" nativeFoot="+path.getEntityPosAtNode(pilot,path.getNextNodeIndex())
                    +" realFoot="+safeFeetPositionR47(level,at)+" block="+level.getBlockState(at)
                    +" below="+level.getBlockState(at.below())+" head="+level.getBlockState(at.above());
        }
        String post=PilotRestroomsR47.plan(level,v).map(p->" room="+p.id()+" originalRoomActor="+PilotRestroomsR47.original(p,pilot)
                +" ownedSeat="+PilotRestroomsR47.isSeated(level,pilot)+" roomStand="+p.stand()
                +" actualAtRoomStand="+PilotRestroomsR47.atStand(level,p,pilot)).orElse(" room=unconfigured");
        String returnReject=pilot.getPersistentData().getString("SeelePilotReturnRejectR47");
        if(!returnReject.isEmpty())post+=" returnReject={"+returnReject+"}";
        return String.format(Locale.ROOT,"uuid=%s feet=(%.5f,%.5f,%.5f) onGround=%s nativeCanUpdate=%s(%s) actualFootSupport=%s route=%s leg=%d target=%s targetFoot=%s pathNodes=%d nextNode=%d pathReach=%s remaining=%s stall=%d pendingFullPreflight=%s nextDetail={%s} navigation=%s",
                pilot.getStringUUID(),pilot.getX(),pilot.getY(),pilot.getZ(),pilot.onGround(),nativeCanUpdateR47(pilot),nativeCanUpdateLookupFailedR47?"vanilla_ground_fallback":"actual_native_method",
                safeActualFeetR46(level,pilot.position()),pilot.getPersistentData().getString("SeelePilotRouteR30"),leg,target,dest,path==null?0:path.getNodeCount(),path==null?-1:path.getNextNodeIndex(),path!=null&&path.canReach(),remaining,STALLED_TICKS.getOrDefault(v,0),PENDING_NATIVE_PREFLIGHT_R47.contains(v),details,pilot.getNavigation().getClass().getSimpleName())+post;
    }

    private static void holdAtStandby(ServerLevel level,
                                      TrainingPilotEntity pilot)
    {
        if(PilotRestroomsR47.configured(level))
        {PilotRestroomsR47.holdOrArrangePost(level,pilot);return;}
        if(pilot.getVehicle()!=null)return;
        if(pilot.getPersistentData().getString("SeelePilotRouteR30").equals("hold"))
        {pilot.getNavigation().stop();return;}
        if(!atStandbyFeetR47(level,pilot))
        {holdRouteR45(pilot,"standby_not_reached");return;}
        pilot.getNavigation().stop();pilot.setDeltaMovement(Vec3.ZERO);pilot.fallDistance=0;
        pilot.setInvisible(false);pilot.setTrainingStage(TrainingPilotEntity.STAGE_STANDBY);
        pilot.setYRot(0);pilot.setXRot(0);pilot.yBodyRot=pilot.yHeadRot=0;
    }

    private static boolean atStandbyFeetR47(ServerLevel level,TrainingPilotEntity pilot)
    {
        if(PilotRestroomsR47.configured(level))
            return PilotRestroomsR47.plan(level,pilot.getAssignedVariant()).map(p->PilotRestroomsR47.atStand(level,p,pilot)).orElse(false);
        if(!safeActualFeetR46(level,pilot.position()))return false;
        Vec3 target=safeFeetPositionR47(level,requestedStandby(level,pilot.getAssignedVariant()));
        return target!=null&&Math.abs(pilot.getY()-target.y)<=.45
                &&pilot.position().multiply(1,0,1).distanceToSqr(target.multiply(1,0,1))<=.65*.65;
    }

    /** Held-in-place STANDBY is distinct from actually returning to the original post. */
    public static boolean atOriginalStandbyR47(ServerLevel level,int variant)
    {
        var pilot=existingPilotR45(level,variant);
        if(PilotRestroomsR47.configured(level))return pilot!=null&&PilotRestroomsR47.isSeated(level,pilot)
                &&pilot.getTrainingStage()==TrainingPilotEntity.STAGE_STANDBY
                &&!pilot.getPersistentData().getString("SeelePilotRouteR30").equals("hold");
        return pilot!=null&&pilot.getVehicle()==null
                &&pilot.getTrainingStage()==TrainingPilotEntity.STAGE_STANDBY
                &&!pilot.getPersistentData().getString("SeelePilotRouteR30").equals("hold")
                &&!pilot.getPersistentData().getBoolean("SeelePilotDoorClosePendingR46")
                &&atStandbyFeetR47(level,pilot);
    }

    private static void parkPilot(ServerLevel level,
                                  TrainingPilotEntity pilot)
    {
        pilot.getPersistentData().putString("SeelePilotRouteR30","standby");
        pilot.getPersistentData().remove("SeelePilotRestroomReturnRouteR47");
        pilot.getPersistentData().remove("SeelePilotRestroomReturnEpochR47");
        clearRouteState(pilot.getAssignedVariant());
        if(PilotRestroomsR47.configured(level)&&atStandbyFeetR47(level,pilot))
            pilot.setTrainingStage(TrainingPilotEntity.STAGE_STANDBY);
        holdAtStandby(level, pilot);
    }

    private static void clearRouteState(int variant)
    {
        ACTIVE_REMOTE_PILOTS.remove(variant);
        RETURNING_PILOTS.remove(variant);
        PENDING_NATIVE_PREFLIGHT_R47.remove(variant);
        BOARDING_LEG.remove(variant);
        BOARDING_ROUTES.remove(variant);
        CLOSEST_APPROACH.remove(variant);
        STALLED_TICKS.remove(variant);
        LAST_SAFE_FEET.remove(variant);
    }

    private enum RouteStep
    {
        MOVING,
        ARRIVED,
        FAILED
    }
    private static void resumeSavedRouteR30(ServerLevel level,TrainingPilotEntity pilot)
    {
        String intent=pilot.getPersistentData().getString("SeelePilotRouteR30");
        if(!intent.equals("board")&&!intent.equals("return"))return;
        if(openPilotRouteDoorsR47(level,pilot).isPresent())return;
        int variant=pilot.getAssignedVariant();
        boolean roomReturn=intent.equals("return")&&PilotRestroomsR47.configured(level);
        if(roomReturn&&!PilotRestroomsR47.EPOCH.equals(pilot.getPersistentData().getString("SeelePilotRestroomEpochR47"))
                &&TvPersonnelPlatformInterlockR44.openForOriginalBoardingPilotR46(level,pilot).isPresent())return;
        var route=new ArrayList<>(roomReturn?savedRestroomReturnRouteR47(level,pilot)
                :validatedBoardingRoute(level,variant,FacilityV2EvaRuntime.ready(level,variant)));
        if(route.size()<2){if(roomReturn)holdRouteR45(pilot,"saved_room_route_unavailable");return;}
        if(intent.equals("return")&&!roomReturn)java.util.Collections.reverse(route);
        int leg=1;double best=Double.MAX_VALUE;
        for(int i=1;i<route.size();i++)
        {
            Vec3 a=Vec3.atBottomCenterOf(route.get(i-1)),b=Vec3.atBottomCenterOf(route.get(i)),ab=b.subtract(a);
            double t=ab.lengthSqr()<1e-8?1:Mth.clamp(pilot.position().subtract(a).dot(ab)/ab.lengthSqr(),0,1);
            double distance=pilot.position().distanceToSqr(a.add(ab.scale(t)));if(distance<best){best=distance;leg=i;}
        }
        if(best>36){holdRouteR45(pilot,"saved_route_outside_catwalk");return;}
        BOARDING_ROUTES.put(variant,List.copyOf(route));BOARDING_LEG.put(variant,leg);CLOSEST_APPROACH.remove(variant);STALLED_TICKS.remove(variant);
        if(safeActualFeetR46(level,pilot.position()))LAST_SAFE_FEET.put(variant,pilot.blockPosition());
        if(intent.equals("return"))RETURNING_PILOTS.add(variant);else ACTIVE_REMOTE_PILOTS.add(variant);
        if(intent.equals("board")||roomReturn)PENDING_NATIVE_PREFLIGHT_R47.add(variant);
        pilot.setNoAi(false);pilot.setNoGravity(false);
    }

    private static BlockPos nearestSafeFeet(ServerLevel level,
                                             BlockPos requested)
    {
        int[] offsets = {0, 1, -1, 2, -2, 3, -3};
        for (int radius = 0; radius <= 2; radius++)
        {
            for (int dx = -radius; dx <= radius; dx++)
            {
                for (int dz = -radius; dz <= radius; dz++)
                {
                    if (Math.max(Math.abs(dx), Math.abs(dz)) != radius)
                    {
                        continue;
                    }
                    for (int offset : offsets)
                    {
                        BlockPos candidate = requested.offset(dx, offset, dz);
                        Vec3 supported = safeFeetPositionR47(level,candidate);
                        if (supported != null)
                        {
                            // Native nodes use the integer cell above a partial
                            // tread; physical arrival still uses its real top.
                            return new BlockPos(candidate.getX(),Mth.ceil(supported.y),candidate.getZ());
                        }
                    }
                }
            }
        }
        return null;
    }

    private static List<BlockPos> validatedBoardingRoute(ServerLevel level,
                                                          int variant,
                                                          boolean modern)
    {
        if(PilotRestroomsR47.configured(level))
        {
            var room=PilotRestroomsR47.plan(level,variant);if(room.isEmpty())return List.of();
            var route=new ArrayList<BlockPos>();
            for(Vec3 point:room.get().route())
            {
                BlockPos q=new BlockPos(Mth.floor(point.x),Mth.ceil(point.y-1e-7),Mth.floor(point.z));
                if(nativeNodeFeetR47(level,q)==null)return List.of();
                if(route.isEmpty()||!route.get(route.size()-1).equals(q))route.add(q);
            }
            return List.copyOf(route);
        }
        List<BlockPos> requested = new ArrayList<>();
        if (modern)
        {
            requested.add(requestedStandby(level, variant));
            requested.add(FacilityV2EvaRuntime.boardingPosition(level,
                    variant));
        }
        else
        {
            BlockPos origin = RegionalFacilityLayout.evaOrigin(level);
            BlockPos standby = EvaHangarBuilder.pilotStandbyPosition(origin,
                    variant);
            List<BlockPos> fixedApproach=TvPersonnelPlatformInterlockR44.boardingApproachR47(level,variant);
            if(!fixedApproach.isEmpty())
            {
                requested.add(standby);
                requested.addAll(fixedApproach);
                requested.add(EvaHangarBuilder.boardingPosition(origin,variant));
            }
            else
            {
                BlockPos sideDoor = EvaHangarBuilder.boardingRouteWaypoint(origin,
                        variant, 0);
                requested.add(standby);
                requested.add(new BlockPos(sideDoor.getX(), standby.getY(),
                        standby.getZ()));
                for (int leg = 0; leg < 4; leg++)
                {
                    requested.add(EvaHangarBuilder.boardingRouteWaypoint(origin,
                            variant, leg));
                }
                requested.add(EvaHangarBuilder.boardingPosition(origin, variant));
            }
        }

        List<BlockPos> route = new ArrayList<>(requested.size());
        for (int anchor = 0; anchor < requested.size(); anchor++)
        {
            BlockPos safe = nearestSafeFeet(level, requested.get(anchor));
            if (safe == null)
            {
                ProjectSeele.LOGGER.warn(
                        "NERV dummy route anchor unsupported: eva={} anchor={} requested={}",
                        variant, anchor, requested.get(anchor).toShortString());
                return List.of();
            }
            route.add(safe.immutable());
        }
        ProjectSeele.LOGGER.info(
                "NERV dummy route validated: eva={} anchors={} start={} plug={}",
                variant, route.size(), route.get(0).toShortString(),
                route.get(route.size() - 1).toShortString());
        return List.copyOf(route);
    }

    static BlockPos requestedStandby(ServerLevel level, int variant)
    {
        if(PilotRestroomsR47.configured(level))return PilotRestroomsR47.plan(level,variant)
                .map(p->BlockPos.containing(p.stand())).orElseGet(()->EvaHangarBuilder.pilotStandbyPosition(RegionalFacilityLayout.evaOrigin(level),variant));
        if (FacilityV2EvaRuntime.ready(level, variant))
        {
            return FacilityV2EvaRuntime.statusControl(level, variant)
                    .offset(0, 0, -5);
        }
        return EvaHangarBuilder.pilotStandbyPosition(
                RegionalFacilityLayout.evaOrigin(level), variant);
    }

    private static boolean isSafeFeet(ServerLevel level, BlockPos feet)
    {
        return safeFeetPositionR47(level,feet)!=null;
    }

    private static Vec3 safeFeetPositionR47(net.minecraft.world.level.Level level, BlockPos feet)
    {
        return supportedFeetR47(level,feet,false);
    }

    /** A native integer node denotes the ceiling of the actual fractional sole. */
    public static Vec3 nativeNodeFeetR47(net.minecraft.world.level.Level level, BlockPos feet)
    {
        return supportedFeetR47(level,feet,true);
    }

    private static Vec3 supportedFeetR47(net.minecraft.world.level.Level level, BlockPos feet,boolean nativeNode)
    {
        // The real fine-grating/ramp surface may lie inside the feet block;
        // faceSturdy plus two entirely empty voxels rejects that valid floor.
        // Use the native collision top intersecting the actual .6m footprint.
        for(int dy=-2;dy<=0;dy++)
        {
            var at=feet.offset(0,dy,0);if(!level.hasChunkAt(at))return null;
            var state=level.getBlockState(at);
            if(!state.getFluidState().isEmpty()||state.getBlock() instanceof net.minecraft.world.level.block.DoorBlock
                    ||state.getBlock() instanceof StationDepartureBoardBlock
                    ||state.getBlock() instanceof TvPersonnelGuardR44
                    ||state.getBlock() instanceof FacilityEdgeRailR41)continue;
            if(dy==0&&!(state.getBlock() instanceof TvPersonnelDeckR44)
                    &&!(state.getBlock() instanceof net.minecraft.world.level.block.StairBlock)
                    &&!state.is(com.projectseele.registry.ModBlocks.NERV_MOVING_WALK.get())
                    &&!net.minecraft.core.registries.BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString().equals("mtr:escalator_step"))continue;
            for(var local:state.getCollisionShape(level,at).toAabbs())
            {
                var floor=local.move(at);double top=floor.maxY;
                if(top<feet.getY()-.9999||top>feet.getY()+1.0001
                        ||(nativeNode&&Mth.ceil(top-1.0E-7)!=feet.getY())
                        ||floor.maxX<=feet.getX()+.2||floor.minX>=feet.getX()+.8
                        ||floor.maxZ<=feet.getZ()+.2||floor.minZ>=feet.getZ()+.8)continue;
                var body=new net.minecraft.world.phys.AABB(feet.getX()+.2,top+.001,feet.getZ()+.2,
                        feet.getX()+.8,top+1.8,feet.getZ()+.8);
                if(level.containsAnyLiquid(body))continue;
                var volume=net.minecraft.world.phys.shapes.Shapes.create(body);boolean blocked=false;
                for(var shape:level.getBlockCollisions(null,body))
                    if(net.minecraft.world.phys.shapes.Shapes.joinIsNotEmpty(shape,volume,
                            net.minecraft.world.phys.shapes.BooleanOp.AND)){blocked=true;break;}
                if(!blocked)return new Vec3(feet.getX()+.5,top,feet.getZ()+.5);
            }
        }
        return null;
    }

    private static boolean safeActualFeetR46(ServerLevel level,Vec3 feet)
    {
        var body=new net.minecraft.world.phys.AABB(feet.x-.3,feet.y+.001,feet.z-.3,feet.x+.3,feet.y+1.8,feet.z+.3);
        if(level.containsAnyLiquid(body))return false;
        var volume=net.minecraft.world.phys.shapes.Shapes.create(body);
        for(var collision:level.getBlockCollisions(null,body))
            if(net.minecraft.world.phys.shapes.Shapes.joinIsNotEmpty(collision,volume,
                    net.minecraft.world.phys.shapes.BooleanOp.AND))return false;
        for(int x=Mth.floor(feet.x-.3);x<=Mth.floor(feet.x+.3);x++)
            for(int z=Mth.floor(feet.z-.3);z<=Mth.floor(feet.z+.3);z++)
                for(int y=Mth.floor(feet.y)-1;y<=Mth.floor(feet.y);y++)
                {
                    var at=new BlockPos(x,y,z);if(!level.hasChunkAt(at))return false;
                    // Liquid below a dry grating is not liquid inside the pilot.
                    var state=level.getBlockState(at);if(!state.getFluidState().isEmpty())continue;
                    if(state.getBlock() instanceof net.minecraft.world.level.block.DoorBlock
                            ||state.getBlock() instanceof StationDepartureBoardBlock
                            ||state.getBlock() instanceof TvPersonnelGuardR44
                            ||state.getBlock() instanceof FacilityEdgeRailR41)continue;
                    for(var local:state.getCollisionShape(level,at).toAabbs())
                    {
                        var floor=local.move(at);
                        // Imported display pilots may be one sixteenth above
                        // a 15/16 moving walk. Gravity settles that real sole;
                        // a nearby surface is not a position-reset licence.
                        if(Math.abs(floor.maxY-feet.y)<=.08&&floor.maxX>feet.x-.3&&floor.minX<feet.x+.3
                                &&floor.maxZ>feet.z-.3&&floor.minZ<feet.z+.3)return true;
                    }
                }
        return false;
    }

    public static boolean safeActualFeetR47(ServerLevel level,Vec3 feet){return safeActualFeetR46(level,feet);}

    private static net.minecraft.world.level.pathfinder.Path createPilotDeclaredPathR47(TrainingPilotEntity pilot,
            List<BlockPos> declared,BlockPos target)
    {
        return pilot.getNavigation() instanceof com.projectseele.entity.TrainingPilotNavigationR47 exact
                ?exact.createDeclaredRoutePathR47(target,declared):pilot.getNavigation().createPath(target,0);
    }

    private static boolean actualNativeRouteR46(ServerLevel level,TrainingPilotEntity pilot,List<BlockPos> route)
    {
        BlockPos target=route.get(route.size()-1);
        var path=createPilotDeclaredPathR47(pilot,route,target);
        if(path==null||!path.canReach())
        {
            String failure="mode=full_boarding_preflight "+routeTraceR47(level,pilot)+" "
                    +attemptedPathTraceR47(level,pilot,path,target);
            pilot.getPersistentData().putString("SeelePilotNativePathFailureR47",failure);
            ProjectSeele.LOGGER.warn("NERV original pilot full boarding path failed: eva={} {}",
                    pilot.getAssignedVariant(),failure);
            return false;
        }
        for(int i=0;i<path.getNodeCount();i++)
        {
            var node=path.getNode(i);var feet=new BlockPos(node.x,node.y,node.z);
            if(!isSafeFeet(level,feet))
            {
                String failure="mode=full_boarding_preflight unsafeIndex="+i+" unsafeNode="+feet
                        +" unsafeType="+node.type+" unsafeSole="+nativeNodeFeetR47(level,feet)
                        +" unsafeBlock="+level.getBlockState(feet)+" unsafeBelow="+level.getBlockState(feet.below())
                        +" unsafeHead="+level.getBlockState(feet.above())+" "+routeTraceR47(level,pilot)
                        +" "+attemptedPathTraceR47(level,pilot,path,target);
                pilot.getPersistentData().putString("SeelePilotNativePathFailureR47",failure);
                ProjectSeele.LOGGER.warn("NERV original pilot full boarding path unsafe node: eva={} index={} feet={} floor={} body={} head={}",
                        pilot.getAssignedVariant(),i,feet,level.getBlockState(feet.below()),
                        level.getBlockState(feet),level.getBlockState(feet.above()));return false;
            }
        }
        pilot.getPersistentData().putString("SeelePilotLastFullNativeRouteR47",
                "mode=full_preflight_validated_not_physical_arrival "+attemptedPathTraceR47(level,pilot,path,target));
        ProjectSeele.LOGGER.info("NERV original pilot full native boarding path validated: eva={} nodes={} from={} target={} search={}",
                pilot.getAssignedVariant(),path.getNodeCount(),pilot.position(),target,
                pilot.getNavigation() instanceof com.projectseele.entity.TrainingPilotNavigationR47 exact
                        ?exact.lastSearchEvidenceR47():"other_native_navigation");
        return true;
    }

    public static void resetRuntime()
    {
        CLOSEST_APPROACH.clear();
        STALLED_TICKS.clear();
        BOARDING_LEG.clear();
        BOARDING_ROUTES.clear();
        LAST_SAFE_FEET.clear();
        ACTIVE_REMOTE_PILOTS.clear();
        RETURNING_PILOTS.clear();
        PENDING_NATIVE_PREFLIGHT_R47.clear();
    }
    public static void tickFeeds(MinecraftServer server)
    {
        if (!SeeleConfig.dummyPilotVideoEnabled()
                || server.getTickCount() % FEED_INTERVAL_TICKS != 0)
        {
            return;
        }
        ServerLevel level = server.getLevel(GeoFrontCommands.GEOFRONT);
        if (level == null
                || !ServerboundEvaVideoFramePacket.hasCommandViewers(level))
        {
            return;
        }
        for (TrainingPilotEntity pilot : pilots(level))
        {
            EvaUnit01Entity unit = EvaPilotResolver.controlTarget(pilot);
            if (unit == null || EvaPilotResolver.pilot(unit) != pilot
                    || ServerboundEvaVideoFramePacket.isHumanFeedActive(
                            level, unit.getUnitVariant()))
            {
                continue;
            }
            byte[] png = trainingFrame(level, pilot, unit);
            ServerboundEvaVideoFramePacket.relayTrainingFrame(
                    level, unit.getUnitVariant(), png);
        }
    }

    private static byte[] trainingFrame(ServerLevel level,
                                        TrainingPilotEntity pilot,
                                        EvaUnit01Entity unit)
    {
        int[] samples = new int[SAMPLE_WIDTH * SAMPLE_HEIGHT];
        Vec3 eye = pilot.getEyePosition();
        Vec3 forward = Vec3.directionFromRotation(
                pilot.getXRot(), pilot.getYRot()).normalize();
        Vec3 right = forward.cross(new Vec3(0.0D, 1.0D, 0.0D));
        right = right.lengthSqr() < 1.0E-6D
                ? new Vec3(1.0D, 0.0D, 0.0D) : right.normalize();
        Vec3 up = right.cross(forward).normalize();
        PerformanceCounters.recordRaycasts(
                (long) SAMPLE_WIDTH * SAMPLE_HEIGHT);
        for (int row = 0; row < SAMPLE_HEIGHT; row++)
        {
            double vertical = (1.0D - (row + 0.5D)
                    / SAMPLE_HEIGHT * 2.0D) * TAN_HALF_FOV_Y;
            for (int column = 0; column < SAMPLE_WIDTH; column++)
            {
                double horizontal = ((column + 0.5D)
                        / SAMPLE_WIDTH * 2.0D - 1.0D) * TAN_HALF_FOV_X;
                Vec3 direction = forward.add(right.scale(horizontal))
                        .add(up.scale(vertical)).normalize();
                BlockHitResult hit = level.clip(new ClipContext(
                        eye, eye.add(direction.scale(FEED_RANGE)),
                        ClipContext.Block.COLLIDER, ClipContext.Fluid.ANY,
                        pilot));
                samples[row * SAMPLE_WIDTH + column] = sampleColour(
                        level, eye, direction, hit);
            }
        }
        int width = ServerboundEvaVideoFramePacket.FRAME_WIDTH;
        int height = ServerboundEvaVideoFramePacket.FRAME_HEIGHT;
        int[] pixels = new int[width * height];
        for (int y = 0; y < height; y++)
        {
            int sourceY = y * SAMPLE_HEIGHT / height;
            for (int x = 0; x < width; x++)
            {
                int sourceX = x * SAMPLE_WIDTH / width;
                int colour = samples[sourceY * SAMPLE_WIDTH + sourceX];
                if ((y & 3) == 3)
                {
                    colour = shade(colour, 0.82D);
                }
                pixels[y * width + x] = colour;
            }
        }
        paintOverlay(pixels, width, height, unit.getUnitVariant());
        return encodePng(width, height, pixels);
    }

    private static int sampleColour(ServerLevel level, Vec3 eye,
                                    Vec3 direction, BlockHitResult hit)
    {
        if (hit.getType() == HitResult.Type.MISS)
        {
            double sky = Mth.clamp(direction.y * 0.5D + 0.5D, 0.0D, 1.0D);
            return mix(0x182538, 0x78A9E8, sky);
        }
        BlockPos position = hit.getBlockPos();
        BlockState state = level.getBlockState(position);
        int colour;
        if (state.getFluidState().getFluidType() == ModFluids.LCL_TYPE.get())
        {
            colour = 0xE98720;
        }
        else if (state.getFluidState().is(FluidTags.WATER))
        {
            colour = 0x315FAD;
        }
        else if (state.getFluidState().is(FluidTags.LAVA))
        {
            colour = 0xF04A16;
        }
        else if (state.is(BlockTags.LEAVES)
                || state.is(Blocks.GRASS_BLOCK)
                || state.is(Blocks.MOSS_BLOCK))
        {
            colour = 0x497B36;
        }
        else
        {
            colour = state.getMapColor(level, position).col;
            if (colour == 0)
            {
                colour = 0x777A80;
            }
        }
        double distance = eye.distanceTo(hit.getLocation());
        double brightness = Mth.clamp(1.05D - distance / 240.0D,
                0.38D, 1.0D);
        brightness *= switch (hit.getDirection())
        {
            case DOWN -> 0.58D;
            case NORTH, SOUTH -> 0.83D;
            case EAST, WEST -> 0.70D;
            default -> 1.0D;
        };
        return shade(colour, brightness);
    }

    private static void paintOverlay(int[] pixels, int width, int height,
                                     int variant)
    {
        int accent = UNIT_COLOURS[Mth.clamp(variant, 0, 2)];
        fill(pixels, width, height, 0, 0, width, 2, accent);
        fill(pixels, width, height, 0, height - 2, width, 2, accent);
        fill(pixels, width, height, 0, 0, 2, height, accent);
        fill(pixels, width, height, width - 2, 0, 2, height, accent);
        fill(pixels, width, height, 8, 7, 28, 2, accent);
        fill(pixels, width, height, width - 36, 7, 28, 2, accent);
        int centreX = width / 2;
        int centreY = height / 2;
        fill(pixels, width, height, centreX - 8, centreY, 6, 1, accent);
        fill(pixels, width, height, centreX + 3, centreY, 6, 1, accent);
        fill(pixels, width, height, centreX, centreY - 8, 1, 6, accent);
        fill(pixels, width, height, centreX, centreY + 3, 1, 6, accent);
        for (int bar = 0; bar < 8; bar++)
        {
            fill(pixels, width, height, 12 + bar * 9, height - 10,
                    6, 2, bar < 5 ? accent : shade(accent, 0.35D));
        }
    }

    private static void fill(int[] pixels, int width, int height,
                             int x, int y, int areaWidth, int areaHeight,
                             int colour)
    {
        for (int py = Math.max(0, y); py < Math.min(height, y + areaHeight); py++)
        {
            for (int px = Math.max(0, x); px < Math.min(width, x + areaWidth); px++)
            {
                pixels[py * width + px] = colour;
            }
        }
    }

    private static int mix(int from, int to, double amount)
    {
        double safe = Mth.clamp(amount, 0.0D, 1.0D);
        int red = (int) Mth.lerp(safe, from >> 16 & 0xFF, to >> 16 & 0xFF);
        int green = (int) Mth.lerp(safe, from >> 8 & 0xFF, to >> 8 & 0xFF);
        int blue = (int) Mth.lerp(safe, from & 0xFF, to & 0xFF);
        return red << 16 | green << 8 | blue;
    }

    private static int shade(int colour, double brightness)
    {
        int red = Mth.clamp((int) ((colour >> 16 & 0xFF) * brightness), 0, 255);
        int green = Mth.clamp((int) ((colour >> 8 & 0xFF) * brightness), 0, 255);
        int blue = Mth.clamp((int) ((colour & 0xFF) * brightness), 0, 255);
        return red << 16 | green << 8 | blue;
    }

    private static byte[] encodePng(int width, int height, int[] pixels)
    {
        try
        {
            ByteArrayOutputStream raw = new ByteArrayOutputStream(
                    height * (width * 3 + 1));
            for (int y = 0; y < height; y++)
            {
                raw.write(0);
                for (int x = 0; x < width; x++)
                {
                    int colour = pixels[y * width + x];
                    raw.write(colour >> 16 & 0xFF);
                    raw.write(colour >> 8 & 0xFF);
                    raw.write(colour & 0xFF);
                }
            }
            ByteArrayOutputStream compressed = new ByteArrayOutputStream();
            try (DeflaterOutputStream deflater =
                         new DeflaterOutputStream(compressed))
            {
                raw.writeTo(deflater);
            }
            ByteArrayOutputStream png = new ByteArrayOutputStream();
            DataOutputStream output = new DataOutputStream(png);
            output.write(new byte[] {(byte) 0x89, 0x50, 0x4E, 0x47,
                    0x0D, 0x0A, 0x1A, 0x0A});
            ByteArrayOutputStream headerBytes = new ByteArrayOutputStream();
            DataOutputStream header = new DataOutputStream(headerBytes);
            header.writeInt(width);
            header.writeInt(height);
            header.writeByte(8);
            header.writeByte(2);
            header.writeByte(0);
            header.writeByte(0);
            header.writeByte(0);
            writeChunk(output, "IHDR", headerBytes.toByteArray());
            writeChunk(output, "IDAT", compressed.toByteArray());
            writeChunk(output, "IEND", new byte[0]);
            output.flush();
            PerformanceCounters.recordPngEncode();
            return png.toByteArray();
        }
        catch (IOException exception)
        {
            ProjectSeele.LOGGER.error("Unable to encode NERV training feed", exception);
            return new byte[0];
        }
    }

    private static void writeChunk(DataOutputStream output, String type,
                                   byte[] data) throws IOException
    {
        byte[] name = type.getBytes(java.nio.charset.StandardCharsets.US_ASCII);
        output.writeInt(data.length);
        output.write(name);
        output.write(data);
        CRC32 crc = new CRC32();
        crc.update(name);
        crc.update(data);
        output.writeInt((int) crc.getValue());
    }

    private static String label(int variant)
    {
        return String.format(Locale.ROOT, "EVA-%02d", variant);
    }

    public record ActionResult(boolean accepted, String message) {}
}

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

    private TrainingPilotDirector() {}

    public static ActionResult start(ServerLevel level, int variant)
    {
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
        if(pilot.getVehicle()!=null)
            return new ActionResult(false,"驾驶员还在另一台设备内，请先让驾驶员返回待命。");
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
        var gateFault=TvPersonnelPlatformInterlockR44.openForOriginalBoardingPilotR46(level,pilot);
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
        if(!actualNativeRouteR46(level,pilot,route.get(route.size()-1)))
        {
            TvPersonnelPlatformInterlockR44.finishPilotDoorUseR46(level,pilot);
            return new ActionResult(false,"登机通道还不能通过，驾驶员先在原地待命。");
        }
        BOARDING_ROUTES.put(variant, route);
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
        return new ActionResult(true, label(variant)
                + " dummy is walking to the dorsal boarding bridge.");
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

    public static int stop(ServerLevel level, int variant)
    {
        int returning=0;
        for(int candidate=0;candidate<3;candidate++)
        {
            if(variant>=0&&candidate!=variant||!parkedR45(level,candidate)
                    ||StaffCommandBookR24.unitOrder(level,candidate)!=null)continue;
            var pilot=existingPilotR45(level,candidate);
            if(pilot==null||!beginReturnOrReset(level,pilot))continue;
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
        if(!parkedR45(level,variant))return false;
        if(RETURNING_PILOTS.contains(variant))return true;
        if(pilot.getVehicle()==null&&safeActualFeetR46(level,pilot.position())
                &&pilot.blockPosition().distManhattan(requestedStandby(level,variant))<=2)
        {parkPilot(level,pilot);return true;}
        var outbound=BOARDING_ROUTES.get(variant);
        if(outbound==null||outbound.size()<2)
            outbound=validatedBoardingRoute(level,variant,FacilityV2EvaRuntime.ready(level,variant));
        if(outbound.size()<2)return false;
        var route=new ArrayList<>(outbound);java.util.Collections.reverse(route);
        Vec3 feet=pilot.position();
        if(pilot.getVehicle()!=null)
        {
            if(!(pilot.getVehicle() instanceof EntryPlugCarrierEntity plug)
                    ||plug!=EntryPlugDirector.canonical(level,variant)||plug.isLockedToEva()
                    ||!Set.of(EntryPlugCarrierEntity.STAGE_SUSPENDED,EntryPlugCarrierEntity.STAGE_OCCUPIED,
                            EntryPlugCarrierEntity.STAGE_ABORT_DOCKED).contains(plug.getInsertionStage()))return false;
            feet=plug.getDismountLocationForPassenger(pilot);
        }
        int leg=nearestRouteLegR45(feet,route);
        if(leg<0||!safeActualFeetR46(level,feet))return false;
        // The real capsule chooses its safe dismount; no route-start teleport.
        if(pilot.getVehicle()!=null)pilot.stopRiding();
        if(!safeActualFeetR46(level,pilot.position())){holdRouteR45(pilot,"dismount_not_on_catwalk");return false;}
        leg=nearestRouteLegR45(pilot.position(),route);
        if(leg<0){holdRouteR45(pilot,"dismount_outside_return_route");return false;}
        pilot.getNavigation().stop();pilot.setInvisible(false);
        pilot.setTrainingStage(TrainingPilotEntity.STAGE_WALKING);
        ACTIVE_REMOTE_PILOTS.remove(variant);RETURNING_PILOTS.add(variant);
        pilot.getPersistentData().putString("SeelePilotRouteR30","return");
        pilot.getPersistentData().remove("SeelePilotRouteMissionR45");
        BOARDING_ROUTES.put(variant,List.copyOf(route));BOARDING_LEG.put(variant,leg);
        LAST_SAFE_FEET.put(variant,pilot.blockPosition());CLOSEST_APPROACH.remove(variant);STALLED_TICKS.remove(variant);
        ProjectSeele.LOGGER.info("NERV original pilot returning without reset: eva={} pilot={} at={} leg={}",variant,pilot.getStringUUID(),pilot.blockPosition(),leg);
        return true;
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
        if(step==RouteStep.ARRIVED)parkPilot(level,pilot);
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
        if (pilot.position().distanceToSqr(Vec3.atBottomCenterOf(finalTarget))
                <= 2.75D * 2.75D)
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
        Vec3 destination = Vec3.atBottomCenterOf(routeTarget);
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

        double dx = pilot.getX() - destination.x;
        double dz = pilot.getZ() - destination.z;
        double flatSqr = dx * dx + dz * dz;
        Double best = CLOSEST_APPROACH.get(variant);
        if (best == null || flatSqr < best - 0.25D)
        {
            CLOSEST_APPROACH.put(variant, flatSqr);
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
        if (pilot.tickCount % 20 == 1 || pilot.getNavigation().isDone())
        {
            var path=pilot.getNavigation().createPath(routeTarget,0);
            if(path==null||!path.canReach())
            {
                ProjectSeele.LOGGER.warn("NERV original pilot native path cannot reach: eva={} from={} leg={} target={} pathNodes={}",
                        variant,pilot.position(),leg,routeTarget,path==null?0:path.getNodeCount());
                return RouteStep.FAILED;
            }
            pilot.getNavigation().moveTo(path,1.05D);
        }
        return RouteStep.MOVING;
    }

    private static void holdAtStandby(ServerLevel level,
                                      TrainingPilotEntity pilot)
    {
        if(pilot.getVehicle()!=null)return;
        if(pilot.getPersistentData().getString("SeelePilotRouteR30").equals("hold"))
        {pilot.getNavigation().stop();return;}
        int variant=pilot.getAssignedVariant();BlockPos feet=pilot.blockPosition();
        if(!safeActualFeetR46(level,pilot.position())||feet.distManhattan(requestedStandby(level,variant))>2)
        {holdRouteR45(pilot,"standby_not_reached");return;}
        pilot.getNavigation().stop();pilot.setDeltaMovement(Vec3.ZERO);pilot.fallDistance=0;
        pilot.setInvisible(false);pilot.setTrainingStage(TrainingPilotEntity.STAGE_STANDBY);
        pilot.setYRot(0);pilot.setXRot(0);pilot.yBodyRot=pilot.yHeadRot=0;
    }

    private static void parkPilot(ServerLevel level,
                                  TrainingPilotEntity pilot)
    {
        pilot.getPersistentData().putString("SeelePilotRouteR30","standby");
        clearRouteState(pilot.getAssignedVariant());
        holdAtStandby(level, pilot);
    }

    private static void clearRouteState(int variant)
    {
        ACTIVE_REMOTE_PILOTS.remove(variant);
        RETURNING_PILOTS.remove(variant);
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
        int variant=pilot.getAssignedVariant();var route=new ArrayList<>(validatedBoardingRoute(level,variant,FacilityV2EvaRuntime.ready(level,variant)));
        if(route.size()<2)return;if(intent.equals("return"))java.util.Collections.reverse(route);
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
                        if (isSafeFeet(level, candidate))
                        {
                            return candidate;
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
        // The real fine-grating/ramp surface may lie inside the feet block;
        // faceSturdy plus two entirely empty voxels rejects that valid floor.
        // Use the native collision top intersecting the actual .6m footprint.
        for(int dy=-1;dy<=0;dy++)
        {
            var at=feet.offset(0,dy,0);if(!level.hasChunkAt(at))return false;
            var state=level.getBlockState(at);
            if(!state.getFluidState().isEmpty()||state.getBlock() instanceof net.minecraft.world.level.block.DoorBlock
                    ||state.getBlock() instanceof StationDepartureBoardBlock
                    ||state.getBlock() instanceof TvPersonnelGuardR44)continue;
            if(dy==0&&!(state.getBlock() instanceof TvPersonnelDeckR44)
                    &&!(state.getBlock() instanceof net.minecraft.world.level.block.StairBlock)
                    &&!state.is(com.projectseele.registry.ModBlocks.NERV_MOVING_WALK.get())
                    &&!net.minecraft.core.registries.BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString().equals("mtr:escalator_step"))continue;
            for(var local:state.getCollisionShape(level,at).toAabbs())
            {
                var floor=local.move(at);double top=floor.maxY;
                if(top<feet.getY()-.75||top>feet.getY()+1.0001
                        ||floor.maxX<=feet.getX()+.2||floor.minX>=feet.getX()+.8
                        ||floor.maxZ<=feet.getZ()+.2||floor.minZ>=feet.getZ()+.8)continue;
                var body=new net.minecraft.world.phys.AABB(feet.getX()+.2,top+.001,feet.getZ()+.2,
                        feet.getX()+.8,top+1.8,feet.getZ()+.8);
                var volume=net.minecraft.world.phys.shapes.Shapes.create(body);boolean blocked=false;
                for(var shape:level.getBlockCollisions(null,body))
                    if(net.minecraft.world.phys.shapes.Shapes.joinIsNotEmpty(shape,volume,
                            net.minecraft.world.phys.shapes.BooleanOp.AND)){blocked=true;break;}
                if(!blocked)return true;
            }
        }
        return false;
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
                            ||state.getBlock() instanceof TvPersonnelGuardR44)continue;
                    for(var local:state.getCollisionShape(level,at).toAabbs())
                    {
                        var floor=local.move(at);
                        if(Math.abs(floor.maxY-feet.y)<=.05&&floor.maxX>feet.x-.3&&floor.minX<feet.x+.3
                                &&floor.maxZ>feet.z-.3&&floor.minZ<feet.z+.3)return true;
                    }
                }
        return false;
    }

    private static boolean actualNativeRouteR46(ServerLevel level,TrainingPilotEntity pilot,BlockPos target)
    {
        var path=pilot.getNavigation().createPath(target,0);
        if(path==null||!path.canReach())
        {
            ProjectSeele.LOGGER.warn("NERV original pilot full boarding path failed: eva={} from={} target={} reachable={} nodes={}",
                    pilot.getAssignedVariant(),pilot.position(),target,path!=null&&path.canReach(),path==null?0:path.getNodeCount());
            return false;
        }
        for(int i=0;i<path.getNodeCount();i++)
        {
            var node=path.getNode(i);var feet=new BlockPos(node.x,node.y,node.z);
            if(!isSafeFeet(level,feet))
            {
                ProjectSeele.LOGGER.warn("NERV original pilot full boarding path unsafe node: eva={} index={} feet={} floor={} body={} head={}",
                        pilot.getAssignedVariant(),i,feet,level.getBlockState(feet.below()),
                        level.getBlockState(feet),level.getBlockState(feet.above()));return false;
            }
        }
        ProjectSeele.LOGGER.info("NERV original pilot full native boarding path validated: eva={} nodes={} from={} target={}",
                pilot.getAssignedVariant(),path.getNodeCount(),pilot.position(),target);
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

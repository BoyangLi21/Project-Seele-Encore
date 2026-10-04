package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.world.*;
import com.supermartijn642.movingelevators.blocks.ControllerBlockEntity;
import net.minecraft.server.level.*;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Real native cabin trips with a moving, corner-standing human passenger. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class LiftPassengerR20Review
{
    private static final boolean DESCENT="r22-lift-descend".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final boolean R44="r44-lifts".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final boolean R43=R44||"r43-lifts".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R42=R43||"r42-lifts".equals(System.getProperty("projectseele.regionalBuild",""));
    private static boolean accessReviewed;
    private static final boolean R41=R42||"r41-lifts".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R40=R41||"r40-lifts".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean ALL=R40||"r22-lifts-all".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R26="r26-lifts".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R25=R26||"r25-lifts".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final boolean R22=R25||ALL||DESCENT||"r22-lifts".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R21="r21-lifts".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final boolean ENABLED=R22||R21||Set.of("r20-lift","r20-lift-rest").contains(System.getProperty("projectseele.regionalBuild",""));
    public static volatile net.minecraft.core.BlockPos controllerPosition;
    public static volatile boolean clientReady,finished,moving;
    public static volatile int tripAge;
    public static volatile net.minecraft.world.phys.Vec3 walkingTargetR43;
    public static volatile String phaseR43="";
    public static volatile net.minecraft.core.BlockPos clickTargetR44;
    public static volatile net.minecraft.world.phys.Vec3 clickPointR44;
    public static volatile boolean clickedR44;
    private static boolean exteriorCallObservedR44;
    public static volatile String clickFailureR44="";
    public static volatile JsonObject clickReceiptR44;
    public static volatile JsonObject blockedClientR44;
    private static JsonArray measuredInterfacesR44;
    private static final Set<String> completedSourcesR44=new LinkedHashSet<>();
    private static JsonObject pendingTripR43;
    private static float entryHealthR43;
    private static int entryDamageCountR43;
    private static int entryStartedTimerR43;
    private static int age,index=R40?Integer.getInteger("projectseele.r40LiftStart",0):DESCENT?3:R21?2:"r20-lift-rest".equals(System.getProperty("projectseele.regionalBuild",""))?4:0,stage,timer,doorArrivalTicks;
    private static final JsonArray results=new JsonArray();
    private static final JsonArray damageEvents=new JsonArray();
    private static final JsonArray diagnosticStates=new JsonArray();
    private static final JsonArray interfaceSpecsR43=new JsonArray();
    @SubscribeEvent public static void hurt(net.minecraftforge.event.entity.living.LivingHurtEvent e)
    {
        if(!ENABLED||finished||!(e.getEntity() instanceof ServerPlayer p))return;
        JsonObject r=new JsonObject();r.addProperty("source",e.getSource().getMsgId());r.addProperty("amount",e.getAmount());r.addProperty("stage",stage);r.addProperty("timer",timer);r.addProperty("lift",IDS[Math.min(index,IDS.length-1)]);r.addProperty("position",p.position().toString());r.addProperty("fallDistance",p.fallDistance);
        JsonArray blocks=new JsonArray();for(var q:net.minecraft.core.BlockPos.betweenClosed(p.blockPosition().offset(-1,0,-1),p.blockPosition().offset(1,2,1)))if(!p.level().getBlockState(q).isAir())blocks.add(q.toShortString()+" "+p.level().getBlockState(q));r.add("nearbyBlocks",blocks);damageEvents.add(r);
        ProjectSeele.LOGGER.warn("R21 LIFT DAMAGE {}",r);
    }
    private static double minimumFloorError=100,maximumWallOverflow;
    private static JsonObject candidateTripsR45;
    private static final JsonArray actualInputsR45=new JsonArray();
    private static final String[] IDS=R40?tripsR40().stream().map(Trip::id).toArray(String[]::new):R26?new String[]{FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.OBSERVATION,FacilityLiftsR25.OBSERVATION}:R25?new String[]{FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.OBSERVATION,FacilityLiftsR25.OBSERVATION}:new String[]{S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID,S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID,S20PhysicalElevatorDirector.SURFACE_TRANSIT_LIFT_ID,S20PhysicalElevatorDirector.SURFACE_TRANSIT_LIFT_ID,NervLiftPassengerSync.GATEWAY,NervLiftPassengerSync.GATEWAY,S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID,S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID,S20PhysicalElevatorDirector.COMMANDER_OFFICE_LIFT_ID,S20PhysicalElevatorDirector.COMMANDER_OFFICE_LIFT_ID};
    private static final int[] FROM=R40?tripsR40().stream().mapToInt(Trip::from).toArray():R26?new int[]{-461,-364,-448,-434,-420,-406,-392,-378,-394,-367}:R25?new int[]{-448,-392,-434,-420,-406,-448,-394,-367}:new int[]{-566,-448,-442,81,-466,81,-442,-370,-388,-340};
    private static final int[] TO=R40?tripsR40().stream().mapToInt(Trip::to).toArray():R26?new int[]{-364,-448,-434,-420,-406,-392,-378,-461,-367,-394}:R25?new int[]{-392,-434,-420,-406,-448,-434,-367,-394}:new int[]{-448,-566,81,-442,81,-466,-370,-394,-340,-388};
    private record Trip(String id,int from,int to) {}
    private static List<Trip> tripsR40()
    {
        var trips=new ArrayList<Trip>();
        String file=System.getProperty("projectseele.r45LiftTripCases", "");
        if(R44&&!file.isBlank())
        {
            try
            {
                candidateTripsR45=CandidateLiftTripCasesR45.load();
                for(var raw:candidateTripsR45.getAsJsonArray("cases"))
                {
                    var row=raw.getAsJsonObject();
                    trips.add(new Trip(row.get("runtime_alias").getAsString(),
                            row.getAsJsonArray("from_cabin").get(1).getAsInt(),
                            row.getAsJsonArray("to_cabin").get(1).getAsInt()));
                }
                return trips;
            }
            catch(Exception failure){throw new IllegalStateException("Strict candidate lift trip file rejected",failure);}
        }
        append(trips,S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID,-566,-448,-423,-419,-409,-448,-566);
        append(trips,S20PhysicalElevatorDirector.SURFACE_TRANSIT_LIFT_ID,-442,75,-442);
        append(trips,NervLiftPassengerSync.GATEWAY,-466,81,-466);
        append(trips,S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID,-442,-394,-370,-442);
        append(trips,S20PhysicalElevatorDirector.COMMANDER_OFFICE_LIFT_ID,-388,-340,-388);
        append(trips,FacilityLiftsR25.EAST,-461,-448,-434,-420,-406,-392,-378,-364,-461);
        append(trips,FacilityLiftsR25.OBSERVATION,-394,-367,-394);
        return trips;
    }
    private static void append(List<Trip> trips,String id,int... floors)
    {for(int i=1;i<floors.length;i++)trips.add(new Trip(id,floors[i-1],floors[i]));}
    private static void require(boolean value,String why){if(!value)throw new IllegalStateException(why);}
    private static void reviewAccess(ServerLevel level,ServerPlayer player,Path world)throws Exception
    {
        var before=player.position();var dimension=player.serverLevel();float yaw=player.getYRot(),pitch=player.getXRot();
        var main=player.getMainHandItem().copy();var off=player.getOffhandItem().copy();var rows=new JsonArray();
        try
        {
            for(String id:List.of(S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID,S20PhysicalElevatorDirector.COMMANDER_OFFICE_LIFT_ID))
            {
                var spec=NervLiftPassengerSync.managedLifts(level).stream().filter(s->s.id().equals(id)).findFirst().orElseThrow();
                for(var stop:spec.stops())
                {level.getChunkAt(stop.cabinCentre());level.getChunkAt(S20MovingElevatorsAdapter.controllerPosition(spec,stop));}
                require(S20MovingElevatorsAdapter.reconcile(level,spec),"Clearance review controller not ready");
                var controller=(ControllerBlockEntity)level.getBlockEntity(S20MovingElevatorsAdapter.controllerPosition(spec,spec.lower()));
                var target=id.equals(S20PhysicalElevatorDirector.COMMANDER_OFFICE_LIFT_ID)?spec.upper():spec.lower();
                var publicStop=spec.stops().stream().filter(s->Math.abs(s.walkY()-target.walkY())>8).findFirst().orElseThrow();
                player.teleportTo(level,publicStop.cabinCentre().getX()+.5,publicStop.walkY(),publicStop.cabinCentre().getZ()+.5,0,0);
                player.setItemInHand(net.minecraft.world.InteractionHand.MAIN_HAND,net.minecraft.world.item.ItemStack.EMPTY);
                player.setItemInHand(net.minecraft.world.InteractionHand.OFF_HAND,net.minecraft.world.item.ItemStack.EMPTY);
                boolean denied=!S20MovingElevatorsAdapter.allowDisplayPress(controller.getGroup(),target.walkY(),0,player);
                player.setItemInHand(net.minecraft.world.InteractionHand.OFF_HAND,new net.minecraft.world.item.ItemStack(com.projectseele.registry.ModItems.TERMINAL_DOGMA_ACCESS_CARD.get()));
                boolean admitted=S20MovingElevatorsAdapter.allowDisplayPress(controller.getGroup(),target.walkY(),0,player);
                var row=new JsonObject();row.addProperty("lift",id);row.addProperty("label",target.label());row.addProperty("denied_without_card",denied);row.addProperty("admitted_with_card",admitted);rows.add(row);
                require(denied&&admitted,"Translated landing changed real clearance policy: "+id);
            }
            Files.writeString(world.resolve("r42_clearance_review.json"),rows.toString());
        }
        finally
        {
            player.setItemInHand(net.minecraft.world.InteractionHand.MAIN_HAND,main);player.setItemInHand(net.minecraft.world.InteractionHand.OFF_HAND,off);
            player.teleportTo(dimension,before.x,before.y,before.z,yaw,pitch);
        }
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent e)
    {
        if(!ENABLED||finished||e.phase!=TickEvent.Phase.END||!clientReady||e.getServer().getPlayerList().getPlayers().isEmpty())return;
        Path world=e.getServer().getWorldPath(LevelResource.ROOT).normalize();
        String worldName=world.getFileName().toString();
        require(R44?(worldName.equals(com.projectseele.visual.NativeReviewWorldsR45.expectedName())||worldName.matches("SEELE_R44_LIFT_COLD_REVIEW_V[0-9]+"))
                :R43?(worldName.equals("SEELE_FIELD_R43_REVIEW")||worldName.matches("SEELE_R43_LIFT_COLD_REVIEW_V[0-9]+"))
                :worldName.equals(R42?"SEELE_R42_MECHANICS_REVIEW":R41?"SEELE_R41_MECHANICS_REVIEW":R40?"SEELE_FIELD_R40_REVIEW":R26?"SEELE_R26_REVIEW":R25?"SEELE_R25_REVIEW":R22?"SEELE_R22_REVIEW":R21?"SEELE_R21_REVIEW":"SEELE_R20_REVIEW"),"Lift review boundary");
        var player=e.getServer().getPlayerList().getPlayers().get(0);var level=e.getServer().getLevel(FacilitySchemaV2.DIMENSION);
        try
        {
            if(candidateTripsR45!=null)
            {
                if(!FacilitySourceAdmissionR45.admit(level,candidateTripsR45))return;
                String requested=System.getProperty("projectseele.r45LiftOutput", "");
                require(!requested.isBlank(),"Candidate lift receipt must use a unique artifact path before movement");
                Path output=Path.of(requested).toAbsolutePath().normalize();
                require(!output.startsWith(world.toRealPath())&&!Files.exists(output),"Candidate lift receipt cannot overwrite a world or earlier run");
            }
            if(R44&&!clickFailureR44.isEmpty())throw new IllegalStateException(clickFailureR44);
            if(R44&&clickReceiptR44!=null){diagnosticStates.add(clickReceiptR44);clickReceiptR44=null;}
            if(R44&&blockedClientR44!=null){diagnosticStates.add(blockedClientR44);blockedClientR44=null;}
            if(R43&&interfaceSpecsR43.isEmpty())
                for(var resolved:NervLiftPassengerSync.managedLifts(level))for(var stop:resolved.stops())
                {
                    boolean gateway=resolved.id().equals(NervLiftPassengerSync.GATEWAY);double distance=gateway?11.5:7.5;
                    var row=new JsonObject();row.addProperty("lift",resolved.id());row.addProperty("label",stop.label());
                    row.addProperty("cabin_walk_y",stop.walkY());row.addProperty("approach_walk_y",stop.approachWalkY());row.addProperty("exit",stop.exit().getName());
                    var centre=new JsonArray();centre.add(stop.cabinCentre().getX());centre.add(stop.cabinCentre().getY());centre.add(stop.cabinCentre().getZ());row.add("cabin_centre",centre);
                    var approach=new JsonArray();approach.add(stop.cabinCentre().getX()+.5+stop.exit().getStepX()*distance);approach.add(stop.approachWalkY());approach.add(stop.cabinCentre().getZ()+.5+stop.exit().getStepZ()*distance);row.add("approach",approach);
                    var control=S20MovingElevatorsAdapter.controllerPosition(resolved,stop);var call=gateway?new net.minecraft.core.BlockPos(-355,stop.walkY()+1,740):S20PhysicalElevatorDirector.exteriorCallPosition(stop);
                    row.addProperty("controller",control.toShortString());row.addProperty("call_button",call.toShortString());interfaceSpecsR43.add(row);
                }
            if(++age>(candidateTripsR45==null?15000:180000))throw new IllegalStateException("R20 lift suite timeout");
            if(DESCENT&&index==4){write(world,"");finished=true;return;}
            if((R21||R22)&&!R25&&!R40){FROM[3]=75;TO[2]=75;if(index==4&&!ALL)index=6;}
            if(index==IDS.length||R41&&index==Integer.getInteger("projectseele.r41LiftEnd",IDS.length)||R21&&index==8){write(world,"");finished=true;return;}
            if(R42&&!accessReviewed){reviewAccess(level,player,world);accessReviewed=true;}
            var spec=NervLiftPassengerSync.managedLifts(level).stream().filter(s->s.id().equals(IDS[index])).findFirst().orElseThrow();
            var from=spec.stops().stream().filter(s->s.walkY()==FROM[index]).findFirst().orElseThrow();var to=spec.stops().stream().filter(s->s.walkY()==TO[index]).findFirst().orElseThrow();
            var base=S20MovingElevatorsAdapter.controllerPosition(spec,spec.lower());level.getChunkAt(base);
            controllerPosition=base;
            if(spec.id().equals(NervLiftPassengerSync.GATEWAY)){level.getChunkAt(RegionalGatewayDirector.controllerPos(81));if(stage==0)RegionalGatewayDirector.commission(level);}
            if(!(level.getBlockEntity(base) instanceof ControllerBlockEntity c)||c.getGroup()==null)return;
            var group=c.getGroup();timer++;
            if(stage==0)
            {
                if(candidateTripsR45!=null)CandidateLiftTripCasesR45.verifyNative(level,spec,group,index);
                while(actualInputsR45.size()>0)actualInputsR45.remove(actualInputsR45.size()-1);
                walkingTargetR43=null;phaseR43=index+"_outside_call";
                doorArrivalTicks=0;
                ProjectSeele.LOGGER.info("R20 lift setup {} {} -> {}",spec.id(),FROM[index],TO[index]);
                var card=new net.minecraft.world.item.ItemStack(com.projectseele.registry.ModItems.TERMINAL_DOGMA_ACCESS_CARD.get());
                if(!player.getInventory().contains(card))player.getInventory().add(card);
                if(R40)player.setItemInHand(net.minecraft.world.InteractionHand.OFF_HAND,card.copy());
                player.setGameMode(GameType.CREATIVE);player.getAbilities().flying=false;player.onUpdateAbilities();
                double distance=spec.id().equals(NervLiftPassengerSync.GATEWAY)?11.5:7.5;
                if(R44)
                {
                    var face=measuredInterfaceR44(level,spec,from);
                    var seed=face.getAsJsonArray("handoff");var reader=face.getAsJsonArray("reader");var button=face.getAsJsonArray("outside_call");
                    player.teleportTo(level,seed.get(0).getAsDouble()+.5,seed.get(1).getAsDouble(),seed.get(2).getAsDouble()+.5,from.exit().getOpposite().toYRot(),0);
                    player.setGameMode(GameType.SURVIVAL);
                    walkingTargetR43=new net.minecraft.world.phys.Vec3(reader.get(0).getAsDouble()+.5,reader.get(1).getAsDouble(),reader.get(2).getAsDouble()+.5);
                    clickTargetR44=new net.minecraft.core.BlockPos(button.get(0).getAsInt(),button.get(1).getAsInt(),button.get(2).getAsInt());
                    clickPointR44=null;clickedR44=false;exteriorCallObservedR44=false;stage=10;timer=0;continuePhaseR44();return;
                }
                player.teleportTo(level,from.cabinCentre().getX()+.5+from.exit().getStepX()*distance,R43?from.approachWalkY():from.walkY(),from.cabinCentre().getZ()+.5+from.exit().getStepZ()*distance,from.exit().getOpposite().toYRot(),0);
                if(R40)
                {
                    if(R41)diagnose(level,spec,group,player,"before_call");
                    var call=spec.id().equals(NervLiftPassengerSync.GATEWAY)?new net.minecraft.core.BlockPos(-355,FROM[index]+1,740):S20PhysicalElevatorDirector.exteriorCallPosition(from);
                    require(level.getBlockState(call).getBlock() instanceof net.minecraft.world.level.block.ButtonBlock,"Missing exterior call button: "+call);
                    if(spec.id().equals(NervLiftPassengerSync.GATEWAY))RegionalGatewayDirector.request(level,FROM[index],player);
                    else require(S20MovingElevatorsAdapter.handleExternalCall(player,call),"Exterior call rejected");
                    if(R41)diagnose(level,spec,group,player,"after_call");
                }
                else if(spec.id().equals(NervLiftPassengerSync.GATEWAY))RegionalGatewayDirector.request(level,FROM[index],player);else group.onDisplayPress(FROM[index],0,player);stage=1;timer=0;
            }
            else if(stage==10)
            {
                phaseR43=index+"_walking_to_actual_call";
                require(timer<500,"Actual exterior call approach/input timed out");
                // Local useItemOn completion can precede server packet dispatch.
                // Keep this target live until the real server observer records it.
                if(!clickedR44||!exteriorCallObservedR44)return;
                walkingTargetR43=null;clickTargetR44=null;clickPointR44=null;stage=1;timer=0;
            }
            else if(stage==1)
            {
                if(R41&&timer==100)diagnose(level,spec,group,player,"waiting_100");
                if(group.isMoving()||!NervLiftPassengerSync.carPresent(level,spec,from)){doorArrivalTicks=0;require(timer<1800,"Empty cabin failed to arrive");return;}
                if(timer<30)return;
                // The native cage can settle earlier in the same server tick
                // than the landing interlock opens. Observe the completed
                // door movement before testing a human walking through it.
                if(R41&&++doorArrivalTicks<16)return;
                if(R43)
                {
                    if(walkingTargetR43==null)
                    {
                        entryHealthR43=player.getHealth();entryDamageCountR43=damageEvents.size();
                        entryStartedTimerR43=timer;
                        player.setGameMode(GameType.SURVIVAL);player.getAbilities().flying=false;player.onUpdateAbilities();
                        walkingTargetR43=new net.minecraft.world.phys.Vec3(from.cabinCentre().getX()+.5,from.walkY(),from.cabinCentre().getZ()+.5);
                    }
                    phaseR43=index+"_walking_into_car";
                    require(player.getY()>=from.walkY()-.65,"Entry fell below landing: "+player.position());
                    require(timer-entryStartedTimerR43<500,"Actual client could not enter cabin: "+player.position()+" target="+walkingTargetR43);
                    if(player.position().subtract(walkingTargetR43).horizontalDistanceSqr()>.16||Math.abs(player.getY()-from.walkY())>.2)return;
                    walkingTargetR43=null;stage=2;timer=0;minimumFloorError=100;maximumWallOverflow=0;return;
                }
                if(R41)probeOpenLanding(level,from);
                double half=group.getCageSizeX()*.5D;
                player.teleportTo(level,from.cabinCentre().getX()+.5+half-1.36,from.walkY(),from.cabinCentre().getZ()+.5+half-1.36,180,0);
                player.setHealth(player.getMaxHealth());
                player.setGameMode(GameType.SURVIVAL);player.getAbilities().flying=false;player.onUpdateAbilities();
                stage=2;timer=0;minimumFloorError=100;maximumWallOverflow=0;
            }
            else if(stage==2)
            {
                if(R44)
                {
                    if(timer==1)prepareCarControlR44(level,spec,group,from,to);
                    if(timer==100)diagnose(level,spec,group,player,"r44_car_input_wait_100");
                    if(timer==499){var stalled=new JsonObject();stalled.addProperty("point","r44_car_input_stalled");stalled.addProperty("clicked",clickedR44);stalled.addProperty("player",player.position().toString());stalled.addProperty("walk_target",String.valueOf(walkingTargetR43));stalled.addProperty("click_target",String.valueOf(clickTargetR44));stalled.addProperty("pixel",String.valueOf(clickPointR44));diagnosticStates.add(stalled);ProjectSeele.LOGGER.info("R44 stalled actual car input {}",stalled);}
                    if(group.isMoving()){clickTargetR44=null;clickPointR44=null;walkingTargetR43=null;stage=3;timer=0;moving=true;}
                    require(timer<500,"Actual in-car destination input did not depart");return;
                }
                // Start immediately after entry, including the old five-tick gap.
                if(timer==1){player.setGameMode(R43?GameType.SURVIVAL:GameType.CREATIVE);phaseR43=index+"_ride";if(spec.id().equals(NervLiftPassengerSync.GATEWAY))
                    {
                        boolean accepted=RegionalGatewayDirector.request(level,TO[index],player);
                        if(!accepted)
                        {
                            var anchor=group.getCageAnchorBlockPos(FROM[index]);var target=group.getCageAnchorBlockPos(TO[index]);var blocks=new TreeMap<String,Integer>();
                            for(var q:net.minecraft.core.BlockPos.betweenClosed(target,target.offset(14,8,14)))if(!level.getBlockState(q).isAir())blocks.merge(q.toShortString()+" "+level.getBlockState(q),1,Integer::sum);
                            ProjectSeele.LOGGER.error("R20 gateway diagnostic available={} sourceRule={} nativeCapture={} destinationBlocks={} controller={}",group.isCageAvailableAt(group.getFloorNumber(FROM[index]),true,player),S20MovingElevatorsAdapter.validCommandCageSource(level,group,anchor),com.supermartijn642.movingelevators.elevator.ElevatorCage.canCreateCage(level,anchor,15,9,15,player),blocks,level.getBlockEntity(RegionalGatewayDirector.controllerPos(TO[index])));
                        }
                    }
                    else group.onDisplayPress(TO[index],0,player);player.setGameMode(GameType.SURVIVAL);}
                if(group.isMoving()){stage=3;timer=0;moving=true;}
                require(timer<140,"Loaded cabin did not depart");
            }
            else if(stage==3)
            {
                tripAge=timer;
                if(group.isMoving())
                {
                    AABB b=group.getCage().bounds.move(group.getCageAnchorPos(group.getCurrentY()));double floor=b.minY+1;
                    double err=player.getY()-floor;minimumFloorError=Math.min(minimumFloorError,err);
                    double over=Math.max(Math.max(b.minX-player.getX(),player.getX()-b.maxX),Math.max(b.minZ-player.getZ(),player.getZ()-b.maxZ));maximumWallOverflow=Math.max(maximumWallOverflow,over);
                    require(err>-.35,"Passenger escaped below native floor: "+err);require(over<.35,"Passenger escaped lateral cabin: "+over);require(player.isAlive(),"Passenger died");
                }
                else
                {
                    moving=false;require(NervLiftPassengerSync.carPresent(level,spec,to),"Wrong arrival floor");
                    require(Math.abs(player.getY()-to.walkY())<1.8,"Passenger did not arrive with cabin");
                    require(level.noCollision(player,player.getBoundingBox().deflate(.03)),"Arrived inside cabin wall");
                    require(R43?player.getHealth()>=entryHealthR43-.01&&damageEvents.size()==entryDamageCountR43:player.getHealth()>=player.getMaxHealth()-.01,"Passenger took collision or fall damage");
                    JsonObject r=new JsonObject();r.addProperty("lift",IDS[index]);r.addProperty("from",FROM[index]);r.addProperty("to",TO[index]);r.addProperty("minFloorError",minimumFloorError);r.addProperty("maxLateralOverflow",maximumWallOverflow);r.addProperty("ticks",timer);r.addProperty("passed",true);
                    if(R43){pendingTripR43=r;stage=4;timer=0;doorArrivalTicks=0;phaseR43=index+"_arrival_wait";return;}
                    results.add(r);
                    ProjectSeele.LOGGER.info("R20 native lift passenger pass {} {} -> {}",IDS[index],FROM[index],TO[index]);index++;stage=0;timer=0;
                }
                require(timer<1800,"Passenger trip stalled");
            }
            else if(R43&&stage==4)
            {
                if(++doorArrivalTicks<16)return;
                double distance=spec.id().equals(NervLiftPassengerSync.GATEWAY)?11.5:7.5;
                if (R44)
                {
                    // Arrival must end on the same measured public handoff
                    // used for an actual exterior call. The old generic 7.5m
                    // endpoint landed on the command-office upper stair's
                    // half step at Z314, despite the snapshot resolving its
                    // actual complete flat approach to Z315.
                    var measuredExit = measuredInterfaceR44(level, spec, to);
                    var handoff = measuredExit.getAsJsonArray("handoff");
                    walkingTargetR43 = new net.minecraft.world.phys.Vec3(
                            handoff.get(0).getAsDouble() + .5,
                            handoff.get(1).getAsDouble(),
                            handoff.get(2).getAsDouble() + .5);
                    if (doorArrivalTicks == 16)
                    {
                        var proof = new JsonObject();
                        proof.addProperty("point", "r44_actual_exit_plan");
                        proof.addProperty("lift", spec.id());
                        proof.addProperty("target", walkingTargetR43.toString());
                        proof.add("measured_handoff", handoff.deepCopy());
                        proof.addProperty("legacy_generic_target", new net.minecraft.world.phys.Vec3(
                                to.cabinCentre().getX() + .5 + to.exit().getStepX() * distance,
                                to.approachWalkY(),
                                to.cabinCentre().getZ() + .5 + to.exit().getStepZ() * distance).toString());
                        diagnosticStates.add(proof);
                    }
                }
                else
                {
                    walkingTargetR43=new net.minecraft.world.phys.Vec3(to.cabinCentre().getX()+.5+to.exit().getStepX()*distance,to.approachWalkY(),to.cabinCentre().getZ()+.5+to.exit().getStepZ()*distance);
                }
                phaseR43=index+"_walking_out_of_car";
                if(R44 && (timer==100 || timer==499))
                    diagnosticStates.add(collisionWitnessR44(level,player,walkingTargetR43,"server_exit_"+timer));
                require(player.isAlive()&&player.getY()>=to.walkY()-.65,"Exit fell below landing: "+player.position());
                require(timer<500,"Actual client could not leave cabin: "+player.position()+" target="+walkingTargetR43);
                if(player.position().subtract(walkingTargetR43).horizontalDistanceSqr()>.16||Math.abs(player.getY()-to.approachWalkY())>.2)return;
                walkingTargetR43=null;pendingTripR43.addProperty("actual_client_entry",true);pendingTripR43.addProperty("actual_client_exit",true);
                require(player.getHealth()>=entryHealthR43-.01&&damageEvents.size()==entryDamageCountR43,"Passenger lost health during exit");
                pendingTripR43.addProperty("entry_health",entryHealthR43);pendingTripR43.addProperty("exit_health",player.getHealth());
                pendingTripR43.addProperty("from_approach_y",from.approachWalkY());pendingTripR43.addProperty("to_approach_y",to.approachWalkY());
                pendingTripR43.addProperty("outside_call","native button handler with real player and card permissions");
                if(R44)
                {
                    var support = exitSupportWitnessR44(level, player, spec.id(), to.walkY());
                    diagnosticStates.add(support);
                    require(player.onGround(),"Actual exit has no grounded passenger");
                    require(support.get("complete_actual_footprint_bearing").getAsBoolean(),
                            "Actual exit has no complete physical floor beneath the passenger");
                    require(level.noCollision(player,player.getBoundingBox().deflate(.03)),"Actual exit has body obstruction");
                    pendingTripR43.addProperty("actual_client_call_click",true);pendingTripR43.addProperty("actual_client_car_selection",true);
                    pendingTripR43.addProperty("grounded_exit",true);completedSourcesR44.add(spec.id()+"/"+FROM[index]);
                }
                if(candidateTripsR45!=null)
                {
                    var caseProof=CandidateLiftTripCasesR45.evidence(index);
                    caseProof.addProperty("actual_player_uuid",player.getUUID().toString());
                    caseProof.addProperty("native_verified",true);
                    caseProof.add("actual_server_inputs",actualInputsR45.deepCopy());
                    boolean call=false,selection=false;
                    for(var raw:actualInputsR45)
                    {
                        var input=raw.getAsJsonObject();
                        call|=input.get("stage").getAsInt()==10;
                        selection|=input.get("stage").getAsInt()==2;
                    }
                    require(call&&selection,"Completed ride lacks real server exterior-call or car-selection input");
                    caseProof.addProperty("same_jvm_reload","UNVERIFIED");
                    caseProof.addProperty("cold_reload","UNVERIFIED");
                    caseProof.addProperty("save_interrupt","UNVERIFIED");
                    caseProof.addProperty("two_clients","UNVERIFIED");
                    pendingTripR43.add("candidate_case",caseProof);
                }
                results.add(pendingTripR43);pendingTripR43=null;
                ProjectSeele.LOGGER.info("R43 complete lift passage {} {} -> {}",IDS[index],FROM[index],TO[index]);index++;stage=0;timer=0;
            }
        }
        catch(Exception failure)
        {
            ProjectSeele.LOGGER.error("R20 lift passenger review failed",failure);walkingTargetR43=null;moving=false;finished=true;write(world,failure.toString());
        }
    }
    public static JsonObject collisionWitnessR44(net.minecraft.world.level.Level level,
            net.minecraft.world.entity.Entity actor,net.minecraft.world.phys.Vec3 target,String side)
    {
        var row=new JsonObject();row.addProperty("point","r44_blocked_walk_"+side);row.addProperty("phase",phaseR43);
        row.addProperty("position",actor.position().toString());row.addProperty("target",target.toString());
        row.addProperty("bounding_box",actor.getBoundingBox().toString());row.addProperty("on_ground",actor.onGround());
        row.addProperty("horizontal_collision",actor.horizontalCollision);
        var direction=target.subtract(actor.position());direction=new net.minecraft.world.phys.Vec3(direction.x,0,direction.z).normalize().scale(.8);
        var query=actor.getBoundingBox().expandTowards(direction).deflate(.001);
        var blocks=new JsonArray();var queryShape=net.minecraft.world.phys.shapes.Shapes.create(query);
        for(var pos:net.minecraft.core.BlockPos.betweenClosed(net.minecraft.core.BlockPos.containing(query.minX,query.minY,query.minZ),
                net.minecraft.core.BlockPos.containing(query.maxX,query.maxY,query.maxZ)))
        {
            var state=level.getBlockState(pos);var shape=state.getCollisionShape(level,pos,net.minecraft.world.phys.shapes.CollisionContext.of(actor));
            if(shape.isEmpty())continue;
            var placed=shape.move(pos.getX(),pos.getY(),pos.getZ());
            if(!net.minecraft.world.phys.shapes.Shapes.joinIsNotEmpty(placed,queryShape,net.minecraft.world.phys.shapes.BooleanOp.AND))continue;
            var hit=new JsonObject();hit.addProperty("position",pos.toShortString());hit.addProperty("state",state.toString());
            hit.addProperty("shape",placed.toAabbs().toString());blocks.add(hit);
        }
        row.add("swept_block_obstacles",blocks);var entities=new JsonArray();
        for(var shape:level.getEntityCollisions(actor,query))entities.add(shape.toAabbs().toString());
        row.add("swept_entity_obstacles",entities);
        ProjectSeele.LOGGER.info("R44 real blocked walk {}",row);return row;
    }
    private static JsonObject exitSupportWitnessR44(ServerLevel level,
            ServerPlayer player, String lift, int cabinY)
    {
        var proof = new JsonObject();
        proof.addProperty("point", "r44_actual_exit_support");
        proof.addProperty("index", index);
        proof.addProperty("lift", lift);
        proof.addProperty("cabin_y", cabinY);
        proof.addProperty("player", player.position().toString());
        proof.addProperty("on_ground", player.onGround());
        proof.addProperty("velocity", player.getDeltaMovement().toString());
        var rays = new JsonArray();
        boolean completeBearing = true;
        for (double dx : new double[] {-.25, 0, .25})
        {
            for (double dz : new double[] {-.25, 0, .25})
            {
                var start = player.position().add(dx, .10, dz);
                var end = player.position().add(dx, -.65, dz);
                var hit = level.clip(new net.minecraft.world.level.ClipContext(
                        start, end, net.minecraft.world.level.ClipContext.Block.COLLIDER,
                        net.minecraft.world.level.ClipContext.Fluid.NONE, player));
                var ray = new JsonObject();
                ray.addProperty("start", start.toString());
                ray.addProperty("hit", hit.getType().name());
                ray.addProperty("face", hit.getDirection().getName());
                ray.addProperty("position", hit.getBlockPos().toShortString());
                ray.addProperty("location", hit.getLocation().toString());
                ray.addProperty("state", level.getBlockState(hit.getBlockPos()).toString());
                boolean bearing = hit.getType() == net.minecraft.world.phys.HitResult.Type.BLOCK
                        && hit.getDirection() == net.minecraft.core.Direction.UP
                        && Math.abs(hit.getLocation().y - player.getY()) < .03;
                ray.addProperty("bearing_at_actual_feet", bearing);
                completeBearing &= bearing;
                rays.add(ray);
            }
        }
        proof.add("nine_real_collision_rays", rays);
        proof.addProperty("complete_actual_footprint_bearing", completeBearing);
        return proof;
    }
    private static void continuePhaseR44(){phaseR43=index+"_walking_to_actual_call";}
    private static JsonObject measuredInterfaceR44(ServerLevel level,S20PhysicalElevatorDirector.LiftSpec spec,S20PhysicalElevatorDirector.Landing stop)throws Exception
    {
        if(measuredInterfacesR44==null)
        {
            String file=System.getProperty("projectseele.r44LiftInterfaces","");
            require(!file.isBlank(),"r44LiftInterfaces must identify the current measured 7-column/24-stop JSON");
            measuredInterfacesR44=JsonParser.parseString(Files.readString(Path.of(file))).getAsJsonArray();
            require(measuredInterfacesR44.size()==7,"R44 measured lift denominator must be seven");
            int stops=0;for(var lift:measuredInterfacesR44)stops+=lift.getAsJsonObject().getAsJsonArray("landings").size();
            require(stops==24,"R44 measured stop denominator must be twenty-four");
        }
        var controller=S20MovingElevatorsAdapter.controllerPosition(spec,stop);
        for(var lift:measuredInterfacesR44)for(var row:lift.getAsJsonObject().getAsJsonArray("landings"))
        {
            var r=row.getAsJsonObject();var a=r.getAsJsonArray("controller");
            if(a.get(0).getAsInt()==controller.getX()&&a.get(1).getAsInt()==controller.getY()&&a.get(2).getAsInt()==controller.getZ())
            {require(r.has("outside_call_path")&&!r.get("outside_call_path").isJsonNull(),"Measured exterior approach unresolved");return r;}
        }
        throw new IllegalStateException("Current native stop has no measured R44 interface: "+controller);
    }
    private static void prepareCarControlR44(ServerLevel level,S20PhysicalElevatorDirector.LiftSpec spec,com.supermartijn642.movingelevators.elevator.ElevatorGroup group,S20PhysicalElevatorDirector.Landing from,S20PhysicalElevatorDirector.Landing to)
    {
        clickTargetR44=null;clickPointR44=null;clickedR44=false;phaseR43=index+"_actual_car_floor_selection";
        if(spec.id().equals(NervLiftPassengerSync.GATEWAY))
        {
            // These are the real two gateway car buttons, independent of the
            // surface reader and the large 7x5 checkpoint aperture.
            clickTargetR44=new net.minecraft.core.BlockPos(-366,from.walkY()+1,to.walkY()==81?750:747);
            walkingTargetR43=new net.minecraft.world.phys.Vec3(-364.5,from.walkY(),clickTargetR44.getZ()+.5);return;
        }
        for(var pos:net.minecraft.core.BlockPos.betweenClosed(from.cabinCentre().offset(-4,1,-4),from.cabinCentre().offset(4,4,4)))
        {
            if(!(level.getBlockEntity(pos) instanceof com.supermartijn642.movingelevators.blocks.DisplayBlockEntity display))continue;
            var input=display.getInputBlockEntity();int category=display.getDisplayCategory();
            if(input==null||!input.hasGroup()||input.getGroup()!=group||category<1||category>2)continue;
            int current=group.getFloorNumber(input.getFloorLevel()),target=group.getFloorNumber(to.walkY()),limit=category==1?3:7,span=category==1?1:2;
            int below=current,above=group.getFloorCount()-current-1;
            if(below<above){below=Math.min(below,limit);above=Math.min(above,limit*2-below);}
            else{above=Math.min(above,limit);below=Math.min(below,limit*2-above);}
            int first=current-below,count=below+1+above;
            if(target<first||target>=first+count)
            {
                var unavailable = new JsonObject();
                unavailable.addProperty("point", "r44_real_display_row_unavailable");
                unavailable.addProperty("position", pos.toShortString());
                unavailable.addProperty("category", category);
                unavailable.addProperty("native_floor_count", group.getFloorCount());
                unavailable.addProperty("current_index", current);
                unavailable.addProperty("target_index", target);
                unavailable.addProperty("row_first", first);
                unavailable.addProperty("row_count", count);
                unavailable.addProperty("above_state", level.getBlockState(pos.above()).toString());
                diagnosticStates.add(unavailable);
                continue;
            }
            double raw=(span-count*.125)/2+(target-first+.5)*.125;
            var selected=raw<1?pos.immutable():pos.above();double localY=raw<1?raw:raw-1;
            var facing=display.getFacing();var shape=level.getBlockState(selected).getShape(level,selected);
            require(!shape.isEmpty(),"Official car display has no physical selection outline");var b=shape.bounds();
            double x=.5,z=.5;
            if(facing.getAxis()==net.minecraft.core.Direction.Axis.X)x=facing.getStepX()>0?b.maxX-.005:b.minX+.005;
            else z=facing.getStepZ()>0?b.maxZ-.005:b.minZ+.005;
            clickTargetR44=selected;clickPointR44=new net.minecraft.world.phys.Vec3(selected.getX()+x,selected.getY()+localY,selected.getZ()+z);
            walkingTargetR43=new net.minecraft.world.phys.Vec3(selected.getX()+.5+facing.getStepX()*1.5,from.walkY(),selected.getZ()+.5+facing.getStepZ()*1.5);
            var proof=new JsonObject();proof.addProperty("point","r44_car_input_plan");proof.addProperty("display",pos.toShortString());proof.addProperty("selected_display",selected.toShortString());proof.addProperty("category",category);proof.addProperty("facing",facing.getName());proof.addProperty("input_floor",input.getFloorLevel());proof.addProperty("current_index",current);proof.addProperty("target_index",target);proof.addProperty("row_first",first);proof.addProperty("row_count",count);proof.addProperty("raw_y",raw);proof.addProperty("pixel",clickPointR44.toString());proof.addProperty("operator_target",walkingTargetR43.toString());proof.addProperty("outline",b.toString());diagnosticStates.add(proof);ProjectSeele.LOGGER.info("R44 actual car display plan {}",proof);return;
        }
        throw new IllegalStateException("No installed native car display exposes the requested destination in occupied cabin "+spec.id());
    }
    @SubscribeEvent(priority=net.minecraftforge.eventbus.api.EventPriority.LOWEST,receiveCanceled=true)
    public static void observedInputR44(net.minecraftforge.event.entity.player.PlayerInteractEvent.RightClickBlock event)
    {
        if(!R44||finished||!(event.getEntity() instanceof ServerPlayer player)||clickTargetR44==null||!event.getPos().equals(clickTargetR44))return;
        var proof=new JsonObject();proof.addProperty("point","r44_actual_server_right_click");proof.addProperty("position",event.getPos().toShortString());proof.addProperty("hit",event.getHitVec().getLocation().toString());proof.addProperty("face",String.valueOf(event.getFace()));proof.addProperty("canceled",event.isCanceled());proof.addProperty("hand",event.getHand().name());proof.addProperty("player",player.position().toString());
        if(player.serverLevel().getBlockEntity(event.getPos()) instanceof com.supermartijn642.movingelevators.blocks.DisplayBlockEntity display)
        {
            var input=display.getInputBlockEntity();int category=display.getDisplayCategory();proof.addProperty("category",category);proof.addProperty("native_facing",String.valueOf(display.getFacing()));
            if(input!=null&&input.hasGroup())
            {
                var group=input.getGroup();int current=group.getFloorNumber(input.getFloorLevel()),limit=category==1?3:7,span=category==1?1:2;
                int below=current,above=group.getFloorCount()-current-1;
                if(below<above){below=Math.min(below,limit);above=Math.min(above,limit*2-below);}else{above=Math.min(above,limit);below=Math.min(below,limit*2-above);}
                double local=event.getHitVec().getLocation().y-event.getPos().getY()+(category==3?1:0);int offset=(int)Math.floor((local-(span-(below+1+above)*.125)/2)/.125)-below;
                proof.addProperty("input_floor",input.getFloorLevel());proof.addProperty("decoded_offset",offset);proof.addProperty("decoded_target_index",current+offset);
            }
        }
        proof.addProperty("case_index",index);proof.addProperty("stage",stage);proof.addProperty("phase",phaseR43);
        proof.addProperty("cancellation_result",event.getCancellationResult().name());
        if(candidateTripsR45!=null)actualInputsR45.add(proof.deepCopy());
        if(stage==10)exteriorCallObservedR44=true;
        diagnosticStates.add(proof);ProjectSeele.LOGGER.info("R44 observed real input {}",proof);
    }
    private static void probeOpenLanding(ServerLevel level,S20PhysicalElevatorDirector.Landing landing)
    {
        var centre=landing.cabinCentre();var exit=landing.exit();
        var actor=net.minecraftforge.common.util.FakePlayerFactory.get(level,new com.mojang.authlib.GameProfile(UUID.fromString("9cd03169-9577-4cd3-9d23-8614ae2b0941"),"r41_lift_entry"));
        double x=centre.getX()+.5+exit.getStepX()*7.5,z=centre.getZ()+.5+exit.getStepZ()*7.5;
        var start=new net.minecraft.world.phys.Vec3(x,landing.walkY()+2,z);
        var hit=level.clip(new net.minecraft.world.level.ClipContext(start,start.add(0,-5,0),net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,actor));
        require(hit.getType()!=net.minecraft.world.phys.HitResult.Type.MISS,"No approach floor outside lift "+landing.label());
        actor.setPos(x,hit.getLocation().y,z);actor.setOnGround(true);actor.setDeltaMovement(net.minecraft.world.phys.Vec3.ZERO);
        require(level.noCollision(actor,actor.getBoundingBox()),"Lift approach starts in an obstruction");
        double velocity=0;int stalled=0;
        for(int n=0;n<300;n++)
        {
            var before=actor.position();double dx=centre.getX()+.5-before.x,dz=centre.getZ()+.5-before.z,range=Math.hypot(dx,dz);
            if(range<.18&&actor.onGround())
            {require(Math.abs(before.y-landing.walkY())<.18,"Lift entry arrived at wrong floor");return;}
            velocity=(velocity-.08)*.98;double step=Math.min(.12,range);
            actor.move(net.minecraft.world.entity.MoverType.SELF,new net.minecraft.world.phys.Vec3(range<.001?0:dx/range*step,velocity,range<.001?0:dz/range*step));
            if(actor.onGround())velocity=0;
            require(actor.getY()>=landing.walkY()-.65,"Unprotected gap between gallery and lift car");
            stalled=actor.position().distanceToSqr(before)<1e-8?stalled+1:0;
            require(stalled<10,"Open lift doorway is not physically walkable: "+landing.label()+" "+actor.position());
        }
        throw new IllegalStateException("Lift entry collision sweep timed out");
    }
    private static void write(Path world,String error)
    {
        try{JsonObject r=new JsonObject();r.addProperty("error",error);r.add("trips",results);r.add("damage",damageEvents);r.add("diagnostics",diagnosticStates);if(R43)r.add("resolved_interfaces",interfaceSpecsR43);
            if(R44){r.addProperty("required_source_stops",24);r.addProperty("completed_source_stops",completedSourcesR44.size());r.addProperty("full_current_run_pass",error.isEmpty()&&completedSourcesR44.size()==24&&(candidateTripsR45==null||results.size()==90));r.addProperty("required_directed_pairs",candidateTripsR45==null?IDS.length:90);r.addProperty("completed_directed_pairs",results.size());r.addProperty("full_lifecycle_pass",false);r.addProperty("save_interrupt","UNVERIFIED");r.addProperty("two_clients","UNVERIFIED");if(candidateTripsR45!=null){r.addProperty("candidate_binding_sha256",candidateTripsR45.get("candidate_binding_sha256").getAsString());r.addProperty("declared_session_phase",System.getProperty("projectseele.r45LiftLifecyclePhase","current_native_function"));}r.addProperty("same_jvm_reload","UNVERIFIED");r.addProperty("cold_reload","UNVERIFIED");r.addProperty("inherited","NOT_USED");r.add("completed_sources",new Gson().toJsonTree(completedSourcesR44));}
            String requested=System.getProperty("projectseele.r45LiftOutput", "");
            if(candidateTripsR45!=null)
            {
                require(!requested.isBlank(),"Candidate lift receipt must use a unique artifact path");
                Path output=Path.of(requested).toAbsolutePath().normalize();
                require(!output.startsWith(world.toRealPath())&&!Files.exists(output),"Candidate lift receipt cannot overwrite a world or earlier run");
                Files.createDirectories(output.getParent());
                Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(r),StandardOpenOption.CREATE_NEW);
            }
            else Files.writeString(world.resolve(R44?"r44_lift_review.json":"r20_lift_review.json"),r.toString());}catch(Exception x){throw new IllegalStateException(x);}
    }
    private static void diagnose(ServerLevel level,S20PhysicalElevatorDirector.LiftSpec spec,com.supermartijn642.movingelevators.elevator.ElevatorGroup group,ServerPlayer player,String point)
    {
        if(Boolean.getBoolean("projectseele.r41LiftNoDiagnostics"))return;
        JsonObject r=new JsonObject();r.addProperty("point",point);r.addProperty("lift",spec.id());r.addProperty("currentY",group.getCurrentY());r.addProperty("moving",group.isMoving());
        var nativeFloors=new JsonArray();for(int i=0;i<group.getFloorCount();i++)nativeFloors.add(group.getFloorYLevel(i));r.add("native_registered_floors",nativeFloors);
        if(R43&&!Boolean.getBoolean("projectseele.r43DeepLiftDiagnosis"))
        {
            // Reading block/cage availability can load an adjacent chunk and
            // initialize the very controller whose cold-start race is tested.
            diagnosticStates.add(r);ProjectSeele.LOGGER.info("R43 passive lift state {}",r);return;
        }
        JsonArray stops=new JsonArray();
        for(var landing:spec.stops())
        {
            var at=group.getCageAnchorBlockPos(landing.walkY());JsonObject row=new JsonObject();row.addProperty("floor",landing.walkY());row.addProperty("anchor",at.toShortString());
            row.addProperty("car_present",NervLiftPassengerSync.carPresent(level,spec,landing));
            row.addProperty("source_valid",S20MovingElevatorsAdapter.validCommandCageSource(level,group,at));
            row.addProperty("native_capture",com.supermartijn642.movingelevators.elevator.ElevatorCage.canCreateCage(level,at,group.getCageSizeX(),group.getCageSizeY(),group.getCageSizeZ(),player));stops.add(row);
        }
        r.add("stops",stops);diagnosticStates.add(r);ProjectSeele.LOGGER.info("R41 lift diagnostic {}",r);
    }
}

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
    private static final boolean R42="r42-lifts".equals(System.getProperty("projectseele.regionalBuild",""));
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
    private static int age,index=R40?Integer.getInteger("projectseele.r40LiftStart",0):DESCENT?3:R21?2:"r20-lift-rest".equals(System.getProperty("projectseele.regionalBuild",""))?4:0,stage,timer,doorArrivalTicks;
    private static final JsonArray results=new JsonArray();
    private static final JsonArray damageEvents=new JsonArray();
    private static final JsonArray diagnosticStates=new JsonArray();
    @SubscribeEvent public static void hurt(net.minecraftforge.event.entity.living.LivingHurtEvent e)
    {
        if(!ENABLED||finished||!(e.getEntity() instanceof ServerPlayer p))return;
        JsonObject r=new JsonObject();r.addProperty("source",e.getSource().getMsgId());r.addProperty("amount",e.getAmount());r.addProperty("stage",stage);r.addProperty("timer",timer);r.addProperty("lift",IDS[Math.min(index,IDS.length-1)]);r.addProperty("position",p.position().toString());r.addProperty("fallDistance",p.fallDistance);
        JsonArray blocks=new JsonArray();for(var q:net.minecraft.core.BlockPos.betweenClosed(p.blockPosition().offset(-1,0,-1),p.blockPosition().offset(1,2,1)))if(!p.level().getBlockState(q).isAir())blocks.add(q.toShortString()+" "+p.level().getBlockState(q));r.add("nearbyBlocks",blocks);damageEvents.add(r);
        ProjectSeele.LOGGER.warn("R21 LIFT DAMAGE {}",r);
    }
    private static double minimumFloorError=100,maximumWallOverflow;
    private static final String[] IDS=R40?tripsR40().stream().map(Trip::id).toArray(String[]::new):R26?new String[]{FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.OBSERVATION,FacilityLiftsR25.OBSERVATION}:R25?new String[]{FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.EAST,FacilityLiftsR25.OBSERVATION,FacilityLiftsR25.OBSERVATION}:new String[]{S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID,S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID,S20PhysicalElevatorDirector.SURFACE_TRANSIT_LIFT_ID,S20PhysicalElevatorDirector.SURFACE_TRANSIT_LIFT_ID,NervLiftPassengerSync.GATEWAY,NervLiftPassengerSync.GATEWAY,S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID,S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID,S20PhysicalElevatorDirector.COMMANDER_OFFICE_LIFT_ID,S20PhysicalElevatorDirector.COMMANDER_OFFICE_LIFT_ID};
    private static final int[] FROM=R40?tripsR40().stream().mapToInt(Trip::from).toArray():R26?new int[]{-461,-364,-448,-434,-420,-406,-392,-378,-394,-367}:R25?new int[]{-448,-392,-434,-420,-406,-448,-394,-367}:new int[]{-566,-448,-442,81,-466,81,-442,-370,-388,-340};
    private static final int[] TO=R40?tripsR40().stream().mapToInt(Trip::to).toArray():R26?new int[]{-364,-448,-434,-420,-406,-392,-378,-461,-367,-394}:R25?new int[]{-392,-434,-420,-406,-448,-434,-367,-394}:new int[]{-448,-566,81,-442,81,-466,-370,-394,-340,-388};
    private record Trip(String id,int from,int to) {}
    private static List<Trip> tripsR40()
    {
        var trips=new ArrayList<Trip>();
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
        Path world=e.getServer().getWorldPath(LevelResource.ROOT).normalize();require(world.getFileName().toString().equals(R42?"SEELE_R42_MECHANICS_REVIEW":R41?"SEELE_R41_MECHANICS_REVIEW":R40?"SEELE_FIELD_R40_REVIEW":R26?"SEELE_R26_REVIEW":R25?"SEELE_R25_REVIEW":R22?"SEELE_R22_REVIEW":R21?"SEELE_R21_REVIEW":"SEELE_R20_REVIEW"),"Lift review boundary");
        var player=e.getServer().getPlayerList().getPlayers().get(0);var level=e.getServer().getLevel(FacilitySchemaV2.DIMENSION);
        try
        {
            if(++age>15000)throw new IllegalStateException("R20 lift suite timeout");
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
                doorArrivalTicks=0;
                ProjectSeele.LOGGER.info("R20 lift setup {} {} -> {}",spec.id(),FROM[index],TO[index]);
                var card=new net.minecraft.world.item.ItemStack(com.projectseele.registry.ModItems.TERMINAL_DOGMA_ACCESS_CARD.get());
                if(!player.getInventory().contains(card))player.getInventory().add(card);
                if(R40)player.setItemInHand(net.minecraft.world.InteractionHand.OFF_HAND,card.copy());
                player.setGameMode(GameType.CREATIVE);player.getAbilities().flying=false;player.onUpdateAbilities();
                double distance=spec.id().equals(NervLiftPassengerSync.GATEWAY)?11.5:7.5;
                player.teleportTo(level,from.cabinCentre().getX()+.5+from.exit().getStepX()*distance,from.walkY(),from.cabinCentre().getZ()+.5+from.exit().getStepZ()*distance,from.exit().getOpposite().toYRot(),0);
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
            else if(stage==1)
            {
                if(R41&&timer==100)diagnose(level,spec,group,player,"waiting_100");
                if(group.isMoving()||!NervLiftPassengerSync.carPresent(level,spec,from)){doorArrivalTicks=0;require(timer<1800,"Empty cabin failed to arrive");return;}
                if(timer<30)return;
                // The native cage can settle earlier in the same server tick
                // than the landing interlock opens. Observe the completed
                // door movement before testing a human walking through it.
                if(R41&&++doorArrivalTicks<16)return;
                if(R41)probeOpenLanding(level,from);
                double half=group.getCageSizeX()*.5D;
                player.teleportTo(level,from.cabinCentre().getX()+.5+half-1.36,from.walkY(),from.cabinCentre().getZ()+.5+half-1.36,180,0);
                player.setHealth(player.getMaxHealth());
                player.setGameMode(GameType.SURVIVAL);player.getAbilities().flying=false;player.onUpdateAbilities();
                stage=2;timer=0;minimumFloorError=100;maximumWallOverflow=0;
            }
            else if(stage==2)
            {
                // Start immediately after entry, including the old five-tick gap.
                if(timer==1){player.setGameMode(GameType.CREATIVE);if(spec.id().equals(NervLiftPassengerSync.GATEWAY))
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
                    require(level.noCollision(player,player.getBoundingBox().deflate(.03)),"Arrived inside cabin wall");require(player.getHealth()>=player.getMaxHealth()-.01,"Passenger took collision or fall damage");
                    JsonObject r=new JsonObject();r.addProperty("lift",IDS[index]);r.addProperty("from",FROM[index]);r.addProperty("to",TO[index]);r.addProperty("minFloorError",minimumFloorError);r.addProperty("maxLateralOverflow",maximumWallOverflow);r.addProperty("ticks",timer);r.addProperty("passed",true);results.add(r);
                    ProjectSeele.LOGGER.info("R20 native lift passenger pass {} {} -> {}",IDS[index],FROM[index],TO[index]);index++;stage=0;timer=0;
                }
                require(timer<1800,"Passenger trip stalled");
            }
        }
        catch(Exception failure)
        {
            ProjectSeele.LOGGER.error("R20 lift passenger review failed",failure);moving=false;finished=true;write(world,failure.toString());
        }
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
        try{JsonObject r=new JsonObject();r.addProperty("error",error);r.add("trips",results);r.add("damage",damageEvents);r.add("diagnostics",diagnosticStates);Files.writeString(world.resolve("r20_lift_review.json"),r.toString());}catch(Exception x){throw new IllegalStateException(x);}
    }
    private static void diagnose(ServerLevel level,S20PhysicalElevatorDirector.LiftSpec spec,com.supermartijn642.movingelevators.elevator.ElevatorGroup group,ServerPlayer player,String point)
    {
        if(Boolean.getBoolean("projectseele.r41LiftNoDiagnostics"))return;
        JsonObject r=new JsonObject();r.addProperty("point",point);r.addProperty("lift",spec.id());r.addProperty("currentY",group.getCurrentY());r.addProperty("moving",group.isMoving());
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

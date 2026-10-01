package com.projectseele.client.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.visual.RegionalNativeTransitInspection;
import com.projectseele.world.FacilitySchemaV2;
import net.minecraft.client.Minecraft;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;
import java.util.function.Consumer;

/** Every configured native platform is a separate real boarding/arrival case.
 * The only teleports are initial outside staging and final player restoration.
 * Attachment, movement, doors, route positions and detachment remain native. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class RegionalTransitR44Checks
{
    private static final boolean ENABLED="r44-transit-all".equals(System.getProperty("projectseele.regionalBuild",""));
    private static JsonArray cases;private static final JsonArray results=new JsonArray();
    private static final Set<String> completed=new LinkedHashSet<>();
    private static int index,end,stage,ticks,stageTicks,walkIndex,exitTicks;private static boolean started,done;
    private static volatile boolean staged,serverRiding,serverDetached;private static volatile String serverFailure="";
    private static volatile String clientFailure="";
    private static final JsonArray motionHistory=new JsonArray();
    private static Path world;private static JsonObject current;private static long vehicleId;
    private static Object vehicle,cache,car;private static RegionalTransitRidingChecks.NativeDoorway doorway;
    private static List<Vec3> walk=List.of();private static Vec3 departure,previousRendered;
    private static long motionNanos;private static double simulationSeconds,previousSpeed,maxFrameStep,travel;
    private static float health;private static JsonObject result;
    private static GameType oldMode;private static Vec3 oldPosition;private static float oldYaw,oldPitch;
    private static net.minecraft.resources.ResourceKey<net.minecraft.world.level.Level> oldDimension;
    private static boolean oldFlying,oldPause;private static int oldDistance;
    private static volatile JsonObject serverStageEvidence;
    private static volatile JsonObject serverArrivalEvidence;
    private static boolean arrivalSupported;
    private static int stagingAcknowledgedAt=-1;
    private static boolean survivalRequested;
    private static boolean clientChunkLoaded(Minecraft mc,BlockPos point)
    {return mc.level.getChunkSource().hasChunk(point.getX()>>4,point.getZ()>>4);}

    private static Object call(Object a,String name)throws Exception{return a.getClass().getMethod(name).invoke(a);}
    private static long number(Object a,String name)throws Exception{return ((Number)call(a,name)).longValue();}
    private static Vec3 vec(JsonArray a){return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static void require(boolean ok,String why){if(!ok)throw new IllegalStateException(why);}
    private static boolean aircraft(){return "AIRPLANE".equals(current.get("mode").getAsString());}
    private static JsonObject profile(boolean destination){return current.getAsJsonObject(destination?"destination":"source");}
    private static void phase(int next)
    {stage=next;stageTicks=0;ProjectSeele.LOGGER.info("R44 TRANSIT phase={} case={}",next,current==null?"initial":current.get("id").getAsString());}
    private static void keys(Minecraft mc,boolean up,boolean shift){mc.options.keyUp.setDown(up);mc.options.keyShift.setDown(shift);mc.options.keyRight.setDown(false);mc.options.keyJump.setDown(false);}
    private static boolean onNativeVehicle()throws Exception{return (Boolean)Class.forName("org.mtr.mod.client.VehicleRidingMovement").getMethod("isRiding",long.class).invoke(null,vehicleId);}
    private static Object actualVehicle()throws Exception
    {
        Object data=Class.forName("org.mtr.mod.client.MinecraftClientData").getMethod("getInstance").invoke(null);
        for(Object v:(Iterable<?>)data.getClass().getField("vehicles").get(data))if(number(v,"getId")==vehicleId)return v;
        return null;
    }
    private static boolean stoppedAt(Object v,long platform)throws Exception
    {
        Object extra=v.getClass().getField("vehicleExtraData").get(v),persistent=v.getClass().getField("persistentVehicleData").get(v);
        return number(extra,"getThisPlatformId")==platform&&number(extra,"getThisRouteId")==Long.parseLong(current.get("route_id").getAsString())
                &&((Number)call(v,"getSpeed")).doubleValue()<.001&&((Number)call(persistent,"getDoorValue")).doubleValue()>.8;
    }
    private static boolean supported(Minecraft mc,Vec3 point)
    {
        var box=mc.player.getBoundingBox().move(point.subtract(mc.player.position()));
        if(!mc.level.noCollision(mc.player,box.deflate(.025)))return false;
        double y=point.y;
        for(double dx:new double[]{-.25,0,.25})for(double dz:new double[]{-.25,0,.25})
        {
            var start=new Vec3(point.x+dx,y+.08,point.z+dz);
            var hit=mc.level.clip(new net.minecraft.world.level.ClipContext(start,start.add(0,-.30,0),net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,mc.player));
            if(hit.getType()!=net.minecraft.world.phys.HitResult.Type.BLOCK||Math.abs(hit.getLocation().y-y)>=.15)return false;
        }
        return true;
    }
    private static boolean eligibleDoor(Minecraft mc,Vec3 p,boolean destination)
    {
        JsonObject profile=profile(destination);
        if(aircraft())return p.distanceTo(vec(profile.getAsJsonObject("air_stairs").getAsJsonArray("landing")))<5;
        Vec3 lo=vec(profile.getAsJsonArray("platform_lo")),hi=vec(profile.getAsJsonArray("platform_hi"));
        boolean xAxis="x".equals(profile.get("axis").getAsString());
        if(xAxis?(p.x<lo.x-2||p.x>hi.x+2||p.z<lo.z-2||p.z>hi.z+2):(p.z<lo.z-2||p.z>hi.z+2||p.x<lo.x-2||p.x>hi.x+2))return false;
        return supported(mc,p);
    }
    private static JsonObject stagingEvidence(Minecraft mc)throws Exception
    {
        var evidence=new JsonObject();Vec3 p=mc.player.position();
        evidence.addProperty("client_position",p.toString());evidence.addProperty("client_dimension",mc.level.dimension().location().toString());
        evidence.add("declared_position",profile(false).getAsJsonArray("staging"));evidence.addProperty("on_ground",mc.player.onGround());
        var declared=BlockPos.containing(vec(profile(false).getAsJsonArray("staging")));
        evidence.addProperty("declared_chunk_cached",clientChunkLoaded(mc,declared));
        evidence.addProperty("declared_floor_state",mc.level.getBlockState(declared.below()).toString());
        evidence.addProperty("client_min_build_height",mc.level.getMinBuildHeight());
        evidence.addProperty("client_max_build_height",mc.level.getMaxBuildHeight());
        evidence.addProperty("client_mode",mc.gameMode.getPlayerMode().getName());
        evidence.addProperty("pose",mc.player.getPose().name());evidence.addProperty("bbox",mc.player.getBoundingBox().toString());
        evidence.addProperty("body_clear",mc.level.noCollision(mc.player,mc.player.getBoundingBox().deflate(.025)));
        evidence.addProperty("vanilla_vehicle",mc.player.getVehicle()==null?"none":mc.player.getVehicle().toString());
        if(serverStageEvidence!=null)evidence.add("server_initial_stage",serverStageEvidence.deepCopy());
        var feet=new JsonArray();
        for(double dx:new double[]{-.25,0,.25})for(double dz:new double[]{-.25,0,.25})
        {
            var start=p.add(dx,.08,dz);var hit=mc.level.clip(new net.minecraft.world.level.ClipContext(start,start.add(0,-.30,0),net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,mc.player));
            var sample=new JsonObject();sample.addProperty("from",start.toString());sample.addProperty("hit",hit.getType().name());
            sample.addProperty("at",hit.getLocation().toString());sample.addProperty("block",hit.getBlockPos().toShortString());
            sample.addProperty("state",mc.level.getBlockState(hit.getBlockPos()).toString());feet.add(sample);
        }
        evidence.add("nine_real_floor_rays",feet);var riders=new JsonArray();
        Object data=Class.forName("org.mtr.mod.client.MinecraftClientData").getMethod("getInstance").invoke(null);
        for(Object v:(Iterable<?>)data.getClass().getField("vehicles").get(data))
        {
            long id=number(v,"getId");
            if((Boolean)Class.forName("org.mtr.mod.client.VehicleRidingMovement").getMethod("isRiding",long.class).invoke(null,id))
            {var item=new JsonObject();item.addProperty("id",id);item.addProperty("speed",((Number)call(v,"getSpeed")).doubleValue());riders.add(item);}
        }
        evidence.add("native_registered_vehicles",riders);return evidence;
    }
    private static Object resourceCache(Object v,Object selectedCar)throws Exception
    {
        Object extra=v.getClass().getField("vehicleExtraData").get(v);var cars=(List<?>)extra.getClass().getField("immutableVehicleCars").get(extra);
        Class<?> transport=Class.forName("org.mtr.core.data.TransportMode");Object mode=transport.getField(current.get("mode").getAsString()).get(null);
        String id=(String)call(selectedCar,"getVehicleId");Object[] holder={null};
        Consumer<Object> consumer=pair->{try{holder[0]=pair.getClass().getMethod("left").invoke(pair);}catch(Exception e){throw new IllegalStateException(e);}};
        Class.forName("org.mtr.mod.client.CustomResourceLoader").getMethod("getVehicleById",transport,String.class,Consumer.class).invoke(null,mode,id,consumer);
        if(holder[0]==null)return null;
        return holder[0].getClass().getMethod("getCachedVehicleResource",int.class,int.class,boolean.class).invoke(holder[0],0,cars.size(),true);
    }
    private static void deployIfInactive(Minecraft mc)
    {
        mc.getSingleplayerServer().execute(()->{
            try
            {
                Object sim=RegionalNativeTransitInspection.simulator();if(sim==null)return;
                String service=current.get("service").getAsString();
                for(Object siding:(Iterable<?>)sim.getClass().getField("sidings").get(sim))
                    if(((String)call(siding,"getName")).startsWith(service+" ")||((String)call(siding,"getName")).equals(service+"车辆段"))
                    {var f=siding.getClass().getDeclaredField("vehicles");f.setAccessible(true);for(Object v:(Iterable<?>)f.get(siding))if((Boolean)call(v,"getIsOnRoute"))return;}
                long id=Long.parseLong(current.get("route_id").getAsString());List<Object> depots=new ArrayList<>();
                for(Object depot:(Iterable<?>)sim.getClass().getField("depots").get(sim))
                {Object ids=call(depot,"getRouteIds");if((Boolean)ids.getClass().getMethod("contains",long.class).invoke(ids,id))depots.add(depot);}
                require(depots.size()==1,"Expected one exact native depot for configured route");
                Class<?> list=Class.forName("org.mtr.libraries.it.unimi.dsi.fastutil.objects.ObjectArrayList");
                sim.getClass().getMethod("instantDeployDepots",list).invoke(sim,list.getConstructor(Collection.class).newInstance(depots));
            }
            catch(Exception e){serverFailure=e.toString();}
        });
    }
    private static void requestRegistration(Minecraft mc)
    {
        long id=vehicleId;
        mc.getSingleplayerServer().execute(()->{
            try{Object sim=RegionalNativeTransitInspection.simulator();boolean r=(Boolean)sim.getClass().getMethod("isRiding",UUID.class,long.class).invoke(sim,mc.getSingleplayerServer().getPlayerList().getPlayers().get(0).getUUID(),id);serverRiding=r;serverDetached=!r;}
            catch(Exception e){serverFailure=e.toString();}
        });
    }
    private static void recordNativeDismount(Minecraft mc,boolean riding)
    {
        var row=new JsonObject();row.addProperty("phase_tick",stageTicks);row.addProperty("client_riding",riding);
        row.addProperty("server_detached",serverDetached);row.addProperty("shift_key_down",mc.options.keyShift.isDown());
        row.addProperty("player_shift_down",mc.player.isShiftKeyDown());row.addProperty("position",mc.player.position().toString());
        try
        {
            var field=Class.forName("org.mtr.mod.client.VehicleRidingMovement").getDeclaredField("shiftHoldingTicks");
            if(field.trySetAccessible())row.addProperty("native_shift_holding_ticks",field.getFloat(null));
            else row.addProperty("native_counter_unavailable","runtime field is not accessible");
        }
        catch(Exception exception){row.addProperty("native_counter_unavailable",exception.toString());}
        if(!result.has("native_dismount_progress"))result.add("native_dismount_progress",new JsonArray());
        result.getAsJsonArray("native_dismount_progress").add(row);
    }
    private static JsonObject floorEvidence(net.minecraft.world.level.Level level,net.minecraft.world.entity.Entity rider,Vec3 point)
    {
        var evidence=new JsonObject();var box=rider.getBoundingBox().move(point.subtract(rider.position()));
        evidence.addProperty("position",point.toString());evidence.addProperty("velocity",rider.getDeltaMovement().toString());
        evidence.addProperty("on_ground",rider.onGround());evidence.addProperty("bbox",box.toString());
        boolean cached=true;
        for(int x=net.minecraft.util.Mth.floor(box.minX)-1;x<=net.minecraft.util.Mth.floor(box.maxX)+1;x++)
            for(int z=net.minecraft.util.Mth.floor(box.minZ)-1;z<=net.minecraft.util.Mth.floor(box.maxZ)+1;z++)
                cached&=level.getChunkSource().hasChunk(x>>4,z>>4);
        evidence.addProperty("body_neighbour_chunks_cached",cached);
        if(cached)evidence.addProperty("body_clear",level.noCollision(rider,box.deflate(.025)));
        var rays=new JsonArray();
        for(double dx:new double[]{-.25,0,.25})for(double dz:new double[]{-.25,0,.25})
        {
            Vec3 start=point.add(dx,.08,dz);BlockPos cell=BlockPos.containing(start);var row=new JsonObject();
            boolean loaded=level.getChunkSource().hasChunk(cell.getX()>>4,cell.getZ()>>4);
            row.addProperty("from",start.toString());row.addProperty("chunk_cached",loaded);
            if(loaded)
            {
                for(double depth:new double[]{.30,2.0})
                {
                    var hit=level.clip(new net.minecraft.world.level.ClipContext(start,start.add(0,-depth,0),net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,rider));
                    var sample=new JsonObject();sample.addProperty("type",hit.getType().name());sample.addProperty("at",hit.getLocation().toString());
                    sample.addProperty("block",hit.getBlockPos().toShortString());sample.addProperty("state",level.getBlockState(hit.getBlockPos()).toString());
                    row.add(depth<1?"acceptance_ray":"diagnostic_two_metre_ray",sample);
                }
                var column=new JsonArray();
                for(int dy=-3;dy<=1;dy++)
                {var p=cell.offset(0,dy,0);var state=new JsonObject();state.addProperty("block",p.toShortString());state.addProperty("state",level.getBlockState(p).toString());column.add(state);}
                row.add("actual_vertical_states",column);
            }
            rays.add(row);
        }
        evidence.add("nine_floor_rays",rays);return evidence;
    }
    private static void captureArrivalEvidence(Minecraft mc)throws Exception
    {
        arrivalSupported=supported(mc,mc.player.position());serverArrivalEvidence=null;
        var row=floorEvidence(mc.level,mc.player,mc.player.position());
        row.addProperty("acceptance_supported",arrivalSupported);row.addProperty("native_riding",onNativeVehicle());
        row.addProperty("measured_doorway",doorway.toString());row.addProperty("client_game_time",mc.level.getGameTime());
        if(aircraft())row.add("declared_air_stairs",profile(true).getAsJsonObject("air_stairs").deepCopy());
        result.add("arrival_threshold_client",row);
        Vec3 actualClientPoint=mc.player.position();UUID playerId=mc.player.getUUID();
        mc.getSingleplayerServer().execute(()->{
            var evidence=new JsonObject();var player=mc.getSingleplayerServer().getPlayerList().getPlayer(playerId);
            if(player==null)evidence.addProperty("error","Actual passenger no longer registered with server");
            else
            {
                evidence=floorEvidence(player.serverLevel(),player,player.position());
                evidence.add("at_client_point",floorEvidence(player.serverLevel(),player,actualClientPoint));
                evidence.addProperty("server_game_time",player.level().getGameTime());
            }
            serverArrivalEvidence=evidence;
        });
    }
    private static void setWalk(List<Vec3> points){walk=points;walkIndex=0;}
    private static boolean walking(Minecraft mc)
    {
        if(walkIndex>=walk.size()){keys(mc,false,false);return true;}
        Vec3 target=walk.get(walkIndex),delta=target.subtract(mc.player.position());
        if(delta.horizontalDistanceSqr()<.10&&Math.abs(delta.y)<.35){walkIndex++;keys(mc,false,false);return walkIndex>=walk.size();}
        mc.player.setYRot((float)Math.toDegrees(Math.atan2(-delta.x,delta.z)));mc.player.setXRot(0);keys(mc,true,false);return false;
    }
    private static List<Vec3> liveFlatPath(Minecraft mc,Vec3 target,boolean destination)
    {
        BlockPos start=BlockPos.containing(mc.player.getX(),target.y,mc.player.getZ()),goal=BlockPos.containing(target);
        var previous=new HashMap<BlockPos,BlockPos>();var queue=new ArrayDeque<BlockPos>();previous.put(start,null);queue.add(start);
        JsonObject p=profile(destination);boolean air=aircraft(),xAxis=!air&&"x".equals(p.get("axis").getAsString());
        Vec3 lo=air?null:vec(p.getAsJsonArray("platform_lo")),hi=air?null:vec(p.getAsJsonArray("platform_hi"));
        while(!queue.isEmpty()&&previous.size()<60000)
        {
            var a=queue.removeFirst();if(a.equals(goal))
            {var route=new ArrayList<Vec3>();for(var q=a;q!=null;q=previous.get(q))route.add(new Vec3(q.getX()+.5,target.y,q.getZ()+.5));Collections.reverse(route);return route;}
            for(var direction:net.minecraft.core.Direction.Plane.HORIZONTAL)
            {
                var b=a.relative(direction);if(previous.containsKey(b)||Math.abs(b.getX()-start.getX())>200||Math.abs(b.getZ()-start.getZ())>200)continue;
                // No ground walk can cross the native running track between
                // the two actual owned strips. Bridges/stairs remain explicit.
                if(!air&&(xAxis?b.getZ()+.5>lo.z+.6&&b.getZ()+.5<hi.z+.4:b.getX()+.5>lo.x+.6&&b.getX()+.5<hi.x+.4))continue;
                var point=new Vec3(b.getX()+.5,target.y,b.getZ()+.5);if(!clientChunkLoaded(mc,b)||!supported(mc,point))continue;
                if(!mc.level.noCollision(mc.player,mc.player.getBoundingBox().move(point.subtract(mc.player.position())).expandTowards(new Vec3(a.getX()-b.getX(),0,a.getZ()-b.getZ())).deflate(.025)))continue;
                previous.put(b,a);queue.addLast(b);
            }
        }
        throw new IllegalStateException("No real loaded supported passenger path to "+target);
    }
    private static void begin(Minecraft mc)
    {
        current=cases.get(index).getAsJsonObject();require(!profile(true).get("exit_path").isJsonNull(),"Configured destination exit unresolved "+current.get("destination_platform"));
        Vec3 point=vec(profile(false).getAsJsonArray("staging"));staged=false;stagingAcknowledgedAt=-1;survivalRequested=false;serverStageEvidence=null;serverRiding=false;serverDetached=false;vehicleId=0;vehicle=null;cache=null;car=null;maxFrameStep=0;travel=0;
        result=new JsonObject();result.addProperty("id",current.get("id").getAsString());result.addProperty("source_platform",current.get("source_platform").getAsString());result.addProperty("destination_platform",current.get("destination_platform").getAsString());
        result.addProperty("station_paths","UNVERIFIED separate station_walk_cases.json obligations");phase(0);
        mc.getSingleplayerServer().execute(()->{var player=mc.getSingleplayerServer().getPlayerList().getPlayers().get(0);player.stopRiding();player.setGameMode(GameType.SPECTATOR);player.teleportTo(mc.getSingleplayerServer().getLevel(FacilitySchemaV2.DIMENSION),point.x,point.y,point.z,0,0);player.setDeltaMovement(Vec3.ZERO);player.fallDistance=0;
            var snapshot=new JsonObject();snapshot.addProperty("position",player.position().toString());snapshot.addProperty("dimension",player.level().dimension().location().toString());
            snapshot.addProperty("floor_state",player.level().getBlockState(BlockPos.containing(point.add(0,-.05,0))).toString());serverStageEvidence=snapshot;staged=true;});
    }
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent e)
    {
        if(!ENABLED||e.phase!=TickEvent.Phase.END)return;var mc=Minecraft.getInstance();
        if(done){if(++exitTicks>30)mc.stop();return;}
        if(mc.player==null||mc.level==null||mc.getSingleplayerServer()==null)return;
        if(mc.screen instanceof net.minecraft.client.gui.screens.PauseScreen)mc.setScreen(null);if(mc.screen!=null)return;
        try
        {
            if(!started)
            {
                world=mc.getSingleplayerServer().getWorldPath(LevelResource.ROOT).normalize();require(world.getFileName().toString().equals("SEELE_FIELD_R44_REVIEW"),"R44 transit refuses non-review save");
                String file=System.getProperty("projectseele.r44TransitCases","");require(!file.isBlank(),"Current 38 native cases file is required");var data=JsonParser.parseString(Files.readString(Path.of(file))).getAsJsonObject();cases=data.getAsJsonArray("cases");require(cases.size()==38,"Required native interface denominator is 38");
                index=Integer.getInteger("projectseele.r44TransitStart",0);end=Integer.getInteger("projectseele.r44TransitEnd",cases.size());require(index>=0&&end>index&&end<=38,"Invalid native transit window");
                oldDistance=mc.options.renderDistance().get();oldPause=mc.options.pauseOnLostFocus;mc.options.renderDistance().set(8);mc.options.pauseOnLostFocus=false;mc.options.broadcastOptions();
                var p=mc.getSingleplayerServer().getPlayerList().getPlayers().get(0);oldMode=p.gameMode.getGameModeForPlayer();oldPosition=p.position();oldDimension=p.level().dimension();oldYaw=p.getYRot();oldPitch=p.getXRot();oldFlying=p.getAbilities().flying;started=true;begin(mc);return;
            }
            require(serverFailure.isEmpty(),"Native server state read: "+serverFailure);require(clientFailure.isEmpty(),"Native rendered client state: "+clientFailure);ticks++;stageTicks++;require(ticks<120000,"Native case queue deadline");require(stageTicks<12000,"Native phase deadline "+stage+" "+current.get("id"));
            if(!staged)return;
            if(stage==0)
            {
                keys(mc,false,false);Vec3 declared=vec(profile(false).getAsJsonArray("staging"));
                if(stagingAcknowledgedAt<0)
                {
                    // ClientLevel.hasChunk() always returns true in 1.20.1.
                    // Keep initial staging weightless until actual cached
                    // terrain and its collision surface arrive; the journey
                    // itself is entirely survival movement.
                    if(!mc.level.dimension().equals(FacilitySchemaV2.DIMENSION)||!clientChunkLoaded(mc,BlockPos.containing(declared))||mc.player.position().distanceToSqr(declared)>.04||!supported(mc,declared))
                    {
                        if(stageTicks>600){result.add("initial_staging_evidence",stagingEvidence(mc));throw new IllegalStateException("Declared outside staging never acknowledged by client");}
                        return;
                    }
                    if(!survivalRequested)
                    {
                        result.add("loaded_staging_evidence",stagingEvidence(mc));survivalRequested=true;
                        mc.getSingleplayerServer().execute(()->{var p=mc.getSingleplayerServer().getPlayerList().getPlayers().get(0);p.setGameMode(GameType.SURVIVAL);p.getAbilities().flying=false;p.onUpdateAbilities();p.fallDistance=0;});
                        return;
                    }
                    if(mc.gameMode.getPlayerMode()!=GameType.SURVIVAL||mc.player.getAbilities().flying)return;
                    stagingAcknowledgedAt=stageTicks;result.addProperty("actual_client_staging_ack_tick",stageTicks);
                }
                if(stageTicks-stagingAcknowledgedAt<100)return;
                result.add("initial_staging_evidence",stagingEvidence(mc));require(supported(mc,mc.player.position()),"Initial external staging unsupported");health=mc.player.getHealth();deployIfInactive(mc);phase(1);
            }
            else if(stage==1)
            {
                Object data=Class.forName("org.mtr.mod.client.MinecraftClientData").getMethod("getInstance").invoke(null);
                for(Object v:(Iterable<?>)data.getClass().getField("vehicles").get(data))
                {
                    if(!stoppedAt(v,Long.parseLong(current.get("source_platform").getAsString())))continue;
                    Object extra=v.getClass().getField("vehicleExtraData").get(v);var cars=(List<?>)extra.getClass().getField("immutableVehicleCars").get(extra);if(cars.isEmpty())continue;
                    Object c=cars.get(0),resource=resourceCache(v,c);if(resource==null)continue;
                    var d=RegionalTransitRidingChecks.measuredDoorway(v,resource,c,mc.player.position(),aircraft(),p->eligibleDoor(mc,p,false));if(d==null)continue;
                    vehicle=v;vehicleId=number(v,"getId");cache=resource;car=c;doorway=d;
                    result.addProperty("origin_stopped_with_open_doors",true);result.addProperty("vehicle_id",vehicleId);
                    setWalk(aircraft()?List.of(vec(profile(false).getAsJsonObject("air_stairs").getAsJsonArray("landing"))):liveFlatPath(mc,d.approach(),false));phase(2);break;
                }
            }
            else if(stage==2)
            {vehicle=actualVehicle();require(vehicle!=null,"Boarding vehicle disappeared");if(!stoppedAt(vehicle,Long.parseLong(current.get("source_platform").getAsString()))){keys(mc,false,false);phase(1);return;}if(walking(mc)){phase(3);}}
            else if(stage==3)
            {
                mc.player.setYRot(doorway.inwardYaw());mc.player.setXRot(0);keys(mc,true,false);
                if(onNativeVehicle())
                {setWalk(List.of(doorway.inside()));result.addProperty("actual_native_door_crossing",true);phase(4);}
                else{vehicle=actualVehicle();if(vehicle==null||!stoppedAt(vehicle,Long.parseLong(current.get("source_platform").getAsString()))){keys(mc,false,false);phase(1);}}
            }
            else if(stage==4){if(walking(mc)){departure=mc.player.position();travel=0;previousRendered=null;while(motionHistory.size()>0)motionHistory.remove(0);phase(5);}}
            else if(stage==5)
            {
                require(onNativeVehicle(),"Native rider lost while moving");vehicle=actualVehicle();require(vehicle!=null,"Native carrier no longer streamed");if(stageTicks%20==0)requestRegistration(mc);
                if(stageTicks>300)require(serverRiding,"Server never registered native passenger");
                if(stageTicks>80&&serverRiding&&mc.player.position().distanceTo(departure)>30&&stoppedAt(vehicle,Long.parseLong(current.get("destination_platform").getAsString())))
                {
                    result.addProperty("client_and_server_registered",true);result.addProperty("correct_destination_stop_and_doors",true);
                    var p=profile(true);Vec3 preferred=aircraft()?vec(p.getAsJsonObject("air_stairs").getAsJsonArray("landing")):vec(p.getAsJsonArray("exit_path").get(0).getAsJsonArray());
                    doorway=RegionalTransitRidingChecks.measuredDoorway(vehicle,cache,car,preferred,aircraft(),q->eligibleDoor(mc,q,true));require(doorway!=null,"No supported destination doorway");
                    setWalk(List.of(aircraft()?preferred:doorway.approach()));phase(6);
                }
            }
            else if(stage==6)
            {if(walking(mc)){keys(mc,false,false);captureArrivalEvidence(mc);phase(60);}}
            else if(stage==60)
            {
                if(serverArrivalEvidence==null){require(stageTicks<100,"Arrival support observation not acknowledged by server");return;}
                result.add("arrival_threshold_server",serverArrivalEvidence.deepCopy());
                require(arrivalSupported,"Actual destination threshold body clearance or floor support failed; see paired native evidence");keys(mc,false,true);phase(7);
            }
            else if(stage==7)
            {
                keys(mc,false,true);if(stageTicks%10==0)requestRegistration(mc);
                boolean riding=onNativeVehicle();
                if(stageTicks==1||stageTicks%10==0||!riding)recordNativeDismount(mc,riding);
                // MTR4.0.5 releases a retained standing rider after its native
                // 30-tick sneak hold. The previous20-tick assertion rejected
                // a correct aircraft landing before that gesture could finish.
                // Observe the actual client/server handshake instead of
                // bypassing it or forcing the native passenger registration.
                if(riding){require(stageTicks<160,"Native sneak hold did not release client rider");return;}
                if(!serverDetached){require(stageTicks<200,"Native dismount not acknowledged by server");return;}
                keys(mc,false,false);result.addProperty("actual_supported_disembark",true);result.addProperty("server_detached",true);
                var profile=profile(true);Vec3 first=vec(profile.getAsJsonArray("exit_path").get(0).getAsJsonArray());var targets=new ArrayList<Vec3>();
                if(aircraft())targets.add(vec(profile.getAsJsonObject("air_stairs").getAsJsonArray("entry")));
                else targets.addAll(liveFlatPath(mc,first,true));
                for(var point:profile.getAsJsonArray("exit_path"))targets.add(vec(point.getAsJsonArray()));setWalk(targets);phase(8);
            }
            else if(stage==8)
            {
                if(!walking(mc))return;require(supported(mc,mc.player.position())&&mc.player.onGround(),"Exit path did not end on supported public floor");
                require(mc.player.getHealth()>=health-.01&&mc.player.isAlive(),"Passenger lost health during actual native passage");
                result.addProperty("actual_exit_path",true);result.addProperty("native_interface_pass",true);result.addProperty("whole_station","UNVERIFIED remaining station paths/entrances/gates/transfers");result.addProperty("max_rendered_step",maxFrameStep);results.add(result);completed.add(current.get("source_platform").getAsString());write("");
                if(++index>=end){finish(mc,"");return;}begin(mc);
            }
        }
        catch(Exception failure){ProjectSeele.LOGGER.error("R44 native transit case failed",failure);finish(mc,failure.toString());}
    }
    @SubscribeEvent public static void render(TickEvent.RenderTickEvent e)
    {
        if(!ENABLED||e.phase!=TickEvent.Phase.END||stage!=5||done)return;var mc=Minecraft.getInstance();if(mc.player==null)return;
        try
        {
            var v=actualVehicle();if(v==null)return;double speed=((Number)call(v,"getSpeed")).doubleValue();long now=System.nanoTime();Vec3 p=mc.player.position();
            if(previousRendered!=null)
            {
                double move=p.distanceTo(previousRendered),wallSeconds=(now-motionNanos)/1e9;
                double nativeSeconds=com.projectseele.client.AircraftRenderClockR21.simulationSeconds-simulationSeconds;
                double seconds=Math.max(wallSeconds,nativeSeconds),bound=Math.max(15,Math.max(speed,previousSpeed)*1000*seconds*2+5);
                if(move>1e-5)
                {
                    var row=new JsonObject();row.addProperty("client_game_time",mc.level.getGameTime());row.addProperty("phase_tick",stageTicks);
                    row.addProperty("from",previousRendered.toString());row.addProperty("to",p.toString());row.addProperty("distance",move);
                    row.addProperty("wall_seconds",wallSeconds);row.addProperty("native_seconds",nativeSeconds);
                    row.addProperty("speed_blocks_per_millisecond",speed);row.addProperty("previous_speed",previousSpeed);row.addProperty("acceptance_bound",bound);
                    row.addProperty("vehicle_id",vehicleId);row.addProperty("native_riding",onNativeVehicle());row.addProperty("server_registered",serverRiding);
                    row.addProperty("client_chunk_cached",clientChunkLoaded(mc,BlockPos.containing(p)));
                    Object extra=v.getClass().getField("vehicleExtraData").get(v);
                    row.addProperty("route",number(extra,"getThisRouteId"));row.addProperty("platform",number(extra,"getThisPlatformId"));
                    motionHistory.add(row);if(motionHistory.size()>32)motionHistory.remove(0);
                    if(move>=bound)result.add("native_motion_failure_last32_actual_frames",motionHistory.deepCopy());
                    require(move<bound,"Native rendered passenger discontinuity");maxFrameStep=Math.max(maxFrameStep,move);travel+=move;
                }
            }
            if(previousRendered==null||p.distanceToSqr(previousRendered)>1e-10||speed<.001){previousRendered=p;motionNanos=now;simulationSeconds=com.projectseele.client.AircraftRenderClockR21.simulationSeconds;}previousSpeed=speed;
        }
        catch(Exception failure){clientFailure=failure.toString();}
    }
    private static void write(String error)
    {
        try{var out=new JsonObject();out.addProperty("error",error);out.addProperty("required_train_platforms",34);out.addProperty("required_air_interfaces",4);out.addProperty("completed_interfaces",completed.size());out.addProperty("full_native_interface_run_pass",error.isEmpty()&&completed.size()==38);out.addProperty("whole_station_acceptance","UNVERIFIED independent station_walk_cases/gate/transfer obligations");out.addProperty("reload","UNVERIFIED");out.add("cases",results);if(current!=null){out.addProperty("current_case",current.get("id").getAsString());out.addProperty("current_phase",stage);if(result!=null)out.add("current_case_evidence",result.deepCopy());}Files.writeString(world.resolve("r44_transit_review.json"),new GsonBuilder().setPrettyPrinting().create().toJson(out));}catch(Exception e){ProjectSeele.LOGGER.error("R44 transit result write failed",e);}
    }
    private static void finish(Minecraft mc,String error)
    {
        keys(mc,false,true);write(error);done=true;if(!started)return;
        mc.options.renderDistance().set(oldDistance);mc.options.pauseOnLostFocus=oldPause;mc.options.broadcastOptions();
        mc.getSingleplayerServer().execute(()->{var p=mc.getSingleplayerServer().getPlayerList().getPlayers().get(0);p.setGameMode(oldMode);p.getAbilities().flying=oldFlying;p.onUpdateAbilities();p.teleportTo(mc.getSingleplayerServer().getLevel(oldDimension),oldPosition.x,oldPosition.y,oldPosition.z,oldYaw,oldPitch);});
    }
}

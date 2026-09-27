package com.projectseele.visual;

import com.google.gson.*;
import com.mojang.authlib.GameProfile;
import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilitySchemaV2;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.EmptyBlockGetter;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.Property;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraftforge.common.util.FakePlayer;
import net.minecraftforge.common.util.FakePlayerFactory;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Measures native voxel shapes and actual player collision movement; no world blocks are authored. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class RegionalSpatialAuditDriver
{
    private static final boolean COMBINED=Set.of("r10-world","r20-civil-annex").contains(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R42="r42-collision".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R41=R42||"r41-collision".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R40=R41||"r40-collision".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R30=R40||Set.of("r30-shapes","r30-collision").contains(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R29_TOUR="r29-worldtour".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R29=R30||R29_TOUR||"r29-collision".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R28=R29||"r28-collision".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R26=R28||"r26-collision".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R25=R26||"r25-collision".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R24=R25||"r24-collision".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R23=R24||"r23-collision".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R21=R23||"r21-collision".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R20=R21||Set.of("r20-collision","r20-civil-annex").contains(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R19=R20||"r19-collision".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean ENABLED=R19||COMBINED||"collision-audit".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final TicketType<ChunkPos> TICKET=TicketType.create("projectseele_spatial_audit",Comparator.comparingLong(ChunkPos::toLong),100);
    private static final Gson GSON=new GsonBuilder().setPrettyPrinting().create();
    private static final JsonArray RESULTS=new JsonArray();
    private static JsonArray cases;
    private static JsonArray generation;private static int generated;
    private static FakePlayer player;
    private static int age,index,wait,steps,stalled,settled,stepLimit;
    public static volatile boolean done;
    private static boolean positioned;
    private static Vec3 start,end;
    private static JsonArray route;
    private static int waypoint;
    private static double distance,maxRise,fallSpeed;
    private static int doorInteractions;
    private static int mechanismWait;
    private static int commandDoorWait;
    private static final JsonArray TRACE=new JsonArray();
    private static ServerLevel activeLevel;
    private static final Map<BlockPos,BlockState> RESTORE=new LinkedHashMap<>();

    @SuppressWarnings({"rawtypes","unchecked"})
    private static BlockState parse(String text)
    {
        int bracket=text.indexOf('[');String name=bracket<0?text:text.substring(0,bracket);
        ResourceLocation id=new ResourceLocation(name);
        if(!BuiltInRegistries.BLOCK.containsKey(id))throw new IllegalStateException("Unknown block "+text);
        var block=BuiltInRegistries.BLOCK.get(id);BlockState state=block.defaultBlockState();
        if(bracket>=0)for(String property:text.substring(bracket+1,text.length()-1).split(","))
        {
            String[] pair=property.split("=");Property key=block.getStateDefinition().getProperty(pair[0]);
            if(key==null)throw new IllegalStateException("Unknown property "+text);
            state=state.setValue(key,(Comparable)key.getValue(pair[1]).orElseThrow());
        }
        return state;
    }
    private static Vec3 vector(JsonArray a){return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static JsonArray position(Vec3 p){JsonArray a=new JsonArray();a.add(p.x);a.add(p.y);a.add(p.z);return a;}

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||done||event.phase!=TickEvent.Phase.END)return;
        var server=event.getServer();Path world=server.getWorldPath(LevelResource.ROOT).normalize();
        if(!world.getFileName().toString().equals(R42?"SEELE_FIELD_R42_REVIEW":R41?"SEELE_FIELD_R41_REVIEW":R40?"SEELE_FIELD_R40_REVIEW":R30?"SEELE_FIELD_R30_REVIEW":R29?"SEELE_FIELD_R29_REVIEW":R28?"SEELE_FIELD_R28_REVIEW":R26?"SEELE_R26_REVIEW":R25?"SEELE_R25_REVIEW":R24?"SEELE_R24_TV_REVIEW":R23?"SEELE_R22_REVIEW":R21?"SEELE_R21_REVIEW":R20?"SEELE_R20_REVIEW":R19?"SEELE_R19_NATIVE_REVIEW":"SEELE_TV_WORLD_PREVIEW_20260906"))throw new IllegalStateException("Wrong quality audit world");
        ServerLevel level=server.getLevel(FacilitySchemaV2.DIMENSION);
        if(level!=null)level.resetEmptyTime();
        try
        {
            if(++age<100)return;
            if(cases==null)
            {
                if(R20&&Files.isRegularFile(world.resolve("r20_generate_chunks.json")))
                {
                    if(generation==null)generation=JsonParser.parseString(Files.readString(world.resolve("r20_generate_chunks.json"))).getAsJsonArray();
                    for(int n=0;n<2&&generated<generation.size();n++,generated++){var q=generation.get(generated).getAsJsonArray();level.getChunk(q.get(0).getAsInt(),q.get(1).getAsInt());}
                    if(generated<generation.size())return;
                    Files.writeString(world.resolve("r20_generated_chunks_result.json"),generation.toString());
                }
                player=FakePlayerFactory.get(level,new GameProfile(UUID.fromString("9bc3f5d1-2e80-4a10-8986-965c47c87e61"),"[SEELE audit]"));
                player.setGameMode(GameType.SURVIVAL);player.getAbilities().flying=false;player.noPhysics=false;
                player.setMaxUpStep(.6F);
                var stepAttribute=player.getAttribute(net.minecraftforge.common.ForgeMod.STEP_HEIGHT_ADDITION.get());
                if(stepAttribute!=null)stepAttribute.setBaseValue(0);
                JsonObject shapes=new JsonObject();
                for(JsonElement e:JsonParser.parseString(Files.readString(world.resolve("regional_states.json"))).getAsJsonArray())
                {
                    String key=e.getAsString();BlockState state=parse(key);JsonArray boxes=new JsonArray();
                    for(var b:state.getCollisionShape(EmptyBlockGetter.INSTANCE,BlockPos.ZERO,CollisionContext.of(player)).toAabbs())
                    {JsonArray box=new JsonArray();for(double v:new double[]{b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ})box.add(v);boxes.add(box);}
                    shapes.add(key,boxes);
                }
                Files.writeString(world.resolve("native_collision_shapes.json"),GSON.toJson(shapes));
                Path survey=world.resolve("quality_survey_points.json");
                if(Files.exists(survey))
                {
                    JsonArray heights=new JsonArray();
                    for(JsonElement e:JsonParser.parseString(Files.readString(survey)).getAsJsonArray())
                    {
                        JsonArray point=e.getAsJsonArray();int x=point.get(0).getAsInt(),z=point.get(1).getAsInt();
                        int y=level.getChunkSource().getGenerator().getBaseHeight(x,z,net.minecraft.world.level.levelgen.Heightmap.Types.OCEAN_FLOOR_WG,level,level.getChunkSource().randomState());
                        JsonArray row=new JsonArray();row.add(x);row.add(y);row.add(z);heights.add(row);
                    }
                    Files.writeString(world.resolve("quality_terrain_survey.json"),GSON.toJson(heights));
                }
                cases=JsonParser.parseString(Files.readString(world.resolve(R42?"r42_walk_cases.json":R41?"r41_walk_cases.json":R40?"r40_walk_cases.json":R30?"r30_walk_cases.json":R29?"r29_walk_cases.json":R28?"r28_walk_cases.json":R26?"r26_walk_cases.json":R25?"r25_walk_cases.json":R24?"r24_walk_cases.json":R23?"r23_walk_cases.json":"quality_walk_cases.json"))).getAsJsonArray();
                ProjectSeele.LOGGER.info("SPATIAL NATIVE shapes={} cases={} playerStep={}",shapes.size(),cases.size(),player.maxUpStep());
            }
            if(Files.exists(world.resolve("regional_stop_requested")))
            {Files.writeString(world.resolve("quality_native_walk_results.json"),GSON.toJson(RESULTS));Files.delete(world.resolve("regional_stop_requested"));done=true;server.halt(false);return;}
            if(index==cases.size())
            {
                Files.writeString(world.resolve("quality_native_walk_results.json"),GSON.toJson(RESULTS));
                ProjectSeele.LOGGER.info("SPATIAL NATIVE COMPLETE cases={}",RESULTS.size());done=true;if(!COMBINED&&!R29_TOUR)server.halt(false);return;
            }
            JsonObject test=cases.get(index).getAsJsonObject();
            if(wait==0)
            {
                route=test.has("path")?test.getAsJsonArray("path"):new JsonArray();
                if(!test.has("path")){route.add(test.getAsJsonArray("start"));route.add(test.getAsJsonArray("end"));}
                if(route.size()<2)throw new IllegalStateException("Route needs two points");
                waypoint=1;start=vector(route.get(0).getAsJsonArray());end=vector(route.get(1).getAsJsonArray());
                for(int segment=1;segment<route.size();segment++)
                {
                    Vec3 a=vector(route.get(segment-1).getAsJsonArray()),b=vector(route.get(segment).getAsJsonArray());
                    for(int cx=(int)Math.floor(Math.min(a.x,b.x)-3)>>4;cx<=(int)Math.floor(Math.max(a.x,b.x)+3)>>4;cx++)
                        for(int cz=(int)Math.floor(Math.min(a.z,b.z)-3)>>4;cz<=(int)Math.floor(Math.max(a.z,b.z)+3)>>4;cz++)
                        {ChunkPos chunk=new ChunkPos(cx,cz);level.getChunkSource().addRegionTicket(TICKET,chunk,2,chunk);level.getChunk(cx,cz);}
                }
                // getChunk above is synchronous: the collision data is already
                // FULL. Extra idle ticks here added half an hour to a whole-world
                // audit without simulating any additional player movement.
                wait=3;positioned=false;
            }
            if(wait++<3)return;
            if(!positioned)
            {
                player.setPos(start);player.setOnGround(true);player.setDeltaMovement(Vec3.ZERO);steps=0;stalled=0;settled=0;maxRise=0;fallSpeed=0;
                double length=0;
                for(int j=1;j<route.size();j++)length+=vector(route.get(j).getAsJsonArray()).distanceTo(vector(route.get(j-1).getAsJsonArray()));
                stepLimit=Math.max(2000,(int)Math.ceil(length/.12)+route.size()*100);
                TRACE.asList().clear();positioned=true;
                activeLevel=level;RESTORE.clear();doorInteractions=0;
                if(R41&&!level.noCollision(player,player.getBoundingBox()))
                {
                    // A .6F player is 0.6000000238 blocks wide. Decimal
                    // catalogue endpoints .3 from a wall can overlap it by
                    // 1.2e-8 despite having no meaningful penetration.
                    if(!level.noCollision(player,player.getBoundingBox().deflate(1e-7)))
                    {finish(test,"probe_start_obstructed");return;}
                    test.addProperty("startBoundaryTolerance",1e-7);
                }
                if(R41&&test.has("barrier")&&!level.getBlockCollisions(player,player.getBoundingBox().move(0,-.2,0)).iterator().hasNext())
                {finish(test,"probe_start_unsupported");return;}
                if(test.has("readingBoard"))
                {
                    var b=test.getAsJsonArray("readingBoard");BlockPos at=new BlockPos(b.get(0).getAsInt(),b.get(1).getAsInt(),b.get(2).getAsInt());
                    boolean wayfinding=test.has("readingWayfinding")&&test.get("readingWayfinding").getAsBoolean();
                    if(!(level.getBlockEntity(at) instanceof com.projectseele.world.StationDepartureBoardBlockEntity board)
                            || (wayfinding?board.rows().size()<3:!board.routeMap()||board.rows().size()<4))
                    {finish(test,"missing_complete_station_diagram");return;}
                    var outline=level.getBlockState(at).getShape(level,at);
                    if(outline.isEmpty()){finish(test,"missing_sign_outline");return;}
                    var target=outline.bounds().getCenter().add(Vec3.atLowerCornerOf(at));
                    var hit=level.clip(new net.minecraft.world.level.ClipContext(player.getEyePosition(),target,
                            net.minecraft.world.level.ClipContext.Block.OUTLINE,net.minecraft.world.level.ClipContext.Fluid.NONE,player));
                    if(hit.getType()!=net.minecraft.world.phys.HitResult.Type.BLOCK||!hit.getBlockPos().equals(at)){finish(test,"station_diagram_obstructed");return;}
                }
                if(test.has("commandButton"))
                {
                    var b=test.getAsJsonArray("commandButton");BlockPos button=new BlockPos(b.get(0).getAsInt(),b.get(1).getAsInt(),b.get(2).getAsInt());
                    var state=level.getBlockState(button);var shape=state.getShape(level,button);
                    if(shape.isEmpty()){finish(test,"command_button_missing");return;}
                    var point=shape.bounds().getCenter().add(Vec3.atLowerCornerOf(button));var eye=player.getEyePosition();
                    var hit=level.clip(new net.minecraft.world.level.ClipContext(eye,point.add(point.subtract(eye).normalize().scale(.03)),net.minecraft.world.level.ClipContext.Block.OUTLINE,net.minecraft.world.level.ClipContext.Fluid.NONE,player));
                    if(eye.distanceTo(point)>4.5||!hit.getBlockPos().equals(button)){finish(test,"command_button_not_physically_reachable");return;}
                    if(!com.projectseele.world.CommandRoomSlidingDoorDirector.handleUse(player,button)){finish(test,"command_button_rejected");return;}
                    commandDoorWait=200;doorInteractions++;
                }
                if(test.has("interactBlocks"))
                {
                    // Imported multi-height shutters are functional entrances too.
                    // Snapshot their local neighbours before invoking the real use action.
                    for(var item:test.getAsJsonArray("interactBlocks"))
                    {
                        var value=item.getAsJsonArray();BlockPos pos=new BlockPos(value.get(0).getAsInt(),value.get(1).getAsInt(),value.get(2).getAsInt());
                        for(BlockPos neighbour:BlockPos.betweenClosed(pos.offset(-1,-1,-1),pos.offset(1,3,1)))RESTORE.putIfAbsent(neighbour.immutable(),level.getBlockState(neighbour));
                    }
                    for(var item:test.getAsJsonArray("interactBlocks"))
                    {
                        var value=item.getAsJsonArray();BlockPos pos=new BlockPos(value.get(0).getAsInt(),value.get(1).getAsInt(),value.get(2).getAsInt());var state=level.getBlockState(pos);
                        var open=state.getProperties().stream().filter(property->property.getName().equals("open")).findFirst();
                        if(open.isPresent()&&state.getValue(open.get()).toString().equals("true"))continue;
                        state.use(level,player,net.minecraft.world.InteractionHand.MAIN_HAND,new net.minecraft.world.phys.BlockHitResult(Vec3.atCenterOf(pos),net.minecraft.core.Direction.NORTH,pos,false));
                    }
                }
                if(test.has("useDoor"))
                {
                    JsonArray d=test.getAsJsonArray("door");BlockPos door=new BlockPos(d.get(0).getAsInt(),d.get(1).getAsInt(),d.get(2).getAsInt());
                    for(BlockPos pos:List.of(door,door.above()))RESTORE.put(pos,level.getBlockState(pos));
                    BlockState state=level.getBlockState(door);
                    if(!(state.getBlock() instanceof net.minecraft.world.level.block.DoorBlock)){finish(test,"missing_entry_door");return;}
                    if(!state.getValue(net.minecraft.world.level.block.DoorBlock.OPEN))state.use(level,player,net.minecraft.world.InteractionHand.MAIN_HAND,new net.minecraft.world.phys.BlockHitResult(Vec3.atCenterOf(door),net.minecraft.core.Direction.SOUTH,door,false));
                    if(!level.getBlockState(door).getValue(net.minecraft.world.level.block.DoorBlock.OPEN)){finish(test,"door_did_not_open");return;}
                }
                if(test.has("button"))
                {
                    JsonArray a=test.getAsJsonArray("button"),d=test.getAsJsonArray("door");
                    BlockPos button=new BlockPos(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt());
                    BlockPos door=new BlockPos(d.get(0).getAsInt(),d.get(1).getAsInt(),d.get(2).getAsInt());
                    for(BlockPos pos:List.of(door,door.above(),button))RESTORE.put(pos,level.getBlockState(pos));
                    BlockState state=level.getBlockState(button);
                    if(!(state.getBlock() instanceof net.minecraft.world.level.block.ButtonBlock))throw new IllegalStateException("Expected a native door button at "+button);
                    state.use(level,player,net.minecraft.world.InteractionHand.MAIN_HAND,new net.minecraft.world.phys.BlockHitResult(Vec3.atCenterOf(button),net.minecraft.core.Direction.NORTH,button,false));
                    BlockState opened=level.getBlockState(door);
                    if(!opened.hasProperty(net.minecraft.world.level.block.DoorBlock.OPEN)||!opened.getValue(net.minecraft.world.level.block.DoorBlock.OPEN))
                    {finish(test,"door_did_not_open");return;}
                }
            }
            if(commandDoorWait>0)
            {
                var b=test.getAsJsonArray("commandButton");var button=new BlockPos(b.get(0).getAsInt(),b.get(1).getAsInt(),b.get(2).getAsInt());
                var chunk=new ChunkPos(button);level.getChunkSource().addRegionTicket(TICKET,chunk,3,chunk);
                if(!com.projectseele.world.CommandRoomSlidingDoorDirector.passageReady(level,button))
                {if(--commandDoorWait==0)finish(test,"command_door_did_not_clear");return;}
                commandDoorWait=0;
            }
            if(mechanismWait>0){mechanismWait--;return;}
            for(int n=0;n<120;n++)
            {
                Vec3 old=player.position();double dx=end.x-old.x,dz=end.z-old.z;distance=Math.hypot(dx,dz);
                if(test.has("climbablePort")&&player.onClimbable())
                {finish(test,start.y-old.y<=2.5?"pass":"unsafe_ladder_entry_drop");break;}
                if(distance<.18 && player.onGround() && settled>=2)
                {
                    if(Math.abs(old.y-end.y)>=.16){finish(test,"wrong_arrival_height");break;}
                    if(R41&&!test.has("barrier")&&waypoint==route.size()-1
                            &&!level.noCollision(player,player.getBoundingBox().move(end.subtract(old)).deflate(1e-7)))
                    {finish(test,"requested_endpoint_obstructed");break;}
                    if(++waypoint==route.size()){finish(test,"pass");break;}
                    // A route gets one initial placement. Turns continue from the actual
                    // settled player position, so a disconnected seam cannot be skipped.
                    start=end;end=vector(route.get(waypoint).getAsJsonArray());settled=0;stalled=0;continue;
                }
                if(old.y<Math.min(start.y,end.y)-(test.has("climbablePort")?2.5:.65)){finish(test,"floor_gap");break;}
                double amount=distance<.18?0:Math.min(.12,distance);
                fallSpeed=(fallSpeed-.08)*.98;
                player.move(MoverType.SELF,new Vec3(distance<.001?0:dx/distance*amount,fallSpeed,distance<.001?0:dz/distance*amount));
                if(player.onGround())fallSpeed=0;
                Vec3 now=player.position();maxRise=Math.max(maxRise,now.y-old.y);steps++;
                if(amount==0 && player.onGround() && Math.abs(now.y-old.y)<.0001)settled++;else settled=0;
                if(distance>=.18 && Math.hypot(now.x-old.x,now.z-old.z)<.0001)stalled++;else stalled=0;
                if(steps%4==0||stalled>0)TRACE.add(position(now));
                if(stalled==1&&openReachableDoor()){stalled=0;continue;}
                if(stalled>=8)
                {
                    if(test.has("barrier"))
                    {
                        var boundary=test.getAsJsonObject("barrier");double coordinate=boundary.get("axis").getAsString().equals("x")?now.x:now.z;
                        double gap=Math.abs(coordinate-boundary.get("plane").getAsDouble());
                        double maximum=boundary.has("maxGap")?boundary.get("maxGap").getAsDouble():.75;
                        finish(test,gap>=.25&&gap<=maximum&&Math.abs(now.y-start.y)<.16?"pass":"barrier_not_reached");
                    }
                    else finish(test,"blocked_by_native_collision");break;
                }
                if(steps>stepLimit){finish(test,"timeout");break;}
            }
        }
        catch(Exception exception)
        {
            ProjectSeele.LOGGER.error("SPATIAL NATIVE AUDIT FAILED",exception);
            if(activeLevel!=null){RESTORE.forEach((pos,state)->activeLevel.setBlock(pos,state,3));RESTORE.clear();}
            try{Files.writeString(world.resolve("quality_native_failure.txt"),exception.toString());}catch(Exception ignored){}
            done=true;server.halt(false);
        }
    }
    private static boolean openReachableDoor()
    {
        // A cold save may have ordinary doors closed. Exercise the player's
        // real right-click action; never turn a collision block into air.
        boolean opened=false;var centre=player.blockPosition();
        for(BlockPos p:BlockPos.betweenClosed(centre.offset(-1,0,-1),centre.offset(1,1,1)))
        {
            var state=activeLevel.getBlockState(p);String name=BuiltInRegistries.BLOCK.getKey(state.getBlock()).getPath();
            if(!(name.endsWith("_door")||name.endsWith("shutter")||name.endsWith("fence_gate")))continue;
            var property=state.getProperties().stream().filter(k->k.getName().equals("open")).findFirst();
            if(property.isEmpty()||!state.getValue(property.get()).toString().equals("false"))continue;
            for(BlockPos q:BlockPos.betweenClosed(p.offset(-1,-1,-1),p.offset(1,2,1)))RESTORE.putIfAbsent(q.immutable(),activeLevel.getBlockState(q));
            state.use(activeLevel,player,net.minecraft.world.InteractionHand.MAIN_HAND,new net.minecraft.world.phys.BlockHitResult(Vec3.atCenterOf(p),net.minecraft.core.Direction.NORTH,p,false));
            var after=activeLevel.getBlockState(p);
            if(state.is(net.minecraft.world.level.block.Blocks.IRON_DOOR)&&after.getValue(property.get()).toString().equals("false"))
            {
                BlockPos nearest=null;double distance=Double.MAX_VALUE;
                for(BlockPos q:BlockPos.betweenClosed(p.offset(-2,-1,-2),p.offset(2,2,2)))
                {
                    var button=activeLevel.getBlockState(q);
                    if(!(button.getBlock() instanceof net.minecraft.world.level.block.ButtonBlock)||button.getValue(net.minecraft.world.level.block.ButtonBlock.POWERED))continue;
                    double d=Vec3.atCenterOf(q).distanceToSqr(player.getEyePosition());
                    if(d<9&&d<distance){nearest=q.immutable();distance=d;}
                }
                if(nearest!=null)
                {
                    var q=nearest;RESTORE.putIfAbsent(q,activeLevel.getBlockState(q));
                    activeLevel.getBlockState(q).use(activeLevel,player,net.minecraft.world.InteractionHand.MAIN_HAND,new net.minecraft.world.phys.BlockHitResult(Vec3.atCenterOf(q),net.minecraft.core.Direction.NORTH,q,false));
                    after=activeLevel.getBlockState(p);
                }
            }
            if(after.hasProperty(property.get())&&after.getValue(property.get()).toString().equals("true")){opened=true;doorInteractions++;}
        }
        return opened;
    }
    private static void finish(JsonObject test,String status)
    {
        JsonObject result=test.deepCopy();result.addProperty("status",status);result.add("actual",position(player.position()));
        result.addProperty("waypointsReached",waypoint);result.addProperty("nativeDoorInteractions",doorInteractions);
        result.addProperty("maxRise",maxRise);result.addProperty("playerStep",player.maxUpStep());result.add("trace",TRACE.deepCopy());RESULTS.add(result);
        if(test.has("commandButton"))
        {
            var doors=new JsonArray();for(var door:activeLevel.getEntitiesOfClass(com.projectseele.entity.NervSlidingDoorEntity.class,player.getBoundingBox().inflate(8)))
            {var d=new JsonObject();d.addProperty("id",door.getDoorId());d.addProperty("entity",door.getId());d.addProperty("ticks",door.tickCount);d.addProperty("open",door.getOpenProgress(1));d.addProperty("target",door.requestedOpenProgress());d.addProperty("entityTicking",activeLevel.isPositionEntityTicking(door.blockPosition()));doors.add(d);}result.add("doorRuntime",doors);
        }
        if(!status.equals("pass"))
        {
            var nearby=new JsonArray();var at=player.blockPosition();
            for(BlockPos q:BlockPos.betweenClosed(at.offset(-2,-2,-2),at.offset(2,3,2)))if(!activeLevel.getBlockState(q).isAir())nearby.add(q.toShortString()+" "+activeLevel.getBlockState(q));result.add("nearbyBlocks",nearby);
            var entities=new JsonArray();for(var entity:activeLevel.getEntities(player,player.getBoundingBox().inflate(4)))entities.add(entity.getType()+" "+entity.getUUID()+" "+entity.getBoundingBox());result.add("nearbyEntities",entities);
        }
        ProjectSeele.LOGGER.info("SPATIAL WALK {} {} actual={} target={}",test.get("id").getAsString(),status,player.position(),end);
        RESTORE.forEach((pos,state)->activeLevel.setBlock(pos,state,3));RESTORE.clear();
        index++;wait=0;
    }
}

package com.projectseele.world;

import com.google.gson.*;
import com.mojang.authlib.GameProfile;
import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModBlocks;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.nbt.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.common.util.FakePlayer;
import net.minecraftforge.common.util.FakePlayerFactory;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.event.server.ServerStoppingEvent;

/** Parent-scheduled native tests; each operation has a separate denominator. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class Tokyo3BuildingQualityR44
{
    private static final String JOB=System.getProperty("projectseele.r44TokyoQualityJob","");
    private static int age,index,phase,timer,startDepth,checkpointDepth,requestedEndpointDepth;
    private static boolean done,requested,reversed,reversalBoundaryObserved;
    private static JsonObject input;
    private static Path output,snapshots;
    private static String mode,worldIdentity;
    private static FakePlayer player;
    private static ArmorStand occupant;
    private static ServerLevel probeLevel;
    private static ChunkPos probeChunk;
    private static final TicketType<ChunkPos> PROBE_TICKET=TicketType.create(
            "projectseele_r44_city_quality_probe",Comparator.comparingLong(ChunkPos::toLong),0);
    private static final JsonArray results=new JsonArray(),failures=new JsonArray();
    private static JsonObject lastWalk,lastDistrict;

    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(JOB.isEmpty()||done||event.phase!=TickEvent.Phase.END)return;
        try
        {
            if(++age<40)return;
            ServerLevel level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);
            if(level==null)throw new IllegalStateException("Missing city dimension");
            BlockPos origin=IntegratedNervMapBuilder.tokyo3Origin(level);
            if(input==null)initialise(level);
            level.resetEmptyTime();
            var district=Tokyo3RetractionSavedData.get(level).get(origin).orElseThrow();
            lastDistrict=districtState(district);
            if(district.faulted())throw new IllegalStateException("Movement fault: "+district.fault());
            switch(mode)
            {
                case "rooms" -> rooms(level,origin,district);
                case "capture" -> snapshot(level,origin,district,false);
                case "verify" -> snapshot(level,origin,district,true);
                case "travel", "interrupt", "resume" -> travel(level,origin,district);
                case "occupied" -> occupied(level,origin,district);
                default -> throw new IllegalStateException("Unknown quality mode "+mode);
            }
            if(age>integer("timeout_ticks",180000))throw new IllegalStateException("Quality job timed out");
        }
        catch(Throwable error)
        {
            try{cleanupProbe();}catch(Throwable cleanup){error.addSuppressed(cleanup);}
            try
            {
                JsonObject result=report(false);result.addProperty("error",error.toString());
                Files.writeString(Path.of(JOB+".failed.json"),pretty(result),StandardCharsets.UTF_8);
            }
            catch(Exception ignored){}
            done=true;ProjectSeele.LOGGER.error("R44 city quality fixture failed",error);
        }
    }

    @SubscribeEvent public static void stopping(ServerStoppingEvent event)
    {
        if(JOB.isEmpty())return;
        try{cleanupProbe();}
        catch(Exception error){ProjectSeele.LOGGER.error("R44 city probe teardown failed",error);}
    }

    private static void cleanupProbe() throws Exception
    {
        if(occupant!=null)
        {
            UUID id=occupant.getUUID();
            var live=probeLevel==null?null:probeLevel.getEntity(id);
            if(live!=null&&live!=occupant)
            {
                if(!(live instanceof ArmorStand)||!live.getTags().contains("r44_city_quality/"+worldIdentity))
                    throw new IllegalStateException("Active probe UUID resolved to a foreign actor; preserve it: "+id);
                live.discard();
            }
            occupant.discard();
            var remaining=probeLevel==null?null:probeLevel.getEntity(id);
            if(remaining!=null&&!remaining.isRemoved())throw new IllegalStateException("Active quality probe remained resident after discard: "+id);
            occupant=null;
        }
        if(probeLevel!=null&&probeChunk!=null)probeLevel.getChunkSource().removeRegionTicket(PROBE_TICKET,probeChunk,0,probeChunk);
        probeLevel=null;probeChunk=null;
    }

    private static void initialise(ServerLevel level) throws Exception
    {
        input=JsonParser.parseString(Files.readString(Path.of(JOB),StandardCharsets.UTF_8)).getAsJsonObject();
        Path world=level.getServer().getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize();
        if(!world.getFileName().toString().equals(com.projectseele.visual.NativeReviewWorldsR45.expectedName())
                ||!world.equals(Path.of(input.get("world").getAsString()).toAbsolutePath().normalize())
                ||level.getSeed()!=input.get("world_seed").getAsLong())
            throw new IllegalStateException("Wrong measured world identity");
        mode=input.get("mode").getAsString();
        // The identity is explicit and persisted beside the per-world snapshots.
        // Minecraft itself has no portable world UUID in LevelData.
        worldIdentity=input.get("world_id").getAsString();
        if(worldIdentity.isBlank())throw new IllegalStateException("Explicit world_id required");
        Tokyo3BuildingWorldIdentityR44.bindFirstIdentity(level,worldIdentity);
        output=Path.of(input.get("output").getAsString()).toAbsolutePath().normalize();
        snapshots=Path.of(input.get("snapshot_dir").getAsString()).toAbsolutePath().normalize();
        Files.createDirectories(output);Files.createDirectories(snapshots);
        Path identity=snapshots.resolve("world_identity.json");
        JsonObject expected=new JsonObject();expected.addProperty("world",world.toString());
        expected.addProperty("world_seed",level.getSeed());expected.addProperty("world_id",worldIdentity);
        expected.addProperty("dimension",level.dimension().location().toString());
        if(Files.exists(identity)&&!JsonParser.parseString(Files.readString(identity)).equals(expected))
            throw new IllegalStateException("Snapshot identity belongs to a different world");
        if(mode.equals("capture"))Files.writeString(identity,pretty(expected),StandardCharsets.UTF_8);
        else if(!mode.equals("rooms")&&!mode.equals("occupied")&&!Files.exists(identity))
            throw new IllegalStateException("Capture complete cargo before a movement test");
        player=FakePlayerFactory.get(level,new GameProfile(UUID.nameUUIDFromBytes(
                (worldIdentity+"/r44-city-quality").getBytes(StandardCharsets.UTF_8)),"R44CityQuality"));
        player.setGameMode(GameType.SURVIVAL);player.getAbilities().flying=false;
        player.noPhysics=false;player.setMaxUpStep(.6F);
        var d=Tokyo3RetractionSavedData.get(level).get(IntegratedNervMapBuilder.tokyo3Origin(level)).orElseThrow();
        startDepth=d.depth();
        requestedEndpointDepth=bool("retract",false)?ThirdTokyoSurfaceBuilder.maximumRetractionDepth(IntegratedNervMapBuilder.tokyo3Origin(level)):0;
        if(mode.equals("resume"))
        {
            JsonObject saved=JsonParser.parseString(Files.readString(output.resolve("interruption_checkpoint.json"))).getAsJsonObject();
            if(!saved.get("world_id").getAsString().equals(worldIdentity))throw new IllegalStateException("Foreign checkpoint");
            // A normal server save can complete more work than the requested checkpoint.
            // Its layer direction must remain the persisted one, never be reinitialised.
            if(d.depth()!=saved.get("depth").getAsInt()||d.targetDepth()!=saved.get("target").getAsInt()
                    ||d.queuedTargetDepth()!=saved.get("queued_target").getAsInt()
                    ||d.cursor()!=saved.get("tower_cursor").getAsInt()||d.voxelCursor()!=saved.get("voxel_cursor").getAsInt())
                throw new IllegalStateException("Reloaded district differs from durable checkpoint");
            reversed=saved.get("reversal_queued").getAsBoolean();
            checkpointDepth=saved.has("reversal_requested_at_depth")?saved.get("reversal_requested_at_depth").getAsInt():saved.get("depth").getAsInt();
            reversalBoundaryObserved=saved.has("reversal_atomic_boundary_observed")&&saved.get("reversal_atomic_boundary_observed").getAsBoolean();
            if(saved.has("original_requested_endpoint_depth")&&saved.get("original_requested_endpoint_depth").getAsInt()!=requestedEndpointDepth)
                throw new IllegalStateException("Resume input changed the original movement direction");
            requested=true;
        }
    }

    private static int base(BlockPos origin,ThirdTokyoSurfaceBuilder.TowerSpec tower,int depth)
    {
        if(depth==0)return origin.getY();
        int roof=origin.getY()+ThirdTokyoSurfaceBuilder.ceilingRoofRelativeY(tower,origin);
        int travel=Math.max(tower.height(),origin.getY()-roof);
        if(depth-travel<tower.height())throw new IllegalStateException("Complete endpoint required for tower cargo");
        return roof-tower.height()-1;
    }

    private static void settled(Tokyo3RetractionSavedData.StoredDistrict d)
    {
        if(d.depth()!=d.targetDepth()||d.cursor()!=0||d.voxelCursor()!=0||d.queuedTargetDepth()>=0)
            throw new IllegalStateException("Settled complete city required for rooms/snapshot");
    }

    private static JsonObject districtState(Tokyo3RetractionSavedData.StoredDistrict d)
    {
        JsonObject row=new JsonObject();row.addProperty("origin",d.origin().toShortString());row.addProperty("depth",d.depth());
        row.addProperty("target",d.targetDepth());row.addProperty("queued_target",d.queuedTargetDepth());row.addProperty("tower_cursor",d.cursor());
        row.addProperty("voxel_cursor",d.voxelCursor());row.addProperty("next_step_at",d.nextStepAt());row.addProperty("fault",d.fault());return row;
    }

    private static void load(ServerLevel level,BlockPos centre,int half)
    {
        for(int x=(centre.getX()-half-2)>>4;x<=(centre.getX()+half+2)>>4;x++)
            for(int z=(centre.getZ()-half-2)>>4;z<=(centre.getZ()+half+2)>>4;z++)level.getChunk(x,z);
    }

    private static void rooms(ServerLevel level,BlockPos origin,Tokyo3RetractionSavedData.StoredDistrict d) throws Exception
    {
        settled(d);var towers=ThirdTokyoSurfaceBuilder.movableBuildings(level);
        if(index>=towers.size()){finish("complete",failures.isEmpty());return;}
        var tower=towers.get(index);BlockPos centre=origin.offset(tower.x(),0,tower.z());
        int b=base(origin,tower,d.depth()),half=tower.halfSize();load(level,centre,half);
        JsonObject result=new JsonObject();result.addProperty("tower",index);result.addProperty("base",b);
        JsonArray doors=new JsonArray(),entranceCells=new JsonArray(),floors=new JsonArray(),flights=new JsonArray();
        Map<BlockPos,BlockState> doorBefore=new LinkedHashMap<>();
        try
        {
            for(int x=-1;x<=1;x++)for(int y=1;y<=3;y++)
            {
                BlockPos p=new BlockPos(centre.getX()+x,b+y,centre.getZ()+half);
                BlockState expected=TvTokyo3Architecture.entrance(x,y,half,tower);
                if(x==-1)expected=TvTokyo3Architecture.wall(y,x,tower);
                if(expected==null)expected=net.minecraft.world.level.block.Blocks.AIR.defaultBlockState();
                BlockState actual=level.getBlockState(p);
                boolean same=expected.is(ModBlocks.CITY_PERSONNEL_DOOR.get())?actual.is(ModBlocks.CITY_PERSONNEL_DOOR.get()):actual.equals(expected);
                JsonObject cell=new JsonObject();cell.addProperty("pos",p.toShortString());cell.addProperty("expected",expected.toString());cell.addProperty("actual",actual.toString());cell.addProperty("template_match",same);entranceCells.add(cell);
                if(!same)fail("ENTRANCE_COMPONENT_DIFFERS",p,actual.toString());
            }
            for(int x=0;x<=1;x++)for(int y=1;y<=2;y++)
            {
                BlockPos p=new BlockPos(centre.getX()+x,b+y,centre.getZ()+half);
                BlockState before=level.getBlockState(p);doorBefore.put(p,before);
                if(!before.is(ModBlocks.CITY_PERSONNEL_DOOR.get()))fail("MISSING_NATIVE_ENTRANCE",p,before.toString());
            }
            if(doorBefore.values().stream().allMatch(s->s.is(ModBlocks.CITY_PERSONNEL_DOOR.get())))
            {
                for(int x=0;x<=1;x++)
                {
                    BlockPos p=new BlockPos(centre.getX()+x,b+1,centre.getZ()+half);
                    BlockState before=level.getBlockState(p);
                    var use=before.use(level,player,InteractionHand.MAIN_HAND,new BlockHitResult(Vec3.atCenterOf(p),Direction.SOUTH,p,false));
                    boolean toggled=level.getBlockState(p).getValue(DoorBlock.OPEN)!=before.getValue(DoorBlock.OPEN)
                            &&level.getBlockState(p.above()).getValue(DoorBlock.OPEN)==level.getBlockState(p).getValue(DoorBlock.OPEN);
                    JsonObject q=new JsonObject();q.addProperty("x",x);q.addProperty("native_use_result",use.toString());q.addProperty("lower_upper_toggled",toggled);doors.add(q);
                    if(!toggled)fail("NATIVE_DOOR_USE_FAILED",p,use.toString());
                    ((DoorBlock)before.getBlock()).setOpen(player,level,level.getBlockState(p),p,true);
                }
                // Whole two-door threshold from each side, with native collision movement.
                for(int x=0;x<=1;x++)for(int sign:new int[]{-1,1})
                {
                    Vec3 start=new Vec3(centre.getX()+x+.5,b+1,centre.getZ()+half+.5+sign*1.25);
                    Vec3 end=new Vec3(start.x,start.y,start.z-sign*2.5);
                    if(d.depth()==0)walk(level,start,end,"door_"+x+"/direction_"+sign,true);
                    else
                    {
                        AABB body=body(new Vec3(start.x,start.y,centre.getZ()+half+.5));
                        if(!level.noCollision(player,body))fail("OPEN_DOOR_COLLISION",BlockPos.containing(start),body.toString());
                    }
                }
            }
            int last=(tower.height()-3)/6*6;
            for(int floor=0;floor<=last;floor+=6)
            {
                Map<Long,Vec3> walkable=new HashMap<>();int fixture=0,voids=0,unknown=0;
                for(int x=-half+1;x<half;x++)for(int z=-half+1;z<half;z++)
                {
                    BlockState expected=TvTokyo3Architecture.interior(x,floor,z,tower);
                    if(expected==null||expected.isAir()){voids++;continue;}
                    Vec3 p=new Vec3(centre.getX()+x+.5,b+floor+1,centre.getZ()+z+.5);
                    BlockPos feet=BlockPos.containing(p);
                    if(!level.noCollision(player,body(p)))
                    {
                        BlockState fitting=TvTokyo3Architecture.interior(x,floor+1,z,tower);
                        BlockState actual=level.getBlockState(feet);
                        if(fitting!=null&&!fitting.isAir()&&actual.equals(fitting))fixture++;
                        else {unknown++;fail("NON_TEMPLATE_FLOOR_OBSTRUCTION",feet,actual.toString());}
                        continue;
                    }
                    player.setPos(p);player.setOnGround(false);player.setDeltaMovement(Vec3.ZERO);
                    for(int step=0;step<4;step++)player.move(MoverType.SELF,new Vec3(0,-.2,0));
                    if(p.y-player.getY()>.26){fail("FULL_FLOOR_DROP",feet,"drop="+(p.y-player.getY()));continue;}
                    walkable.put(new BlockPos(x,0,z).asLong(),p);
                }
                Set<Long> reached=new HashSet<>();ArrayDeque<Long> queue=new ArrayDeque<>();
                // This is the declared lobby aisle outside the stairwell's
                // coreRight boundary rail, not an arbitrary discovered air cell.
                long seed=new BlockPos(-half+11,0,0).asLong();
                if(!walkable.containsKey(seed))fail("MISSING_FLOOR_LOBBY",new BlockPos(centre.getX()-half+11,b+floor+1,centre.getZ()),"Declared lobby aisle seed is blocked");
                else {reached.add(seed);queue.add(seed);}
                while(!queue.isEmpty())
                {
                    long k=queue.remove();BlockPos p=BlockPos.of(k);
                    for(int[] offset:new int[][]{{1,0},{-1,0},{0,1},{0,-1}})
                    {
                        long next=p.offset(offset[0],0,offset[1]).asLong();
                        if(reached.contains(next)||!walkable.containsKey(next))continue;
                        Vec3 from=walkable.get(k),to=walkable.get(next);
                        boolean clear=true;for(int step=1;step<=4;step++)if(!level.noCollision(player,body(from.lerp(to,step/4.0)))){clear=false;break;}
                        if(clear){reached.add(next);queue.add(next);}
                    }
                }
                int isolated=walkable.size()-reached.size(),unguarded=0,stairPorts=0;
                if(isolated>0&&walkable.containsKey(seed))fail("ISOLATED_FLOOR_CELLS",new BlockPos(centre.getX()-half+11,b+floor+1,centre.getZ()),"cells="+isolated);
                // Test the complete landing boundary. An opening that is a real
                // stair tread remains traversable; an unguarded void is a failure.
                for(var entry:walkable.entrySet())
                {
                    BlockPos local=BlockPos.of(entry.getKey());Vec3 feet=entry.getValue();
                    for(int[] offset:new int[][]{{1,0},{-1,0},{0,1},{0,-1}})
                    {
                        int xx=local.getX()+offset[0],zz=local.getZ()+offset[1];
                        if(Math.abs(xx)>=half||Math.abs(zz)>=half)continue;
                        BlockState nominal=TvTokyo3Architecture.interior(xx,floor,zz,tower);
                        if(nominal==null||!nominal.isAir())continue;
                        Vec3 next=feet.add(offset[0],0,offset[1]);
                        if(!level.noCollision(player,body(next)))continue;
                        boolean stairPort=false;
                        for(int tread=Math.max(0,floor-1);tread<=floor;tread++)
                        {
                            BlockState signed=TvTokyo3Architecture.interior(xx,tread,zz,tower);
                            if(signed!=null&&signed.getBlock() instanceof net.minecraft.world.level.block.StairBlock
                                    &&level.getBlockState(new BlockPos(centre.getX()+xx,b+tread,centre.getZ()+zz)).equals(signed))stairPort=true;
                        }
                        if(stairPort){stairPorts++;continue;}
                        player.setPos(next);player.setOnGround(false);player.setDeltaMovement(Vec3.ZERO);
                        for(int drop=0;drop<5;drop++)player.move(MoverType.SELF,new Vec3(0,-.2,0));
                        if(next.y-player.getY()>.61)
                        {unguarded++;fail("UNGUARDED_LANDING_VOID",BlockPos.containing(next),"floor="+floor+" from="+feet);}
                    }
                }
                JsonObject f=new JsonObject();f.addProperty("floor",floor);f.addProperty("walkable",walkable.size());f.addProperty("connected",reached.size());
                f.addProperty("connectivity_status",walkable.containsKey(seed)?"MEASURED":"UNKNOWN_BLOCKED_DECLARED_SEED");
                f.addProperty("signed_functional_fittings",fixture);f.addProperty("stair_openings",voids);f.addProperty("unknown_obstructions",unknown);f.addProperty("unguarded_landing_edges",unguarded);f.addProperty("declared_descending_stair_edges",stairPorts);f.addProperty("declared_lobby_seed_x",centre.getX()-half+11);floors.add(f);
                if(floor==last)continue;
                boolean north=(floor/6)%2==0;int lane=-half+(north?3:7),z0=-half+(north?10:5),direction=north?-1:1;
                for(int delta=-1;delta<=1;delta++)
                {
                    Vec3 from=new Vec3(centre.getX()+lane+delta+.5,b+floor+1,centre.getZ()+z0-direction+.5);
                    Vec3 to=new Vec3(from.x,b+floor+7,centre.getZ()+z0+direction*6+.5);
                    boolean up=walk(level,from,to,"stair_"+floor+"/lane_"+delta+"/up",false);
                    JsonObject upTrace=lastWalk.deepCopy();
                    boolean down=walk(level,to,from,"stair_"+floor+"/lane_"+delta+"/down",false);
                    JsonObject flight=new JsonObject();flight.addProperty("floor",floor);flight.addProperty("lane",delta);flight.addProperty("up",up);flight.addProperty("down",down);flight.add("up_trace",upTrace);flight.add("down_trace",lastWalk.deepCopy());flights.add(flight);
                }
            }
        }
        finally
        {
            doorBefore.forEach((p,state)->level.setBlock(p,state,2|16));
            for(var e:doorBefore.entrySet())if(!level.getBlockState(e.getKey()).equals(e.getValue()))throw new IllegalStateException("Door restoration failed at "+e.getKey());
        }
        result.add("entrance_cells",entranceCells);result.add("native_door_use",doors);result.add("complete_floors",floors);result.add("native_stair_physics",flights);results.add(result);index++;
    }

    private static boolean walk(ServerLevel level,Vec3 start,Vec3 end,String purpose,boolean flat)
    {
        player.setPos(start);player.setDeltaMovement(Vec3.ZERO);player.setOnGround(true);player.fallDistance=0;
        double low=start.y;int steps=0;
        for(;steps<240;steps++)
        {
            Vec3 remaining=end.subtract(player.position());double length=Math.hypot(remaining.x,remaining.z);
            if(length<.02)break;
            double speed=Math.min(.11,length);
            player.move(MoverType.SELF,new Vec3(remaining.x/length*speed,-.12,remaining.z/length*speed));low=Math.min(low,player.getY());
        }
        Vec3 beforeSettle=player.position();int settle=0;
        for(;settle<16;settle++)
        {
            player.travel(Vec3.ZERO);low=Math.min(low,player.getY());
            if(player.onGround())break;
        }
        boolean ok=player.position().distanceTo(end)<.32&&(!flat||low>=start.y-.2);
        lastWalk=new JsonObject();lastWalk.addProperty("start",start.toString());lastWalk.addProperty("end",end.toString());lastWalk.addProperty("before_settle",beforeSettle.toString());
        lastWalk.addProperty("after_settle",player.position().toString());lastWalk.addProperty("horizontal_moves",steps);lastWalk.addProperty("vanilla_travel_settle_steps",settle+1);lastWalk.addProperty("on_ground",player.onGround());lastWalk.addProperty("passed",ok);
        if(!ok)fail("NATIVE_WALK_FAILED",BlockPos.containing(start),purpose+" actual="+player.position()+" end="+end+" steps="+steps);
        return ok;
    }

    private static AABB body(Vec3 p){return new AABB(p.x-.28,p.y+.01,p.z-.28,p.x+.28,p.y+1.79,p.z+.28);}

    private static void snapshot(ServerLevel level,BlockPos origin,Tokyo3RetractionSavedData.StoredDistrict d,boolean verify) throws Exception
    {
        settled(d);var towers=ThirdTokyoSurfaceBuilder.movableBuildings(level);
        if(index>=towers.size()){finish("complete",failures.isEmpty());return;}
        var tower=towers.get(index);BlockPos centre=origin.offset(tower.x(),0,tower.z());int b=base(origin,tower,d.depth());load(level,centre,tower.halfSize());
        Path file=snapshots.resolve("tower_"+index+".nbt");CompoundTag expected=verify?NbtIo.readCompressed(file.toFile()):null;
        boolean immobileCore=level.getBlockState(centre).is(ModBlocks.RETRACTABLE_BUILDING_CORE.get());
        BlockPos centreSource=new BlockPos(centre.getX(),b,centre.getZ());
        if(immobileCore)
        {
            BlockState actual=level.getBlockState(centreSource);
            boolean valid=d.depth()==0?actual.is(ModBlocks.RETRACTABLE_BUILDING_CORE.get()):actual.equals(net.minecraft.world.level.block.Blocks.SEA_LANTERN.defaultBlockState());
            if(!valid||level.getBlockEntity(centreSource)!=null)fail("IMMUTABLE_CENTRE_STATE_OR_NBT_DIFFERS",centreSource,actual.toString());
        }
        Map<Long,CompoundTag> old=new HashMap<>();
        if(expected!=null)
        {
            if(!worldIdentity.equals(expected.getString("WorldID")))throw new IllegalStateException("Foreign tower snapshot");
            if(expected.getBoolean("FixedStreetCore")!=immobileCore)throw new IllegalStateException("Immutable core mask changed after cargo capture");
            for(Tag t:expected.getList("Cells",Tag.TAG_COMPOUND)){CompoundTag c=(CompoundTag)t;old.put(c.getLong("Pos"),c);}
        }
        ListTag cells=new ListTag();int checked=0,entities=0,mismatch=0,negative=0;
        int roof=origin.getY()+ThirdTokyoSurfaceBuilder.ceilingRoofRelativeY(tower,origin);
        for(int y=0;y<=tower.height()+3;y++)for(int x=-tower.halfSize();x<=tower.halfSize();x++)for(int z=-tower.halfSize();z<=tower.halfSize();z++)
        {
            if(x==0&&z==0&&y==0&&immobileCore)continue; // exact separately audited negative mask only
            BlockPos local=new BlockPos(x,y,z),p=new BlockPos(centre.getX()+x,b+y,centre.getZ()+z);
            if(tower.tv()&&Math.abs(x)==tower.halfSize()&&Math.abs(z)==tower.halfSize()&&p.getY()>roof&&p.getY()<=TvWorldPreviewTerrain.ROOF_Y)
            {
                BlockState fixed=level.getBlockState(p);
                if(!fixed.equals(net.minecraft.world.level.block.Blocks.IRON_BLOCK.defaultBlockState())||level.getBlockEntity(p)!=null)
                    fail("NEGATIVE_DOME_ANCHOR_STATE_OR_NBT_DIFFERS",p,fixed.toString());
                negative++;continue;
            }
            BlockState state=level.getBlockState(p);BlockEntity be=level.getBlockEntity(p);
            CompoundTag cell=new CompoundTag();cell.putLong("Pos",local.asLong());cell.put("State",NbtUtils.writeBlockState(state));
            if(be!=null){CompoundTag tag=be.saveWithFullMetadata();tag.remove("x");tag.remove("y");tag.remove("z");cell.put("NBT",tag);entities++;}
            if(!state.isAir()||be!=null)cells.add(cell);
            if(verify)
            {
                CompoundTag before=old.remove(local.asLong());
                boolean same=before==null?state.isAir()&&be==null:before.equals(cell);
                if(!same){mismatch++;fail("COMPLETE_CARGO_STATE_OR_NBT_CHANGED",p,"local="+local+" expected="+before+" actual="+cell);}
            }
            checked++;
        }
        if(verify&&!old.isEmpty())throw new IllegalStateException("Snapshot cells outside current cargo envelope");
        if(!verify)
        {
            if(Files.exists(file)&&!bool("replace_snapshot",false))throw new IllegalStateException("Snapshot already exists; explicit replacement required");
            CompoundTag tag=new CompoundTag();tag.putString("WorldID",worldIdentity);tag.putInt("Depth",d.depth());tag.putInt("Height",tower.height());tag.putInt("Half",tower.halfSize());tag.putBoolean("FixedStreetCore",immobileCore);tag.put("Cells",cells);NbtIo.writeCompressed(tag,file.toFile());
        }
        JsonObject result=new JsonObject();result.addProperty("tower",index);result.addProperty("full_prism_cells",checked);result.addProperty("block_entities",entities);
        result.addProperty("separately_checked_immutable_centre_cells",immobileCore?1:0);
        result.addProperty("negative_dome_anchor_cells",negative);result.addProperty("mismatches",mismatch);results.add(result);index++;
    }

    private static void travel(ServerLevel level,BlockPos origin,Tokyo3RetractionSavedData.StoredDistrict d) throws Exception
    {
        if(!requested)
        {
            if(!Files.exists(snapshots.resolve("tower_92.nbt")))throw new IllegalStateException("All 93 complete cargo snapshots required");
            if(d.depth()==requestedEndpointDepth&&d.targetDepth()==requestedEndpointDepth&&d.cursor()==0&&d.voxelCursor()==0&&d.queuedTargetDepth()<0)
                throw new IllegalStateException("Travel QA must start away from its requested endpoint; use explicit verify for a settled endpoint reread");
            if((d.targetDepth()==requestedEndpointDepth&&d.queuedTargetDepth()<0)||d.queuedTargetDepth()==requestedEndpointDepth)
            {
                JsonObject row=districtState(d);row.addProperty("kind","ADOPT_EXISTING_MATCHING_MOVEMENT");row.addProperty("requested_endpoint",requestedEndpointDepth);
                results.add(row);requested=true;return;
            }
            var r=Tokyo3RetractionDirector.request(level,origin,bool("retract",false));
            if(!r.accepted())throw new IllegalStateException(r.message());requested=true;
            JsonObject row=districtState(Tokyo3RetractionSavedData.get(level).get(origin).orElseThrow());
            row.addProperty("kind","MOVEMENT_REQUEST_ACCEPTED");row.addProperty("requested_endpoint",requestedEndpointDepth);row.addProperty("request_message",r.message());results.add(row);return;
        }
        if(bool("queue_reversal",false)&&!reversed&&d.voxelCursor()>0)
        {
            checkpointDepth=d.depth();var r=Tokyo3RetractionDirector.request(level,origin,!bool("retract",false));
            if(!r.accepted())throw new IllegalStateException("Reversal request rejected: "+r.message());reversed=true;
            JsonObject row=new JsonObject();row.addProperty("kind","PARTIAL_LAYER_REVERSAL_QUEUED");row.addProperty("depth",d.depth());row.addProperty("tower_cursor",d.cursor());row.addProperty("voxel_cursor",d.voxelCursor());results.add(row);return;
        }
        if(reversed&&!reversalBoundaryObserved&&d.depth()!=checkpointDepth)
        {
            int expectedBoundary=checkpointDepth+Integer.signum(requestedEndpointDepth-checkpointDepth);
            int reversedEndpoint=requestedEndpointDepth==0?ThirdTokyoSurfaceBuilder.maximumRetractionDepth(origin):0;
            if(d.depth()!=expectedBoundary||d.targetDepth()!=reversedEndpoint||d.queuedTargetDepth()>=0)
                throw new IllegalStateException("Queued reversal did not commit the original active layer before consuming the queued target");
            reversalBoundaryObserved=true;JsonObject row=districtState(d);row.addProperty("kind","REVERSAL_ATOMIC_LAYER_BOUNDARY_OBSERVED");
            row.addProperty("queued_at_depth",checkpointDepth);results.add(row);
        }
        if(mode.equals("interrupt")&&d.voxelCursor()>0)
        {
            // Save the actual district and all write-ahead journals before the root
            // stops/restarts this JVM. No forced process kill is hidden in the test.
            level.getServer().saveAllChunks(false,true,true);
            var saved=Tokyo3RetractionSavedData.get(level).get(origin).orElseThrow();
            JsonObject checkpoint=report(true);checkpoint.addProperty("depth",saved.depth());checkpoint.addProperty("target",saved.targetDepth());
            checkpoint.addProperty("queued_target",saved.queuedTargetDepth());checkpoint.addProperty("tower_cursor",saved.cursor());checkpoint.addProperty("voxel_cursor",saved.voxelCursor());
            checkpoint.addProperty("original_requested_endpoint_depth",requestedEndpointDepth);checkpoint.addProperty("reversal_requested_at_depth",checkpointDepth);
            checkpoint.addProperty("reversal_atomic_boundary_observed",reversalBoundaryObserved);
            checkpoint.addProperty("reversal_queued",reversed);Files.writeString(output.resolve("interruption_checkpoint.json"),pretty(checkpoint),StandardCharsets.UTF_8);
            finish("checkpoint",true);
            if(bool("halt_on_checkpoint",true))level.getServer().halt(false);return;
        }
        int expectedEndpoint=reversed?(requestedEndpointDepth==0?ThirdTokyoSurfaceBuilder.maximumRetractionDepth(origin):0):requestedEndpointDepth;
        if(d.depth()==expectedEndpoint&&d.targetDepth()==expectedEndpoint&&d.cursor()==0&&d.voxelCursor()==0&&d.queuedTargetDepth()<0)
        {
            if(bool("queue_reversal",false)&&(!reversed||!reversalBoundaryObserved))throw new IllegalStateException("Reversal has no observed atomic layer boundary");
            JsonObject row=new JsonObject();row.addProperty("kind","MOVEMENT_ENDPOINT_REACHED");row.addProperty("depth",d.depth());row.addProperty("ticks",age);results.add(row);
            mode="verify";index=0;return;
        }
    }

    private static void occupied(ServerLevel level,BlockPos origin,Tokyo3RetractionSavedData.StoredDistrict d) throws Exception
    {
        var towers=ThirdTokyoSurfaceBuilder.movableBuildings(level);
        if(index>=towers.size()){finish("complete",failures.isEmpty());return;}
        if(phase==0)
        {
            settled(d);var tower=towers.get(index);BlockPos centre=origin.offset(tower.x(),0,tower.z());int b=base(origin,tower,d.depth());load(level,centre,tower.halfSize());
            Tokyo3RetractionDirector.acquireTravelTickets(level,origin);
            if(!Tokyo3RetractionDirector.districtLoaded(level,origin))return;
            int next=d.depth()+(d.depth()==0?1:-1);
            if(Tokyo3RetractionDirector.travelOccupied(level,origin,d.depth(),next))
                throw new IllegalStateException("Unprobed negative occupancy control already blocked by an existing living actor; probe cannot establish causality for tower "+index);
            // PersistentEntitySectionManager consults shouldBeSaved() while
            // unloading/saving. A diagnostic actor must never enter the save.
            occupant=new ArmorStand(EntityType.ARMOR_STAND,level)
            {
                @Override public boolean shouldBeSaved(){return false;}
            };
            probeLevel=level;probeChunk=new ChunkPos(centre);
            level.getChunkSource().addRegionTicket(PROBE_TICKET,probeChunk,0,probeChunk);
            double probeY=bool("roof_occupancy",false)?b+tower.height()+4:b+1;
            occupant.setPos(centre.getX()+.5,probeY,centre.getZ()+.5);occupant.setNoGravity(true);occupant.noPhysics=true;
            occupant.addTag("r44_city_quality/"+worldIdentity);
            if(!level.addFreshEntity(occupant))throw new IllegalStateException("Native occupancy probe registration rejected");
            if(!Tokyo3RetractionDirector.travelOccupied(level,origin,d.depth(),next))
                throw new IllegalStateException("Production occupancy guard did not observe the sole added probe for tower "+index);
            startDepth=d.depth();var r=Tokyo3RetractionDirector.request(level,origin,startDepth==0);
            if(!r.accepted())throw new IllegalStateException("Occupied movement request rejected: "+r.message());timer=0;phase=1;return;
        }
        if(d.depth()!=startDepth||d.cursor()!=0||d.voxelCursor()!=0)throw new IllegalStateException("Occupied cargo was moved for tower "+index);
        if(!Tokyo3RetractionDirector.districtLoaded(level,origin))return;
        if(!Tokyo3RetractionDirector.travelOccupied(level,origin,startDepth,startDepth+(startDepth==0?1:-1)))
            throw new IllegalStateException("Added probe ceased to block the production guard for tower "+index);
        if(++timer<25)return;
        var cancel=Tokyo3RetractionDirector.request(level,origin,startDepth!=0);
        if(!cancel.accepted())throw new IllegalStateException("Could not cancel held fixture command: "+cancel.message());
        String probeUUID=occupant.getUUID().toString();cleanupProbe();
        if(Tokyo3RetractionDirector.travelOccupied(level,origin,startDepth,startDepth+(startDepth==0?1:-1)))
            throw new IllegalStateException("Post-probe negative occupancy control remained blocked for tower "+index);
        JsonObject row=new JsonObject();row.addProperty("tower",index);row.addProperty("depth",d.depth());row.addProperty("roof_occupancy",bool("roof_occupancy",false));row.addProperty("native_living_occupancy_ticks",timer);row.addProperty("movement_blocked",true);
        row.addProperty("unprobed_negative_guard_control",true);row.addProperty("probe_positive_guard_control",true);row.addProperty("removed_probe_negative_guard_control",true);
        row.addProperty("travel_chunks_full_during_hold",true);row.addProperty("probe_uuid",probeUUID);row.addProperty("unoccupied_actual_travel_validated_by_this_job",false);results.add(row);
        phase=0;index++;
    }

    private static void fail(String kind,BlockPos position,String details)
    {
        JsonObject row=new JsonObject();row.addProperty("tower",index);row.addProperty("kind",kind);row.addProperty("pos",position.toShortString());row.addProperty("details",details);failures.add(row);
    }
    private static boolean bool(String name,boolean fallback){return input.has(name)?input.get(name).getAsBoolean():fallback;}
    private static int integer(String name,int fallback){return input.has(name)?input.get(name).getAsInt():fallback;}
    private static JsonObject report(boolean passed)
    {
        JsonObject r=new JsonObject();r.addProperty("world_id",worldIdentity);r.addProperty("mode",mode);r.addProperty("passed",passed);
        if(lastDistrict!=null)r.add("actual_district",lastDistrict);r.addProperty("original_requested_endpoint",requestedEndpointDepth);
        r.addProperty("reversal_atomic_boundary_observed",reversalBoundaryObserved);
        r.addProperty("tower_cursor",index);r.addProperty("ticks",age);r.addProperty("native_client_walk",false);r.addProperty("visual_passed",false);
        r.add("objects",results);r.add("failures",failures);return r;
    }
    private static String pretty(JsonObject value){return new GsonBuilder().setPrettyPrinting().create().toJson(value);}
    private static void finish(String marker,boolean passed) throws Exception
    {
        cleanupProbe();
        JsonObject r=report(passed);Files.writeString(Path.of(JOB+"."+(passed?marker:"failed")+".json"),pretty(r),StandardCharsets.UTF_8);done=true;
    }
    private Tokyo3BuildingQualityR44(){}
}

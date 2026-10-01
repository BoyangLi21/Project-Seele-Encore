package com.projectseele.world;

import com.google.gson.*;
import com.mojang.authlib.GameProfile;
import com.projectseele.ProjectSeele;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.common.util.FakePlayer;
import net.minecraftforge.common.util.FakePlayerFactory;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Native use and collision at every current ordinary-building entrance. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class RegionalBuildingQualityR44
{
    private static final String JOB=System.getProperty("projectseele.r44RegionalBuildingQualityJob","");
    private static int age,index;private static boolean done;private static JsonObject input;
    private static JsonArray buildings;private static FakePlayer actor;
    private static final JsonArray results=new JsonArray(),failures=new JsonArray();
    private record Before(BlockState state,CompoundTag nbt){}
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(JOB.isEmpty()||done||event.phase!=TickEvent.Phase.END||++age<40)return;
        try
        {
            ServerLevel level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);
            if(input==null)
            {
                input=JsonParser.parseString(Files.readString(Path.of(JOB),StandardCharsets.UTF_8)).getAsJsonObject();
                Path world=event.getServer().getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize();
                if(!world.getFileName().toString().equals("SEELE_FIELD_R44_REVIEW")||!world.equals(Path.of(input.get("world").getAsString()).toAbsolutePath().normalize())||level.getSeed()!=input.get("world_seed").getAsLong())throw new IllegalStateException("Different measured ordinary-building world");
                if(!Tokyo3BuildingWorldIdentityR44.get(level).equals(input.get("world_id").getAsString()))throw new IllegalStateException("Different persisted WorldUUID");
                buildings=JsonParser.parseString(Files.readString(Path.of(input.get("catalogue").getAsString()),StandardCharsets.UTF_8)).getAsJsonObject().getAsJsonArray("buildings");
                if(buildings.size()!=193)throw new IllegalStateException("Complete 193 ordinary-building denominator required");
                actor=FakePlayerFactory.get(level,new GameProfile(UUID.nameUUIDFromBytes((input.get("world_id").getAsString()+"/regional-entrances-r44").getBytes(StandardCharsets.UTF_8)),"R44RegionalEntry"));
                actor.setGameMode(GameType.SURVIVAL);actor.getAbilities().flying=false;actor.noPhysics=false;actor.setMaxUpStep(.6F);
            }
            if(index<buildings.size()){test(level,buildings.get(index++).getAsJsonObject());return;}
            JsonObject report=report();report.addProperty("passed",failures.isEmpty());
            Files.writeString(Path.of(JOB+(failures.isEmpty()?".complete.json":".failed.json")),new GsonBuilder().setPrettyPrinting().create().toJson(report),StandardCharsets.UTF_8);done=true;
        }
        catch(Throwable error)
        {
            done=true;try{JsonObject report=report();report.addProperty("passed",false);report.addProperty("error",error.toString());Files.writeString(Path.of(JOB+".failed.json"),report.toString(),StandardCharsets.UTF_8);}catch(Exception ignored){}
            ProjectSeele.LOGGER.error("R44 complete regional entrance fixture failed",error);
        }
    }
    private static BlockPos pos(JsonArray a){return new BlockPos(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt());}
    private static Vec3 point(JsonArray a){return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static Before read(ServerLevel level,BlockPos p)
    {BlockEntity be=level.getBlockEntity(p);return new Before(level.getBlockState(p),be==null?null:be.saveWithFullMetadata().copy());}
    private static void test(ServerLevel level,JsonObject building)
    {
        String id=building.get("id").getAsString();JsonArray pairs=building.getAsJsonArray("public_doors"),uses=new JsonArray(),walks=new JsonArray();
        Map<BlockPos,Before> before=new LinkedHashMap<>();
        for(JsonElement item:pairs)
        {
            BlockPos p=pos(item.getAsJsonObject().getAsJsonArray("pos"));
            for(int dx=-1;dx<=1;dx++)for(int dz=-1;dz<=1;dz++)level.getChunk((p.getX()>>4)+dx,(p.getZ()>>4)+dz);
            before.put(p,read(level,p));before.put(p.above(),read(level,p.above()));
        }
        try
        {
            for(JsonElement item:pairs)
            {
                BlockPos p=pos(item.getAsJsonObject().getAsJsonArray("pos"));BlockState state=level.getBlockState(p);JsonObject use=new JsonObject();use.addProperty("pos",p.toShortString());
                if(!(state.getBlock() instanceof DoorBlock)||!state.hasProperty(DoorBlock.OPEN))
                {fail(id,"UNKNOWN_CURRENT_DOOR",p,state.toString());use.addProperty("passed",false);uses.add(use);continue;}
                Direction front=state.getValue(DoorBlock.FACING);
                actor.setPos(p.getX()+.5+front.getStepX()*1.5,p.getY(),p.getZ()+.5+front.getStepZ()*1.5);actor.setYRot(front.getOpposite().toYRot());
                var interaction=state.use(level,actor,InteractionHand.MAIN_HAND,new BlockHitResult(Vec3.atCenterOf(p),front,p,false));
                BlockState lower=level.getBlockState(p),upper=level.getBlockState(p.above());
                boolean toggled=lower.hasProperty(DoorBlock.OPEN)&&lower.getValue(DoorBlock.OPEN)!=state.getValue(DoorBlock.OPEN);
                boolean pair=upper.hasProperty(DoorBlock.OPEN)&&lower.getValue(DoorBlock.OPEN)==upper.getValue(DoorBlock.OPEN);
                use.addProperty("native_interaction",interaction.toString());use.addProperty("toggled",toggled);use.addProperty("upper_lower_consistent",pair);use.addProperty("passed",toggled&&pair);uses.add(use);
                if(!toggled||!pair)fail(id,"NATIVE_DOOR_USE_FAILED",p,"result="+interaction+" lower="+lower+" upper="+upper);
                ((DoorBlock)state.getBlock()).setOpen(actor,level,level.getBlockState(p),p,true);
            }
            // Some registered double-door use methods toggle their neighbour.
            // Their native use outcome remains above; open the whole tested
            // aperture together for the independent physical threshold pass.
            for(JsonElement item:pairs)
            {
                BlockPos p=pos(item.getAsJsonObject().getAsJsonArray("pos"));BlockState state=level.getBlockState(p);
                if(state.getBlock() instanceof DoorBlock door)door.setOpen(actor,level,state,p,true);
            }
            for(JsonElement item:building.getAsJsonArray("native_walk_cases"))
            {
                JsonObject test=item.getAsJsonObject();Vec3 start=point(test.getAsJsonArray("start")),end=point(test.getAsJsonArray("end"));
                int cx=(int)Math.floor(start.x)>>4,cz=(int)Math.floor(start.z)>>4;for(int dx=-1;dx<=1;dx++)for(int dz=-1;dz<=1;dz++)level.getChunk(cx+dx,cz+dz);
                actor.setPos(start);actor.setOnGround(true);actor.setDeltaMovement(Vec3.ZERO);actor.fallDistance=0;double low=start.y;int steps=0;
                for(;steps<160;steps++)
                {
                    Vec3 delta=end.subtract(actor.position());double distance=Math.hypot(delta.x,delta.z);if(distance<.02)break;double speed=Math.min(.11,distance);
                    actor.move(MoverType.SELF,new Vec3(delta.x/distance*speed,-.12,delta.z/distance*speed));low=Math.min(low,actor.getY());
                }
                Vec3 beforeSettle=actor.position();int settle=0;for(;settle<16;settle++){actor.travel(Vec3.ZERO);low=Math.min(low,actor.getY());if(actor.onGround())break;}
                boolean passed=actor.position().distanceTo(end)<.32&&low>=Math.min(start.y,end.y)-.2&&actor.onGround();
                JsonObject walk=new JsonObject();walk.addProperty("id",test.get("id").getAsString());walk.addProperty("start",start.toString());walk.addProperty("end",end.toString());walk.addProperty("before_settle",beforeSettle.toString());walk.addProperty("actual",actor.position().toString());walk.addProperty("minimum_y",low);walk.addProperty("on_ground",actor.onGround());walk.addProperty("vanilla_settle_steps",settle+1);walk.addProperty("passed",passed);walks.add(walk);
                if(!passed)fail(id,"NATIVE_THRESHOLD_WALK_FAILED",BlockPos.containing(start),walk.toString());
            }
        }
        finally
        {
            before.forEach((p,old)->
            {
                level.setBlock(p,old.state,2|16);
                if(old.nbt!=null){BlockEntity be=level.getBlockEntity(p);if(be==null)throw new IllegalStateException("Lost original door block entity at "+p);be.load(old.nbt.copy());be.setChanged();}
            });
            for(var entry:before.entrySet())if(!read(level,entry.getKey()).equals(entry.getValue()))throw new IllegalStateException("Complete original door state/NBT restoration failed at "+entry.getKey());
        }
        JsonObject result=new JsonObject();result.addProperty("building",id);result.add("native_door_pairs",uses);result.add("native_public_thresholds",walks);result.addProperty("complete_door_state_and_nbt_restored",true);results.add(result);
    }
    private static void fail(String id,String kind,BlockPos p,String details)
    {JsonObject row=new JsonObject();row.addProperty("building",id);row.addProperty("kind",kind);row.addProperty("pos",p.toShortString());row.addProperty("details",details);failures.add(row);}
    private static JsonObject report()
    {JsonObject report=new JsonObject();report.addProperty("objects_completed",results.size());report.addProperty("catalogue_denominator",193);report.addProperty("native_client_walk",false);report.addProperty("visual_passed",false);report.add("objects",results);report.add("failures",failures);return report;}
    private RegionalBuildingQualityR44(){}
}

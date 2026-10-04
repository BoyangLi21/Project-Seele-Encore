package com.projectseele.client.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.world.*;
import net.minecraft.client.Minecraft;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.*;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.*;
import net.minecraft.world.level.*;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.*;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.common.ForgeMod;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Fixedv5 component inputs; real keyed walking, live BE load, no authored blocks. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class FacilityComponentReviewR45
{
    private static final boolean ENABLED=Boolean.getBoolean("projectseele.r45FacilityComponentsReview");
    private static final Gson GSON=new GsonBuilder().setPrettyPrinting().create();
    private static final TicketType<ChunkPos> TICKET=TicketType.create("seele_v5_component_review",Comparator.comparingLong(ChunkPos::toLong),120);
    private static final Set<ChunkPos> leases=new HashSet<>();
    private static final JsonArray walks=new JsonArray(),entities=new JsonArray();
    private static JsonObject job,current,observation;
    private static JsonArray cases,beCases,path;
    private static Path output;
    private static volatile int index;
    private static int waypoint,caseAge,ackTicks,upTicks,beIndex,beTicks,restoreTicks,restoreStable;
    private static long beStartTime;
    private static volatile Vec3 target,clientPosition;
    private static volatile UUID clientId;
    private static volatile boolean clientGround,clientUp,actuating,finished;
    private static UUID actorId;
    private static CompoundTag original;
    private static JsonObject firstFailure,restoreDiagnostic;
    private static volatile boolean clientHorizontalCollision;
    private static volatile int clientContactSamples;
    private static int clientObservedCase=-1;
    private static volatile AABB clientBody;
    private static volatile float clientForwardImpulse;
    private static volatile Vec3 clientVelocity;
    private static volatile boolean clientStopped;
    private static volatile long clientSampleSerial;
    private static Vec3 beforeStopServerPosition;
    private static long lastStopClientSample=-1;
    private static int stopStableTicks;
    private static boolean startTeleported;
    private static Vec3 originalPosition;
    private static ResourceKey<Level> originalDimension;
    private static GameType originalMode;
    private static float originalYaw,originalPitch;
    private static volatile boolean restoring;
    private static boolean restored,oldPause,optionsSaved,originalNoPhysics;
    private static boolean BEonlyRecheck;
    private static String error="";
    private static ServerLevel active;
    private FacilityComponentReviewR45() { }

    @SubscribeEvent public static void client(TickEvent.ClientTickEvent event)
    {
        if(!ENABLED||event.phase!=TickEvent.Phase.END)return;
        var mc=Minecraft.getInstance();
        if(!optionsSaved){optionsSaved=true;oldPause=mc.options.pauseOnLostFocus;mc.options.pauseOnLostFocus=false;}
        keys(mc,false);clientUp=false;
        if(finished){mc.options.pauseOnLostFocus=oldPause;mc.stop();return;}
        if(mc.player==null||mc.level==null)return;
        clientPosition=mc.player.position();clientId=mc.player.getUUID();clientGround=mc.player.onGround();
        clientHorizontalCollision=mc.player.horizontalCollision;clientBody=mc.player.getBoundingBox();
        if(clientObservedCase!=index){clientObservedCase=index;clientContactSamples=0;}
        if(mc.screen instanceof net.minecraft.client.gui.screens.PauseScreen)mc.setScreen(null);
        clientVelocity=mc.player.getDeltaMovement();clientSampleSerial++;
        clientStopped=!mc.options.keyUp.isDown()&&!mc.options.keyDown.isDown()&&!mc.options.keyLeft.isDown()&&!mc.options.keyRight.isDown()
                &&mc.player.input.forwardImpulse==0&&mc.player.input.leftImpulse==0&&mc.player.zza==0&&mc.player.xxa==0
                &&clientVelocity.horizontalDistanceSqr()<.000001;
        if(!actuating||target==null||mc.screen!=null)return;
        clientStopped=false;
        Vec3 delta=target.subtract(mc.player.position());
        mc.player.setYRot((float)Math.toDegrees(Math.atan2(-delta.x,delta.z)));mc.player.setXRot(0);
        boolean move=delta.horizontalDistanceSqr()>.01;keys(mc,move);clientUp=move;
        if(move&&clientGround&&clientHorizontalCollision)clientContactSamples++;
        clientForwardImpulse=mc.player.input.forwardImpulse;
        mc.player.input.up=move;mc.player.input.forwardImpulse=move?1:0;mc.player.zza=move?1:0;mc.player.xxa=0;
    }
    private static void keys(Minecraft mc,boolean up)
    {
        mc.options.keyUp.setDown(up);mc.options.keyDown.setDown(false);mc.options.keyLeft.setDown(false);mc.options.keyRight.setDown(false);
        mc.options.keyJump.setDown(false);mc.options.keyShift.setDown(false);mc.options.keySprint.setDown(false);mc.options.keyUse.setDown(false);
        if(mc.player!=null){mc.player.input.up=up;mc.player.input.forwardImpulse=up?1:0;mc.player.input.leftImpulse=0;mc.player.zza=up?1:0;mc.player.xxa=0;if(!up)clientForwardImpulse=0;}
    }
    @SubscribeEvent public static void server(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||finished||event.phase!=TickEvent.Phase.END)return;
        var server=event.getServer();
        if(server.getPlayerList().getPlayers().isEmpty())return;
        var player=server.getPlayerList().getPlayers().get(0);
        try
        {
            require(server.getPlayerList().getPlayers().size()==1,"Component review requires exactly one real connected player");
            if(job==null)initialize(player);
            active.resetEmptyTime();
            if(restoring){restoreAck(player);return;}
            if(index<cases.size()){walk(player);return;}
            actuating=false;target=null;
            if(beIndex<beCases.size()){beProbe(player);return;}
            beginRestore(player);
        }
        catch(Exception failure)
        {
            if(error.isEmpty()){error=failure.toString();firstFailure=pose(player);firstFailure.addProperty("planned_target",String.valueOf(target));firstFailure.addProperty("case_index",index);firstFailure.addProperty("waypoint",waypoint);if(current!=null)firstFailure.add("input_case",current.deepCopy());if(observation!=null)firstFailure.add("actual_trace",observation.deepCopy());}
            ProjectSeele.LOGGER.error("V5 component review first failure",failure);
            actuating=false;target=null;
            if(original!=null&&!restoring)beginRestore(player);
            else{write();finished=true;}
        }
    }
    private static void initialize(ServerPlayer player) throws Exception
    {
        String name=System.getProperty("projectseele.r45FacilityComponentsJob","");
        String digest=System.getProperty("projectseele.r45FacilityComponentsJobSHA256","");
        require(!name.isEmpty()&&hash(Path.of(name)).equals(digest),"Exact current component job required");
        job=read(Path.of(name));require(job.get("bound").getAsBoolean(),"Component job remains UNBOUND");
        active=player.server.getLevel(FacilitySchemaV2.DIMENSION);require(active!=null,"Actual GeoFront absent");
        var walkJob=job.deepCopy();walkJob.addProperty("facility_scope","COMPONENT_WALK");
        var beJob=job.deepCopy();beJob.addProperty("facility_scope","COMPONENT_BE");
        BEonlyRecheck=job.has("BE_only_recheck")&&job.get("BE_only_recheck").getAsBoolean();
        var admitted=read(Path.of(job.get("candidate_binding").getAsString()));
        require(BEonlyRecheck==admitted.has("postrun_BE_recheck"),"BE-only phase differs from actual admitted postrun binding");
        require(FacilitySourceAdmissionR45.admit(active,beJob)&& (BEonlyRecheck||FacilitySourceAdmissionR45.admit(active,walkJob)),"Current composedv5 admission required");
        cases=readRef(job.getAsJsonObject("walk_inputs")).getAsJsonArray("cases");beCases=readRef(job.getAsJsonObject("BE_inputs")).getAsJsonArray("cases");
        require(cases.size()==165&&beCases.size()==17,"Complete fixedv5165/17 input set required");
        if(BEonlyRecheck)index=cases.size(); // execute0walk; inherit only the explicitly admitted165 receipt
        output=Path.of(job.get("output").getAsString()).toAbsolutePath().normalize();
        require(!output.startsWith(player.server.getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize())&&!Files.exists(output),"Fresh external component output required");
        require(player.getVehicle()==null,"Review refuses to detach an original mounted actor");
        actorId=player.getUUID();original=player.saveWithoutId(new CompoundTag()).copy();originalPosition=player.position();originalDimension=player.serverLevel().dimension();
        originalYaw=player.getYRot();originalPitch=player.getXRot();originalMode=player.gameMode.getGameModeForPlayer();originalNoPhysics=player.noPhysics;
        player.setGameMode(GameType.SURVIVAL);player.noPhysics=false;player.getAbilities().flying=false;player.onUpdateAbilities();
        player.setMaxUpStep(.6F);var step=player.getAttribute(ForgeMod.STEP_HEIGHT_ADDITION.get());if(step!=null)step.setBaseValue(0);
        require(Math.abs(player.maxUpStep()-.6)<.001,"Actual actor step height differs from measured0.6");
    }
    private static void walk(ServerPlayer player) throws Exception
    {
        if(current==null)
        {
            current=cases.get(index).getAsJsonObject();path=current.has("path")?current.getAsJsonArray("path"):null;
            Vec3 start=vec(path==null?current.getAsJsonArray("start"):path.get(0).getAsJsonArray());
            lease(active,new ChunkPos(BlockPos.containing(start)));
            target=null;waypoint=1;caseAge=ackTicks=upTicks=stopStableTicks=0;actuating=false;startTeleported=false;
            beforeStopServerPosition=null;lastStopClientSample=-1;
            observation=new JsonObject();observation.addProperty("id",current.get("id").getAsString());observation.addProperty("actual_actor_UUID",actorId.toString());observation.add("trace",new JsonArray());
        }
        require(++caseAge<3000,"Actual component route timeout: "+current.get("id"));
        if(caseAge%40==0)for(var at:leases)active.getChunkSource().addRegionTicket(TICKET,at,2,at);
        if(!startTeleported)
        {
            // Release actual keys and drain the previous client movement BEFORE
            // the single allowed case-start teleport. No repeated teleport or
            // wider0.3m staging tolerance masks a late old movement packet.
            boolean serverStable=beforeStopServerPosition!=null&&player.position().distanceToSqr(beforeStopServerPosition)<.000001;
            boolean freshClientSample=clientSampleSerial>lastStopClientSample;
            boolean stopACK=clientStopped&&clientId!=null&&clientId.equals(actorId)&&clientPosition!=null&&clientGround&&player.onGround()
                    &&clientPosition.distanceToSqr(player.position())<.0004&&serverStable&&freshClientSample;
            var prep=new JsonObject();prep.addProperty("phase","STOP_INPUT_BEFORE_SINGLE_TELEPORT");prep.addProperty("stop_ACK",stopACK);prep.addProperty("server_stable",serverStable);
            prep.addProperty("fresh_client_sample",freshClientSample);prep.addProperty("client_stopped",clientStopped);prep.addProperty("client_velocity",String.valueOf(clientVelocity));prep.add("actual_pose",pose(player));
            observation.add("initial_preparation",prep);
            if(!freshClientSample){if(!serverStable)stopStableTicks=0;return;}
            beforeStopServerPosition=player.position();lastStopClientSample=clientSampleSerial;
            if(!stopACK){stopStableTicks=0;return;}if(++stopStableTicks<3)return;
            Vec3 start=vec(path==null?current.getAsJsonArray("start"):path.get(0).getAsJsonArray());
            observation.addProperty("stop_ACK_stable_ticks",stopStableTicks);observation.addProperty("start_teleports",1);
            player.teleportTo(active,start.x,start.y,start.z,0,0);player.setDeltaMovement(Vec3.ZERO);player.fallDistance=0;
            target=start;startTeleported=true;ackTicks=0;return;
        }
        if(!actuating)
        {
            // SameXY/differentY must wait for the actual client teleport packet.
            boolean ack=clientId!=null&&clientId.equals(actorId)&&clientPosition!=null&&clientGround&&player.onGround()
                    &&clientPosition.distanceToSqr(target)<.09&&player.position().distanceToSqr(target)<.04;
            var prep=new JsonObject();prep.addProperty("phase","ACTUAL_CLIENT_SERVER3D_FLOOR_ACK_AFTER_SINGLE_TELEPORT");prep.addProperty("floor_ACK",ack);prep.addProperty("planned_start",String.valueOf(target));prep.add("actual_pose",pose(player));observation.add("initial_preparation_after_teleport",prep);
            if(!ack){ackTicks=0;return;}if(++ackTicks<3)return;
            target=vec(path==null?current.getAsJsonArray("target"):path.get(waypoint).getAsJsonArray());actuating=true;
        }
        lease(active,new ChunkPos(BlockPos.containing(target)));require(!player.noPhysics&&!player.getAbilities().flying&&player.getVehicle()==null,"Actual keyed actor physics changed");
        require(Math.abs(player.getBoundingBox().getXsize()-.6)<.001&&Math.abs(player.getBoundingBox().getYsize()-1.8)<.001,"Actual actor body differs from full0.6x1.8 plan");
        if(clientUp)upTicks++;
        Vec3 prior=vec(path==null?current.getAsJsonArray("start"):path.get(waypoint-1).getAsJsonArray());
        require(player.getY()>=Math.min(prior.y,target.y)-.65,"Actual component lost floor: "+player.position()+" target="+target);
        if(caseAge%5==0)observation.getAsJsonArray("trace").add(pose(player));
        if(path==null)
        {
            if(upTicks<current.get("actual_keys_ticks_min").getAsInt())return;
            require(player.getZ()<=current.get("expected_max_player_z").getAsDouble()&&player.onGround()&&clientGround,"Closed observation boundary passed or lost support");
            observation.add("native_boundary_shapes",boundaryShapes(active,player));
            observation.addProperty("actual_client_contact_samples",clientContactSamples);
            observation.addProperty("server_remote_horizontalCollision",player.horizontalCollision);
            boolean nativeForwardBlocked=!active.noCollision(player,player.getBoundingBox().move(0,0,.02));
            observation.addProperty("actual_native_forward_body_blocked",nativeForwardBlocked);
            require(player.position().subtract(prior).horizontalDistanceSqr()>.10&&clientHorizontalCollision&&clientContactSamples>=10&&nativeForwardBlocked,
                    "No actual client keyed/native collision against assigned boundary");completeWalk(player);return;
        }
        // Half-step points retain decimalY; transition may stand0.5 above the
        // next lower half. Flat datum and final endpoints require0.15 accuracy.
        boolean half=(prior.y!=target.y)||target.y!=Math.rint(target.y);double tolerance=half?.55:.15;
        boolean arrived=player.position().subtract(target).horizontalDistanceSqr()<.0225&&clientPosition!=null&&clientPosition.subtract(target).horizontalDistanceSqr()<.04
                &&Math.abs(player.getY()-target.y)<=tolerance&&Math.abs(clientPosition.y-target.y)<=tolerance&&player.onGround()&&clientGround;
        if(!arrived)return;
        observation.getAsJsonArray("trace").add(pose(player));
        if(++waypoint>=path.size()){completeWalk(player);return;}
        target=vec(path.get(waypoint).getAsJsonArray());
    }
    private static void completeWalk(ServerPlayer player)
    {
        observation.addProperty("actual_key_up_ticks",upTicks);observation.addProperty("passed",true);observation.add("final_pose",pose(player));walks.add(observation);
        ProjectSeele.LOGGER.info("V5 COMPONENT WALK {}/165 {}",index+1,current.get("id"));index++;current=null;actuating=false;target=null;
    }
    @SuppressWarnings({"rawtypes","unchecked"}) private static void beProbe(ServerPlayer player) throws Exception
    {
        var test=beCases.get(beIndex).getAsJsonObject();BlockPos at=BlockPos.containing(vec(test.getAsJsonArray("position")));ChunkPos chunk=new ChunkPos(at);
        lease(active,chunk);active.getChunkAt(at);
        if(!active.getChunkSource().isPositionTicking(chunk.toLong())){require(++caseAge<3000,"Exact BE chunk did not become ticking");return;}
        if(beTicks++==0)beStartTime=active.getGameTime();
        var state=active.getBlockState(at);require(net.minecraft.commands.arguments.blocks.BlockStateParser.serialize(state).equals(test.get("expected_full_state").getAsString()),"Actual BE position state changed");
        var be=active.getBlockEntity(at);boolean absent=test.get("expected_BE_absent").getAsBoolean();require((be==null)==absent,"Actual retired/live BE presence differs");
        if(be!=null)
        {
            require(be.getType().isValid(state),"Actual BE type is invalid for loaded state");
            CompoundTag wanted=TagParser.parseTag(test.get("expected_full_nbt").getAsString()),actual=be.saveWithFullMetadata();
            // keepPacked=false is a serialized loader hint, not retained payload.
            if(wanted.contains("keepPacked")&&!wanted.getBoolean("keepPacked")&&!actual.contains("keepPacked"))wanted.remove("keepPacked");
            require(retainedPayloadEqual(wanted,actual,state),"Actual loaded BE full payload differs: "+at+" actual="+actual);
        }
        if(active.getGameTime()-beStartTime<100)return;
        var row=new JsonObject();row.addProperty("id",test.get("id").getAsString());row.addProperty("position",at.toShortString());row.addProperty("actual_block_ticking",active.getChunkSource().isPositionTicking(chunk.toLong()));
        row.addProperty("actual_active_server_ticks",active.getGameTime()-beStartTime);row.addProperty("actual_state",net.minecraft.commands.arguments.blocks.BlockStateParser.serialize(state));row.addProperty("actual_BE_absent",be==null);
        if(be!=null){row.addProperty("actual_type",BuiltInRegistries.BLOCK_ENTITY_TYPE.getKey(be.getType()).toString());row.addProperty("full_NBT",be.saveWithFullMetadata().toString());row.addProperty("ticker_present",state.getTicker(active,(net.minecraft.world.level.block.entity.BlockEntityType)be.getType())!=null);}
        row.addProperty("passed_load_and_preservation",true);row.addProperty("relog_pass",BEonlyRecheck);entities.add(row);beIndex++;beTicks=caseAge=0;
    }
    private static boolean retainedPayloadEqual(CompoundTag wanted,CompoundTag actual,net.minecraft.world.level.block.state.BlockState state)
    {
        CompoundTag normalized=wanted.copy();
        if(state.getBlock() instanceof net.minecraft.world.level.block.SignBlock
                &&wanted.getString("id").equals("minecraft:sign")&&actual.getString("id").equals("minecraft:sign"))
        {
            for(String side:List.of("front_text","back_text"))
            {
                if(wanted.contains(side,Tag.TAG_COMPOUND)!=actual.contains(side,Tag.TAG_COMPOUND))return false;
                if(!wanted.contains(side,Tag.TAG_COMPOUND))continue;
                for(String field:List.of("messages","filtered_messages"))
                {
                    var before=wanted.getCompound(side);var after=actual.getCompound(side);
                    if(before.contains(field,Tag.TAG_LIST)!=after.contains(field,Tag.TAG_LIST))return false;
                    if(!before.contains(field,Tag.TAG_LIST))continue;
                    var beforeRaw=(ListTag)before.get(field);var afterRaw=(ListTag)after.get(field);
                    if(!beforeRaw.isEmpty()&&beforeRaw.getElementType()!=Tag.TAG_STRING
                            ||!afterRaw.isEmpty()&&afterRaw.getElementType()!=Tag.TAG_STRING)return false;
                    ListTag left=before.getList(field,Tag.TAG_STRING),right=after.getList(field,Tag.TAG_STRING);
                    if(left.size()!=right.size())return false;
                    ListTag same=new ListTag();
                    for(int i=0;i<left.size();i++)
                    {
                        // Only component JSON trees. No text/style/clickEvent,
                        // array order, side, waxing or other typedNBT waiver.
                        if(!JsonParser.parseString(left.getString(i)).equals(JsonParser.parseString(right.getString(i))))return false;
                        same.add(StringTag.valueOf(right.getString(i)));
                    }
                    normalized.getCompound(side).put(field,same);
                }
            }
        }
        return normalized.equals(actual);
    }
    private static void lease(ServerLevel level,ChunkPos at)
    {leases.add(at);level.getChunkSource().addRegionTicket(TICKET,at,2,at);}
    private static JsonArray boundaryShapes(ServerLevel level,ServerPlayer player)
    {
        var rows=new JsonArray();int x=(int)Math.floor(player.getX()),z=current.get("expected_closed_boundary_z").getAsInt(),feet=(int)Math.floor(player.getY());
        for(int y=feet;y<feet+6;y++)
        {
            var at=new BlockPos(x,y,z);var state=level.getBlockState(at);var row=new JsonObject();
            row.addProperty("position",at.toShortString());row.addProperty("actual_state",net.minecraft.commands.arguments.blocks.BlockStateParser.serialize(state));
            row.addProperty("actual_collision_AABBs",state.getCollisionShape(level,at,net.minecraft.world.phys.shapes.CollisionContext.of(player)).toAabbs().toString());rows.add(row);
        }
        return rows;
    }
    private static JsonObject pose(ServerPlayer player)
    {
        var row=new JsonObject();row.addProperty("server_feet",player.position().toString());row.addProperty("client_feet",String.valueOf(clientPosition));row.addProperty("server_on_ground",player.onGround());row.addProperty("client_on_ground",clientGround);row.addProperty("actual_client_key_up",clientUp);row.addProperty("actual_body",player.getBoundingBox().toString());row.addProperty("horizontal_collision",player.horizontalCollision);row.addProperty("actual_client_horizontal_collision",clientHorizontalCollision);row.addProperty("actual_client_contact_samples",clientContactSamples);row.addProperty("actual_client_forward_impulse",clientForwardImpulse);row.addProperty("actual_client_body",String.valueOf(clientBody));row.addProperty("actual_client_velocity",String.valueOf(clientVelocity));row.addProperty("actual_client_stopped_ACK",clientStopped);row.addProperty("actual_client_sample",clientSampleSerial);row.addProperty("health",player.getHealth());return row;
    }
    private static void beginRestore(ServerPlayer player)
    {
        actuating=false;target=null;restoring=true;restoreTicks=restoreStable=0;
        if(original==null){restored=true;write();finished=true;return;}
        player.setGameMode(originalMode);player.load(original.copy());player.noPhysics=originalNoPhysics;player.zza=0;player.xxa=0;player.teleportTo(player.server.getLevel(originalDimension),originalPosition.x,originalPosition.y,originalPosition.z,originalYaw,originalPitch);
        player.onUpdateAbilities();player.inventoryMenu.sendAllDataToRemote();player.containerMenu.broadcastChanges();
        player.connection.send(new net.minecraft.network.protocol.game.ClientboundSetExperiencePacket(player.experienceProgress,player.totalExperience,player.experienceLevel));
    }
    private static void restoreAck(ServerPlayer player)
    {
        ++restoreTicks;var mc=Minecraft.getInstance();CompoundTag after=player.saveWithoutId(new CompoundTag());
        restoreDiagnostic=new JsonObject();restoreDiagnostic.addProperty("original_position",String.valueOf(originalPosition));restoreDiagnostic.addProperty("server_position",player.position().toString());restoreDiagnostic.addProperty("client_position",String.valueOf(clientPosition));
        restoreDiagnostic.addProperty("server_original_position_ACK",player.position().distanceToSqr(originalPosition)<.04);restoreDiagnostic.addProperty("client_original_position_ACK",clientPosition!=null&&clientPosition.distanceToSqr(originalPosition)<.10);
        restoreDiagnostic.addProperty("inventory_typed_equal",Objects.equals(after.get("Inventory"),original.get("Inventory")));restoreDiagnostic.addProperty("server_slot",player.getInventory().selected);restoreDiagnostic.addProperty("original_slot",original.getInt("SelectedItemSlot"));
        restoreDiagnostic.addProperty("server_mode",player.gameMode.getGameModeForPlayer().toString());restoreDiagnostic.addProperty("original_mode",originalMode.toString());restoreDiagnostic.addProperty("server_health",player.getHealth());restoreDiagnostic.addProperty("original_health",original.getFloat("Health"));
        restoreDiagnostic.addProperty("server_XP",player.totalExperience+"/"+player.experienceLevel+"/"+player.experienceProgress);restoreDiagnostic.addProperty("original_XP",original.getInt("XpTotal")+"/"+original.getInt("XpLevel")+"/"+original.getFloat("XpP"));
        if(mc.player!=null&&mc.level!=null){restoreDiagnostic.addProperty("client_slot",mc.player.getInventory().selected);restoreDiagnostic.addProperty("client_mode",mc.gameMode.getPlayerMode().toString());restoreDiagnostic.addProperty("client_health",mc.player.getHealth());restoreDiagnostic.addProperty("client_XP",mc.player.totalExperience+"/"+mc.player.experienceLevel+"/"+mc.player.experienceProgress);restoreDiagnostic.addProperty("client_dimension",mc.level.dimension().location().toString());}
        restoreDiagnostic.addProperty("server_dimension",player.serverLevel().dimension().location().toString());restoreDiagnostic.addProperty("original_dimension",originalDimension.location().toString());restoreDiagnostic.addProperty("server_UUID_equal",player.getUUID().equals(actorId));restoreDiagnostic.addProperty("actual_client_forward_impulse",clientForwardImpulse);restoreDiagnostic.addProperty("restore_ticks",restoreTicks);
        boolean aligned=clientPosition!=null&&player.position().distanceToSqr(originalPosition)<.04&&clientPosition.distanceToSqr(originalPosition)<.10&&mc.player!=null&&mc.level!=null
                &&player.serverLevel().dimension().equals(originalDimension)&&mc.level.dimension().equals(originalDimension)&&player.getUUID().equals(actorId)
                &&Objects.equals(after.get("Inventory"),original.get("Inventory"))&&player.getInventory().selected==original.getInt("SelectedItemSlot")&&mc.player.getInventory().selected==original.getInt("SelectedItemSlot")
                &&player.gameMode.getGameModeForPlayer()==originalMode&&mc.gameMode.getPlayerMode()==originalMode&&Math.abs(player.getHealth()-original.getFloat("Health"))<.001&&Math.abs(mc.player.getHealth()-original.getFloat("Health"))<.001
                &&player.totalExperience==original.getInt("XpTotal")&&mc.player.totalExperience==original.getInt("XpTotal")&&player.experienceLevel==original.getInt("XpLevel")&&mc.player.experienceLevel==original.getInt("XpLevel")
                &&Math.abs(player.experienceProgress-original.getFloat("XpP"))<.001&&Math.abs(mc.player.experienceProgress-original.getFloat("XpP"))<.001;
        require(restoreTicks<600,"Original actor restoration not acknowledged: "+restoreDiagnostic);
        if(!aligned){restoreStable=0;return;}if(++restoreStable<8)return;
        restored=true;restoring=false;for(var at:leases)active.getChunkSource().removeRegionTicket(TICKET,at,2,at);leases.clear();write();finished=true;
    }
    private static void write()
    {
        if(output==null)return;
        try{var result=new JsonObject();result.addProperty("schema","projectseele.v5-component-native-receipt.v1");result.addProperty("error",error);result.addProperty("walk_required",BEonlyRecheck?0:165);result.addProperty("walk_complete",walks.size());result.addProperty("BE_required",17);result.addProperty("BE_complete",entities.size());result.addProperty("actual_actor_restored",restored);result.addProperty("fresh_session_pass",!BEonlyRecheck&&error.isEmpty()&&restored&&walks.size()==165&&entities.size()==17);result.addProperty("full_lifecycle_pass",false);result.addProperty("relog_pass",BEonlyRecheck&&error.isEmpty()&&restored&&walks.size()==0&&entities.size()==17);result.addProperty("walk_executed_this_run",walks.size());result.addProperty("walk_inherited",BEonlyRecheck?165:0);if(BEonlyRecheck)result.add("walk_inheritance",job.getAsJsonObject("walk_inheritance"));result.addProperty("phase",BEonlyRecheck?"SAME_QA_BE_ONLY_RELOG":"FRESH_COMPOSED_V5");result.add("walk_cases",walks);result.add("BE_cases",entities);if(firstFailure!=null)result.add("first_failure",firstFailure);if(restoreDiagnostic!=null)result.add("restore_ACK_diagnostic",restoreDiagnostic);if(original!=null)result.addProperty("original_actor_full_NBT",original.toString());Files.createDirectories(output.getParent());Files.writeString(output,GSON.toJson(result),StandardOpenOption.CREATE_NEW);}catch(Exception failure){throw new IllegalStateException("V5 receipt write failed",failure);}
    }
    private static JsonObject readRef(JsonObject ref) throws Exception
    {Path p=Path.of(ref.get("path").getAsString());require(hash(p).equals(ref.get("sha256").getAsString()),"Actual input file bytes changed");return read(p);}
    private static JsonObject read(Path p) throws Exception {return JsonParser.parseString(Files.readString(p)).getAsJsonObject();}
    private static String hash(Path p) throws Exception
    {var digest=MessageDigest.getInstance("SHA-256");try(var input=Files.newInputStream(p)){byte[] bytes=new byte[1024*1024];for(int n;(n=input.read(bytes))>=0;)if(n>0)digest.update(bytes,0,n);}return HexFormat.of().formatHex(digest.digest());}
    private static Vec3 vec(JsonArray v){require(v!=null&&v.size()==3,"Measured Vec3 required");return new Vec3(v.get(0).getAsDouble(),v.get(1).getAsDouble(),v.get(2).getAsDouble());}
    private static void require(boolean pass,String why){if(!pass)throw new IllegalStateException(why);}
}

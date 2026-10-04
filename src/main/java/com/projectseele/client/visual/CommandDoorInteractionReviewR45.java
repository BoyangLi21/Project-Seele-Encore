package com.projectseele.client.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervSlidingDoorEntity;
import com.projectseele.world.*;
import net.minecraft.client.Minecraft;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.*;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.*;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.*;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.*;
import net.minecraft.world.phys.shapes.*;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.*;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Real command-door inputs and full-width keyed crossing; no authored block writes. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class CommandDoorInteractionReviewR45
{
    private static final boolean ENABLED=Boolean.getBoolean("projectseele.r45CommandDoorsReview");
    private static final Gson GSON=new GsonBuilder().setPrettyPrinting().create();
    private static final TicketType<ChunkPos> TICKET=TicketType.create("seele_command17_review",Comparator.comparingLong(ChunkPos::toLong),120);
    private static final Set<ChunkPos> leases=new HashSet<>();
    private static final Map<Integer,JsonObject> owners=new HashMap<>();
    private static final JsonArray results=new JsonArray();
    private static JsonObject job,current,row,firstFailure,restoreDiagnostic;
    private static JsonArray cases,path;
    private static ServerLevel level;
    private static Path output;
    private static UUID actorId;
    private static CompoundTag original;
    private static ResourceKey<Level> originalDimension;
    private static GameType originalMode;
    private static Vec3 originalPosition,beforeStop;
    private static float originalYaw,originalPitch,entryHealth,originalServerStep,originalClientStep;
    private static boolean originalNoPhysics,oldPause,optionsSaved,restored,startTeleported;
    private static volatile String phase="STOP",error="";
    private static volatile int index;
    private static int age,caseAge,stageTicks,stopTicks,ackTicks,waypoint,holdTicks,restoreTicks,restoreStable,startupTicks;
    private static JsonObject startupDiagnostic,artViews;
    private static final JsonArray firstContactFrames=new JsonArray();
    private static long firstContactWalkTick=-1;
    private static boolean shortArt,firstContact;
    private static long firstContactScopeStart=-1;
    private static final JsonArray artPhotos=new JsonArray();
    private static volatile boolean photoQueued,photoComplete;
    private static volatile JsonObject photoAtCapture;
    private static int photoOrdinal,photoFrames;
    private static String photoNext;
    private static long lastStopSample=-1,holdStart;
    private static volatile long clientSerial;
    private static volatile Vec3 target,clientPosition,clientVelocity;
    private static volatile AABB clientBody;
    private static volatile UUID clientId;
    private static volatile ResourceKey<Level> clientDimension;
    private static volatile boolean clientGround,clientUp,clientStopped,used,finished,restoring;
    private static volatile float clientImpulse;
    private static volatile BlockPos useTarget;
    private static volatile JsonObject clientUse,serverUse;
    private CommandDoorInteractionReviewR45() {}

    @SubscribeEvent public static void client(TickEvent.ClientTickEvent event)
    {
        if(!ENABLED||event.phase!=TickEvent.Phase.END)return;
        var mc=Minecraft.getInstance();
        if(!optionsSaved){optionsSaved=true;oldPause=mc.options.pauseOnLostFocus;mc.options.pauseOnLostFocus=false;}
        keys(mc,false);clientUp=false;
        if(finished){mc.options.pauseOnLostFocus=oldPause;mc.stop();return;}
        if(mc.player==null||mc.level==null)return;
        if(mc.screen instanceof net.minecraft.client.gui.screens.PauseScreen)mc.setScreen(null);
        clientPosition=mc.player.position();clientBody=mc.player.getBoundingBox();clientId=mc.player.getUUID();clientDimension=mc.level.dimension();clientGround=mc.player.onGround();clientVelocity=mc.player.getDeltaMovement();clientSerial++;
        clientStopped=mc.player.input.forwardImpulse==0&&mc.player.input.leftImpulse==0&&mc.player.zza==0&&mc.player.xxa==0&&clientVelocity.horizontalDistanceSqr()<.000001;
        try
        {
            if(mc.screen!=null)return;
            if(phase.equals("PHOTO"))
            {
                Vec3 aim=vec(artViews.getAsJsonArray(photoOrdinal<2?"door_look_at":"cabin_look_at")).subtract(mc.player.getEyePosition());
                mc.player.setYRot((float)Math.toDegrees(Math.atan2(-aim.x,aim.z)));mc.player.setXRot((float)-Math.toDegrees(Math.atan2(aim.y,aim.horizontalDistance())));
                if(++photoFrames>=10&&!photoQueued)
                {
                    photoQueued=true;photoAtCapture=new JsonObject();photoAtCapture.addProperty("actual_client_position_at_pixels",mc.player.position().toString());photoAtCapture.addProperty("actual_client_gameTime_at_pixels",mc.level.getGameTime());photoAtCapture.addProperty("actual_client_onGround_at_pixels",mc.player.onGround());
                    var image=Minecraft.getInstance().getResourceManager().getResource(new net.minecraft.resources.ResourceLocation("projectseele","textures/entity/nerv_pressure_door_r45.png")).orElseThrow();
                    try(var bytes=image.open()){photoAtCapture.addProperty("actual_effective_pressure_texture_SHA256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes.readAllBytes())));}
                    net.minecraft.client.Screenshot.grab(output.getParent().toFile(),photoName(),mc.getMainRenderTarget(),message->{photoComplete=true;});
                }
                return;
            }
            if(phase.equals("USE")&&(mc.gameMode==null||mc.gameMode.getPlayerMode()!=GameType.SURVIVAL||!mc.player.getMainHandItem().isEmpty()))return;
            if(phase.equals("USE")&&!used&&useTarget!=null)
            {
                require(actorId!=null&&actorId.equals(clientId)&&clientGround&&clientDimension.equals(level.dimension()),"Actual input actor not grounded/aligned in GeoFront");
                require(clientPosition.distanceToSqr(vec(current.getAsJsonArray("staging")))<.09,"Actual client left input floor before use");
                var state=mc.level.getBlockState(useTarget);require(state.getBlock() instanceof ButtonBlock&&state.canSurvive(mc.level,useTarget),"Assigned actual native button/support refused");
                Vec3 eye=mc.player.getEyePosition();BlockHitResult chosen=null;double closest=Double.POSITIVE_INFINITY;
                for(var box:state.getShape(mc.level,useTarget).toAabbs())
                {
                    Vec3 point=box.getCenter().add(useTarget.getX(),useTarget.getY(),useTarget.getZ());double range=eye.distanceTo(point);
                    if(range>mc.gameMode.getPickRange()||range>=closest)continue;
                    Vec3 direction=point.subtract(eye);
                    var hit=mc.level.clip(new ClipContext(eye,point.add(direction.normalize().scale(.01)),ClipContext.Block.OUTLINE,ClipContext.Fluid.NONE,mc.player));
                    if(hit.getType()==HitResult.Type.BLOCK&&hit.getBlockPos().equals(useTarget)){chosen=hit;closest=range;}
                }
                require(chosen!=null,"No actual reachable OUTLINE on assigned command button: "+useTarget+" eye="+eye);
                Vec3 aim=chosen.getLocation().subtract(eye);mc.player.setYRot((float)Math.toDegrees(Math.atan2(-aim.x,aim.z)));mc.player.setXRot((float)-Math.toDegrees(Math.atan2(aim.y,aim.horizontalDistance())));
                var proof=new JsonObject();proof.addProperty("case_index",index);proof.addProperty("target",useTarget.toShortString());proof.addProperty("actual_eye",eye.toString());proof.addProperty("actual_reach",closest);proof.addProperty("actual_pick_range",mc.gameMode.getPickRange());proof.addProperty("actual_outline",state.getShape(mc.level,useTarget).toAabbs().toString());proof.addProperty("actual_hit",chosen.getLocation().toString());proof.addProperty("actual_face",chosen.getDirection().getName());proof.addProperty("actual_native_canSurvive",true);proof.addProperty("actual_client_tick",mc.level.getGameTime());
                proof.addProperty("actual_use_result",mc.gameMode.useItemOn(mc.player,InteractionHand.MAIN_HAND,chosen).name());clientUse=proof;used=true;
            }
            else if(phase.equals("WALK")&&target!=null)
            {
                Vec3 delta=target.subtract(mc.player.position());mc.player.setYRot((float)Math.toDegrees(Math.atan2(-delta.x,delta.z)));mc.player.setXRot(0);
                boolean move=delta.horizontalDistanceSqr()>.01;keys(mc,move);clientUp=move;clientStopped=false;clientImpulse=move?1:0;
            }
        }
        catch(Exception failure){error=failure.toString();}
    }
    private static void keys(Minecraft mc,boolean up)
    {
        mc.options.keyUp.setDown(up);mc.options.keyDown.setDown(false);mc.options.keyLeft.setDown(false);mc.options.keyRight.setDown(false);mc.options.keyJump.setDown(false);mc.options.keyShift.setDown(false);mc.options.keySprint.setDown(false);mc.options.keyUse.setDown(false);
        if(mc.player!=null){mc.player.input.up=up;mc.player.input.forwardImpulse=up?1:0;mc.player.input.leftImpulse=0;mc.player.zza=up?1:0;mc.player.xxa=0;clientImpulse=up?1:0;}
    }
    @SubscribeEvent(priority=EventPriority.LOWEST,receiveCanceled=true)
    public static void observe(PlayerInteractEvent.RightClickBlock event)
    {
        if(!ENABLED||!phase.equals("USE")||useTarget==null||!(event.getEntity() instanceof ServerPlayer p)||!p.getUUID().equals(actorId)||!event.getPos().equals(useTarget))return;
        var proof=new JsonObject();proof.addProperty("case_index",index);proof.addProperty("actor_UUID",actorId.toString());proof.addProperty("target",event.getPos().toShortString());proof.addProperty("actual_server_tick",p.serverLevel().getGameTime());proof.addProperty("hand",event.getHand().name());proof.addProperty("actual_hit",event.getHitVec().getLocation().toString());proof.addProperty("canceled",event.isCanceled());proof.addProperty("cancellation_result",event.getCancellationResult().name());proof.addProperty("actual_server_eye",p.getEyePosition().toString());serverUse=proof;
    }
    @SubscribeEvent public static void server(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||finished||event.phase!=TickEvent.Phase.END)return;
        var server=event.getServer();if(server.getPlayerList().getPlayers().isEmpty())return;
        var p=server.getPlayerList().getPlayers().get(0);
        try
        {
            require(server.getPlayerList().getPlayers().size()==1,"COMMAND17 requires one real connected player");
            if(job==null)initialize(p);
            if(original==null){if(!startupReady(p))return;captureOriginal(p);}
            if(restoring){restoreAck(p);return;}
            require(error.isEmpty(),error);require(++age<200000,"Whole COMMAND17 deadline");level.resetEmptyTime();
            if(phase.equals("PHOTO"))
            {
                require(++stageTicks<600,"Actual image write not acknowledged");if(!photoComplete)return;
                Path image=output.getParent().resolve("screenshots").resolve(photoName());require(Files.isRegularFile(image)&&Files.size(image)>0,"Actual screenshot bytes absent");
                var proof=photoAtCapture.deepCopy();proof.addProperty("path",image.toString());proof.addProperty("sha256",hash(image));proof.addProperty("view",photoName());proof.add("actual_server_pose_after_pixels",pose(p));if(photoOrdinal<2)proof.add("actual_current_door",doorEvidence(p));artPhotos.add(proof);phase=photoNext;return;
            }
            if(index>=cases.size()){if(shortArt&&!firstContact&&!phase.equals("CAR_DONE")){cabinPhoto(p);return;}restore(p);return;}
            if(current==null)begin(p);
            require(++caseAge<5000,"Actual COMMAND17 case timed out: "+current.get("id")+" phase="+phase);
            if(firstContact&&firstContactScopeStart>=0)require(level.getGameTime()-firstContactScopeStart<160,"First-contact scope ended at160 actual server gameTicks: "+phase);
            require(p.isAlive()&&p.getHealth()>=entryHealth-.01,"Actual command-door actor damaged");
            if(caseAge%40==0)for(var at:leases)level.getChunkSource().addRegionTicket(TICKET,at,2,at);
            if(phase.equals("STOP"))
            {
                boolean stable=beforeStop!=null&&p.position().distanceToSqr(beforeStop)<.000001;boolean fresh=clientSerial>lastStopSample;
                boolean ack=clientStopped&&actorId.equals(clientId)&&clientPosition!=null&&clientGround&&p.onGround()&&clientDimension!=null&&clientDimension.equals(p.serverLevel().dimension())&&clientPosition.distanceToSqr(p.position())<.0004&&stable&&fresh;
                row.add("initial_stop_ACK",pose(p));row.addProperty("server_stable",stable);row.addProperty("fresh_client_sample",fresh);
                if(!fresh){if(!stable)stopTicks=0;return;}beforeStop=p.position();lastStopSample=clientSerial;
                if(!ack){stopTicks=0;return;}if(++stopTicks<3)return;
                Vec3 at=vec(current.getAsJsonArray("staging"));p.teleportTo(level,at.x,at.y,at.z,0,0);p.setDeltaMovement(Vec3.ZERO);p.fallDistance=0;row.addProperty("start_teleports",1);row.addProperty("stop_stable_samples",stopTicks);phase="ACK";return;
            }
            if(phase.equals("ACK"))
            {
                Vec3 at=vec(current.getAsJsonArray("staging"));boolean ack=actorId.equals(clientId)&&clientPosition!=null&&clientGround&&p.onGround()&&clientDimension!=null&&clientDimension.equals(level.dimension())&&p.position().distanceToSqr(at)<.04&&clientPosition.distanceToSqr(at)<.09;
                row.add("initial_actual_3D_floor_ACK",pose(p));if(!ack){ackTicks=0;return;}if(++ackTicks<3)return;bearing(p);if(firstContact)firstContactScopeStart=level.getGameTime();phase="CLOSED";return;
            }
            if(phase.equals("CLOSED"))
            {
                if(!doorReady(p,false))return;
                if(shortArt&&!firstContact&&artPhotos.size()==0){startPhoto(0,"CLOSED");return;}
                row.add("before_closed_actual",doorEvidence(p));fixedInput(p);useTarget=pos(current.getAsJsonObject("button").getAsJsonArray("pos"));phase="USE";return;
            }
            if(phase.equals("USE"))
            {
                // Keep the target until BOTH endpoints observed the real use.
                if(clientUse==null||serverUse==null)return;
                require(clientUse.get("case_index").getAsInt()==index&&serverUse.get("case_index").getAsInt()==index,"Input observer case identity changed");
                require(serverUse.get("hand").getAsString().equals(InteractionHand.MAIN_HAND.name()),"Unexpected real server input hand");
                row.add("actual_client_use",clientUse.deepCopy());row.add("actual_server_use",serverUse.deepCopy());useTarget=null;phase="OPEN";return;
            }
            if(phase.equals("OPEN"))
            {
                if(!doorReady(p,true))return;
                if(shortArt&&!firstContact&&artPhotos.size()==1){startPhoto(1,"OPEN");return;}
                row.add("after_open_actual",doorEvidence(p));
                if(current.get("kind").getAsString().equals("input")){phase="CLOSE";return;}
                path=current.getAsJsonArray("path");waypoint=1;target=vec(path.get(waypoint).getAsJsonArray());phase="WALK";return;
            }
            if(phase.equals("WALK"))
            {
                if(job.has("first_contact_diagnostic")&&job.get("first_contact_diagnostic").getAsBoolean())firstContactProbe(p);
                require(!p.noPhysics&&!p.getAbilities().flying&&p.getVehicle()==null,"Actual player physics changed");
                require(Math.abs(p.getBoundingBox().getXsize()-.6)<.001&&Math.abs(p.getBoundingBox().getYsize()-1.8)<.001,"Actual full .6x1.8 body changed");
                require(clientBody!=null&&Math.abs(clientBody.getXsize()-.6)<.001&&Math.abs(clientBody.getYsize()-1.8)<.001,"Actual full client body changed");
                require(Math.abs(p.maxUpStep()-originalServerStep)<.001F&&Math.abs(Minecraft.getInstance().player.maxUpStep()-originalClientStep)<.001F,"Actual native per-endpoint step changed during keyed walking");
                Vec3 prior=vec(path.get(waypoint-1).getAsJsonArray());require(p.getY()>=Math.min(prior.y,target.y)-.65,"Actual floor lost before doorway: "+p.position());
                if(caseAge%5==0)row.getAsJsonArray("trace").add(pose(p));
                boolean arrived=clientPosition!=null&&p.position().subtract(target).horizontalDistanceSqr()<.06&&clientPosition.subtract(target).horizontalDistanceSqr()<.09&&Math.abs(p.getY()-target.y)<.20&&Math.abs(clientPosition.y-target.y)<.20&&p.onGround()&&clientGround;
                if(!arrived)return;bearing(p);row.getAsJsonArray("trace").add(pose(p));
                if(waypoint==current.get("threshold_waypoint").getAsInt())
                {
                    require(p.getBoundingBox().intersects(bounds())&&clientBody!=null&&clientBody.intersects(bounds())&&CommandRoomSlidingDoorDirector.apertureOccupied(level,current.get("door_id").getAsInt()),"Actual actor did not occupy assigned threshold");phase="OCCUPIED";target=null;holdStart=level.getGameTime();holdTicks=0;return;
                }
                if(++waypoint>=path.size()){target=null;phase="CLOSE";return;}target=vec(path.get(waypoint).getAsJsonArray());return;
            }
            if(phase.equals("OCCUPIED"))
            {
                require(p.getBoundingBox().intersects(bounds())&&clientBody!=null&&clientBody.intersects(bounds())&&CommandRoomSlidingDoorDirector.apertureOccupied(level,current.get("door_id").getAsInt())&&doorReady(p,true),"Actual actor occupied doorway failed to stay physically open");
                if(++holdTicks<current.get("occupied_hold_actual_ticks").getAsInt()||level.getGameTime()-holdStart<current.get("occupied_hold_actual_ticks").getAsInt())return;
                row.addProperty("actual_occupied_active_ticks",level.getGameTime()-holdStart);row.addProperty("occupied_keep_open_observed",true);row.addProperty("independent_expiry_without_auto18_refresh",current.get("occupied_expiry_without_auto_refresh_required").getAsBoolean());
                if(++waypoint>=path.size()){phase="CLOSE";return;}target=vec(path.get(waypoint).getAsJsonArray());phase="WALK";return;
            }
            if(phase.equals("CLOSE"))
            {
                if(!doorReady(p,false))return;row.add("after_clear_closed_actual",doorEvidence(p));row.addProperty("passed",true);results.add(row);ProjectSeele.LOGGER.info("R45 COMMAND17 {}/141 {}",index+1,current.get("id"));index++;current=null;target=null;phase=shortArt?"CAR_STOP":"STOP";beforeStop=null;lastStopSample=-1;stopTicks=stageTicks=ackTicks=0;
            }
        }
        catch(Exception failure)
        {
            if(error.isEmpty())error=failure.toString();if(firstFailure==null){firstFailure=pose(p);firstFailure.addProperty("error",error);firstFailure.addProperty("phase",phase);firstFailure.addProperty("case_index",index);firstFailure.addProperty("waypoint",waypoint);firstFailure.addProperty("planned_target",String.valueOf(target));if(current!=null)firstFailure.add("current_input",current.deepCopy());if(row!=null)firstFailure.add("actual_current_trace",row.deepCopy());
            if(level!=null&&current!=null)firstFailure.add("actual_current_door",doorEvidence(p));}ProjectSeele.LOGGER.error("R45 COMMAND17 first failure",failure);
            if(!restoring&&original!=null)restore(p);else{write();finished=true;}
        }
    }
    private static void firstContactProbe(ServerPlayer p)
    {
        require(shortArt&&current.get("id").getAsString().equals("cross/6/lane1/from-1"),"First-contact probe is limited to the actual failed lane");
        if(firstContactWalkTick<0)firstContactWalkTick=level.getGameTime();
        Vec3 delta=target.subtract(p.position());Vec3 desired=delta.horizontalDistanceSqr()<.000001?Vec3.ZERO:new Vec3(delta.x,0,delta.z).normalize().scale(Math.min(.15,delta.horizontalDistance()));
        var proof=pose(p);proof.addProperty("actual_server_gameTime",level.getGameTime());proof.addProperty("actual_client_gameTime",Minecraft.getInstance().level.getGameTime());proof.addProperty("actual_server_ticks_since_walk",level.getGameTime()-firstContactWalkTick);proof.addProperty("assigned_target",target.toString());proof.addProperty("direction_probe_not_Entity_move_input",desired.toString());
        proof.add("actual_six_cells_and_leaves",doorEvidence(p));var hold=new JsonArray();for(var d:doors(level)){var h=new JsonObject();h.addProperty("UUID",d.getUUID().toString());h.addProperty("actual_server_hold_ticks",d.reviewHoldTicksR45());h.addProperty("actual_progress",d.getOpenProgress(1));h.addProperty("target_progress",d.requestedOpenProgress());hold.add(h);}proof.add("actual_hold",hold);
        var server=collisionProbe(level,p,desired);proof.add("actual_server_collision_sources",server);var mc=Minecraft.getInstance();proof.add("actual_client_collision_sources",collisionProbe(mc.level,mc.player,desired));firstContactFrames.add(proof);
        require(!server.get("horizontal_sweep_blocked").getAsBoolean()&&!proof.getAsJsonObject("actual_client_collision_sources").get("horizontal_sweep_blocked").getAsBoolean(),"FIRST_ACTUAL_ASSIGNED_SWEEP_BLOCKED; exact gameTime/hold/cells/block/entity/provider witness retained");
        require(level.getGameTime()-firstContactWalkTick<160,"One failed lane made no completion in160 actual gameTicks; no5000tick spin");
    }
    private static JsonObject collisionProbe(Level world,net.minecraft.world.entity.Entity actor,Vec3 desired)
    {
        var result=new JsonObject();AABB body=actor.getBoundingBox(),sweep=body.expandTowards(desired);var nativeBlocks=new ArrayList<VoxelShape>();for(var shape:world.getBlockCollisions(actor,sweep))nativeBlocks.add(shape);
        var nativeEntities=world.getEntityCollisions(actor,sweep);var withTv=com.projectseele.world.TvCageCollisionR44.append(world,actor,sweep,nativeEntities);var all=new ArrayList<VoxelShape>(nativeBlocks);all.addAll(withTv);
        double z=Shapes.collide(net.minecraft.core.Direction.Axis.Z,body,all,desired.z);double x=Shapes.collide(net.minecraft.core.Direction.Axis.X,body.move(0,0,z),all,desired.x);
        result.addProperty("body",body.toString());result.addProperty("query_sweep",sweep.toString());result.addProperty("assigned_probe",desired.toString());result.addProperty("actual_shapes_clipped_x",x);result.addProperty("actual_shapes_clipped_z",z);result.addProperty("horizontal_sweep_blocked",Math.abs(x-desired.x)>.00001||Math.abs(z-desired.z)>.00001);
        result.addProperty("native_aggregate_block_shapes",nativeBlocks.toString());result.addProperty("native_entity_shapes",nativeEntities.toString());result.addProperty("TV_virtual_provider_enabled",com.projectseele.world.TvCageCollisionR44.enabled());result.addProperty("with_actual_TV_provider_shapes",withTv.toString());var cells=new JsonArray();
        for(BlockPos at:BlockPos.betweenClosed(BlockPos.containing(sweep.minX-.01,sweep.minY-.01,sweep.minZ-.01),BlockPos.containing(sweep.maxX+.01,sweep.maxY+.01,sweep.maxZ+.01)))
        {
            var state=world.getBlockState(at);var shape=state.getCollisionShape(world,at,CollisionContext.of(actor)).move(at.getX(),at.getY(),at.getZ());if(shape.isEmpty())continue;
            var cell=new JsonObject();cell.addProperty("pos",at.toShortString());cell.addProperty("state",BlockStateParser.serialize(state));cell.addProperty("block_class",state.getBlock().getClass().getName());cell.addProperty("actual_world_collision_boxes",shape.toAabbs().toString());cells.add(cell);
        }
        result.add("actual_neighbor_blocks",cells);var entities=new JsonArray();for(var e:world.getEntities(actor,sweep.inflate(1),e->true)){var row=new JsonObject();row.addProperty("UUID",e.getUUID().toString());row.addProperty("type",BuiltInRegistries.ENTITY_TYPE.getKey(e.getType()).toString());row.addProperty("class",e.getClass().getName());row.addProperty("body",e.getBoundingBox().toString());row.addProperty("noPhysics",e.noPhysics);row.addProperty("alive",e.isAlive());row.addProperty("collidable",e.canBeCollidedWith());row.addProperty("can_collide_with_actor",e.canCollideWith(actor));row.addProperty("pushable",e.isPushable());row.addProperty("tags",e.getTags().toString());entities.add(row);}result.add("actual_nearby_entities_including_invisible",entities);
        var cages=new JsonArray();for(var spec:NervLiftPassengerSync.managedLifts(level))
        {
            BlockPos at=S20MovingElevatorsAdapter.controllerPosition(spec,spec.lower());if(!world.hasChunkAt(at))continue;
            var tile=world.getBlockEntity(at);if(!(tile instanceof com.supermartijn642.movingelevators.blocks.ControllerBlockEntity controller)||!controller.hasGroup())continue;
            var group=controller.getGroup();var cage=group.getCage();var row=new JsonObject();row.addProperty("runtime_id",spec.id());row.addProperty("controller",at.toShortString());row.addProperty("group_actualY",group.getCurrentY());row.addProperty("moving",group.isMoving());row.addProperty("declared_size",group.getCageSizeX()+"/"+group.getCageSizeY()+"/"+group.getCageSizeZ());
            if(cage!=null){var anchor=group.getCageAnchorPos(group.getCurrentY());row.addProperty("world_cage_bounds",cage.bounds.move(anchor).toString());var hit=new JsonArray();for(var b:cage.collisionBoxes){var box=b.move(anchor);if(box.intersects(sweep))hit.add(box.toString());}row.add("actual_intersecting_native_cage_collision_boxes",hit);}else row.addProperty("native_cage_payload","NULL no invented bounding box");cages.add(row);
        }
        result.add("actual_MovingElevators_groups_readonly_no_reconcile",cages);return result;
    }
    private static String photoName(){return new String[]{"door6_closed.png","door6_open.png","tv22_cabin_inside.png"}[photoOrdinal];}
    private static void startPhoto(int ordinal,String next)
    {
        photoOrdinal=ordinal;photoNext=next;photoQueued=photoComplete=false;photoFrames=stageTicks=0;phase="PHOTO";
    }
    private static void cabinPhoto(ServerPlayer p)
    {
        require(++stageTicks<800,"Actual parked cabin inspection did not settle");
        if(phase.equals("CAR_STOP"))
        {
            boolean stable=beforeStop!=null&&p.position().subtract(beforeStop).horizontalDistanceSqr()<.000001;boolean fresh=clientSerial>lastStopSample;
            boolean ack=clientStopped&&fresh&&stable&&clientPosition!=null&&clientPosition.distanceToSqr(p.position())<.0004;
            if(!fresh)return;beforeStop=p.position();lastStopSample=clientSerial;if(!ack){stopTicks=0;return;}if(++stopTicks<3)return;
            Vec3 at=vec(artViews.getAsJsonArray("cabin_camera_feet"));lease(new ChunkPos(net.minecraft.core.BlockPos.containing(at)));
            var spec=NervLiftPassengerSync.managedLifts(level).stream().filter(v->v.id().equals("r25-west-observation")).findFirst().orElseThrow();
            var stop=spec.stops().stream().filter(v->v.walkY()==-394).findFirst().orElseThrow();require(NervLiftPassengerSync.carPresent(level,spec,stop),"Original TV22 cabin absent; no rebuild or fake lift entry");
            p.teleportTo(level,at.x,at.y,at.z,0,0);p.setDeltaMovement(Vec3.ZERO);p.fallDistance=0;stageTicks=0;phase="CAR_ACK";return;
        }
        Vec3 at=vec(artViews.getAsJsonArray("cabin_camera_feet"));boolean ack=clientPosition!=null&&p.onGround()&&clientGround&&p.position().distanceToSqr(at)<.04&&clientPosition.distanceToSqr(at)<.09;
        if(!ack){ackTicks=0;return;}if(++ackTicks<3)return;
        require(level.noCollision(p,p.getBoundingBox().deflate(.01)),"Inspection body obstructed");
        for(double dx:new double[]{-.25,0,.25})for(double dz:new double[]{-.25,0,.25})
        {
            Vec3 from=p.position().add(dx,.1,dz);var h=level.clip(new ClipContext(from,from.add(0,-.2,0),ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,p));require(h.getType()==HitResult.Type.BLOCK&&h.getDirection()==net.minecraft.core.Direction.UP&&Math.abs(h.getLocation().y-p.getY())<.03,"Actual cabin inspection lacks whole support");
        }
        startPhoto(2,"CAR_DONE");
    }
    private static void initialize(ServerPlayer p)throws Exception
    {
        Path input=Path.of(System.getProperty("projectseele.r45CommandDoorsJob",""));require(hash(input).equals(System.getProperty("projectseele.r45CommandDoorsJobSHA256","")),"Explicit exact COMMAND17 bound job required");job=read(input);
        require(!Boolean.getBoolean("projectseele.r45FacilityComponentsReview")&&!Boolean.getBoolean("projectseele.r45NervSecurityReview")&&!com.projectseele.visual.LiftPassengerR20Review.ENABLED,"One actual actor controller per process");
        require(job.get("bound").getAsBoolean()&&job.get("facility_scope").getAsString().equals("COMMAND17"),"COMMAND17 remains unbound or wrong scope");level=p.server.getLevel(FacilitySchemaV2.DIMENSION);require(level!=null&&FacilitySourceAdmissionR45.admit(level,job),"Actual current source COMMAND17 admission refused");
        var data=readRef(job.getAsJsonObject("inputs"));require(data.get("input_required").getAsInt()==39&&data.get("door_lines_required").getAsInt()==51&&data.get("directed_crossings_required").getAsInt()==102,"Complete39/51/102 set required");
        for(var raw:data.getAsJsonArray("owners")){var o=raw.getAsJsonObject();require(owners.put(o.get("id").getAsInt(),o)==null,"Repeated original owner");}require(owners.size()==17&&!owners.containsKey(5)&&!owners.containsKey(14),"Original17/manual exclusion changed");
        cases=data.getAsJsonArray("cases");require(cases.size()==141,"Complete141 real input/crossing cases required");var ids=new HashSet<String>();var expected=new HashSet<String>();
        for(var o:owners.values())
        {
            int id=o.get("id").getAsInt();for(var raw:o.getAsJsonArray("inputs"))expected.add(raw.getAsJsonObject().get("id").getAsString());
            for(int lane=-1;lane<=1;lane++)for(int side:new int[]{-1,1})expected.add("cross/"+id+"/lane"+lane+"/from"+side);
        }
        for(var raw:cases)require(ids.add(raw.getAsJsonObject().get("id").getAsString()),"Repeated real command case");require(expected.size()==141&&ids.equals(expected),"Real input/full directed lane set changed");
        if(job.has("short_art_preview_v13"))
        {
            shortArt=true;artViews=readRef(job.getAsJsonObject("short_art_preview_v13"));String selected=artViews.get("case_id").getAsString();require(selected.equals("cross/6/lane1/from-1"),"Only actual ID6 failing lane short preview is approved");
            var picked=new JsonArray();for(var raw:cases)if(raw.getAsJsonObject().get("id").getAsString().equals(selected))picked.add(raw);require(picked.size()==1,"Actual selected lane missing");cases=picked;
        }
        firstContact=job.has("first_contact_diagnostic")&&job.get("first_contact_diagnostic").getAsBoolean();
        require(!firstContact||shortArt,"First-contact diagnostic requires the one actual failed ID6 lane selection");
        Path world=p.server.getWorldPath(LevelResource.ROOT).toRealPath();require(hash(world.resolve(CommandRoomSlidingDoorDirector.MARKER)).equals(data.getAsJsonObject("required_marker_after").get("sha256").getAsString()),"Exact39 original/side-frame input marker is not actually installed");
        output=Path.of(job.get("output").getAsString()).toAbsolutePath().normalize();require(!output.startsWith(world)&&!Files.exists(output),"Fresh external COMMAND17 result required");Files.createDirectories(output.getParent());if(firstContact)captureRegisteredCabinMaterials();
    }
    private static void captureRegisteredCabinMaterials() throws Exception
    {
        var proof=new JsonObject();proof.addProperty("schema","projectseele.tv-cabin-registered-state-capture.r45.v1");
        proof.addProperty("captured_at_utc",java.time.Instant.now().toString());proof.addProperty("world_written",false);proof.addProperty("world_chunks_read_or_loaded",false);
        proof.addProperty("native_registry_and_geometry_executed",true);proof.addProperty("visual_or_user_approved",false);
        proof.addProperty("candidate_binding_sha256",job.get("candidate_binding_sha256").getAsString());proof.addProperty("world_id",job.get("world_id").getAsString());
        var states=new JsonArray();
        for(String name:List.of("tv_staff_lift_panel_r45","tv_staff_lift_band_r45","tv_utility_lift_ceiling_r45"))
        {
            var id=new net.minecraft.resources.ResourceLocation("projectseele",name);require(BuiltInRegistries.BLOCK.containsKey(id),"Actual cabin material not registered: "+id);
            var state=BuiltInRegistries.BLOCK.get(id).defaultBlockState();var row=new JsonObject();row.addProperty("state",BlockStateParser.serialize(state));
            row.addProperty("registered",true);row.addProperty("java_class",state.getBlock().getClass().getName());row.addProperty("state_count",state.getBlock().getStateDefinition().getPossibleStates().size());
            row.addProperty("has_block_entity",state.hasBlockEntity());row.addProperty("entity_block_factory",state.getBlock() instanceof net.minecraft.world.level.block.EntityBlock);
            var collision=state.getCollisionShape(EmptyBlockGetter.INSTANCE,BlockPos.ZERO,CollisionContext.empty());var outline=state.getShape(EmptyBlockGetter.INSTANCE,BlockPos.ZERO,CollisionContext.empty());
            row.add("native_collision_aabbs",GSON.toJsonTree(collision.toAabbs().stream().map(b->List.of(b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ)).toList()));
            row.add("native_outline_aabbs",GSON.toJsonTree(outline.toAabbs().stream().map(b->List.of(b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ)).toList()));
            row.addProperty("native_context","EmptyBlockGetter.INSTANCE / BlockPos.ZERO / CollisionContext.empty");states.add(row);
        }
        proof.add("states",states);var classes=new JsonObject();
        for(String resource:List.of("/com/projectseele/registry/ModBlocks.class","/com/projectseele/registry/ModItems.class","/com/projectseele/world/TvLiftFinishR45.class","/com/projectseele/world/S20MovingElevatorsAdapter.class","/com/projectseele/client/visual/CommandDoorInteractionReviewR45.class"))
        {
            try(var input=CommandDoorInteractionReviewR45.class.getResourceAsStream(resource))
            {require(input!=null,"Actual cabin source resource missing: "+resource);classes.addProperty(resource,HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(input.readAllBytes())));}
        }
        proof.add("actual_loaded_class_SHA256",classes);Files.writeString(output.getParent().resolve("cabin_registered_materials.native.json"),GSON.toJson(proof),StandardOpenOption.CREATE_NEW);
    }

    private static void captureOriginal(ServerPlayer p)throws Exception
    {
        originalServerStep=p.maxUpStep();originalClientStep=Minecraft.getInstance().player.maxUpStep();
        actorId=p.getUUID();original=p.saveWithoutId(new CompoundTag()).copy();originalPosition=p.position();originalDimension=p.serverLevel().dimension();originalYaw=p.getYRot();originalPitch=p.getXRot();originalMode=p.gameMode.getGameModeForPlayer();originalNoPhysics=p.noPhysics;entryHealth=p.getHealth();Files.writeString(output.resolveSibling("player_before.snbt"),original.toString(),StandardOpenOption.CREATE_NEW);
        p.setGameMode(GameType.SURVIVAL);p.noPhysics=false;p.getAbilities().flying=false;p.onUpdateAbilities();p.setItemInHand(InteractionHand.MAIN_HAND,ItemStack.EMPTY);p.inventoryMenu.broadcastChanges();startupDiagnostic.addProperty("actual_original_server_step",originalServerStep);startupDiagnostic.addProperty("actual_original_client_step",originalClientStep);
        startupDiagnostic.addProperty("actual_server_step_after_survival",p.maxUpStep());startupDiagnostic.addProperty("actual_client_step_at_input_ready",Minecraft.getInstance().player.maxUpStep());
        var serverAddition=p.getAttribute(net.minecraftforge.common.ForgeMod.STEP_HEIGHT_ADDITION.get());var clientAddition=Minecraft.getInstance().player.getAttribute(net.minecraftforge.common.ForgeMod.STEP_HEIGHT_ADDITION.get());
        startupDiagnostic.addProperty("actual_server_Forge_step_addition",serverAddition==null?0:serverAddition.getValue());startupDiagnostic.addProperty("actual_client_Forge_step_addition",clientAddition==null?0:clientAddition.getValue());
        require(Math.abs(p.maxUpStep()-1.0F)<.001F&&Math.abs(Minecraft.getInstance().player.maxUpStep()-.6F)<.001F
                &&(serverAddition==null||serverAddition.getValue()==0)&&(clientAddition==null||clientAddition.getValue()==0),
                "Actual native server1.0/client0.6 unchanged pair required: "+startupDiagnostic);
    }
    private static boolean startupReady(ServerPlayer p)
    {
        var mc=Minecraft.getInstance();startupDiagnostic=pose(p);startupDiagnostic.addProperty("startup_ticks",++startupTicks);
        var vehicle=p.getVehicle();startupDiagnostic.addProperty("actual_vehicle",vehicle==null?"NONE":BuiltInRegistries.ENTITY_TYPE.getKey(vehicle.getType())+" "+vehicle.getUUID());
        require(vehicle==null,"Actual original mounted actor refused: "+startupDiagnostic);
        require(startupTicks<800,"Actual startup client/server floor did not settle: "+startupDiagnostic);
        boolean aligned=mc.player!=null&&mc.level!=null&&mc.getSingleplayerServer()==p.server
                &&mc.player.getUUID().equals(p.getUUID())&&mc.level.dimension().equals(p.serverLevel().dimension())
                &&p.onGround()&&mc.player.onGround()&&p.position().distanceToSqr(mc.player.position())<.0004;
        startupDiagnostic.addProperty("actual_client_server_floor_ready",aligned);if(!aligned)return false;
        var rays=new JsonArray();
        for(double dx:new double[]{-.25,0,.25})for(double dz:new double[]{-.25,0,.25})
        {
            Vec3 from=p.position().add(dx,.1,dz);var hit=p.serverLevel().clip(new ClipContext(from,from.add(0,-.75,0),ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,p));
            boolean supported=hit.getType()==HitResult.Type.BLOCK&&hit.getDirection()==net.minecraft.core.Direction.UP&&Math.abs(p.getY()-hit.getLocation().y)<.03;
            var r=new JsonObject();r.addProperty("ray",from.toString());r.addProperty("actual_hit",hit.getLocation().toString());r.addProperty("exact_original_floor_supported",supported);rays.add(r);if(!supported){startupDiagnostic.add("actual_bearing_rays",rays);return false;}
        }
        startupDiagnostic.add("actual_bearing_rays",rays);return p.serverLevel().noCollision(p,p.getBoundingBox().deflate(.01));
    }
    private static void begin(ServerPlayer p)
    {
        current=cases.get(index).getAsJsonObject();caseAge=stageTicks=stopTicks=ackTicks=holdTicks=0;beforeStop=null;lastStopSample=-1;used=false;clientUse=serverUse=null;useTarget=null;target=null;phase="STOP";row=new JsonObject();row.addProperty("id",current.get("id").getAsString());row.addProperty("actual_actor_UUID",actorId.toString());row.add("trace",new JsonArray());
        lease(new ChunkPos(pos(current.getAsJsonObject("button").getAsJsonArray("pos"))));lease(new ChunkPos(BlockPos.containing(vec(current.getAsJsonArray("staging")))));
        if(current.has("path"))for(var point:current.getAsJsonArray("path"))lease(new ChunkPos(BlockPos.containing(vec(point.getAsJsonArray()))));
    }
    private static void fixedInput(ServerPlayer p)
    {
        var input=current.getAsJsonObject("button");var support=current.getAsJsonObject("fixed_support");BlockPos at=pos(input.getAsJsonArray("pos")),back=pos(support.getAsJsonArray("pos"));var state=level.getBlockState(at);
        require(state.getBlock() instanceof ButtonBlock&&state.canSurvive(level,at)&&level.getBlockEntity(at)==null&&level.getBlockEntity(back)==null,"Actual assigned input/support is foreign or unsafe");
        require(BlockStateParser.serialize(state).replace("powered=true","powered=false").equals(input.get("state").getAsString().replace("powered=true","powered=false"))&&BlockStateParser.serialize(level.getBlockState(back)).equals(support.get("state").getAsString()),"Complete original button/support changed");
    }
    private static AABB bounds()
    {
        var o=owners.get(current.get("door_id").getAsInt());BlockPos p=pos(o.getAsJsonArray("lower"));boolean x=o.get("axis").getAsString().equals("x");return new AABB(p.getX()-(x?1:0),p.getY(),p.getZ()-(x?0:1),p.getX()+(x?2:1),p.getY()+2,p.getZ()+(x?1:2));
    }
    private static List<NervSlidingDoorEntity> doors(Level l)
    {return l.getEntitiesOfClass(NervSlidingDoorEntity.class,bounds().inflate(3),e->e.getDoorId()==current.get("door_id").getAsInt());}
    private static boolean doorReady(ServerPlayer p,boolean opened)
    {
        var server=doors(level);var mc=Minecraft.getInstance();if(server.size()!=1||mc.level==null||mc.player==null||!mc.level.dimension().equals(level.dimension()))return false;var client=doors(mc.level);if(client.size()!=1||!client.get(0).getUUID().equals(server.get(0).getUUID()))return false;
        boolean axis=owners.get(current.get("door_id").getAsInt()).get("axis").getAsString().equals("x");require(server.get(0).isAxisX()==axis&&client.get(0).isAxisX()==axis,"Actual owner axis changed");
        BlockPos lower=pos(owners.get(current.get("door_id").getAsInt()).getAsJsonArray("lower"));Vec3 centre=new Vec3(lower.getX()+.5,lower.getY(),lower.getZ()+.5);
        require(server.get(0).position().distanceToSqr(centre)<.000001&&client.get(0).position().distanceToSqr(centre)<.000001,"Actual original door leaf centre moved");
        float a=server.get(0).getOpenProgress(1),b=client.get(0).getOpenProgress(1);if(opened?a<.99||b<.99:a>.01||b>.01)return false;
        var o=owners.get(current.get("door_id").getAsInt());for(var r:o.getAsJsonArray("aperture"))
        {
            BlockPos at=pos(r.getAsJsonObject().getAsJsonArray("pos"));var s=level.getBlockState(at);require(level.getBlockEntity(at)==null&&(s.isAir()||s.is(net.minecraft.world.level.block.Blocks.BARRIER)),"Foreign state/BE in owned aperture");var shape=s.getCollisionShape(level,at,CollisionContext.of(p));
            if(opened){if(!s.isAir()||!shape.isEmpty())return false;}
            else if(!s.is(net.minecraft.world.level.block.Blocks.BARRIER)||Shapes.joinIsNotEmpty(Shapes.create(new AABB(0,0,0,1,1,1).deflate(.01)),shape,BooleanOp.ONLY_FIRST))return false;
            var cs=mc.level.getBlockState(at);require(mc.level.getBlockEntity(at)==null&&(cs.isAir()||cs.is(net.minecraft.world.level.block.Blocks.BARRIER)),"Actual client aperture has foreign state/BE");var clientShape=cs.getCollisionShape(mc.level,at,CollisionContext.of(mc.player));
            if(opened){if(!cs.isAir()||!clientShape.isEmpty())return false;}
            else if(!cs.is(net.minecraft.world.level.block.Blocks.BARRIER)||Shapes.joinIsNotEmpty(Shapes.create(new AABB(0,0,0,1,1,1).deflate(.01)),clientShape,BooleanOp.ONLY_FIRST))return false;
        }
        return true;
    }
    private static JsonObject doorEvidence(ServerPlayer p)
    {
        var proof=new JsonObject();proof.addProperty("door_id",current.get("door_id").getAsInt());proof.addProperty("actual_server_tick",level.getGameTime());var cells=new JsonArray();
        for(var raw:owners.get(current.get("door_id").getAsInt()).getAsJsonArray("aperture"))
        {
            BlockPos at=pos(raw.getAsJsonObject().getAsJsonArray("pos"));var s=level.getBlockState(at);var c=new JsonObject();c.addProperty("pos",at.toShortString());c.addProperty("state",BlockStateParser.serialize(s));c.addProperty("collision",s.getCollisionShape(level,at,CollisionContext.of(p)).toAabbs().toString());c.addProperty("outline",s.getShape(level,at,CollisionContext.of(p)).toAabbs().toString());if(Minecraft.getInstance().level!=null&&Minecraft.getInstance().player!=null){var cl=Minecraft.getInstance().level;c.addProperty("actual_client_state",BlockStateParser.serialize(cl.getBlockState(at)));c.addProperty("actual_client_collision",cl.getBlockState(at).getCollisionShape(cl,at,CollisionContext.of(Minecraft.getInstance().player)).toAabbs().toString());}if(level.getBlockEntity(at)!=null)c.addProperty("full_NBT",level.getBlockEntity(at).saveWithFullMetadata().toString());cells.add(c);
        }
        proof.add("actual_complete6_cells",cells);var leaves=new JsonArray();for(var d:doors(level)){var r=new JsonObject();r.addProperty("UUID",d.getUUID().toString());r.addProperty("actual_position",d.position().toString());r.addProperty("axis_x",d.isAxisX());r.addProperty("actual_progress",d.getOpenProgress(1));r.addProperty("requested_progress",d.requestedOpenProgress());leaves.add(r);}proof.add("actual_server_leaves",leaves);
        if(Minecraft.getInstance().level!=null){var list=new JsonArray();for(var d:doors(Minecraft.getInstance().level)){var r=new JsonObject();r.addProperty("UUID",d.getUUID().toString());r.addProperty("actual_position",d.position().toString());r.addProperty("actual_progress",d.getOpenProgress(1));list.add(r);}proof.add("actual_client_leaves",list);}
        var occupied=new JsonArray();for(var e:level.getEntities((net.minecraft.world.entity.Entity)null,bounds(),e->e.isAlive()&&!(e instanceof NervSlidingDoorEntity))){var r=new JsonObject();r.addProperty("UUID",e.getUUID().toString());r.addProperty("type",BuiltInRegistries.ENTITY_TYPE.getKey(e.getType()).toString());r.addProperty("actual_body",e.getBoundingBox().toString());occupied.add(r);}proof.add("actual_occupied_entities",occupied);return proof;
    }
    private static void bearing(ServerPlayer p)
    {
        require(level.noCollision(p,p.getBoundingBox().deflate(.01)),"Actual full actor body collision");var rays=new JsonArray();
        for(double dx:new double[]{-.25,0,.25})for(double dz:new double[]{-.25,0,.25})
        {
            Vec3 from=p.position().add(dx,.1,dz);var hit=level.clip(new ClipContext(from,from.add(0,-.75,0),ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,p));require(hit.getType()==HitResult.Type.BLOCK&&hit.getDirection()==net.minecraft.core.Direction.UP&&p.getY()-hit.getLocation().y<=.65,"Actual stair/flat footprint lost support");var r=new JsonObject();r.addProperty("ray",from.toString());r.addProperty("hit",hit.getLocation().toString());r.addProperty("state",BlockStateParser.serialize(level.getBlockState(hit.getBlockPos())));rays.add(r);
        }
        var proof=new JsonObject();proof.addProperty("actual_feet",p.position().toString());proof.add("nine_native_bearing_rays",rays);row.getAsJsonArray("trace").add(proof);
    }
    private static JsonObject pose(ServerPlayer p)
    {
        var r=new JsonObject();r.addProperty("actual_server_position",p.position().toString());r.addProperty("actual_client_position",String.valueOf(clientPosition));r.addProperty("actual_server_body",p.getBoundingBox().toString());r.addProperty("actual_client_body",String.valueOf(clientBody));r.addProperty("server_onGround",p.onGround());r.addProperty("client_onGround",clientGround);r.addProperty("actual_client_key_up",clientUp);r.addProperty("actual_client_forward_impulse",clientImpulse);r.addProperty("client_velocity",String.valueOf(clientVelocity));r.addProperty("client_stopped",clientStopped);r.addProperty("client_sample",clientSerial);r.addProperty("health",p.getHealth());return r;
    }
    private static void restore(ServerPlayer p)
    {
        phase="STOP_RESTORE";useTarget=null;target=null;restoring=true;restoreTicks=restoreStable=stopTicks=0;beforeStop=null;lastStopSample=-1;
    }
    private static void restoreAck(ServerPlayer p)
    {
        if(phase.equals("STOP_RESTORE"))
        {
            require(++restoreTicks<600,"Actual client input did not stop before original restoration");
            boolean stable=beforeStop!=null&&p.position().subtract(beforeStop).horizontalDistanceSqr()<.000001;
            boolean fresh=clientSerial>lastStopSample;
            boolean ack=clientStopped&&actorId.equals(clientId)&&clientPosition!=null&&clientDimension!=null
                    &&clientDimension.equals(p.serverLevel().dimension())&&clientPosition.distanceToSqr(p.position())<.0004&&stable&&fresh;
            restoreDiagnostic=pose(p);restoreDiagnostic.addProperty("phase","STOP_RESTORE");restoreDiagnostic.addProperty("server_horizontal_stable",stable);restoreDiagnostic.addProperty("fresh_client_sample",fresh);
            if(!fresh){if(!stable)stopTicks=0;return;}beforeStop=p.position();lastStopSample=clientSerial;
            if(!ack){stopTicks=0;return;}if(++stopTicks<3)return;
            phase="RESTORE";restoreTicks=restoreStable=0;p.setGameMode(originalMode);p.load(original.copy());p.noPhysics=originalNoPhysics;p.zza=p.xxa=0;
            p.teleportTo(p.server.getLevel(originalDimension),originalPosition.x,originalPosition.y,originalPosition.z,originalYaw,originalPitch);
            p.onUpdateAbilities();p.inventoryMenu.sendAllDataToRemote();p.containerMenu.broadcastChanges();
            p.connection.send(new net.minecraft.network.protocol.game.ClientboundSetExperiencePacket(p.experienceProgress,p.totalExperience,p.experienceLevel));return;
        }
        ++restoreTicks;var mc=Minecraft.getInstance();var after=p.saveWithoutId(new CompoundTag());restoreDiagnostic=pose(p);restoreDiagnostic.addProperty("restore_ticks",restoreTicks);restoreDiagnostic.addProperty("original_position",originalPosition.toString());restoreDiagnostic.addProperty("inventory_typed_equal",Objects.equals(after.get("Inventory"),original.get("Inventory")));restoreDiagnostic.addProperty("original_health",original.getFloat("Health"));restoreDiagnostic.addProperty("server_slot",p.getInventory().selected);restoreDiagnostic.addProperty("original_slot",original.getInt("SelectedItemSlot"));
        restoreDiagnostic.addProperty("original_mode",originalMode.toString());restoreDiagnostic.addProperty("server_mode",p.gameMode.getGameModeForPlayer().toString());restoreDiagnostic.addProperty("original_dimension",originalDimension.location().toString());restoreDiagnostic.addProperty("server_dimension",p.serverLevel().dimension().location().toString());restoreDiagnostic.addProperty("server_UUID_equal",p.getUUID().equals(actorId));restoreDiagnostic.addProperty("server_XP",p.totalExperience+"/"+p.experienceLevel+"/"+p.experienceProgress);restoreDiagnostic.addProperty("original_XP",original.getInt("XpTotal")+"/"+original.getInt("XpLevel")+"/"+original.getFloat("XpP"));
        if(mc.player!=null&&mc.level!=null){restoreDiagnostic.addProperty("client_mode",mc.gameMode.getPlayerMode().toString());restoreDiagnostic.addProperty("client_dimension",mc.level.dimension().location().toString());restoreDiagnostic.addProperty("client_health",mc.player.getHealth());restoreDiagnostic.addProperty("client_slot",mc.player.getInventory().selected);restoreDiagnostic.addProperty("client_XP",mc.player.totalExperience+"/"+mc.player.experienceLevel+"/"+mc.player.experienceProgress);}
        boolean ack=clientPosition!=null&&p.position().distanceToSqr(originalPosition)<.04&&clientPosition.distanceToSqr(originalPosition)<.10&&mc.player!=null&&mc.level!=null&&p.getUUID().equals(actorId)&&p.serverLevel().dimension().equals(originalDimension)&&mc.level.dimension().equals(originalDimension)&&Objects.equals(after.get("Inventory"),original.get("Inventory"))&&p.getInventory().selected==original.getInt("SelectedItemSlot")&&mc.player.getInventory().selected==original.getInt("SelectedItemSlot")&&p.gameMode.getGameModeForPlayer()==originalMode&&mc.gameMode.getPlayerMode()==originalMode&&Math.abs(p.getHealth()-original.getFloat("Health"))<.001&&Math.abs(mc.player.getHealth()-original.getFloat("Health"))<.001&&p.experienceLevel==original.getInt("XpLevel")&&mc.player.experienceLevel==original.getInt("XpLevel")&&p.totalExperience==original.getInt("XpTotal")&&mc.player.totalExperience==original.getInt("XpTotal")&&Math.abs(p.experienceProgress-original.getFloat("XpP"))<.001&&Math.abs(mc.player.experienceProgress-original.getFloat("XpP"))<.001;
        restoreDiagnostic.addProperty("original_server_step",originalServerStep);restoreDiagnostic.addProperty("actual_server_step",p.maxUpStep());restoreDiagnostic.addProperty("original_client_step",originalClientStep);
        if(mc.player!=null)restoreDiagnostic.addProperty("actual_client_step",mc.player.maxUpStep());
        ack&=Math.abs(p.maxUpStep()-originalServerStep)<.001F&&mc.player!=null&&Math.abs(mc.player.maxUpStep()-originalClientStep)<.001F;
        require(restoreTicks<600,"Strict original actor restoration never acknowledged: "+restoreDiagnostic);if(!ack){restoreStable=0;return;}if(++restoreStable<8)return;restored=true;restoring=false;for(var at:leases)level.getChunkSource().removeRegionTicket(TICKET,at,2,at);leases.clear();write();finished=true;
    }
    private static void lease(ChunkPos at){if(leases.add(at)){level.getChunkSource().addRegionTicket(TICKET,at,2,at);level.getChunk(at.x,at.z);}}
    private static void write()
    {
        if(output==null)return;
        try{var r=new JsonObject();r.addProperty("schema","projectseele.command17-actual-native-receipt.v1");r.addProperty("error",error);r.addProperty("required_cases",shortArt?1:141);r.addProperty("complete_dataset_cases_kept",141);r.addProperty("short_art_preview_v13",shortArt);r.add("actual_art_images",artPhotos);r.add("first_contact_actual_gameTick_frames",firstContactFrames);r.addProperty("first_contact_diagnostic",firstContact);r.addProperty("first_contact_scope_start_actual_gameTime",firstContactScopeStart);r.addProperty("first_contact_scope_limit_actual_gameTicks",firstContact?160:0);r.addProperty("cabin_inspection_teleport_only_no_lift_trip",shortArt&&!firstContact);r.addProperty("requested_short_functional_pass",shortArt&&error.isEmpty()&&restored&&results.size()==1);r.addProperty("requested_three_images_captured",shortArt&&!firstContact&&error.isEmpty()&&restored&&artPhotos.size()==3);r.addProperty("visual_or_user_approved",false);r.addProperty("completed_cases",results.size());r.addProperty("actual_actor_restored",restored);r.addProperty("requested_CMD17_functional_pass",!shortArt&&error.isEmpty()&&restored&&results.size()==141);r.addProperty("full_lifecycle_pass",false);r.addProperty("relog_pass",false);r.addProperty("all684_objects_pass",false);r.addProperty("old165_BE17_executed_this_run",0);r.addProperty("auto18_independent_occupied_expiry_UNVERIFIED",true);r.add("cases",results);r.addProperty("original_snapshot_captured",original!=null);r.addProperty("restoration_action_started",original!=null);if(startupDiagnostic!=null)r.add("initial_actual_ready_diagnostic",startupDiagnostic);if(firstFailure!=null)r.add("first_failure",firstFailure);if(restoreDiagnostic!=null)r.add("restore_ACK_diagnostic",restoreDiagnostic);Files.writeString(output,GSON.toJson(r),StandardOpenOption.CREATE_NEW);}catch(Exception failure){throw new IllegalStateException("COMMAND17 receipt lost",failure);}
    }
    private static JsonObject read(Path p)throws Exception{return JsonParser.parseString(Files.readString(p)).getAsJsonObject();}
    private static JsonObject readRef(JsonObject r)throws Exception{Path p=Path.of(r.get("path").getAsString());require(hash(p).equals(r.get("sha256").getAsString()),"Frozen complete input bytes changed");return read(p);}
    private static String hash(Path p)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(p)));}
    private static Vec3 vec(JsonArray a){require(a!=null&&a.size()==3,"Exact floating Vec3 required");return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static BlockPos pos(JsonArray a){Vec3 p=vec(a);require(p.x==Math.rint(p.x)&&p.y==Math.rint(p.y)&&p.z==Math.rint(p.z),"Exact block coordinate required");return BlockPos.containing(p);}
    private static void require(boolean pass,String reason){if(!pass)throw new IllegalStateException(reason);}
}

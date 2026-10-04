package com.projectseele.client.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.visual.LiftPassengerR20Review;
import com.projectseele.world.*;
import com.projectseele.item.NervAccessCardR44;
import net.minecraft.client.Minecraft;
import net.minecraft.core.*;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.*;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.*;
import net.minecraft.world.*;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.*;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.*;
import net.minecraft.world.phys.shapes.*;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Native reader input, complete apertures and immutable Tree images in a leased QA copy. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class NervSecurityLifecycleR45
{
    private static final boolean ENABLED=Boolean.getBoolean("projectseele.r45NervSecurityReview");
    private static JsonObject job,current,row;
    private static JsonArray cases;
    private static final JsonArray results=new JsonArray();
    private static Path output;
    private static UUID actorId;
    private static CompoundTag originalPlayer;
    private static ResourceKey<Level> originalDimension;
    private static net.minecraft.world.level.GameType originalMode;
    private static Vec3 originalPosition;
    private static float originalYaw,originalPitch;
    private static boolean originalNoPhysics;
    private static int index,step,age,ticks,stagingTicks,restoreTicks,restoreStable;
    private static volatile JsonObject action,clientUse;
    private static volatile String error="";
    private static volatile boolean ready,finished;
    private static boolean restoring,restored,optionsSaved,oldPause,stopping,used,swapped;
    private static int oldDistance;
    private static long actualServerUseTick=-1;
    private static long lastReaderInputTick=-1;
    private static JsonObject actualServerUse;
    private static float entryHealth;
    private NervSecurityLifecycleR45() {}

    @SubscribeEvent
    public static void client(TickEvent.ClientTickEvent event)
    {
        if(!ENABLED||event.phase!=TickEvent.Phase.END)return;
        var mc=Minecraft.getInstance();
        if(!optionsSaved)
        {
            optionsSaved=true;oldPause=mc.options.pauseOnLostFocus;oldDistance=mc.options.renderDistance().get();
            mc.options.pauseOnLostFocus=false;mc.options.renderDistance().set(8);mc.options.broadcastOptions();
        }
        keys(mc,false);
        if(finished)
        {
            mc.options.pauseOnLostFocus=oldPause;mc.options.renderDistance().set(oldDistance);mc.options.broadcastOptions();
            if(!stopping){stopping=true;mc.stop();}return;
        }
        if(mc.screen instanceof net.minecraft.client.gui.screens.PauseScreen)mc.setScreen(null);
        if(!ready||action==null||mc.player==null||mc.level==null||mc.screen!=null)return;
        try
        {
            String kind=action.get("kind").getAsString();
            if(kind.equals("use")&&!used)
            {
                BlockPos target=pos(action.getAsJsonArray("block"));var state=mc.level.getBlockState(target);
                String id=BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString();
                require(id.equals("projectseele:nerv_access_reader")||id.equals("projectseele:dead_sea_archive")||state.getBlock() instanceof ButtonBlock,
                        "Assigned input is not a reader, archive or actual release button");
                Vec3 eye=mc.player.getEyePosition();BlockHitResult chosen=null;double nearest=Double.POSITIVE_INFINITY;
                for(var bounds:state.getShape(mc.level,target).toAabbs())
                {
                    Vec3 point=bounds.getCenter().add(target.getX(),target.getY(),target.getZ());double range=point.distanceTo(eye);
                    if(range>mc.gameMode.getPickRange()||range>=nearest)continue;
                    Vec3 direction=point.subtract(eye);
                    var hit=mc.level.clip(new ClipContext(eye,point.add(direction.normalize().scale(.01)),ClipContext.Block.OUTLINE,ClipContext.Fluid.NONE,mc.player));
                    if(hit.getType()==HitResult.Type.BLOCK&&hit.getBlockPos().equals(target)){chosen=hit;nearest=range;}
                }
                require(chosen!=null,"No actual reachable native outline on assigned security input: "+target);
                var aim=chosen.getLocation().subtract(eye);
                mc.player.setYRot((float)Math.toDegrees(Math.atan2(-aim.x,aim.z)));
                mc.player.setXRot((float)-Math.toDegrees(Math.atan2(aim.y,aim.horizontalDistance())));
                InteractionHand hand=hand(action);
                int held=mc.player.getItemInHand(hand).getItem() instanceof NervAccessCardR44 card?card.clearance():0;
                if(held!=action.get("presented_tier").getAsInt())return;
                var proof=new JsonObject();proof.addProperty("target",target.toShortString());proof.addProperty("actual_eye",eye.toString());
                proof.addProperty("hit",chosen.getLocation().toString());proof.addProperty("face",chosen.getDirection().getName());
                proof.addProperty("client_tick",mc.level.getGameTime());proof.addProperty("hand",hand.name());proof.addProperty("held_tier",held);
                proof.addProperty("result",mc.gameMode.useItemOn(mc.player,hand,chosen).name());clientUse=proof;used=true;
            }
            else if(kind.equals("walk"))
            {
                Vec3 delta=vec(action.getAsJsonArray("target")).subtract(mc.player.position());
                mc.player.setYRot((float)Math.toDegrees(Math.atan2(-delta.x,delta.z)));mc.player.setXRot(0);
                keys(mc,delta.horizontalDistanceSqr()>.025);
            }
        }
        catch(Exception failure){error=failure.toString();}
    }

    @SubscribeEvent(priority=net.minecraftforge.eventbus.api.EventPriority.LOWEST,receiveCanceled=true)
    public static void input(PlayerInteractEvent.RightClickBlock event)
    {
        if(!ENABLED||!ready||action==null||!action.get("kind").getAsString().equals("use")
                ||!(event.getEntity() instanceof ServerPlayer player)||!player.getUUID().equals(actorId)
                ||!event.getPos().equals(pos(action.getAsJsonArray("block"))))return;
        actualServerUseTick=player.serverLevel().getGameTime();actualServerUse=new JsonObject();
        actualServerUse.addProperty("tick",actualServerUseTick);actualServerUse.addProperty("actor_UUID",actorId.toString());
        actualServerUse.addProperty("target",event.getPos().toShortString());actualServerUse.addProperty("hand",event.getHand().name());
        actualServerUse.addProperty("hit",event.getHitVec().getLocation().toString());actualServerUse.addProperty("canceled",event.isCanceled());
        actualServerUse.addProperty("cancellation_result",event.getCancellationResult().name());
        if(player.serverLevel().getBlockEntity(event.getPos()) instanceof NervAccessReaderEntityR44 reader)
        {
            lastReaderInputTick=actualServerUseTick;
            actualServerUse.addProperty("reader_full_NBT_at_input",reader.saveWithFullMetadata().toString());
        }
    }

    @SubscribeEvent
    public static void server(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||finished||event.phase!=TickEvent.Phase.END)return;
        var server=event.getServer();var mc=Minecraft.getInstance();
        if(mc.player==null||mc.getSingleplayerServer()!=server)return;
        var player=server.getPlayerList().getPlayer(mc.player.getUUID());if(player==null)return;
        try
        {
            ServerLevel level=server.getLevel(FacilitySchemaV2.DIMENSION);require(level!=null,"GeoFront level absent");
            if(job==null)
            {
                require(!LiftPassengerR20Review.ENABLED&&!Boolean.getBoolean("projectseele.r44AccessReview"),"Run a single native device controller per process");
                String file=System.getProperty("projectseele.r45NervSecurityCases","");require(!file.isBlank(),"Explicit bound security job required");
                job=JsonParser.parseString(Files.readString(Path.of(file))).getAsJsonObject();
                require("projectseele.nerv-security-native-cases-r45.v1".equals(job.get("schema").getAsString())&&job.get("bound").getAsBoolean(),"Unbound security job");
                require(FacilitySourceAdmissionR45.admit(level,job),"Security candidate lease refused");
                cases=job.getAsJsonArray("cases");
                require(cases.size()==5&&cases.size()==job.get("cases_required").getAsInt()
                        &&job.get("reader_objects_required").getAsInt()==5&&job.get("total_security_objects").getAsInt()==684
                        &&job.getAsJsonArray("uncovered_objects").size()==679,"Security object denominator changed");
                Set<BlockPos> actualReaders=new HashSet<>();
                for(var raw:cases)require(actualReaders.add(pos(raw.getAsJsonObject().getAsJsonArray("reader"))),"Duplicate reader lifecycle case");
                require(actualReaders.equals(Set.of(new BlockPos(-354,82,732),new BlockPos(119,76,270),new BlockPos(228,82,303),
                        new BlockPos(36,-328,339),new BlockPos(35,-328,341))),"Current actual fixed reader coverage differs");
                output=Path.of(System.getProperty("projectseele.r45NervSecurityOutput","")).toAbsolutePath().normalize();
                Path world=server.getWorldPath(LevelResource.ROOT).toRealPath();
                require(!System.getProperty("projectseele.r45NervSecurityOutput","").isBlank()&&!output.startsWith(world)&&!Files.exists(output),"Use a new artifact receipt outside the world");
                Files.createDirectories(output.getParent());
                require(player.getVehicle()==null&&player.onGround(),"Begin with the actual player grounded outside a vehicle");
                actorId=player.getUUID();originalDimension=player.level().dimension();originalMode=player.gameMode.getGameModeForPlayer();
                originalPosition=player.position();originalYaw=player.getYRot();originalPitch=player.getXRot();originalNoPhysics=player.noPhysics;
                originalPlayer=player.saveWithoutId(new CompoundTag()).copy();
                Files.writeString(output.resolveSibling(output.getFileName()+".player_before.snbt"),originalPlayer.toString(),StandardOpenOption.CREATE_NEW);
                begin(level,player);return;
            }
            require(++age<150000,"Whole security queue deadline");
            require(player.getUUID().equals(actorId),"Actual review actor identity changed");
            if(restoring){restoreAcknowledgment(player,mc);return;}
            require(error.isBlank(),error);require(player.isAlive()&&player.getHealth()>=entryHealth-.01,"Security review passenger took damage");
            if(!ready)
            {
                Vec3 staging=vec(current.getAsJsonArray("staging"));
                require(++stagingTicks<800,"Security outside staging never acknowledged");
                if(stagingTicks<60||mc.level==null||!mc.level.dimension().equals(level.dimension())
                        ||mc.player.position().distanceToSqr(staging)>.05||!player.onGround()||!mc.player.onGround())return;
                require(level.noCollision(player,player.getBoundingBox().deflate(.01)),"Security staging intersects actual collision");
                player.setGameMode(net.minecraft.world.level.GameType.SURVIVAL);player.getAbilities().flying=false;player.onUpdateAbilities();
                ready=true;next(player);return;
            }
            require(++ticks<1200,"Actual security action timed out: "+current.get("id")+" step="+step+" actor="+player.position());
            String kind=action.get("kind").getAsString();boolean complete=false;
            if(kind.equals("equip")){if(ticks==1)equip(player,action.get("tier").getAsInt(),hand(action));complete=ticks>=5;}
            else if(kind.equals("use"))
            {
                if(actualServerUseTick<0)return;
                if(action.has("swap_after_ticks")&&!swapped&&level.getGameTime()-actualServerUseTick>=action.get("swap_after_ticks").getAsInt())
                {
                    require(level.getGameTime()-actualServerUseTick<6,"Credential cancellation missed the real authorization tick");
                    equip(player,0,hand(action));swapped=true;
                }
                complete=clientUse!=null&&level.getGameTime()-actualServerUseTick>=action.get("settle_ticks").getAsInt();
            }
            else if(kind.equals("walk"))
            {
                Vec3 target=vec(action.getAsJsonArray("target"));
                require(player.getY()>=target.y-.65,"Security threshold lost actual floor support");
                complete=player.position().subtract(target).horizontalDistanceSqr()<.06&&mc.player.position().subtract(target).horizontalDistanceSqr()<.10
                        &&Math.abs(player.getY()-target.y)<.15&&player.onGround()&&mc.player.onGround();
                if(complete)bearing(level,player);
            }
            else if(kind.equals("hold"))
            {
                if(action.has("expect_clear"))require(aperture(level,player,current).get("complete_clear").getAsBoolean()==action.get("expect_clear").getAsBoolean(),"Safety hold aperture changed while occupied");
                complete=ticks>=action.get("ticks").getAsInt();
            }
            else if(kind.equals("assert_reader"))
            {
                var reader=reader(level,action);require(reader.isOpen()==action.get("expect_open").getAsBoolean(),"Reader lease differs from actual expected state");
                require(reader.indicator()==action.get("status").getAsInt(),"Reader did not make the required actual authorization decision");
                if(action.has("expected_open_ticks"))
                {
                    long until=reader.saveWithoutMetadata().getLong("OpenUntil");
                    require(lastReaderInputTick>=0&&until==lastReaderInputTick+6+action.get("expected_open_ticks").getAsInt(),"Actual authorization lease differs from the original real input and six-tick decision");
                    var proof=new JsonObject();proof.addProperty("kind","exact_native_authorization_deadline");proof.addProperty("actual_input_tick",lastReaderInputTick);
                    proof.addProperty("actual_open_until",until);proof.addProperty("authorized_ticks",action.get("expected_open_ticks").getAsInt());row.getAsJsonArray("observations").add(proof);
                }
                complete=true;
            }
            else if(kind.equals("assert_aperture"))
            {
                var proof=aperture(level,player,current);row.getAsJsonArray("observations").add(proof);
                boolean expected=action.get("expect_clear").getAsBoolean();
                require(proof.get("complete_clear").getAsBoolean()==expected,"Complete authored aperture collision differs");
                if(!expected)require(proof.get("complete_closed").getAsBoolean(),"Only part of the closed aperture blocks passage");complete=true;
            }
            else if(kind.equals("assert_chamber_images")){images(level,action.get("opened").getAsBoolean());complete=true;}
            else if(kind.equals("assert_archive")){archive(level,player,action);complete=true;}
            else throw new IllegalStateException("Unknown security action "+kind);
            if(!complete)return;
            var witness=new JsonObject();witness.addProperty("ordinal",step);witness.add("action",action.deepCopy());
            witness.addProperty("server_tick",level.getGameTime());witness.addProperty("actual_server_position",player.position().toString());
            witness.addProperty("actual_client_position",mc.player.position().toString());witness.addProperty("on_ground",player.onGround());
            if(clientUse!=null)witness.add("actual_client_input",clientUse.deepCopy());if(actualServerUse!=null)witness.add("actual_server_input",actualServerUse.deepCopy());
            row.getAsJsonArray("actions").add(witness);
            if(++step<current.getAsJsonArray("steps").size()){next(player);return;}
            row.addProperty("requested_actions_passed",true);results.add(row);
            if(++index<cases.size()){begin(level,player);return;}
            restore(player);
        }
        catch(Exception failure)
        {
            error=failure.toString();ProjectSeele.LOGGER.error("R45 native NERV security lifecycle failed",failure);
            try{if(restoring||originalPlayer==null){write();finished=true;}else restore(player);}
            catch(Exception restoreFailure){error+=" RESTORATION_ERROR:"+restoreFailure;write();finished=true;}
        }
    }

    private static void begin(ServerLevel level,ServerPlayer player) throws Exception
    {
        ready=false;action=null;step=stagingTicks=0;current=cases.get(index).getAsJsonObject();
        row=new JsonObject();row.addProperty("id",current.get("id").getAsString());row.addProperty("actual_actor_UUID",actorId.toString());
        row.add("actions",new JsonArray());row.add("observations",new JsonArray());
        CompoundTag expected=TagParser.parseTag(current.get("reader_full_nbt").getAsString());
        BlockPos at=pos(current.getAsJsonArray("reader"));level.getChunkAt(at);
        var entity=level.getBlockEntity(at);require(entity instanceof NervAccessReaderEntityR44,"Actual fixed security reader absent");
        CompoundTag actual=entity.saveWithFullMetadata();
        for(String field:List.of("Gate","Exit","Width","Height","Clearance","Style","DoorId","AlongX","Linked","ChamberId","ChamberRole"))
            require(Objects.equals(expected.get(field),actual.get(field)),"Reader fixed ownership field changed: "+field);
        require(BlockPos.of(actual.getLong("Gate")).equals(pos(current.getAsJsonArray("gate")))
                &&actual.getInt("Width")==current.get("width").getAsInt()&&actual.getInt("Height")==current.get("height").getAsInt()
                &&actual.getBoolean("AlongX")==current.get("along_x").getAsBoolean()
                &&actual.getInt("DoorId")==current.get("door_id").getAsInt(),"Test aperture is not the real fixed reader's authored aperture");
        row.addProperty("actual_reader_before_full_NBT",actual.toString());
        equip(player,0,InteractionHand.MAIN_HAND);entryHealth=player.getHealth();
        Vec3 staging=vec(current.getAsJsonArray("staging"));player.teleportTo(level,staging.x,staging.y,staging.z,0,0);
        player.setDeltaMovement(Vec3.ZERO);player.fallDistance=0;
    }

    private static void next(ServerPlayer player)
    {action=current.getAsJsonArray("steps").get(step).getAsJsonObject();ticks=0;used=swapped=false;clientUse=null;actualServerUse=null;actualServerUseTick=-1;}

    private static void equip(ServerPlayer player,int tier,InteractionHand hand)
    {
        ItemStack card=ItemStack.EMPTY;
        if(tier>0)
        {
            String id=switch(tier){case 1->"projectseele:nerv_employee_card";case 3->"projectseele:terminal_dogma_access_card";default->throw new IllegalStateException("No actual installed card at requested tier "+tier);};
            var item=BuiltInRegistries.ITEM.get(new net.minecraft.resources.ResourceLocation(id));
            require(item instanceof NervAccessCardR44&&((NervAccessCardR44)item).clearance()==tier,"Installed original card id/tier differs: "+id);card=new ItemStack(item);
        }
        player.setItemInHand(InteractionHand.MAIN_HAND,ItemStack.EMPTY);player.setItemInHand(InteractionHand.OFF_HAND,ItemStack.EMPTY);
        player.setItemInHand(hand,card);player.inventoryMenu.broadcastChanges();player.containerMenu.broadcastChanges();
    }

    private static NervAccessReaderEntityR44 reader(ServerLevel level,JsonObject input)
    {
        var entity=level.getBlockEntity(pos(input.getAsJsonArray("block")));require(entity instanceof NervAccessReaderEntityR44,"Expected real reader absent");return (NervAccessReaderEntityR44)entity;
    }

    private static JsonObject aperture(ServerLevel level,ServerPlayer player,JsonObject scope)
    {
        BlockPos gate=pos(scope.getAsJsonArray("gate"));int width=scope.get("width").getAsInt(),height=scope.get("height").getAsInt();boolean alongX=scope.get("along_x").getAsBoolean();
        require(width>=1&&width<=7&&height>=2&&height<=9,"Aperture dimensions outside real reader protocol");
        JsonObject proof=new JsonObject();proof.addProperty("kind","complete_native_authored_aperture");JsonArray cells=new JsonArray();
        boolean clear=true,closed=true;
        for(int lateral=0;lateral<width;lateral++)for(int y=0;y<height;y++)
        {
            BlockPos at=gate.offset(alongX?lateral:0,y,alongX?0:lateral);AABB box=new AABB(at).deflate(.01);
            var state=level.getBlockState(at);var shape=state.getCollisionShape(level,at,CollisionContext.of(player)).move(at.getX(),at.getY(),at.getZ());
            boolean blocked=Shapes.joinIsNotEmpty(shape,Shapes.create(box),BooleanOp.AND);clear&=!blocked;closed&=blocked;
            JsonObject cell=new JsonObject();cell.addProperty("pos",at.toShortString());cell.addProperty("state",state.toString());cell.addProperty("actual_collision",shape.toAabbs().toString());cell.addProperty("blocked",blocked);cells.add(cell);
        }
        proof.add("all_cells",cells);proof.addProperty("complete_clear",clear);proof.addProperty("complete_closed",closed);
        var bounds=new AABB(gate.getX(),gate.getY(),gate.getZ(),gate.getX()+(alongX?width:1),gate.getY()+height,gate.getZ()+(alongX?1:width));
        var doors=new JsonArray();
        for(var door:level.getEntitiesOfClass(com.projectseele.entity.NervLiftDoorEntity.class,bounds.inflate(4)))
        {
            var leaf=new JsonObject();leaf.addProperty("door_id",door.getDoorId());leaf.addProperty("entity_UUID",door.getUUID().toString());
            leaf.addProperty("position",door.position().toString());leaf.addProperty("width",door.getDoorWidth());leaf.addProperty("height",door.getDoorHeight());
            leaf.addProperty("open_progress",door.getOpenProgress(1));leaf.addProperty("axis_x",door.isAxisX());doors.add(leaf);
            if(scope.has("door_id")&&scope.get("door_id").getAsInt()==door.getDoorId())
                require(clear?door.getOpenProgress(1)>=.99F:!closed||door.getOpenProgress(1)<=.01F,"Actual assigned door leaves have not completed motion");
        }
        proof.add("actual_nearby_leaf_states",doors);
        proof.addProperty("reader_lease_and_occupied_physical_clear_are_distinct",true);return proof;
    }

    private static void bearing(ServerLevel level,ServerPlayer player)
    {
        var proof=new JsonObject();proof.addProperty("kind","actual_threshold_complete_footprint_bearing");var rays=new JsonArray();
        for(double dx:new double[]{-.25,0,.25})for(double dz:new double[]{-.25,0,.25})
        {
            Vec3 start=player.position().add(dx,.10,dz);var hit=level.clip(new ClipContext(start,start.add(0,-.75,0),ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,player));
            require(hit.getType()==HitResult.Type.BLOCK&&hit.getDirection()==Direction.UP&&Math.abs(hit.getLocation().y-player.getY())<.03,"Threshold has incomplete actual foot support");
            var ray=new JsonObject();ray.addProperty("start",start.toString());ray.addProperty("hit",hit.getLocation().toString());ray.addProperty("state",level.getBlockState(hit.getBlockPos()).toString());rays.add(ray);
        }
        proof.add("nine_collision_rays",rays);proof.addProperty("on_ground",player.onGround());
        require(level.noCollision(player,player.getBoundingBox().deflate(.01)),"Actual threshold body intersects native collision");row.getAsJsonArray("observations").add(proof);
    }

    private static void images(ServerLevel level,boolean opened) throws Exception
    {
        var proof=new JsonObject();proof.addProperty("kind","complete_original_chamber_images");proof.addProperty("opened",opened);var all=new JsonArray();
        for(var raw:job.getAsJsonArray("chamber_images"))
        {
            JsonObject image=raw.getAsJsonObject();BlockPos at=pos(image.getAsJsonArray("pos"));var entity=level.getBlockEntity(at);
            if(opened)require(level.getBlockState(at).isAir()&&entity==null,"Opened chamber retained a original-image obstruction");
            else
            {
                var expected=TagParser.parseTag(image.get("state_nbt").getAsString());
                require(NbtUtils.writeBlockState(level.getBlockState(at)).equals(expected),"Complete chamber original block state changed");
                if(image.has("full_nbt")&&!image.get("full_nbt").isJsonNull())
                {
                    require(entity!=null,"Original artwork BE was not restored");CompoundTag before=TagParser.parseTag(image.get("full_nbt").getAsString()),after=entity.saveWithFullMetadata();
                    if(!after.contains("keepPacked")&&before.contains("keepPacked",Tag.TAG_BYTE)&&before.getByte("keepPacked")==0)after.putByte("keepPacked",(byte)0);
                    require(before.equals(after),"Complete original artwork NBT differs after real closure");
                }
                else require(entity==null,"Unexpected BE in original wall mask");
            }
            var cell=new JsonObject();cell.addProperty("pos",at.toShortString());cell.addProperty("state",level.getBlockState(at).toString());
            if(entity!=null)cell.addProperty("full_NBT",entity.saveWithFullMetadata().toString());all.add(cell);
        }
        require(all.size()==10,"All nine portal cells and full original Tree image are required");proof.add("images",all);row.getAsJsonArray("observations").add(proof);
    }

    private static void archive(ServerLevel level,ServerPlayer player,JsonObject input)
    {
        BlockPos at=pos(input.getAsJsonArray("block"));var state=level.getBlockState(at);
        require(level.getBlockEntity(at) instanceof DeadSeaArchiveEntityR45&&BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString().equals("projectseele:dead_sea_archive"),"Physical original archive BE missing");
        var collision=state.getCollisionShape(level,at,CollisionContext.of(player));var outline=state.getShape(level,at);
        require(!collision.isEmpty()&&!outline.isEmpty(),"Actual native archive has no physical collision/outline");
        var proof=new JsonObject();proof.addProperty("kind","archive_exact_native_collision");proof.addProperty("pos",at.toShortString());
        proof.addProperty("collision",collision.toAabbs().toString());proof.addProperty("outline",outline.toAabbs().toString());proof.addProperty("full_NBT",level.getBlockEntity(at).saveWithFullMetadata().toString());row.getAsJsonArray("observations").add(proof);
    }

    private static void restore(ServerPlayer player)
    {
        ready=false;action=null;restoring=true;restoreTicks=restoreStable=0;player.setGameMode(originalMode);player.load(originalPlayer.copy());player.noPhysics=originalNoPhysics;
        player.teleportTo(player.server.getLevel(originalDimension),originalPosition.x,originalPosition.y,originalPosition.z,originalYaw,originalPitch);
        player.onUpdateAbilities();player.inventoryMenu.sendAllDataToRemote();player.containerMenu.broadcastChanges();
        player.connection.send(new net.minecraft.network.protocol.game.ClientboundSetExperiencePacket(player.experienceProgress,player.totalExperience,player.experienceLevel));
    }

    private static void restoreAcknowledgment(ServerPlayer player,Minecraft mc)
    {
        require(++restoreTicks<600,"Full original player restoration not acknowledged");
        CompoundTag after=player.saveWithoutId(new CompoundTag());
        boolean aligned=player.getUUID().equals(actorId)&&player.serverLevel().dimension().equals(originalDimension)&&mc.level.dimension().equals(originalDimension)
                &&player.position().distanceToSqr(originalPosition)<.04&&mc.player.position().distanceToSqr(originalPosition)<.10
                &&Objects.equals(after.get("Inventory"),originalPlayer.get("Inventory"))&&player.getInventory().selected==originalPlayer.getInt("SelectedItemSlot")
                &&mc.player.getInventory().selected==originalPlayer.getInt("SelectedItemSlot")
                &&player.gameMode.getGameModeForPlayer()==originalMode&&mc.gameMode.getPlayerMode()==originalMode
                &&Math.abs(player.getHealth()-originalPlayer.getFloat("Health"))<.001&&Math.abs(mc.player.getHealth()-originalPlayer.getFloat("Health"))<.001
                &&player.experienceLevel==originalPlayer.getInt("XpLevel")&&mc.player.experienceLevel==originalPlayer.getInt("XpLevel")
                &&player.totalExperience==originalPlayer.getInt("XpTotal")&&mc.player.totalExperience==originalPlayer.getInt("XpTotal")
                &&Math.abs(player.experienceProgress-originalPlayer.getFloat("XpP"))<.001&&Math.abs(mc.player.experienceProgress-originalPlayer.getFloat("XpP"))<.001;
        if(!aligned){restoreStable=0;return;}
        if(++restoreStable<8)return;restored=true;restoring=false;write();finished=true;
    }

    private static void write()
    {
        if(output==null)return;
        try
        {
            var report=new JsonObject();report.addProperty("schema","projectseele.nerv-security-native-receipt-r45.v1");report.addProperty("error",error);
            report.addProperty("required_cases",cases==null?0:cases.size());report.addProperty("completed_cases",results.size());
            report.addProperty("requested_functional_cases_passed",error.isBlank()&&cases!=null&&results.size()==cases.size()&&restored);
            report.addProperty("all_684_objects_passed",false);report.addProperty("full_lifecycle_pass",false);
            report.addProperty("full_player_NBT_restored_and_position_acknowledged",restored);report.add("cases",results);
            if(row!=null)report.add("active_case_evidence",row.deepCopy());
            for(String pending:List.of("same_jvm_reload","cold_reload","save_interrupt","two_clients","no_card_inside_expired_rescue"))report.addProperty(pending,"UNVERIFIED");
            if(job!=null){report.addProperty("candidate_binding_sha256",job.get("candidate_binding_sha256").getAsString());report.add("uncovered_objects",job.get("uncovered_objects").deepCopy());}
            Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(report),StandardOpenOption.CREATE_NEW);
        }
        catch(Exception failure){throw new IllegalStateException("Security receipt could not be preserved",failure);}
    }
    private static void keys(Minecraft mc,boolean up)
    {mc.options.keyUp.setDown(up);mc.options.keyDown.setDown(false);mc.options.keyLeft.setDown(false);mc.options.keyRight.setDown(false);mc.options.keyJump.setDown(false);mc.options.keyShift.setDown(false);mc.options.keySprint.setDown(false);mc.options.keyUse.setDown(false);}
    private static InteractionHand hand(JsonObject row){return row.has("hand")&&row.get("hand").getAsString().equals("off")?InteractionHand.OFF_HAND:InteractionHand.MAIN_HAND;}
    private static Vec3 vec(JsonArray a){require(a!=null&&a.size()==3,"Explicit measured Vec3 required");return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static BlockPos pos(JsonArray a){Vec3 v=vec(a);require(v.x==Math.rint(v.x)&&v.y==Math.rint(v.y)&&v.z==Math.rint(v.z),"Exact integral block position required");return BlockPos.containing(v);}
    private static void require(boolean pass,String why){if(!pass)throw new IllegalStateException(why);}
}

package com.projectseele.client.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilitySchemaV2;
import net.minecraft.client.Minecraft;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Real client input for complete school rooms, stairs and swimming interfaces.
 * Only initial outside staging and final player restoration use teleportation. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class SchoolPoolLifecycleR45
{
    private static final boolean ENABLED = Boolean.getBoolean("projectseele.r45SchoolPoolReview");
    private record SavedBlock(BlockState state, CompoundTag nbt) { }
    private static final JsonArray results = new JsonArray(), trace = new JsonArray();
    private static final Map<BlockPos, SavedBlock> savedBlocks = new LinkedHashMap<>();
    private static JsonArray cases;
    private static JsonObject current, row;
    private static CompoundTag originalPlayer;
    private static ResourceKey<Level> originalDimension;
    private static GameType originalMode;
    private static UUID playerId;
    private static Vec3 originalPosition;
    private static float originalYaw, originalPitch;
    private static int index, end, step, age, stepTicks, stagingTicks, waterTicks, swimmingTicks, climbingTicks, blockedTicks, stationaryTicks;
    private static volatile boolean ready, finished;
    private static volatile JsonObject action;
    private static volatile String error = "";
    private static Path output;
    private static boolean optionsSaved, oldPause, stopping, restored, originalNoPhysics;
    private static boolean restoring;
    private static int restoreTicks, restoreStable;
    private static JsonObject restorationEvidence;
    private static int oldDistance;
    private static long lastUseTick = Long.MIN_VALUE;
    private static volatile JsonObject nativeUseEvidence;
    private static Vec3 stepStart;
    private static double movedInWater;

    @SubscribeEvent
    public static void client(TickEvent.ClientTickEvent event)
    {
        if (!ENABLED || event.phase != TickEvent.Phase.END) return;
        var mc = Minecraft.getInstance();
        if (!optionsSaved)
        {
            optionsSaved = true; oldPause = mc.options.pauseOnLostFocus; oldDistance = mc.options.renderDistance().get();
            mc.options.pauseOnLostFocus = false; mc.options.renderDistance().set(8); mc.options.broadcastOptions();
        }
        keys(mc, false, false, false);
        if (finished)
        {
            mc.options.pauseOnLostFocus = oldPause; mc.options.renderDistance().set(oldDistance); mc.options.broadcastOptions();
            if (!stopping) { stopping = true; mc.stop(); }
            return;
        }
        if (mc.screen instanceof net.minecraft.client.gui.screens.PauseScreen) mc.setScreen(null);
        if (mc.player == null || mc.level == null || mc.screen != null || !ready || action == null) return;
        try
        {
            String kind = action.get("kind").getAsString();
            if (kind.equals("use")) { use(mc, pos(action.get("block")), false); return; }
            if (kind.equals("observe")) return;
            Vec3 target = vec(action.getAsJsonArray("target")), delta = target.subtract(mc.player.position());
            mc.player.setYRot((float) Math.toDegrees(Math.atan2(-delta.x, delta.z)));
            boolean swim = kind.equals("swim"), climb = kind.equals("ladder"), exit = kind.equals("shallow_exit");
            mc.player.setXRot(swim ? (float) -Math.toDegrees(Math.atan2(delta.y, Math.max(.5, delta.horizontalDistance()))) : 0);
            keys(mc, delta.horizontalDistanceSqr() > .025 || climb, climb || exit, swim);
            if (current.has("auto_use_ordinary_doors") && current.get("auto_use_ordinary_doors").getAsBoolean())
            {
                var start = mc.player.getEyePosition(); var endPoint = start.add(delta.normalize().scale(Math.min(2.5, delta.length())));
                var hit = mc.level.clip(new net.minecraft.world.level.ClipContext(start, endPoint,
                    net.minecraft.world.level.ClipContext.Block.OUTLINE, net.minecraft.world.level.ClipContext.Fluid.NONE, mc.player));
                var state = mc.level.getBlockState(hit.getBlockPos());
                if (net.minecraft.core.registries.BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString().equals("projectseele:city_personnel_door")
                    && state.hasProperty(BlockStateProperties.OPEN) && !state.getValue(BlockStateProperties.OPEN)) use(mc, hit.getBlockPos(), true);
            }
        }
        catch (Exception failure) { error = failure.toString(); }
    }

    private static void keys(Minecraft mc, boolean up, boolean jump, boolean sprint)
    {
        mc.options.keyUp.setDown(up); mc.options.keyJump.setDown(jump); mc.options.keySprint.setDown(sprint);
        mc.options.keyDown.setDown(false); mc.options.keyLeft.setDown(false); mc.options.keyRight.setDown(false);
        mc.options.keyShift.setDown(false); mc.options.keyAttack.setDown(false); mc.options.keyUse.setDown(false);
    }

    private static void use(Minecraft mc, BlockPos target, boolean auto) throws Exception
    {
        if (lastUseTick != Long.MIN_VALUE && mc.level.getGameTime()-lastUseTick < 15) return;
        var state = mc.level.getBlockState(target);
        if (!auto && action.has("want_open") && state.hasProperty(BlockStateProperties.OPEN)
            && state.getValue(BlockStateProperties.OPEN) == action.get("want_open").getAsBoolean()) return;
        Vec3 start = mc.player.getEyePosition();
        net.minecraft.world.phys.BlockHitResult hit=null;double nearest=Double.POSITIVE_INFINITY;
        // An opened native door occupies its hinge-side outline, so a ray to
        // the empty centre cannot close it. Test actual outline-box centres.
        for(var box:state.getShape(mc.level,target).toAabbs())
        {
            Vec3 aimed=box.getCenter().add(target.getX(),target.getY(),target.getZ());
            double distance=start.distanceTo(aimed);if(distance>4.25||distance>=nearest)continue;
            var measured=mc.level.clip(new net.minecraft.world.level.ClipContext(start,aimed,
                net.minecraft.world.level.ClipContext.Block.OUTLINE,net.minecraft.world.level.ClipContext.Fluid.NONE,mc.player));
            if(measured.getType()!=net.minecraft.world.phys.HitResult.Type.BLOCK
                ||measured.getBlockPos().getX()!=target.getX()||measured.getBlockPos().getZ()!=target.getZ()
                ||Math.abs(measured.getBlockPos().getY()-target.getY())>1)continue;
            hit=measured;nearest=distance;
        }
        if(hit==null)throw new IllegalStateException("No actual reachable native outline on the assigned ordinary control: "+target);
        Vec3 aim=hit.getLocation().subtract(start);
        mc.player.setYRot((float)Math.toDegrees(Math.atan2(-aim.x,aim.z)));
        mc.player.setXRot((float)-Math.toDegrees(Math.atan2(aim.y,aim.horizontalDistance())));
        var evidence=new JsonObject();evidence.addProperty("target",target.toShortString());evidence.addProperty("client_game_time",mc.level.getGameTime());
        evidence.addProperty("actual_hit_block",hit.getBlockPos().toShortString());evidence.addProperty("actual_hit_face",hit.getDirection().getName());
        evidence.addProperty("actual_hit_location",hit.getLocation().toString());evidence.addProperty("actual_eye",start.toString());
        evidence.addProperty("actual_state",state.toString());evidence.addProperty("ordinary_native_outline_only",true);nativeUseEvidence=evidence;
        String id = net.minecraft.core.registries.BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString();
        if (!id.equals("projectseele:city_personnel_door") && !id.equals("minecraft:oak_fence_gate"))
            throw new IllegalStateException("This runner may use only ordinary school/personnel doors and pool gates: "+id);
        mc.gameMode.useItemOn(mc.player,InteractionHand.MAIN_HAND,hit); lastUseTick=mc.level.getGameTime();
    }

    @SubscribeEvent
    public static void server(TickEvent.ServerTickEvent event)
    {
        if (!ENABLED || event.phase != TickEvent.Phase.END || finished) return;
        var mc = Minecraft.getInstance(); var server = event.getServer();
        if (mc.player == null || mc.getSingleplayerServer() != server) return;
        var player = server.getPlayerList().getPlayer(mc.player.getUUID()); if (player == null) return;
        try
        {
            Path world = server.getWorldPath(LevelResource.ROOT).normalize();
            require(world.getFileName().toString().equals(com.projectseele.visual.NativeReviewWorldsR45.expectedName()),"Refuse another world");
            require(++age < 160000,"Whole school input queue deadline");
            var level = server.getLevel(FacilitySchemaV2.DIMENSION); require(level != null,"GeoFront level absent");
            if (cases == null)
            {
                String file = System.getProperty("projectseele.r45SchoolPoolCases",""); require(!file.isBlank(),"Explicit current case file required");
                cases = JsonParser.parseString(Files.readString(Path.of(file))).getAsJsonArray();
                index = Integer.getInteger("projectseele.r45SchoolPoolStart",0); end = Integer.getInteger("projectseele.r45SchoolPoolEnd",cases.size());
                require(index >= 0 && index < end && end <= cases.size(),"Invalid school case window");
                output = Path.of(System.getProperty("projectseele.r45SchoolPoolOutput",world.resolve("r45_school_pool_client_review.json").toString()));
                require(player.getVehicle() == null,"Start with actual player outside a vehicle; existing ride is not canceled by this runner");
                playerId = player.getUUID(); originalDimension=player.level().dimension(); originalMode=player.gameMode.getGameModeForPlayer();
                originalPosition=player.position(); originalYaw=player.getYRot(); originalPitch=player.getXRot();originalNoPhysics=player.noPhysics;
                originalPlayer=player.saveWithoutId(new CompoundTag()).copy();
                Files.writeString(output.resolveSibling("player_before_full_snbt.txt"),originalPlayer.toString());
                player.getInventory().setItem(player.getInventory().selected,ItemStack.EMPTY); player.inventoryMenu.broadcastChanges();
                begin(level,player); return;
            }
            require(player.getUUID().equals(playerId),"Review player identity changed");
            if(restoring){acknowledgeRestoration(player,mc);return;}
            require(error.isBlank(),error);
            require(player.isAlive(),"Actual player died during school operation");
            if (!ready)
            {
                Vec3 staging=vec(current.getAsJsonArray("staging"));
                BlockPos at=BlockPos.containing(staging);
                if (++stagingTicks < 80 || !mc.level.dimension().equals(level.dimension())
                    || !mc.level.getChunkSource().hasChunk(at.getX()>>4,at.getZ()>>4)
                    || mc.player.position().distanceToSqr(staging) > .05) { require(stagingTicks < 800,"Outside staging never loaded/acknowledged"); return; }
                if (player.gameMode.getGameModeForPlayer() != GameType.SURVIVAL)
                { player.setGameMode(GameType.SURVIVAL); player.getAbilities().flying=false; player.onUpdateAbilities(); return; }
                if (mc.gameMode.getPlayerMode() != GameType.SURVIVAL || !player.onGround() || !mc.player.onGround()) return;
                ready=true; nextStep(player); return;
            }
            require(++stepTicks < 1800,"Native action timed out: "+current.get("id")+" step="+step+" action="+action+" player="+player.position());
            if (stepTicks%5==0) sample(player,mc);
            if (player.isInWater()) { waterTicks++; movedInWater=Math.max(movedInWater,player.position().distanceTo(stepStart)); }
            if (player.isSwimming() && mc.player.isSwimming()) swimmingTicks++;
            if (player.onClimbable() || mc.player.onClimbable()) climbingTicks++;
            String kind=action.get("kind").getAsString(); boolean accepted=false;
            if (kind.equals("use") || kind.equals("observe") && action.has("expect_open"))
            {
                var q=pos(action.get("block")); var state=level.getBlockState(q); var clientState=mc.level.getBlockState(q);
                boolean want=action.get(kind.equals("use")?"want_open":"expect_open").getAsBoolean();
                accepted=state.hasProperty(BlockStateProperties.OPEN)&&clientState.hasProperty(BlockStateProperties.OPEN)
                    && state.getValue(BlockStateProperties.OPEN)==want && clientState.getValue(BlockStateProperties.OPEN)==want;
            }
            else if (kind.equals("observe"))
            { accepted=player.onGround()&&mc.player.onGround()&&!player.isInWater()&&!mc.player.isInWater(); }
            else if (kind.equals("blocked"))
            {
                var q=pos(action.get("block"));var state=level.getBlockState(q);
                require(state.hasProperty(BlockStateProperties.OPEN)&&!state.getValue(BlockStateProperties.OPEN),"Assigned pool gate did not start closed");
                if (player.horizontalCollision&&mc.player.horizontalCollision) blockedTicks++;
                Vec3 target=vec(action.getAsJsonArray("target"));require(player.position().subtract(target).horizontalDistanceSqr()>.25,"Closed pool gate was crossed");
                accepted=stepTicks>=action.get("ticks").getAsInt()&&blockedTicks>=8;
            }
            else
            {
                Vec3 target=vec(action.getAsJsonArray("target"));
                boolean near=player.position().subtract(target).horizontalDistanceSqr()<.065&&mc.player.position().subtract(target).horizontalDistanceSqr()<.10;
                if (kind.equals("swim"))
                {
                    accepted=near&&player.isInWater()&&mc.player.isInWater();
                    if (action.has("minimum_water_ticks")) accepted&=waterTicks>=action.get("minimum_water_ticks").getAsInt();
                    if (action.has("require_actual_swimming")) accepted&=swimmingTicks>=12;
                }
                else
                {
                    accepted=near&&Math.abs(player.getY()-target.y)<.25&&player.onGround()&&mc.player.onGround()&&!player.isInWater();
                    if (kind.equals("ladder")) accepted&=climbingTicks>0;
                }
            }
            if (!accepted) { stationaryTicks=0; return; }
            if (++stationaryTicks < 3) return;
            var witness=new JsonObject();witness.addProperty("ordinal",step);witness.add("action",action.deepCopy());
            witness.addProperty("actual_water_ticks",waterTicks);witness.addProperty("paired_actual_swimming_ticks",swimmingTicks);
            witness.addProperty("actual_climbable_ticks",climbingTicks);witness.addProperty("actual_blocked_collision_ticks",blockedTicks);
            witness.addProperty("actual_water_displacement",movedInWater);witness.addProperty("actual_server_position",player.position().toString());
            witness.addProperty("actual_client_position",mc.player.position().toString());if(nativeUseEvidence!=null)witness.add("last_actual_native_use_ray",nativeUseEvidence.deepCopy());row.getAsJsonArray("actions").add(witness);
            if (++step < current.getAsJsonArray("steps").size()) { nextStep(player); return; }
            restoreBlocks(level); row.addProperty("all_requested_native_actions_completed",true);results.add(row);persist(false);
            if (++index < end) { begin(level,player); return; }
            restorePlayer(player);persist(false);
        }
        catch (Exception failure)
        {
            error=failure.toString();ready=false;action=null;
            try
            {
                if(restoring){restored=false;persist(true);finished=true;}
                else if(cases!=null){restoreBlocks(server.getLevel(FacilitySchemaV2.DIMENSION));restorePlayer(player);persist(false);}
                else finished=true;
            }
            catch(Exception restoration){error += " RESTORATION_ERROR:"+restoration;restored=false;if(output!=null)persist(true);finished=true;}
            ProjectSeele.LOGGER.error("R45 school/pool native lifecycle failed",failure);
        }
    }

    private static void begin(ServerLevel level, ServerPlayer player)
    {
        ready=false;action=null;step=stagingTicks=0;current=cases.get(index).getAsJsonObject();savedBlocks.clear();
        for (var value:current.getAsJsonArray("restore_blocks"))
        {
            var q=pos(value);var entity=level.getBlockEntity(q);
            savedBlocks.put(q,new SavedBlock(level.getBlockState(q),entity==null?null:entity.saveWithFullMetadata().copy()));
        }
        row=new JsonObject();row.addProperty("id",current.get("id").getAsString());row.addProperty("actual_player_UUID",playerId.toString());
        row.add("outside_staging",current.getAsJsonArray("staging").deepCopy());row.add("actions",new JsonArray());
        Vec3 start=vec(current.getAsJsonArray("staging"));player.setGameMode(GameType.SPECTATOR);
        player.teleportTo(level,start.x,start.y,start.z,0,0);player.setDeltaMovement(Vec3.ZERO);player.fallDistance=0;
        ProjectSeele.LOGGER.info("R45 SCHOOL case={} actual_player={}",current.get("id").getAsString(),playerId);
    }

    private static void nextStep(ServerPlayer player)
    {
        action=current.getAsJsonArray("steps").get(step).getAsJsonObject();stepTicks=waterTicks=swimmingTicks=climbingTicks=blockedTicks=stationaryTicks=0;
        movedInWater=0;stepStart=player.position();
        ProjectSeele.LOGGER.info("R45 SCHOOL action case={} ordinal={} kind={} start={}",current.get("id").getAsString(),step,action.get("kind"),stepStart);
    }

    private static void sample(ServerPlayer player, Minecraft mc)
    {
        var r=new JsonObject();r.addProperty("age",age);r.addProperty("step",step);r.addProperty("kind",action.get("kind").getAsString());
        r.addProperty("server_position",player.position().toString());r.addProperty("client_position",mc.player.position().toString());
        r.addProperty("server_grounded",player.onGround());r.addProperty("client_grounded",mc.player.onGround());
        r.addProperty("server_in_water",player.isInWater());r.addProperty("client_in_water",mc.player.isInWater());
        r.addProperty("server_swimming",player.isSwimming());r.addProperty("client_swimming",mc.player.isSwimming());
        r.addProperty("server_climbable",player.onClimbable());r.addProperty("client_climbable",mc.player.onClimbable());
        r.addProperty("actual_key_forward",mc.options.keyUp.isDown());r.addProperty("actual_key_jump",mc.options.keyJump.isDown());
        r.addProperty("actual_key_sprint",mc.options.keySprint.isDown());r.addProperty("server_no_physics",player.noPhysics);
        r.addProperty("client_no_physics",mc.player.noPhysics);r.addProperty("server_air_supply",player.getAirSupply());
        r.addProperty("server_body_clear",player.level().noCollision(player,player.getBoundingBox().deflate(.025)));
        trace.add(r);if(trace.size()>180)trace.remove(0);row.add("last180_actual_samples",trace.deepCopy());
    }

    private static void restoreBlocks(ServerLevel level)
    {
        if (level==null) return;
        for (var entry:savedBlocks.entrySet())
        {
            var q=entry.getKey();var saved=entry.getValue();
            require(level.getBlockState(q).getBlock()==saved.state.getBlock(),"Concurrent block replacement refuses restoration at "+q);
            if (!level.getBlockState(q).equals(saved.state)) level.setBlock(q,saved.state,3);
            if (saved.nbt!=null)
            {
                var entity=level.getBlockEntity(q);require(entity!=null,"Original BE disappeared at "+q);
                if (!entity.saveWithFullMetadata().equals(saved.nbt)) { entity.load(saved.nbt.copy());entity.setChanged(); }
            }
        }
        savedBlocks.clear();
    }

    private static void restorePlayer(ServerPlayer player)
    {
        ready=false;action=null;if(originalPlayer==null)return;
        // Change mode first so native mode packets are emitted. Loading
        // afterwards preserves every original ability instead of allowing a
        // mode-default update to overwrite the full saved player's abilities.
        player.setGameMode(originalMode);player.load(originalPlayer.copy());player.noPhysics=originalNoPhysics;
        player.teleportTo(player.server.getLevel(originalDimension),originalPosition.x,originalPosition.y,originalPosition.z,originalYaw,originalPitch);
        player.onUpdateAbilities();player.inventoryMenu.broadcastFullState();
        player.connection.send(new net.minecraft.network.protocol.game.ClientboundSetCarriedItemPacket(player.getInventory().selected));
        player.connection.send(new net.minecraft.network.protocol.game.ClientboundSetHealthPacket(player.getHealth(),player.getFoodData().getFoodLevel(),player.getFoodData().getSaturationLevel()));
        player.connection.send(new net.minecraft.network.protocol.game.ClientboundSetExperiencePacket(player.experienceProgress,player.totalExperience,player.experienceLevel));
        require(player.getUUID().equals(playerId),"Original UUID not preserved");
        restored=false;restoring=true;restoreTicks=restoreStable=0;
    }

    private static void acknowledgeRestoration(ServerPlayer player,Minecraft mc)throws Exception
    {
        require(++restoreTicks<600,"Original player restoration packet acknowledgment timed out");
        // Pinned MC1.20.1 has exactly one Vec3 member on this listener:
        // awaitingPositionFromClient. Resolve by declared type so official/SRG
        // names cannot quietly turn the mandatory acknowledgment into a skip.
        var candidates=Arrays.stream(player.connection.getClass().getDeclaredFields())
            .filter(field->field.getType()==Vec3.class).toList();
        require(candidates.size()==1,"Pinned native pending-teleport field contract differs");
        var pending=candidates.get(0);pending.setAccessible(true);
        boolean nativeAck=pending.get(player.connection)==null;
        var expectedInventory=originalPlayer.getList("Inventory",10);
        var serverInventory=player.getInventory().save(new net.minecraft.nbt.ListTag());
        var clientInventory=mc.player.getInventory().save(new net.minecraft.nbt.ListTag());
        var serverAbilities=new CompoundTag();player.getAbilities().addSaveData(serverAbilities);
        var clientAbilities=new CompoundTag();mc.player.getAbilities().addSaveData(clientAbilities);
        var expectedAbilities=originalPlayer.getCompound("abilities");
        boolean aligned=nativeAck&&player.getUUID().equals(playerId)&&mc.player.getUUID().equals(playerId)
            &&player.level().dimension().equals(originalDimension)&&mc.level.dimension().equals(originalDimension)
            &&player.position().distanceToSqr(originalPosition)<.01&&mc.player.position().distanceToSqr(originalPosition)<.01
            &&player.gameMode.getGameModeForPlayer()==originalMode&&mc.gameMode.getPlayerMode()==originalMode
            &&serverInventory.equals(expectedInventory)&&clientInventory.equals(expectedInventory)
            &&player.getInventory().selected==originalPlayer.getInt("SelectedItemSlot")&&mc.player.getInventory().selected==originalPlayer.getInt("SelectedItemSlot")
            &&serverAbilities.getCompound("abilities").equals(expectedAbilities)&&clientAbilities.getCompound("abilities").equals(expectedAbilities)
            &&Math.abs(player.getHealth()-originalPlayer.getFloat("Health"))<.001&&Math.abs(mc.player.getHealth()-originalPlayer.getFloat("Health"))<.001
            &&player.experienceLevel==originalPlayer.getInt("XpLevel")&&mc.player.experienceLevel==originalPlayer.getInt("XpLevel")
            &&player.totalExperience==originalPlayer.getInt("XpTotal")&&mc.player.totalExperience==originalPlayer.getInt("XpTotal")
            &&Math.abs(player.experienceProgress-originalPlayer.getFloat("XpP"))<.001&&Math.abs(mc.player.experienceProgress-originalPlayer.getFloat("XpP"))<.001
            &&player.noPhysics==originalNoPhysics&&mc.player.noPhysics==originalNoPhysics;
        restorationEvidence=new JsonObject();restorationEvidence.addProperty("actual_UUID",playerId.toString());
        restorationEvidence.addProperty("server_position",player.position().toString());restorationEvidence.addProperty("client_position",mc.player.position().toString());
        restorationEvidence.addProperty("native_server_pending_teleport_cleared",nativeAck);restorationEvidence.addProperty("client_server_mode_inventory_abilities_health_XP_aligned",aligned);
        restorationEvidence.addProperty("ticks",restoreTicks);restorationEvidence.addProperty("mode",originalMode.getName());
        restorationEvidence.addProperty("server_full_NBT_load_performed",true);
        restorationEvidence.addProperty("tick_statistics_bytes","Root wrapper restores exact original playerdata/stats/advancements only after this process stops; MTR progress remains live");
        if(!aligned){restoreStable=0;return;}
        if(++restoreStable<8)return;
        restorationEvidence.addProperty("stable_acknowledged_ticks",restoreStable);
        Files.writeString(output.resolveSibling("player_after_ack_full_snbt.txt"),player.saveWithoutId(new CompoundTag()).toString());
        restored=true;restoring=false;persist(true);finished=true;
    }

    private static void persist(boolean complete)
    {
        var report=new JsonObject();report.addProperty("error",error);report.addProperty("start",Integer.getInteger("projectseele.r45SchoolPoolStart",0));
        report.addProperty("end",end);report.addProperty("case_denominator",cases==null?0:cases.size());report.add("cases",results.deepCopy());
        if(row!=null)report.add("active_case_evidence",row.deepCopy());report.addProperty("full_player_NBT_restored",restored);report.addProperty("client_restoration_packet_acknowledged",restored);if(restorationEvidence!=null)report.add("actual_restoration_evidence",restorationEvidence.deepCopy());
        report.addProperty("real_client_input",true);report.addProperty("mid_case_teleports",false);report.addProperty("final",complete);
        report.addProperty("save_reload","UNVERIFIED: run again in a fresh process and inspect complete original BE/UUID/progress");
        report.addProperty("artistic_acceptance",false);
        try { Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(report)); }
        catch(Exception failure) { throw new IllegalStateException("Native school evidence write failed",failure); }
    }

    private static BlockPos pos(JsonElement value)
    {var a=value.getAsJsonArray();return new BlockPos(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt());}
    private static Vec3 vec(JsonArray a)
    {return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static void require(boolean ok,String message) {if(!ok)throw new IllegalStateException(message);}
    private SchoolPoolLifecycleR45() { }
}

package com.projectseele.visual;

import com.google.gson.*;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.projectseele.entity.*;
import com.projectseele.world.*;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.Tag;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.common.util.FakePlayer;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPInputStream;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.lang.reflect.Method;

/** ROOT-only real-player production command/interaction observer; never installs or fabricates results. */
public final class TvCampaignNativeAcceptanceR45
{
    private static final String INPUT=System.getProperty("projectseele.r45CampaignAcceptancePlan","");
    private static JsonObject plan;private static Run run;
    private static final class Run
    {
        UUID player;String id;JsonArray steps;int cursor;long began,stepBegan,monitorBegan;
        UUID target;long generation;boolean stopped,supplyVerified;String result="RUNNING";
        final JsonArray events=new JsonArray();
    }
    private TvCampaignNativeAcceptanceR45(){}
    private static JsonObject plan()throws Exception
    {
        if(plan!=null)return plan;
        if(INPUT.isBlank()||!Path.of(INPUT).isAbsolute())throw new IllegalStateException("Explicit ROOT absolute plan required");
        var read=JsonParser.parseString(Files.readString(Path.of(INPUT))).getAsJsonObject();
        if(!"projectseele.r45.native-campaign-acceptance.v1".equals(read.get("schema").getAsString()))throw new IllegalStateException("Unknown acceptance plan");
        Path output=Path.of(read.get("output_directory").getAsString());
        if(!output.isAbsolute())throw new IllegalStateException("Absolute artifact output required");
        plan=read;return plan;
    }
    private static void bound(ServerPlayer player)throws Exception
    {
        var p=plan();var level=player.serverLevel();
        if(player instanceof FakePlayer||player.isSpectator()||!player.isAlive()||!player.hasPermissions(2))throw new IllegalStateException("One real alive non-spectator ROOT client operator required");
        long real=player.server.getPlayerList().getPlayers().stream().filter(q->!(q instanceof FakePlayer)).count();
        if(real!=1)throw new IllegalStateException("Single real client suite requires exactly one actual client; do not replace multiplayer with FakePlayer");
        Path expected=Path.of(p.get("world_root").getAsString()).toRealPath();
        Path actual=player.server.getWorldPath(LevelResource.ROOT).toRealPath();
        if(!actual.equals(expected)||actual.equals(Path.of(p.get("frozen_source_world").getAsString()).toRealPath()))throw new IllegalStateException("Explicit new QA copy required; frozen source is forbidden");
        if(!level.dimension().equals(FacilitySchemaV2.DIMENSION)||!p.get("world_id").getAsString().equals(Tokyo3BuildingWorldIdentityR44.get(level)))throw new IllegalStateException("Wrong world/dimension identity");
        if(Path.of(p.get("output_directory").getAsString()).toAbsolutePath().normalize().startsWith(actual))throw new IllegalStateException("Write artifacts outside world");
    }
    @SubscribeEvent public static void commands(RegisterCommandsEvent event)
    {
        if(INPUT.isBlank())return;
        event.getDispatcher().register(Commands.literal("seele").requires(s->s.hasPermission(2)).then(Commands.literal("native_campaign")
            .then(Commands.literal("start").then(Commands.argument("case",StringArgumentType.word()).executes(c->start(c.getSource().getPlayerOrException(),StringArgumentType.getString(c,"case")))))
            .then(Commands.literal("status").executes(c->status(c.getSource().getPlayerOrException())))
            .then(Commands.literal("snapshot").executes(c->snapshot(c.getSource().getPlayerOrException())))
            .then(Commands.literal("stop").executes(c->stop(c.getSource().getPlayerOrException())))));
    }
    private static int start(ServerPlayer player,String id)
    {
        try
        {
            bound(player);if(run!=null&&!run.stopped)throw new IllegalStateException("Existing acceptance run active");
            var selected=plan().getAsJsonObject("cases").getAsJsonObject(id);if(selected==null)throw new IllegalArgumentException("Unknown case");
            var campaign=TvCampaignSavedData.get(player.serverLevel());
            if(!campaign.active.isEmpty())throw new IllegalStateException("Existing player mission must not be commandeered");
            if(id.equals("full_ramiel")&&campaign.completed.contains("ramiel"))throw new IllegalStateException("First-episode archive proof needs a fresh declared QA copy without completed Ramiel");
            for(int unit=0;unit<3;unit++)if(!EvaLogisticsDirector.status(player.serverLevel(),unit).phase().equals("PARKED"))throw new IllegalStateException("Recover original units using production controls before starting fresh case");
            var current=new Run();current.player=player.getUUID();current.id=id;current.steps=selected.getAsJsonArray("steps");
            if(current.steps.size()<1||current.steps.size()>48)throw new IllegalArgumentException("Bounded case steps required");
            current.began=current.stepBegan=player.level().getGameTime();run=current;
            if(selected.has("capture_current_generation")&&selected.get("capture_current_generation").getAsBoolean())run.generation=campaign.generationR43;
            event(player,"BEGIN",id,observe(player));
            player.sendSystemMessage(Component.literal("原生验收开始："+id+"。人工步骤须实际行走/交互；没有跳过成功按钮。"));return 1;
        }
        catch(Exception failure){player.sendSystemMessage(Component.literal("验收前置未满足："+failure.getMessage()));return 0;}
    }
    private static int status(ServerPlayer player)
    {player.sendSystemMessage(Component.literal(run==null?"没有原生验收。":run.id+" / "+run.result+" / step "+run.cursor));return 1;}
    private static int snapshot(ServerPlayer player)
    {try{bound(player);if(run!=null)event(player,"OPERATOR_SNAPSHOT","read_only",observe(player));return 1;}catch(Exception failure){return 0;}}
    private static int stop(ServerPlayer player)
    {
        if(run==null||!run.player.equals(player.getUUID()))return 0;
        try{finish(player,"STOPPED_UNVERIFIED","Driver stop does not cancel or repair a production mission. Operator must use production controls.");}catch(Exception failure){return 0;}return 1;
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||run==null||run.stopped||event.getServer().getTickCount()%5!=0)return;
        var player=event.getServer().getPlayerList().getPlayer(run.player);if(player==null)return;
        try
        {
            bound(player);long now=player.level().getGameTime();
            if(now-run.began>72000){finish(player,"TIMEOUT_UNVERIFIED","Maximum 60 minute server-tick budget reached");return;}
            if(run.cursor>=run.steps.size()){finish(player,"PASSED_OBSERVED","All declared actual predicates observed; excludes visual/client-network and multiplayer claims");return;}
            var step=run.steps.get(run.cursor).getAsJsonObject();String kind=step.get("kind").getAsString(),name=step.get("id").getAsString();
            if(!run.supplyVerified&&step.has("requires_supply")&&step.get("requires_supply").getAsBoolean())
            {
                String blocker=supplyBlocker(player.serverLevel());if(!blocker.isEmpty()){finish(player,"BLOCKED_PREREQUISITE",blocker);return;}
                run.supplyVerified=true;
            }
            if(kind.equals("command"))
            {
                String command=step.get("command").getAsString();
                if(!command.matches("seele tv (?:select (?:sachiel|shamshel|ramiel)|support [012] npc|cancel|retry|status)")
                        &&!command.matches("seele eva (?:prepare|launch|recover) unit0[012]"))throw new IllegalArgumentException("Not an approved existing production command: "+command);
                int result=player.server.getCommands().performPrefixedCommand(player.createCommandSourceStack(),command);
                var detail=observe(player);detail.addProperty("command",command);detail.addProperty("command_return",result);event(player,"PRODUCTION_COMMAND",name,detail);
                if(result<=0){finish(player,"FAILED_COMMAND_REJECTED","Production command rejected: "+command);return;}
                if(step.has("capture_generation")&&step.get("capture_generation").getAsBoolean())run.generation=TvCampaignSavedData.get(player.serverLevel()).generationR43;
                if(step.has("begin_no_launch_monitor")&&step.get("begin_no_launch_monitor").getAsBoolean())
                {if(anyLaunch(player.serverLevel())){finish(player,"UNVERIFIED_TOO_LATE","Launch already began before cancel; not a no-launch regression");return;}run.monitorBegan=now;}
                advance(player);return;
            }
            if(kind.equals("interact"))
            {
                UUID id=UUID.fromString(step.get("entity_uuid").getAsString());var entity=player.serverLevel().getEntity(id);
                if(entity==null||player.distanceToSqr(entity)>36)return;
                var detail=observe(player);detail.addProperty("entity",id.toString());detail.addProperty("interaction_result",player.interactOn(entity,InteractionHand.MAIN_HAND).toString());
                event(player,"PRODUCTION_ENTITY_INTERACTION",name,detail);advance(player);return;
            }
            if(!Set.of("await","manual").contains(kind))throw new IllegalArgumentException("Unknown step kind");
            if(now==run.stepBegan||now-run.stepBegan==5)player.sendSystemMessage(Component.literal(step.has("instruction")?step.get("instruction").getAsString():"等待实际条件："+name));
            if(run.monitorBegan>0&&anyLaunch(player.serverLevel())){finish(player,"FAILED_OBSERVED","A real launch started after accepted cancellation");return;}
            if(condition(player,step))
            {event(player,"OBSERVED_PREDICATE",name,observe(player));advance(player);return;}
            int timeout=step.has("timeout_ticks")?step.get("timeout_ticks").getAsInt():12000;
            if(now-run.stepBegan>timeout)finish(player,"TIMEOUT_UNVERIFIED","Missing actual predicate: "+name+"; "+TvCampaignSavedData.get(player.serverLevel()).notice);
        }
        catch(Exception failure){try{finish(player,"ERROR_UNVERIFIED",failure.toString());}catch(Exception ignored){run.stopped=true;}}
    }
    private static void advance(ServerPlayer player){run.cursor++;run.stepBegan=player.level().getGameTime();}
    private static boolean anyLaunch(ServerLevel level)
    {for(int unit=0;unit<3;unit++){var eva=EvaLogisticsDirector.canonicalUnit(level,unit);if(eva!=null&&eva.isLaunchSequenceActive())return true;}return false;}
    private static UUID expected(String group,int unit)throws Exception
    {return UUID.fromString(plan().getAsJsonObject("original_identities").getAsJsonObject(group).get(Integer.toString(unit)).getAsString());}
    private static boolean originalBoarded(ServerLevel level,int unit)throws Exception
    {
        var eva=EvaLogisticsDirector.canonicalUnit(level,unit);
        return eva!=null&&eva.getUUID().equals(expected("eva",unit))&&eva.getPilotEntity() instanceof TrainingPilotEntity pilot
                &&pilot.getUUID().equals(expected("pilot",unit))&&pilot.getVehicle() instanceof EntryPlugCarrierEntity plug
                &&plug.getUUID().equals(expected("plug",unit))&&plug.getLinkedEva()==eva&&plug.getVehicle()==eva;
    }
    private static CompoundTag equipment(ServerLevel level)throws Exception
    {
        Method state=TvMissionEquipmentR45.class.getDeclaredMethod("state",ServerLevel.class);state.setAccessible(true);
        return ((net.minecraft.world.level.saveddata.SavedData)state.invoke(null,level)).save(new CompoundTag());
    }
    private static boolean loans(ServerLevel level,String status)throws Exception
    {
        var data=TvCampaignSavedData.get(level);var ledger=equipment(level);Set<UUID> found=new HashSet<>();
        for(var raw:ledger.getList("Loans",Tag.TAG_COMPOUND))
        {
            var row=(CompoundTag)raw;if(row.getLong("Generation")!=run.generation||!row.hasUUID("Owner")||!row.getUUID("Owner").equals(run.player))continue;
            if(!row.getString("Status").equals(status))return false;found.add(row.getUUID("Cargo"));
        }
        return found.contains(UUID.fromString(plan().get("shield_cargo").getAsString()))&&found.contains(UUID.fromString(plan().get("cannon_cargo").getAsString()));
    }
    private static boolean condition(ServerPlayer player,JsonObject step)throws Exception
    {
        var level=player.serverLevel();var data=TvCampaignSavedData.get(level);String test=step.get("condition").getAsString();
        switch(test)
        {
            case "original_boarded":for(var raw:step.getAsJsonArray("units"))if(!originalBoarded(level,raw.getAsInt()))return false;return true;
            case "combat_real_target":
                if(!data.phase.equals("combat")||data.angel==null||!(level.getEntity(data.angel) instanceof RamielEntity boss)||!boss.isAlive())return false;
                if(run.target==null)run.target=boss.getUUID();return run.generation==data.generationR43&&run.target.equals(data.angel);
            case "reinforcement_same_mission":return data.generationR43==run.generation&&run.target!=null&&run.target.equals(data.angel)&&originalBoarded(level,2)&&data.sorties.containsKey(2);
            case "cargo_borrowed":
                var cannon=EvaLogisticsDirector.canonicalUnit(level,1);var shield=EvaLogisticsDirector.canonicalUnit(level,0);
                return cannon!=null&&shield!=null&&loans(level,"loaned")&&TvMissionEquipmentR45.cannonAuthorized(cannon)&&TvMissionEquipmentR45.shieldAuthorized(shield);
            case "victory_unarchived":return data.phase.equals("combat_victory")&&data.targetDeathConfirmedR45&&!data.completed.contains("ramiel")&&data.generationR43==run.generation;
            case "originals_parked":
                for(var raw:step.getAsJsonArray("units")){int unit=raw.getAsInt();var eva=EvaLogisticsDirector.canonicalUnit(level,unit);if(eva==null||!eva.getUUID().equals(expected("eva",unit))||!EvaLogisticsDirector.status(level,unit).phase().equals("PARKED"))return false;}return true;
            case "cargo_stored":return loans(level,"stored")&&TvMissionEquipmentR45.missionEquipmentReturned(level,run.player,run.generation,"ramiel");
            case "near_entity":
                var contact=level.getEntity(UUID.fromString(step.get("entity_uuid").getAsString()));return contact!=null&&player.distanceToSqr(contact)<=36;
            case "holding_original_cargo":
                var held=player.getMainHandItem();return held.getCount()==1&&held.hasTag()&&held.getTag().hasUUID(TvMissionEquipmentR45.CARGO_ID)
                        &&held.getTag().getUUID(TvMissionEquipmentR45.CARGO_ID).equals(UUID.fromString(step.get("cargo_uuid").getAsString()));
            case "stored_at_entity":
                var receiver=level.getEntity(UUID.fromString(step.get("entity_uuid").getAsString()));
                if(!(receiver instanceof NervArmamentStationEntity rack)||!TvMissionEquipmentR45.physicalStockPresent(rack))return false;
                var slot=rack.getPersistentData();return slot.hasUUID(TvMissionEquipmentR45.CARGO_ID)&&slot.getUUID(TvMissionEquipmentR45.CARGO_ID).equals(UUID.fromString(step.get("cargo_uuid").getAsString()));
            case "episode_archived":return data.active.isEmpty()&&data.phase.equals("episode_archived")&&data.episodeChapterR45.equals("ramiel")&&data.episodeGenerationR45==run.generation&&Collections.frequency(data.completed,"ramiel")==1;
            case "cancel_no_automatic":
                if(run.monitorBegan==0||player.level().getGameTime()-run.monitorBegan<step.get("observe_ticks").getAsInt())return false;
                for(int unit=0;unit<3;unit++){if(!AutoSortieR32.missionToken(level).isEmpty())return false;var order=StaffCommandBookR24.unitOrder(level,unit);if(order!=null&&order.automatic)return false;}
                return data.phase.equals("cancel")||data.active.isEmpty();
            default:throw new IllegalArgumentException("Unknown actual predicate "+test);
        }
    }
    private static String supplyBlocker(ServerLevel level)throws Exception
    {
        var p=plan();
        String patchHash=HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(Path.of(p.get("supply_forward_patch").getAsString()))));
        if(!patchHash.equals(p.get("supply_forward_sha256").getAsString()))return "Supply forward patch epoch changed; cannot validate a different component";
        if(!BuiltInRegistries.ITEM.containsKey(new ResourceLocation("projectseele:yashima_shield"))||!BuiltInRegistries.ITEM.containsKey(new ResourceLocation("projectseele:eva_positron_cannon")))return "Real registered cannon/shield items missing; no give/phantom stock fallback";
        var site=TvEncounterSitesR45.site(level,"ramiel").orElse(null);
        if(site==null||!site.geometryValidated()||!site.modelReady()||!site.supportReady())return "Actual measured TV06/Unit02 site, geometry/model/support receipt not installed";
        int rows=0;
        try(var input=new GZIPInputStream(Files.newInputStream(Path.of(p.get("supply_forward_patch").getAsString())));var reader=new BufferedReader(new InputStreamReader(input,StandardCharsets.UTF_8)))
        {
            for(String line;(line=reader.readLine())!=null;){var row=JsonParser.parseString(line).getAsJsonObject();var pos=row.getAsJsonArray("pos");var at=new BlockPos(pos.get(0).getAsInt(),pos.get(1).getAsInt(),pos.get(2).getAsInt());
                if(!level.hasChunkAt(at))return "Supply proposal chunk not loaded for actual 5436-cell readback; ROOT load only its declared existing chunks";
                if(!BuiltInRegistries.BLOCK.getKey(level.getBlockState(at).getBlock()).toString().equals(row.get("after").getAsString())||level.getBlockEntity(at)!=null)return "5436-cell installed component mismatch at "+at;rows++;}
        }
        if(rows!=5436)return "Not the final 5436-cell supply proposal";
        for(String key:List.of("shield_surface","cannon_surface","shield_return","cannon_return"))
        {UUID id=UUID.fromString(p.getAsJsonObject("rack_ids").get(key).getAsString());if(!(level.getEntity(id) instanceof NervArmamentStationEntity rack)||!TvMissionEquipmentR45.missionRack(rack))return "Actual independent mission rack/return fixture missing: "+key;}
        return "";
    }
    private static JsonObject observe(ServerPlayer player)throws Exception
    {
        var level=player.serverLevel();var data=TvCampaignSavedData.get(level);var out=new JsonObject();out.addProperty("tick",level.getGameTime());
        out.addProperty("real_operator",player.getUUID().toString());out.addProperty("operator_fake",player instanceof FakePlayer);out.addProperty("operator_position",player.position().toString());
        out.addProperty("generation",data.generationR43);out.addProperty("phase",data.phase);out.addProperty("active",data.active);out.addProperty("notice",data.notice);out.addProperty("target",data.angel==null?"":data.angel.toString());
        out.addProperty("completed",data.completed.toString());out.addProperty("actual_campaign_full_nbt",data.save(new CompoundTag()).toString());out.addProperty("actual_equipment_full_nbt",equipment(level).toString());
        var fleet=new JsonArray();for(int unit=0;unit<3;unit++)
        {var eva=EvaLogisticsDirector.canonicalUnit(level,unit);var row=new JsonObject();row.addProperty("unit",unit);row.addProperty("phase",EvaLogisticsDirector.status(level,unit).phase());row.addProperty("eva",eva==null?"":eva.getUUID().toString());
            if(eva!=null){row.addProperty("position",eva.position().toString());row.addProperty("pilot",eva.getPilotEntity()==null?"":eva.getPilotEntity().getUUID().toString());row.addProperty("launch",eva.isLaunchSequenceActive());row.addProperty("armament",eva.getArmamentMask());}fleet.add(row);}
        out.add("fleet",fleet);return out;
    }
    private static void event(ServerPlayer player,String type,String id,JsonObject detail)throws Exception
    {var row=new JsonObject();row.addProperty("type",type);row.addProperty("id",id);row.add("actual",detail);run.events.add(row);write();}
    private static void finish(ServerPlayer player,String result,String reason)throws Exception
    {run.result=result;run.stopped=true;var detail=observe(player);detail.addProperty("reason",reason);event(player,"END",result,detail);player.sendSystemMessage(Component.literal("原生验收："+result+" / "+reason));}
    private static void write()throws Exception
    {
        var result=new JsonObject();result.addProperty("case",run.id);result.addProperty("result",run.result);result.addProperty("direct_success_identity_or_cargo_writes",false);
        result.addProperty("production_actions_mutate_declared_QA_world",true);
        result.addProperty("fake_players_used",false);result.addProperty("visual_quality_verified",false);result.addProperty("actual_client_packet_path_verified",false);result.addProperty("real_multiplayer_verified",false);
        result.addProperty("scope","Real operator production commands/entity interaction and read-only actual state; no finish/identity/cargo result writes, give, kill, spawn, teleport, reset or FakePlayer");result.add("events",run.events);
        Path directory=Path.of(plan().get("output_directory").getAsString());Files.createDirectories(directory);Files.writeString(directory.resolve(run.id+"_"+run.began+".json"),new GsonBuilder().setPrettyPrinting().create().toJson(result));
    }
}

package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervStaffEntity;
import com.projectseele.registry.ModItems;
import com.projectseele.world.*;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.*;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Real posted engineer and physical switch cycle, followed by a cold-process continuation. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class CoordinationR44Review
{
    public static final boolean ENABLED=Boolean.getBoolean("projectseele.r44CoordinationReview");
    private static final boolean RELOAD=Boolean.getBoolean("projectseele.r44CoordinationReload");
    public static volatile boolean done;
    private static int age,step,wait;
    private static int stepAge;
    private static int observedStep=-1;
    private static UUID instance;
    private static String originalCampaign;
    private static final JsonArray CASES=new JsonArray();
    private static final TicketType<ChunkPos> TICKET=TicketType.create("coordination_review_r44",Comparator.comparingLong(ChunkPos::toLong),100);
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||done||event.phase!=TickEvent.Phase.END)return;var server=event.getServer();if(server.getPlayerList().getPlayers().isEmpty())return;
        var world=server.getWorldPath(LevelResource.ROOT).normalize();
        if(!world.getFileName().toString().equals(com.projectseele.visual.NativeReviewWorldsR45.expectedName()))throw new IllegalStateException("Dossier review refuses owner world");
        try
        {
            if(++age>9000)throw new IllegalStateException("Dossier review deadline step="+step);
            var level=server.getLevel(FacilitySchemaV2.DIMENSION);var player=server.getPlayerList().getPlayers().get(0);
            for(var post:NervStaffDirector.roster(level))if(Set.of("misato","grid_liaison_r44").contains(post.id()))
            {var chunk=new ChunkPos(post.feet());level.getChunkSource().addRegionTicket(TICKET,chunk,2,chunk);level.getChunkAt(post.feet());}
            var data=CityCoordinationSavedDataR44.get(level);
            if(observedStep!=step){observedStep=step;stepAge=0;}else stepAge++;
            if(stepAge>1200)throw new IllegalStateException("Dossier step stalled: "+step+" / "+data.notice);
            if(age%100==0){var progress=new JsonObject();progress.addProperty("age",age);progress.addProperty("step",step);progress.addProperty("stage",data.stage);progress.addProperty("notice",data.notice);Files.writeString(world.resolve("r44_coordination_progress.json"),progress.toString());}
            var contact=NervStaffDirector.roster(level).stream().filter(p->p.id().equals("misato")).map(p->NervStaffSavedData.get(level).identity(p.id())).filter(Objects::nonNull)
                    .map(level::getEntity).filter(NervStaffEntity.class::isInstance).map(NervStaffEntity.class::cast).findFirst().orElse(null);
            if(age<100||contact==null)return;
            if(wait>0){wait--;return;}
            switch(step)
            {
                case 0->
                {
                    player.stopRiding();player.teleportTo(level,37.5,-406,390.5,0,0);player.getInventory().add(new ItemStack(ModItems.NERV_EMPLOYEE_CARD.get()));player.getInventory().add(new ItemStack(ModItems.SATELLITE_PHONE.get()));
                    if(RELOAD)
                    {
                        var checkpoint=JsonParser.parseString(Files.readString(world.resolve("r44_coordination_checkpoint.json"))).getAsJsonObject();
                        require(data.active&&data.stage==4&&data.tested,"Cold reload lost completed physical test");
                        require(data.instance.toString().equals(checkpoint.get("instance").getAsString()),"Cold reload changed task identity");
                        instance=data.instance;originalCampaign=checkpoint.get("campaign").getAsString();record("cold_reload_identity_evidence_and_stage");step=6;
                    }
                    else
                    {
                        originalCampaign=TvCampaignSavedData.get(level).save(new CompoundTag()).toString();
                        if(data.active){action(player,contact,"cancel",data.instance);wait=30;return;}
                        if(data.restoring){wait=20;return;}
                        action(player,contact,"start",null);require(data.active,"Start rejected: "+data.notice);instance=data.instance;
                        action(player,contact,"share",instance);require(data.stage==1,"Unread evidence was accepted");record("unread_evidence_cannot_advance");step++;
                    }
                }
                case 1->
                {
                    action(player,contact,"read/page",instance);action(player,contact,"read/annotation",instance);action(player,contact,"read/field",instance);
                    require(data.evidence==7&&data.acquired.size()==3,"Evidence missing");action(player,contact,"share",instance);require(data.stage==2&&data.knowledge==7,"Sharing did not advance");record("three_sources_and_explicit_sharing");
                    action(player,contact,"evacuate/services",instance);require(data.cityRequested,"City order missing");step++;
                }
                case 2->{if(data.stage!=3)return;record("actual_city_settles_before_test");require(!TvCampaignSavedData.get(level).active.equals("ramiel"),"Dossier secretly started battle");step++;}
                case 3->{String result=action(player,contact,"test/onsite",instance);require(!data.isolating&&!result.isEmpty(),"Uncertified passenger route was bypassed");record("uncertified_onsite_route_stays_locked");String response=action(player,contact,"test/delegate",instance);if(response.contains("尚未")){wait=20;return;}step++;}
                case 4->{if(!data.isolating){if(data.notice.startsWith("设备操作中止"))throw new IllegalStateException(data.notice);return;}require(!level.getBlockState(new BlockPos(36,-405,393)).getValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.POWERED),"Reserve switch not physically isolated");record("engineer_walks_and_physically_isolates");step++;}
                case 5->
                {
                    if(data.stage!=4||!data.tested)return;record("isolation_wait_and_physical_reconnection");
                    JsonObject checkpoint=new JsonObject();checkpoint.addProperty("instance",instance.toString());checkpoint.addProperty("campaign",originalCampaign);Files.writeString(world.resolve("r44_coordination_checkpoint.json"),checkpoint.toString());
                    write(world,true,"",data);done=true;
                }
                case 6->{action(player,contact,"supply/reserve",instance);step++;}
                case 7->{if(data.stage!=5)return;record("actual_supply_branch_charges_before_roster");action(player,contact,"assign/1/human",instance);action(player,contact,"consent/1",instance);require(data.stage==6,"Human confirmation missing");record("explicit_roster_consent");action(player,contact,"withdraw/1",instance);require(data.stage==5&&data.confirmed.isEmpty(),"Withdrawal failed");record("withdrawal_revokes_confirmation");action(player,contact,"assign/1/human",instance);action(player,contact,"consent/1",instance);step++;}
                case 8->
                {
                    action(player,contact,"finish",instance);require(!data.active&&data.stage==7&&data.archiveCount()>0,"Archive not completed");record("archive_is_separate_from_tv_completion");wait=20;step++;
                }
                case 9->
                {
                    require(!data.restoring,"Grid restoration still pending");action(player,contact,"start",null);UUID current=data.instance;require(!current.equals(instance),"Instance generation reused");
                    action(player,contact,"cancel",instance);require(data.active,"Stale cancellation affected new dossier");record("stale_instance_rejected");
                    action(player,contact,"cancel",current);require(!data.active&&data.acquired.size()==3,"Cancel discarded evidence");record("cancel_keeps_acquired_sources");wait=20;step++;
                }
                case 10->{require(!data.restoring,"Cancel restoration still pending");require(TvCampaignSavedData.get(level).save(new CompoundTag()).toString().equals(originalCampaign),"Dossier changed combat campaign progress");record("no_angel_no_launch_no_tv_progress_change");write(world,true,"",data);done=true;}
            }
        }
        catch(Exception error){write(world,false,error.toString(),null);done=true;ProjectSeele.LOGGER.error("R44 coordination review failed",error);}
    }
    private static String action(ServerPlayer player,NervStaffEntity contact,String action,UUID expected)
    {String result=CityCoordinationR44.request(player,contact,action,expected);ProjectSeele.LOGGER.info("R44 dossier {} -> {}",action,result);return result;}
    private static void require(boolean pass,String error){if(!pass)throw new IllegalStateException(error);}
    private static void record(String name){var row=new JsonObject();row.addProperty("case",name);row.addProperty("passed",true);CASES.add(row);}
    private static void write(Path world,boolean pass,String error,CityCoordinationSavedDataR44 data)
    {try{var j=new JsonObject();j.addProperty("passed",pass);j.addProperty("reload",RELOAD);j.addProperty("error",error);j.addProperty("step",step);j.add("cases",CASES);if(data!=null)j.addProperty("state",data.save(new CompoundTag()).toString());Files.writeString(world.resolve(RELOAD?"r44_coordination_reload.json":"r44_coordination_review.json"),new GsonBuilder().setPrettyPrinting().create().toJson(j));}catch(Exception e){throw new IllegalStateException(e);}}
    private CoordinationR44Review() {}
}

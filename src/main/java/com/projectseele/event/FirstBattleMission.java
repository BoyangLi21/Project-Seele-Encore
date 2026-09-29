package com.projectseele.event;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.SachielEntity;
import com.projectseele.registry.ModEntities;
import com.projectseele.world.EvaPilotResolver;
import com.projectseele.world.FirstBattleSavedData;
import com.projectseele.world.CityBattlefieldR29;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerBossEvent;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.BossEvent;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** An explicit briefing-room dispatch, a real surface approach and a persistent Angel identity. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class FirstBattleMission
{
    private record Site(String dimension,Vec3 hero,Vec3 angel,BlockPos console,float yaw) {}
    private static final Map<ServerLevel,Optional<Site>> SITES=new WeakHashMap<>();
    private static final Map<ServerLevel,ServerBossEvent> BARS=new WeakHashMap<>();
    private static final net.minecraft.server.level.TicketType<net.minecraft.world.level.ChunkPos> TICKET=
            net.minecraft.server.level.TicketType.create("first_battle_mission",Comparator.comparingLong(net.minecraft.world.level.ChunkPos::toLong),60);
    private static void loadTarget(ServerLevel level,BlockPos at)
    {
        var chunk=new net.minecraft.world.level.ChunkPos(at);
        level.getChunkSource().addRegionTicket(TICKET,chunk,2,chunk);level.getChunk(at);
    }
    private static Vec3 point(com.google.gson.JsonArray a){return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static Site site(ServerLevel level)
    {
        return SITES.computeIfAbsent(level,l->{
            Path path=l.getServer().getWorldPath(LevelResource.ROOT).resolve("first_battle_site_r10.json");if(!Files.isRegularFile(path))return Optional.empty();
            try{var d=JsonParser.parseString(Files.readString(path)).getAsJsonObject();String dim=d.get("dimension").getAsString();if(!l.dimension().location().toString().equals(dim))return Optional.empty();return Optional.of(new Site(dim,point(d.getAsJsonArray("hero")),point(d.getAsJsonArray("angel")),BlockPos.containing(point(d.getAsJsonArray("console"))),d.get("yaw").getAsFloat()));}
            catch(Exception e){ProjectSeele.LOGGER.error("First battle site rejected",e);return Optional.empty();}
        }).orElse(null);
    }
    private static ServerLevel missionLevel(ServerPlayer player)
    {
        for(ServerLevel level:player.server.getAllLevels())if(site(level)!=null)return level;return null;
    }
    public static boolean begin(ServerPlayer player)
    {
        ServerLevel level=missionLevel(player);if(level==null){player.displayClientMessage(Component.literal("当前世界尚未设置迎击区域。"),false);return false;}
        var data=FirstBattleSavedData.get(level);if(data.active!=null||data.missionOwner!=null){player.displayClientMessage(Component.literal("迎击任务已下达，请先完成当前行动。"),false);return false;}
        Site existingSite=site(level);
        if(!level.getEntitiesOfClass(SachielEntity.class,new net.minecraft.world.phys.AABB(existingSite.angel,existingSite.angel).inflate(220),
                a->a.isAlive()&&a.getTags().contains("seele_first_battle_mission")).isEmpty())
        {player.displayClientMessage(Component.literal("迎击区域仍有未归档的任务目标，本次不会重复生成使徒。"),false);return false;}
        data.missionOwner=player.getUUID();data.missionAngel=null;data.missionLastPos=null;data.missionCancelRequested=false;data.missionMissingTicks=0;data.setDirty();Site s=site(level);
        player.displayClientMessage(Component.literal("作战命令：驾驶初号机前往"+CityBattlefieldR29.name(level)+"。目标区域 X "+(int)s.hero.x+" / Z "+(int)s.hero.z+"。削弱使徒后将进入自主作战演出。"),false);return true;
    }
    public static boolean cancel(ServerPlayer player)
    {
        ServerLevel level=missionLevel(player);if(level==null)return false;var data=FirstBattleSavedData.get(level);
        if(!player.getUUID().equals(data.missionOwner)&&!player.hasPermissions(2))return false;
        if(data.active!=null)FirstBattleDirector.abort(level,"mission cancelled");
        data.missionCancelRequested=true;
        if(data.missionAngel==null){data.missionOwner=null;data.missionCancelRequested=false;}
        else if(level.getEntity(data.missionAngel) instanceof SachielEntity angel&&angel.getTags().contains("seele_first_battle_mission"))
        {angel.discard();data.missionAngel=null;data.missionOwner=null;data.missionCancelRequested=false;}
        data.setDirty();return true;
    }
    public static void naturalResolution(SachielEntity angel)
    {
        if(!(angel.level() instanceof ServerLevel level))return;var data=FirstBattleSavedData.get(level);
        if(data.active!=null||data.missionCancelRequested||data.missionOwner==null||!angel.getUUID().equals(data.missionAngel))return;
        TvCampaignDirector.firstBattleComplete(level,data.missionOwner,angel.getUUID());data.completedPilots.add(data.missionOwner);
        data.missionOwner=null;data.missionAngel=null;data.setDirty();
    }
    @SubscribeEvent public static void interact(PlayerInteractEvent.RightClickBlock event)
    {
        if(!(event.getEntity() instanceof ServerPlayer player)||!(event.getLevel() instanceof ServerLevel level))return;Site s=site(level);
        if(s==null||!event.getPos().equals(s.console)||player.distanceToSqr(Vec3.atCenterOf(s.console))>64)return;
        begin(player);event.setCanceled(true);event.setCancellationResult(InteractionResult.SUCCESS);
    }
    @SubscribeEvent public static void commands(RegisterCommandsEvent event)
    {
        if(!com.projectseele.visual.DevelopmentCommandsR43.enabled())return;
        event.getDispatcher().register(Commands.literal("seele").then(Commands.literal("firstbattle")
            .then(Commands.literal("begin").requires(s->s.hasPermission(2)).executes(c->begin(c.getSource().getPlayerOrException())?1:0))
            .then(Commands.literal("cancel").executes(c->cancel(c.getSource().getPlayerOrException())?1:0))
            .then(Commands.literal("status").executes(c->{ServerPlayer p=c.getSource().getPlayerOrException();ServerLevel l=missionLevel(p);if(l==null)return 0;var d=FirstBattleSavedData.get(l);p.displayClientMessage(Component.literal(d.active!=null?"自主行动中":d.missionOwner!=null?"迎击任务进行中":"作战资料室可下达迎击命令"),false);return 1;}))));
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||event.getServer().getTickCount()%10!=0)return;
        for(ServerLevel level:event.getServer().getAllLevels())
        {
            Site s=site(level);if(s==null)continue;var data=FirstBattleSavedData.get(level);var bar=BARS.computeIfAbsent(level,l->new ServerBossEvent(Component.literal("NERV 迎撃指令"),BossEvent.BossBarColor.YELLOW,BossEvent.BossBarOverlay.PROGRESS));bar.removeAllPlayers();
            if(data.missionOwner==null)continue;
            if(data.missionAngel!=null)
            {
                loadTarget(level,data.missionLastPos==null?BlockPos.containing(s.angel):data.missionLastPos);
                var entity=level.getEntity(data.missionAngel);
                if(entity==null)
                {
                    BlockPos last=data.missionLastPos==null?BlockPos.containing(s.angel):data.missionLastPos;
                    for(int x=-1;x<=1;x++)for(int z=-1;z<=1;z++)level.getChunk((last.getX()>>4)+x,(last.getZ()>>4)+z);
                    // A requested chunk can be FULL before its saved entities
                    // have attached. That interval is not proof of deletion.
                    boolean attached=level.areEntitiesLoaded(new net.minecraft.world.level.ChunkPos(last).toLong())&&level.isPositionEntityTicking(last);
                    if(attached&&++data.missionMissingTicks>40&&data.active==null){data.missionOwner=null;data.missionAngel=null;data.missionCancelRequested=false;data.setDirty();}
                    continue;
                }
                data.missionMissingTicks=0;data.missionLastPos=entity.blockPosition();data.setDirty();
                if(data.missionCancelRequested)
                {
                    if(entity instanceof SachielEntity&&entity.getTags().contains("seele_first_battle_mission"))entity.discard();
                    data.missionOwner=null;data.missionAngel=null;data.missionCancelRequested=false;data.setDirty();continue;
                }
            }
            var player=event.getServer().getPlayerList().getPlayer(data.missionOwner);if(player==null)continue;
            if(data.active!=null){bar.setVisible(false);continue;}bar.setVisible(true);bar.addPlayer(player);
            var eva=TvCampaignDirector.combatEvaR30(player);var campaign=com.projectseele.world.TvCampaignSavedData.get(level);int assigned=campaign.active.equals("sachiel")?campaign.assignedVariant:EvaUnit01Entity.UNIT_01;double distance=eva==null?player.position().distanceTo(s.hero):eva.position().distanceTo(s.hero);
            if(data.missionAngel==null)
            {
                bar.setName(Component.literal("初号机 · 前往"+CityBattlefieldR29.name(level)+" / "+Math.round(distance)+" m"));bar.setProgress(1);
                String blocked=CityBattlefieldR29.obstruction(level);if(!blocked.isEmpty()){bar.setName(Component.literal(blocked));continue;}
                if(eva==null||eva.level()!=level||!com.projectseele.world.TvSortiesR32.ready(eva)||distance>90)continue;
                loadTarget(level,BlockPos.containing(s.angel));SachielEntity angel=ModEntities.SACHIEL.get().create(level);if(angel==null)continue;
                angel.moveTo(s.angel.x,s.angel.y,s.angel.z,s.yaw+180,0);angel.yBodyRot=angel.yHeadRot=s.yaw+180;angel.setPersistenceRequired();angel.addTag("seele_first_battle_mission");angel.addTag("seele_first_battle_replay");angel.setTarget(eva);
                if(!level.noCollision(angel,angel.getBoundingBox())){player.displayClientMessage(Component.literal("迎击区域被占用，清空大道后会继续出动。"),true);continue;}
                if(!level.addFreshEntity(angel))continue;
                data.missionAngel=angel.getUUID();data.missionLastPos=angel.blockPosition();data.setDirty();
                TvCampaignDirector.firstBattleBound(level,data.missionOwner,angel.getUUID());
                com.projectseele.world.NervStaffDialogue.say(player,"葛城美里 · 作战通信","目标就在前方。先站稳，注意它两侧的手臂。攻击没有奏效就报告，别只顾着往前冲。");
                ProjectSeele.LOGGER.info("R10 MISSION Angel deployed {}",angel.getUUID());
            }
            if(level.getEntity(data.missionAngel) instanceof SachielEntity angel)
            {
                if(!angel.isAlive())
                {
                    TvCampaignDirector.firstBattleComplete(level,data.missionOwner,angel.getUUID());
                    data.missionOwner=null;data.missionAngel=null;data.setDirty();bar.removeAllPlayers();continue;
                }
                float field=angel.getAtField();bar.setName(Component.literal("第3使徒 サキエル · "+(field>0?"AT FIELD "+Math.round(field):"CORE "+Math.round(angel.getHealth()/angel.getMaxHealth()*100)+"%")));bar.setProgress(field>0?Math.min(1,field/900):angel.getHealth()/angel.getMaxHealth());
            }
        }
    }
    private FirstBattleMission() {}
}

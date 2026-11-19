package com.projectseele.event;

import com.projectseele.world.OperationText;
import com.google.gson.JsonParser;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.SachielEntity;
import com.projectseele.registry.ModEntities;
import com.projectseele.world.EvaPilotResolver;
import com.projectseele.world.FirstBattleSavedData;
import com.projectseele.world.CityBattlefieldR29;
import net.minecraft.commands.CommandSourceStack;
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
        if(com.projectseele.world.SurfaceAngelPlanR52.declared(level))return null;
        return SITES.computeIfAbsent(level,l->{
            Path path=l.getServer().getWorldPath(LevelResource.ROOT).resolve("first_battle_site_r10.json");if(!Files.isRegularFile(path))return Optional.empty();
            try{var d=JsonParser.parseString(Files.readString(path)).getAsJsonObject();String dim=d.get("dimension").getAsString();if(!l.dimension().location().toString().equals(dim))return Optional.empty();return Optional.of(new Site(dim,point(d.getAsJsonArray("hero")),point(d.getAsJsonArray("angel")),BlockPos.containing(point(d.getAsJsonArray("console"))),d.get("yaw").getAsFloat()));}
            catch(Exception e){ProjectSeele.LOGGER.error("First battle site rejected",e);return Optional.empty();}
        }).orElse(null);
    }
    private static ServerLevel missionLevel(ServerPlayer player)
    {
        for(ServerLevel level:player.server.getAllLevels())if(com.projectseele.world.SurfaceAngelPlanR52.declared(level))return level;
        for(ServerLevel level:player.server.getAllLevels())if(site(level)!=null)return level;return null;
    }
    public static boolean begin(ServerPlayer player)
    {
        ServerLevel level=missionLevel(player);if(level==null){player.displayClientMessage(Component.translatable("message.projectseele.first_battle.no_area"),false);return false;}
        var campaign=com.projectseele.world.TvCampaignSavedData.get(level);
        if(com.projectseele.world.SurfaceAngelPlanR52.handles(level,"sachiel"))
        {String blocker=com.projectseele.world.SurfaceAngelPlanR52.startBlocker(level,"sachiel");player.displayClientMessage(blocker.isEmpty()?Component.translatable("ops.projectseele.sachiel.registered"):OperationText.read(blocker),false);return false;}
        var data=FirstBattleSavedData.get(level);if(data.active!=null||data.missionOwner!=null){player.displayClientMessage(Component.translatable("message.projectseele.first_battle.active"),false);return false;}
        Site existingSite=site(level);
        if(!level.getEntitiesOfClass(SachielEntity.class,new net.minecraft.world.phys.AABB(existingSite.angel,existingSite.angel).inflate(220),
                a->a.isAlive()&&a.getTags().contains("seele_first_battle_mission")).isEmpty())
        {player.displayClientMessage(Component.translatable("message.projectseele.first_battle.existing_target"),false);return false;}
        data.missionOwner=player.getUUID();data.missionAngel=null;data.missionLastPos=null;data.missionCancelRequested=false;data.missionMissingTicks=0;data.setDirty();Site s=site(level);
        player.displayClientMessage(Component.translatable("ops.projectseele.sachiel.orders", OperationText.read(CityBattlefieldR29.name(level)), (int)s.hero.x, (int)s.hero.z),false);return true;
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
    /** /seele dev firstbattle: the standalone replay that the TV campaign has since taken over. */
    public static LiteralArgumentBuilder<CommandSourceStack> firstBattleCommand()
    {
        return Commands.literal("firstbattle")
            .then(Commands.literal("begin").executes(c->begin(c.getSource().getPlayerOrException())?1:0))
            .then(Commands.literal("cancel").executes(c->cancel(c.getSource().getPlayerOrException())?1:0))
            .then(Commands.literal("status").executes(c->{ServerPlayer p=c.getSource().getPlayerOrException();ServerLevel l=missionLevel(p);if(l==null)return 0;var d=FirstBattleSavedData.get(l);p.displayClientMessage(Component.translatable(d.active!=null?"ops.projectseele.sachiel.autonomous":d.missionOwner!=null?"ops.projectseele.sachiel.active":"ops.projectseele.sachiel.available"),false);return 1;}));
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||event.getServer().getTickCount()%10!=0)return;
        for(ServerLevel level:event.getServer().getAllLevels())
        {
            Site s=site(level);if(s==null)continue;var data=FirstBattleSavedData.get(level);var bar=BARS.computeIfAbsent(level,l->new ServerBossEvent(Component.translatable("message.projectseele.first_battle.order"),BossEvent.BossBarColor.YELLOW,BossEvent.BossBarOverlay.PROGRESS));bar.removeAllPlayers();
            // The TV surface director already owns spawn, approach, live bar and original UUID retention.
            // Independent development replays keep their separate lifecycle.
            if(com.projectseele.world.SurfaceAngelPlanR52.handles(level,com.projectseele.world.TvCampaignSavedData.get(level).active))
            {bar.setVisible(false);continue;}
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
                bar.setName(Component.translatable("ops.projectseele.sachiel.distance", OperationText.read(CityBattlefieldR29.name(level)), Math.round(distance)));bar.setProgress(1);
                String blocked=CityBattlefieldR29.obstruction(level);if(!blocked.isEmpty()){bar.setName(OperationText.read(blocked));continue;}
                if(eva==null||eva.level()!=level||!com.projectseele.world.TvSortiesR32.ready(eva)||distance>90)continue;
                loadTarget(level,BlockPos.containing(s.angel));SachielEntity angel=ModEntities.SACHIEL.get().create(level);if(angel==null)continue;
                angel.moveTo(s.angel.x,s.angel.y,s.angel.z,s.yaw+180,0);angel.yBodyRot=angel.yHeadRot=s.yaw+180;angel.setPersistenceRequired();angel.addTag("seele_first_battle_mission");angel.addTag("seele_first_battle_replay");angel.setTarget(eva);
                if(!level.noCollision(angel,angel.getBoundingBox())){player.displayClientMessage(Component.translatable("message.projectseele.first_battle.blocked"),true);continue;}
                if(!level.addFreshEntity(angel))continue;
                data.missionAngel=angel.getUUID();data.missionLastPos=angel.blockPosition();data.setDirty();
                TvCampaignDirector.firstBattleBound(level,data.missionOwner,angel.getUUID());
                com.projectseele.world.NervStaffDialogue.say(player,"葛城美里 · 作战通信","dialogue.projectseele.sachiel.approach");
                ProjectSeele.LOGGER.info("R10 MISSION Angel deployed {}",angel.getUUID());
            }
            if(level.getEntity(data.missionAngel) instanceof SachielEntity angel)
            {
                if(!angel.isAlive())
                {
                    TvCampaignDirector.firstBattleComplete(level,data.missionOwner,angel.getUUID());
                    data.missionOwner=null;data.missionAngel=null;data.setDirty();bar.removeAllPlayers();continue;
                }
                float field=angel.getAtField();bar.setName(field>0?Component.translatable("ops.projectseele.sachiel.at", Math.round(field)):Component.translatable("ops.projectseele.sachiel.core", Math.round(angel.getHealth()/angel.getMaxHealth()*100)));bar.setProgress(field>0?Math.min(1,field/900):angel.getHealth()/angel.getMaxHealth());
            }
        }
    }
    private FirstBattleMission() {}
}

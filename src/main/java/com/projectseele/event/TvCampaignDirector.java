package com.projectseele.event;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import com.projectseele.registry.ModEntities;
import com.projectseele.world.*;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.*;
import net.minecraft.world.BossEvent;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.living.LivingDeathEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class TvCampaignDirector
{
    private static final TicketType<ChunkPos> TICKET = TicketType.create("tv_campaign_r24", Comparator.comparingLong(ChunkPos::toLong), 60);
    private static final Map<ServerLevel, ServerBossEvent> BARS = new WeakHashMap<>();
    private static final Map<ServerLevel, Integer> MISSING = new WeakHashMap<>();
    private record Site(Vec3 hero, Vec3 angel, float yaw) {}
    private static final Map<ServerLevel, Optional<Site>> SITES = new WeakHashMap<>();
    private static Vec3 vector(com.google.gson.JsonArray a) { return new Vec3(a.get(0).getAsDouble(), a.get(1).getAsDouble(), a.get(2).getAsDouble()); }
    private static Site site(ServerLevel level)
    {
        return SITES.computeIfAbsent(level, key -> {
            Path file = level.getServer().getWorldPath(LevelResource.ROOT).resolve("first_battle_site_r10.json");
            if (!Files.isRegularFile(file)) return Optional.empty();
            try
            {
                var json = JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                if (!json.get("dimension").getAsString().equals(level.dimension().location().toString())) return Optional.empty();
                return Optional.of(new Site(vector(json.getAsJsonArray("hero")), vector(json.getAsJsonArray("angel")), json.get("yaw").getAsFloat()));
            }
            catch (Exception error) { ProjectSeele.LOGGER.error("TV campaign site rejected", error); return Optional.empty(); }
        }).orElse(null);
    }
    public static ServerLevel level(ServerPlayer player)
    { for (var level : player.server.getAllLevels()) if (site(level) != null) return level; return null; }
    public static Vec3 approachPointR30(ServerLevel level){var configured=site(level);return configured==null?null:configured.hero;}
    public static EvaUnit01Entity combatEvaR30(ServerPlayer player)
    {
        var level=level(player);if(level==null)return EvaPilotResolver.controlTarget(player);var data=TvCampaignSavedData.get(level);
        if(data.active.isEmpty())return EvaPilotResolver.controlTarget(player);
        Vec3 point=approachPointR30(level);
        return data.sorties.values().stream().map(entry->TvSortiesR32.unit(level,entry.unit))
                .filter(TvSortiesR32::ready).min(Comparator.comparingDouble(e->point==null?0:e.distanceToSqr(point))).orElse(null);
    }

    public static String briefing(ServerPlayer player)
    {
        var level = level(player); if (level == null) return "本世界尚未配置 TV 作战区域。";
        var data = TvCampaignSavedData.get(level); var chapter = selected(player,data);
        String activity = data.active.isEmpty() ? "尚未下达本章指令" : switch (data.phase)
        { case "alert" -> "使徒信号确认中 · 总部进入战斗配置";case "approach" -> "作战已接受，等待出击机体抵达"; case "combat" -> "目标正在交战"; case "cancel" -> "正在解除目标登记"; default -> "记录暂停，请查看提示"; };
        return "TV 1995 · 第 " + chapter.episode() + " 话 / " + chapter.title() + "\n"
                + (chapter.playable() ? "可执行作战" : "后续制作档案 · 尚不可开始") + " · 已归档 " + data.completed.size() + " 章\n"
                + activity + "\n" + TvSortiesR32.roster(data) + "\n" + chapter.briefing().replace("东北迎击大道", CityBattlefieldR29.name(level)) + "\n" + CityBattlefieldR29.obstruction(level) + "\n" + data.notice;
    }
    public static int begin(ServerPlayer player)
    {return beginAssigned(player,1,false,false);}
    public static int beginAssigned(ServerPlayer player,int variant,boolean npc,boolean rifle)
    {
        if(variant<0||variant>4||npc&&variant>2)return message(player,"NPC 驾驶员对应零号机、初号机、二号机；UN 机体可由玩家加入。",false);
        if (!NervStaffDialogue.authorized(player)) return message(player, "作战下达需要 NERV 通行权限。", false);
        var level = level(player); if (level == null) return message(player, "本世界尚未配置作战区域。", false);
        if(npc&&player.level()!=level)return message(player,"请进入第三新东京市后下达驾驶员出击指令。",false);
        var data = TvCampaignSavedData.get(level); var chapter = selected(player,data);
        if (!data.active.isEmpty()) return TvSortiesR32.reinforce(player,variant,npc,rifle);
        if (!chapter.playable()) return message(player, "这一章尚未制作完成。您可以从作战列表选择已制作的萨基尔或夏姆榭尔迎击。", false);
        var replay = FirstBattleSavedData.get(level);
        if (replay.active != null || replay.missionOwner != null) return message(player, "已有独立迎击或重播占用作战区，请先结束该行动。", false);
        data.generationR43++;
        data.owner = player.getUUID(); data.active = chapter.id(); data.phase = "alert";data.assignedVariant=variant;data.npcPilot=npc;data.autoArmament=npc&&rifle;data.pilotDispatchRequested=false; data.alertStarted=level.getGameTime();data.alertLine=0;data.notice = "出击编成："+TvSortiesR32.name(variant)+" · "+(npc?TrainingPilotEntity.pilotName(variant):"司令亲自驾驶"); data.angel = null; data.lastPosition = null; data.setDirty();
        data.assign(variant,player.getUUID(),npc,npc&&rifle);
        return message(player, "作战已接受。" + chapter.briefing().replace("东北迎击大道", CityBattlefieldR29.name(level)) + "\n" + CityBattlefieldR29.obstruction(level), true);
    }
    private static TvCampaignCatalog.Chapter selected(ServerPlayer player,TvCampaignSavedData data)
    {
        String id=data.active.isEmpty()?player.getPersistentData().getString("SeeleMissionChoiceR30"):data.active;
        return TvCampaignCatalog.find(id).orElse(TvCampaignCatalog.at(data.chapter));
    }
    public static int select(ServerPlayer player,String id)
    {
        if(!NervStaffDialogue.authorized(player))return message(player,"需要 NERV 指挥权限。",false);
        var mission=TvCampaignCatalog.find(id).orElse(null);
        if(mission==null||!mission.playable())return message(player,"这份作战尚未开放。",false);
        var level=level(player);if(level==null)return message(player,"当前世界没有已交付的作战区。",false);
        if(!TvCampaignSavedData.get(level).active.isEmpty())return message(player,"请先结束或取消正在执行的作战。",false);
        player.getPersistentData().putString("SeeleMissionChoiceR30",id);
        return message(player,"已选择："+mission.title()+" / "+mission.target()+"。\n"+briefing(player),true);
    }
    public static int cancel(ServerPlayer player)
    {
        var level = level(player); if (level == null) return 0;
        var data = TvCampaignSavedData.get(level);
        if (data.active.isEmpty()) return message(player, "当前没有 TV 作战。", false);
        if (!player.getUUID().equals(data.owner) && !player.hasPermissions(2)) return message(player, "只能撤销自己的作战指令。", false);
        if (data.active.equals("sachiel")) FirstBattleMission.cancel(player);
        TvMissionAlertR30.clear(level);
        data.phase = "cancel"; data.setDirty();
        return message(player, "作战已撤销，不计通关。机体仍需按正常流程回收。", true);
    }
    private static int message(ServerPlayer player, String text, boolean accepted)
    { player.sendSystemMessage(Component.literal(text)); return accepted ? 1 : 0; }
    public static void firstBattleComplete(ServerLevel level, UUID owner, UUID angel)
    { complete(level, "sachiel", owner, angel); }
    public static void firstBattleBound(ServerLevel level, UUID owner, UUID angel)
    {
        var data = TvCampaignSavedData.get(level);
        if (data.active.equals("sachiel") && owner.equals(data.owner) && data.angel == null)
        { data.angel = angel; data.phase = "combat"; data.setDirty(); }
    }
    private static void complete(ServerLevel level, String chapter, UUID owner, UUID angel)
    {
        var data = TvCampaignSavedData.get(level);
        var returning=java.util.List.copyOf(data.sorties.values());
        if (data.phase.equals("cancel") || !data.finish(chapter, owner, angel)) return;
        com.projectseele.world.PilotReturnR39.enqueue(level,returning);
        var player = level.getServer().getPlayerList().getPlayer(owner);
        if (player != null)
        {
            message(player, data.notice, true);
            NervStaffDialogue.say(player, "葛城美里 · 作战通信", "目标已确认消失。先别急着动，检查供电和机体状态，我们准备接你回来。");
        }
        ProjectSeele.LOGGER.info("TV CAMPAIGN completed={} owner={} target={}", chapter, owner, angel);
    }
    @SubscribeEvent public static void death(LivingDeathEvent event)
    {
        if (!(event.getEntity() instanceof ShamshelEntity angel) || !(angel.level() instanceof ServerLevel level)) return;
        var data = TvCampaignSavedData.get(level);
        if (angel.getUUID().equals(data.angel) && angel.getTags().contains("seele_tv_shamshel_r24")) complete(level, "shamshel", data.owner, angel.getUUID());
    }
    private static void load(ServerLevel level, BlockPos pos)
    {
        var chunk = new ChunkPos(pos); level.getChunkSource().addRegionTicket(TICKET, chunk, 2, chunk); level.getChunk(pos);
    }
    private static void pilotContinuity(ServerLevel level,TvCampaignSavedData data)
    {
        TvSortiesR32.continuity(level,data);
    }
    @SubscribeEvent public static void protectReconnectingPilot(net.minecraftforge.event.entity.living.LivingAttackEvent event)
    {
        if(!(event.getEntity() instanceof ServerPlayer player)||!event.getSource().is(net.minecraft.tags.DamageTypeTags.IS_FALL))return;
        var data=TvCampaignSavedData.get(player.serverLevel());
        if(data.sorties.values().stream().anyMatch(s->s.resumePending&&s.wasRiding&&player.getUUID().equals(s.commander)&&s.resumeTicks<=200))event.setCanceled(true);
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END) return;
        for (var level : event.getServer().getAllLevels())
        {
            Site site = site(level); if (site == null) continue;
            var data = TvCampaignSavedData.get(level);
            pilotContinuity(level,data);
            if(event.getServer().getTickCount()%10!=0)continue;
            var bar = BARS.computeIfAbsent(level, key -> new ServerBossEvent(Component.literal("TV 作战"), BossEvent.BossBarColor.RED, BossEvent.BossBarOverlay.PROGRESS));
            bar.removeAllPlayers();
            if (data.active.isEmpty()) continue;
            TvSortiesR32.updateTarget(level,data);
            if(data.phase.equals("alert"))
            {
                var commander=event.getServer().getPlayerList().getPlayer(data.owner);
                if(!TvMissionAlertR30.tick(level,data,commander)||commander==null)continue;
                if(data.active.equals("sachiel")&&!FirstBattleMission.begin(commander)){data.clear("迎击区暂不可用，请确认其他行动已结束后重新下达指令。");continue;}
                data.phase="approach";data.setDirty();
            }
            if (data.phase.equals("cancel"))
            {
                if (data.angel == null) { data.clear("行动已取消，本章可以重新接受。"); continue; }
                load(level, data.lastPosition == null ? BlockPos.containing(site.angel) : data.lastPosition);
                var entity = level.getEntity(data.angel);
                if (entity != null && entity.getTags().contains("seele_tv_shamshel_r24")) entity.discard();
                if (entity != null || !data.active.equals("shamshel")) { data.clear("行动已取消，本章可以重新接受。"); MISSING.remove(level); }
                else if (MISSING.merge(level, 1, Integer::sum) > 40) { data.clear("目标记录已解除，未计通关。"); MISSING.remove(level); }
                continue;
            }
            if (data.active.equals("sachiel"))
            {
                var first = FirstBattleSavedData.get(level);
                if (data.owner.equals(first.missionOwner))
                {
                    if (first.missionAngel != null && data.angel == null)
                    { data.angel = first.missionAngel; data.phase = "combat"; data.setDirty(); }
                }
                else if (first.active == null) data.clear("独立迎击已结束或被取消，未收到该章节的完成信号。");
                continue;
            }
            var player = event.getServer().getPlayerList().getPlayer(data.owner);
            if (player == null || player.level() != level) continue;
            bar.addPlayer(player);
            for(var participant:data.sorties.values()){var p=event.getServer().getPlayerList().getPlayer(participant.commander);if(p!=null&&p.level()==level)bar.addPlayer(p);}
            if (data.angel == null)
            {
                var eva = combatEvaR30(player);
                double distance = (eva == null ? player.position() : eva.position()).distanceTo(site.hero);
                bar.setName(Component.literal("第4使徒迎击 · 前往" + CityBattlefieldR29.name(level) + " / " + Math.round(distance) + " m")); bar.setProgress(1);
                String blocked = CityBattlefieldR29.obstruction(level);
                if (!blocked.isEmpty()) { bar.setName(Component.literal(blocked)); continue; }
                if (!TvSortiesR32.ready(eva) || distance > 90) continue;
                load(level, BlockPos.containing(site.angel));
                if(!level.isPositionEntityTicking(BlockPos.containing(site.angel)))continue;
                if(!level.getEntitiesOfClass(ShamshelEntity.class,new net.minecraft.world.phys.AABB(site.angel,site.angel).inflate(180),
                        q->q.isAlive()&&q.getTags().contains("seele_tv_shamshel_r24")).isEmpty())
                {bar.setName(Component.literal("战区仍有未归档目标，请先检查原目标"));continue;}
                var angel = ModEntities.SHAMSHEL.get().create(level); if (angel == null) continue;
                angel.moveTo(site.angel.x, site.angel.y + 4, site.angel.z, site.yaw + 180, 0);
                angel.yBodyRot = angel.yHeadRot = site.yaw + 180; angel.setPersistenceRequired(); angel.addTag("seele_tv_shamshel_r24"); angel.setTarget(eva);
                if (!level.noCollision(angel, angel.getBoundingBox())) { bar.setName(Component.literal("迎击区域被占用，请清空后继续")); continue; }
                if (!level.addFreshEntity(angel)) continue;
                data.angel = angel.getUUID(); data.lastPosition = angel.blockPosition(); data.phase = "combat"; data.setDirty();
                message(player, "目标确认。光鞭将先蓄势再横扫，注意两侧退路。", true);
            }
            load(level, data.lastPosition == null ? BlockPos.containing(site.angel) : data.lastPosition);
            if (level.getEntity(data.angel) instanceof ShamshelEntity angel)
            {
                MISSING.remove(level);
                if (!angel.blockPosition().equals(data.lastPosition)) { data.lastPosition = angel.blockPosition(); data.setDirty(); }
                TvSortiesR32.updateTarget(level,data);
                float field = angel.getAtField();
                bar.setName(Component.literal("第4使徒 夏姆榭尔 · " + (field > 0 ? "AT 力场 " + Math.round(field) : "核心 " + Math.round(100 * angel.getHealth() / angel.getMaxHealth()) + "%")));
                bar.setProgress(Math.max(0, Math.min(1, field > 0 ? field / 700 : angel.getHealth() / angel.getMaxHealth())));
            }
            else if (MISSING.merge(level, 1, Integer::sum) > 40)
            { data.clear("目标实体已丢失。本章未完成；确认世界状态后可重新接受作战。"); MISSING.remove(level); }
        }
    }
    @SubscribeEvent public static void commands(RegisterCommandsEvent event)
    {
        event.getDispatcher().register(Commands.literal("seele").then(Commands.literal("tv")
                .then(Commands.literal("status").executes(c -> message(c.getSource().getPlayerOrException(), briefing(c.getSource().getPlayerOrException()), true)))
                .then(Commands.literal("begin").executes(c -> begin(c.getSource().getPlayerOrException())))
                .then(Commands.literal("select").then(Commands.literal("sachiel").executes(c->select(c.getSource().getPlayerOrException(),"sachiel"))).then(Commands.literal("shamshel").executes(c->select(c.getSource().getPlayerOrException(),"shamshel"))))
                .then(Commands.literal("cancel").executes(c -> cancel(c.getSource().getPlayerOrException())))));
    }
    private TvCampaignDirector() {}
}

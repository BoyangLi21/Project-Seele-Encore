package com.projectseele.event;

import com.projectseele.entity.Angel;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.RamielEntity;
import com.projectseele.registry.ModEntities;
import com.projectseele.world.*;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.ServerBossEvent;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.MobSpawnType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.chunk.ChunkStatus;
import net.minecraft.network.chat.Component;
import net.minecraftforge.event.entity.living.LivingDeathEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.Comparator;

/** One real owned boss per TV mission, with bounded preload and recoverable failure. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class TvEncounterDirectorR45
{
    private static final TicketType<ChunkPos> TICKET=TicketType.create("tv_encounter_r45",Comparator.comparingLong(ChunkPos::toLong),600);
    public static String tag(String chapter){return "seele_tv_r45_"+chapter;}
    private static void retain(ServerLevel l,BlockPos pos)
    {var c=new ChunkPos(pos);l.getChunkSource().addRegionTicket(TICKET,c,2,c);l.getChunkSource().getChunkFuture(c.x,c.z,ChunkStatus.FULL,true);}
    private static boolean corridorReady(ServerLevel l,TvEncounterSitesR45.Site site,int segments)
    {
        for(int n=0;n<=segments;n++)
        {
            var point=BlockPos.containing(site.hero().lerp(site.angel(),n/(double)segments));
            if(l.getChunkSource().getChunkNow(point.getX()>>4,point.getZ()>>4)==null)return false;
        }
        return true;
    }
    public static String startBlocker(ServerLevel l,String chapter)
    {
        String reason=TvEncounterSitesR45.startBlocker(l,chapter);if(!reason.isEmpty())return reason;
        if(chapter.equals("gaghiel")&&!BuiltInRegistries.ENTITY_TYPE.containsKey(new ResourceLocation("projectseele:gaghiel")))
            return "海上迎击仍在准备中。";
        if(!Tokyo3RamielBattleSavedData.get(l).battles().isEmpty())return "已有行动占用战区，请先结束该行动。";
        return "";
    }
    public static void tick(ServerLevel l,TvCampaignSavedData d,ServerPlayer commander,ServerBossEvent bar)
    {
        if(d.phase.equals("combat_victory")||d.phase.equals("episode_archived"))
        {TvEncounterRulesR45.stopEquipment(l,d);bar.setName(Component.literal(d.notice));return;}
        var site=TvEncounterSitesR45.site(l,d.active).orElse(null);
        if(site==null){TvEncounterRulesR45.stopEquipment(l,d);d.notice="作战阵地暂不可用，请等待恢复或取消行动。";return;}
        if(!site.id().equals(d.encounterSiteR45)||!site.fingerprint().equals(d.encounterLayoutR45)
                ||!site.geometryValidated()||!site.modelReady())
        {
            TvEncounterRulesR45.stopEquipment(l,d);
            if(d.angel!=null&&l.getEntity(d.angel) instanceof Mob original&&owned(original,d))original.setNoAi(true);
            d.notice="原作战阵地正在重新确认，请恢复原配置或取消行动。";return;
        }
        // Retain the saved original even during a hold; a reload is not a loss.
        if(d.angel!=null)retain(l,d.lastPosition==null?BlockPos.containing(site.angel()):d.lastPosition);
        if(commander!=null)bar.addPlayer(commander);
        for(var s:d.sorties.values())
        {var p=l.getServer().getPlayerList().getPlayer(s.commander);if(p!=null&&p.level()==l)bar.addPlayer(p);}
        if(d.phase.equals("failure"))
        {TvEncounterRulesR45.stopEquipment(l,d);bar.setName(Component.literal(d.notice+" · 可重试或取消，不计通关"));return;}
        if(d.angel!=null&&TvSortiesR32.allOriginalsUnavailable(l,d))
        {d.phase="failure";d.notice="出战机体暂不可用，请完成回收整备后重试。";d.setDirty();}
        if(d.phase.equals("failure")){TvEncounterRulesR45.stopEquipment(l,d);if(d.angel!=null&&l.getEntity(d.angel) instanceof Mob m&&owned(m,d))m.setNoAi(true);return;}
        String blocked=commander==null||commander.level()!=l?"司令暂离战区，原目标与任务暂停。":TvEncounterRulesR45.obstruction(l,d);
        if(blocked.isEmpty())blocked=TvEncounterRulesR45.equipmentBlocker(l,d);
        if(blocked.isEmpty()&&!TvEncounterRulesR45.visibleToCommander(l,d,commander))
            blocked="远程观测仍在准备中，请保持阵地。";
        var lead=TvSortiesR32.assignedUnit(l,d,site.primaryUnit());
        if(blocked.isEmpty()&&(!TvSortiesR32.readyAssigned(l,d.sorties.get(site.primaryUnit()))||lead.position().distanceTo(site.hero())>45))
            blocked="等待主战机完成整备发射并抵达阵地。";
        if(!blocked.isEmpty())
        {
            TvEncounterRulesR45.pauseFire(l,d);
            if(d.angel!=null&&l.getEntity(d.angel)instanceof Mob existing&&owned(existing,d))existing.setNoAi(true);
            d.notice=blocked;bar.setName(Component.literal(blocked));bar.setProgress(1);return;
        }
        retain(l,BlockPos.containing(site.hero()));retain(l,BlockPos.containing(site.angel()));
        // A narrow actual shot corridor is preloaded incrementally. The client
        // still needs its own real-entity rendering handshake, never a fake Mob.
        // Refresh the whole narrow corridor within the 600-tick ticket lifetime.
        // A completed first pass does not mean its middle chunks can be abandoned.
        int cursorBefore=d.rayPreloadCursorR45;
        int segments=Math.max(1,(int)Math.ceil(site.separation()/16));
        for(int count=0;count<2&&d.rayPreloadCursorR45<=segments;count++,d.rayPreloadCursorR45++)
        {
            double t=d.rayPreloadCursorR45/(double)segments;
            retain(l,BlockPos.containing(site.hero().lerp(site.angel(),t)));
        }
        if(d.rayPreloadCursorR45!=cursorBefore)d.setDirty();
        if(d.rayPreloadCursorR45<=segments){d.notice="正在校准远程火控。";return;}
        int cursor=(int)((l.getGameTime()/10*2)%(segments+1));
        for(int n=0;n<2;n++)retain(l,BlockPos.containing(site.hero().lerp(site.angel(),((cursor+n)%(segments+1))/(double)segments)));
        if(!corridorReady(l,site,segments))
        {
            TvEncounterRulesR45.pauseFire(l,d);
            if(d.angel!=null&&l.getEntity(d.angel) instanceof Mob original&&owned(original,d))original.setNoAi(true);
            d.notice="火控通路正在恢复，请保持阵地。";return;
        }
        if(d.angel==null)
        {
            if(!l.isPositionEntityTicking(BlockPos.containing(site.angel())))return;
            var type=d.active.equals("ramiel")?ModEntities.RAMIEL.get():BuiltInRegistries.ENTITY_TYPE.get(new ResourceLocation("projectseele:gaghiel"));
            var created=type.create(l);
            if(!(created instanceof Mob boss)||!(boss instanceof Angel))
            {d.notice="海上迎击仍在准备中。";return;}
            boss.moveTo(site.angel().x,site.angel().y,site.angel().z,site.yaw()+180,0);
            boss.finalizeSpawn(l,l.getCurrentDifficultyAt(boss.blockPosition()),MobSpawnType.EVENT,null,null);
            if(!l.noCollision(boss,boss.getBoundingBox())){d.notice="目标位置尚未确认，请等待作战指示。";return;}
            if(!l.getEntitiesOfClass(Mob.class,boss.getBoundingBox().inflate(128),m->m.isAlive()&&m.getTags().contains(tag(d.active))).isEmpty())
            {d.notice="战区仍有目标，请先处理现有行动。";return;}
            boss.setPersistenceRequired();boss.setNoAi(true);boss.addTag(tag(d.active));
            boss.getPersistentData().putLong("TvGenerationR45",d.generationR43);
            boss.getPersistentData().putUUID("TvOwnerR45",d.owner);
            boss.setTarget(lead);
            if(!l.addFreshEntity(boss))return;
            d.angel=boss.getUUID();d.lastPosition=boss.blockPosition();d.phase="combat";d.setDirty();
        }
        retain(l,d.lastPosition==null?BlockPos.containing(site.angel()):d.lastPosition);
        if(l.getEntity(d.angel)instanceof Mob boss&&owned(boss,d)&&boss.isAlive())
        {
            d.missingTicksR45=0;
            if(!TvEncounterRulesR45.targetFrameReady(l,d,commander))
            {boss.setNoAi(true);d.notice="正在确认远方目标，请保持阵地。";bar.setName(Component.literal(d.notice));return;}
            boss.setNoAi(false);
            if(!boss.blockPosition().equals(d.lastPosition)){d.lastPosition=boss.blockPosition();d.setDirty();}
            if(d.active.equals("ramiel"))boss.setTarget(lead);
            float progress=boss.getHealth()/boss.getMaxHealth();
            bar.setName(Component.literal(d.active.equals("ramiel")?"屋岛作战 · 远程炮击与防护":"TV08 港区迁址演习 · 迦基尔"));
            bar.setProgress(Math.max(0,Math.min(1,progress)));
        }
        else
        {
            if(++d.missingTicksR45>=40)
            {d.phase="failure";d.notice="目标通信中断，请重试确认或取消行动；未计通关。";d.setDirty();}
        }
    }
    public static boolean owned(Mob boss,TvCampaignSavedData d)
    {return boss.getTags().contains(tag(d.active))&&boss.getPersistentData().getLong("TvGenerationR45")==d.generationR43
            &&d.owner!=null&&boss.getPersistentData().hasUUID("TvOwnerR45")&&d.owner.equals(boss.getPersistentData().getUUID("TvOwnerR45"));}
    @SubscribeEvent public static void death(LivingDeathEvent e)
    {
        if(!(e.getEntity()instanceof Mob boss)||!(boss.level()instanceof ServerLevel l))return;
        var d=TvCampaignSavedData.get(l);
        if(!TvEncounterRulesR45.handles(d.active)||!boss.getUUID().equals(d.angel)||!owned(boss,d))return;
        var owner=d.owner==null?null:l.getServer().getPlayerList().getPlayer(d.owner);
        boolean valid=d.phase.equals("combat")&&owner!=null&&owner.level()==l
                &&TvEncounterRulesR45.targetFrameReady(l,d,owner)&&TvEncounterRulesR45.equipmentBlocker(l,d).isEmpty();
        // Evaluate live mission permission before the terminal fact revokes it.
        d.targetDeathConfirmedR45=true;d.setDirty();
        if(valid)TvCampaignDirector.encounterCompleteR45(l,d.active,d.owner,boss.getUUID());
        else if(!d.phase.equals("cancel"))
        {d.phase="failure";d.notice="目标死亡已确认，本行动未归档；请取消后重新接受作战。";d.setDirty();}

    }
    @SubscribeEvent public static void logout(net.minecraftforge.event.entity.player.PlayerEvent.PlayerLoggedOutEvent e)
    {if(e.getEntity() instanceof ServerPlayer p)TvEncounterRulesR45.logout(p);}
    @SubscribeEvent public static void unloaded(net.minecraftforge.event.level.LevelEvent.Unload e)
    {if(e.getLevel() instanceof ServerLevel l)TvEncounterRulesR45.clearSession(l);}
    private TvEncounterDirectorR45(){}
}

package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.nbt.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.saveddata.SavedData;
import java.util.*;

/** One cooperative TV chronology per world; replays use the old independent system. */
public final class TvCampaignSavedData extends SavedData
{
    public int chapter;
    public UUID owner, angel;
    public UUID pilotEva, pilotPlug;
    public boolean wasRiding, resumePending;
    public int resumeTicks;
    public int assignedVariant=1,alertLine;
    public boolean npcPilot,autoArmament,pilotDispatchRequested;
    public long alertStarted;
    public long generationR43;
    public int rayPreloadCursorR45,missingTicksR45;
    public boolean targetDeathConfirmedR45;
    public String encounterSiteR45="";
    public String encounterLayoutR45="";
    public String episodeStateR45="",episodeChapterR45="";
    public long episodeGenerationR45;
    public boolean equipmentReturnedR45;
    public final List<String> combatVictoriesR45=new ArrayList<>();
    private final Map<Integer,Recovery> recoveryR45=new LinkedHashMap<>();
    public record Recovery(UUID eva,UUID pilot,long generation){}
    public String active = "", phase = "idle", notice = "";
    public BlockPos lastPosition;
    public final List<String> completed = new ArrayList<>();
    public static final class Sortie
    {
        public int unit,resumeTicks;
        public UUID commander,eva,plug,pilotR45;
        public boolean npc,rifle,wasRiding,resumePending,dispatchRequested;
        public BlockPos position;
        public Sortie(int unit,UUID commander,boolean npc,boolean rifle)
        {this.unit=unit;this.commander=commander;this.npc=npc;this.rifle=rifle;this.pilotR45=npc?null:commander;}
    }
    public final Map<Integer,Sortie> sorties=new LinkedHashMap<>();
    public void assign(int unit,UUID commander,boolean npc,boolean rifle)
    {sorties.put(unit,new Sortie(unit,commander,npc,rifle));setDirty();}
    public static TvCampaignSavedData get(ServerLevel level)
    { return level.getDataStorage().computeIfAbsent(TvCampaignSavedData::load, TvCampaignSavedData::new, "projectseele_tv_campaign_r24"); }
    public static TvCampaignSavedData load(CompoundTag tag)
    {
        var data = new TvCampaignSavedData();
        data.chapter = Math.max(0, Math.min(tag.getInt("Chapter"), TvCampaignCatalog.CHAPTERS.size()));
        if (tag.hasUUID("Owner")) data.owner = tag.getUUID("Owner");
        if (tag.hasUUID("Angel")) data.angel = tag.getUUID("Angel");
        if (tag.hasUUID("PilotEva")) data.pilotEva=tag.getUUID("PilotEva");
        if (tag.hasUUID("PilotPlug")) data.pilotPlug=tag.getUUID("PilotPlug");
        data.wasRiding=tag.getBoolean("WasRiding");
        data.assignedVariant=tag.contains("AssignedVariant")?Math.max(0,Math.min(2,tag.getInt("AssignedVariant"))):1;
        data.npcPilot=tag.getBoolean("NpcPilot");data.autoArmament=tag.getBoolean("AutoArmament");data.pilotDispatchRequested=tag.getBoolean("PilotDispatchRequested");data.alertStarted=tag.getLong("AlertStarted");data.alertLine=tag.getInt("AlertLine");
        data.active = tag.getString("Active"); data.phase = tag.getString("Phase"); data.notice = tag.getString("Notice");
        data.generationR43=tag.getLong("GenerationR43");
        data.rayPreloadCursorR45=Math.max(0,tag.getInt("RayPreloadCursorR45"));
        data.encounterSiteR45=tag.getString("EncounterSiteR45");data.encounterLayoutR45=tag.getString("EncounterLayoutR45");data.targetDeathConfirmedR45=tag.getBoolean("TargetDeathConfirmedR45");
        data.episodeStateR45=tag.getString("EpisodeStateR45");data.episodeChapterR45=tag.getString("EpisodeChapterR45");
        data.episodeGenerationR45=tag.getLong("EpisodeGenerationR45");data.equipmentReturnedR45=tag.getBoolean("EquipmentReturnedR45");
        for(var raw:tag.getList("CombatVictoriesR45",Tag.TAG_STRING))data.combatVictoriesR45.add(raw.getAsString());
        for(var raw:tag.getList("OriginalRecoveryR45",Tag.TAG_COMPOUND))
        {var row=(CompoundTag)raw;if(row.hasUUID("Eva")&&row.hasUUID("Pilot"))data.recoveryR45.putIfAbsent(row.getInt("Unit"),new Recovery(row.getUUID("Eva"),row.getUUID("Pilot"),row.getLong("Generation")));}
        if (tag.contains("LastPosition")) data.lastPosition = BlockPos.of(tag.getLong("LastPosition"));
        for (var entry : tag.getList("Completed", Tag.TAG_STRING)) data.completed.add(entry.getAsString());
        data.resumePending=!data.active.isEmpty()&&data.wasRiding&&data.pilotEva!=null&&data.pilotPlug!=null;
        for(var raw:tag.getList("SortiesR32",Tag.TAG_COMPOUND))
        {
            var t=(CompoundTag)raw;int unit=t.getInt("Unit");if(unit<0||unit>4||!t.hasUUID("Commander"))continue;
            var s=new Sortie(unit,t.getUUID("Commander"),t.getBoolean("Npc"),t.getBoolean("Rifle"));
            if(t.hasUUID("Eva"))s.eva=t.getUUID("Eva");if(t.hasUUID("Plug"))s.plug=t.getUUID("Plug");
            if(t.hasUUID("ActualPilotR45"))s.pilotR45=t.getUUID("ActualPilotR45");
            s.dispatchRequested=t.getBoolean("DispatchRequestedR39");
            s.wasRiding=t.getBoolean("Riding");s.resumePending=!s.npc&&s.wasRiding&&s.eva!=null&&s.plug!=null;
            if(t.contains("Position"))s.position=BlockPos.of(t.getLong("Position"));data.sorties.put(unit,s);
        }
        if(!data.active.isEmpty()&&data.sorties.isEmpty()&&data.owner!=null)
        {
            data.assign(data.assignedVariant,data.owner,data.npcPilot,data.autoArmament);
            var s=data.sorties.get(data.assignedVariant);s.eva=data.pilotEva;s.plug=data.pilotPlug;s.wasRiding=data.wasRiding;s.resumePending=data.resumePending;s.position=data.lastPosition;
        }
        return data;
    }
    @Override public CompoundTag save(CompoundTag tag)
    {
        tag.putInt("Chapter", chapter); tag.putString("Active", active); tag.putString("Phase", phase); tag.putString("Notice", notice);
        tag.putLong("GenerationR43",generationR43);
        tag.putBoolean("TargetDeathConfirmedR45",targetDeathConfirmedR45);tag.putInt("RayPreloadCursorR45",rayPreloadCursorR45);tag.putString("EncounterSiteR45",encounterSiteR45);tag.putString("EncounterLayoutR45",encounterLayoutR45);
        tag.putString("EpisodeStateR45",episodeStateR45);tag.putString("EpisodeChapterR45",episodeChapterR45);tag.putLong("EpisodeGenerationR45",episodeGenerationR45);tag.putBoolean("EquipmentReturnedR45",equipmentReturnedR45);
        var victories=new ListTag();combatVictoriesR45.forEach(id->victories.add(StringTag.valueOf(id)));tag.put("CombatVictoriesR45",victories);
        var recoveries=new ListTag();recoveryR45.forEach((unit,receipt)->{var row=new CompoundTag();row.putInt("Unit",unit);row.putUUID("Eva",receipt.eva);row.putUUID("Pilot",receipt.pilot);row.putLong("Generation",receipt.generation);recoveries.add(row);});tag.put("OriginalRecoveryR45",recoveries);
        tag.putInt("AssignedVariant",assignedVariant);tag.putBoolean("NpcPilot",npcPilot);tag.putBoolean("AutoArmament",autoArmament);tag.putBoolean("PilotDispatchRequested",pilotDispatchRequested);tag.putLong("AlertStarted",alertStarted);tag.putInt("AlertLine",alertLine);
        if (owner != null) tag.putUUID("Owner", owner); if (angel != null) tag.putUUID("Angel", angel);
        if(pilotEva!=null)tag.putUUID("PilotEva",pilotEva);if(pilotPlug!=null)tag.putUUID("PilotPlug",pilotPlug);tag.putBoolean("WasRiding",wasRiding);
        if (lastPosition != null) tag.putLong("LastPosition", lastPosition.asLong());
        var roster=new ListTag();for(var s:sorties.values())
        {
            var t=new CompoundTag();t.putInt("Unit",s.unit);t.putUUID("Commander",s.commander);t.putBoolean("Npc",s.npc);t.putBoolean("Rifle",s.rifle);t.putBoolean("Riding",s.wasRiding);t.putBoolean("DispatchRequestedR39",s.dispatchRequested);
            if(s.eva!=null)t.putUUID("Eva",s.eva);if(s.plug!=null)t.putUUID("Plug",s.plug);if(s.position!=null)t.putLong("Position",s.position.asLong());roster.add(t);
            if(s.pilotR45!=null)t.putUUID("ActualPilotR45",s.pilotR45);
        }tag.put("SortiesR32",roster);
        var list = new ListTag(); completed.forEach(id -> list.add(StringTag.valueOf(id))); tag.put("Completed", list); return tag;
    }
    public void clear(String reason)
    { sorties.clear(); owner = null; angel = null; pilotEva=pilotPlug=null;wasRiding=resumePending=false;resumeTicks=0;active = ""; phase = "idle"; lastPosition = null; notice = reason;npcPilot=autoArmament=pilotDispatchRequested=false;alertStarted=0;alertLine=0;assignedVariant=1;rayPreloadCursorR45=missingTicksR45=0;encounterSiteR45=encounterLayoutR45="";targetDeathConfirmedR45=false;recoveryR45.clear();equipmentReturnedR45=false;episodeStateR45="";setDirty(); }
    public boolean canFinish(String id, UUID pilot, UUID target)
    {
        return phase.equals("combat")&&active.equals(id)&&owner!=null&&owner.equals(pilot)
                &&angel!=null&&angel.equals(target)&&TvCampaignCatalog.find(id).map(TvCampaignCatalog.Chapter::playable).orElse(false);
    }
    public boolean finish(String id, UUID pilot, UUID target)
    {
        if(!canFinish(id,pilot,target))return false;
        targetDeathConfirmedR45=true;phase=episodeStateR45="combat_victory";episodeChapterR45=id;episodeGenerationR45=generationR43;
        if(!combatVictoriesR45.contains(id))combatVictoriesR45.add(id);
        equipmentReturnedR45=false;recoveryR45.clear();notice="目标已击破。先把机体和装备送回机库，确认驾驶员安全返回。";setDirty();return true;
    }
    public boolean recordOriginalRecovery(UUID commander,long generation,int unit,UUID actualEva,UUID actualPilot)
    {
        var sortie=sorties.get(unit);
        if(!phase.equals("combat_victory")||owner==null||!owner.equals(commander)||generation!=generationR43||sortie==null
                ||sortie.eva==null||!sortie.eva.equals(actualEva)||sortie.pilotR45==null||!sortie.pilotR45.equals(actualPilot))return false;
        var receipt=new Recovery(actualEva,actualPilot,generation);if(!receipt.equals(recoveryR45.get(unit))){recoveryR45.put(unit,receipt);setDirty();}return true;
    }
    public void invalidateRecovery(int unit){if(recoveryR45.remove(unit)!=null)setDirty();}
    public boolean originalRecoveryRecorded(int unit)
    {
        var sortie=sorties.get(unit);var receipt=recoveryR45.get(unit);
        return sortie!=null&&receipt!=null&&receipt.generation==generationR43&&sortie.eva!=null&&sortie.eva.equals(receipt.eva)
                &&sortie.pilotR45!=null&&sortie.pilotR45.equals(receipt.pilot);
    }
    public boolean canArchiveEpisode(String id,UUID commander,long generation)
    {
        if(!phase.equals("combat_victory")||!episodeStateR45.equals("combat_victory")||!targetDeathConfirmedR45
                ||owner==null||!owner.equals(commander)||generation!=generationR43||episodeGenerationR45!=generation
                ||!active.equals(id)||!episodeChapterR45.equals(id)||!equipmentReturnedR45||sorties.isEmpty())return false;
        for(var sortie:sorties.values())
        {
            var receipt=recoveryR45.get(sortie.unit);
            if(receipt==null||receipt.generation!=generation||sortie.eva==null||!sortie.eva.equals(receipt.eva)
                    ||sortie.pilotR45==null||!sortie.pilotR45.equals(receipt.pilot))return false;
        }return true;
    }
    public boolean archiveEpisode(String id,UUID commander,long generation)
    {
        if(!canArchiveEpisode(id,commander,generation))return false;
        boolean replay=completed.contains(id);if(!replay)completed.add(id);
        while(chapter<TvCampaignCatalog.CHAPTERS.size()&&completed.contains(TvCampaignCatalog.at(chapter).id()))chapter++;
        clear(replay?"本次演习回收与装备交接已完成。":"机体、驾驶员和装备交接完成，这次行动结束了。");
        episodeStateR45=phase="episode_archived";episodeChapterR45=id;episodeGenerationR45=generation;setDirty();return true;
    }
}

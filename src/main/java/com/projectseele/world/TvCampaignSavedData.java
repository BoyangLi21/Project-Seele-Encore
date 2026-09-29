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
    public String active = "", phase = "idle", notice = "";
    public BlockPos lastPosition;
    public final List<String> completed = new ArrayList<>();
    public static final class Sortie
    {
        public int unit,resumeTicks;
        public UUID commander,eva,plug;
        public boolean npc,rifle,wasRiding,resumePending,dispatchRequested;
        public BlockPos position;
        public Sortie(int unit,UUID commander,boolean npc,boolean rifle)
        {this.unit=unit;this.commander=commander;this.npc=npc;this.rifle=rifle;}
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
        if (tag.contains("LastPosition")) data.lastPosition = BlockPos.of(tag.getLong("LastPosition"));
        for (var entry : tag.getList("Completed", Tag.TAG_STRING)) data.completed.add(entry.getAsString());
        data.resumePending=!data.active.isEmpty()&&data.wasRiding&&data.pilotEva!=null&&data.pilotPlug!=null;
        for(var raw:tag.getList("SortiesR32",Tag.TAG_COMPOUND))
        {
            var t=(CompoundTag)raw;int unit=t.getInt("Unit");if(unit<0||unit>4||!t.hasUUID("Commander"))continue;
            var s=new Sortie(unit,t.getUUID("Commander"),t.getBoolean("Npc"),t.getBoolean("Rifle"));
            if(t.hasUUID("Eva"))s.eva=t.getUUID("Eva");if(t.hasUUID("Plug"))s.plug=t.getUUID("Plug");
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
        tag.putInt("AssignedVariant",assignedVariant);tag.putBoolean("NpcPilot",npcPilot);tag.putBoolean("AutoArmament",autoArmament);tag.putBoolean("PilotDispatchRequested",pilotDispatchRequested);tag.putLong("AlertStarted",alertStarted);tag.putInt("AlertLine",alertLine);
        if (owner != null) tag.putUUID("Owner", owner); if (angel != null) tag.putUUID("Angel", angel);
        if(pilotEva!=null)tag.putUUID("PilotEva",pilotEva);if(pilotPlug!=null)tag.putUUID("PilotPlug",pilotPlug);tag.putBoolean("WasRiding",wasRiding);
        if (lastPosition != null) tag.putLong("LastPosition", lastPosition.asLong());
        var roster=new ListTag();for(var s:sorties.values())
        {
            var t=new CompoundTag();t.putInt("Unit",s.unit);t.putUUID("Commander",s.commander);t.putBoolean("Npc",s.npc);t.putBoolean("Rifle",s.rifle);t.putBoolean("Riding",s.wasRiding);t.putBoolean("DispatchRequestedR39",s.dispatchRequested);
            if(s.eva!=null)t.putUUID("Eva",s.eva);if(s.plug!=null)t.putUUID("Plug",s.plug);if(s.position!=null)t.putLong("Position",s.position.asLong());roster.add(t);
        }tag.put("SortiesR32",roster);
        var list = new ListTag(); completed.forEach(id -> list.add(StringTag.valueOf(id))); tag.put("Completed", list); return tag;
    }
    public void clear(String reason)
    { sorties.clear(); owner = null; angel = null; pilotEva=pilotPlug=null;wasRiding=resumePending=false;resumeTicks=0;active = ""; phase = "idle"; lastPosition = null; notice = reason;npcPilot=autoArmament=pilotDispatchRequested=false;alertStarted=0;alertLine=0;assignedVariant=1;setDirty(); }
    public boolean finish(String id, UUID pilot, UUID target)
    {
        if (!active.equals(id) || owner == null || !owner.equals(pilot) || angel == null || !angel.equals(target)
                || !TvCampaignCatalog.find(id).map(TvCampaignCatalog.Chapter::playable).orElse(false)) return false;
        boolean replay=completed.contains(id);if(!replay)completed.add(id);
        while(chapter<TvCampaignCatalog.CHAPTERS.size()&&completed.contains(TvCampaignCatalog.at(chapter).id()))chapter++;
        clear(replay?"本次演习已结束。可以回收机体，或重新选择已制作的作战。":"作战记录已归档。可以回收机体，并选择下一次作战。");return true;
    }
}

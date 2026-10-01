package com.projectseele.world;

import net.minecraft.nbt.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.saveddata.SavedData;
import java.util.*;

/** An original preparation dossier, separate from TV chapter completion and combat authority. */
public final class CityCoordinationSavedDataR44 extends SavedData
{
    public UUID instance,owner;
    public int stage,evidence,knowledge,chargeTicks,fieldSamples;
    public boolean active,tested,isolating,restoring,cityRequested,fieldSampling,fieldSamplePassed;
    public long operationAt,fieldStartedAt;
    public String priority="",supply="",method="",notice="";
    public final Map<Integer,String> formation=new LinkedHashMap<>();
    public final Set<Integer> confirmed=new LinkedHashSet<>();
    public final Set<String> acquired=new LinkedHashSet<>();
    private final ListTag archives=new ListTag();
    private CompoundTag inherited=new CompoundTag();

    public static CityCoordinationSavedDataR44 get(ServerLevel level)
    {return level.getDataStorage().computeIfAbsent(CityCoordinationSavedDataR44::load,CityCoordinationSavedDataR44::new,"projectseele_city_coordination_r44");}
    public void begin(UUID commander)
    {
        instance=UUID.randomUUID();owner=commander;active=true;stage=1;evidence=knowledge=chargeTicks=0;
        tested=isolating=restoring=cityRequested=fieldSampling=fieldSamplePassed=false;
        operationAt=fieldStartedAt=0;fieldSamples=0;priority=supply=method="";formation.clear();confirmed.clear();
        notice="核对原页、译注和现场记录后，再决定供电与驾驶员编成。";setDirty();
    }
    public void archive()
    {
        var entry=new CompoundTag();entry.putUUID("Instance",instance);entry.putUUID("Commander",owner);
        entry.putInt("Evidence",evidence);entry.putInt("KnowledgeShared",knowledge);entry.putString("Priority",priority);
        entry.putString("Supply",supply);entry.putString("Method",method);entry.putBoolean("Tested",tested);
        entry.putBoolean("FieldSamplePassed",fieldSamplePassed);entry.putInt("FieldSamples",fieldSamples);
        entry.put("Formation",formationTag());entry.putIntArray("Confirmed",confirmed.stream().mapToInt(Integer::intValue).toArray());archives.add(entry);
        active=false;stage=7;restoring=true;notice="供电检查和编成已归档，机体保持待命。屋岛作战的射击条件仍待确认。";setDirty();
    }
    public int archiveCount(){return archives.size();}
    private ListTag formationTag()
    {
        var roster=new ListTag();formation.forEach((unit,pilot)->{var row=new CompoundTag();row.putInt("Unit",unit);row.putString("Pilot",pilot);roster.add(row);});return roster;
    }
    public static CityCoordinationSavedDataR44 load(CompoundTag tag)
    {
        var data=new CityCoordinationSavedDataR44();data.inherited=tag.copy();
        if(tag.hasUUID("Instance"))data.instance=tag.getUUID("Instance");if(tag.hasUUID("Owner"))data.owner=tag.getUUID("Owner");
        data.active=tag.getBoolean("Active");data.stage=tag.getInt("Stage");data.evidence=tag.getInt("Evidence");data.knowledge=tag.getInt("Knowledge");
        data.tested=tag.getBoolean("Tested");data.isolating=tag.getBoolean("Isolating");data.restoring=tag.getBoolean("Restoring");
        data.cityRequested=tag.getBoolean("CityRequested");data.operationAt=tag.getLong("OperationAt");data.chargeTicks=tag.getInt("ChargeTicks");
        data.fieldSampling=tag.getBoolean("FieldSampling");data.fieldSamplePassed=tag.getBoolean("FieldSamplePassed");
        data.fieldStartedAt=tag.getLong("FieldStartedAt");data.fieldSamples=tag.getInt("FieldSamples");
        data.priority=tag.getString("Priority");data.supply=tag.getString("Supply");data.method=tag.getString("Method");data.notice=tag.getString("Notice");
        for(var raw:tag.getList("Formation",Tag.TAG_COMPOUND)){var row=(CompoundTag)raw;int unit=row.getInt("Unit");if(unit>=0&&unit<=4)data.formation.put(unit,row.getString("Pilot"));}
        for(int unit:tag.getIntArray("Confirmed"))if(data.formation.containsKey(unit))data.confirmed.add(unit);
        for(var raw:tag.getList("Acquired",Tag.TAG_STRING))data.acquired.add(raw.getAsString());
        data.archives.addAll(tag.getList("Archives",Tag.TAG_COMPOUND).copy());
        if(data.active&&(data.instance==null||data.owner==null)){data.active=false;data.restoring=true;data.notice="档案缺少指令归属，已停止后续操作。";}
        return data;
    }
    @Override public CompoundTag save(CompoundTag tag)
    {
        tag.merge(inherited.copy());if(instance!=null)tag.putUUID("Instance",instance);if(owner!=null)tag.putUUID("Owner",owner);
        tag.putInt("Version",1);tag.putBoolean("Active",active);tag.putInt("Stage",stage);tag.putInt("Evidence",evidence);tag.putInt("Knowledge",knowledge);
        tag.putBoolean("Tested",tested);tag.putBoolean("Isolating",isolating);tag.putBoolean("Restoring",restoring);tag.putBoolean("CityRequested",cityRequested);
        tag.putLong("OperationAt",operationAt);tag.putInt("ChargeTicks",chargeTicks);tag.putString("Priority",priority);tag.putString("Supply",supply);
        tag.putBoolean("FieldSampling",fieldSampling);tag.putBoolean("FieldSamplePassed",fieldSamplePassed);
        tag.putLong("FieldStartedAt",fieldStartedAt);tag.putInt("FieldSamples",fieldSamples);
        tag.putString("Method",method);tag.putString("Notice",notice);tag.put("Formation",formationTag());
        tag.putIntArray("Confirmed",confirmed.stream().mapToInt(Integer::intValue).toArray());
        var evidenceList=new ListTag();acquired.forEach(id->evidenceList.add(StringTag.valueOf(id)));tag.put("Acquired",evidenceList);tag.put("Archives",archives.copy());return tag;
    }
}

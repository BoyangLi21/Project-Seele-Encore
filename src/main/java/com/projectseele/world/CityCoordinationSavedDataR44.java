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
    public long formationRevisionR45=1,evidenceRevisionR45=1;
    public record Binding(int unit,String kind,String role,UUID pilot,UUID eva){}
    public record Confirmation(UUID instance,Binding binding,long formationRevision,long evidenceRevision,UUID actor){}
    public record Reading(UUID instance,UUID reader,String document,String revision,String source,long at){}
    private final Map<Integer,Binding> bindingsR45=new LinkedHashMap<>();
    private final Map<Integer,Confirmation> confirmationsR45=new LinkedHashMap<>();
    private final Map<String,Reading> readingsR45=new LinkedHashMap<>();
    public final Set<String> requiredArchivePagesR45=new LinkedHashSet<>();
    public String requiredArchiveRevisionR45="";
    private final ListTag quarantinedParticipantsR45=new ListTag();
    private final ListTag archives=new ListTag();
    private CompoundTag inherited=new CompoundTag();

    public static CityCoordinationSavedDataR44 get(ServerLevel level)
    {return level.getDataStorage().computeIfAbsent(CityCoordinationSavedDataR44::load,CityCoordinationSavedDataR44::new,"projectseele_city_coordination_r44");}
    public void begin(UUID commander)
    {
        instance=UUID.randomUUID();owner=commander;active=true;stage=1;evidence=knowledge=chargeTicks=0;
        tested=isolating=restoring=cityRequested=fieldSampling=fieldSamplePassed=false;
        operationAt=fieldStartedAt=0;fieldSamples=0;priority=supply=method="";formation.clear();confirmed.clear();
        formationRevisionR45=evidenceRevisionR45=1;bindingsR45.clear();confirmationsR45.clear();readingsR45.clear();
        requiredArchivePagesR45.clear();requiredArchiveRevisionR45="";
        notice="核对原页、译注和现场记录后，再决定供电与驾驶员编成。";setDirty();
    }
    public void archive()
    {
        if(!active||stage!=6||!tested||supply.isEmpty()||!allConfirmed())return;
        var entry=new CompoundTag();entry.putUUID("Instance",instance);entry.putUUID("Commander",owner);
        entry.putInt("Evidence",evidence);entry.putInt("KnowledgeShared",knowledge);entry.putString("Priority",priority);
        entry.putString("Supply",supply);entry.putString("Method",method);entry.putBoolean("Tested",tested);
        entry.putBoolean("FieldSamplePassed",fieldSamplePassed);entry.putInt("FieldSamples",fieldSamples);
        entry.put("Formation",formationTag());entry.putIntArray("Confirmed",confirmed.stream().mapToInt(Integer::intValue).toArray());archives.add(entry);
        entry.putLong("FormationRevisionR45",formationRevisionR45);entry.putLong("EvidenceRevisionR45",evidenceRevisionR45);
        entry.put("ParticipantBindingsR45",bindingsTag());entry.put("ParticipantConfirmationsR45",confirmationsTag());entry.put("ReadReceiptsR45",readingsTag());
        active=false;stage=7;restoring=true;notice="供电检查和编成已归档，机体保持待命。屋岛作战的射击条件仍待确认。";setDirty();
    }
    public int archiveCount(){return archives.size();}
    public static String roleFor(int unit){return unit==0?"cover":unit==1?"shooter":"support";}
    private static boolean valid(Binding binding)
    {return binding!=null&&binding.unit>=0&&binding.unit<=4&&Set.of("npc","human").contains(binding.kind)
            &&(!binding.kind.equals("npc")||binding.unit<=2)&&roleFor(binding.unit).equals(binding.role)&&binding.pilot!=null&&binding.eva!=null;}
    public Binding binding(int unit){return bindingsR45.get(unit);}
    public boolean bind(UUID expected,Binding binding)
    {
        if(!active||expected==null||!expected.equals(instance)||!valid(binding))return false;
        for(var other:bindingsR45.values())if(other.unit!=binding.unit&&other.pilot.equals(binding.pilot))return false;
        if(binding.equals(bindingsR45.get(binding.unit)))return true;
        bindingsR45.put(binding.unit,binding);formation.put(binding.unit,binding.kind);
        formationRevisionR45++;confirmationsR45.clear();confirmed.clear();if(stage==6)stage=5;setDirty();return true;
    }
    public boolean withdraw(UUID expected,int unit,UUID actualActor)
    {
        var binding=bindingsR45.get(unit);
        if(!active||expected==null||!expected.equals(instance)||binding==null||actualActor==null
                ||!actualActor.equals(owner)&&!actualActor.equals(binding.pilot))return false;
        bindingsR45.remove(unit);formation.remove(unit);formationRevisionR45++;confirmationsR45.clear();confirmed.clear();stage=5;setDirty();return true;
    }
    public void changeKnowledge(int next)
    {
        if(next!=knowledge){knowledge=next;evidenceRevisionR45++;confirmationsR45.clear();confirmed.clear();if(stage==6)stage=5;}
        setDirty();
    }
    public boolean confirm(UUID expected,Binding actual,long formationRevision,long evidenceRevision,UUID actor)
    {
        if(!active||expected==null||!expected.equals(instance)||!valid(actual)||!actual.equals(bindingsR45.get(actual.unit))
                ||formationRevision!=formationRevisionR45||evidenceRevision!=evidenceRevisionR45
                ||actor==null||!actor.equals(actual.pilot)||evidence!=7||!dossierReadCurrent(owner)||actual.kind.equals("npc")&&knowledge!=7
                ||actual.kind.equals("human")&&!dossierReadCurrent(actor)
                ||(stage!=5&&stage!=6)||!requiredReadingComplete())return false;
        confirmationsR45.put(actual.unit,new Confirmation(instance,actual,formationRevision,evidenceRevision,actor));
        refreshConfirmed();if(allConfirmed())stage=6;setDirty();return true;
    }
    public boolean confirmationCurrent(int unit)
    {
        var binding=bindingsR45.get(unit);var receipt=confirmationsR45.get(unit);
        return valid(binding)&&receipt!=null&&instance!=null&&instance.equals(receipt.instance)&&binding.equals(receipt.binding)
                &&receipt.formationRevision==formationRevisionR45&&receipt.evidenceRevision==evidenceRevisionR45
                &&binding.pilot.equals(receipt.actor)&&dossierReadCurrent(owner)
                &&(binding.kind.equals("npc")?knowledge==7:dossierReadCurrent(binding.pilot));
    }
    private void refreshConfirmed(){confirmed.clear();for(int unit:formation.keySet())if(confirmationCurrent(unit))confirmed.add(unit);}
    public boolean allConfirmed()
    {return evidence==7&&dossierReadCurrent(owner)&&!formation.isEmpty()&&formation.keySet().stream().allMatch(this::confirmationCurrent)&&requiredReadingComplete();}
    /** Called only after trusted server delivery or a challenged physical-book read event. */
    public boolean recordReading(UUID expected,UUID reader,String document,String revision,String source,long at)
    {
        if(!active||expected==null||!expected.equals(instance)||reader==null||document==null||!document.matches("[a-z0-9_/.-]{1,96}")
                ||revision==null||!revision.matches("[0-9a-f]{64}")||!Set.of("command_dossier","physical_archive").contains(source))return false;
        var previous=readingsR45.get(reader+"|"+document);
        var receipt=new Reading(instance,reader,document,revision,source,at);readingsR45.put(reader+"|"+document,receipt);
        acquired.add(document+"@"+revision);if(reader.equals(owner)&&source.equals("command_dossier"))
        {
            int bit=switch(document){case "r44/page"->1;case "r44/annotation"->2;case "r44/field"->4;default->0;};
            if(bit!=0&&((evidence&bit)==0||previous==null||!previous.revision.equals(revision)))
            {evidence|=bit;evidenceRevisionR45++;confirmationsR45.clear();confirmed.clear();if(stage==6)stage=5;}
        }
        setDirty();return true;
    }
    public boolean dossierReadCurrent(UUID reader)
    {
        for(String id:List.of("r44/page","r44/annotation","r44/field"))
        {
            var master=readingsR45.get(owner+"|"+id);var own=readingsR45.get(reader+"|"+id);
            if(master==null||own==null||instance==null||!instance.equals(master.instance)||!instance.equals(own.instance)
                    ||!owner.equals(master.reader)||!reader.equals(own.reader)||!master.revision.equals(own.revision)
                    ||!master.source.equals("command_dossier")||!own.source.equals("command_dossier"))return false;
        }return true;
    }
    public boolean requiredReadingComplete()
    {
        for(String id:requiredArchivePagesR45)
        {
            var receipt=readingsR45.get(owner+"|"+id);
            if(receipt==null||!receipt.instance.equals(instance)||!receipt.revision.equals(requiredArchiveRevisionR45)
                    ||!receipt.source.equals("physical_archive"))return false;
        }
        return true;
    }
    private static CompoundTag bindingTag(Binding binding)
    {
        var row=new CompoundTag();row.putInt("Unit",binding.unit);row.putString("Kind",binding.kind);row.putString("Role",binding.role);
        row.putUUID("Pilot",binding.pilot);row.putUUID("Eva",binding.eva);return row;
    }
    private static Binding bindingFrom(CompoundTag row)
    {return row.hasUUID("Pilot")&&row.hasUUID("Eva")?new Binding(row.getInt("Unit"),row.getString("Kind"),row.getString("Role"),row.getUUID("Pilot"),row.getUUID("Eva")):null;}
    private ListTag bindingsTag(){var list=new ListTag();for(var binding:bindingsR45.values())list.add(bindingTag(binding));return list;}
    private ListTag confirmationsTag()
    {
        var list=new ListTag();for(var receipt:confirmationsR45.values())
        {
            var row=bindingTag(receipt.binding);row.putUUID("Instance",receipt.instance);row.putUUID("Actor",receipt.actor);
            row.putLong("FormationRevision",receipt.formationRevision);row.putLong("EvidenceRevision",receipt.evidenceRevision);list.add(row);
        }return list;
    }
    private ListTag readingsTag()
    {
        var list=new ListTag();for(var receipt:readingsR45.values())
        {
            var row=new CompoundTag();row.putUUID("Instance",receipt.instance);row.putUUID("Reader",receipt.reader);
            row.putString("Document",receipt.document);row.putString("Revision",receipt.revision);row.putString("Source",receipt.source);row.putLong("At",receipt.at);list.add(row);
        }return list;
    }
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
        data.formationRevisionR45=Math.max(1,tag.getLong("FormationRevisionR45"));data.evidenceRevisionR45=Math.max(1,tag.getLong("EvidenceRevisionR45"));
        for(var raw:tag.getList("ParticipantBindingsR45",Tag.TAG_COMPOUND))
        {
            var row=(CompoundTag)raw;var binding=bindingFrom(row);
            if(!valid(binding)||!binding.kind.equals(data.formation.get(binding.unit))
                    ||data.bindingsR45.values().stream().anyMatch(other->other.unit!=binding.unit&&other.pilot.equals(binding.pilot))
                    ||data.bindingsR45.putIfAbsent(binding.unit,binding)!=null)
                data.quarantinedParticipantsR45.add(row.copy());
        }
        for(var raw:tag.getList("ParticipantConfirmationsR45",Tag.TAG_COMPOUND))
        {
            var row=(CompoundTag)raw;var binding=bindingFrom(row);
            if(!valid(binding)||!row.hasUUID("Instance")||!row.hasUUID("Actor")){data.quarantinedParticipantsR45.add(row.copy());continue;}
            var receipt=new Confirmation(row.getUUID("Instance"),binding,row.getLong("FormationRevision"),row.getLong("EvidenceRevision"),row.getUUID("Actor"));
            if(data.confirmationsR45.putIfAbsent(binding.unit,receipt)!=null)data.quarantinedParticipantsR45.add(row.copy());
        }
        for(var raw:tag.getList("ReadReceiptsR45",Tag.TAG_COMPOUND))
        {
            var row=(CompoundTag)raw;
            if(!row.hasUUID("Instance")||!row.hasUUID("Reader")||!row.getString("Document").matches("[a-z0-9_/.-]{1,96}")
                    ||!row.getString("Revision").matches("[0-9a-f]{64}")||!Set.of("command_dossier","physical_archive").contains(row.getString("Source")))
            {data.quarantinedParticipantsR45.add(row.copy());continue;}
            var receipt=new Reading(row.getUUID("Instance"),row.getUUID("Reader"),row.getString("Document"),row.getString("Revision"),row.getString("Source"),row.getLong("At"));
            if(data.readingsR45.putIfAbsent(receipt.reader+"|"+receipt.document,receipt)!=null)data.quarantinedParticipantsR45.add(row.copy());
        }
        for(var raw:tag.getList("RequiredArchivePagesR45",Tag.TAG_STRING))data.requiredArchivePagesR45.add(raw.getAsString());
        data.requiredArchiveRevisionR45=tag.getString("RequiredArchiveRevisionR45");
        data.quarantinedParticipantsR45.addAll(tag.getList("QuarantinedParticipantsR45",Tag.TAG_COMPOUND).copy());
        data.refreshConfirmed();
        if(tag.getInt("Version")<2&&tag.getIntArray("Confirmed").length>0)
            data.inherited.putIntArray("LegacyUnboundConfirmedR45",tag.getIntArray("Confirmed"));
        if(data.active&&data.stage==6&&!data.allConfirmed())
        {data.stage=5;data.notice="旧编成确认缺少本人或原机体绑定，请重新确认。原档案记录保留。";}
        for(var raw:tag.getList("Acquired",Tag.TAG_STRING))data.acquired.add(raw.getAsString());
        data.archives.addAll(tag.getList("Archives",Tag.TAG_COMPOUND).copy());
        if(data.active&&(data.instance==null||data.owner==null)){data.active=false;data.restoring=true;data.notice="档案缺少指令归属，已停止后续操作。";}
        return data;
    }
    @Override public CompoundTag save(CompoundTag tag)
    {
        tag.merge(inherited.copy());if(instance!=null)tag.putUUID("Instance",instance);if(owner!=null)tag.putUUID("Owner",owner);
        tag.putInt("Version",2);tag.putBoolean("Active",active);tag.putInt("Stage",stage);tag.putInt("Evidence",evidence);tag.putInt("Knowledge",knowledge);
        tag.putBoolean("Tested",tested);tag.putBoolean("Isolating",isolating);tag.putBoolean("Restoring",restoring);tag.putBoolean("CityRequested",cityRequested);
        tag.putLong("OperationAt",operationAt);tag.putInt("ChargeTicks",chargeTicks);tag.putString("Priority",priority);tag.putString("Supply",supply);
        tag.putBoolean("FieldSampling",fieldSampling);tag.putBoolean("FieldSamplePassed",fieldSamplePassed);
        tag.putLong("FieldStartedAt",fieldStartedAt);tag.putInt("FieldSamples",fieldSamples);
        tag.putString("Method",method);tag.putString("Notice",notice);tag.put("Formation",formationTag());
        tag.putIntArray("Confirmed",confirmed.stream().mapToInt(Integer::intValue).toArray());
        tag.putLong("FormationRevisionR45",formationRevisionR45);tag.putLong("EvidenceRevisionR45",evidenceRevisionR45);
        tag.put("ParticipantBindingsR45",bindingsTag());tag.put("ParticipantConfirmationsR45",confirmationsTag());tag.put("ReadReceiptsR45",readingsTag());
        var required=new ListTag();requiredArchivePagesR45.forEach(id->required.add(StringTag.valueOf(id)));tag.put("RequiredArchivePagesR45",required);
        tag.putString("RequiredArchiveRevisionR45",requiredArchiveRevisionR45);tag.put("QuarantinedParticipantsR45",quarantinedParticipantsR45.copy());
        var evidenceList=new ListTag();acquired.forEach(id->evidenceList.add(StringTag.valueOf(id)));tag.put("Acquired",evidenceList);tag.put("Archives",archives.copy());return tag;
    }
}

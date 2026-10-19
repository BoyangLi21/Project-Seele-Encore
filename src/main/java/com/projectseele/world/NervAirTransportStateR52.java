package com.projectseele.world;

import java.util.*;
import net.minecraft.nbt.*;
import net.minecraft.world.level.saveddata.SavedData;
import com.projectseele.world.NervRouteReservationsR52.Original;
import com.projectseele.world.TransportMembershipR52.Kind;

/** One durable task per original aircraft, with no backup-spawn/rebase path. */
public final class NervAirTransportStateR52 extends SavedData
{
    public static final String NAME="projectseele_nerv_air_transport_r52";
    public enum Phase { PREPARE,TAKEOFF,FERRY,APPROACH,CLAMP,ASCEND,STOW,CRUISE,UNSTOW,DESCEND,HANDOFF,RELEASE,RETREAT,RETURN,LAND,HOLD,COMPLETE,CANCELLED }
    public record Job(UUID task,UUID aircraft,Original original,Kind kind,String manifestFingerprint,
                      String itinerary,String receiver,int leg,int age,Phase phase,Phase heldPhase,
                      boolean carrying,boolean payloadTransferred,boolean cancelRequested,
                      Set<String> spaces,Set<String> mechanisms,CompoundTag ownerData,String waiting)
    {
        public Job
        {
            Objects.requireNonNull(task);Objects.requireNonNull(aircraft);Objects.requireNonNull(original);Objects.requireNonNull(kind);
            Objects.requireNonNull(manifestFingerprint);Objects.requireNonNull(itinerary);Objects.requireNonNull(receiver);Objects.requireNonNull(phase);Objects.requireNonNull(heldPhase);Objects.requireNonNull(waiting);
            if(List.of(original.eva(),original.plug(),original.pilot()).contains(aircraft)||leg<0||age<0
                    ||!manifestFingerprint.matches("[0-9a-f]{64}")||payloadTransferred&&carrying)throw new IllegalArgumentException("Incompatible original flight state");
            spaces=Set.copyOf(spaces);mechanisms=Set.copyOf(mechanisms);ownerData=ownerData.copy();
        }
        @Override public CompoundTag ownerData(){return ownerData.copy();}
        public boolean hasStatusReport(){return ownerData.contains("ReportAtR53");}
        public long lastStatusReportTime(){return ownerData.getLong("ReportAtR53");}
        public String lastStatusReportNote(){return ownerData.getString("ReportNoteR53");}
        public boolean active(){return phase!=Phase.COMPLETE&&phase!=Phase.CANCELLED;}
        public Job update(int nextLeg,int nextAge,Phase nextPhase,boolean attached,boolean transferred,Set<String> newSpaces,Set<String> newMechanisms,CompoundTag data,String note)
        {return new Job(task,aircraft,original,kind,manifestFingerprint,itinerary,receiver,nextLeg,nextAge,nextPhase,nextPhase==Phase.HOLD?heldPhase:nextPhase,attached,transferred,cancelRequested,newSpaces,newMechanisms,data,note);}
        public Job hold(String reason)
        {return new Job(task,aircraft,original,kind,manifestFingerprint,itinerary,receiver,leg,age,Phase.HOLD,phase==Phase.HOLD?heldPhase:phase,carrying,payloadTransferred,cancelRequested,spaces,mechanisms,ownerData,reason);}
        public Job requestCancel()
        {return new Job(task,aircraft,original,kind,manifestFingerprint,itinerary,receiver,leg,age,phase,heldPhase,carrying,payloadTransferred,true,spaces,mechanisms,ownerData,waiting);}
    }
    private CompoundTag extra=new CompoundTag();
    private final Map<UUID,Job> jobs=new LinkedHashMap<>();
    private final Map<UUID,CompoundTag> jobExtras=new HashMap<>();
    private long epoch;private String directoryFingerprint="",manifestFingerprint="",fault="";
    public static NervAirTransportStateR52 load(CompoundTag tag)
    {
        var state=new NervAirTransportStateR52();state.extra=tag.copy();
        try
        {
            if(tag.contains("Version")&&tag.getInt("Version")!=52)throw new IllegalArgumentException("Unsupported flight save version");
            state.epoch=tag.getLong("Epoch");state.directoryFingerprint=tag.getString("DirectoryFingerprint");state.manifestFingerprint=tag.getString("ManifestFingerprint");
            for(var value:tag.getList("Jobs",Tag.TAG_COMPOUND))
            {
                var n=(CompoundTag)value;var o=n.getCompound("Original");
                var original=new Original(o.getLong("Epoch"),o.getInt("Variant"),o.getUUID("Eva"),o.getUUID("Plug"),o.getUUID("Pilot"),o.getUUID("Owner"),o.getString("Mission"),o.getString("Dimension"));
                var phase=Phase.valueOf(n.getString("Phase"));
                var job=new Job(n.getUUID("Task"),n.getUUID("Aircraft"),original,Kind.valueOf(n.getString("Kind")),n.getString("ManifestFingerprint"),n.getString("Itinerary"),n.getString("Receiver"),n.getInt("Leg"),n.getInt("Age"),phase,
                        Phase.valueOf(n.getString("HeldPhase")),n.getBoolean("Carrying"),n.getBoolean("PayloadTransferred"),n.getBoolean("CancelRequested"),strings(n,"Spaces"),strings(n,"Mechanisms"),n.getCompound("OwnerData"),n.getString("Waiting"));
                state.validate(job);if(state.jobs.putIfAbsent(job.task(),job)!=null)throw new IllegalArgumentException("Duplicate original flight task");state.jobExtras.put(job.task(),n.copy());
            }
        }
        catch(RuntimeException malformed){state.fault="Flight save held: "+malformed.getMessage();state.jobs.clear();}
        return state;
    }
    public String fault(){return fault;}
    public long epoch(){return epoch;}
    public String directoryFingerprint(){return directoryFingerprint;}
    public String manifestFingerprint(){return manifestFingerprint;}
    public List<Job> jobs(){return List.copyOf(jobs.values());}
    public Job job(UUID task){return jobs.get(task);}
    public Job aircraft(UUID aircraft){return jobs.values().stream().filter(j->j.active()&&j.aircraft().equals(aircraft)).findFirst().orElse(null);}
    public Job payload(UUID eva){return jobs.values().stream().filter(j->j.active()&&!j.payloadTransferred()&&j.original().eva().equals(eva)).findFirst().orElse(null);}
    public void bind(long newEpoch,String directory,String manifest)
    {
        if(!fault.isEmpty())throw new IllegalStateException(fault);
        if(newEpoch<=0||!directory.matches("[0-9a-f]{64}")||!manifest.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Explicit matching Root flight receipt required");
        if(jobs.values().stream().anyMatch(Job::active)&&(epoch!=newEpoch||!directoryFingerprint.equals(directory)||!manifestFingerprint.equals(manifest)))throw new IllegalStateException("Active original flights cannot change directory/epoch/manifest");
        epoch=newEpoch;directoryFingerprint=directory;manifestFingerprint=manifest;setDirty();
    }
    private void validate(Job job)
    {
        if(!job.active())return;
        if(job.original().epoch()!=epoch||job.original().epoch()<=0||job.original().variant()<0||job.original().variant()>2
                ||!job.manifestFingerprint().equals(manifestFingerprint))throw new IllegalArgumentException("Saved original flight context changed");
        for(var existing:jobs.values())if(existing.active()&&!existing.task().equals(job.task()))
        {
            if(existing.aircraft().equals(job.aircraft()))throw new IllegalArgumentException("Original aircraft has two tasks");
            if(!existing.payloadTransferred()&&!job.payloadTransferred()&&existing.original().eva().equals(job.original().eva()))throw new IllegalArgumentException("Original EVA has two flight owners");
        }
    }
    public void put(Job job){if(!fault.isEmpty())throw new IllegalStateException(fault);validate(job);jobs.put(job.task(),job);setDirty();}
    @Override public CompoundTag save(CompoundTag ignored)
    {
        var tag=extra.copy();if(!fault.isEmpty())return tag;
        tag.putInt("Version",52);tag.putLong("Epoch",epoch);tag.putString("DirectoryFingerprint",directoryFingerprint);tag.putString("ManifestFingerprint",manifestFingerprint);
        var list=new ListTag();
        for(var j:jobs.values())
        {
            var n=jobExtras.getOrDefault(j.task(),new CompoundTag()).copy();var o=n.getCompound("Original").copy();var original=j.original();
            o.putLong("Epoch",original.epoch());o.putInt("Variant",original.variant());o.putUUID("Eva",original.eva());o.putUUID("Plug",original.plug());o.putUUID("Pilot",original.pilot());o.putUUID("Owner",original.owner());o.putString("Mission",original.mission());o.putString("Dimension",original.dimension());n.put("Original",o);
            n.putUUID("Task",j.task());n.putUUID("Aircraft",j.aircraft());n.putString("Kind",j.kind().name());n.putString("ManifestFingerprint",j.manifestFingerprint());n.putString("Itinerary",j.itinerary());n.putString("Receiver",j.receiver());n.putInt("Leg",j.leg());n.putInt("Age",j.age());n.putString("Phase",j.phase().name());n.putString("HeldPhase",j.heldPhase().name());n.putBoolean("Carrying",j.carrying());n.putBoolean("PayloadTransferred",j.payloadTransferred());n.putBoolean("CancelRequested",j.cancelRequested());n.put("Spaces",strings(j.spaces()));n.put("Mechanisms",strings(j.mechanisms()));n.put("OwnerData",j.ownerData());n.putString("Waiting",j.waiting());list.add(n);
        }
        tag.put("Jobs",list);return tag;
    }
    private static Set<String> strings(CompoundTag tag,String key){var result=new HashSet<String>();for(var s:tag.getList(key,Tag.TAG_STRING))if(!result.add(s.getAsString()))throw new IllegalArgumentException("Duplicate flight resource");return Set.copyOf(result);}
    private static ListTag strings(Set<String> values){var list=new ListTag();values.stream().sorted().forEach(s->list.add(StringTag.valueOf(s)));return list;}
}

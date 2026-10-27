package com.projectseele.world;

import java.util.*;
import net.minecraft.nbt.*;
import net.minecraft.world.level.saveddata.SavedData;
import com.projectseele.world.NervRouteReservationsR52.*;

/** Persisted real runtime lifecycle. A claimed interrupted world never falls back to old coordinates. */
public final class NervRouteRuntimeStateR52 extends SavedData
{
    public static final String NAME="projectseele_nerv_routes_r52";
    public enum Phase { PREPARING,READY,DEPARTING,DEPLOYED,RETURNING,FINISHING,PARKED,CANCELLED }
    public record Job(Snapshot snapshot,Phase phase,CompoundTag ownerData,String waiting)
    {
        public Job{Objects.requireNonNull(snapshot);Objects.requireNonNull(phase);ownerData=ownerData.copy();waiting=waiting==null?"":waiting;}
        public Job update(Snapshot snapshot,Phase phase,CompoundTag data,String reason){return new Job(snapshot,phase,data,reason);}
    }
    private boolean claimed;
    private long epoch;
    private String fingerprint="",fault="",personnelLiftManifest="",installationBundle="",installationBundleSHA="",uprightGuideSourceSHA="";
    public record PendingInstallationR52(String bundle,String sha,long epoch,String directory,boolean restoring)
    {
        public PendingInstallationR52
        {
            bundle=relativeBundleR52(bundle);
            if(sha==null||!sha.matches("[0-9a-f]{64}")||epoch<=0||directory==null||!directory.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Exact pending bundle SHA, epoch and directory required");
        }
    }
    private PendingInstallationR52 pendingInstallation;
    private String pendingInstallationHold="";
    private String pendingInstallationPreviousHold="";
    private int pendingInstallationAttempts;
    private boolean pendingInstallationPaused;
    private boolean pendingCarrierEquipmentUpdate;
    private CompoundTag pendingBankCurbRefit=new CompoundTag();
    private final Map<UUID,Long> installationActorChunks=new LinkedHashMap<>();
    private final Map<Integer,Job> jobs=new LinkedHashMap<>();
    public boolean claimed(){return claimed;}
    public long epoch(){return epoch;}
    public String fingerprint(){return fingerprint;}
    public String fault(){return fault;}
    /** Only this post-move readback failure has a recoverable physical window. */
    Job interruptedContinuousCommitR53()
    {
        for(var job:jobs.values())
            if(fault.equals("Continuous final commit/readback fault at task "+job.snapshot().task()+": Committed continuous assembly final readback failed"))return job;
        return null;
    }
    synchronized boolean recoverContinuousCommitR53(String expectedFault,Job expected,Job recovered,
                                                     java.util.function.BooleanSupplier commitPool)
    {
        if(!fault.equals(expectedFault)||jobs.get(expected.snapshot().original().variant())!=expected
                ||interruptedContinuousCommitR53()!=expected)return false;
        var from=expected.snapshot();var to=recovered.snapshot();
        if(!from.task().equals(to.task())||!from.original().equals(to.original())||from.kind()!=to.kind()
                ||!from.route().equals(to.route())||!from.directoryFingerprint().equals(to.directoryFingerprint())
                ||epoch!=to.original().epoch()||!fingerprint.equals(to.directoryFingerprint())
                ||!allowed(expected.phase(),recovered.phase()))return false;
        if(!commitPool.getAsBoolean())return false;
        jobs.put(to.original().variant(),recovered);fault="";setDirty();return true;
    }
    void faultR52(String reason){if(reason==null||reason.isBlank())throw new IllegalArgumentException("Actual runtime fault required");fault=reason;setDirty();}
    public String personnelLiftManifest(){return personnelLiftManifest;}
    public String installationBundle(){return installationBundle;}
    public String installationBundleSHA(){return installationBundleSHA;}
    public PendingInstallationR52 pendingInstallationR52(){return pendingInstallation;}
    public String pendingInstallationHoldR52(){return pendingInstallationHold;}
    public String pendingInstallationPreviousHoldR52(){return pendingInstallationPreviousHold;}
    public int pendingInstallationAttemptsR52(){return pendingInstallationAttempts;}
    public boolean pendingInstallationPausedR52(){return pendingInstallationPaused;}
    boolean pendingCarrierEquipmentUpdateR53(){return pendingCarrierEquipmentUpdate;}
    void queueCarrierEquipmentUpdateR53(PendingInstallationR52 request)
    {
        if(pendingInstallation!=null||jobs.size()!=3||jobs.values().stream().anyMatch(j->j.phase()!=Phase.PARKED||!j.waiting().isEmpty()))
            throw new IllegalStateException("Equipment update requires the three retained parked jobs and no pending installation");
        pendingCarrierEquipmentUpdate=true;
        try{queueInstallationR52(request);}catch(RuntimeException failure){pendingCarrierEquipmentUpdate=false;throw failure;}
    }
    void queueCarrierEquipmentUpdateR53(PendingInstallationR52 request,CarrierEquipmentUpdateR53.StoppedBankRefit proof)
    {
        if(pendingInstallation!=null||proof==null||!proof.current(this))throw new IllegalStateException("Exact same-tick stopped bank equipment admission required");
        pendingBankCurbRefit=proof.persistence();
        pendingCarrierEquipmentUpdate=true;
        try{queueInstallationR52(request);}catch(RuntimeException failure){pendingCarrierEquipmentUpdate=false;pendingBankCurbRefit=new CompoundTag();throw failure;}
    }
    CompoundTag pendingBankCurbRefitR53(){return pendingBankCurbRefit.copy();}
    boolean pendingBankCurbCurrentR53()
    {
        var tag=pendingBankCurbRefit;
        if(!pendingCarrierEquipmentUpdate||tag.getInt("Version")!=2||!tag.getString("Source").equals(NervLegacyBankClearanceR53.SOURCE_SHA)||!tag.hasUUID("Carrier")||jobs.size()!=3)return false;
        int variant=tag.getInt("Variant");if(!tag.contains("Variant")||variant<0||variant>2)return false;
        var rows=tag.getList("Snapshots",Tag.TAG_COMPOUND);if(rows.size()!=3)return false;var variants=new HashSet<Integer>();
        for(var raw:rows){var snapshot=decode((CompoundTag)raw);var job=jobs.get(snapshot.original().variant());if(job==null||!variants.add(snapshot.original().variant())||!job.snapshot().equals(snapshot)||snapshot.original().variant()!=variant&&!((Set.of(Phase.PARKED,Phase.DEPLOYED).contains(job.phase())&&job.waiting().isEmpty())||CarrierEquipmentUpdateR53.unmovedBayPreparationR53(job)))return false;}
        var preserved=tag.getList("Jobs",Tag.TAG_COMPOUND);if(preserved.size()!=3)return false;var matched=new HashSet<Integer>();
        for(var raw:preserved){var row=(CompoundTag)raw;int unit=row.getInt("Variant");var kept=jobs.get(unit);if(kept==null||!matched.add(unit)||!row.getString("Phase").equals(kept.phase().name())||!row.getString("Waiting").equals(kept.waiting())||!row.getCompound("Owner").equals(kept.ownerData()))return false;}
        if(!variants.equals(Set.of(0,1,2))||!matched.equals(variants))return false;var job=jobs.get(variant);var snapshot=job.snapshot();var data=job.ownerData();var clock=data.getCompound("ContinuousClockR52");var phase=data.getCompound(NervLaunchPhasesR53.KEY);var head=tag.getCompound("Head");
        boolean preparing=job.phase()==Phase.PREPARING&&phase.getString("Stage").equals("PRELAUNCH")
                &&clock.getDouble("ToMetres")==tag.getDouble("Distance")&&head.getInt("Clock")>=0&&head.getInt("Clock")<NervBankHeadTransferR53.TICKS;
        boolean awaitingLaunch=job.phase()==Phase.DEPARTING&&phase.getString("Stage").equals("ASCENT")&&!phase.getBoolean("LaunchCommitted")
                &&clock.getDouble("ToMetres")>tag.getDouble("Distance")&&head.getInt("Clock")==NervBankHeadTransferR53.TICKS;
        return (preparing||awaitingLaunch)&&snapshot.kind()==TransportMembershipR52.Kind.OCCUPIED&&snapshot.fraction()==0
                &&!data.contains("ContinuousBrakeR52")&&!clock.isEmpty()&&clock.equals(tag.getCompound("Clock"))&&phase.equals(tag.getCompound("Phase"))
                &&clock.getDouble("SpeedMps")==0&&Double.isFinite(tag.getDouble("Distance"))&&tag.getDouble("Distance")==data.getDouble("ContinuousDistanceR52")
                &&clock.getDouble("DistanceMetres")==tag.getDouble("Distance")
                &&clock.getString("Route").equals(snapshot.route())&&clock.getString("Directory").equals(fingerprint)
                &&phase.hasUUID("Task")&&phase.getUUID("Task").equals(snapshot.task())
                &&phase.getString("Directory").equals(fingerprint)&&phase.getString("Route").equals(snapshot.route())
                &&head.hasUUID("Task")&&head.getUUID("Task").equals(snapshot.task())&&head.getString("Directory").equals(fingerprint)&&head.getString("Route").equals(snapshot.route())
                &&head.getString("Source").equals(NervBankHeadTransferR53.SOURCE_SHA)&&!head.getBoolean("AbortedToStart");
    }
    public void queueInstallationR52(PendingInstallationR52 request)
    {
        Objects.requireNonNull(request);
        if(!fault.isEmpty()&&(!request.restoring()||interruptedContinuousCommitR53()==null))throw new IllegalStateException("Existing runtime fault must be resolved before installation: "+fault);
        if(pendingInstallation!=null&&!pendingInstallation.equals(request))throw new IllegalStateException("Pending bundle authority changed; preserve the original request and repair its exact sources");
        if(request.restoring())
        {
            if(!claimed||epoch!=request.epoch()||!fingerprint.equals(request.directory())||!installationBundle.equals(request.bundle())||!installationBundleSHA.equals(request.sha())&&!pendingCarrierEquipmentUpdate)throw new IllegalStateException("Restoration must retain the accepted bundle, epoch and directory");
        }
        else if(!installationBundle.isEmpty()||!jobs.isEmpty())throw new IllegalStateException("Accepted installation or original jobs require restoration, not new commissioning");
        if(pendingInstallation!=null&&!pendingInstallationHold.isEmpty())pendingInstallationPreviousHold=pendingInstallationHold;
        claim(request.epoch(),request.directory());pendingInstallation=request;pendingInstallationPaused=false;pendingInstallationHold="";pendingInstallationAttempts=Math.addExact(pendingInstallationAttempts,1);setDirty();
    }
    public void installationHoldR52(String reason)
    {if(pendingInstallation!=null&&!Objects.equals(pendingInstallationHold,reason)){pendingInstallationHold=Objects.requireNonNull(reason);setDirty();}}
    public void pauseInstallationR52(String reason)
    {if(pendingInstallation==null)throw new IllegalStateException("No pending installation");if(reason==null||reason.isBlank())throw new IllegalArgumentException("Explicit cancellation reason required");pendingInstallationPaused=true;pendingInstallationHold=reason;setDirty();}
    public void finishInstallationR52(PendingInstallationR52 request)
    {
        if(!Objects.equals(pendingInstallation,request)||pendingInstallationPaused||epoch!=request.epoch()||!fingerprint.equals(request.directory()))throw new IllegalStateException("Only the current verified request may complete installation");
        rememberInstallationR52(request.bundle(),request.sha());pendingInstallation=null;pendingInstallationPaused=false;pendingCarrierEquipmentUpdate=false;pendingBankCurbRefit=new CompoundTag();pendingInstallationHold="";pendingInstallationPreviousHold="";pendingInstallationAttempts=0;setDirty();
    }
    public String uprightGuideSourceR52(){return uprightGuideSourceSHA;}
    void declareUprightGuideSourceR52(String sha){if(!claimed||sha==null||!sha.matches("[0-9a-f]{64}")||sha.equals("0".repeat(64)))throw new IllegalArgumentException("Actual claimed upright source SHA required");if(!sha.equals(uprightGuideSourceSHA)){uprightGuideSourceSHA=sha;setDirty();}}
    public Map<UUID,Long> installationActorChunks(){return Map.copyOf(installationActorChunks);}
    public void rememberInstallationR52(String relativeBundle,String sha){
        if(!claimed)throw new IllegalStateException("Actual claimed directory required before remembering installation");
        String checked=relativeBundleR52(relativeBundle);if(sha==null||!sha.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Exact installed bundle SHA required");installationBundle=checked;installationBundleSHA=sha;setDirty();
    }
    public static String relativeBundleR52(String name){
        if(name==null||name.isBlank()||name.length()>1024||name.contains(":"))throw new IllegalArgumentException("Explicit world-relative installed bundle required");
        var path=java.nio.file.Path.of(name);if(path.isAbsolute()||path.getRoot()!=null||path.normalize().startsWith("..")||path.normalize().toString().isEmpty())throw new IllegalArgumentException("Explicit world-relative installed bundle required");return path.normalize().toString().replace('\\','/');
    }
    private static long checkedInstallationChunkR52(long chunk){int x=(int)chunk,z=(int)(chunk>>32);if(Math.abs((long)x)>1875000||Math.abs((long)z)>1875000)throw new IllegalArgumentException("Actual installed actor chunk exceeds world bounds");return chunk;}
    public void installationActorChunkR52(UUID actor,long chunk){if(installationBundle.isEmpty()&&pendingInstallation==null||actor==null)throw new IllegalStateException("Accepted or pending bundle and original actor required");checkedInstallationChunkR52(chunk);if(!Objects.equals(installationActorChunks.put(actor,chunk),chunk))setDirty();}
    public void retainInstallationActorsR52(Set<UUID> actual){if(installationActorChunks.keySet().removeIf(id->!actual.contains(id)))setDirty();}
    public void personnelLiftManifest(String relativeRootFile)
    {
        var path=java.nio.file.Path.of(relativeRootFile);if(path.isAbsolute()||relativeRootFile.contains(":")||path.normalize().startsWith(".."))throw new IllegalArgumentException("Root world-relative lift manifest required");
        personnelLiftManifest=relativeRootFile;setDirty();
    }
    public Job job(int variant){return jobs.get(variant);}
    public void clearOriginalMaintenanceR53(int variant){jobs.remove(variant);fault="";setDirty();}
    public Collection<Job> jobs(){return List.copyOf(jobs.values());}
    public void claim(long epoch,String fingerprint)
    {
        if(epoch<=0||fingerprint==null||!fingerprint.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Root epoch/fingerprint required");
        if(claimed&&(this.epoch!=epoch||!this.fingerprint.equals(fingerprint))&&!jobs.isEmpty())throw new IllegalStateException("Existing R52 jobs require explicit native migration");
        if(this.epoch!=epoch||!this.fingerprint.equals(fingerprint))uprightGuideSourceSHA="";
        claimed=true;this.epoch=epoch;this.fingerprint=fingerprint;setDirty();
    }
    public void put(Job job)
    {
        var snapshot=job.snapshot();if(!claimed||snapshot.original().epoch()!=epoch||!snapshot.directoryFingerprint().equals(fingerprint))throw new IllegalArgumentException("Job does not match claimed Root epoch/directory");
        var previous=jobs.get(snapshot.original().variant());
        if(previous!=null)
        {
            if(!allowed(previous.phase(),job.phase()))throw new IllegalArgumentException("Invalid real logistics lifecycle transition");
            if(previous.snapshot().task().equals(snapshot.task())&&(!previous.snapshot().original().equals(snapshot.original())||previous.snapshot().kind()!=snapshot.kind()))throw new IllegalArgumentException("Original provenance/moving membership changed inside one task");
            if(!previous.snapshot().task().equals(snapshot.task())&&!Set.of(Phase.PARKED,Phase.CANCELLED,Phase.DEPLOYED).contains(previous.phase()))throw new IllegalArgumentException("Active original job cannot be replaced");
        }
        jobs.put(snapshot.original().variant(),job);setDirty();
    }
    void resumeParkedServiceR53(Job expected,CompoundTag observed)
    {
        int variant=expected.snapshot().original().variant();
        if(jobs.get(variant)!=expected||expected.phase()!=Phase.PARKED||expected.snapshot().stage()!=Stage.COMPLETE
                ||!"DONE".equals(expected.ownerData().getString("Finish"))
                ||!observed.getBoolean("Returning")||!Set.of("REFILL","BRIDGE").contains(observed.getString("Finish"))
                ||!observed.hasUUID("ServiceReadbackTaskR53")||!observed.getUUID("ServiceReadbackTaskR53").equals(expected.snapshot().task()))
            throw new IllegalArgumentException("Only the unchanged completed task may resume observed bay service");
        jobs.put(variant,expected.update(expected.snapshot(),Phase.FINISHING,observed,"现场回读不一致，补完原机库整备"));setDirty();
    }
    public static boolean allowed(Phase from,Phase to)
    {
        if(from==to||to==Phase.CANCELLED)return true;
        return switch(from){case PREPARING->to==Phase.READY||to==Phase.DEPARTING;case READY->to==Phase.DEPARTING||to==Phase.PREPARING;case DEPARTING,RETURNING->to==Phase.FINISHING;case FINISHING->to==Phase.DEPLOYED||to==Phase.PARKED;case DEPLOYED->to==Phase.RETURNING;case PARKED->to==Phase.PREPARING;case CANCELLED->to==Phase.PREPARING||to==Phase.RETURNING;};
    }
    public static String legacyPhase(Job job)
    {
        return switch(job.phase()){case PREPARING->"TO_SILO";case READY,DEPARTING->"SILO_READY";case DEPLOYED->"DEPLOYED";case RETURNING->"TO_HANGAR";case FINISHING->job.ownerData().getBoolean("Returning")?"TO_HANGAR":"SILO_READY";case PARKED->"PARKED";case CANCELLED->"CANCELLED";};
    }
    public static NervRouteRuntimeStateR52 load(CompoundTag tag)
    {
        var state=new NervRouteRuntimeStateR52();state.claimed=tag.getBoolean("Claimed");state.epoch=tag.getLong("Epoch");state.fingerprint=tag.getString("DirectoryFingerprint");state.personnelLiftManifest=tag.getString("PersonnelLiftManifest");state.fault=tag.getString("Fault");
        if(tag.getInt("Version")!=1){state.fault="Unsupported R52 runtime save version";return state;}
        if(state.claimed&&(state.epoch<=0||!state.fingerprint.matches("[0-9a-f]{64}"))){state.fault="Invalid claimed Root epoch/directory";return state;}
        if(!state.personnelLiftManifest.isEmpty())try{state.personnelLiftManifest(state.personnelLiftManifest);}catch(RuntimeException invalid){state.fault="Invalid world-relative lift manifest";}
        if(tag.contains("UprightGuideSourceSHA"))try{state.declareUprightGuideSourceR52(tag.getString("UprightGuideSourceSHA"));}catch(RuntimeException invalid){state.fault="Invalid persisted upright guide source: "+invalid.getMessage();}
        if(tag.contains("InstallationBundle")||tag.contains("InstallationBundleSHA"))try{
            state.rememberInstallationR52(tag.getString("InstallationBundle"),tag.getString("InstallationBundleSHA"));
        }catch(RuntimeException invalid){state.fault="Invalid persisted Root installation: "+invalid.getMessage();}
        if(tag.contains("PendingInstallation",Tag.TAG_COMPOUND))try
        {
            var p=tag.getCompound("PendingInstallation");if(p.getInt("Version")!=1||!p.contains("Restoring",Tag.TAG_BYTE))throw new IllegalArgumentException("Explicit pending installation version and mode required");
            var request=new PendingInstallationR52(p.getString("Bundle"),p.getString("SHA"),p.getLong("Epoch"),p.getString("Directory"),p.getBoolean("Restoring"));
            if(!state.claimed||state.epoch!=request.epoch()||!state.fingerprint.equals(request.directory()))throw new IllegalArgumentException("Pending request differs from claimed epoch/directory");
            state.pendingCarrierEquipmentUpdate=p.getBoolean("CarrierEquipmentUpdate");
            if(p.contains("BankCurbRefit")){state.pendingBankCurbRefit=p.getCompound("BankCurbRefit").copy();if(!state.pendingCarrierEquipmentUpdate||state.pendingBankCurbRefit.isEmpty())throw new IllegalArgumentException("Explicit equipment-only bank refit receipt required");}
            if(state.pendingCarrierEquipmentUpdate&&!request.restoring())throw new IllegalArgumentException("Equipment update must restore original machinery");
            state.queueInstallationR52(request);state.pendingInstallationPaused=p.getBoolean("Paused");state.pendingInstallationHold=p.getString("Hold");state.pendingInstallationPreviousHold=p.getString("PreviousHold");state.pendingInstallationAttempts=p.contains("Attempts")?p.getInt("Attempts"):1;if(state.pendingInstallationAttempts<1)throw new IllegalArgumentException("Positive pending attempt count required");
        }catch(RuntimeException invalid){state.fault="Invalid pending Root installation: "+invalid.getMessage();}
        try
        {
            for(var raw:tag.getList("InstallationActorChunks",Tag.TAG_COMPOUND)){var row=(CompoundTag)raw;if(!row.hasUUID("Actor")||!row.contains("Chunk",Tag.TAG_LONG)||state.installationBundle.isEmpty()&&state.pendingInstallation==null||state.installationActorChunks.putIfAbsent(row.getUUID("Actor"),checkedInstallationChunkR52(row.getLong("Chunk")))!=null)throw new IllegalArgumentException("Distinct actual actor chunks require an accepted or pending bundle");}
        }catch(RuntimeException invalid){state.fault="Invalid persisted Root actor chunks: "+invalid.getMessage();}
        for(var element:tag.getList("Jobs",Tag.TAG_COMPOUND))
        {
            try
            {
                var row=(CompoundTag)element;var snapshot=decode(row.getCompound("Snapshot"));int v=snapshot.original().variant();
                if(v<0||v>2||state.jobs.containsKey(v))throw new IllegalArgumentException("Duplicate original unit job");
                if(!state.claimed||snapshot.original().epoch()!=state.epoch||!snapshot.directoryFingerprint().equals(state.fingerprint))throw new IllegalArgumentException("Saved job/Root claim mismatch");
                state.jobs.put(v,new Job(snapshot,Phase.valueOf(row.getString("Phase")),row.getCompound("OwnerData"),row.getString("Waiting")));
            }
            catch(RuntimeException invalid){state.fault="Invalid persisted R52 job: "+invalid.getMessage();}
        }
        if(state.pendingInstallation!=null&&!state.pendingInstallation.restoring()&&!state.jobs.isEmpty())state.fault="Initial commissioning cannot replace original saved jobs";
        if(state.pendingCarrierEquipmentUpdate)try
        {
            if(!state.pendingBankCurbRefit.isEmpty()){if(!state.pendingBankCurbCurrentR53())state.fault="Equipment update must retain the admitted original stopped bank task and clock";}
            else if(state.jobs.size()!=3||state.jobs.values().stream().anyMatch(j->j.phase()!=Phase.PARKED||!j.waiting().isEmpty()))state.fault="Equipment update must retain three parked original jobs";
        }catch(RuntimeException invalid){state.fault="Invalid pending bank equipment receipt: "+invalid.getMessage();}
        return state;
    }
    @Override public CompoundTag save(CompoundTag tag)
    {
        tag.putInt("Version",1);tag.putBoolean("Claimed",claimed);tag.putLong("Epoch",epoch);tag.putString("DirectoryFingerprint",fingerprint);tag.putString("PersonnelLiftManifest",personnelLiftManifest);tag.putString("Fault",fault);
        if(!uprightGuideSourceSHA.isEmpty())tag.putString("UprightGuideSourceSHA",uprightGuideSourceSHA);
        if(!installationBundle.isEmpty()){tag.putString("InstallationBundle",installationBundle);tag.putString("InstallationBundleSHA",installationBundleSHA);}
        if(pendingInstallation!=null){var p=new CompoundTag();p.putInt("Version",1);p.putString("Bundle",pendingInstallation.bundle());p.putString("SHA",pendingInstallation.sha());p.putLong("Epoch",pendingInstallation.epoch());p.putString("Directory",pendingInstallation.directory());p.putBoolean("Restoring",pendingInstallation.restoring());p.putBoolean("CarrierEquipmentUpdate",pendingCarrierEquipmentUpdate);p.putBoolean("Paused",pendingInstallationPaused);p.putString("Hold",pendingInstallationHold);p.putString("PreviousHold",pendingInstallationPreviousHold);p.putInt("Attempts",pendingInstallationAttempts);tag.put("PendingInstallation",p);}
        if(pendingInstallation!=null&&!pendingBankCurbRefit.isEmpty())tag.getCompound("PendingInstallation").put("BankCurbRefit",pendingBankCurbRefit.copy());
        if(!installationActorChunks.isEmpty()){var chunks=new ListTag();for(var e:installationActorChunks.entrySet()){var row=new CompoundTag();row.putUUID("Actor",e.getKey());row.putLong("Chunk",e.getValue());chunks.add(row);}tag.put("InstallationActorChunks",chunks);}
        var rows=new ListTag();for(var job:jobs.values()){var row=new CompoundTag();row.put("Snapshot",encode(job.snapshot()));row.putString("Phase",job.phase().name());row.put("OwnerData",job.ownerData().copy());row.putString("Waiting",job.waiting());rows.add(row);}tag.put("Jobs",rows);return tag;
    }
    public static CompoundTag encode(Snapshot snapshot)
    {
        var t=new CompoundTag();var o=snapshot.original();t.putUUID("Task",snapshot.task());t.putLong("Epoch",o.epoch());t.putInt("Variant",o.variant());
        t.putUUID("Eva",o.eva());t.putUUID("Plug",o.plug());t.putUUID("Pilot",o.pilot());t.putUUID("Owner",o.owner());t.putString("Mission",o.mission());t.putString("Dimension",o.dimension());
        t.putString("DirectoryFingerprint",snapshot.directoryFingerprint());t.putString("Route",snapshot.route());t.putInt("Leg",snapshot.leg());t.putDouble("Fraction",snapshot.fraction());t.putString("Stage",snapshot.stage().name());t.putString("Waiting",snapshot.waiting());t.putString("AssemblyKind",snapshot.kind().name());return t;
    }
    public static Snapshot decode(CompoundTag tag)
    {
        for(String key:List.of("Task","Eva","Plug","Pilot","Owner"))if(!tag.hasUUID(key))throw new IllegalArgumentException("Missing original UUID: "+key);
        var original=new Original(tag.getLong("Epoch"),tag.getInt("Variant"),tag.getUUID("Eva"),tag.getUUID("Plug"),tag.getUUID("Pilot"),tag.getUUID("Owner"),tag.getString("Mission"),tag.getString("Dimension"));
        double fraction=tag.getDouble("Fraction");if(!Double.isFinite(fraction)||fraction<0||fraction>1)throw new IllegalArgumentException("Invalid saved fraction");
        var kind=tag.contains("AssemblyKind")?TransportMembershipR52.Kind.valueOf(tag.getString("AssemblyKind")):TransportMembershipR52.Kind.OCCUPIED;
        return new Snapshot(tag.getUUID("Task"),original,tag.getString("DirectoryFingerprint"),tag.getString("Route"),tag.getInt("Leg"),fraction,Stage.valueOf(tag.getString("Stage")),tag.getString("Waiting"),kind);
    }
}

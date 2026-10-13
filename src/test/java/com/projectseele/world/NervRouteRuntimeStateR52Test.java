package com.projectseele.world;

import java.util.*;
import net.minecraft.nbt.CompoundTag;
import com.projectseele.world.NervRouteReservationsR52.*;
import com.projectseele.world.NervRouteRuntimeStateR52.*;

/** Tests the production SavedData/lifecycle with real native CompoundTags.
 * No substitute model, world, actor creation or physical-transport pass claim. */
public final class NervRouteRuntimeStateR52Test
{
    private static int checks;
    private static void check(boolean condition,String why){checks++;if(!condition)throw new AssertionError(why);}
    private static void rejects(Runnable call,String why){boolean rejected=false;try{call.run();}catch(RuntimeException expected){rejected=true;}check(rejected,why);}
    private static Snapshot snapshot(UUID task,Stage stage,int leg,double fraction,String mission)
    {return new Snapshot(task,new Original(7,0,new UUID(0,10),new UUID(0,20),new UUID(0,30),new UUID(0,40),mission,"test:native_nbt_lifecycle"),"f".repeat(64),"root_declared_route",leg,fraction,stage,"");}
    public static void main(String[] args)
    {
        var state=new NervRouteRuntimeStateR52();check(!state.claimed(),"Ordinary old save unexpectedly claimed R52");state.claim(7,"f".repeat(64));state.personnelLiftManifest("root_personnel_lifts_r52.json");
        UUID task=new UUID(0,100);var owner=new CompoundTag();owner.putString("OriginalPoseHash","measured_pose_receipt");var initial=snapshot(task,Stage.RESERVED,0,0,"original_mission");state.put(new Job(initial,Phase.PREPARING,owner,""));
        owner.putString("OriginalPoseHash","mutated_external_tag");check(state.job(0).ownerData().getString("OriginalPoseHash").equals("measured_pose_receipt"),"Owner payload aliased external mutation");
        var tag=state.save(new CompoundTag());var loaded=NervRouteRuntimeStateR52.load(tag);check(loaded.claimed()&&loaded.epoch()==7&&loaded.personnelLiftManifest().equals("root_personnel_lifts_r52.json"),"Shared pending claim/lift reference did not survive real NBT roundtrip");
        check(loaded.job(0).snapshot().equals(initial),"Original UUID triple/owner/mission/progress not exactly preserved");
        rejects(()->loaded.put(new Job(initial,Phase.DEPLOYED,new CompoundTag(),"")),"Preparation skipped actual READY/release/departure lifecycle");
        loaded.put(new Job(snapshot(task,Stage.MOVING,1,0,"original_mission"),Phase.READY,new CompoundTag(),""));check(NervRouteRuntimeStateR52.legacyPhase(loaded.job(0)).equals("SILO_READY"),"Existing UI/commands lost SILO_READY semantics");
        loaded.put(new Job(snapshot(task,Stage.MOVING,1,0,"original_mission"),Phase.DEPARTING,new CompoundTag(),""));loaded.put(new Job(snapshot(task,Stage.HOLD,1,.25,"original_mission"),Phase.DEPARTING,new CompoundTag(),"actual_door_blocked"));
        check(loaded.job(0).snapshot().fraction()==.25&&loaded.job(0).waiting().equals("actual_door_blocked"),"Blocked real phase did not persist unchanged progress");
        rejects(()->loaded.put(new Job(snapshot(task,Stage.MOVING,1,.5,"replacement_mission"),Phase.DEPARTING,new CompoundTag(),"")),"Mission changed inside an original task");
        loaded.put(new Job(snapshot(task,Stage.COMPLETE,3,1,"original_mission"),Phase.FINISHING,new CompoundTag(),"physical_finish_pending"));var restart=NervRouteRuntimeStateR52.load(loaded.save(new CompoundTag()));
        check(restart.job(0).phase()==Phase.FINISHING&&restart.job(0).snapshot().stage()==Stage.COMPLETE,"Restart lost actual mechanical finishing hold");
        check(NervRouteRuntimeStateR52.legacyPhase(restart.job(0)).equals("SILO_READY"),"Outgoing mechanical completion was falsely reported as return");
        restart.put(new Job(snapshot(task,Stage.COMPLETE,3,1,"original_mission"),Phase.DEPLOYED,new CompoundTag(),""));
        UUID returning=new UUID(0,101);restart.put(new Job(snapshot(returning,Stage.RESERVED,0,0,""),Phase.RETURNING,new CompoundTag(),""));restart.put(new Job(snapshot(returning,Stage.COMPLETE,3,1,""),Phase.FINISHING,new CompoundTag(),""));restart.put(new Job(snapshot(returning,Stage.COMPLETE,3,1,""),Phase.PARKED,new CompoundTag(),""));
        check(NervRouteRuntimeStateR52.legacyPhase(restart.job(0)).equals("PARKED"),"Actual return/refill completion did not reach parked phase");
        var bad=tag.copy();bad.putInt("Version",99);var unsupported=NervRouteRuntimeStateR52.load(bad);check(unsupported.claimed()&&!unsupported.fault().isEmpty(),"Unsupported claimed state silently fell back to old coordinates");
        bad=tag.copy();bad.getList("Jobs",net.minecraft.nbt.Tag.TAG_COMPOUND).getCompound(0).getCompound("Snapshot").remove("Plug");var missing=NervRouteRuntimeStateR52.load(bad);check(missing.claimed()&&!missing.fault().isEmpty(),"Missing original plug receipt became an unclaimed legacy world");
        rejects(()->restart.personnelLiftManifest("../another_world.json"),"Lift reference escaped Root world");
        rejects(()->restart.claim(8,"a".repeat(64)),"Live Root job silently migrated to another epoch");
        bad=tag.copy();bad.getList("Jobs",net.minecraft.nbt.Tag.TAG_COMPOUND).getCompound(0).getCompound("Snapshot").putLong("Epoch",8);check(!NervRouteRuntimeStateR52.load(bad).fault().isEmpty(),"Saved job with foreign Root epoch accepted");
        bad=tag.copy();bad.putString("PersonnelLiftManifest","../escape.json");check(!NervRouteRuntimeStateR52.load(bad).fault().isEmpty(),"Persisted lift reference escaped Root world");
        check(!NervRouteRuntimeStateR52.load(NervRouteRuntimeStateR52.load(bad).save(new CompoundTag())).fault().isEmpty(),"Readback erased prior safety fault");
        check(loaded.installationBundle().isEmpty(),"Old claimed save inferred a default bundle path");
        loaded.rememberInstallationR52("runtime/ROOT_ASSEMBLY_BUNDLE.json","b".repeat(64));UUID carrier=new UUID(5,1),station=new UUID(5,2);long firstChunk=net.minecraft.world.level.ChunkPos.asLong(12,-5),secondChunk=net.minecraft.world.level.ChunkPos.asLong(13,-5);loaded.installationActorChunkR52(carrier,firstChunk);loaded.installationActorChunkR52(station,firstChunk);loaded.installationActorChunkR52(carrier,secondChunk);
        var installedTag=loaded.save(new CompoundTag());var restored=NervRouteRuntimeStateR52.load(installedTag);check(restored.fault().isEmpty()&&restored.installationBundle().equals("runtime/ROOT_ASSEMBLY_BUNDLE.json")&&restored.installationBundleSHA().equals("b".repeat(64)),"Exact relative Root bundle/SHA did not survive cold NBT roundtrip");
        check(restored.installationActorChunks().get(carrier)==secondChunk&&restored.installationActorChunks().get(station)==firstChunk,"Moved original carrier/station chunk or original UUID was lost");check(restored.job(0).snapshot().equals(loaded.job(0).snapshot())&&restored.job(0).phase()==loaded.job(0).phase(),"Remembering installation changed saved mission/progress");
        rejects(()->restored.installationActorChunks().put(new UUID(5,3),0L),"External caller mutated saved controller locations");rejects(()->restored.rememberInstallationR52("other.json","invalid"),"Invalid installation SHA admitted");check(restored.installationBundle().equals("runtime/ROOT_ASSEMBLY_BUNDLE.json"),"Rejected installation partially changed the remembered path");
        for(String unsafe:List.of("../escape.json","C:/other/world.json","/other/world.json","\\other\\world.json","","."))rejects(()->NervRouteRuntimeStateR52.relativeBundleR52(unsafe),"World-relative bundle accepted unsafe path: "+unsafe);
        restored.retainInstallationActorsR52(Set.of(carrier));check(restored.installationActorChunks().keySet().equals(Set.of(carrier)),"Unrelated prior controller chunks were retained for a new exact Root roster");
        bad=installedTag.copy();bad.putString("InstallationBundle","../escape.json");check(!NervRouteRuntimeStateR52.load(bad).fault().isEmpty(),"Persisted bundle escaped actual world");bad=installedTag.copy();bad.putString("InstallationBundleSHA","invalid");check(!NervRouteRuntimeStateR52.load(bad).fault().isEmpty(),"Malformed persisted bundle SHA silently restored");bad=installedTag.copy();bad.getList("InstallationActorChunks",net.minecraft.nbt.Tag.TAG_COMPOUND).add(bad.getList("InstallationActorChunks",net.minecraft.nbt.Tag.TAG_COMPOUND).getCompound(0).copy());check(!NervRouteRuntimeStateR52.load(bad).fault().isEmpty(),"Duplicate saved machine identity silently restored");bad=installedTag.copy();bad.getList("InstallationActorChunks",net.minecraft.nbt.Tag.TAG_COMPOUND).getCompound(0).putLong("Chunk",Long.MAX_VALUE);check(!NervRouteRuntimeStateR52.load(bad).fault().isEmpty(),"Out-of-world actor chunk silently restored");
        System.out.println("R52 real SavedData/lifecycle PASS checks="+checks+"; native NBT only, no live movement/collision acceptance");
    }
    private NervRouteRuntimeStateR52Test(){}
}

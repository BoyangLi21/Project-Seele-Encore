package com.projectseele.world;

import com.google.gson.*;
import java.io.IOException;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import com.projectseele.entity.EvaMechanicalFrameR52;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.NervCarrierPlatformEntity;
import net.minecraft.nbt.CompoundTag;

/** Admits explicit bay or stopped-bank equipment refits while retaining the accepted jobs.
 * The previous accepted bundle stays authoritative until normal restoration finishes. */
public final class CarrierEquipmentUpdateR53
{
    public static NervRootAssemblyInstallationR52.Result admit(ServerLevel level, Path previousDirectory) throws IOException
    {
        var saved=NervRouteRuntimeR52.installationStateR52(level);
        require(saved!=null&&saved.claimed()&&saved.fault().isEmpty(),"Original accepted installation required");
        require(!NervRouteRuntimeR52.controllerLoadedR52(level),"Equipment update requires a stopped original controller");
        var world=level.getServer().getWorldPath(LevelResource.ROOT).toRealPath();
        var currentFile=world.resolve(NervRouteRuntimeStateR52.relativeBundleR52(saved.installationBundle())).toRealPath();
        require(currentFile.startsWith(world),"Original same-world bundle required");
        var previous=previousDirectory.toRealPath();
        byte[] oldBytes=read(previous.resolve(currentFile.getFileName()),256000),newBytes=read(currentFile,256000);
        require(binding(oldBytes).equals(saved.installationBundleSHA()),"Backup is not the original accepted installation");
        var oldBundle=json(oldBytes);var newBundle=json(newBytes);
        var oldReference=oldBundle.getAsJsonObject("mechanical_owner");
        var newReference=newBundle.getAsJsonObject("mechanical_owner");
        var expected=oldBundle.deepCopy();expected.add("mechanical_owner",newReference.deepCopy());
        require(expected.equals(newBundle),"Equipment update cannot change epoch, directory or other components");
        expected=oldReference.deepCopy();expected.add("sha256",newReference.get("sha256"));
        require(expected.equals(newReference),"Equipment update cannot move the original owner source");
        var relative=Path.of(oldReference.get("file").getAsString());
        require(!relative.isAbsolute()&&relative.getNameCount()==1&&!relative.toString().contains(":"),"Original owner filename required");
        var ownerFile=currentFile.getParent().resolve(relative);
        byte[] oldOwner=read(previous.resolve(relative),32000000),newOwner=read(ownerFile,32000000);
        require(binding(oldOwner).equals(oldReference.get("sha256").getAsString())&&binding(newOwner).equals(newReference.get("sha256").getAsString()),"Actual old and new owner sources required");
        var oldDocument=json(oldOwner);
        boolean bankRefit=bankOverlayDelta(oldDocument,json(newOwner));
        StoppedBankRefit bankPermit=null;
        if(bankRefit)
        {
            var reference=newBundle.getAsJsonObject("directory");
            var directoryFile=currentFile.getParent().resolve(reference.get("file").getAsString()).toRealPath();
            require(directoryFile.startsWith(world),"Original same-world directory required");
            byte[] directoryBytes=read(directoryFile,32000000);
            require(binding(directoryBytes).equals(reference.get("sha256").getAsString()),"Exact retained route directory required");
            bankPermit=stoppedBank(level,saved,NervRouteDirectoryR52.parse(json(directoryBytes)),oldDocument);
        }
        else
        {
            restorePreviousBridgeTables(oldDocument,previous,currentFile.getParent());
            var expectedOwner=NervAssemblyOwnerR52.readDocumentR52(ownerFile,oldDocument.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
            var installedOwner=NervAssemblyOwnerR52.readDocumentR52(ownerFile,newOwner);
            extendOriginalFrontLeaves(expectedOwner);
            relocateOriginalBridgeFrames(expectedOwner,installedOwner);
            require(expectedOwner.equals(installedOwner),"Only the declared original gate and rear boarding-frame refits may change");
            var bays=CarrierBayTrayR53.selected();require(bays.size()==3,"Installed three-bay tray source required");
            for(var bay:bays)
            {
                var job=saved.job(bay.variant());
                require(job!=null&&job.phase()==NervRouteRuntimeStateR52.Phase.PARKED&&job.waiting().isEmpty()
                        &&job.snapshot().original().eva().equals(bay.eva()),"Original parked bay identities required");
            }
        }
        var request=new NervRouteRuntimeStateR52.PendingInstallationR52(saved.installationBundle(),binding(newBytes),
                newBundle.get("epoch").getAsLong(),newBundle.get("directory_fingerprint").getAsString(),true);
        if(saved.pendingInstallationR52()==null)
        {
            if(bankPermit!=null)saved.queueCarrierEquipmentUpdateR53(request,bankPermit);
            else saved.queueCarrierEquipmentUpdateR53(request);
        }
        else require(saved.pendingCarrierEquipmentUpdateR53()&&request.equals(saved.pendingInstallationR52()),"Retain the already admitted equipment request");
        return NervRootAssemblyInstallationR52.install(level,currentFile);
    }

    static boolean bankOverlayDelta(JsonObject before,JsonObject after)
    {
        String key=NervLegacyBankClearanceR53.SOURCE;
        var oldSources=before.getAsJsonObject("mechanism_sources");var newSources=after.getAsJsonObject("mechanism_sources");
        if(!newSources.has(key))return false;
        if(oldSources.has(key)&&oldSources.get(key).equals(newSources.get(key)))return false;
        if(oldSources.has(key))require(oldSources.get(key).getAsString().equals(NervLegacyBankClearanceR53.PREVIOUS_SOURCE_SHA),
                "Only the preceding accepted bank curb source may receive its declared interface refit");
        require(newSources.get(key).getAsString().equals(NervLegacyBankClearanceR53.SOURCE_SHA),"Exact selected bank curb equipment required");
        var expected=before.deepCopy();expected.getAsJsonObject("mechanism_sources").addProperty(key,NervLegacyBankClearanceR53.SOURCE_SHA);
        require(expected.equals(after),"Bank equipment may only update its one source; all original owner fields must remain unchanged");
        return true;
    }

    /** Created only after the exact equipment delta and real stopped assembly are checked. */
    static final class StoppedBankRefit
    {
        private final ServerLevel level;private final long tick;private final NervRouteRuntimeStateR52 saved;
        private final List<NervRouteRuntimeStateR52.Job> jobs;
        private final NervCarrierPlatformEntity carrier;private final CompoundTag carrierState,mount;private final int variant;
        private StoppedBankRefit(ServerLevel level,NervRouteRuntimeStateR52 saved,NervCarrierPlatformEntity carrier,int variant)
        {
            this.level=level;this.tick=level.getGameTime();this.saved=saved;this.carrier=carrier;this.variant=variant;
            this.jobs=saved.jobs().stream().map(j->new NervRouteRuntimeStateR52.Job(j.snapshot(),j.phase(),j.ownerData(),j.waiting())).toList();
            this.carrierState=carrier.originalCarrierStateR52().copy();this.mount=carrier.carrierMountProfileR53().copy();
        }
        boolean current(NervRouteRuntimeStateR52 state)
        {return state==saved&&level.getGameTime()==tick&&List.copyOf(state.jobs()).equals(jobs)
                &&level.getEntity(carrier.getUUID())==carrier&&carrier.originalCarrierStateR52().equals(carrierState)&&carrier.carrierMountProfileR53().equals(mount);}
        CompoundTag persistence()
        {
            var tag=new CompoundTag();tag.putInt("Version",2);tag.putInt("Variant",variant);tag.putString("Source",NervLegacyBankClearanceR53.SOURCE_SHA);tag.putUUID("Carrier",carrier.getUUID());
            var rows=new net.minecraft.nbt.ListTag();for(var job:jobs)rows.add(NervRouteRuntimeStateR52.encode(job.snapshot()));tag.put("Snapshots",rows);
            var preserved=new net.minecraft.nbt.ListTag();for(var job:jobs){var row=new CompoundTag();row.putInt("Variant",job.snapshot().original().variant());row.putString("Phase",job.phase().name());row.putString("Waiting",job.waiting());row.put("Owner",job.ownerData());preserved.add(row);}tag.put("Jobs",preserved);
            var data=saved.job(variant).ownerData();tag.put("Phase",data.getCompound(NervLaunchPhasesR53.KEY).copy());tag.put("Clock",data.getCompound("ContinuousClockR52").copy());
            tag.putDouble("Distance",data.getDouble("ContinuousDistanceR52"));tag.put("Head",carrierState.getCompound(NervBankHeadTransferR53.KEY).copy());return tag;
        }
    }

    private static StoppedBankRefit stoppedBank(ServerLevel level,NervRouteRuntimeStateR52 saved,NervRouteDirectoryR52 directory,JsonObject owner)
    {
        require(saved.epoch()==directory.epoch()&&saved.fingerprint().equals(directory.fingerprint())&&saved.jobs().size()==3,"Retained original directory and three jobs required");
        var variants=new HashSet<Integer>();
        for(var raw:owner.getAsJsonArray("units"))
        {
            var unit=raw.getAsJsonObject();int variant=unit.get("variant").getAsInt();var job=saved.job(variant);
            require(variants.add(variant)&&job!=null&&job.snapshot().original().eva().toString().equals(unit.get("eva").getAsString())
                    &&job.snapshot().original().plug().toString().equals(unit.get("plug").getAsString()),"Unchanged original bay identities required");
        }
        require(variants.equals(Set.of(0,1,2)),"Original three bay owners required");
        return stoppedBankAssembly(level,saved,directory);
    }
    private static StoppedBankRefit stoppedBankAssembly(ServerLevel level,NervRouteRuntimeStateR52 saved,NervRouteDirectoryR52 directory)
    {
        var candidates=saved.jobs().stream().filter(j->{
            var route=directory.route(j.snapshot().route());var s=j.snapshot();
            return Set.of(NervRouteRuntimeStateR52.Phase.PREPARING,NervRouteRuntimeStateR52.Phase.DEPARTING).contains(j.phase())
                    &&route!=null&&s.leg()>=0&&s.leg()<route.legs().size()&&s.fraction()==0
                    &&directory.leg(route.legs().get(s.leg())).from().equals(route.readyNode());
        }).toList();
        require(candidates.size()==1,"Exactly one original stopped bank assembly required");
        var job=candidates.get(0);var snapshot=job.snapshot();var original=snapshot.original();var data=job.ownerData().copy();
        for(var other:saved.jobs())if(other.snapshot().original().variant()!=original.variant())
        {
            if(Set.of(NervRouteRuntimeStateR52.Phase.PARKED,NervRouteRuntimeStateR52.Phase.DEPLOYED).contains(other.phase())&&other.waiting().isEmpty())continue;
            require(unmovedBayPreparationR53(other),"Other original jobs must remain released, parked or in their unmoved preparation bay");
            var otherActor=level.getEntity(other.snapshot().original().eva());
            require(otherActor instanceof EvaUnit01Entity&&otherActor.getDeltaMovement().lengthSqr()==0,"Other preparing original must be physically stationary");
            var otherEva=(EvaUnit01Entity)otherActor;var otherRoute=directory.route(other.snapshot().route());
            require(otherRoute!=null&&!otherRoute.recovery()&&otherRoute.continuousUpright(),"Other preparation must retain its original departure route");
            try
            {
                var bay=directory.sample(directory.leg(otherRoute.legs().get(0)),0,NervOriginalCarrierR52.nominalBinding(other.snapshot().original().variant())).evaRoot();
                var otherCarrier=EvaMechanicalFrameR52.originalCarrierControllerR52(otherEva);
                require(NervAirTransportManifestR52.same(bay,NervOwnerPlacementR52.actualRoot(otherEva))&&otherCarrier!=null
                        &&otherCarrier.getDeltaMovement().lengthSqr()==0&&NervAirTransportManifestR52.same(bay,NervOriginalCarrierR52.actualRoot(otherCarrier,1)),
                        "Other preparation must remain at its declared original bay, outside the bank interface refit");
            }
            catch(IOException missing){throw new IllegalStateException("Actual original bay reference unavailable",missing);}
        }
        var route=directory.route(snapshot.route());
        boolean awaitingLaunch=job.phase()==NervRouteRuntimeStateR52.Phase.DEPARTING;
        require(snapshot.kind()==TransportMembershipR52.Kind.OCCUPIED
                &&snapshot.directoryFingerprint().equals(directory.fingerprint())&&route!=null&&!route.recovery()&&route.phased()
                &&data.contains(NervLaunchPhasesR53.KEY)&&data.contains("ContinuousClockR52"),"Original occupied departure at its saved bank preparation required");
        if(awaitingLaunch)
        {
            var run=NervLaunchPhasesR53.current(data,snapshot.task(),directory,route,data.getDouble("ContinuousDistanceR52"));
            var clock=data.getCompound("ContinuousClockR52");
            require(run.stage()==NervLaunchPhasesR53.Stage.ASCENT&&!data.getCompound(NervLaunchPhasesR53.KEY).getBoolean("LaunchCommitted")
                    &&!data.contains("ContinuousBrakeR52")&&data.getDouble("ContinuousDistanceR52")==directory.readyDistanceR53(route)
                    &&clock.getDouble("DistanceMetres")==directory.readyDistanceR53(route)&&clock.getDouble("SpeedMps")==0
                    &&clock.getDouble("ToMetres")==run.stop()&&clock.getString("Route").equals(route.id())&&clock.getString("Directory").equals(directory.fingerprint()),
                    "Only an unlaunched zero-speed ascent at its exact saved bank may receive the interface refit");
        }
        else NervLaunchPhasesR53.verifyStoppedBank(data,snapshot.task(),directory,route,data.getDouble("ContinuousDistanceR52"));
        require(data.equals(job.ownerData()),"Bank admission cannot create or alter a phase receipt");
        require(snapshot.leg()>=0&&snapshot.leg()<route.legs().size()&&snapshot.fraction()==0
                &&directory.leg(route.legs().get(snapshot.leg())).from().equals(route.readyNode()),"Exact original bank route boundary required");
        var actor=level.getEntity(original.eva());var plug=level.getEntity(original.plug());var pilot=level.getEntity(original.pilot());
        require(actor instanceof EvaUnit01Entity&&plug!=null&&pilot!=null&&pilot.getVehicle()==plug&&plug.getFirstPassenger()==pilot&&plug.getVehicle()==actor,"Original EVA/capsule/pilot custody required");
        var eva=(EvaUnit01Entity)actor;var carrier=EvaMechanicalFrameR52.originalCarrierControllerR52(eva);
        require(eva.isAlive()&&EvaMechanicalFrameR52.active(eva)&&EvaMechanicalFrameR52.epoch(eva)==original.epoch()
                &&eva.getDeltaMovement().lengthSqr()==0&&carrier!=null&&carrier.getDeltaMovement().lengthSqr()==0
                &&NervOriginalCarrierR52.isCapturedMemberR52(eva,carrier),"Actual stationary complete original carrier assembly required");
        var root=directory.sample(directory.leg(route.legs().get(snapshot.leg())),0,EvaMechanicalFrameR52.measuredBinding(eva,original)).evaRoot();
        require(NervAirTransportManifestR52.same(root,EvaMechanicalFrameR52.frame(eva,1))
                &&NervAirTransportManifestR52.same(root,NervOriginalCarrierR52.actualRoot(carrier,1)),"Actual carrier and payload must remain at their original bank root");
        var head=carrier.originalCarrierStateR52().getCompound(NervBankHeadTransferR53.KEY);
        require(head.hasUUID("Task")&&head.getUUID("Task").equals(snapshot.task())&&head.getString("Directory").equals(directory.fingerprint())
                &&head.getString("Route").equals(route.id())&&(awaitingLaunch?head.getInt("Clock")==NervBankHeadTransferR53.TICKS&&!head.getBoolean("AbortedToStart"):NervBankHeadTransferR53.unfinished(head)),"Original retained bank head task required");
        var pose=NervBankHeadTransferR53.pose(head,head.getInt("Clock"));
        require(NervOriginalCarrierR52.uprightDirectionR52(carrier,1).distanceTo(pose.direction())<1e-7
                &&NervOriginalCarrierR52.headSlideR53(carrier,1)==pose.slide(),"Retain the actual saved head clock and source pose");
        return new StoppedBankRefit(level,saved,carrier,original.variant());
    }

    static boolean unmovedBayPreparationR53(NervRouteRuntimeStateR52.Job job)
    {
        var data=job.ownerData();
        return job.phase()==NervRouteRuntimeStateR52.Phase.PREPARING&&job.snapshot().leg()==0&&job.snapshot().fraction()==0
                &&data.getDouble("ContinuousDistanceR52")==0&&data.getCompound("ContinuousClockR52").getDouble("SpeedMps")==0
                &&!data.contains("ContinuousBrakeR52");
    }

    static void verifyPendingBank(ServerLevel level,NervRouteRuntimeStateR52 saved,NervRouteDirectoryR52 directory)
    {
        if(saved==null||saved.pendingBankCurbRefitR53().isEmpty())return;
        require(saved.pendingBankCurbCurrentR53(),"Persisted original bank task/clock changed during equipment admission");
        var observed=stoppedBankAssembly(level,saved,directory).persistence();
        require(observed.equals(saved.pendingBankCurbRefitR53()),"Actual original bank head/carrier differs from admitted equipment stop");
    }

    private static void restorePreviousBridgeTables(JsonObject owner,Path previous,Path world)throws IOException
    {
        for(var raw:owner.getAsJsonArray("units"))
        {
            var unit=raw.getAsJsonObject();var table=unit.get("bridge_states");if(table.isJsonArray())continue;
            var ref=table.getAsJsonObject();String name=ref.get("cells_file").getAsString();
            var relative=Path.of(name);require(!relative.isAbsolute()&&!name.contains("..")&&!name.contains(":"),"Original local bridge table required");
            var backup=previous.resolve(relative);var file=Files.isRegularFile(backup)?backup:world.resolve(relative);
            byte[] bytes=read(file,32000000);require(binding(bytes).equals(ref.get("sha256").getAsString()),"Exact accepted bridge predecessor required");
            if(name.endsWith(".gz"))try(var in=new java.util.zip.GZIPInputStream(new java.io.ByteArrayInputStream(bytes))){bytes=in.readNBytes(32000001);require(bytes.length<=32000000,"Bounded bridge table required");}
            unit.add("bridge_states",JsonParser.parseString(new String(bytes,java.nio.charset.StandardCharsets.UTF_8)));
        }
    }

    static void relocateOriginalBridgeFrames(JsonObject expected,JsonObject installed)
    {
        var oldUnits=expected.getAsJsonArray("units");var newUnits=installed.getAsJsonArray("units");
        require(oldUnits.size()==3&&newUnits.size()==3,"Original three bridge owners required");
        for(int index=0;index<3;index++)
        {
            var unit=oldUnits.get(index).getAsJsonObject();int variant=unit.get("variant").getAsInt();
            var states=unit.getAsJsonArray("bridge_states");var actual=newUnits.get(index).getAsJsonObject().getAsJsonArray("bridge_states");
            if(states.equals(actual))continue;
            require(states.size()==10&&actual.size()==10,"Ten original boarding states required");
            for(int state=0;state<10;state++)relocateBridgeState(states.get(state).getAsJsonArray(),variant);
            require(states.equals(actual),"Exact retained-width rear bridge refit required");
        }
    }
    private static java.util.List<Integer> point(JsonArray a)
    {return java.util.List.of(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt());}
    private static void relocateBridgeState(JsonArray rows,int unit)
    {
        String deck="projectseele:entry_plug_bridge_deck",guard="projectseele:entry_plug_bridge_guard",air="minecraft:air";
        var old=new java.util.LinkedHashMap<java.util.List<Integer>,String>();
        for(var raw:rows){var row=raw.getAsJsonObject();require(old.put(point(row.getAsJsonArray("position")),row.get("state").getAsString())==null,"Distinct bridge cells required");}
        var next=new java.util.LinkedHashMap<>(old);var moving=new java.util.LinkedHashMap<java.util.List<Integer>,String>();
        for(var entry:old.entrySet())
        {var at=entry.getKey();String value=entry.getValue();if(at.get(0)>=56-42*unit&&at.get(0)<=88-42*unit&&(at.get(2)==313||at.get(2)==314)&&(value.startsWith(deck)||value.startsWith(guard)))moving.put(at,value);}
        for(var at:moving.keySet())next.put(at,air);
        var affected=new java.util.LinkedHashSet<java.util.List<Integer>>();
        for(var entry:moving.entrySet())
        {
            var at=entry.getKey();var target=java.util.List.of(at.get(0),at.get(1),at.get(2)-1);String before=old.getOrDefault(target,air);
            require(old.containsKey(target)&&(before.equals(air)||before.startsWith(deck)||before.startsWith(guard)),"Retained declared bridge interface required");next.put(target,entry.getValue());
            if(entry.getValue().startsWith(deck))affected.add(java.util.List.of(at.get(0),-1015,at.get(2)-1));
        }
        String[] names={"east","north","south","west"};int[] dx={1,0,0,-1},dz={0,-1,1,0};
        for(var at:affected)
        {
            require(next.get(at).startsWith(deck),"Original full-width rear beam required");var flags=new java.util.TreeMap<String,String>();boolean edge=false;
            for(int i=0;i<4;i++){boolean exposed=next.getOrDefault(java.util.List.of(at.get(0)+dx[i],at.get(1),at.get(2)+dz[i]),air).equals(air);flags.put(names[i],Boolean.toString(exposed));edge|=exposed;}
            var upper=java.util.List.of(at.get(0),at.get(1)+1,at.get(2));String before=next.getOrDefault(upper,air);
            require(old.containsKey(upper)&&(before.equals(air)||before.startsWith(guard)),"Existing guarded interface required");
            next.put(upper,edge?blockState(guard,flags):air);flags.put("unit",Integer.toString(unit));next.put(at,blockState(deck,flags));
        }
        for(var raw:rows){var row=raw.getAsJsonObject();row.addProperty("state",next.get(point(row.getAsJsonArray("position"))));}
    }
    private static String blockState(String name,java.util.SortedMap<String,String> flags)
    {return name+"["+String.join(",",flags.entrySet().stream().map(e->e.getKey()+"="+e.getValue()).toList())+"]";}

    static void extendOriginalFrontLeaves(JsonObject owner)
    {
        var found=new HashSet<Integer>();
        for(var raw:owner.getAsJsonArray("gates"))
        {
            var gate=raw.getAsJsonObject();String name=gate.get("resource").getAsString();
            if(!Set.of("bay_0_front","bay_1_front","bay_2_front").contains(name))continue;
            int variant=gate.get("variant").getAsInt();require(found.add(variant)&&name.equals("bay_"+variant+"_front"),"Distinct original front gates required");
            var position=gate.getAsJsonObject("frame").getAsJsonArray("position");
            require(gate.get("width").getAsDouble()==33&&gate.get("height").getAsDouble()==72
                    &&position.get(1).getAsDouble()==-1062&&position.get(2).getAsDouble()==301.5,"Original front gate dimensions required");
            var existingStack=gate.getAsJsonObject("hangar_stack");
            if(existingStack.has("leaf_lower_extension_m")&&existingStack.get("leaf_lower_extension_m").getAsDouble()==5)continue;
            var retired=new HashSet<JsonElement>();
            if(gate.has("floor_seal_original_cells"))for(var at:gate.remove("floor_seal_original_cells").getAsJsonArray())retired.add(at);
            var steps=new JsonArray();var occupied=new HashSet<JsonElement>();
            for(var row:gate.getAsJsonArray("collision_steps"))
            {
                var kept=new JsonArray();
                for(var cell:row.getAsJsonArray())if(!retired.contains(cell.getAsJsonObject().get("position")))
                {kept.add(cell);occupied.add(cell.getAsJsonObject().get("position"));}
                steps.add(kept);
            }
            require(steps.size()>0,"Original gate collision phases required");
            int left=(int)Math.round(position.get(0).getAsDouble()-16.5);
            for(int x=left;x<left+33;x++)for(int y=-1067;y<-1062;y++)
            {
                var at=new JsonArray();at.add(x);at.add(y);at.add(301);
                require(!occupied.contains(at),"New lower proxy cannot replace an original upper cell");
                var cell=new JsonObject();cell.add("position",at);cell.addProperty("closed","minecraft:barrier");cell.addProperty("open","minecraft:air");
                steps.get(0).getAsJsonArray().add(cell);
            }
            gate.add("collision_steps",steps);var stack=gate.getAsJsonObject("hangar_stack");
            require(!stack.has("leaf_lower_extension_m")||stack.get("leaf_lower_extension_m").getAsDouble()==0,"Only original unextended leaves may be refitted");
            stack.remove("floor_seal");stack.addProperty("leaf_lower_extension_m",5);
        }
        require(found.equals(Set.of(0,1,2)),"All three original front gates required");
    }
    private static byte[] read(Path file,int limit)throws IOException
    {require(Files.isRegularFile(file)&&Files.size(file)<=limit,"Bounded explicit installation source required");return Files.readAllBytes(file);}
    private static JsonObject json(byte[] bytes){return JsonParser.parseString(new String(bytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();}
    private static String binding(byte[] bytes)
    {try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}}
    private static void require(boolean okay,String why){if(!okay)throw new IllegalArgumentException(why);}
    private CarrierEquipmentUpdateR53(){}
}

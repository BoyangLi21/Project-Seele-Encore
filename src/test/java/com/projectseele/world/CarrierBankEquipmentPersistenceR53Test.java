package com.projectseele.world;

import com.google.gson.JsonParser;
import java.nio.file.*;
import java.util.UUID;
import net.minecraft.nbt.*;

/** Reads the selected saved bank stop; every mutation stays in an in-memory NBT copy. */
public final class CarrierBankEquipmentPersistenceR53Test
{
    public static void main(String[] args)throws Exception
    {
        CompoundTag source;try(var in=Files.newInputStream(Path.of(args[0]))){source=NbtIo.readCompressed(in).getCompound("data");}
        var saved=NervRouteRuntimeStateR52.load(source);check(saved.fault().isEmpty(),"Actual source state already faulty");
        int variant=args.length>2?Integer.parseInt(args[2]):1;
        var bank=saved.job(variant);var head=TagParser.parseTag(JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject().get("head").getAsString());
        var marker=new CompoundTag();marker.putInt("Version",2);marker.putInt("Variant",variant);marker.putString("Source",NervLegacyBankClearanceR53.SOURCE_SHA);
        marker.putUUID("Carrier",NervOriginalCarrierR52.proposedIdentityR52(bank.snapshot().original().epoch(),bank.snapshot().original().eva()));
        var rows=new ListTag();for(var job:saved.jobs())rows.add(NervRouteRuntimeStateR52.encode(job.snapshot()));marker.put("Snapshots",rows);
        var preserved=new ListTag();for(var job:saved.jobs()){var row=new CompoundTag();row.putInt("Variant",job.snapshot().original().variant());row.putString("Phase",job.phase().name());row.putString("Waiting",job.waiting());row.put("Owner",job.ownerData());preserved.add(row);}marker.put("Jobs",preserved);
        marker.put("Head",head);marker.put("Clock",bank.ownerData().getCompound("ContinuousClockR52").copy());marker.put("Phase",bank.ownerData().getCompound(NervLaunchPhasesR53.KEY).copy());marker.putDouble("Distance",bank.ownerData().getDouble("ContinuousDistanceR52"));
        var pending=new CompoundTag();pending.putInt("Version",1);pending.putString("Bundle",saved.installationBundle());pending.putString("SHA","a".repeat(64));pending.putLong("Epoch",saved.epoch());pending.putString("Directory",saved.fingerprint());pending.putBoolean("Restoring",true);pending.putBoolean("CarrierEquipmentUpdate",true);pending.putInt("Attempts",1);pending.put("BankCurbRefit",marker);
        var candidate=source.copy();candidate.put("PendingInstallation",pending);
        var loaded=NervRouteRuntimeStateR52.load(candidate);check(loaded.fault().isEmpty(),loaded.fault());
        var roundTrip=NervRouteRuntimeStateR52.load(loaded.save(new CompoundTag()));check(roundTrip.fault().isEmpty()&&roundTrip.job(variant).equals(bank)&&roundTrip.pendingBankCurbRefitR53().equals(marker),"Pending bank roundtrip changed original state");
        var changed=candidate.copy();bankRow(changed,variant).getCompound("OwnerData").getCompound("ContinuousClockR52").putDouble("SpeedMps",1);reject(changed);
        changed=candidate.copy();bankRow(changed,variant).getCompound("Snapshot").putUUID("Task",UUID.randomUUID());reject(changed);
        changed=candidate.copy();bankRow(changed,(variant+1)%3).getCompound("OwnerData").putString("Unexpected","changed");reject(changed);
        changed=candidate.copy();changed.getCompound("PendingInstallation").remove("BankCurbRefit");reject(changed);
        System.out.println("Bank equipment pending NBT roundtrip and four mutation rejections passed; world unchanged");
    }
    private static CompoundTag bankRow(CompoundTag tag,int variant){for(var raw:tag.getList("Jobs",Tag.TAG_COMPOUND)){var row=(CompoundTag)raw;if(row.getCompound("Snapshot").getInt("Variant")==variant)return row;}throw new AssertionError("Original bank job missing");}
    private static void reject(CompoundTag tag){check(!NervRouteRuntimeStateR52.load(tag).fault().isEmpty(),"Changed pending state accepted");}
    private static void check(boolean condition,String why){if(!condition)throw new AssertionError(why);}
    private CarrierBankEquipmentPersistenceR53Test(){}
}

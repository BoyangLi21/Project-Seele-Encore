package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;

/** Relocation must never mint another machine or relax non-positional ownership. */
public final class CityRelocationTest
{
    private static void check(boolean ok, String reason)
    { if (!ok) throw new AssertionError(reason); }

    public static void main(String[] args) throws Exception
    {
        BlockPos origin = new BlockPos(30, 80, 220), source = new BlockPos(-130, 80, 60);
        BlockPos delta = new BlockPos(-120, 0, 80), target = source.offset(delta);
        var old = new CityRigidTopologyR45.Tower(0, "generated", source, 56, 9, source.offset(12, 0, 0),
                new long[0], -9, 9, -9, 9, -37);
        var moved = new CityRigidTopologyR45.Tower(0, "generated", target, 56, 9, old.core().offset(delta),
                new long[0], -9, 9, -9, 9, -37, source);
        check(old.owner("actual-world", origin).equals(moved.owner("actual-world", origin)), "Relocation changed owner");
        check(!old.owner("actual-world", origin).equals(moved.owner("another-world", origin)), "World identity lost");
        CompoundTag original = new CompoundTag();
        original.putLong("Centre", source.asLong()); original.putInt("Height", 56);
        original.putLong("FixedCorePos", old.core().asLong());
        original.putLongArray("NegativeDomeAnchorMask", new long[] {new BlockPos(-142, 21, 48).asLong()});
        CompoundTag current = original.copy();
        current.putLong("IdentityCentre", source.asLong()); current.putLong("Centre", target.asLong());
        current.putLong("FixedCorePos", moved.core().asLong());
        current.putLongArray("NegativeDomeAnchorMask", new long[] {new BlockPos(-142, 21, 48).offset(delta).asLong()});
        check(CityRigidTopologyR45.retainsOriginalFrame(original, current), "Complete translated frame rejected");
        check(CityRigidTopologyR45.retainsOriginalFrame(original, original), "Legacy frame rejected");
        current.putInt("Height", 55);
        check(!CityRigidTopologyR45.retainsOriginalFrame(original, current), "Changed building cargo accepted");
        current.putInt("Height", 56); current.putLong("IdentityCentre", target.asLong());
        check(!CityRigidTopologyR45.retainsOriginalFrame(original, current), "Replacement identity accepted");
        CompoundTag cargo = new CompoundTag(), epoch = new CompoundTag();
        java.util.UUID journey = java.util.UUID.randomUUID();
        cargo.putUUID("RelocationSnapshotJourney", journey); epoch.putUUID("Journey", journey);
        check(CityRigidGenerationR45.useRelocationSnapshot(cargo, epoch), "Current relocated inventories lost to old journal");
        epoch.putUUID("Journey", java.util.UUID.randomUUID());
        check(!CityRigidGenerationR45.useRelocationSnapshot(cargo, epoch), "Later completed inventory changes ignored");
        check(!CityRigidGenerationR45.useRelocationSnapshot(cargo, new CompoundTag()), "Missing epoch treated as matching");
        if (args.length == 1)
        {
            var candidate = java.nio.file.Path.of(args[0]);
            String topology = "dimensions/projectseele/geofront/data/projectseele_city_rigid_topology_r45_8246338109520.dat";
            var beforeTag = net.minecraft.nbt.NbtIo.readCompressed(candidate.resolve("before").resolve(topology).toFile()).getCompound("data");
            var afterTag = net.minecraft.nbt.NbtIo.readCompressed(candidate.resolve("after").resolve(topology).toFile()).getCompound("data");
            var before = CityRigidTopologyR45.towers(beforeTag); var after = CityRigidTopologyR45.towers(afterTag);
            check(before.size() == 100 && after.size() == 100, "Actual object count changed");
            int movedCount = 0;
            for (int i = 0; i < before.size(); i++)
            {
                check(before.get(i).owner(beforeTag.getString("WorldUUID"), origin)
                        .equals(after.get(i).owner(afterTag.getString("WorldUUID"), origin)), "Actual owner changed at " + i);
                check(before.get(i).retractedY() == after.get(i).retractedY(), "Actual retraction endpoint changed");
                if (!before.get(i).centre().equals(after.get(i).centre())) movedCount++;
            }
            check(movedCount == 30, "Wrong actual translated component count");
            var ledger = net.minecraft.nbt.NbtIo.readCompressed(candidate.resolve("preserved")
                    .resolve("projectseele_city_rigid_control_r45_8246338109520.dat").toFile()).getCompound("data");
            CityLowriseAddonR48.validateRetainedLedger(afterTag, ledger);
            var modern = ledger.copy(); var entries = new net.minecraft.nbt.ListTag();
            for (int i = 0; i < 100; i++) entries.add(net.minecraft.nbt.StringTag.valueOf(i + ".dat"));
            modern.put("JournalEntries", entries); modern.remove("JournalSHA256s");
            CityLowriseAddonR48.validateRetainedLedger(afterTag, modern);
            System.out.println("Actual candidate: 100 original owners, 30 translations, retained endpoints accepted by production topology parser");
        }
        System.out.println("City relocation identity, frame and inventory epoch checks passed");
    }
}

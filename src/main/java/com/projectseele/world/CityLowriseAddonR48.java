package com.projectseele.world;

import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.Tag;

/** Four explicitly restored original control-cell templates, as one city's additional WAL members. */
public final class CityLowriseAddonR48
{
    public static final int ORIGINAL_COUNT = 96;
    public static final int EXTENDED_COUNT = 100;
    private static final List<BlockPos> CENTRES = List.of(new BlockPos(-10,80,180), new BlockPos(-10,80,260),
            new BlockPos(70,80,180), new BlockPos(70,80,260));
    private static final List<String> IDS = List.of("r48_launch_control_nw", "r48_launch_control_sw",
            "r48_launch_control_ne", "r48_launch_control_se");
    private CityLowriseAddonR48() { }

    /** No marker preserves the original exactly-96 contract; arbitrary counts never become valid. */
    public static void validate(CompoundTag topology, List<CityRigidTopologyR45.Tower> parsed)
    {
        if (parsed.size() == ORIGINAL_COUNT && !topology.contains("LowriseAddonR48")) return;
        require(parsed.size() == EXTENDED_COUNT, "Only the explicit original96 plus four approved low-rise cells are allowed");
        CompoundTag addon = topology.getCompound("LowriseAddonR48");
        require(addon.getInt("Version") == 1 && addon.getString("Stage").equals("INSTALLED")
                && addon.getBoolean("RootApprovedSourceTemplate") && addon.getBoolean("ExactComponentMigrationPassed")
                && addon.getBoolean("FullSweepVerified")
                && addon.getString("WorldUUID").equals(topology.getString("WorldUUID"))
                && addon.getLong("Origin") == topology.getLong("Origin"), "Low-rise component installation proof is incomplete/foreign");
        var originals = addon.getList("Original96Towers", Tag.TAG_COMPOUND);
        var rows = topology.getList("Towers", Tag.TAG_COMPOUND);
        require(originals.size() == ORIGINAL_COUNT && rows.size() == EXTENDED_COUNT, "Missing exact retained original96 topology");
        CompoundTag before = addon.getCompound("OriginalSettledLedger");
        require(before.getString("Phase").equals("IDLE") && before.getInt("Depth")==0 && before.getInt("Target")==0
                && before.getInt("Queued")==-1 && before.getInt("SavedPlans")==ORIGINAL_COUNT && before.getInt("Created")==ORIGINAL_COUNT
                && before.getString("WorldUUID").equals(topology.getString("WorldUUID"))
                && before.getLong("Origin")==topology.getLong("Origin"), "Missing unchanged settled original96 installation epoch");
        Set<UUID> owners = new HashSet<>();
        BlockPos origin = BlockPos.of(topology.getLong("Origin"));
        for (int i=0; i<ORIGINAL_COUNT; i++)
        {
            require(originals.getCompound(i).equals(rows.getCompound(i)), "An original96 owner/frame/anchor was changed");
            require(owners.add(owner(topology.getString("WorldUUID"), origin, parsed.get(i).centre())), "Duplicate original city owner");
        }
        for (int i=0; i<CENTRES.size(); i++)
        {
            var spec = parsed.get(ORIGINAL_COUNT+i); var row = rows.getCompound(ORIGINAL_COUNT+i);
            require(spec.index()==ORIGINAL_COUNT+i && spec.kind().equals("r48_launch_control")
                    && spec.centre().equals(CENTRES.get(i)) && spec.height()==26 && spec.half()==7
                    && spec.minX()==-7 && spec.maxX()==7 && spec.minZ()==-7 && spec.maxZ()==7
                    && spec.retractedY()==-7 && spec.core()==null, "Unapproved low-rise template/frame/endpoint");
            require(row.getString("R48TemplateId").equals(IDS.get(i))
                    && row.getString("R48SourceTemplate").equals("ThirdTokyoSurfaceBuilder.buildLaunchControlBlock")
                    && row.getInt("R48FullComponentHeight")==26, "Low-rise component lacks its exact template provenance");
            UUID owner = owner(topology.getString("WorldUUID"), origin, spec.centre());
            require(row.hasUUID("R48Owner") && row.getUUID("R48Owner").equals(owner) && owners.add(owner), "New independent low-rise owner mismatch");
            long[] anchors = CityRigidTopologyR45.externalNegativeAnchors(spec.centre(),7).stream().mapToLong(BlockPos::asLong).toArray();
            require(java.util.Arrays.equals(anchors,spec.fixedAnchors()), "Low-rise complete external anchors changed");
            for (int peer=0; peer<spec.index(); peer++)
            {
                var other=parsed.get(peer);
                boolean separated=spec.centre().getX()+spec.maxX()<other.centre().getX()+other.minX()
                        ||spec.centre().getX()+spec.minX()>other.centre().getX()+other.maxX()
                        ||spec.centre().getZ()+spec.maxZ()<other.centre().getZ()+other.minZ()
                        ||spec.centre().getZ()+spec.minZ()>other.centre().getZ()+other.maxZ();
                require(separated,"Low-rise sweep overlaps an original/peer city footprint");
            }
        }
    }

    private static UUID owner(String world, BlockPos origin, BlockPos centre)
    { return UUID.nameUUIDFromBytes((world+"/"+origin+"/rigid-owner/"+centre).getBytes(StandardCharsets.UTF_8)); }

    /** Original imported floors are Y81; their Y80 street covers remain distinct from their cargo. */
    public static boolean retainsRaisedStreetCover(CityRigidTopologyR45.Tower spec)
    { return spec.index() >= 93 && spec.index() < ORIGINAL_COUNT; }

    /** Retain the last original96 journal after installation until the first genuine100 journey. */
    public static boolean hasCommittedRecipeJournal(int savedPlans, int index, int currentObjects)
    {
        return savedPlans == currentObjects || currentObjects == EXTENDED_COUNT
                && savedPlans == ORIGINAL_COUNT && index < ORIGINAL_COUNT;
    }

    /** Installation extends a settled original; it never resets/adapts its historical progress or inverse. */
    public static void validateRetainedLedger(CompoundTag topology, CompoundTag ledger)
    {
        if (!topology.contains("LowriseAddonR48")) return;
        validateHeaderAndState(topology,ledger);
        if (ledger.getString("Phase").equals("IDLE")) effectiveCommittedLedger(topology,ledger);
    }

    private static void validateHeaderAndState(CompoundTag topology, CompoundTag ledger)
    {
        require(!ledger.isEmpty() && ledger.getInt("Version")==1
                && ledger.getString("WorldUUID").equals(topology.getString("WorldUUID"))
                && ledger.getLong("Origin")==topology.getLong("Origin"),
                "Missing/foreign low-rise city ledger; no recipe/legacy replacement");
        CityCreateDistrictR45.validateLedgerStateR48(ledger,EXTENDED_COUNT);
    }

    /** Snapshot only the real preceding committed epoch before begin overwrites its live journey fields. */
    public static CompoundTag captureCommittedLedger(CompoundTag topology, CompoundTag ledger)
    {
        require(topology.contains("LowriseAddonR48") && ledger.getString("Phase").equals("IDLE"),"Only the original begin's settled epoch can be inherited");
        validateHeaderAndState(topology,ledger);
        CompoundTag captured=effectiveCommittedLedger(topology,ledger).copy();
        captured.remove("PreviousCommittedLedgerR48"); // One durable epoch, not a recursively growing history tree.
        captured.putInt("Queued",-1); captured.putString("QueueFault","");
        return captured;
    }

    /** Called after the existing detached-cargo return; unplaced/canceled preparation uses the actual preceding journal. */
    public static CompoundTag recipeLedger(CompoundTag topology, CompoundTag current)
    {
        if (!topology.contains("LowriseAddonR48")) return current;
        validateHeaderAndState(topology,current);
        return effectiveCommittedLedger(topology,current);
    }

    private static CompoundTag effectiveCommittedLedger(CompoundTag topology,CompoundTag current)
    {
        if (current.getBoolean("WorldTouched")) return requireCommittedEpoch(topology,current);
        CompoundTag previous=current.getCompound("PreviousCommittedLedgerR48");
        require(!previous.isEmpty(),"Unplaced preparation/cancel lacks its exact preceding committed epoch; no initial96/template fallback");
        validateHeaderAndState(topology,previous);
        require(previous.getInt("Depth")==current.getInt("Depth"),"Preceding committed epoch differs from the untouched current source endpoint");
        return requireCommittedEpoch(topology,previous);
    }

    private static CompoundTag requireCommittedEpoch(CompoundTag topology,CompoundTag ledger)
    {
        require(ledger.getString("Phase").equals("IDLE"),"Recipe epoch must be the actual static commit, not a partial active journey");
        CompoundTag original=topology.getCompound("LowriseAddonR48").getCompound("OriginalSettledLedger");
        if (ledger.getInt("SavedPlans")==EXTENDED_COUNT)
        {
            int endpoint=ledger.getBoolean("Rollback")?ledger.getInt("JourneySourceDepth"):ledger.getInt("JourneyTargetDepth");
            require(ledger.getBoolean("WorldTouched") && ledger.getList("JournalSHA256s",Tag.TAG_STRING).size()==EXTENDED_COUNT
                    && ledger.hasUUID("Journey") && original.hasUUID("Journey")
                    && !ledger.getUUID("Journey").equals(original.getUUID("Journey"))
                    && ledger.getInt("Depth")==endpoint && ledger.getInt("Target")==endpoint
                    && ledger.getInt("Index")==0 && ledger.getInt("Cursor")==0
                    && ledger.getInt("JourneySourceDepth")!=ledger.getInt("JourneyTargetDepth"),
                    "Counts alone cannot convert the old96 journal into a committed100 inverse");
            // Existing commit/reconcile owns rollback/Created/progress semantics; no new successful-MOVE gate.
            return ledger;
        }
        CompoundTag observed = ledger.copy();
        require(ledger.contains("Queued",Tag.TAG_INT) && ledger.contains("QueueFault",Tag.TAG_STRING)
                && (ledger.getInt("Queued")==-1 || ledger.getInt("Queued")==0 || ledger.getInt("Queued")==312),
                "Invalid pending original city request");
        // The existing request path writes only this pending intent before begin; a cold hold/reload is legitimate.
        observed.putInt("Queued",original.getInt("Queued"));
        observed.putString("QueueFault",original.getString("QueueFault"));
        require(!original.isEmpty() && original.getString("Phase").equals("IDLE")
                && original.getInt("Depth")==0 && original.getInt("Target")==0 && original.getInt("Queued")==-1
                && original.getInt("SavedPlans")==ORIGINAL_COUNT && original.getInt("Created")==ORIGINAL_COUNT
                && original.getList("JournalSHA256s",Tag.TAG_STRING).size()==ORIGINAL_COUNT
                && observed.equals(original),"Original settled96 ledger changed before the first complete100 journey; no template fallback/reset");
        return ledger;
    }

    private static void require(boolean value,String reason)
    { if(!value)throw new IllegalStateException(reason); }
}

package com.projectseele.world;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.saveddata.SavedData;

/** Durable plan and per-feature receipts for the GeoFront exterior fabric. */
public final class GeoFrontFabricSavedData extends SavedData
{
    private static final String DATA_NAME =
            "projectseele_geofront_fabric_f2_e3";
    private static final int DATA_VERSION = 2;

    private Lifecycle lifecycle = Lifecycle.DRAFT;
    private int formatVersion;
    private int fabricRevision;
    private int facilityEpoch;
    private String regionId = "";
    private String regionCoreHash = "";
    private String planHash = "";
    private String ownerUnionHash = "";
    private String ownerGuardHash = "";
    private String failure = "";
    private boolean programmeActive;
    private boolean westSeamOpen;
    private final Map<String, FeatureRecord> features =
            new LinkedHashMap<>();
    private final Map<String, GeoFrontFabricPlan.FeatureContract>
            committedContracts = new LinkedHashMap<>();
    private final Map<String, GeoFrontFabricPlan.FeatureContract>
            previousContracts = new LinkedHashMap<>();
    private boolean reconciliationActive;
    private int reconciliationPass;
    private int reconciliationFeatureIndex;
    private long reconciliationCursor;
    private long reconciliationVisited;
    private long reconciliationChanged;
    private long rescueCavernChunkCursor;

    public static GeoFrontFabricSavedData get(ServerLevel level)
    {
        return level.getDataStorage().computeIfAbsent(
                GeoFrontFabricSavedData::load,
                GeoFrontFabricSavedData::new, DATA_NAME);
    }

    public static GeoFrontFabricSavedData load(CompoundTag tag)
    {
        GeoFrontFabricSavedData data = new GeoFrontFabricSavedData();
        int version = tag.contains("Version", Tag.TAG_INT)
                ? tag.getInt("Version") : DATA_VERSION;
        if (version != 1 && version != DATA_VERSION)
        {
            data.lifecycle = Lifecycle.FAILED;
            data.failure = "unsupported fabric saved-data version "
                    + version;
            return data;
        }
        data.lifecycle = Lifecycle.parse(tag.getString("Lifecycle"));
        data.formatVersion = tag.getInt("FormatVersion");
        data.fabricRevision = tag.getInt("FabricRevision");
        data.facilityEpoch = tag.getInt("FacilityEpoch");
        data.regionId = tag.getString("RegionId");
        data.regionCoreHash = tag.getString("RegionCoreHash");
        data.planHash = tag.getString("PlanHash");
        data.ownerUnionHash = tag.getString("OwnerUnionHash");
        data.ownerGuardHash = tag.getString("OwnerGuardHash");
        data.failure = tag.getString("Failure");
        data.programmeActive = tag.getBoolean("ProgrammeActive");
        data.westSeamOpen = tag.getBoolean("WestSeamOpen");
        data.rescueCavernChunkCursor = Math.max(0L,
                tag.getLong("RescueCavernChunkCursor"));

        ListTag list = tag.getList("Features", Tag.TAG_COMPOUND);
        for (int index = 0; index < list.size(); index++)
        {
            CompoundTag featureTag = list.getCompound(index);
            String id = featureTag.getString("Id");
            if (id.isBlank() || data.features.containsKey(id))
            {
                continue;
            }
            data.features.put(id, new FeatureRecord(
                    FeatureState.parse(featureTag.getString("State")),
                    featureTag.getString("Revision"),
                    featureTag.getInt("Priority"),
                    featureTag.getString("ContractHash"),
                    featureTag.getString("ResolvedMaskHash"),
                    featureTag.getString("ContentHash"),
                    Math.max(0L, featureTag.getLong("Cursor")),
                    Math.max(0L, featureTag.getLong("Visited")),
                    Math.max(0L, featureTag.getLong("Changed")),
                    featureTag.getString("Failure")));
        }
        if (version >= 2)
        {
            readContracts(tag.getList(
                    "CommittedContracts", Tag.TAG_COMPOUND),
                    data.committedContracts);
            readContracts(tag.getList(
                    "PreviousContracts", Tag.TAG_COMPOUND),
                    data.previousContracts);
            CompoundTag reconciliation =
                    tag.getCompound("Reconciliation");
            data.reconciliationActive =
                    reconciliation.getBoolean("Active");
            data.reconciliationPass = Math.max(0,
                    Math.min(1, reconciliation.getInt("Pass")));
            data.reconciliationFeatureIndex = Math.max(0,
                    reconciliation.getInt("FeatureIndex"));
            data.reconciliationCursor = Math.max(0L,
                    reconciliation.getLong("Cursor"));
            data.reconciliationVisited = Math.max(0L,
                    reconciliation.getLong("Visited"));
            data.reconciliationChanged = Math.max(0L,
                    reconciliation.getLong("Changed"));
        }
        if (data.committedContracts.isEmpty()
                && !data.features.isEmpty())
        {
            data.migrateLegacyContracts();
        }
        return data;
    }

    public void commit(FacilityV2SavedData facility)
    {
        if (!facility.commissioned())
        {
            throw new IllegalStateException(
                    "FacilitySchema v2 is not commissioned");
        }
        FacilitySchemaV2.ResolvedManifest manifest = facility.manifest();
        String expectedPlan = FacilityV2Hashing.fabricPlanHash(
                facility.regionCoreHash(),
                java.util.List.of(GeoFrontFabricPlan.Feature.values()));
        if (this.lifecycle != Lifecycle.DRAFT)
        {
            if (!sameFacilityIdentity(facility))
            {
                throw new IllegalStateException(
                        "A GeoFrontFabric receipt belongs to another "
                                + "facility identity");
            }
            if (this.planHash.equals(expectedPlan)
                    && this.formatVersion
                    == GeoFrontFabricPlan.FORMAT_VERSION
                    && this.fabricRevision
                    == GeoFrontFabricPlan.FABRIC_REVISION
                    && this.committedContracts.equals(
                    currentContractMap()))
            {
                return;
            }
            stageReconciliation(facility, expectedPlan);
            return;
        }

        this.lifecycle = Lifecycle.COMMITTED;
        this.formatVersion = GeoFrontFabricPlan.FORMAT_VERSION;
        this.fabricRevision = GeoFrontFabricPlan.FABRIC_REVISION;
        this.facilityEpoch = FacilitySchemaV2.EPOCH;
        this.regionId = FacilitySchemaV2.REGION_ID;
        this.regionCoreHash = facility.regionCoreHash();
        this.planHash = expectedPlan;
        this.ownerUnionHash =
                FacilityV2Hashing.fabricOwnerMaskHash(manifest, 0);
        this.ownerGuardHash =
                FacilityV2Hashing.fabricOwnerMaskHash(manifest, 1);
        this.failure = "";
        this.programmeActive = false;
        this.westSeamOpen = false;
        this.features.clear();
        this.committedContracts.clear();
        this.committedContracts.putAll(currentContractMap());
        this.previousContracts.clear();
        this.reconciliationActive = false;
        this.reconciliationPass = 0;
        this.reconciliationFeatureIndex = 0;
        this.reconciliationCursor = 0L;
        this.reconciliationVisited = 0L;
        this.reconciliationChanged = 0L;
        this.rescueCavernChunkCursor = 0L;
        for (GeoFrontFabricPlan.Feature feature
                : GeoFrontFabricPlan.Feature.values())
        {
            this.features.put(feature.id(), new FeatureRecord(
                    FeatureState.PENDING, feature.revision(),
                    feature.priority(), feature.contractHash(),
                    this.ownerGuardHash, "", 0L, 0L, 0L, ""));
        }
        this.setDirty();
    }

    public boolean validFor(FacilityV2SavedData facility)
    {
        return facility.commissioned()
                && this.lifecycle != Lifecycle.DRAFT
                && this.lifecycle != Lifecycle.FAILED
                && this.formatVersion == GeoFrontFabricPlan.FORMAT_VERSION
                && this.fabricRevision
                == GeoFrontFabricPlan.FABRIC_REVISION
                && this.facilityEpoch == FacilitySchemaV2.EPOCH
                && FacilitySchemaV2.REGION_ID.equals(this.regionId)
                && sameContractsIgnoringHash(this.committedContracts,
                currentContractMap());
    }

    private boolean sameFacilityIdentity(FacilityV2SavedData facility)
    {
        return facility.commissioned()
                && this.facilityEpoch == FacilitySchemaV2.EPOCH
                && FacilitySchemaV2.REGION_ID.equals(this.regionId);
    }

    /** Stored plan/owner digests are receipts only; never a reason to refuse saved work. */
    private static boolean sameContractsIgnoringHash(
            Map<String, GeoFrontFabricPlan.FeatureContract> stored,
            Map<String, GeoFrontFabricPlan.FeatureContract> current)
    {
        if (!stored.keySet().equals(current.keySet()))
        {
            return false;
        }
        for (GeoFrontFabricPlan.FeatureContract contract : current.values())
        {
            GeoFrontFabricPlan.FeatureContract saved =
                    stored.get(contract.id());
            if (saved == null
                    || !saved.revision().equals(contract.revision())
                    || saved.priority() != contract.priority()
                    || saved.authoredWork() != contract.authoredWork()
                    || saved.geometryVersion()
                    != contract.geometryVersion())
            {
                return false;
            }
        }
        return true;
    }

    private void stageReconciliation(
            FacilityV2SavedData facility, String expectedPlan)
    {
        if (this.reconciliationActive || activeFeature().isPresent())
        {
            throw new IllegalStateException(
                    "GeoFrontFabric cannot replace a plan while work "
                            + "is active");
        }
        if (this.committedContracts.isEmpty())
        {
            migrateLegacyContracts();
        }
        this.previousContracts.clear();
        this.previousContracts.putAll(this.committedContracts);
        this.committedContracts.clear();
        this.committedContracts.putAll(currentContractMap());
        this.formatVersion = GeoFrontFabricPlan.FORMAT_VERSION;
        this.fabricRevision = GeoFrontFabricPlan.FABRIC_REVISION;
        this.facilityEpoch = FacilitySchemaV2.EPOCH;
        this.regionId = FacilitySchemaV2.REGION_ID;
        this.regionCoreHash = facility.regionCoreHash();
        this.planHash = expectedPlan;
        this.ownerUnionHash = FacilityV2Hashing.fabricOwnerMaskHash(
                facility.manifest(), 0);
        this.ownerGuardHash = FacilityV2Hashing.fabricOwnerMaskHash(
                facility.manifest(), 1);
        this.features.clear();
        for (GeoFrontFabricPlan.Feature feature
                : GeoFrontFabricPlan.Feature.values())
        {
            this.features.put(feature.id(), new FeatureRecord(
                    FeatureState.PENDING, feature.revision(),
                    feature.priority(), feature.contractHash(),
                    this.ownerGuardHash, "", 0L, 0L, 0L, ""));
        }
        this.reconciliationActive = true;
        this.reconciliationPass =
                this.previousContracts.isEmpty() ? 1 : 0;
        this.reconciliationFeatureIndex = 0;
        this.reconciliationCursor = 0L;
        this.reconciliationVisited = 0L;
        this.reconciliationChanged = 0L;
        this.rescueCavernChunkCursor = 0L;
        this.lifecycle = Lifecycle.RECONCILING;
        this.programmeActive = true;
        this.failure = "";
        this.setDirty();
    }

    public void startProgramme()
    {
        requireCommitted();
        if (this.reconciliationActive)
        {
            return;
        }
        this.programmeActive = true;
        if (this.lifecycle == Lifecycle.COMPLETE)
        {
            this.programmeActive = false;
        }
        this.setDirty();
    }

    public void begin(GeoFrontFabricPlan.Feature feature)
    {
        requireCommitted();
        if (this.reconciliationActive)
        {
            throw new IllegalStateException(
                    "GeoFrontFabric plan reconciliation is active");
        }
        if (activeFeature().isPresent())
        {
            throw new IllegalStateException(
                    "Another GeoFront fabric feature is already building");
        }
        for (GeoFrontFabricPlan.Feature dependency
                : feature.dependencies())
        {
            if (requireFeature(dependency).state()
                    != FeatureState.COMPLETE)
            {
                throw new IllegalStateException(feature.id()
                        + " requires completed " + dependency.id());
            }
        }
        FeatureRecord record = requireFeature(feature);
        if (record.state() != FeatureState.PENDING)
        {
            throw new IllegalStateException(feature.id() + " is "
                    + record.state() + ", expected PENDING");
        }
        if (!record.revision().equals(feature.revision())
                || record.priority() != feature.priority())
        {
            throw new IllegalStateException(
                    feature.id() + " persisted contract mismatch");
        }
        this.features.put(feature.id(), record.withState(
                FeatureState.BUILDING, ""));
        this.lifecycle = Lifecycle.BUILDING;
        this.setDirty();
    }

    /**
     * Rescue-world scheduler entry point.  It preserves the committed feature
     * contract but deliberately bypasses the normal exterior dependency chain
     * so player-facing routes and scenery can be authored before the enormous
     * cavern shell finishes.  The deterministic owner guards in blockAt still
     * prevent facility overlap.
     */
    public void beginRescueFeature(GeoFrontFabricPlan.Feature feature)
    {
        requireCommitted();
        if (this.reconciliationActive)
        {
            throw new IllegalStateException(
                    "GeoFrontFabric plan reconciliation is active");
        }
        if (activeFeature().isPresent())
        {
            throw new IllegalStateException(
                    "Another GeoFront fabric feature is already building");
        }
        FeatureRecord record = requireFeature(feature);
        if (record.state() != FeatureState.PENDING)
        {
            throw new IllegalStateException(feature.id() + " is "
                    + record.state() + ", expected PENDING");
        }
        if (!record.revision().equals(feature.revision())
                || record.priority() != feature.priority())
        {
            throw new IllegalStateException(
                    feature.id() + " persisted contract mismatch");
        }
        this.features.put(feature.id(), record.withState(
                FeatureState.BUILDING, ""));
        this.lifecycle = Lifecycle.BUILDING;
        this.programmeActive = false;
        this.setDirty();
    }

    /**
     * Pauses the current deterministic cursor without discarding any work.
     * Used only by the local rescue scheduler to move the multi-million-block
     * cavern shell behind the immediately reviewable scene features.
     */
    public GeoFrontFabricPlan.Feature suspendActiveForRescue()
    {
        GeoFrontFabricPlan.Feature feature =
                activeFeature().orElseThrow(() ->
                        new IllegalStateException(
                                "No active GeoFront feature to suspend"));
        FeatureRecord record = requireFeature(feature);
        this.features.put(feature.id(), record.withState(
                FeatureState.PENDING, ""));
        this.lifecycle = Lifecycle.COMMITTED;
        this.programmeActive = false;
        this.setDirty();
        return feature;
    }

    public void update(GeoFrontFabricPlan.Feature feature, long cursor,
                       long visited, long changed)
    {
        FeatureRecord record = requireFeature(feature);
        if (record.state() != FeatureState.BUILDING)
        {
            throw new IllegalStateException(
                    feature.id() + " is not BUILDING");
        }
        this.features.put(feature.id(),
                record.withProgress(cursor, visited, changed));
        this.setDirty();
    }

    public long rescueCavernChunkCursor()
    {
        return this.rescueCavernChunkCursor;
    }

    public void updateRescueCavernChunkCursor(long cursor)
    {
        this.rescueCavernChunkCursor = Math.max(0L, cursor);
        this.setDirty();
    }

    public void clearRescueCavernChunkCursor()
    {
        if (this.rescueCavernChunkCursor != 0L)
        {
            this.rescueCavernChunkCursor = 0L;
            this.setDirty();
        }
    }

    public void complete(GeoFrontFabricPlan.Feature feature)
    {
        FeatureRecord record = requireFeature(feature);
        if (record.state() != FeatureState.BUILDING)
        {
            throw new IllegalStateException(
                    feature.id() + " is not BUILDING");
        }
        this.features.put(feature.id(), new FeatureRecord(
                FeatureState.COMPLETE, record.revision(), record.priority(),
                record.contractHash(), record.resolvedMaskHash(),
                record.contractHash(), record.cursor(), record.visited(),
                record.changed(), ""));
        boolean allComplete = this.features.values().stream()
                .allMatch(value -> value.state() == FeatureState.COMPLETE);
        this.lifecycle = allComplete
                ? Lifecycle.COMPLETE : Lifecycle.COMMITTED;
        if (allComplete)
        {
            this.programmeActive = false;
        }
        this.setDirty();
    }

    public void fail(GeoFrontFabricPlan.Feature feature, String reason)
    {
        FeatureRecord record = requireFeature(feature);
        this.features.put(feature.id(), record.withState(
                FeatureState.FAILED, reason));
        this.lifecycle = Lifecycle.FAILED;
        this.programmeActive = false;
        this.failure = reason;
        this.setDirty();
    }

    public Optional<GeoFrontFabricPlan.Feature> activeFeature()
    {
        return this.features.entrySet().stream()
                .filter(entry -> entry.getValue().state()
                        == FeatureState.BUILDING)
                .map(entry -> GeoFrontFabricPlan.Feature.byId(
                        entry.getKey()))
                .findFirst();
    }

    public Optional<GeoFrontFabricPlan.Feature> nextPending()
    {
        for (GeoFrontFabricPlan.Feature feature
                : GeoFrontFabricPlan.Feature.values())
        {
            FeatureRecord record = requireFeature(feature);
            if (record.state() != FeatureState.PENDING)
            {
                continue;
            }
            boolean ready = feature.dependencies().stream()
                    .allMatch(dependency -> requireFeature(dependency)
                            .state() == FeatureState.COMPLETE);
            if (ready)
            {
                return Optional.of(feature);
            }
        }
        return Optional.empty();
    }

    public FeatureRecord requireFeature(
            GeoFrontFabricPlan.Feature feature)
    {
        FeatureRecord record = this.features.get(feature.id());
        if (record == null)
        {
            throw new IllegalStateException(
                    "Missing fabric feature receipt " + feature.id());
        }
        return record;
    }

    public boolean reconciliationActive()
    {
        return this.reconciliationActive;
    }

    public ReconciliationProgress reconciliationProgress()
    {
        return new ReconciliationProgress(this.reconciliationPass,
                this.reconciliationFeatureIndex,
                this.reconciliationCursor,
                this.reconciliationVisited,
                this.reconciliationChanged);
    }

    public List<GeoFrontFabricPlan.FeatureContract>
    reconciliationContracts(int pass)
    {
        Map<String, GeoFrontFabricPlan.FeatureContract> source =
                pass == 0 ? this.previousContracts
                        : this.committedContracts;
        return List.copyOf(source.values());
    }

    public void updateReconciliation(
            int pass, int featureIndex, long cursor,
            long visited, long changed)
    {
        if (!this.reconciliationActive)
        {
            throw new IllegalStateException(
                    "GeoFrontFabric reconciliation is not active");
        }
        this.reconciliationPass = Math.max(0, Math.min(1, pass));
        this.reconciliationFeatureIndex = Math.max(0, featureIndex);
        this.reconciliationCursor = Math.max(0L, cursor);
        this.reconciliationVisited = Math.max(0L, visited);
        this.reconciliationChanged = Math.max(0L, changed);
        this.setDirty();
    }

    public void completeReconciliation()
    {
        if (!this.reconciliationActive)
        {
            return;
        }
        this.features.clear();
        for (GeoFrontFabricPlan.Feature feature
                : GeoFrontFabricPlan.Feature.values())
        {
            this.features.put(feature.id(), new FeatureRecord(
                    FeatureState.COMPLETE, feature.revision(),
                    feature.priority(), feature.contractHash(),
                    this.ownerGuardHash, feature.contractHash(),
                    feature.authoredWork(), feature.authoredWork(),
                    0L, ""));
        }
        this.previousContracts.clear();
        this.reconciliationActive = false;
        this.reconciliationPass = 1;
        this.reconciliationFeatureIndex =
                this.committedContracts.size();
        this.reconciliationCursor = 0L;
        this.lifecycle = Lifecycle.COMPLETE;
        this.programmeActive = false;
        this.failure = "";
        this.setDirty();
    }

    public void failReconciliation(String reason)
    {
        this.reconciliationActive = false;
        this.lifecycle = Lifecycle.FAILED;
        this.programmeActive = false;
        this.failure = reason == null ? "unknown reconciliation failure"
                : reason;
        this.setDirty();
    }

    public Lifecycle lifecycle()
    {
        return this.lifecycle;
    }

    public boolean programmeActive()
    {
        return this.programmeActive;
    }

    public boolean westSeamOpen()
    {
        return this.westSeamOpen;
    }

    public void markWestSeamOpen()
    {
        requireCommitted();
        if (!this.westSeamOpen)
        {
            this.westSeamOpen = true;
            this.setDirty();
        }
    }

    public String summary()
    {
        long complete = this.features.values().stream()
                .filter(record -> record.state()
                        == FeatureState.COMPLETE).count();
        Optional<GeoFrontFabricPlan.Feature> active = activeFeature();
        String progress = active.map(feature ->
        {
            FeatureRecord record = requireFeature(feature);
            return feature.id() + "=" + record.cursor() + "/"
                    + feature.authoredWork() + " changed="
                    + record.changed();
        }).orElse("idle");
        return "state=" + this.lifecycle + " revision="
                + this.fabricRevision + " complete=" + complete + "/"
                + this.features.size() + " programme="
                + this.programmeActive + " westSeam="
                + (this.westSeamOpen ? "OPEN" : "SEALED")
                + " reconcile="
                + (this.reconciliationActive
                ? this.reconciliationPass + ":"
                + this.reconciliationFeatureIndex + ":"
                + this.reconciliationCursor : "idle")
                + " active=" + progress
                + (this.failure.isBlank() ? "" : " failure=" + this.failure);
    }

    private static Map<String, GeoFrontFabricPlan.FeatureContract>
    currentContractMap()
    {
        Map<String, GeoFrontFabricPlan.FeatureContract> contracts =
                new LinkedHashMap<>();
        for (GeoFrontFabricPlan.FeatureContract contract
                : GeoFrontFabricPlan.currentContracts())
        {
            contracts.put(contract.id(), contract);
        }
        return contracts;
    }

    private void migrateLegacyContracts()
    {
        for (Map.Entry<String, FeatureRecord> entry
                : this.features.entrySet())
        {
            try
            {
                GeoFrontFabricPlan.Feature feature =
                        GeoFrontFabricPlan.Feature.byId(entry.getKey());
                FeatureRecord record = entry.getValue();
                this.committedContracts.put(entry.getKey(),
                        new GeoFrontFabricPlan.FeatureContract(
                                entry.getKey(), record.revision(),
                                record.priority(), feature.authoredWork(),
                                GeoFrontFabricPlan.GEOMETRY_VERSION,
                                record.contractHash()));
            }
            catch (IllegalArgumentException ignored)
            {
                this.lifecycle = Lifecycle.FAILED;
                this.failure = "legacy feature contract cannot be replayed: "
                        + entry.getKey();
            }
        }
    }

    private static void readContracts(
            ListTag list,
            Map<String, GeoFrontFabricPlan.FeatureContract> target)
    {
        for (int index = 0; index < list.size(); index++)
        {
            CompoundTag contractTag = list.getCompound(index);
            String id = contractTag.getString("Id");
            if (id.isBlank() || target.containsKey(id))
            {
                continue;
            }
            target.put(id, new GeoFrontFabricPlan.FeatureContract(
                    id, contractTag.getString("Revision"),
                    contractTag.getInt("Priority"),
                    Math.max(0L, contractTag.getLong("AuthoredWork")),
                    Math.max(0, contractTag.getInt("GeometryVersion")),
                    contractTag.getString("ContractHash")));
        }
    }

    private static ListTag writeContracts(
            Map<String, GeoFrontFabricPlan.FeatureContract> source)
    {
        ListTag list = new ListTag();
        for (GeoFrontFabricPlan.FeatureContract contract
                : source.values())
        {
            CompoundTag contractTag = new CompoundTag();
            contractTag.putString("Id", contract.id());
            contractTag.putString("Revision", contract.revision());
            contractTag.putInt("Priority", contract.priority());
            contractTag.putLong("AuthoredWork",
                    contract.authoredWork());
            contractTag.putInt("GeometryVersion",
                    contract.geometryVersion());
            contractTag.putString("ContractHash",
                    contract.contractHash());
            list.add(contractTag);
        }
        return list;
    }

    private void requireCommitted()
    {
        if (this.lifecycle == Lifecycle.DRAFT
                || this.lifecycle == Lifecycle.FAILED)
        {
            throw new IllegalStateException(
                    "GeoFrontFabric is not in a writable lifecycle: "
                            + this.lifecycle);
        }
    }

    @Override
    public CompoundTag save(CompoundTag tag)
    {
        tag.putInt("Version", DATA_VERSION);
        tag.putString("Lifecycle", this.lifecycle.name());
        tag.putInt("FormatVersion", this.formatVersion);
        tag.putInt("FabricRevision", this.fabricRevision);
        tag.putInt("FacilityEpoch", this.facilityEpoch);
        tag.putString("RegionId", this.regionId);
        tag.putString("RegionCoreHash", this.regionCoreHash);
        tag.putString("PlanHash", this.planHash);
        tag.putString("OwnerUnionHash", this.ownerUnionHash);
        tag.putString("OwnerGuardHash", this.ownerGuardHash);
        tag.putString("Failure", this.failure);
        tag.putBoolean("ProgrammeActive", this.programmeActive);
        tag.putBoolean("WestSeamOpen", this.westSeamOpen);
        tag.putLong("RescueCavernChunkCursor",
                this.rescueCavernChunkCursor);
        tag.put("CommittedContracts",
                writeContracts(this.committedContracts));
        tag.put("PreviousContracts",
                writeContracts(this.previousContracts));
        CompoundTag reconciliation = new CompoundTag();
        reconciliation.putBoolean("Active",
                this.reconciliationActive);
        reconciliation.putInt("Pass", this.reconciliationPass);
        reconciliation.putInt("FeatureIndex",
                this.reconciliationFeatureIndex);
        reconciliation.putLong("Cursor", this.reconciliationCursor);
        reconciliation.putLong("Visited",
                this.reconciliationVisited);
        reconciliation.putLong("Changed",
                this.reconciliationChanged);
        tag.put("Reconciliation", reconciliation);
        ListTag list = new ListTag();
        for (Map.Entry<String, FeatureRecord> entry
                : this.features.entrySet())
        {
            CompoundTag featureTag = new CompoundTag();
            FeatureRecord record = entry.getValue();
            featureTag.putString("Id", entry.getKey());
            featureTag.putString("State", record.state().name());
            featureTag.putString("Revision", record.revision());
            featureTag.putInt("Priority", record.priority());
            featureTag.putString("ContractHash", record.contractHash());
            featureTag.putString("ResolvedMaskHash",
                    record.resolvedMaskHash());
            featureTag.putString("ContentHash", record.contentHash());
            featureTag.putLong("Cursor", record.cursor());
            featureTag.putLong("Visited", record.visited());
            featureTag.putLong("Changed", record.changed());
            featureTag.putString("Failure", record.failure());
            list.add(featureTag);
        }
        tag.put("Features", list);
        return tag;
    }

    public enum Lifecycle
    {
        DRAFT,
        COMMITTED,
        BUILDING,
        RECONCILING,
        COMPLETE,
        FAILED;

        private static Lifecycle parse(String raw)
        {
            try
            {
                return Lifecycle.valueOf(raw);
            }
            catch (IllegalArgumentException ignored)
            {
                return DRAFT;
            }
        }
    }

    public enum FeatureState
    {
        PENDING,
        BUILDING,
        COMPLETE,
        FAILED;

        private static FeatureState parse(String raw)
        {
            try
            {
                return FeatureState.valueOf(raw);
            }
            catch (IllegalArgumentException ignored)
            {
                return PENDING;
            }
        }
    }

    public record FeatureRecord(FeatureState state, String revision,
                                int priority, String contractHash,
                                String resolvedMaskHash, String contentHash,
                                long cursor, long visited, long changed,
                                String failure)
    {
        private FeatureRecord withState(FeatureState state, String failure)
        {
            return new FeatureRecord(state, this.revision, this.priority,
                    this.contractHash, this.resolvedMaskHash,
                    this.contentHash, this.cursor, this.visited,
                    this.changed, failure == null ? "" : failure);
        }

        private FeatureRecord withProgress(long cursor, long visited,
                                           long changed)
        {
            return new FeatureRecord(this.state, this.revision,
                    this.priority, this.contractHash,
                    this.resolvedMaskHash, this.contentHash,
                    Math.max(0L, cursor), Math.max(0L, visited),
                    Math.max(0L, changed), this.failure);
        }
    }

    public record ReconciliationProgress(int pass, int featureIndex,
                                         long cursor, long visited,
                                         long changed) {}
}

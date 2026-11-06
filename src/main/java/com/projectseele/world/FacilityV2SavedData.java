package com.projectseele.world;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

import com.projectseele.ProjectSeele;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.saveddata.SavedData;

/**
 * Durable authority for the clean FacilitySchema v2 region.
 *
 * <p>The retired GeoFront builders never read or mutate this record. A zone
 * may be generated only after an administrator commissions a bootstrap
 * receipt, and ordinary gameplay code may only read completed receipts.</p>
 */
public final class FacilityV2SavedData extends SavedData
{
    private static final String DATA_NAME = "projectseele_facility_v2_e2";
    private static final int DATA_VERSION = 1;

    private Lifecycle lifecycle = Lifecycle.UNCOMMISSIONED;
    private int schemaVersion;
    private int epoch;
    private int candidateIndex = -1;
    private int surfaceY;
    private String regionId = "";
    private String regionCoreHash = "";
    private String generatorVersion = "";
    private String failure = "";
    private final Map<String, ZoneRecord> zones = new LinkedHashMap<>();

    public static FacilityV2SavedData get(ServerLevel level)
    {
        return level.getDataStorage().computeIfAbsent(
                FacilityV2SavedData::load, FacilityV2SavedData::new,
                DATA_NAME);
    }

    public static FacilityV2SavedData load(CompoundTag tag)
    {
        FacilityV2SavedData data = new FacilityV2SavedData();
        int version = tag.contains("Version", Tag.TAG_INT)
                ? tag.getInt("Version") : 1;
        if (version != DATA_VERSION)
        {
            ProjectSeele.LOGGER.error(
                    "Unsupported FacilitySchema v2 SavedData version {}; "
                            + "facility remains unavailable", version);
            data.lifecycle = Lifecycle.FAILED;
            data.failure = "unsupported saved-data version " + version;
            return data;
        }

        data.lifecycle = Lifecycle.parse(tag.getString("Lifecycle"));
        data.schemaVersion = tag.getInt("SchemaVersion");
        data.epoch = tag.getInt("Epoch");
        data.candidateIndex = tag.getInt("CandidateIndex");
        data.surfaceY = tag.getInt("SurfaceY");
        data.regionId = tag.getString("RegionId");
        data.regionCoreHash = tag.getString("RegionCoreHash");
        data.generatorVersion = tag.getString("GeneratorVersion");
        data.failure = tag.getString("Failure");

        ListTag list = tag.getList("Zones", Tag.TAG_COMPOUND);
        for (int index = 0; index < list.size(); index++)
        {
            CompoundTag zoneTag = list.getCompound(index);
            String id = zoneTag.getString("Id");
            if (id.isBlank() || data.zones.containsKey(id))
            {
                continue;
            }
            ZoneState state = ZoneState.parse(zoneTag.getString("State"));
            String zoneFailure = zoneTag.getString("Failure");
            if (state == ZoneState.GENERATING)
            {
                state = ZoneState.FAILED;
                zoneFailure = "generation interrupted by save/reload";
            }
            data.zones.put(id, new ZoneRecord(state,
                    zoneTag.getString("Stage"),
                    zoneTag.getString("GeneratorVersion"),
                    zoneTag.getString("BuildPlanHash"),
                    Math.max(0L, zoneTag.getLong("Cursor")),
                    Math.max(0L, zoneTag.getLong("Visited")),
                    Math.max(0L, zoneTag.getLong("Changed")),
                    zoneFailure));
        }
        return data;
    }

    public boolean commissioned()
    {
        return this.lifecycle == Lifecycle.COMMISSIONED
                && this.schemaVersion == FacilitySchemaV2.SCHEMA_VERSION
                && this.epoch == FacilitySchemaV2.EPOCH
                && FacilitySchemaV2.REGION_ID.equals(this.regionId)
                && FacilitySchemaV2.GENERATOR_VERSION.equals(
                        this.generatorVersion);
    }

    public void commission(FacilitySchemaV2.ResolvedManifest manifest,
                           String newRegionCoreHash)
    {
        if (this.lifecycle != Lifecycle.UNCOMMISSIONED)
        {
            throw new IllegalStateException(
                    "Facility v2 already has lifecycle " + this.lifecycle);
        }
        if (newRegionCoreHash == null || newRegionCoreHash.isBlank())
        {
            throw new IllegalArgumentException(
                    "Region-core hash cannot be empty");
        }
        this.lifecycle = Lifecycle.COMMISSIONED;
        this.schemaVersion = FacilitySchemaV2.SCHEMA_VERSION;
        this.epoch = FacilitySchemaV2.EPOCH;
        this.candidateIndex = manifest.candidateIndex();
        this.surfaceY = manifest.surfaceY();
        this.regionId = FacilitySchemaV2.REGION_ID;
        this.regionCoreHash = newRegionCoreHash;
        this.generatorVersion = FacilitySchemaV2.GENERATOR_VERSION;
        this.failure = "";
        this.zones.clear();
        for (FacilitySchemaV2.ZoneSpec zone : manifest.zones())
        {
            this.zones.put(zone.id(), ZoneRecord.empty());
        }
        this.setDirty();
    }

    public void beginZone(String zoneId, String stage, String buildPlanHash)
    {
        requireCommissioned();
        if (this.zones.values().stream()
                .anyMatch(record -> record.state() == ZoneState.GENERATING))
        {
            throw new IllegalStateException(
                    "Another facility zone is already generating");
        }
        ZoneRecord current = requireZone(zoneId);
        if (current.state() != ZoneState.EMPTY)
        {
            throw new IllegalStateException(zoneId + " is "
                    + current.state() + ", expected EMPTY");
        }
        this.zones.put(zoneId, new ZoneRecord(ZoneState.GENERATING,
                stage, FacilitySchemaV2.GENERATOR_VERSION, buildPlanHash,
                0L, 0L, 0L, ""));
        this.setDirty();
    }

    public void updateZoneProgress(String zoneId, long cursor, long visited,
                                   long changed)
    {
        ZoneRecord current = requireZone(zoneId);
        if (current.state() != ZoneState.GENERATING)
        {
            throw new IllegalStateException(zoneId + " is not generating");
        }
        this.zones.put(zoneId, current.withProgress(cursor, visited, changed));
        this.setDirty();
    }

    public void completeZone(String zoneId)
    {
        ZoneRecord current = requireZone(zoneId);
        if (current.state() != ZoneState.GENERATING)
        {
            throw new IllegalStateException(zoneId + " is not generating");
        }
        this.zones.put(zoneId, current.withState(ZoneState.COMPLETE, ""));
        this.setDirty();
    }

    public void failZone(String zoneId, String reason)
    {
        ZoneRecord current = requireZone(zoneId);
        this.zones.put(zoneId, current.withState(ZoneState.FAILED, reason));
        this.setDirty();
    }

    public Optional<Map.Entry<String, ZoneRecord>> activeZone()
    {
        return this.zones.entrySet().stream()
                .filter(entry -> entry.getValue().state()
                        == ZoneState.GENERATING)
                .findFirst();
    }

    public ZoneRecord requireZone(String zoneId)
    {
        ZoneRecord record = this.zones.get(zoneId);
        if (record == null)
        {
            throw new IllegalArgumentException(
                    "Unknown FacilitySchema v2 zone " + zoneId);
        }
        return record;
    }

    public FacilitySchemaV2.ResolvedManifest manifest()
    {
        requireCommissioned();
        return FacilitySchemaV2.resolve(this.candidateIndex, this.surfaceY);
    }

    public Lifecycle lifecycle()
    {
        return this.lifecycle;
    }

    public int candidateIndex()
    {
        return this.candidateIndex;
    }

    public int surfaceY()
    {
        return this.surfaceY;
    }

    public String regionCoreHash()
    {
        return this.regionCoreHash;
    }

    public Map<String, ZoneRecord> zones()
    {
        return Map.copyOf(this.zones);
    }

    public String summary()
    {
        long complete = this.zones.values().stream()
                .filter(zone -> zone.state() == ZoneState.COMPLETE).count();
        long failed = this.zones.values().stream()
                .filter(zone -> zone.state() == ZoneState.FAILED).count();
        return "lifecycle=" + this.lifecycle
                + " schema=" + this.schemaVersion
                + " epoch=" + this.epoch
                + " candidate=" + this.candidateIndex
                + " surfaceY=" + this.surfaceY
                + " complete=" + complete + "/" + this.zones.size()
                + " failed=" + failed;
    }

    private void requireCommissioned()
    {
        if (!commissioned())
        {
            throw new IllegalStateException(
                    "FacilitySchema v2 has no valid commission receipt");
        }
    }

    @Override
    public CompoundTag save(CompoundTag tag)
    {
        tag.putInt("Version", DATA_VERSION);
        tag.putString("Lifecycle", this.lifecycle.name());
        tag.putInt("SchemaVersion", this.schemaVersion);
        tag.putInt("Epoch", this.epoch);
        tag.putInt("CandidateIndex", this.candidateIndex);
        tag.putInt("SurfaceY", this.surfaceY);
        tag.putString("RegionId", this.regionId);
        tag.putString("RegionCoreHash", this.regionCoreHash);
        tag.putString("GeneratorVersion", this.generatorVersion);
        tag.putString("Failure", this.failure);
        ListTag list = new ListTag();
        for (Map.Entry<String, ZoneRecord> entry : this.zones.entrySet())
        {
            CompoundTag zoneTag = new CompoundTag();
            zoneTag.putString("Id", entry.getKey());
            zoneTag.putString("State", entry.getValue().state().name());
            zoneTag.putString("Stage", entry.getValue().stage());
            zoneTag.putString("GeneratorVersion",
                    entry.getValue().generatorVersion());
            zoneTag.putString("BuildPlanHash",
                    entry.getValue().buildPlanHash());
            zoneTag.putLong("Cursor", entry.getValue().cursor());
            zoneTag.putLong("Visited", entry.getValue().visited());
            zoneTag.putLong("Changed", entry.getValue().changed());
            zoneTag.putString("Failure", entry.getValue().failure());
            list.add(zoneTag);
        }
        tag.put("Zones", list);
        return tag;
    }

    public enum Lifecycle
    {
        UNCOMMISSIONED,
        COMMISSIONED,
        FAILED,
        RETIRED;

        private static Lifecycle parse(String raw)
        {
            try
            {
                return Lifecycle.valueOf(raw);
            }
            catch (IllegalArgumentException ignored)
            {
                return UNCOMMISSIONED;
            }
        }
    }

    public enum ZoneState
    {
        EMPTY,
        GENERATING,
        COMPLETE,
        FAILED,
        RETIRED;

        private static ZoneState parse(String raw)
        {
            try
            {
                return ZoneState.valueOf(raw);
            }
            catch (IllegalArgumentException ignored)
            {
                return EMPTY;
            }
        }
    }

    public record ZoneRecord(ZoneState state, String stage,
                             String generatorVersion, String buildPlanHash,
                             long cursor, long visited, long changed,
                             String failure)
    {
        public ZoneRecord
        {
            stage = stage == null ? "" : stage;
            generatorVersion = generatorVersion == null
                    ? "" : generatorVersion;
            buildPlanHash = buildPlanHash == null ? "" : buildPlanHash;
            failure = failure == null ? "" : failure;
        }

        public static ZoneRecord empty()
        {
            return new ZoneRecord(ZoneState.EMPTY, "", "", "",
                    0L, 0L, 0L, "");
        }

        public ZoneRecord withProgress(long newCursor, long newVisited,
                                       long newChanged)
        {
            return new ZoneRecord(this.state, this.stage,
                    this.generatorVersion, this.buildPlanHash,
                    Math.max(0L, newCursor), Math.max(0L, newVisited),
                    Math.max(0L, newChanged), this.failure);
        }

        public ZoneRecord withState(ZoneState newState, String newFailure)
        {
            return new ZoneRecord(newState, this.stage,
                    this.generatorVersion, this.buildPlanHash,
                    this.cursor, this.visited, this.changed, newFailure);
        }
    }
}

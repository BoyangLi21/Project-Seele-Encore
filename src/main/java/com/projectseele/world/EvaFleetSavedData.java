package com.projectseele.world;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import com.projectseele.ProjectSeele;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.saveddata.SavedData;

/** World-global canonical EVA identities and persistent logistics progress. */
public final class EvaFleetSavedData extends SavedData
{
    private static final String DATA_NAME = "projectseele_eva_fleet";
    private static final int DATA_VERSION = 2;

    private final Map<Integer, FleetEntry> entries = new LinkedHashMap<>();

    public static EvaFleetSavedData get(MinecraftServer server)
    {
        ServerLevel overworld = server.overworld();
        return overworld.getDataStorage().computeIfAbsent(
                EvaFleetSavedData::load, EvaFleetSavedData::new, DATA_NAME);
    }

    public static EvaFleetSavedData load(CompoundTag tag)
    {
        EvaFleetSavedData data = new EvaFleetSavedData();
        int version = tag.contains("Version", Tag.TAG_INT)
                ? tag.getInt("Version") : 1;
        if (version < 1 || version > DATA_VERSION)
        {
            ProjectSeele.LOGGER.error(
                    "Unsupported EVA fleet SavedData version {}; ignoring fleet",
                    version);
            return data;
        }
        ListTag list = tag.getList("Fleet", Tag.TAG_COMPOUND);
        for (int index = 0; index < list.size(); index++)
        {
            CompoundTag entryTag = list.getCompound(index);
            int variant = entryTag.getInt("Variant");
            if (variant < 0 || variant > 2 || !entryTag.hasUUID("Canonical"))
            {
                continue;
            }
            Phase phase = Phase.parse(entryTag.getString("Phase"));
            FleetEntry entry = new FleetEntry(entryTag.getUUID("Canonical"),
                    phase, Math.max(0, entryTag.getInt("Ticks")),
                    entryTag.getInt("Carrier"),
                    Math.max(0, Math.min(EvaHangarBuilder.LCL_SHOULDER_LAYERS,
                            entryTag.getInt("LclLayers"))),
                    entryTag.hasUUID("EntryPlug")
                            ? entryTag.getUUID("EntryPlug") : null);
            data.entries.put(variant, entry);
        }
        return data;
    }

    public Optional<FleetEntry> entry(int variant)
    {
        return Optional.ofNullable(this.entries.get(variant));
    }

    public Optional<UUID> canonicalId(int variant)
    {
        return this.entry(variant).map(FleetEntry::canonicalId);
    }

    public boolean claimIfAbsent(int variant, UUID entityId, int carrier,
                                 int lclLayers)
    {
        FleetEntry current = this.entries.get(variant);
        if (current != null)
        {
            return current.canonicalId().equals(entityId);
        }
        this.put(variant, new FleetEntry(entityId, Phase.PARKED,
                0, carrier, lclLayers));
        return true;
    }

    public void put(int variant, FleetEntry entry)
    {
        this.entries.put(variant, entry);
        this.setDirty();
    }

    @Override
    public CompoundTag save(CompoundTag tag)
    {
        tag.putInt("Version", DATA_VERSION);
        ListTag list = new ListTag();
        for (Map.Entry<Integer, FleetEntry> value : this.entries.entrySet())
        {
            CompoundTag entryTag = new CompoundTag();
            entryTag.putInt("Variant", value.getKey());
            entryTag.putUUID("Canonical", value.getValue().canonicalId());
            entryTag.putString("Phase", value.getValue().phase().name());
            entryTag.putInt("Ticks", value.getValue().ticks());
            entryTag.putInt("Carrier", value.getValue().carrier());
            entryTag.putInt("LclLayers", value.getValue().lclLayers());
            if (value.getValue().entryPlugId() != null)
            {
                entryTag.putUUID("EntryPlug",
                        value.getValue().entryPlugId());
            }
            list.add(entryTag);
        }
        tag.put("Fleet", list);
        return tag;
    }

    public enum Phase
    {
        PARKED,
        BRIDGE_RETRACTING,
        PLUG_INSERTING,
        PLUG_ABORT_RETURNING,
        PLUG_ABORT_DOCKED,
        PLUG_FAULT,
        PLUG_LOCKING,
        DRAINING,
        TO_SILO,
        SILO_READY,
        DEPLOYED,
        DESCENDING,
        TO_HANGAR,
        FILLING,
        CANCELLED;

        private static Phase parse(String value)
        {
            try
            {
                return Phase.valueOf(value);
            }
            catch (IllegalArgumentException ignored)
            {
                return PARKED;
            }
        }
    }

    public record FleetEntry(UUID canonicalId, Phase phase, int ticks,
                             int carrier, int lclLayers, UUID entryPlugId)
    {
        public FleetEntry(UUID canonicalId, Phase phase, int ticks,
                          int carrier, int lclLayers)
        {
            this(canonicalId, phase, ticks, carrier, lclLayers, null);
        }

        public FleetEntry withPhase(Phase value, int newTicks,
                                    int newCarrier, int newLclLayers)
        {
            return new FleetEntry(this.canonicalId, value, newTicks,
                    newCarrier, newLclLayers, this.entryPlugId);
        }

        public FleetEntry withEntryPlug(UUID plugId)
        {
            return new FleetEntry(this.canonicalId, this.phase, this.ticks,
                    this.carrier, this.lclLayers, plugId);
        }
    }
}

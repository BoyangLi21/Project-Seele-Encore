package com.projectseele.world;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.saveddata.SavedData;
import java.util.*;

/** A saved request binds originals; equipment inventory remains owned by its physical well. */
public final class ArmedSortieSavedDataR48 extends SavedData
{
    public record Selection(int variant, int payload, UUID owner, UUID eva, UUID pilot, UUID operator,
                            UUID well, String mission, boolean npc, String phase)
    {
        public Selection phase(String next)
        { return new Selection(variant,payload,owner,eva,pilot,operator,well,mission,npc,next); }
    }
    private final Map<Integer,Selection> selections = new LinkedHashMap<>();
    public static ArmedSortieSavedDataR48 get(ServerLevel level)
    {
        return level.getDataStorage().computeIfAbsent(ArmedSortieSavedDataR48::load,
                ArmedSortieSavedDataR48::new,"projectseele_armed_sorties_r48");
    }
    public Selection selection(int variant) { return selections.get(variant); }
    public List<Selection> selections() { return List.copyOf(selections.values()); }
    public void put(Selection selection) { selections.put(selection.variant(),selection); setDirty(); }
    public void remove(int variant) { if(selections.remove(variant)!=null)setDirty(); }
    public static ArmedSortieSavedDataR48 load(CompoundTag tag)
    {
        if(tag.getInt("Version")!=48)throw new IllegalStateException("Unknown armed sortie selection version");
        var data = new ArmedSortieSavedDataR48();
        for(var raw:tag.getList("Selections",Tag.TAG_COMPOUND))
        {
            var row=(CompoundTag)raw;int variant=row.getInt("Variant"),payload=row.getInt("Payload");
            if(variant!=0&&variant!=2||payload!=(variant==0?7:6)
                    ||!row.hasUUID("Owner")||!row.hasUUID("Eva")||!row.hasUUID("Pilot")
                    ||!row.hasUUID("Operator")||!row.hasUUID("Well")||row.getString("Mission").isEmpty()
                    ||!Set.of("pending","issued","return_pending").contains(row.getString("Phase")))continue;
            data.selections.putIfAbsent(variant,new Selection(variant,payload,row.getUUID("Owner"),row.getUUID("Eva"),
                    row.getUUID("Pilot"),row.getUUID("Operator"),row.getUUID("Well"),row.getString("Mission"),
                    row.getBoolean("Npc"),row.getString("Phase")));
        }
        return data;
    }
    @Override public CompoundTag save(CompoundTag tag)
    {
        tag.putInt("Version",48);var rows=new ListTag();
        for(var selection:selections.values())
        {
            var row=new CompoundTag();row.putInt("Variant",selection.variant());row.putInt("Payload",selection.payload());
            row.putUUID("Owner",selection.owner());row.putUUID("Eva",selection.eva());row.putUUID("Pilot",selection.pilot());
            row.putUUID("Operator",selection.operator());row.putUUID("Well",selection.well());
            row.putString("Mission",selection.mission());row.putBoolean("Npc",selection.npc());row.putString("Phase",selection.phase());
            rows.add(row);
        }
        tag.put("Selections",rows);return tag;
    }
}

package com.projectseele.world;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.saveddata.SavedData;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/** Damage to the installed roof plates survives logout, reload and failed-sortie recovery. */
public final class NervArmorSavedDataR50 extends SavedData
{
    public String column="",phase="sealed";
    public UUID attacker;
    public long generation,lastTick=-1;
    public final Map<String,Float> integrity=new LinkedHashMap<>();
    public int breached,stepBudget;
    public boolean terminalContact;
    public static NervArmorSavedDataR50 get(ServerLevel level)
    {return level.getDataStorage().computeIfAbsent(NervArmorSavedDataR50::load,NervArmorSavedDataR50::new,"projectseele_nerv_armor_column_r50");}
    private static NervArmorSavedDataR50 load(CompoundTag tag)
    {
        var data=new NervArmorSavedDataR50();data.column=tag.getString("Column");data.phase=tag.getString("Phase");data.generation=tag.getLong("Generation");data.lastTick=tag.getLong("LastTick");
        data.breached=Math.max(0,tag.getInt("Breached"));data.stepBudget=Math.max(0,tag.getInt("StepBudget"));data.terminalContact=tag.getBoolean("TerminalContact");if(tag.hasUUID("Attacker"))data.attacker=tag.getUUID("Attacker");
        for(var raw:tag.getList("Integrity",Tag.TAG_COMPOUND)){var row=(CompoundTag)raw;float hp=row.getFloat("HP");if(Float.isFinite(hp))data.integrity.put(row.getString("Layer"),Math.max(0,hp));}return data;
    }
    @Override public CompoundTag save(CompoundTag tag)
    {
        tag.putString("Column",column);tag.putString("Phase",phase);tag.putLong("Generation",generation);tag.putLong("LastTick",lastTick);tag.putInt("Breached",breached);tag.putInt("StepBudget",stepBudget);tag.putBoolean("TerminalContact",terminalContact);if(attacker!=null)tag.putUUID("Attacker",attacker);
        var list=new ListTag();integrity.forEach((id,hp)->{var row=new CompoundTag();row.putString("Layer",id);row.putFloat("HP",hp);list.add(row);});tag.put("Integrity",list);return tag;
    }
}

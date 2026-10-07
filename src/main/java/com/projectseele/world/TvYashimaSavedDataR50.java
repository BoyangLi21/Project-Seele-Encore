package com.projectseele.world;

import java.util.UUID;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.saveddata.SavedData;

/** Cannon service receipts; the shared armour controller owns all drilling progress. */
public final class TvYashimaSavedDataR50 extends SavedData
{
    public UUID owner, boss, fireTarget;
    public long generation, onlineTicks;
    public int shots;
    public boolean coolantReady = true, reloadReady = true, coolantPressed, reloadPressed;
    public boolean fireControlLocked;
    public static TvYashimaSavedDataR50 get(ServerLevel level)
    {return level.getDataStorage().computeIfAbsent(TvYashimaSavedDataR50::load,TvYashimaSavedDataR50::new,"projectseele_tv_yashima_r50");}
    private static TvYashimaSavedDataR50 load(CompoundTag tag)
    {
        var state = new TvYashimaSavedDataR50();
        if(tag.hasUUID("Owner"))state.owner=tag.getUUID("Owner");
        if(tag.hasUUID("Boss"))state.boss=tag.getUUID("Boss");
        state.generation=tag.getLong("Generation");state.onlineTicks=tag.getLong("OnlineTicks");state.shots=tag.getInt("Shots");
        state.coolantReady=tag.getBoolean("CoolantReady");state.reloadReady=tag.getBoolean("ReloadReady");
        // A held switch across reload is not a new post-shot service operation.
        state.coolantPressed=tag.getBoolean("CoolantPressed");state.reloadPressed=tag.getBoolean("ReloadPressed");
        state.fireControlLocked=tag.contains("FireControlLockedR50")?tag.getBoolean("FireControlLockedR50"):state.shots>0;
        if(tag.hasUUID("FireTargetR50"))state.fireTarget=tag.getUUID("FireTargetR50");
        return state;
    }
    @Override public CompoundTag save(CompoundTag tag)
    {
        if(owner!=null)tag.putUUID("Owner",owner);if(boss!=null)tag.putUUID("Boss",boss);
        tag.putLong("Generation",generation);tag.putLong("OnlineTicks",onlineTicks);tag.putInt("Shots",shots);
        tag.putBoolean("CoolantReady",coolantReady);tag.putBoolean("ReloadReady",reloadReady);
        tag.putBoolean("FireControlLockedR50",fireControlLocked);
        if(fireTarget!=null)tag.putUUID("FireTargetR50",fireTarget);else tag.remove("FireTargetR50");
        tag.putBoolean("CoolantPressed",coolantPressed);tag.putBoolean("ReloadPressed",reloadPressed);return tag;
    }
    public boolean matches(TvCampaignSavedData data)
    {return owner!=null&&owner.equals(data.owner)&&generation==data.generationR43&&boss!=null&&boss.equals(data.angel);}
    public void bind(TvCampaignSavedData data)
    {
        if(matches(data))
        {
            // An older completed cannon shot is positive evidence of exposure,
            // not a reason to hide the same shooter after a save upgrade.
            var shooter=data.sorties.get(1);
            if(fireControlLocked&&fireTarget==null&&shots>0&&shooter!=null&&shooter.eva!=null)
            {fireTarget=shooter.eva;setDirty();}
            return;
        }
        owner=data.owner;boss=data.angel;generation=data.generationR43;onlineTicks=0;shots=0;
        coolantReady=reloadReady=true;coolantPressed=reloadPressed=false;fireControlLocked=false;fireTarget=null;setDirty();
    }
    public void resetFireControlForRetry(TvCampaignSavedData data)
    {if(matches(data)){fireControlLocked=false;fireTarget=null;setDirty();}}
}

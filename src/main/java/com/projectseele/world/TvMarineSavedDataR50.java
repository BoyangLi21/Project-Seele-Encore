package com.projectseele.world;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.saveddata.SavedData;
import java.util.UUID;

/** Marine sortie facts are persisted separately from chronology and original fleet identities. */
public final class TvMarineSavedDataR50 extends SavedData
{
    public UUID boss,owner;
    public long generation;
    public String site="",phase="idle",notice="";
    public int elapsed,spawnWait,missingTicks,cargoHealth=100,powerCharge,holdTicks;
    public boolean powerEnabled;
    public final int[] cannonCharge=new int[2],cannonCooldown=new int[2];
    public final long[] cannonFired={-10000,-10000};
    public final int[] coreHits=new int[2];
    public final int[] shotTagBudget=new int[2];
    public final UUID[] cannonOperator=new UUID[2];
    public long lastCargoHit=-10000;
    public final CompoundTag[] cannonBefore={new CompoundTag(),new CompoundTag()};
    public boolean cannonCleanupPending;
    public static TvMarineSavedDataR50 get(ServerLevel level)
    {return level.getDataStorage().computeIfAbsent(TvMarineSavedDataR50::load,TvMarineSavedDataR50::new,"projectseele_tv_marine_r50");}
    public static TvMarineSavedDataR50 load(CompoundTag tag)
    {
        var data=new TvMarineSavedDataR50();if(tag.hasUUID("Boss"))data.boss=tag.getUUID("Boss");if(tag.hasUUID("Owner"))data.owner=tag.getUUID("Owner");
        data.generation=tag.getLong("Generation");data.site=tag.getString("Site");data.phase=tag.getString("Phase");data.notice=tag.getString("Notice");
        data.elapsed=Math.max(0,tag.getInt("Elapsed"));data.spawnWait=Math.max(0,tag.getInt("SpawnWait"));data.cargoHealth=tag.contains("CargoHealth")?Math.max(0,tag.getInt("CargoHealth")):100;
        data.powerCharge=Math.max(0,tag.getInt("PowerCharge"));data.powerEnabled=tag.getBoolean("PowerEnabled");data.holdTicks=Math.max(0,tag.getInt("HoldTicks"));
        data.lastCargoHit=tag.contains("LastCargoHit")?tag.getLong("LastCargoHit"):-10000;
        data.cannonCleanupPending=tag.getBoolean("CannonCleanupPending");
        for(int i=0;i<2;i++)
        {data.cannonCharge[i]=Math.max(0,tag.getInt("CannonCharge"+i));data.cannonCooldown[i]=Math.max(0,tag.getInt("CannonCooldown"+i));data.cannonFired[i]=tag.contains("CannonFired"+i)?tag.getLong("CannonFired"+i):-10000;data.coreHits[i]=Math.max(0,tag.getInt("CoreHits"+i));data.cannonBefore[i]=tag.getCompound("CannonBefore"+i).copy();data.shotTagBudget[i]=Math.max(0,Math.min(1,tag.getInt("ShotTagBudget"+i)));data.cannonOperator[i]=tag.hasUUID("CannonOperator"+i)?tag.getUUID("CannonOperator"+i):null;}
        return data;
    }
    @Override public CompoundTag save(CompoundTag tag)
    {
        if(boss!=null)tag.putUUID("Boss",boss);if(owner!=null)tag.putUUID("Owner",owner);tag.putLong("Generation",generation);tag.putString("Site",site);tag.putString("Phase",phase);tag.putString("Notice",notice);
        tag.putInt("Elapsed",elapsed);tag.putInt("SpawnWait",spawnWait);tag.putInt("CargoHealth",cargoHealth);tag.putInt("PowerCharge",powerCharge);tag.putBoolean("PowerEnabled",powerEnabled);tag.putInt("HoldTicks",holdTicks);tag.putLong("LastCargoHit",lastCargoHit);
        tag.putBoolean("CannonCleanupPending",cannonCleanupPending);
        for(int i=0;i<2;i++){tag.putInt("CannonCharge"+i,cannonCharge[i]);tag.putInt("CannonCooldown"+i,cannonCooldown[i]);tag.putLong("CannonFired"+i,cannonFired[i]);tag.putInt("CoreHits"+i,coreHits[i]);tag.put("CannonBefore"+i,cannonBefore[i].copy());tag.putInt("ShotTagBudget"+i,shotTagBudget[i]);if(cannonOperator[i]!=null)tag.putUUID("CannonOperator"+i,cannonOperator[i]);}return tag;
    }
    public void begin(TvCampaignSavedData campaign,TvMarineSiteR50.Site plan)
    {
        if(generation==campaign.generationR43&&campaign.owner!=null&&campaign.owner.equals(owner)&&!phase.equals("idle"))return;
        owner=campaign.owner;boss=null;generation=campaign.generationR43;site=plan.id();phase="loading";notice="迦基尔已进入近海，舰上电源与双炮岗位开始准备。";
        elapsed=spawnWait=missingTicks=powerCharge=holdTicks=0;cargoHealth=plan.cargoHealth();powerEnabled=false;lastCargoHit=-10000;
        for(int i=0;i<2;i++){cannonCharge[i]=cannonCooldown[i]=coreHits[i]=shotTagBudget[i]=0;cannonFired[i]=-10000;cannonOperator[i]=null;}setDirty();
    }
    public boolean bound(TvCampaignSavedData campaign)
    {return campaign.active.equals("gaghiel")&&owner!=null&&owner.equals(campaign.owner)&&generation==campaign.generationR43;}
}

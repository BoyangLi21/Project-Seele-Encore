package com.projectseele.entity;

import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.nbt.CompoundTag;
import java.util.Map;
import java.util.WeakHashMap;

/** The socket is driven by the physical plug director, including reverse and recovery travel. */
public final class EvaDorsalMechanism
{
    private static final EntityDataAccessor<Float> OPEN = SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> BOW = SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Boolean> OPTICS_DORMANT = SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final Map<EvaUnit01Entity, View> VIEWS = new WeakHashMap<>();
    public static boolean bootstrap() { return true; }
    public static void clearViewR30(EvaUnit01Entity eva){VIEWS.remove(eva);}
    private static final class View
    {
        final EvaPoseSignalClock open = new EvaPoseSignalClock(), bow = new EvaPoseSignalClock();
        float lastOpen = -1, lastBow = -1;
    }
    public static void define(SynchedEntityData data) { data.define(OPEN, 0F); data.define(BOW, 0F); data.define(OPTICS_DORMANT, false); }
    public static void set(EvaUnit01Entity eva, float open, float bow)
    {
        if (eva.level().isClientSide) return;
        if (open > .1F) eva.getEntityData().set(OPTICS_DORMANT, false);
        eva.getEntityData().set(OPEN, Math.max(0, Math.min(1, open)));
        eva.getEntityData().set(BOW, Math.max(0, Math.min(1, bow)));
    }
    public static float smooth(float x) { x = Math.max(0, Math.min(1, x)); return x*x*x*(x*(x*6-15)+10); }
    public static void prepare(EvaUnit01Entity eva, int ticks)
    { set(eva, smooth((ticks-12)/22F), smooth(ticks/22F)); }
    public static void seal(EvaUnit01Entity eva, int ticks)
    { set(eva, 1-smooth((ticks-12)/24F), 1-smooth((ticks-38)/22F)); }
    public static float open(EvaUnit01Entity eva) { return sample(eva, true); }
    public static float bow(EvaUnit01Entity eva) { return sample(eva, false); }
    public static boolean eyesEnabled(EvaUnit01Entity eva)
    {
        if (eva.getEntityData().get(OPTICS_DORMANT) && !eva.isBerserk()) return false;
        if (eva.isFirstBattleActive() && eva.firstBattleSignals().time(eva, 0) >= FirstBattleClip.DEATH_TICK / 20F) return false;
        return eva.isPoweredOn() && open(eva) < .001F && bow(eva) < .001F;
    }
    /** Surface colour and emission are separate: an empty hangar EVA retains
     * its normal painted eye surface, even when the optic light is disabled. */
    public static int eyeSurface(EvaUnit01Entity eva)
    {
        if(eva.getUnitVariant()!=EvaUnit01Entity.UNIT_01||eva.isExperimentalUnit())return 0;
        if(EvaBerserkMotionR34.silent(eva)||EvaShutdownR30.wreck(eva)
                ||dormantAfterBerserk(eva)&&!eva.isBerserk()
                ||eva.isFirstBattleActive()&&eva.firstBattleSignals().time(eva,0)>=FirstBattleClip.DEATH_TICK/20F)return 1;
        return eva.isBerserk()||eva.isFirstBattleActive()?2:0;
    }
    public static void afterBerserk(EvaUnit01Entity eva)
    {
        if (!eva.level().isClientSide && eva.getUnitVariant() == EvaUnit01Entity.UNIT_01 && !eva.isExperimentalUnit())
            eva.getEntityData().set(OPTICS_DORMANT, true);
    }
    public static boolean dormantAfterBerserk(EvaUnit01Entity eva)
    {return eva.getEntityData().get(OPTICS_DORMANT);}
    public static void rearmAfterRepair(EvaUnit01Entity eva)
    {
        if(!eva.level().isClientSide&&!eva.isBerserk()&&!eva.isFirstBattleActive()&&eva.getHealth()>50)
            eva.getEntityData().set(OPTICS_DORMANT,false);
    }
    private static float sample(EvaUnit01Entity eva, boolean opening)
    {
        float value = eva.getEntityData().get(opening ? OPEN : BOW);
        if (!eva.level().isClientSide) return value;
        View view = VIEWS.computeIfAbsent(eva, e -> new View());
        if (opening && value != view.lastOpen) { view.open.accept(value, false, false); view.lastOpen=value; }
        if (!opening && value != view.lastBow) { view.bow.accept(value, false, false); view.lastBow=value; }
        return (opening ? view.open : view.bow).sample(FirstBattleSignals.clientFrameTime());
    }
    public static void save(EvaUnit01Entity eva, CompoundTag tag)
    { tag.putFloat("DorsalOpen", eva.getEntityData().get(OPEN)); tag.putFloat("DorsalBow", eva.getEntityData().get(BOW)); tag.putBoolean("OpticsDormantAfterBerserk", eva.getEntityData().get(OPTICS_DORMANT)); }
    public static void load(EvaUnit01Entity eva, CompoundTag tag)
    { set(eva, tag.getFloat("DorsalOpen"), tag.getFloat("DorsalBow")); eva.getEntityData().set(OPTICS_DORMANT, tag.getBoolean("OpticsDormantAfterBerserk")); }
    private EvaDorsalMechanism() {}
}

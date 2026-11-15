package com.projectseele.entity;

import com.projectseele.config.SeeleConfig;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;

/**
 * R64 (M4): which combat core a Unit fights with.
 * <p>
 * Up to M3 each blow is begun, timed, chained and ended by code of its own in the Unit, a few thousand lines of
 * it: what may follow what and when is spread over those. In the new core a blow is one row of a table (start-up,
 * active and recovery ticks, when it may be cancelled into what, what it does when it lands) and one machine
 * reads the table, with the pilot's presses held in a short buffer.
 * <p>
 * The server's config decides ([eva_combat] model and hitStop) and every Unit carries the answer to its clients,
 * as with the movement model. The old core stays the default until the owner says otherwise.
 */
public final class EvaCombatModelR64
{
    public static final byte LEGACY=0,FRAMES=1;
    private static final EntityDataAccessor<Byte> MODEL=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.BYTE);
    private static final EntityDataAccessor<Boolean> TIERED=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.BOOLEAN);
    /** Review only: -Dprojectseele.combatModelR64=frames and -Dprojectseele.hitStopR64=tiered or flat stand in for the config. */
    private static final String REVIEW_MODEL=System.getProperty("projectseele.combatModelR64"),REVIEW_STOP=System.getProperty("projectseele.hitStopR64");

    /** Register base accessors before any subclass allocates its own IDs. */
    public static boolean bootstrap(){return true;}
    public static void define(SynchedEntityData data){data.define(MODEL,LEGACY);data.define(TIERED,true);}

    /** Server, every tick: the config decides. */
    public static void tick(EvaUnit01Entity e)
    {
        if(e.level().isClientSide)return;
        String model=REVIEW_MODEL!=null?REVIEW_MODEL:SeeleConfig.COMMON_SPEC.isLoaded()?SeeleConfig.EVA_COMBAT_MODEL.get():"legacy";
        String stop=REVIEW_STOP!=null?REVIEW_STOP:SeeleConfig.COMMON_SPEC.isLoaded()?SeeleConfig.EVA_HIT_STOP.get():"tiered";
        byte wanted="frames".equalsIgnoreCase(model)?FRAMES:LEGACY;boolean tiered=!"flat".equalsIgnoreCase(stop);
        if(e.getEntityData().get(MODEL)!=wanted)e.getEntityData().set(MODEL,wanted);
        if(e.getEntityData().get(TIERED)!=tiered)e.getEntityData().set(TIERED,tiered);
    }

    /** The new core is this Unit's: asked for, and a Unit it is built for (Unit-01 until the others' tables are written). */
    public static boolean frames(EvaUnit01Entity e)
    {
        // (A Unit built bare by a check has none of this data.)
        return e.getEntityData().hasItem(MODEL)&&e.getEntityData().get(MODEL)==FRAMES&&!e.isExperimentalUnit()&&e.getUnitVariant()==EvaUnit01Entity.UNIT_01
                &&!(e instanceof EvaPrototypeEntity);
    }

    /** Under the new core: the pause at a hit goes by how hard the blow is (the owner's choice, 2026-11-15); otherwise as up to M3. */
    public static boolean tiered(EvaUnit01Entity e){return frames(e)&&e.getEntityData().hasItem(TIERED)&&e.getEntityData().get(TIERED);}

    /**
     * R64 (M5): the Angels fight by the M5 rules (Sachiel's intents and strings, the tells, the dust where a body
     * meets ground or wall). They have no switch of their own: they follow the server's combat core, since what
     * they read of a Unit's blow is the frames core's row. Review only: -Dprojectseele.angelIntentR64=false keeps
     * the Angels of M4 under the frames core, to measure against.
     */
    private static final boolean ANGELS=!"false".equals(System.getProperty("projectseele.angelIntentR64"));
    public static boolean angels()
    {
        if(!ANGELS)return false;
        String model=REVIEW_MODEL!=null?REVIEW_MODEL:SeeleConfig.COMMON_SPEC.isLoaded()?SeeleConfig.EVA_COMBAT_MODEL.get():"legacy";
        return "frames".equalsIgnoreCase(model);
    }

    private EvaCombatModelR64(){}
}

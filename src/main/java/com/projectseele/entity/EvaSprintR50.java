package com.projectseele.entity;

import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.util.Mth;
import com.projectseele.util.WeakIdentityMap;

/** A distinct held dash input; the server owns its continuous blend and speed. */
public final class EvaSprintR50
{
    private static final EntityDataAccessor<Boolean> HELD=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Float> BLEND=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private static final WeakIdentityMap<EvaUnit01Entity,Float> PREVIOUS=new WeakIdentityMap<>();
    public static void define(SynchedEntityData data){data.define(HELD,false);data.define(BLEND,0F);}
    public static boolean held(EvaUnit01Entity e){return e.getEntityData().get(HELD);}
    public static void request(EvaUnit01Entity e,ServerPlayer pilot,boolean value)
    {
        if(e.level().isClientSide||e.getPilotEntity()!=pilot||e.isExperimentalUnit())return;
        e.getEntityData().set(HELD,value&&!e.isPilotControlLocked()&&e.isPoweredOn());
    }
    public static void tick(EvaUnit01Entity e)
    {
        float old=e.getEntityData().get(BLEND);PREVIOUS.put(e,old);
        if(e.level().isClientSide)return;
        boolean enabled=held(e)&&e.isPilotSprinting()&&!e.isPilotCrouching()&&!e.isPilotProne()
                &&e.isPoweredOn()&&!e.isPilotControlLocked()&&e.getPilotEntity()!=null
                &&e.getWeapon()!=EvaUnit01Entity.WEAPON_CANNON&&e.getWeapon()!=EvaUnit01Entity.WEAPON_N2
                &&e.getWeapon()!=EvaUnit01Entity.WEAPON_SHIELD_R45;
        if(e.getPilotEntity()==null)e.getEntityData().set(HELD,false);
        e.getEntityData().set(BLEND,Mth.approach(old,enabled?1:0,.1F));
    }
    public static float blend(EvaUnit01Entity e,float partial)
    {
        float current=e.getEntityData().get(BLEND);
        Float previous=PREVIOUS.get(e);
        return e.level().isClientSide?Mth.lerp(partial,previous==null?current:previous,current):current;
    }
    public static float speed(EvaUnit01Entity e){return 1+.2F*blend(e,1);}
    private EvaSprintR50(){}
}

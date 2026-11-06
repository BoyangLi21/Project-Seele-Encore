package com.projectseele.client;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.entity.Entity;
import com.projectseele.entity.SbwStaticShapesR24;
import java.util.*;

/** Avoid reloading identical, unticked remote copies of parked UN vehicles. */
public final class SbwPhantomLoadR24
{
    private static final boolean DISABLED=Boolean.getBoolean("projectseele.vanillaPhantomLoads");
    private record Entry(CompoundTag tag,int tick,long expires){}
    private static final WeakHashMap<Entity,Entry> previous=new WeakHashMap<>();
    public static void load(Entity entity,CompoundTag tag)
    {
        if(DISABLED||!SbwStaticShapesR24.vehicle(entity)||!entity.level().isClientSide||entity.level().getEntity(entity.getId())==entity)
        {entity.load(tag);return;}
        Entry old=previous.get(entity);boolean equal=old!=null&&tag.equals(old.tag);
        long now=System.nanoTime();
        if(equal&&entity.tickCount==old.tick&&now<old.expires&&entity.isAlive()&&!entity.isVehicle()&&!entity.isPassenger()
                &&entity.level().dimension().location().toString().equals("projectseele:geofront")
                &&entity.getX()>=6000&&entity.getX()<=7200&&entity.getZ()>=-7400&&entity.getZ()<=-5900)
            return;
        entity.load(tag);
        previous.put(entity,new Entry(tag.copy(),entity.tickCount,now+1_000_000_000L));
    }
    private SbwPhantomLoadR24(){}
}

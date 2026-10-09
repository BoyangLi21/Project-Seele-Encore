package com.projectseele.util;

import java.util.Arrays;
import net.minecraft.util.LinearCongruentialGenerator;
import net.minecraft.util.Mth;

/** Exact seed-dependent Voronoi corner offsets, reused across nearby queries. */
public final class BiomeCornerCache
{
    private static final int SIZE=8192;
    private static final ThreadLocal<Cache> LOCAL=ThreadLocal.withInitial(Cache::new);
    private record OwnedCache(Thread owner,Cache value){}
    private static volatile OwnedCache serverCache,renderCache;
    private static final class Cache
    {
        long seed;
        final boolean[] valid=new boolean[SIZE];
        final int[] xs=new int[SIZE],ys=new int[SIZE],zs=new int[SIZE];
        final double[] ox=new double[SIZE],oy=new double[SIZE],oz=new double[SIZE];
    }
    public static double distance(long seed,int x,int y,int z,double dx,double dy,double dz)
    {
        Cache c=cache();
        if(c.seed!=seed){c.seed=seed;Arrays.fill(c.valid,false);}
        int hash=x*73428767^y*912931^z*43828993;
        hash^=hash>>>16;int index=hash&(SIZE-1);
        if(!c.valid[index]||c.xs[index]!=x||c.ys[index]!=y||c.zs[index]!=z)
        {
            long value=seed;
            value=LinearCongruentialGenerator.next(value,x);
            value=LinearCongruentialGenerator.next(value,y);
            value=LinearCongruentialGenerator.next(value,z);
            value=LinearCongruentialGenerator.next(value,x);
            value=LinearCongruentialGenerator.next(value,y);
            value=LinearCongruentialGenerator.next(value,z);
            c.ox[index]=offset(value);
            value=LinearCongruentialGenerator.next(value,seed);c.oy[index]=offset(value);
            value=LinearCongruentialGenerator.next(value,seed);c.oz[index]=offset(value);
            c.xs[index]=x;c.ys[index]=y;c.zs[index]=z;c.valid[index]=true;
        }
        // Match vanilla's addition order, including its IEEE-754 rounding.
        return Mth.square(dz+c.oz[index])+Mth.square(dy+c.oy[index])+Mth.square(dx+c.ox[index]);
    }
    private static Cache cache()
    {
        // Only the exact owning thread uses these two slots. Worker threads
        // keep their independent ThreadLocal; no mutable corner cache is shared.
        Thread thread=Thread.currentThread();var server=serverCache;
        if(server!=null&&server.owner()==thread)return server.value();
        var render=renderCache;if(render!=null&&render.owner()==thread)return render.value();
        Cache value=LOCAL.get();
        if(thread.getName().equals("Server thread"))serverCache=new OwnedCache(thread,value);
        else if(thread.getName().equals("Render thread"))renderCache=new OwnedCache(thread,value);
        return value;
    }
    private static double offset(long value)
    {
        return ((double)Math.floorMod(value>>24,1024)/1024.0D-.5D)*.9D;
    }
    private BiomeCornerCache() {}
}

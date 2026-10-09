package com.projectseele.util;

import java.util.concurrent.atomic.AtomicReference;
import net.minecraft.world.level.biome.BiomeManager;

/** The new fast slots must be owned by exact Thread identity, including restarts. */
public final class BiomeCornerMainThreadR51Test
{
    public static void main(String[] args)throws Exception
    {
        var vanilla=BiomeManager.class.getDeclaredMethod("getFiddledDistance",long.class,int.class,int.class,int.class,double.class,double.class,double.class);
        vanilla.setAccessible(true);var failure=new AtomicReference<Throwable>();
        for(int restart=0;restart<2;restart++)
        {
            var threads=new Thread[3];
            for(int n=0;n<3;n++)
            {
                final int lane=n;threads[n]=new Thread(()->
                {
                    try
                    {
                        for(long seed:new long[]{0,-1,Long.MAX_VALUE,17103+lane})for(int k=0;k<24;k++)
                        {
                            int x=73428767*(k-12),y=lane*4096-k,z=43828993*(12-k);double dx=k/8D-1,dy=-.25,dz=.375;
                            double expected=(double)vanilla.invoke(null,seed,x,y,z,dx,dy,dz);
                            for(int repeat=0;repeat<2;repeat++)if(Double.doubleToRawLongBits(BiomeCornerCache.distance(seed,x,y,z,dx,dy,dz))!=Double.doubleToRawLongBits(expected))throw new AssertionError("Corner changed in "+Thread.currentThread().getName());
                        }
                    }
                    catch(Throwable error){failure.compareAndSet(null,error);}
                },new String[]{"Server thread","Render thread","Biome worker"}[n]);threads[n].start();
            }
            for(var thread:threads)thread.join();
        }
        if(failure.get()!=null)throw new AssertionError("Main-thread corner ownership failed",failure.get());
        System.out.println("Exact native biome distance: server/render/worker concurrent slots and same-name restarted owners PASS");
    }
}

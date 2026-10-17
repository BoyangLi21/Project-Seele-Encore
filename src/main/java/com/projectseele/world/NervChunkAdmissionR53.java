package com.projectseele.world;

import java.util.*;
import java.util.function.*;
import net.minecraft.world.level.ChunkPos;

/** Admission pacing only. Native loaded-state checks remain the authority. */
final class NervChunkAdmissionR53
{
    private final Map<ChunkPos,Integer> requested=new LinkedHashMap<>(),admitted=new LinkedHashMap<>();
    private long lastTick=Long.MIN_VALUE;

    void request(ChunkPos chunk,int radius)
    {
        if(radius!=0&&radius!=2)throw new IllegalArgumentException("Declared FULL or entity-ticking ticket required");
        requested.merge(Objects.requireNonNull(chunk),radius,Math::max);
    }
    void request(Map<ChunkPos,Integer> chunks){chunks.forEach(this::request);}
    void refresh(BiConsumer<ChunkPos,Integer> retain){admitted.forEach(retain);}
    boolean admittedAll(){return admitted.equals(requested);}

    void advance(long tick,BiPredicate<ChunkPos,Integer> ready,BiConsumer<ChunkPos,Integer> retain)
    {
        if(tick==lastTick)return;lastTick=tick;
        int inFlight=0;for(var entry:admitted.entrySet())if(!ready.test(entry.getKey(),entry.getValue()))inFlight++;
        int issued=0;
        for(var entry:requested.entrySet())
        {
            if(Objects.equals(admitted.get(entry.getKey()),entry.getValue()))continue;
            if(issued>=2||inFlight>=4)break;
            retain.accept(entry.getKey(),entry.getValue());admitted.put(entry.getKey(),entry.getValue());issued++;
            if(!ready.test(entry.getKey(),entry.getValue()))inFlight++;
        }
    }
}

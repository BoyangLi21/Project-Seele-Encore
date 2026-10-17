package com.projectseele.world;

import java.util.*;
import java.util.function.Function;
import net.minecraft.world.phys.AABB;

/** Immutable source geometry index. Every candidate still gets the original
 * exact AABB predicate, in source order; no collision surface is discarded. */
public final class NervStaticSpatialIndexR52<T>
{
    private static final double CELL=32;
    private static final long MAX_ENUMERATED_CELLS=32768;
    private record Cell(long x,long y,long z) implements Comparable<Cell>{
        @Override public int hashCode(){long h=x*0x9e3779b97f4a7c15L^Long.rotateLeft(y*0xc2b2ae3d27d4eb4fL,21)^Long.rotateLeft(z*0x165667b19e3779f9L,42);h^=h>>>33;h*=0xff51afd7ed558ccdL;h^=h>>>33;return Long.hashCode(h);}
        @Override public int compareTo(Cell b){int c=Long.compare(x,b.x);if(c==0)c=Long.compare(y,b.y);return c==0?Long.compare(z,b.z):c;}
    }
    private final List<T> values;
    private final AABB[] bounds;
    private final Map<Cell,int[]> cells;
    private final int[] oversized;

    public NervStaticSpatialIndexR52(List<T> source,Function<T,AABB> box)
    {
        values=List.copyOf(source);bounds=new AABB[values.size()];var building=new HashMap<Cell,List<Integer>>();var large=new ArrayList<Integer>();
        for(int i=0;i<values.size();i++)
        {
            var b=Objects.requireNonNull(box.apply(values.get(i)));requireFinite(b);bounds[i]=b;
            long x0=cell(b.minX),x1=last(b.minX,b.maxX),y0=cell(b.minY),y1=last(b.minY,b.maxY),z0=cell(b.minZ),z1=last(b.minZ,b.maxZ);
            if(large(x0,x1,y0,y1,z0,z1)){large.add(i);continue;}
            for(long x=x0;x<=x1;x++)for(long y=y0;y<=y1;y++)for(long z=z0;z<=z1;z++)
                building.computeIfAbsent(new Cell(x,y,z),key->new ArrayList<>()).add(i);
        }
        var frozen=new HashMap<Cell,int[]>();building.forEach((key,v)->frozen.put(key,v.stream().mapToInt(Integer::intValue).toArray()));
        // Compact MapN uses linear probing; regular spatial coordinates can
        // form long clusters. Keep the immutable view of the hashed buckets.
        cells=Collections.unmodifiableMap(frozen);oversized=large.stream().mapToInt(Integer::intValue).toArray();
    }

    public List<T> query(AABB query)
    {
        requireFinite(query);long x0=cell(query.minX),x1=last(query.minX,query.maxX),y0=cell(query.minY),y1=last(query.minY,query.maxY),z0=cell(query.minZ),z1=last(query.minZ,query.maxZ);
        var candidates=new BitSet(values.size());
        if(large(x0,x1,y0,y1,z0,z1)||((double)x1-x0+1)*((double)y1-y0+1)*((double)z1-z0+1)>=values.size())candidates.set(0,values.size());
        else
        {
            for(int id:oversized)candidates.set(id);
            for(long x=x0;x<=x1;x++)for(long y=y0;y<=y1;y++)for(long z=z0;z<=z1;z++)
            {var row=cells.get(new Cell(x,y,z));if(row!=null)for(int id:row)candidates.set(id);}
        }
        var result=new ArrayList<T>();
        for(int id=candidates.nextSetBit(0);id>=0;id=candidates.nextSetBit(id+1))
            if(bounds[id].intersects(query))result.add(values.get(id));
        return List.copyOf(result);
    }

    private static long cell(double value){return (long)Math.floor(value/CELL);}
    private static long last(double min,double max){return Math.max(cell(min),cell(Math.nextDown(max)));}
    private static boolean large(long x0,long x1,long y0,long y1,long z0,long z1)
    {return ((double)x1-x0+1)*((double)y1-y0+1)*((double)z1-z0+1)>MAX_ENUMERATED_CELLS;}
    private static void requireFinite(AABB b)
    {if(!Double.isFinite(b.minX)||!Double.isFinite(b.minY)||!Double.isFinite(b.minZ)||!Double.isFinite(b.maxX)||!Double.isFinite(b.maxY)||!Double.isFinite(b.maxZ)
            ||Math.max(Math.max(Math.abs(b.minX),Math.abs(b.maxX)),Math.max(Math.abs(b.minZ),Math.abs(b.maxZ)))>30_000_000
            ||Math.max(Math.abs(b.minY),Math.abs(b.maxY))>30_000_000)throw new IllegalArgumentException("Finite actual Minecraft geometry required");}
}

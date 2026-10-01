package com.projectseele.world;

import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import net.minecraft.core.Holder;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.biome.*;
import java.util.*;
import java.util.stream.Stream;

/** Temperate woodland/meadow mosaics outside explicitly reserved authored facilities. */
public final class RegionalEcologyBiomeSourceR44 extends BiomeSource
{
    public static final Codec<RegionalEcologyBiomeSourceR44> CODEC=RecordCodecBuilder.create(i->i.group(
            Biome.CODEC.fieldOf("civil").forGetter(s->s.civil),
            Biome.CODEC.fieldOf("meadow").forGetter(s->s.meadow),
            Biome.CODEC.fieldOf("woodland").forGetter(s->s.woodland),
            Biome.CODEC.fieldOf("highland").forGetter(s->s.highland),
            Codec.LONG.optionalFieldOf("seed",0L).forGetter(s->s.seed),
            Codec.INT.listOf().listOf().fieldOf("reserved_bounds").forGetter(s->s.bounds),
            Codec.INT.listOf().listOf().optionalFieldOf("underground_reserved_bounds",List.of()).forGetter(s->s.undergroundBounds),
            Codec.INT.listOf().listOf().optionalFieldOf("protected_volumes",List.of()).forGetter(s->s.protectedVolumes)
    ).apply(i,RegionalEcologyBiomeSourceR44::new));
    private final Holder<Biome> civil,meadow,woodland,highland;
    private final long seed;
    private final List<List<Integer>> bounds;
    private final List<List<Integer>> undergroundBounds;
    private final List<List<Integer>> protectedVolumes;
    private final Map<Long,List<List<Integer>>> volumeTiles;
    private final Map<Long,List<List<Integer>>> reservationTiles;
    public RegionalEcologyBiomeSourceR44(Holder<Biome> civil,Holder<Biome> meadow,Holder<Biome> woodland,
                                       Holder<Biome> highland,long seed,List<List<Integer>> bounds,List<List<Integer>> undergroundBounds,List<List<Integer>> protectedVolumes)
    {
        this.civil=civil;this.meadow=meadow;this.woodland=woodland;this.highland=highland;this.seed=seed;
        if(bounds.stream().anyMatch(b->b.size()!=4||b.get(0)>b.get(2)||b.get(1)>b.get(3)))throw new IllegalArgumentException("Ecology reservation bounds");
        this.bounds=bounds.stream().map(List::copyOf).toList();
        if(undergroundBounds.stream().anyMatch(b->b.size()!=4||b.get(0)>b.get(2)||b.get(1)>b.get(3)))throw new IllegalArgumentException("Underground ecology reservation bounds");
        this.undergroundBounds=undergroundBounds.stream().map(List::copyOf).toList();
        if(protectedVolumes.stream().anyMatch(b->b.size()!=6||b.get(0)>b.get(3)||b.get(1)>b.get(4)||b.get(2)>b.get(5)))throw new IllegalArgumentException("Ecology protected 3D volumes");
        this.protectedVolumes=protectedVolumes.stream().map(List::copyOf).toList();
        Map<Long,List<List<Integer>>> volumes=new HashMap<>();
        for(List<Integer> b:this.protectedVolumes)
            for(int x=b.get(0)>>6;x<=b.get(3)>>6;x++)
                for(int z=b.get(2)>>6;z<=b.get(5)>>6;z++)
                    volumes.computeIfAbsent(((long)x<<32)^(z&0xffffffffL),k->new ArrayList<>()).add(b);
        volumes.replaceAll((k,v)->List.copyOf(v));this.volumeTiles=Map.copyOf(volumes);
        Map<Long,List<List<Integer>>> tiles=new HashMap<>();
        for(List<Integer> b:this.bounds)
            for(int x=b.get(0)>>6;x<=b.get(2)>>6;x++)
                for(int z=b.get(1)>>6;z<=b.get(3)>>6;z++)
                    tiles.computeIfAbsent(((long)x<<32)^(z&0xffffffffL),k->new ArrayList<>()).add(b);
        tiles.replaceAll((k,v)->List.copyOf(v));this.reservationTiles=Map.copyOf(tiles);
    }
    @Override protected Codec<? extends BiomeSource> codec(){return CODEC;}
    @Override protected Stream<Holder<Biome>> collectPossibleBiomes(){return Stream.of(civil,meadow,woodland,highland);}
    public boolean reserved(int x,int z)
    {
        List<List<Integer>> boxes=reservationTiles.get(((long)(x>>6)<<32)^((z>>6)&0xffffffffL));
        return boxes!=null&&boxes.stream().anyMatch(b->x>=b.get(0)&&x<=b.get(2)&&z>=b.get(1)&&z<=b.get(3));
    }
    public boolean reservedBelow(int x,int z)
    {
        return undergroundBounds.stream().anyMatch(b->x>=b.get(0)&&x<=b.get(2)&&z>=b.get(1)&&z<=b.get(3));
    }
    public List<List<Integer>> protectedVolumes(){return protectedVolumes;}
    public boolean protectedAt(BlockPos p)
    {
        List<List<Integer>> boxes=volumeTiles.get(((long)(p.getX()>>6)<<32)^((p.getZ()>>6)&0xffffffffL));
        return boxes!=null&&boxes.stream().anyMatch(b->p.getX()>=b.get(0)&&p.getX()<=b.get(3)
                &&p.getY()>=b.get(1)&&p.getY()<=b.get(4)&&p.getZ()>=b.get(2)&&p.getZ()<=b.get(5));
    }
    public boolean permitsVegetationAt(BlockPos p)
    {
        if(protectedAt(p))return false;
        return p.getY()<0?p.getY()>=-512&&p.getY()<=-405&&!reservedBelow(p.getX(),p.getZ())
                :p.getY()>=60&&p.getY()<=310&&!reserved(p.getX(),p.getZ());
    }
    public static double mosaic(int x,int z,long seed)
    {
        return noise(x/192D,z/192D,seed)*.78+noise(x/56D,z/56D,seed^0x6a09e667f3bcc909L)*.22;
    }
    private static double noise(double x,double z,long seed)
    {
        int ix=(int)Math.floor(x),iz=(int)Math.floor(z);double a=x-ix,b=z-iz;
        a=a*a*(3-2*a);b=b*b*(3-2*b);
        double left=unit(ix,iz,seed)*(1-b)+unit(ix,iz+1,seed)*b;
        double right=unit(ix+1,iz,seed)*(1-b)+unit(ix+1,iz+1,seed)*b;
        return left*(1-a)+right*a;
    }
    private static double unit(int x,int z,long seed)
    {
        long h=seed^x*341873128712L^z*132897987541L;h^=h>>>33;h*=0xff51afd7ed558ccdL;h^=h>>>33;h*=0xc4ceb9fe1a85ec53L;h^=h>>>33;
        return (h>>>32)/4294967295D;
    }
    @Override public Holder<Biome> getNoiseBiome(int x,int y,int z,Climate.Sampler sampler)
    {
        int wx=x*4,wz=z*4;
        if(y<0)
        {
            if(y*4<-512||y*4>-405||reservedBelow(wx,wz))return civil;
            return ecologicalBiomeBelow(wx,wz,sampler);
        }
        if(reserved(wx,wz))return civil;
        return ecologicalBiome(wx,y*4,wz,sampler);
    }
    public Holder<Biome> ecologicalBiome(int x,int y,int z,Climate.Sampler sampler)
    {
        if(reserved(x,z))return civil;
        return chooseEcologicalBiome(x,y,z,sampler);
    }
    public Holder<Biome> ecologicalBiomeBelow(int x,int z,Climate.Sampler sampler)
    {
        if(reservedBelow(x,z))return civil;
        return chooseEcologicalBiome(x,80,z,sampler);
    }
    private Holder<Biome> chooseEcologicalBiome(int x,int y,int z,Climate.Sampler sampler)
    {
        double pattern=mosaic(x,z,seed);
        // A seedless dimension definition uses climate noise that RandomState
        // initializes from that world's seed. Explicit migrated saves retain
        // their measured world seed and their existing cartographic mosaic.
        if(seed==0)
        {
            Climate.TargetPoint climate=sampler.sample(x>>2,20,z>>2);
            pattern=pattern*.72+(Climate.unquantizeCoord(climate.humidity())+1)*.09
                    +(Climate.unquantizeCoord(climate.temperature())+1)*.05;
        }
        if(y>=136&&pattern>.34)return highland;
        return pattern>.43?woodland:meadow;
    }
}

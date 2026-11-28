import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import java.util.concurrent.*;
/** Rebuild the nine-channel height rasters consumed by the road and hillside renewal tools. */
public class SurfaceRoadSurvey {    static final Set<String> soils=Set.of("grass_block","dirt","coarse_dirt","podzol","rooted_dirt","moss_block");
    static final Set<String> rocks=Set.of("stone","deepslate","granite","diorite","andesite","gravel","sand","clay","mud","tuff","calcite","sandstone","red_sandstone","blackstone","smooth_basalt");
    static final Set<String> herbs=Set.of("grass","tall_grass","fern","large_fern","dandelion","poppy","azure_bluet","oxeye_daisy","cornflower","lily_of_the_valley","dead_bush","sweet_berry_bush","vine","moss_carpet","snow","brown_mushroom","red_mushroom","peony","lilac","rose_bush","sunflower","blue_orchid","allium");
    static int kind(String key){
        if(!key.startsWith("minecraft:"))return 7;
        String n=key.substring(10);
        if(n.equals("air")||n.equals("cave_air")||n.equals("void_air"))return 0;
        if(soils.contains(n))return 1;
        if(rocks.contains(n)||n.endsWith("_ore"))return 2;
        if(n.equals("water"))return 3;
        if(n.endsWith("_leaves")||n.endsWith("_log")||n.endsWith("_wood"))return 4;
        if(herbs.contains(n)||n.endsWith("_tulip")||n.endsWith("_sapling"))return 5;
        if(n.equals("seagrass")||n.equals("tall_seagrass")||n.startsWith("kelp"))return 6;
        return 7;
    }

    static int classify(String s) {
        String n=R66RegionPatch.plain(s);
        if(n.contains("asphalt") || n.startsWith("projectseele:road_mark"))return 6;
        if(n.startsWith("trafficcraft:concrete") || n.contains("road_sidewalk"))return 7;
        if(n.contains("rail") || n.contains("ballast") || n.startsWith("mtr:"))return 9;
        if(n.startsWith("trafficcraft:") || n.equals("minecraft:light") || n.equals("minecraft:barrier"))return 10;
        int type=kind(n);
        return switch(type){case 0,5->0;case 1->1;case 2->2;case 3,6->3;case 4->4;default->8;};
    }
    static void run(Path folder,Path out,String[] args)throws Exception {
        String tag=args[0];int[] a=Arrays.stream(args,1,args.length).mapToInt(Integer::parseInt).toArray();
        int x0=a[0],z0=a[1],x1=a[2],z1=a[3],lo=a[4],hi=a[5];
        File dest=out.resolve(tag+".raw.gz").toFile();
        try(DataOutputStream d=R66RegionPatch.zipOut(dest.toPath())){
            for(int v:a)d.writeInt(v);
            for(int rz=z0>>9;rz<=z1>>9;rz++)for(int rx=x0>>9;rx<=x1>>9;rx++){
                Path p=folder.resolve("r."+rx+"."+rz+".mca");if(!Files.isRegularFile(p))continue;
                try(RandomAccessFile in=new RandomAccessFile(p.toFile(),"r")){
                    for(int cz=Math.max(z0>>4,rz*32);cz<=Math.min(z1>>4,rz*32+31);cz++)for(int cx=Math.max(x0>>4,rx*32);cx<=Math.min(x1>>4,rx*32+31);cx++){
                        int ci=(cz&31)*32+(cx&31);if(in.length()<8192)continue;in.seek(ci*4L);if(in.readInt()==0)continue;
                        var root=R66RegionPatch.root(R66RegionPatch.raw(in,ci));var secs=R66RegionPatch.sections(root);
                        int[][] ys=new int[11][256];for(var row:ys)Arrays.fill(row,-2048);
                        for(int sy=lo>>4;sy<=hi>>4;sy++){
                            var row=secs.get(sy);if(row==null||!row.containsKey("block_states"))continue;
                            var sec=new R66RegionPatch.Sec(row);
                            int[] cls=sec.pal.stream().mapToInt(SurfaceRoadSurvey::classify).toArray();
                            if(cls.length==1 && cls[0]==0)continue;
                            for(int i=0;i<4096;i++){int k=cls[sec.ids[i]];if(k!=0)ys[k][i&255]=(sy<<4)+(i>>8);}
                        }
                        d.writeInt(cx);d.writeInt(cz);
                        for(int k:new int[]{1,2,3,4,6,7,8,9,10})for(int v:ys[k])d.writeShort(v);
                    }
                }
            }
        }
        System.out.println(tag);
    }
    public static void main(String[] a)throws Exception{
        Path world=Path.of(a[0]),out=Path.of(a[1]); Files.createDirectories(out);
        String[] zones={
            "air 48 -660 545 -175 40 240",
            "schoolroad -210 -920 345 -415 50 253",
            "valley 1400 882 2600 1580 -125 120",
            "house 2940 1388 3099 1540 -117 72",
            "south -380 1420 680 2210 -127 256"
        };
        for(String zone:zones) {
            String[] fields=zone.split(" ");
            if(a.length==2 || java.util.Arrays.asList(a).subList(2,a.length).contains(fields[0]))run(world,out,fields);
        }
    }
}

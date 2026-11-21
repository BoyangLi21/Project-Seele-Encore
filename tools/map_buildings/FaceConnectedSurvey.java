import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;
import java.util.zip.*;
import net.minecraft.nbt.*;

/**
 * Offline region pass for six-face connectivity over every saved GeoFront block height.
 * Vertical solid runs are the graph nodes. Grounded geometry costs one node per
 * uninterrupted column. Inter-region joins retain the real Y intervals at every edge.
 * Compile/run with the project's mapped Minecraft 1.20.1 development classpath.
 */
public final class FaceConnectedSurvey {
    static final Set<String> OPEN = Set.of("minecraft:air","minecraft:cave_air","minecraft:void_air",
            "minecraft:water","minecraft:lava","minecraft:bubble_column","minecraft:light","minecraft:structure_void",
            "minecraft:kelp","minecraft:kelp_plant","minecraft:seagrass","minecraft:tall_seagrass");
    static final int SIZE = 512, COLUMNS = SIZE * SIZE;
    final int ymin, ymax, sections, rx, rz;
    final List<String> names = new ArrayList<>();
    final Map<String,Integer> indices = new HashMap<>();
    final Chunk[] chunks = new Chunk[1024];
    final int[] start = new int[COLUMNS], end = new int[COLUMNS];
    int used = 1;
    int[] parent = new int[1<<19], weight = new int[parent.length];
    short[] low = new short[parent.length], high = new short[parent.length];
    byte[] anchor = new byte[parent.length];
    int full, partial, scannedSections;
    final Map<String,Integer> statuses = new TreeMap<>();

    FaceConnectedSurvey(int x,int z,int bottom,int top) {
        rx=x; rz=z; ymin=bottom; ymax=top; sections=(top-bottom)/16;
    }

    record Section(int[] palette,long[] data,int bits,int per,boolean solid,boolean open,boolean[] occupancy) {
        int id(int at) {
            if (palette.length==1) return 0;
            return (int)(data[at/per] >>> ((at%per)*bits)) & ((1<<bits)-1);
        }
    }
    record Chunk(Section[] sections, byte status) {}
    int name(String value) {
        Integer found=indices.get(value);
        if (found!=null) return found;
        int id=names.size(); names.add(value); indices.put(value,id); return id;
    }
    Chunk decodeChunk(CompoundTag nbt) {
        String status=nbt.getString("Status").replace("minecraft:","");
        boolean complete=status.equals("full");
        statuses.merge(status,1,Integer::sum);
        if(complete) full++; else partial++;
        Section[] cube = new Section[sections];
        for (Tag tag:nbt.getList("sections",Tag.TAG_COMPOUND)) {
            CompoundTag section=(CompoundTag)tag;
            CompoundTag states=section.getCompound("block_states");
            ListTag palette=states.getList("palette",Tag.TAG_COMPOUND);
            if(palette.isEmpty()) continue;
            int sy=section.getByte("Y")-Math.floorDiv(ymin,16);
            int[] ids=new int[palette.size()];
            boolean allSolid=true,allOpen=true;
            boolean[] occ=new boolean[ids.length];
            for(int k=0;k<ids.length;k++) {
                String state=palette.getCompound(k).getString("Name");
                ids[k]=name(state); occ[k]=!OPEN.contains(state);
                allSolid &= occ[k]; allOpen &= !occ[k];
            }
            if(sy<0 || sy>=sections) {
                if(!allOpen) throw new IllegalStateException("Solid section outside requested height at "+rx+","+rz+":"+section.getByte("Y"));
                continue;
            }
            int bits=Math.max(4,32-Integer.numberOfLeadingZeros(ids.length-1));
            long[] data=states.getLongArray("data");
            if(ids.length>1 && data.length<((4095/(64/bits))+1)) throw new IllegalStateException("Incomplete block palette");
            cube[sy]=new Section(ids,data,bits,64/bits,allSolid,allOpen,occ);
            scannedSections++;
        }
        return new Chunk(cube,(byte)(complete?2:1));
    }

    void add(int a,int b,boolean pending) {
        if(used==parent.length) {
            int n=used*2; parent=Arrays.copyOf(parent,n);weight=Arrays.copyOf(weight,n);
            low=Arrays.copyOf(low,n);high=Arrays.copyOf(high,n);anchor=Arrays.copyOf(anchor,n);
        }
        low[used]=(short)a;high[used]=(short)b;parent[used]=used;weight[used]=1;
        anchor[used]=(byte)((a==ymin?1:0)|(pending?2:0));used++;
    }
    void columnRuns(Chunk c,int chunkX,int chunkZ) {
        int[] occupancy=new int[sections*256];
        for(int s=0;s<sections;s++) {
            Section section=c.sections[s]; if(section==null || section.open)continue;
            if(section.solid){Arrays.fill(occupancy,s*256,(s+1)*256,65535);continue;}
            for(int j=0;j<4096;j++) if(section.occupancy[section.id(j)]) occupancy[s*256+(j&255)]|=1<<(j>>8);
        }
        for(int k=0;k<256;k++) {
            int pos=(chunkZ*16+(k>>4))*512+chunkX*16+(k&15);
            start[pos]=used;
            int running=-1;
            for(int s=0;s<sections;s++) {
                int mask=occupancy[s*256+k],offset=s*16;
                if(mask==65535) { if(running<0)running=offset;continue; }
                if(running>=0) {
                    int ones=Integer.numberOfTrailingZeros(~mask);
                    add(ymin+running,ymin+offset+ones-1,c.status==1);
                    mask&=~((1<<ones)-1);running=-1;
                }
                while(mask!=0) {
                    int lo=Integer.numberOfTrailingZeros(mask);
                    int n=Integer.numberOfTrailingZeros(~(mask>>>lo));
                    if(lo+n==16) {running=offset+lo;break;}
                    add(ymin+offset+lo,ymin+offset+lo+n-1,c.status==1);
                    mask&=~(((1<<n)-1)<<lo);
                }
            }
            if(running>=0)add(ymin+running,ymax-1,c.status==1);
            end[pos]=used;
        }
    }
    int root(int a){while(parent[a]!=a){parent[a]=parent[parent[a]];a=parent[a];}return a;}
    void union(int x,int z) {
        int a=root(x), b=root(z);if(a==b)return;
        if(weight[a]<weight[b]){int t=a;a=b;b=t;}
        parent[b]=a;weight[a]+=weight[b];anchor[a]|=anchor[b];
    }
    void join(int a,int b) {
        int j=start[a], k=start[b];
        while(j<end[a] && k<end[b]) {
            if(low[j]<=high[k] && low[k]<=high[j])union(j,k);
            if(high[j]<high[k])j++;else k++;
        }
    }
    Chunk chunkAt(int x,int z){return chunks[(z>>4)*32+(x>>4)];}
    int material(Chunk c,int xz,int y) {
        Section s=c.sections[(y-ymin)>>4];return s.palette[s.id(((y&15)<<8)|xz)];
    }
    boolean nearGround(int x,int z,int lo,int hi,int[] group) {
        for(int zz=Math.max(0,z-1);zz<=Math.min(511,z+1);zz++)for(int xx=Math.max(0,x-1);xx<=Math.min(511,x+1);xx++){
            int pos=zz*512+xx;
            for(int i=start[pos];i<end[pos] && low[i]<=hi+1;i++)if(high[i]>=lo-1 && group[root(i)]==0)return true;
        }
        return false;
    }
    void analyze(Path input,Path out)throws Exception {
        byte[] file=Files.readAllBytes(input);
        String hash=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(file));
        Path done=out.resolve(input.getFileName()+".sha256");
        Path output=out.resolve(input.getFileName()+".survey.gz");
        if(Files.exists(output) && Files.exists(done) && Files.readString(done).equals(hash)) {
            try(var cached=new DataInputStream(new GZIPInputStream(Files.newInputStream(output)))) {
                if(cached.readInt()==0x46435231 && cached.readInt()==rx && cached.readInt()==rz
                        && cached.readInt()==ymin && cached.readInt()==ymax) return;
            } catch(EOFException | ZipException incomplete) {
                // Rebuild a truncated cached header from the original region.
            }
        }
        if(file.length!=0 && file.length<8192)throw new IOException("Truncated MCA "+input);
        for(int i=0;i<1024 && file.length>=8192;i++){
            int j=4*i,offset=((file[j]&255)<<16|(file[j+1]&255)<<8|(file[j+2]&255))*4096;
            if(offset==0)continue;
            int length=(file[offset]&255)<<24|(file[offset+1]&255)<<16|(file[offset+2]&255)<<8|(file[offset+3]&255);
            if(file[offset+4]!=2)throw new IOException("Unsupported chunk compression "+input+"#"+i);
            try(var in=new DataInputStream(new BufferedInputStream(new InflaterInputStream(new ByteArrayInputStream(file,offset+5,length-1))))) {
                Chunk c=decodeChunk(NbtIo.read(in));chunks[i]=c;columnRuns(c,i%32,i/32);
            }
        }
        for(int z=0;z<512;z++)for(int x=0;x<512;x++) {
            int p=z*512+x;if(start[p]==end[p])continue;
            if(x>0)join(p,p-1);if(z>0)join(p,p-512);
            if((x>0 && chunkAt(x-1,z)==null)||(x<511 && chunkAt(x+1,z)==null)||
                    (z>0 && chunkAt(x,z-1)==null)||(z<511 && chunkAt(x,z+1)==null))
                for(int i=start[p];i<end[p];i++)anchor[root(i)]|=2;
        }
        int[] group=new int[used];
        int number=0;
        for(int i=1;i<used;i++)if(root(i)==i && (anchor[i]&1)==0)group[i]=++number;
        int[] sizes=new int[number+1];byte[] flags=new byte[number+1];
        for(int i=1;i<used;i++) {int r=root(i),g=group[r];if(g>0){sizes[g]+=high[i]-low[i]+1;flags[g]|=anchor[r];}}
        Path tmp=out.resolve(input.getFileName()+".writing");
        try(var data=new DataOutputStream(new BufferedOutputStream(new GZIPOutputStream(Files.newOutputStream(tmp),1<<16),1<<16))) {
            data.writeInt(0x46435231); data.writeInt(rx);data.writeInt(rz);data.writeInt(ymin);data.writeInt(ymax);
            data.writeInt(full);data.writeInt(partial);data.writeInt(scannedSections);data.writeUTF(hash);
            data.writeInt(statuses.size()); for(var e:statuses.entrySet()){data.writeUTF(e.getKey());data.writeInt(e.getValue());}
            for(Chunk c:chunks)data.writeByte(c==null?0:c.status);
            data.writeInt(names.size());for(String s:names)data.writeUTF(s);
            for(int side=0;side<4;side++)for(int at=0;at<512;at++){
                int p=switch(side){case 0->at*512;case 1->at*512+511;case 2->at;default->511*512+at;};
                data.writeShort(end[p]-start[p]);
                for(int j=start[p];j<end[p];j++){data.writeShort(low[j]);data.writeShort(high[j]);data.writeInt(group[root(j)]);}
            }
            data.writeInt(number);
            for(int i=1;i<=number;i++){data.writeInt(sizes[i]);data.writeByte(flags[i]);}
            for(int z=0;z<512;z++)for(int x=0;x<512;x++) {
                int pos=z*512+x,k=(z&15)*16+(x&15);
                for(int j=start[pos];j<end[pos];j++) {
                    int g=group[root(j)];
                    if(g==0 || (flags[g]&2)!=0)continue;
                    Chunk c=chunkAt(x,z);
                    int bottom=low[j],top=high[j],gap=j>start[pos]?bottom-high[j-1]-1:ymax-ymin;
                    boolean near=nearGround(x,z,bottom,top,group);
                    for(int lo=bottom;lo<=top;) {
                        int state=material(c,k,lo),hi=lo;
                        while(hi<top && material(c,k,hi+1)==state)hi++;
                        data.writeInt(g);data.writeInt(pos);data.writeShort(lo);data.writeShort(hi);
                        data.writeShort(state);data.writeShort(gap);data.writeBoolean(near);lo=hi+1;
                    }
                }
            }
        }
        Files.move(tmp,output,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
        Files.writeString(done,hash);System.out.println(input.getFileName()+" "+full+"/"+partial+" "+number);
    }
    public static void main(String[] args)throws Exception {
        Path input=Path.of(args[0]),out=Path.of(args[1]);Files.createDirectories(out);
        int ymin=Integer.parseInt(args[2]),ymax=Integer.parseInt(args[3]),workers=Integer.parseInt(args[4]);
        if((ymin&15)!=0 || (ymax&15)!=0 || ymin>=ymax)throw new IllegalArgumentException("Unaligned height bounds");
        List<Path> paths;
        try(var files=Files.list(input)){paths=files.filter(p->p.getFileName().toString().matches("r\\.-?\\d+\\.-?\\d+\\.mca"))
                .filter(p->args.length<6 || p.getFileName().toString().equals(args[5])).sorted().toList();}
        ExecutorService pool=Executors.newFixedThreadPool(workers);
        try {
            List<Future<?>> jobs=new ArrayList<>();
            for(Path path:paths)jobs.add(pool.submit(()->{
                String[] key=path.getFileName().toString().split("\\.");
                new FaceConnectedSurvey(Integer.parseInt(key[1]),Integer.parseInt(key[2]),ymin,ymax).analyze(path,out);return null;
            }));
            for(var job:jobs)job.get();
        } finally {pool.shutdownNow();}
    }
}

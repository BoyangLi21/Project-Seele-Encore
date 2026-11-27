import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import static java.nio.charset.StandardCharsets.UTF_8;

/** Rebind a checked surface restyle to both durable journey inverses and its regeneration recipe.
 *  Run on a stopped copy. All generated files go to a separate overlay. */
@SuppressWarnings({"unchecked","rawtypes"})
public class Tokyo3CargoR66 extends R66RegionPatch {
    static final Path DATA=Path.of("dimensions/projectseele/geofront/data");
    static final class Edit {
        final int x,y,z; final String before,after;
        Edit(String[] a){x=Integer.parseInt(a[0]);y=Integer.parseInt(a[1]);z=Integer.parseInt(a[2]);before=a[3];after=a[4];}
    }
    static long packed(int x,int y,int z){return ((x&0x3ffffffL)<<38)|((z&0x3ffffffL)<<12)|(y&4095);}
    static int x(long p){return (int)(p>>38);} static int y(long p){return (int)(p<<52>>52);} static int z(long p){return (int)(p<<26>>38);}
    static Map tag(Map m,String k){return (Map)m.get(k);}
    static String uuid(int[] u){return new UUID(((long)u[0]<<32)|(u[1]&0xffffffffL),((long)u[2]<<32)|(u[3]&0xffffffffL)).toString();}
    static Map load(Path p)throws Exception{try(var in=zipIn(p)){return root(in.readAllBytes());}}
    static void save(Path p,Map m)throws Exception{Files.createDirectories(p.getParent());Path tmp=p.resolveSibling(p.getFileName()+".tmp");try(var out=zipOut(tmp)){out.write(bytes(m));}Files.move(tmp,p,StandardCopyOption.REPLACE_EXISTING);}
    static Map<Long,Map> indexed(Seq list){var rows=new LinkedHashMap<Long,Map>();for(Object c:list){var row=(Map)c;if(rows.put((long)row.get("Pos"),row)!=null)throw new IllegalStateException("Duplicate image");}return rows;}
    static List<Edit> edits(Path p)throws Exception{var edits=new ArrayList<Edit>();try(var reader=new BufferedReader(new InputStreamReader(zipIn(p),UTF_8))){for(String line;(line=reader.readLine())!=null;)edits.add(new Edit(line.split("\t")));}return edits;}
    static Map image(String s){return new LinkedHashMap(Map.of("State",state(s)));}
    static void verify(Map row,String expected,String context){String actual=row==null?AIR:name(row.get("State"));if(!actual.equals(expected)||row!=null&&(row.containsKey("NBT")||row.containsKey("Data")))throw new IllegalStateException(context+" "+expected+" actual "+actual);}
    static void replace(Map<Long,Map> rows,long pos,Map value){if(value==null)rows.remove(pos);else rows.put(pos,value);}
    static Map cell(long pos,String s){var c=image(s);c.put("Pos",pos);return c;}
    static Map op(long pos,String before,String after){return new LinkedHashMap(Map.of("Pos",pos,"Before",image(before),"After",image(after)));}
    static void writeRows(Map map,String key,Map<Long,Map> values){Seq s=new Seq(10);s.addAll(values.values());map.put(key,s);}
    static void journal(Map j,List<Edit> edits,int cx,int cz){
        var cells=indexed((Seq)j.get("Cells"));var detach=indexed((Seq)j.get("Ops1"));var place=indexed((Seq)j.get("Ops2"));
        int s=(int)j.get("SourceY"),d=(int)j.get("TargetY");
        for(Edit e:edits){long p=packed(e.x,e.y,e.z), sp=packed(cx+e.x,s+e.y,cz+e.z),dp=packed(cx+e.x,d+e.y,cz+e.z);
            verify(cells.get(p),e.before,"journal cell "+p);
            if(!e.before.equals(AIR)){verify(tag(detach.get(sp),"Before"),e.before,"detach");verify(tag(place.get(dp),"After"),e.before,"place");verify(tag(place.get(dp),"Before"),AIR,"unclear destination");}
            boolean remove=e.after.equals(AIR);replace(cells,p,remove?null:cell(p,e.after));replace(detach,sp,remove?null:op(sp,e.after,AIR));replace(place,dp,remove?null:op(dp,AIR,e.after));}
        writeRows(j,"Cells",cells);writeRows(j,"Ops1",detach);writeRows(j,"Ops2",place);
        var initial=new HashSet<Long>();Map<Long,Map> previous=new HashMap<>();
        for(int k=0;k<4;k++)for(Object row:(Seq)j.get("Ops"+k)){Map r=(Map)row;long p=(long)r.get("Pos");initial.add(p);Map prev=previous.put(p,tag(r,"After"));if(prev!=null&&!Arrays.equals(bytesUnchecked(prev),bytesUnchecked(tag(r,"Before"))))throw new IllegalStateException("discontinuous journal "+p);}
        if(detach.size()!=cells.size()||place.size()!=cells.size())throw new IllegalStateException("partial inverse");
        j.put("InitialWorldImageCount",initial.size());
    }
    static byte[] bytesUnchecked(Map p){try{return bytes(p);}catch(Exception e){throw new RuntimeException(e);}}
    static final class Region {
        final TreeMap<Integer,TreeMap<Integer,TreeMap<Integer,String[]>>> rows=new TreeMap<>();
        final LinkedHashMap<String,Integer> palette=new LinkedHashMap<>();
        void add(int x,int y,int z,String a,String b){int ci=(x>>4&31)+(z>>4&31)*32,sy=y>>4,idx=(x&15)+(z&15)*16+(y&15)*256;
            var values=rows.computeIfAbsent(ci,k->new TreeMap<>()).computeIfAbsent(sy,k->new TreeMap<>());
            String[] previous=values.get(idx);
            if(previous!=null&&!previous[1].equals(a))throw new IllegalStateException("discontinuous edits "+x+","+y+","+z);
            values.put(idx,new String[]{previous==null?a:previous[0],b});
            for(String v:new String[]{a,b})palette.computeIfAbsent(v,k->palette.size());}
        void write(Path file)throws Exception{try(var o=zipOut(file)){o.writeInt(0x46423444);o.writeShort(palette.size());for(String s:palette.keySet())o.writeUTF(s);o.writeInt(rows.size());
            for(var c:rows.entrySet()){o.writeShort(c.getKey());o.writeShort(c.getValue().size());for(var s:c.getValue().entrySet()){o.writeShort(s.getKey());o.writeShort(s.getValue().size());for(var e:s.getValue().entrySet()){o.writeShort(e.getKey());o.writeShort(palette.get(e.getValue()[0]));o.writeShort(palette.get(e.getValue()[1]));}}}}}
    }
    public static void main(String[] args)throws Exception{
        Path source=Path.of(args[0]),plan=Path.of(args[1]),out=Path.of(args[2]),data=source.resolve(DATA);
        if(source.toAbsolutePath().normalize().startsWith(out.toAbsolutePath().normalize())||out.toAbsolutePath().normalize().startsWith(source.toAbsolutePath().normalize()))throw new IllegalArgumentException("output must be a separate overlay");
        var ledgerFile=Files.list(data).filter(f->f.getFileName().toString().startsWith("projectseele_city_rigid_control_r45_")).findFirst().orElseThrow();
        Map ledger=tag(load(ledgerFile),"data");if(!"IDLE".equals(ledger.get("Phase")))throw new IllegalStateException("unparked");
        Path topoFile=Files.list(data).filter(f->f.getFileName().toString().startsWith("projectseele_city_rigid_topology_r45_")).findFirst().orElseThrow();
        Map topoRoot=load(topoFile),topo=tag(topoRoot,"data");
        String[] trips={uuid((int[])ledger.get("Journey")),uuid((int[])tag(ledger,"PreviousCommittedLedgerR48").get("Journey"))};
        Path generation=Path.of("city_rigid_generation_r45/cargo"),journals=Path.of("city_rigid_journal_r45");Map<String,Region> regions=new TreeMap<>();int depth=((Number)ledger.get("Depth")).intValue(),count=0;
        // Clear checked static shaft material before writing any lowered crown occupying the same cells.
        Path fixed=plan.resolve("streetscape.tsv.gz");if(Files.isRegularFile(fixed))for(Edit e:edits(fixed)){regions.computeIfAbsent("r."+(e.x>>9)+"."+(e.z>>9),k->new Region()).add(e.x,e.y,e.z,e.before,e.after);count++;}
        boolean crowns=Files.isRegularFile(plan.resolve("crown-heights.tsv"));
        var files=Files.list(plan).filter(f->f.getFileName().toString().matches("[0-9]+\\.tsv\\.gz")).sorted().toList();
        for(Path file:files){int i=Integer.parseInt(file.getFileName().toString().split("\\.")[0]);Map tw=(Map)((Seq)topo.get("Towers")).get(i);long cp=(long)tw.get("Centre");int cx=x(cp),cy=y(cp),cz=z(cp),base=depth==0?cy:(int)tw.get("RetractedBaseY");
            var updates=edits(file);String n=i+".dat";Path recipe=generation.resolve(n);var root=load(data.resolve(recipe));var building=(Map)((Seq)tag(root,"data").get("Buildings")).get(0);var cargo=indexed((Seq)building.get("Cargo"));Map foot=tag(tw,"Footprint");
            if(crowns){
                int oldHeight=i==37?104:120,newHeight=i==37?130:153;
                if((i!=37&&i!=43)||cx!=(i==37?70:110)||cz!=100||cy!=80||!tw.get("Height").equals(oldHeight)||!building.get("Height").equals(oldHeight))throw new IllegalStateException("wrong crown preimage");
                tw.put("Height",newHeight);tw.put("R66CrownHeight",newHeight);building.put("Height",newHeight);
            }
            for(Edit e:updates){if(e.x<(int)foot.get("MinX")||e.x>(int)foot.get("MaxX")||e.z<(int)foot.get("MinZ")||e.z>(int)foot.get("MaxZ")||e.y<9||e.y>(int)tw.get("Height")+3)throw new IllegalStateException("outside owner");
                long p=packed(e.x,e.y,e.z);verify(cargo.get(p),e.before,"recipe "+i);replace(cargo,p,e.after.equals(AIR)?null:cell(p,e.after));int xx=cx+e.x,yy=base+e.y,zz=cz+e.z;
                regions.computeIfAbsent("r."+(xx>>9)+"."+(zz>>9),k->new Region()).add(xx,yy,zz,e.before,e.after);count++;}
            writeRows(building,"Cargo",cargo);save(out.resolve(DATA).resolve(recipe),root);
            for(String trip:trips){Path rel=journals.resolve(trip).resolve(n);var j=load(data.resolve(rel));if(!j.get("Index").equals(i)||!j.get("WorldUUID").equals(ledger.get("WorldUUID")))throw new IllegalStateException("foreign ledger");if(crowns){if(!j.get("Height").equals(i==37?104:120))throw new IllegalStateException("wrong historical crown");j.put("Height",tw.get("Height"));}journal(j,updates,cx,cz);save(out.resolve(DATA).resolve(rel),j);}
            System.out.println("owner "+i+" "+updates.size()+" cells, "+cargo.size()+" final");}
        if(crowns){if(files.size()!=2)throw new IllegalStateException("partial pair");save(out.resolve(DATA).resolve(topoFile.getFileName()),topoRoot);}
        Path delta=out.resolve("deltas");Files.createDirectories(delta);for(var r:regions.entrySet())r.getValue().write(delta.resolve(r.getKey()+".delta.gz"));
        System.out.println("depth="+depth+" edited="+count+" regions="+regions.size());
    }
}

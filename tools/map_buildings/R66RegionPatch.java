// Checked, copy-on-write Anvil patch application and independent chunk readback.
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.zip.*;
import java.security.*;
import static java.nio.charset.StandardCharsets.UTF_8;

@SuppressWarnings({"unchecked","rawtypes"})
public class R66RegionPatch {
 static class Seq extends ArrayList<Object> { int type; Seq(int type){this.type=type;} }
 static Object read(DataInputStream d,int t)throws Exception{
  switch(t){case 1:return d.readByte();case 2:return d.readShort();case 3:return d.readInt();case 4:return d.readLong();case 5:return d.readFloat();case 6:return d.readDouble();
  case 7:return d.readNBytes(d.readInt());case 8:return d.readUTF();case 9:{int type=d.readByte(),n=d.readInt();Seq s=new Seq(type);for(int i=0;i<n;i++)s.add(read(d,type));return s;}
  case 10:{Map<String,Object> m=new LinkedHashMap<>();int id;while((id=d.readUnsignedByte())!=0)m.put(d.readUTF(),read(d,id));return m;}
  case 11:{int[] a=new int[d.readInt()];for(int i=0;i<a.length;i++)a[i]=d.readInt();return a;}
  case 12:{long[] a=new long[d.readInt()];for(int i=0;i<a.length;i++)a[i]=d.readLong();return a;}
  default:throw new IOException("tag "+t);}
 }
 static int id(Object a)throws Exception {if(a instanceof Byte)return 1;if(a instanceof Short)return 2;if(a instanceof Integer)return 3;if(a instanceof Long)return 4;if(a instanceof Float)return 5;if(a instanceof Double)return 6;if(a instanceof byte[])return 7;if(a instanceof String)return 8;if(a instanceof Seq)return 9;if(a instanceof Map)return 10;if(a instanceof int[])return 11;if(a instanceof long[])return 12;throw new IOException("unknown NBT "+a);}
 static void write(DataOutputStream d,Object a)throws Exception{
  switch(id(a)){
  case 1->d.writeByte((byte)a);case 2->d.writeShort((short)a);case 3->d.writeInt((int)a);case 4->d.writeLong((long)a);case 5->d.writeFloat((float)a);case 6->d.writeDouble((double)a);
  case 7->{byte[] b=(byte[])a;d.writeInt(b.length);d.write(b);}case 8->d.writeUTF((String)a);
  case 9->{Seq s=(Seq)a;d.writeByte(s.type);d.writeInt(s.size());for(Object e:s)write(d,e);}
  case 10->{for(var e:((Map<String,Object>)a).entrySet()){d.writeByte(id(e.getValue()));d.writeUTF(e.getKey());write(d,e.getValue());}d.writeByte(0);}
  case 11->{int[] b=(int[])a;d.writeInt(b.length);for(int i:b)d.writeInt(i);}
  case 12->{long[] b=(long[])a;d.writeInt(b.length);for(long i:b)d.writeLong(i);}
  }
 }
 static Map<String,Object> root(byte[] raw)throws Exception{
  DataInputStream d=new DataInputStream(new ByteArrayInputStream(raw));if(d.readByte()!=10||!d.readUTF().isEmpty())throw new IOException("root");return (Map)read(d,10);}
 static byte[] bytes(Object root)throws Exception{var b=new ByteArrayOutputStream();var d=new DataOutputStream(b);d.writeByte(10);d.writeUTF("");write(d,root);return b.toByteArray();}
 static byte[] raw(RandomAccessFile r,int index)throws Exception{r.seek(index*4L);int loc=r.readInt();if(loc==0)throw new IOException("missing chunk "+index);
    r.seek((loc>>>8)*4096L);int n=r.readInt();int kind=r.readByte();if(kind!=2)throw new IOException("compression "+kind);byte[] a=new byte[n-1];r.readFully(a);try(var in=new InflaterInputStream(new ByteArrayInputStream(a))){return in.readAllBytes();}}
 static void putRaw(RandomAccessFile out,int index,byte[] raw)throws Exception{
  var b=new ByteArrayOutputStream();try(var zip=new DeflaterOutputStream(b)){zip.write(raw);}byte[] payload=b.toByteArray();int n=(payload.length+5+4095)/4096;if(n>=256)throw new IOException("overlarge chunk");
  out.seek(index*4L);int loc=out.readInt(),cnt=loc&255,pos=loc>>>8;if(cnt<n){pos=(int)((out.length()+4095)/4096);cnt=n;}out.seek(pos*4096L);out.writeInt(payload.length+1);out.writeByte(2);out.write(payload);out.write(new byte[n*4096-payload.length-5]);out.seek(index*4L);out.writeInt(pos<<8|n);}
 static String name(Object entry){Map<String,Object> a=(Map)entry;String n=(String)a.get("Name");Map<String,Object> p=(Map)a.get("Properties");
    if(p==null||p.isEmpty())return n;var q=new StringJoiner(",",n+"[","]");new TreeMap<>(p).forEach((k,v)->q.add(k+"="+v));return q.toString();}
 static Map<String,Object> state(String s){Map<String,Object> m=new LinkedHashMap<>();int p=s.indexOf('[');m.put("Name",p<0?s:s.substring(0,p));
    if(p>=0){Map<String,Object> props=new LinkedHashMap<>();for(String a:s.substring(p+1,s.length()-1).split(",")){String[] k=a.split("=");props.put(k[0],k[1]);}m.put("Properties",props);}return m;}
 static final String AIR="minecraft:air";
 static final String[] TARGET={"","minecraft:birch_log[axis=y]","minecraft:birch_leaves[distance=1,persistent=true,waterlogged=false]","minecraft:spruce_log[axis=y]","minecraft:spruce_leaves[distance=1,persistent=true,waterlogged=false]","minecraft:oak_log[axis=y]","minecraft:oak_leaves[distance=1,persistent=true,waterlogged=false]","minecraft:water[level=0]","minecraft:gravel","minecraft:clay","minecraft:sand"};
 static class Sec {
   int[] ids=new int[4096];ArrayList<String> pal=new ArrayList<>();Map<String,Object> bs;
   Sec(Map<String,Object> s){bs=(Map)s.get("block_states");if(bs==null)throw new IllegalStateException("missing block section");for(Object e:(Seq)bs.get("palette"))pal.add(name(e));long[] data=(long[])bs.get("data");int n=pal.size(),bits=Math.max(4,32-Integer.numberOfLeadingZeros(n-1)),per=64/bits;if(data!=null)for(int i=0;i<4096;i++)ids[i]=(int)(data[i/per]>>>((i%per)*bits))&((1<<bits)-1);}
   String get(int i){return pal.get(ids[i]);}
   void set(int i,String s){int ix=pal.indexOf(s);if(ix<0){ix=pal.size();pal.add(s);}ids[i]=ix;}
   void save(){Seq l=new Seq(10);for(String s:pal)l.add(state(s));bs.put("palette",l);if(pal.size()==1){bs.remove("data");return;}int bits=Math.max(4,32-Integer.numberOfLeadingZeros(pal.size()-1)),per=64/bits;long[] d=new long[(4095+per)/per];for(int i=0;i<4096;i++)d[i/per]|=(long)ids[i]<<((i%per)*bits);bs.put("data",d);}
 }
 static Map<Integer,Map<String,Object>> sections(Map<String,Object> r){Map<Integer,Map<String,Object>> m=new TreeMap<>();for(Object e:(Seq)r.get("sections")){Map<String,Object>s=(Map)e;m.put(((Number)s.get("Y")).intValue(),s);}return m;}
 static String plain(String s){int i=s.indexOf('[');return i<0?s:s.substring(0,i);}
 static void clearLight(Map<String,Object> r){r.keySet().removeIf(k->k.equals("BlockLight")||k.equals("SkyLight")||k.startsWith("starlight."));}
 static void normalize(Map<String,Object> root){clearLight(root);root.remove("Heightmaps");root.put("isLightOn",(byte)0);for(Object e:(Seq)root.get("sections"))clearLight((Map)e);}
 static DataInputStream zipIn(Path p)throws Exception{return new DataInputStream(new BufferedInputStream(new GZIPInputStream(Files.newInputStream(p)),1<<17));}
 static DataOutputStream zipOut(Path p)throws Exception{return new DataOutputStream(new BufferedOutputStream(new GZIPOutputStream(Files.newOutputStream(p)),1<<17));}
 static int cid(int x,int z){return (x>>4&31)+(z>>4&31)*32;}
 static void checkFull(Map<String,Object> r){if(!String.valueOf(r.get("Status")).endsWith("full"))throw new IllegalStateException("unfinished chunk");}
 static long[] stage(Path src,Path deltas,Path out,int rx,int rz)throws Exception{
   Path name=Path.of("r."+rx+"."+rz+".mca"),base=src.resolve(name),temp=out.resolve(name+".partial"),dest=out.resolve(name);
   Files.copy(base,temp,StandardCopyOption.REPLACE_EXISTING);long changes=0;int cnt;
   try(var in=zipIn(deltas.resolve("r."+rx+"."+rz+".delta.gz"));var original=new RandomAccessFile(base.toFile(),"r");var next=new RandomAccessFile(temp.toFile(),"rw")){
    if(in.readInt()!=0x46423444)throw new IOException("patch magic");int nc=in.readUnsignedShort();String[] pal=new String[nc];for(int i=0;i<nc;i++)pal[i]=in.readUTF();cnt=in.readInt();Set<Integer> touched=new HashSet<>();
    for(int j=0;j<cnt;j++){int ci=in.readUnsignedShort();if(!touched.add(ci))throw new IOException("duplicate chunk");var r=root(raw(original,ci));checkFull(r);var secs=sections(r);var expected=new TreeMap<Integer,String[]>();int ns=in.readUnsignedShort();
      Set<Integer> be=new HashSet<>();for(Object e:(Seq)r.getOrDefault("block_entities",new Seq(10))){Map ent=(Map)e;int x=(int)ent.get("x"),y=(int)ent.get("y"),z=(int)ent.get("z");be.add(y*256+(z&15)*16+(x&15));}
      for(int k=0;k<ns;k++){int sy=in.readShort(),nr=in.readUnsignedShort();if(expected.containsKey(sy))throw new IOException("duplicate section");Sec sec=new Sec(secs.get(sy));String[] section=new String[4096];for(int t=0;t<4096;t++)section[t]=sec.get(t);
       BitSet seen=new BitSet(4096);for(int n=0;n<nr;n++){int pos=in.readUnsignedShort();String before=pal[in.readUnsignedShort()],after=pal[in.readUnsignedShort()];if(seen.get(pos)||be.contains(sy*4096+pos)||!sec.get(pos).equals(before))throw new IOException("preimage mismatch/BE "+name+" chunk "+ci+" section "+sy+" pos "+pos+" expected "+before+" got "+sec.get(pos));seen.set(pos);sec.set(pos,after);section[pos]=after;changes++;}
       sec.save();expected.put(sy,section);
      }
      normalize(r);putRaw(next,ci,bytes(r));var reread=root(raw(next,ci));var actual=sections(reread);var initial=root(raw(original,ci));normalize(initial);var untouched=sections(initial);
      for(var e:expected.entrySet()){int sy=e.getKey();var sec=new Sec(actual.get(sy));for(int t=0;t<4096;t++)if(!sec.get(t).equals(e.getValue()[t]))throw new IOException("block readback");actual.get(sy).remove("block_states");untouched.get(sy).remove("block_states");}
      if(!Arrays.equals(bytes(initial),bytes(reread)))throw new IOException("unrelated chunk NBT changed "+name+" "+ci);
    }
    if(in.read()!=-1)throw new IOException("extra delta bytes");
    for(int i=0;i<1024;i++)if(!touched.contains(i)){original.seek(i*4L);int a=original.readInt();next.seek(i*4L);if(a!=next.readInt())throw new IOException("outside location");if(a!=0&&!Arrays.equals(raw(original,i),raw(next,i)))throw new IOException("outside chunk");}
   }Files.move(temp,dest,StandardCopyOption.REPLACE_EXISTING);return new long[]{changes,cnt,0};
 }

 public static void main(String[] args)throws Exception {
    Path regions=Path.of(args[0]).toAbsolutePath().normalize(), patches=Path.of(args[1]), out=Path.of(args[2]).toAbsolutePath().normalize();
    if(regions.equals(out))throw new IllegalArgumentException("Use a separate output region folder");
    Files.createDirectories(out);
    try(var files=Files.list(patches)){
       for(Path patch:files.sorted().toList()){
          String[] parts=patch.getFileName().toString().split("\\.");
          if(parts.length!=5 || !parts[3].equals("delta"))continue;
          int rx=Integer.parseInt(parts[1]),rz=Integer.parseInt(parts[2]);
          long[] result=stage(regions,patches,out,rx,rz);
          System.out.println(rx+","+rz+","+result[0]+","+result[1]);
       }
    }
 }
}

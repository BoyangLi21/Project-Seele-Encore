import java.io.*;import java.nio.file.*;import java.util.*;
@SuppressWarnings({"unchecked","rawtypes"})
public class SchoolDistrictLiftCheck extends Tokyo3CargoR66 {
 static Path stage,live,mod;
 static Map<Long,Sec> cache=new HashMap<>();
 static Map<Integer,Map<String,Object>> currentChunk;static int currentCX=Integer.MIN_VALUE,currentCZ;
 static String block(long p)throws Exception{
  int x=x(p),y=y(p),z=z(p),cx=x>>4,cz=z>>4;long ck=packed(cx,y>>4,cz);Sec sec=cache.get(ck);
  if(sec==null){
   if(cx!=currentCX||cz!=currentCZ){
    var rel=DATA.getParent().resolve("region").resolve("r."+(x>>9)+"."+(z>>9)+".mca");
    var file=Files.exists(stage.resolve(rel))?stage.resolve(rel):live.resolve(rel);
    try(var f=new RandomAccessFile(file.toFile(),"r")){currentChunk=sections(root(raw(f,cid(x,z))));currentCX=cx;currentCZ=cz;}
   }
   sec=new Sec(currentChunk.get(y>>4));cache.put(ck,sec);
  }
  return sec.get((x&15)+((z&15)<<4)+((y&15)<<8));
 }
 static Path datafile(Path rel){return Files.isRegularFile(mod.resolve(rel))?mod.resolve(rel):live.resolve(rel);}
 static int apply(int i,Map plan,Map<Long,String> overlay,boolean all)throws Exception{
  int cnt=0;
  for(int s=0;s<4;s++){
   for(Object o: (Seq)plan.get("Ops"+(all ? s : 3-s))){
    Map op=(Map)o;long p=(long)op.get("Pos");String before=name(tag(op,"Before").get("State")),after=name(tag(op,"After").get("State"));
    if(!all){String swap=before;before=after;after=swap;} String actual=overlay.get(p);if(actual==null)actual=block(p);
    if(!before.equals(actual))throw new IllegalStateException("owner="+i+" stage="+s+" p="+x(p)+","+y(p)+","+z(p)+" expected="+before+" actual="+actual);
    overlay.put(p,after);cnt++;
   }
  }
  return cnt;
 }
 public static void main(String[] args)throws Exception{
  stage=Path.of(args[0]);live=Path.of(args[1]);mod=Path.of(args[2]);List<Integer> failures=new ArrayList<>();
  Map ctrl=tag(load(Files.list(live.resolve(DATA)).filter(p->p.getFileName().toString().startsWith("projectseele_city_rigid_control_r45_")).findFirst().orElseThrow()),"data");
  String raise=uuid((int[])ctrl.get("Journey")),lower=uuid((int[])tag(ctrl,"PreviousCommittedLedgerR48").get("Journey"));Path j=DATA.resolve("city_rigid_journal_r45");
  var changed=Set.of(23,29,34,35,39,40);long ops=0,positions=0,fullCargo=0;int completed=0;
  for(int i:changed){
   var overlay=new HashMap<Long,String>();String file=i+".dat";
   try{
    var down=load(datafile(j.resolve(lower).resolve(file)));var up=load(datafile(j.resolve(raise).resolve(file)));
    Map body=(Map)((Seq)tag(load(datafile(DATA.resolve("city_rigid_generation_r45/cargo").resolve(file))),"data").get("Buildings")).get(0);
    if(!down.get("Height").equals(up.get("Height"))||!body.get("Height").equals(up.get("Height")))throw new IllegalStateException("Height disagreement");
    if(!Arrays.equals((int[])down.get("Owner"),(int[])up.get("Owner")))throw new IllegalStateException("Wrong owner");
    long n=apply(i,down,overlay,true);int cx=x((long)down.get("Centre")),cz=z((long)down.get("Centre")),lowerY=(int)down.get("TargetY");
    for(Object o:(Seq)body.get("Cargo")){
     Map cell=(Map)o;long rel=(long)cell.get("Pos"),pos=packed(cx+x(rel),lowerY+y(rel),cz+z(rel));String expected=name(cell.get("State"));
     if(!expected.equals(overlay.get(pos)))throw new IllegalStateException("recipe vs lower cargo at "+pos);
    }
    n+=apply(i,up,overlay,true);
    for(var e:overlay.entrySet())if(!e.getValue().equals(block(e.getKey())))throw new IllegalStateException("Return drift");
    ops+=n;positions+=overlay.size();fullCargo+=((Seq)body.get("Cargo")).size();completed++;
    System.out.println("tower "+i+" cargo="+((Seq)body.get("Cargo")).size()+" downward+upwardWrites="+n+" roundtripCells="+overlay.size());
   }catch(Exception exc){System.out.println("FAILED "+i+" "+exc.getMessage());failures.add(i);}
  }
  System.out.println("CITY ROUNDTRIP completed="+completed+" operations="+ops+" uniqueCells="+positions+" cargoBlocks="+fullCargo+" failedOwners="+failures);
  if(!failures.isEmpty())System.exit(1);
 }
}
package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;
/** Actual complete deck vertices against finite original floor triangles. */
public final class LegacyExactFloorClearanceR52 {
 private record Tri(Vec3 a,Vec3 b,Vec3 c,int index){}
 private static final Map<Long,List<Tri>> cells=new HashMap<>();
 private static long cell(int x,int z){return ((long)x<<32)^(z&0xffffffffL);}
 private static double floor(Vec3 p){double best=-1e99;for(var t:cells.getOrDefault(cell((int)Math.floor(p.x),(int)Math.floor(p.z)),List.of())){var a=t.a;var b=t.b;var c=t.c;double det=(b.z-c.z)*(a.x-c.x)+(c.x-b.x)*(a.z-c.z);if(Math.abs(det)<1e-12)continue;double u=((b.z-c.z)*(p.x-c.x)+(c.x-b.x)*(p.z-c.z))/det,v=((c.z-a.z)*(p.x-c.x)+(a.x-c.x)*(p.z-c.z))/det;if(u>=-1e-7&&v>=-1e-7&&u+v<=1+1e-7)best=Math.max(best,a.y*u+b.y*v+c.y*(1-u-v));}return best;}
 public static void main(String[] args)throws Exception{
  var d=NervRouteDirectoryR52.parse(JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject());var source=NervLegacyCarrierRideR52.fixedPartsR52().stream().filter(p->p.name().equals("legacy_contact_source")).findFirst().orElseThrow();var xyz=source.mesh().triangles();int selected=0;
  for(int n=0;n<xyz.length;n+=9){double x0=Math.min(xyz[n],Math.min(xyz[n+3],xyz[n+6])),x1=Math.max(xyz[n],Math.max(xyz[n+3],xyz[n+6])),y0=Math.min(xyz[n+1],Math.min(xyz[n+4],xyz[n+7])),y1=Math.max(xyz[n+1],Math.max(xyz[n+4],xyz[n+7])),z0=Math.min(xyz[n+2],Math.min(xyz[n+5],xyz[n+8])),z1=Math.max(xyz[n+2],Math.max(xyz[n+5],xyz[n+8]));if(x1-x0<4.99||z1-z0>1.001||y1-y0>.3)continue;var a=source.frame().transformPoint(new Vec3(xyz[n],xyz[n+1],xyz[n+2]));var b=source.frame().transformPoint(new Vec3(xyz[n+3],xyz[n+4],xyz[n+5]));var c=source.frame().transformPoint(new Vec3(xyz[n+6],xyz[n+7],xyz[n+8]));var t=new Tri(a,b,c,n/9);selected++;for(int x=(int)Math.floor(Math.min(a.x,Math.min(b.x,c.x))-1e-7);x<=Math.floor(Math.max(a.x,Math.max(b.x,c.x))+1e-7);x++)for(int z=(int)Math.floor(Math.min(a.z,Math.min(b.z,c.z))-1e-7);z<=Math.floor(Math.max(a.z,Math.max(b.z,c.z))+1e-7);z++)cells.computeIfAbsent(cell(x,z),q->new ArrayList<>()).add(t);}
  var unique=new LinkedHashSet<Vec3>();var deck=NervLegacyCarrierRideR52.actualHousingDeckR52().triangles();for(int n=0;n<deck.length;n+=3)unique.add(new Vec3(deck[n],deck[n+1],deck[n+2]));var rows=new ArrayList<Object>();
  for(int v=0;v<3;v++){var l=d.leg("unit"+v+"/original_incline");var binding=NervOriginalCarrierR52.nominalBinding(v);double maximum=-1e99;int worst=0;Vec3 local=null,world=null;for(int k=0;k<=960;k++){double t=k/960D,f=t*t*t*(10+t*(-15+6*t));var root=d.sample(l,f,binding).evaRoot();for(var q:unique){var p=root.transformPoint(q);double overlap=floor(p)-p.y;if(overlap>maximum){maximum=overlap;worst=k;local=q;world=p;}}}rows.add(Map.of("variant",v,"maximum_floor_over_complete_deck_m",maximum,"at_tick",worst/4D,"actual_local_vertex",local,"actual_world_vertex",world));System.out.println("v="+v+" floorOver="+maximum+" tick="+worst/4D+" vertex="+local);}
  Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("world_written",false,"source",NervLegacyCarrierRideR52.SOURCE_SHA,"deck",NervLegacyCarrierRideR52.DECK_SHA,"actual_floor_triangles",selected,"actual_deck_unique_vertices",unique.size(),"rows",rows)));
 }
}

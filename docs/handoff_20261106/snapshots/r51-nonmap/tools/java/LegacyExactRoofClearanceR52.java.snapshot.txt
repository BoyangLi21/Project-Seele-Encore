package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;
public final class LegacyExactRoofClearanceR52 {
 private static List<Vec3> clip(List<Vec3> p,double x,boolean lower){var out=new ArrayList<Vec3>();if(p.isEmpty())return out;var old=p.get(p.size()-1);boolean was=lower?old.x<=x:old.x>=x;for(var q:p){boolean now=lower?q.x<=x:q.x>=x;if(now!=was)out.add(old.add(q.subtract(old).scale((x-old.x)/(q.x-old.x))));if(now)out.add(q);old=q;was=now;}return out;}
 public static void main(String[] args)throws Exception{var d=NervRouteDirectoryR52.parse(JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject());var xyz=NervLegacyCarrierRideR52.actualHousingDeckR52().triangles();double[] front={-1e9,-1e9};for(int n=0;n<xyz.length;n+=9){if(Math.abs(xyz[n+1]+2.2)>1e-6||Math.abs(xyz[n+4]+2.2)>1e-6||Math.abs(xyz[n+7]+2.2)>1e-6)continue;for(int side=0;side<2;side++){double centre=side==0?-6:6;List<Vec3> p=new ArrayList<>();for(int k=0;k<9;k+=3)p.add(new Vec3(xyz[n+k],xyz[n+k+1],xyz[n+k+2]));p=clip(p,centre-.6,false);p=clip(p,centre+.6,true);for(var q:p)front[side]=Math.max(front[side],q.z);}}
 var rows=new ArrayList<Object>();for(int v=0;v<3;v++){var b=NervOriginalCarrierR52.nominalBinding(v);var l=d.leg("unit"+v+"/original_incline");double maximum=-1e9;int worst=0;String part="";for(int k=0;k<=960;k++){double t=k/960D,f=t*t*t*(10+t*(-15+6*t));var r=d.sample(l,f,b).evaRoot();for(int side=0;side<2;side++){var p=r.transformPoint(new Vec3(side==0?-6:6,-2.200000047683716,front[side]));var h=NervLegacyCarrierRideR52.actualHeadR52(p.x,p.z);if(h!=null&&h.part().equals("legacy_heads_only")){double penetration=h.point().y-p.y;if(penetration>maximum){maximum=penetration;worst=k;part=h.part();}}}}rows.add(Map.of("variant",v,"maximum_actual_top_over_deck_m",maximum,"at_tick",worst/4D,"head",part));System.out.println("v="+v+" exactOver="+maximum+" tick="+worst/4D);}
 Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("world_written",false,"source",NervLegacyCarrierRideR52.SOURCE_SHA,"deck",NervLegacyCarrierRideR52.DECK_SHA,"actual_bottom_strip_front_local_z",front,"rows",rows)));
 }
}

package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.*;
/** Read-only actual first deck/header triangle collision packet. */
public final class LegacyDeckIntersectionR52 {
 public static void main(String[] args)throws Exception{var d=NervRouteDirectoryR52.parse(JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject());int v=Integer.parseInt(args[1]),age=Integer.parseInt(args[2]);var root=d.sample(d.leg("unit"+v+"/original_incline"),NervMechanicalTravelR52.fraction(age,240),NervOriginalCarrierR52.nominalBinding(v)).evaRoot();var deck=NervLegacyCarrierRideR52.actualHousingDeckR52();var rail=NervLegacyCarrierRideR52.fixedPartsR52().stream().filter(p->p.name().equals(args[3])).findFirst().orElseThrow();var xyz=deck.triangles();var hits=new ArrayList<Object>();AABB bounds=null;
  for(int n=0;n<xyz.length;n+=9){var tri=Arrays.copyOfRange(xyz,n,n+9);var mesh=new NervRigidMeshSweepR52(tri);if(!mesh.envelope(root,root).intersects(rail.mesh().envelope(rail.frame(),rail.frame()))||!mesh.intersects(root,root,rail.mesh(),rail.frame(),rail.frame(),.003,Vec3.ZERO))continue;var world=new ArrayList<Double>();for(int i=0;i<9;i+=3){var p=root.transformPoint(new Vec3(tri[i],tri[i+1],tri[i+2]));world.add(p.x);world.add(p.y);world.add(p.z);bounds=bounds==null?new AABB(p,p):bounds.minmax(new AABB(p,p));}hits.add(Map.of("deck_triangle",n/9,"local",tri,"world",world));}
  Files.writeString(Path.of(args[4]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("world_written",false,"variant",v,"age",age,"root",root,"rail",rail.name(),"rail_frame",rail.frame(),"source_deck",NervLegacyCarrierRideR52.DECK_SHA,"source_head",NervLegacyCarrierRideR52.SOURCE_SHA,"hits",hits)));System.out.println("deck triangles="+hits.size()+" bounds="+bounds);
 }
}

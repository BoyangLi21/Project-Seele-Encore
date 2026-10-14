package com.projectseele.world;
import com.google.gson.*;import java.nio.file.*;import java.util.*;import net.minecraft.world.phys.*;
/** Distinguish actual coplanar bearing from an earlier 0.2mm projected-near label. */
public final class DescribeSixOriginalNearFacesR53
{
 public static void main(String[] args)throws Exception
 {
  var input=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var parts=NervLegacyCarrierRideR52.fixedPartsR52();var out=new ArrayList<Object>();
  for(var raw:input.getAsJsonArray("cells")){var c=raw.getAsJsonObject();if(c.getAsJsonArray("actual_finite_native_face_contacts").isEmpty())continue;var rows=new ArrayList<Object>();var pos=c.getAsJsonArray("position");
   for(var v:c.getAsJsonArray("actual_finite_native_face_contacts")){var contact=v.getAsJsonObject();var p=parts.stream().filter(q->q.name().equals(contact.get("fixed_part").getAsString())).findFirst().orElseThrow();int i=contact.get("source_triangle").getAsInt()*9,axis=contact.get("native_shape_face_axis").getAsInt(),side=contact.get("native_shape_face_side").getAsInt();double plane=pos.get(axis).getAsDouble()+side;var vertices=new ArrayList<double[]>();var points=new Vec3[3];var gaps=new ArrayList<Double>();var mesh=p.mesh().triangles();for(int k=0;k<3;k++){points[k]=p.frame().transformPoint(new Vec3(mesh[i+3*k],mesh[i+3*k+1],mesh[i+3*k+2]));vertices.add(new double[]{points[k].x,points[k].y,points[k].z});gaps.add((axis==0?points[k].x:axis==1?points[k].y:points[k].z)-plane);}var n=points[1].subtract(points[0]).cross(points[2].subtract(points[0])).normalize();double mn=Collections.min(gaps),mx=Collections.max(gaps);rows.add(Map.of("part",p.name(),"source_triangle",i/9,"actual_world_vertices",vertices,"actual_normal",new double[]{n.x,n.y,n.z},"native_face_plane",plane,"signed_vertex_plane_gaps_m",gaps,"finite_coplanar_face",Math.max(Math.abs(mn),Math.abs(mx))<=2e-7,"whole_triangle_strictly_above_face",mn>2e-7,"whole_triangle_strictly_below_face",mx< -2e-7));}
   out.add(Map.of("position",pos,"actual_source_faces",rows,"independent_steel_inside_native_cube",c.get("actual_fixed_steel_interior_members")));
  }
  Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("world_written",false,"game_started",false,"cells",out,"scope","Exact production source triangle vertices and signed distance to actual native cube face. A projected near face is not asserted to be physical support; no geometry edited.")));
 }
}

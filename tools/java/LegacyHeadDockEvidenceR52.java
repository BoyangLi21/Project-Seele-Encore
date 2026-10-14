package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;

/** Exact finite legacy running-head / original deck source measurement.
 * Does not commission tracks, raise a body, write a world or hide a source. */
public final class LegacyHeadDockEvidenceR52 {
    private static double lowest(double[] xyz,double x,double z){double low=Double.POSITIVE_INFINITY;for(int n=0;n<xyz.length;n+=9){double ax=xyz[n],az=xyz[n+2],bx=xyz[n+3],bz=xyz[n+5],cx=xyz[n+6],cz=xyz[n+8],det=(bz-cz)*(ax-cx)+(cx-bx)*(az-cz);if(Math.abs(det)<1e-12)continue;double a=((bz-cz)*(x-cx)+(cx-bx)*(z-cz))/det,b=((cz-az)*(x-cx)+(ax-cx)*(z-cz))/det,c=1-a-b;if(a>=-1e-7&&b>=-1e-7&&c>=-1e-7)low=Math.min(low,a*xyz[n+1]+b*xyz[n+4]+c*xyz[n+7]);}return low;}
    private static Vec3 point(JsonArray a){return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    public static void main(String[] args)throws Exception {
        var d=NervRouteDirectoryR52.parse(JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject());FullAssemblyGeometryR52.installClasspath();NervMappedPlugMechanicsR52.install();
        var fixed=JsonParser.parseString(new String(EvaOriginalMeshGeometryR52.classpathBytes("facility/r52_fixed_guides.json"))).getAsJsonObject().getAsJsonObject("original_incline");var frame=RigidTransform.of(point(fixed.getAsJsonArray("origin")),new Quaternionf().rotationY((float)Math.toRadians(fixed.get("yaw_degrees").getAsFloat())));
        var source=JsonParser.parseString(new String(EvaOriginalMeshGeometryR52.classpathBytes("mesh/tv_facilities_r16.json"))).getAsJsonObject().getAsJsonObject("parts").getAsJsonArray("r20_transfer_guide");var rows=new ArrayList<Map<String,Object>>();
        for(int v=0;v<3;v++){
            var binding=NervOriginalCarrierR52.nominalBinding(v);var leg=d.leg("unit"+v+"/original_incline");var deck=NervMappedPlugMechanicsR52.selectedMachinery().carrierParts(v,1,false,0,64).get("deck");var deckBounds=new NervRigidMeshSweepR52(deck).bounds();double lane=(v-1)*42;var heads=new ArrayList<Vec3>();int triangles=0;
            for(int n=0;n<source.size();n+=18){double minX=Double.POSITIVE_INFINITY,maxX=Double.NEGATIVE_INFINITY,minY=minX,maxY=maxX;var p=new Vec3[3];for(int k=0;k<3;k++){int i=n+k*6;p[k]=new Vec3(source.get(i).getAsDouble(),source.get(i+1).getAsDouble(),source.get(i+2).getAsDouble());minX=Math.min(minX,p[k].x);maxX=Math.max(maxX,p[k].x);minY=Math.min(minY,p[k].y);maxY=Math.max(maxY,p[k].y);}if(Math.abs(maxX-minX-1.2)>.00001||maxY-minY>.3||Math.min(Math.abs((minX+maxX)/2-lane-6),Math.abs((minX+maxX)/2-lane+6))>.00001)continue;triangles++;for(var p0:p)heads.add(frame.transformPoint(p0));}
            double required=0;Map<String,Object> worst=Map.of();int contacts=0;for(int k=0;k<=240;k++){double fraction=NervMechanicalTravelR52.fraction(k,240);var root=d.sample(leg,fraction,binding).evaRoot();var inv=root.inverse();for(var world:heads){var local=inv.transformPoint(world);if(local.x<deckBounds.minX||local.x>deckBounds.maxX||local.z<deckBounds.minZ||local.z>deckBounds.maxZ)continue;double low=lowest(deck,local.x,local.z);if(!Double.isFinite(low))continue;contacts++;double interference=local.y-low;if(interference>required){required=interference;worst=Map.of("tick",k,"fraction",fraction,"actual_head_world",new double[]{world.x,world.y,world.z},"actual_head_deck_local",new double[]{local.x,local.y,local.z},"actual_deck_low_face_y",low);}}}
            var levelContacts=new ArrayList<Map<String,Object>>();for(double x:new double[]{-6,6})for(double z:new double[]{-10,10}){double low=lowest(deck,x,z);levelContacts.add(Map.of("x",x,"z",z,"actual_original_deck_bottom",low,"selected_level_head_top",-2.200000047683716,"gap_m",low+2.200000047683716));}
            var row=new LinkedHashMap<String,Object>();row.put("variant",v);row.put("legacy_finite_head_triangles",triangles);row.put("finite_head_vertices_under_actual_deck",contacts);row.put("minimum_downward_head_source_correction_m",required);row.put("worst_actual_contact",worst);row.put("level_four_finite_strip_contacts",levelContacts);rows.add(row);System.out.println("variant="+v+" finite="+contacts+" correction="+required);
        }
        var report=Map.of("world_written",false,"native_admission",false,"root_nodes_changed",false,"height_scope","Maximum real head/deck lower-face interference across the full 29m deck and all 241 actual Root clock samples; does not claim a centre-height offset creates fore/aft load contact", "rows",rows);Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(report));
    }
}

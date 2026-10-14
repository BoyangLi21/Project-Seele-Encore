package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.*;

/** Actual native shape versus all fixed source steel, with spatially indexed finite face contacts. */
public final class ClassifyCurrentPrelaunchSteelCellsR53
{
    record Triangle(String part,String role,int source,Vec3[] points,AABB box){}
    static AABB box(JsonArray a){return new AABB(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble(),a.get(3).getAsDouble(),a.get(4).getAsDouble(),a.get(5).getAsDouble());}
    static double value(Vec3 p,int a){return a==0?p.x:a==1?p.y:p.z;}
    static double lo(AABB b,int a){return a==0?b.minX:a==1?b.minY:b.minZ;}
    static double hi(AABB b,int a){return a==0?b.maxX:a==1?b.maxY:b.maxZ;}
    static List<double[]> clip(List<double[]> p,int axis,double edge,boolean lower){var out=new ArrayList<double[]>();if(p.isEmpty())return out;var a=p.get(p.size()-1);double da=a[axis]-edge;boolean ia=lower?da>=0:da<=0;for(var b:p){double db=b[axis]-edge;boolean ib=lower?db>=0:db<=0;if(ia!=ib){double t=da/(da-db);out.add(new double[]{a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t});}if(ib)out.add(b);a=b;da=db;ia=ib;}return out;}
    static double area(List<double[]> p,AABB box,int u,int v){p=clip(clip(p,0,lo(box,u),true),0,hi(box,u),false);p=clip(clip(p,1,lo(box,v),true),1,hi(box,v),false);double sum=0;for(int i=0;i<p.size();i++){var a=p.get(i);var b=p.get((i+1)%p.size());sum+=a[0]*b[1]-a[1]*b[0];}return Math.abs(sum)*.5;}
    public static void main(String[] args)throws Exception
    {
        var input=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();if(!input.getAsJsonArray("unknown_shapes").isEmpty())throw new AssertionError("Unknown actual shape cannot be classified clear");var steel=NervLegacyCarrierRideR52.fixedPartsR52();var index=new NervStaticSpatialIndexR52<>(steel,p->p.mesh().envelope(p.frame(),p.frame()).inflate(.0002));var triangles=new ArrayList<Triangle>();
        for(var p:steel){var a=p.mesh().triangles();for(int i=0;i<a.length;i+=9){var tri=new Vec3[3];AABB bounds=null;for(int k=0;k<3;k++){tri[k]=p.frame().transformPoint(new Vec3(a[i+k*3],a[i+k*3+1],a[i+k*3+2]));bounds=bounds==null?new AABB(tri[k],tri[k]):bounds.minmax(new AABB(tri[k],tri[k]));}triangles.add(new Triangle(p.name(),p.role(),i/9,tri,bounds.inflate(.0002)));}}
        var triIndex=new NervStaticSpatialIndexR52<>(triangles,Triangle::box);var rows=new ArrayList<Object>();long tests=0;int count=0;
        for(var raw:input.getAsJsonArray("cells"))
        {
            var c=raw.getAsJsonObject();var interior=new TreeSet<String>();var touching=new TreeSet<String>();var contacts=new ArrayList<Object>();var boxes=new ArrayList<AABB>();for(var a:c.getAsJsonArray("native_boxes"))boxes.add(box(a.getAsJsonArray()));
            for(var b:boxes)
            {
                for(var p:index.query(b)){tests++;if(p.mesh().intersects(p.frame(),p.frame(),b.deflate(2e-7),.003))interior.add(p.name());if(p.mesh().intersects(p.frame(),p.frame(),b.inflate(.0002),.003))touching.add(p.name());}
                for(var t:triIndex.query(b.inflate(.0002)))for(int axis=0;axis<3;axis++)for(int side=0;side<2;side++)
                {
                    double plane=side==0?lo(b,axis):hi(b,axis),gap=0;for(var p:t.points())gap=Math.max(gap,Math.abs(value(p,axis)-plane));if(gap>.0002)continue;int u=(axis+1)%3,v=(axis+2)%3;var poly=new ArrayList<double[]>();for(var p:t.points())poly.add(new double[]{value(p,u),value(p,v)});double area=area(poly,b,u,v);if(area<=1e-12)continue;contacts.add(Map.of("fixed_part",t.part(),"fixed_role",t.role(),"source_triangle",t.source(),"native_shape_face_axis",axis,"native_shape_face_side",side,"finite_projected_area_m2",area,"maximum_plane_gap_m",gap,"exact_coplanar_roundoff_only",gap<=2e-7));
                }
            }
            var row=c.deepCopy();row.add("actual_fixed_steel_interior_members",new Gson().toJsonTree(interior));row.add("actual_fixed_steel_contact_or_near_members",new Gson().toJsonTree(touching));row.add("actual_finite_native_face_contacts",new Gson().toJsonTree(contacts));var p=c.getAsJsonArray("position");var wall=new ArrayList<Object>();for(var f:NervLegacyServiceBypassR52.wallFaces())if(f.block().getX()==p.get(0).getAsInt()&&f.block().getY()==p.get(1).getAsInt()&&f.block().getZ()==p.get(2).getAsInt())wall.add(f);row.add("explicit_service_wall_bearings",new Gson().toJsonTree(wall));rows.add(row);
            if(++count%1000==0)System.out.println("Actual fixed/native cells="+count+" tests="+tests);
        }
        var result=new LinkedHashMap<String,Object>();result.put("world_written",false);result.put("game_started",false);result.put("fixed_members",steel.size());result.put("actual_fixed_triangles",triangles.size());result.put("narrow_phase_mesh_tests",tests);result.put("source_region_sha256",input.get("source_region_sha256"));result.put("typed_interface_sha256",input.get("typed_interface_sha256"));result.put("original_source",NervLegacyCarrierRideR52.SOURCE_SHA);result.put("deep_frame_source",NervLegacyDeepFrameR53.SOURCE_SHA);result.put("cells",rows);result.put("scope","Actual current re-read native shapes against every original fixed steel member and all explicit service-wall bearings. Cube/shape interiors, <=.0002m near-contact, and finite native-face triangle projected area are distinct; .0002 only labels an unresolved near-support and is never a collision exemption. No excavation is authorized by this classification.");Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(result));
    }
}

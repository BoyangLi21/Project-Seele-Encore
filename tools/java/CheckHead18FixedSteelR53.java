package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.*;

/** Every actual current fixed mesh and finite coplanar cube-face contact at the eighteen proposed cells. */
public final class CheckHead18FixedSteelR53
{
    static List<double[]> clip(List<double[]> p,int axis,double edge,boolean lower){var out=new ArrayList<double[]>();if(p.isEmpty())return out;var a=p.get(p.size()-1);double da=a[axis]-edge;boolean ia=lower?da>=0:da<=0;for(var b:p){double db=b[axis]-edge;boolean ib=lower?db>=0:db<=0;if(ia!=ib){double t=da/(da-db);out.add(new double[]{a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t});}if(ib)out.add(b);a=b;da=db;ia=ib;}return out;}
    static double area(List<double[]> p,double u,double v){for(int axis=0;axis<2;axis++){double lower=axis==0?u:v;p=clip(clip(p,axis,lower,true),axis,lower+1,false);}double sum=0;for(int i=0;i<p.size();i++){var a=p.get(i);var b=p.get((i+1)%p.size());sum+=a[0]*b[1]-a[1]*b[0];}return Math.abs(sum)*.5;}
    static double value(Vec3 p,int a){return a==0?p.x:a==1?p.y:p.z;}
    public static void main(String[] args)throws Exception
    {
        var doc=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var cells=doc.getAsJsonArray("actual_cells");if(cells==null||cells.size()!=18)throw new AssertionError("Root exact eighteen cells required");var steel=NervLegacyCarrierRideR52.fixedPartsR52();var rows=new ArrayList<Object>();long tests=0;
        for(var raw:cells){var c=raw.getAsJsonObject();var p=c.getAsJsonArray("position");int x=p.get(0).getAsInt(),y=p.get(1).getAsInt(),z=p.get(2).getAsInt();var cube=new AABB(x,y,z,x+1,y+1,z+1);var interior=new ArrayList<String>();var boundary=new ArrayList<String>();var faces=new ArrayList<Object>();
            for(var f:steel){if(!f.mesh().envelope(f.frame(),f.frame()).inflate(2e-7).intersects(cube))continue;tests++;if(f.mesh().intersects(f.frame(),f.frame(),cube.deflate(2e-7),.003))interior.add(f.name());if(f.mesh().intersects(f.frame(),f.frame(),cube.inflate(2e-7),.003))boundary.add(f.name());var a=f.mesh().triangles();
                for(int i=0;i<a.length;i+=9){Vec3[] tri=new Vec3[3];for(int k=0;k<3;k++)tri[k]=f.frame().transformPoint(new Vec3(a[i+k*3],a[i+k*3+1],a[i+k*3+2]));for(int axis=0;axis<3;axis++)for(int side=0;side<2;side++){double plane=(axis==0?x:axis==1?y:z)+side;boolean on=true;for(var q:tri)if(Math.abs(value(q,axis)-plane)>2e-7)on=false;if(!on)continue;int u=(axis+1)%3,v=(axis+2)%3;var poly=new ArrayList<double[]>();for(var q:tri)poly.add(new double[]{value(q,u),value(q,v)});double area=area(poly,u==0?x:u==1?y:z,v==0?x:v==1?y:z);if(area>1e-12)faces.add(Map.of("fixed_part",f.name(),"role",f.role(),"source_triangle",i/9,"cube_face_axis",axis,"cube_face_side",side,"actual_projected_contact_area_m2",area));}}
            }
            rows.add(Map.of("position",new int[]{x,y,z},"before_state",c.get("state").getAsString(),"actual_fixed_mesh_interior_hits",interior,"actual_fixed_boundary_or_interior_hits",boundary,"finite_any_face_contacts",faces));
        }
        Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("world_written",false,"game_started",false,"actual_fixed_members",steel.size(),"narrow_phase_mesh_tests",tests,"original_source",NervLegacyCarrierRideR52.SOURCE_SHA,"deep_frame_source",NervLegacyDeepFrameR53.SOURCE_SHA,"cells",rows,"scope","Every actual fixed mesh from current source including service bypass and compact level overlay. Strict cube interior, conservative boundary contact, and finite coplanar actual triangle intersection against all six cube faces are separate. No new bearing exemptions or World mutation.")));System.out.println("Actual fixed18 cells="+rows.size()+" members="+steel.size()+" tests="+tests);
    }
}

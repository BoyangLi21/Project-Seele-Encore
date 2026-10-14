package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.SiloHatchMechanism;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;

/** Current factory vertices, exact monotone translation occupancy; no game/world. */
public final class MeasureCurrentLowerPitsR53
{
    private record Body(String name,String kind,String phase,NervRigidMeshSweepR52 mesh,RigidTransform from,RigidTransform to){}
    private static final double FOOT_FRAME_Y=-1062.96,HATCH_FRAME_Y=-1062.99,Z=328.5;
    private static final int MIN_Y=-1074,MAX_Y=-1062;
    private static final Gson GSON=new GsonBuilder().setPrettyPrinting().create();
    private static RigidTransform root(double x,double y,int yaw){return RigidTransform.of(new Vec3(x,y,Z),yaw==180?new Quaternionf(0,1,0,0):new Quaternionf());}
    private static double[] array(AABB b){return new double[]{b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ};}
    private static double[] array(Vec3 p){return new double[]{p.x,p.y,p.z};}
    private static Map<String,NervLowerFrameR52.Piece> lower(double p)throws Exception
    {var result=new LinkedHashMap<String,NervLowerFrameR52.Piece>();for(var piece:NervLowerFrameR52.pieces(p)){if(result.put(piece.name(),piece)!=null)throw new AssertionError("Duplicate source member");}return result;}
    private static List<Body> lowerBodies()throws Exception
    {
        var a=lower(0);var b=lower(.3);var c=lower(.45);var d=lower(.85);var e=lower(1);var frame=root(.5,FOOT_FRAME_Y,180);var out=new ArrayList<Body>();
        for(var p:a.values())
        {
            if(p.kind().equals("rope"))continue;
            if(p.kind().equals("fixed")){out.add(new Body(p.name(),p.kind(),"fixed",p.mesh(),frame.compose(p.local()),frame.compose(p.local())));continue;}
            var mid=b.get(p.name());var start=c.get(p.name());var end=d.get(p.name());
            if(mid.local().translation().distanceToSqr(start.local().translation())>1e-20||end.local().translation().distanceToSqr(e.get(p.name()).local().translation())>1e-20)throw new AssertionError("New current source motion needs review: "+p.name());
            if(p.local().translation().x!=mid.local().translation().x||p.local().translation().z!=mid.local().translation().z||Math.abs(p.local().translation().y-mid.local().translation().y-6.19)>1e-10)throw new AssertionError("Actual first phase is not pure6.19m vertical");
            if(start.local().translation().y!=end.local().translation().y||start.local().translation().z!=end.local().translation().z)throw new AssertionError("Actual second phase is not pureX");
            out.add(new Body(p.name(),p.kind(),"vertical_p0_to_p0.3",p.mesh(),frame.compose(p.local()),frame.compose(mid.local())));
            out.add(new Body(p.name(),p.kind(),"horizontal_p0.45_to_p0.85",p.mesh(),frame.compose(start.local()),frame.compose(end.local())));
        }
        for(var table:List.of(b,c,d))for(var p:table.values())if(p.kind().equals("rope"))
        {
            String axis=p.declaration().get("axis").getAsString();
            if(axis.equals("vertical")&&table==b||axis.equals("horizontal")&&table==c||axis.equals("return")&&table==d)
                out.add(new Body(p.name(),p.kind(),"exact_max_extent_"+axis,p.mesh(),frame.compose(p.local()),frame.compose(p.local())));
        }
        if(out.size()!=97||out.stream().map(Body::name).distinct().count()!=67)throw new AssertionError("Current67 source members/97 exact intervals required");
        return out;
    }
    private static List<Body> hatchBodies(NervSiloHatchGeometryR52 geometry,int yaw)
    {
        var a=geometry.pieces(0);var b=geometry.pieces(.3F);var c=geometry.pieces(1);var frame=root(.5,HATCH_FRAME_Y,yaw);var out=new ArrayList<Body>();
        for(int i=0;i<a.size();i++)
        {
            var p=a.get(i);String name=p.part().name()+"/factory_index"+i;var mesh=new NervRigidMeshSweepR52(p.part().xyz());
            if(!p.moving()){out.add(new Body(name,"fixed","fixed",mesh,frame.compose(p.local()),frame.compose(p.local())));continue;}
            if(p.local().translation().x!=b.get(i).local().translation().x||b.get(i).local().translation().y!=c.get(i).local().translation().y)throw new AssertionError("Current hatch stages are not pure axes");
            out.add(new Body(name,"moving","tier_p0_to_p0.3",mesh,frame.compose(p.local()),frame.compose(b.get(i).local())));
            out.add(new Body(name,"moving","stack_p0.3_to_p1",mesh,frame.compose(b.get(i).local()),frame.compose(c.get(i).local())));
        }
        return out;
    }
    private static List<Map<String,Object>> occupied(List<Body> bodies)
    {
        var rows=new TreeMap<String,Map<String,Object>>();long tests=0;
        for(var body:bodies)
        {
            var b=body.mesh().envelope(body.from(),body.to());
            for(int y=Math.max(MIN_Y,(int)Math.floor(b.minY-2e-7));y<=Math.min(MAX_Y,(int)Math.floor(b.maxY+2e-7));y++)
                for(int z=(int)Math.floor(b.minZ-2e-7);z<=Math.floor(b.maxZ+2e-7);z++)for(int x=(int)Math.floor(b.minX-2e-7);x<=Math.floor(b.maxX+2e-7);x++)
                {
                    var box=new AABB(x,y,z,x+1,y+1,z+1);tests++;
                    if(!body.mesh().intersects(body.from(),body.to(),box,.003))continue;
                    boolean penetration=body.mesh().intersects(body.from(),body.to(),box.deflate(2e-7),.003);
                    String key=x+","+y+","+z;var row=rows.get(key);
                    if(row==null){row=new LinkedHashMap<String,Object>();row.put("canonical_cell",new int[]{x,y,z});row.put("hits",new ArrayList<Map<String,Object>>());rows.put(key,row);}
                    @SuppressWarnings("unchecked")var hits=(List<Map<String,Object>>)row.get("hits");
                    hits.add(Map.of("member",body.name(),"kind",body.kind(),"phase",body.phase(),"penetrates_cell_deflated_2e_7",penetration));
                }
        }
        System.out.println("cube occupancy parts="+bodies.size()+" tests="+tests+" hit cells="+rows.size());return List.copyOf(rows.values());
    }
    private static List<Map<String,Object>> hatchPeers(List<Body> lower,List<Body> hatch)
    {
        var rows=new ArrayList<Map<String,Object>>();
        // Only fixed lower members are present throughout every hatch phase.
        // Tube motion and hatch motion belong to different operating stages.
        for(var l:lower)if(l.kind().equals("fixed"))for(var h:hatch)
        {
            if(!l.mesh().envelope(l.from(),l.to()).intersects(h.mesh().envelope(h.from(),h.to())))continue;
            if(l.mesh().intersects(l.from(),l.to(),h.mesh(),h.from(),h.to(),.003,Vec3.ZERO))rows.add(Map.of("lower_member",l.name(),"hatch_member",h.name(),"hatch_phase",h.phase(),"classification","actual triangle intersection; Root must classify declared fixed attachment vs forbidden moving leaf"));
        }
        return rows;
    }
    public static void main(String[] args)throws Exception
    {
        Path out=Path.of(args[0]);Files.createDirectories(out);var lower=lowerBodies();var spec=new SiloHatchMechanism.Spec(33,33,120,180,-1,-2.01,true);var hatch=NervSiloHatchGeometryR52.loadClasspath(spec);
        var bodies=new ArrayList<Object>();for(var p:lower)bodies.add(Map.of("name",p.name(),"kind",p.kind(),"phase",p.phase(),"triangles",p.mesh().triangles().length/9,"canonical_envelope",array(p.mesh().envelope(p.from(),p.to()))));
        var contacts=new ArrayList<Object>();for(int v=0;v<3;v++)
        {
            double x=72.5-42*v;var lf=root(x,FOOT_FRAME_Y,180);var hf=root(x,HATCH_FRAME_Y,0);
            for(var p:NervLowerFrameR52.permanentFloorBearingPointsR52())contacts.add(Map.of("variant",v,"owner","lower_permanent_column_pad","local",array(p),"world",array(lf.transformPoint(p))));
            for(var p:hatch.bearingPoints())contacts.add(Map.of("variant",v,"owner","hatch_fixed_bearing","local",array(p),"world",array(hf.transformPoint(p))));
        }
        var header=new LinkedHashMap<String,Object>();header.put("source_sha",NervLowerFrameR52.SOURCE_SHA);header.put("hatch_source_sha",NervSiloHatchGeometryR52.SOURCE_SHA);header.put("current_lower_members",67);header.put("lower_intervals",97);header.put("canonical_root_x",.5);header.put("lower_frame_y",FOOT_FRAME_Y);header.put("hatch_frame_y",HATCH_FRAME_Y);header.put("root_z",Z);header.put("lower_yaw",180);header.put("voxel_y_band",new int[]{MIN_Y,MAX_Y});header.put("all_reverse_motion_same_occupancy",true);header.put("monotone_proof","Current at() is a monotone quintic pure-Y segment then a pure-X segment. Return is the same geometric path. Each rope axis has a nested straight extent, with exact max at .3/.45/.85 respectively. No temporal point sampling is used as the occupancy proof.");header.put("intervals",bodies);header.put("contacts",contacts);header.put("world_written",false);header.put("game_started",false);
        Files.writeString(out.resolve("CURRENT_FACTORY_CONTRACT.json"),GSON.toJson(header));
        Files.writeString(out.resolve("LOWER_FULL_STROKE_CUBE_OCCUPANCY.json"),GSON.toJson(occupied(lower)));
        for(int yaw:new int[]{0,180})
        {
            var hb=hatchBodies(hatch,yaw);Files.writeString(out.resolve("HATCH_YAW"+yaw+"_FULL_STROKE_CUBE_OCCUPANCY.json"),GSON.toJson(occupied(hb)));
            var peer=hatchPeers(lower,hb);Files.writeString(out.resolve("HATCH_YAW"+yaw+"_VS_CURRENT_FIXED_LOWER.json"),GSON.toJson(peer));System.out.println("hatch yaw="+yaw+" fixed-lower peer hits="+peer.size());
        }
        System.out.println("CURRENT complete lower+factory hatch geometry exported; no world opened");
    }
}

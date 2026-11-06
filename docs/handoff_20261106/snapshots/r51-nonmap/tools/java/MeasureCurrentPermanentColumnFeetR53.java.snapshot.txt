package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.*;
import com.projectseele.entity.SiloHatchMechanism;

/** Current selected fixed columns and permanent pad interfaces only; no Level. */
public final class MeasureCurrentPermanentColumnFeetR53
{
    private static double[] point(Vec3 p){return new double[]{p.x,p.y,p.z};}
    private static RigidTransform frame(JsonObject row){var a=row.getAsJsonArray("position");var q=row.getAsJsonArray("quaternion");return new RigidTransform(new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble()),q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());}
    public static void main(String[] args)throws Exception
    {
        var units=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var gates=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject().getAsJsonArray("gates");var rows=new ArrayList<Object>();var columns=NervPlantMotionR52.originalFixedColumnsR52();
        for(var raw:units.getAsJsonArray("units"))
        {
            var unit=raw.getAsJsonObject();int variant=unit.get("variant").getAsInt();var root=frame(unit.getAsJsonObject("gantry").getAsJsonObject("frame"));var gate=gates.asList().stream().map(JsonElement::getAsJsonObject).filter(g->g.get("resource").getAsString().equals("bay_"+variant+"_service_pit")).findFirst().orElseThrow();var s=gate.getAsJsonObject("silo_hatch");var sf=frame(gate.getAsJsonObject("frame"));var spec=new SiloHatchMechanism.Spec(s.get("opening_x").getAsFloat(),s.get("opening_z").getAsFloat(),s.get("open_ticks").getAsInt(),s.get("close_ticks").getAsInt(),s.get("separation_sign").getAsInt(),s.get("beam_bottom").getAsDouble(),s.get("service_column_ports").getAsBoolean(),s.get("upright_guide_ports").getAsBoolean(),s.get("service_gantry_yaw_degrees").getAsInt());var hatch=NervSiloHatchGeometryR52.loadClasspath(spec);
            for(var local:NervLowerFrameR52.permanentFloorBearingPointsR52())
            {
                var contact=root.transformPoint(local);int x=(int)Math.floor(contact.x),y=(int)Math.floor(contact.y-.001),z=(int)Math.floor(contact.z);var cube=new AABB(x,y,z,x+1,y+1,z+1);var hits=new ArrayList<String>();var transformedColumns=NervRigidMeshSweepR52.transformed(columns.bounds(),root);
                if(columns.intersects(root,root,cube,.003))hits.add("original_fixed_columns");
                var bearingParts=new ArrayList<String>();int bottomFaces=0;
                for(var p:NervLowerFrameR52.pieces(0))if(p.name().startsWith("permanent_column_foot_seat_"))
                {
                    var xyz=p.mesh().triangles();var f=root.compose(p.local());int faces=0;
                    for(int i=0;i<xyz.length;i+=9){boolean bottom=true;for(int n=0;n<9;n+=3){var q=f.transformPoint(new Vec3(xyz[i+n],xyz[i+n+1],xyz[i+n+2]));bottom&=Math.abs(q.y-contact.y)<1e-5&&Math.abs(q.x-contact.x)<.21&&Math.abs(q.z-contact.z)<.21;}if(bottom)faces++;}
                    if(faces==2){bottomFaces+=faces;bearingParts.add(p.name());}
                }
                for(var p:hatch.pieces(0))if(!p.moving()&&new NervRigidMeshSweepR52(p.part().xyz()).intersects(sf.compose(p.local()),sf.compose(p.local()),cube,.003))hits.add("fixed_hatch/"+p.part().name());
                var thinFits=new LinkedHashMap<String,Object>();for(double minimum:new double[]{.5,.8125,.9375,.98,.995})
                {var thin=new AABB(x,y+minimum,z,x+1,y+1,z+1);var cuts=new ArrayList<String>();for(var p:hatch.pieces(0))if(!p.moving()&&new NervRigidMeshSweepR52(p.part().xyz()).intersects(sf.compose(p.local()),sf.compose(p.local()),thin,.003))cuts.add(p.part().name());thinFits.put(Double.toString(minimum),cuts);}
                boolean leaf=hatch.movingIntersects(sf,0,1,new NervRigidMeshSweepR52(new double[]{x,y,z,x+1,y,z,x+1,y+1,z,x,y,z,x+1,y+1,z,x,y+1,z,x,y,z+1,x+1,y+1,z+1,x+1,y,z+1,x,y,z+1,x,y+1,z+1,x+1,y+1,z+1,x,y,z,x,y+1,z,x,y+1,z+1,x,y,z,x,y+1,z+1,x,y,z+1,x+1,y,z,x+1,y+1,z+1,x+1,y+1,z,x+1,y,z,x+1,y,z+1,x+1,y+1,z+1,x,y,z,x+1,y,z+1,x+1,y,z,x,y,z,x,y,z+1,x+1,y,z+1,x,y+1,z,x+1,y+1,z,x+1,y+1,z+1,x,y+1,z,x+1,y+1,z+1,x,y+1,z+1}),RigidTransform.identity());
                if(leaf)hits.add("full_hatch_leaf_stroke");
                var row=new LinkedHashMap<String,Object>();row.put("variant",variant);row.put("cell",new int[]{x,y,z});row.put("bearing_world",point(contact));row.put("bearing_local",point(local));row.put("native_top_y",cube.maxY);row.put("top_error_m",Math.abs(cube.maxY-contact.y));row.put("actual_permanent_bottom_triangles",bottomFaces);row.put("bearing_parts",bearingParts);row.put("original_column_world_min_y",transformedColumns.minY);row.put("candidate_full_cube_conflicts",hits);row.put("thin_fixed_frame_cassette_conflicts",thinFits);rows.add(row);
            }
        }
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("world_written",false,"game_started",false,"selected_lower_frame_source",NervLowerFrameR52.SOURCE_SHA,"actual_original_columns_triangles",columns.triangles().length/9,"rows",rows)));
        System.out.println("Current permanent column pad candidates="+rows.size());
    }
}

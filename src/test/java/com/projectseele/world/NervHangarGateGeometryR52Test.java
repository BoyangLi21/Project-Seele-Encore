package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import net.minecraft.world.phys.*;

public final class NervHangarGateGeometryR52Test
{
    private static int checks;private static void check(boolean b,String text){checks++;if(!b)throw new AssertionError(text);}
    private static JsonArray vector(double... v){var a=new JsonArray();for(double x:v)a.add(x);return a;}
    private static JsonArray box(AABB b){return vector(b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ);}
    public static void main(String[] args)throws Exception
    {
        var assets=Path.of(args.length==0?"src/main/resources/assets/projectseele":args[0]);var result=new JsonObject();result.addProperty("schema","projectseele.r52.vertical-side-stack-source-measurement.v1");result.addProperty("scope","Source/evaluator measurement only; Root supplies actual frames, foundations, pockets, cells and clocks");result.addProperty("source_sha",NervSiloHatchGeometryR52.SOURCE_SHA);var cases=new JsonArray();
        for(var spec:new NervHangarGateGeometryR52.Spec[]{new NervHangarGateGeometryR52.Spec(33,75,60,60),new NervHangarGateGeometryR52.Spec(164,181,120,120)})
        {
            var actual=NervHangarGateGeometryR52.load(p->Files.readAllBytes(assets.resolve(p)),spec);var all=actual.bounds(0).minmax(actual.bounds(1));check(all.minY==0&&Math.abs(all.maxY-spec.height()-.35)<1e-8,"Actual cassette/frame bottom bears on the foundation; no parts below the floor");check(spec.width()==33?all.getXsize()<42:all.getXsize()<=212,"Full static/animated cassette extent fits Root pitch/outer width");check(all.getZsize()<=13&&all.minZ>=-6&&all.maxZ<=7,"Whole source stack fits the Root 13m side pocket depth");check(actual.pieces(0).stream().filter(NervHangarGateGeometryR52.Piece::moving).count()==8,"Four real source panels per side");check(!actual.intersects(RigidTransform.identity(),1,1,new AABB(-spec.width()/2D,0,0,spec.width()/2D,spec.height(),5.4)),"Fully stacked actual machinery clears the complete Root net opening");check(actual.intersects(RigidTransform.identity(),0,0,new AABB(-1,10,.1,1,11,.7)),"Closed original panel geometry actually seals the central aperture");
            var panel=actual.panel(0,.65F);var witness=new AABB(panel.x()+1,10,panel.z()+.1,panel.x()+1.1,11,panel.z()+.2);check(!actual.intersects(RigidTransform.identity(),0,0,witness)&&!actual.intersects(RigidTransform.identity(),1,1,witness),"Both stopped endpoint shapes miss the middle side-stack witness");check(actual.intersects(RigidTransform.identity(),0,1,witness),"Whole lift/depth/side-stack curve catches the real middle panel obstacle");
            var row=new JsonObject();row.add("net_width_height",vector(spec.width(),spec.height()));row.add("complete_static_and_moving_extents",box(all));row.addProperty("gap",spec.gap());row.addProperty("wall",spec.wall());row.addProperty("panel_width",spec.panelWidth());row.addProperty("pocket_start",spec.pocket());var supports=new JsonArray();for(var p:actual.bearingPoints())supports.add(vector(p.x,p.y,p.z));row.add("mandatory_bearing_points_local",supports);var parts=new JsonArray();for(float progress:new float[]{0,.3F,.65F,1})for(var p:actual.pieces(progress)){var detail=new JsonObject();detail.addProperty("progress",progress);detail.addProperty("part",p.part().name());detail.addProperty("moving",p.moving());detail.add("bounds",box(NervRigidMeshSweepR52.transformed(new NervRigidMeshSweepR52(p.part().xyz()).bounds(),p.local())));parts.add(detail);}row.add("actual_part_samples",parts);cases.add(row);System.out.println("Measured side-stack "+spec.width()+"x"+spec.height()+" "+all);
        }
        result.add("cases",cases);if(args.length>1)Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(result));System.out.println("PASS R52 actual eight-panel side-stack/frame/bearing/net-hole/full-curve checks: "+checks);
    }
}

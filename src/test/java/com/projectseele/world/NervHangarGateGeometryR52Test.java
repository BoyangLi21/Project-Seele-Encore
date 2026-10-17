package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import net.minecraft.world.phys.*;

public final class NervHangarGateGeometryR52Test
{
    private static int checks;private static void check(boolean b,String text){checks++;if(!b)throw new AssertionError(text);}
    private static JsonArray vector(double... v){var a=new JsonArray();for(double x:v)a.add(x);return a;}
    private static JsonArray box(AABB b){return vector(b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ);}
    private static void sweepBoundsChecks(NervHangarGateGeometryR52 actual)
    {
        var id=RigidTransform.identity();var panel=actual.panel(0,.65F);
        var witness=new NervRigidMeshSweepR52(new double[]{panel.x()+1,10,panel.z()-1,panel.x()+1,10,panel.z()+1,panel.x()+1,11,panel.z()});
        check(actual.intersects(id,0,1,witness,id),"Middle-of-motion mesh witness must survive the full sweep broad phase");
        var far=new RigidTransform(new Vec3(1000,0,0),0,0,0,1);
        check(!actual.intersects(far,0,1,witness,id),"Changed gate frame cannot reuse another frame's bounds");
        check(actual.intersects(far,0,1,witness,far),"Translated gate and witness preserve the collision");
        var crossing=new NervRigidMeshSweepR52(new double[]{-1,10,0,1,10,0,0,11,0});
        var before=new RigidTransform(new Vec3(0,0,-20),0,0,0,1);
        var after=new RigidTransform(new Vec3(0,0,20),0,0,0,1);
        check(actual.intersects(id,0,0,crossing,before,after),"Obstacle sweep crossing a closed panel cannot be culled from either endpoint");
        check(!actual.intersects(id,1,1,new AABB(-1,10,.1,1,11,.7)),"Progress changes invalidate the closed aperture bounds");
        for(var bounds:actual.envelopes(id,0,1))check(actual.sweptBounds(id,0,1).minmax(bounds).equals(actual.sweptBounds(id,0,1)),"Broad phase contains every certified leaf sweep");
    }
    public static void main(String[] args)throws Exception
    {
        var assets=Path.of(args.length==0?"src/main/resources/assets/projectseele":args[0]);var result=new JsonObject();result.addProperty("schema","projectseele.r52.vertical-side-stack-source-measurement.v1");result.addProperty("scope","Source/evaluator measurement only; Root supplies actual frames, foundations, pockets, cells and clocks");result.addProperty("source_sha",NervSiloHatchGeometryR52.SOURCE_SHA);var cases=new JsonArray();
        for(var spec:new NervHangarGateGeometryR52.Spec[]{new NervHangarGateGeometryR52.Spec(33,75,60,60),new NervHangarGateGeometryR52.Spec(164,181,120,120)})
        {
            var actual=NervHangarGateGeometryR52.load(p->Files.readAllBytes(assets.resolve(p)),spec);var all=actual.bounds(0).minmax(actual.bounds(1));check(all.minY==0&&Math.abs(all.maxY-spec.height()-.35)<1e-8,"Actual cassette/frame bottom bears on the foundation; no parts below the floor");check(spec.width()==33?all.getXsize()<42:all.getXsize()<=212,"Full static/animated cassette extent fits Root pitch/outer width");check(all.getZsize()<=13&&all.minZ>=-6&&all.maxZ<=7,"Whole source stack fits the Root 13m side pocket depth");check(actual.pieces(0).stream().filter(NervHangarGateGeometryR52.Piece::moving).count()==8,"Four real source panels per side");check(!actual.intersects(RigidTransform.identity(),1,1,new AABB(-spec.width()/2D,0,0,spec.width()/2D,spec.height(),5.4)),"Fully stacked actual machinery clears the complete Root net opening");check(actual.intersects(RigidTransform.identity(),0,0,new AABB(-1,10,.1,1,11,.7)),"Closed original panel geometry actually seals the central aperture");
            var panel=actual.panel(0,.65F);var witness=new AABB(panel.x()+1,10,panel.z()+.1,panel.x()+1.1,11,panel.z()+.2);check(!actual.intersects(RigidTransform.identity(),0,0,witness)&&!actual.intersects(RigidTransform.identity(),1,1,witness),"Both stopped endpoint shapes miss the middle side-stack witness");check(actual.intersects(RigidTransform.identity(),0,1,witness),"Whole lift/depth/side-stack curve catches the real middle panel obstacle");
            var row=new JsonObject();row.add("net_width_height",vector(spec.width(),spec.height()));row.add("complete_static_and_moving_extents",box(all));row.addProperty("gap",spec.gap());row.addProperty("wall",spec.wall());row.addProperty("panel_width",spec.panelWidth());row.addProperty("pocket_start",spec.pocket());var supports=new JsonArray();for(var p:actual.bearingPoints())supports.add(vector(p.x,p.y,p.z));row.add("mandatory_bearing_points_local",supports);var parts=new JsonArray();for(float progress:new float[]{0,.3F,.65F,1})for(var p:actual.pieces(progress)){var detail=new JsonObject();detail.addProperty("progress",progress);detail.addProperty("part",p.part().name());detail.addProperty("moving",p.moving());detail.add("bounds",box(NervRigidMeshSweepR52.transformed(new NervRigidMeshSweepR52(p.part().xyz()).bounds(),p.local())));parts.add(detail);}row.add("actual_part_samples",parts);cases.add(row);System.out.println("Measured side-stack "+spec.width()+"x"+spec.height()+" "+all);
        }
        var sealed=NervHangarGateGeometryR52.load(p->Files.readAllBytes(assets.resolve(p)),new NervHangarGateGeometryR52.Spec(33,75,60,60,-1,new NervHangarGateGeometryR52.BottomSeal(java.util.List.of(new NervHangarGateGeometryR52.SealBox(-16,-1,1,-15,0,2),new NervHangarGateGeometryR52.SealBox(-15,-1,1,-14,0,2),new NervHangarGateGeometryR52.SealBox(-16,-1,2,-15,0,3),new NervHangarGateGeometryR52.SealBox(-15,-1,2,-14,0,3)),4.2,8)));
        check(sealed.intersects(RigidTransform.identity(),0,0,new AABB(-15.8,-1.05,1.2,-15.2,-.95,1.8)),"Below-floor seal remains part of the full gate broad phase");
        var adjacentFloor=new AABB(-15.8,-1,0,-15.2,0,1);
        check(!sealed.intersects(RigidTransform.identity(),0,0,adjacentFloor),"Recorded neighbour touches the floor leaf without penetrating it");
        check(!sealed.intersects(RigidTransform.identity(),0,5.7149414E-6F,adjacentFloor),"Initial vertical drop must not expand the clamped horizontal axis into neighbouring floor");
        check(!sealed.intersects(RigidTransform.identity(),5.7149414E-6F,0,adjacentFloor),"Reverse vertical return retains the same stationary horizontal clearance");
        check(sealed.intersects(RigidTransform.identity(),0,.2F,new AABB(-15.8,-2,1.2,-15.2,-1.5,1.8)),"A real obstruction below the descending leaf remains blocked");
        var longSeal=new NervWetFloorSealR52(new NervHangarGateGeometryR52.Spec(33,75,120,180,-1,new NervHangarGateGeometryR52.BottomSeal(java.util.List.of(new NervHangarGateGeometryR52.SealBox(-16,-1,1,-15,0,2),new NervHangarGateGeometryR52.SealBox(-15,-1,1,-14,0,2),new NervHangarGateGeometryR52.SealBox(-16,-1,2,-15,0,3),new NervHangarGateGeometryR52.SealBox(-15,-1,2,-14,0,3)),4.2,24)));
        var endWall=new AABB(-15.8,-5.1,27,-15.2,-4.5,28);
        var penetratingWall=new AABB(-15.8,-5.1,26.99,-15.2,-4.5,28);
        var middleBlock=new AABB(-15.8,-5.1,14,-15.2,-4.5,14.1);
        var emptyCorner=new AABB(-15.8,-2,14,-15.2,-1.5,14.1);
        for(float[] interval:new float[][]{{.9998502F,.9999545F},{.99F,1},{1,.99F},{0,1},{1,0}}){
            check(!longSeal.intersects(RigidTransform.identity(),interval[0],interval[1],endWall),"Finite retreat endpoint must not expand into the adjacent end wall");
            check(longSeal.intersects(RigidTransform.identity(),interval[0],interval[1],penetratingWall),"Actual one-centimetre end-wall intrusion remains blocked");
        }
        check(!longSeal.intersects(RigidTransform.identity(),0,0,middleBlock)&&!longSeal.intersects(RigidTransform.identity(),1,1,middleBlock),"Middle obstruction misses both stopped endpoints");
        check(longSeal.intersects(RigidTransform.identity(),0,1,middleBlock)&&longSeal.intersects(RigidTransform.identity(),1,0,middleBlock),"Complete drop/retreat and reverse sweeps retain middle obstruction");
        check(!longSeal.intersects(RigidTransform.identity(),0,1,emptyCorner)&&!longSeal.intersects(RigidTransform.identity(),1,0,emptyCorner),"L-shaped motion must not fill its empty upper retreat corner");
        for(var spec:new NervHangarGateGeometryR52.Spec[]{new NervHangarGateGeometryR52.Spec(33,75,60,60),new NervHangarGateGeometryR52.Spec(33,75,60,60,-1)})sweepBoundsChecks(NervHangarGateGeometryR52.load(p->Files.readAllBytes(assets.resolve(p)),spec));
        result.add("cases",cases);if(args.length>1)Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(result));System.out.println("PASS R52 actual eight-panel side-stack/frame/bearing/net-hole/full-curve checks: "+checks);
    }
}

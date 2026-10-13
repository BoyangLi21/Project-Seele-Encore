package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Function;
import java.util.zip.ZipFile;
import net.minecraft.world.phys.*;

/** Actual immutable C7 source geometry plus bounded offline native-reader
 * callbacks. No real level or Entity is instantiated. */
public final class BoundedNativeCollisionGroupsR52Check {
    static void check(boolean value,String why){if(!value)throw new AssertionError(why);}
    static void validate(BoundedNativeCollisionGroupsR52.Plan p) {
        int[] seen=new int[p.pieces().size()];
        for(int group=0;group<p.groups().size();group++)for(int piece:p.groups().get(group).pieces()) {
            var original=p.pieces().get(piece);var bounds=p.groups().get(group).bounds();seen[piece]++;
            check(p.groupOf(piece)==group,"Wrong mapping");
            check(bounds.minX<=original.minX&&bounds.minY<=original.minY&&bounds.minZ<=original.minZ&&bounds.maxX>=original.maxX&&bounds.maxY>=original.maxY&&bounds.maxZ>=original.maxZ,"Member not enclosed");
            check(p.pieces().get(piece)==original,"Original AABB replaced");
        }
        for(int n:seen)check(n==1,"Every real piece must have exactly one group");
        check(p.groupedCellEstimate()<=p.originalCellEstimate(),"Grouping increases estimated traversal");
        check(p.maximumChecksForPiece()<=24&&p.candidateChecks()<=p.pieces().size()*24L,"Candidate work is not bounded");
    }
    static Map<String,Object> metrics(List<AABB> boxes) {
        var p=BoundedNativeCollisionGroupsR52.plan(boxes);validate(p);
        AtomicInteger calls=new AtomicInteger();var clear=BoundedNativeCollisionGroupsR52.clear(boxes,b->true,b->{calls.incrementAndGet();return List.of();},(piece,obstacle)->false);
        check(clear.clear()&&calls.get()==p.groups().size(),"Empty reader was skipped or reread");
        var out=new LinkedHashMap<String,Object>();out.put("pieces",boxes.size());out.put("groups",p.groups().size());out.put("original_cell_estimate",p.originalCellEstimate());out.put("grouped_cell_estimate",p.groupedCellEstimate());out.put("candidate_checks",p.candidateChecks());out.put("maximum_candidates_for_piece",p.maximumChecksForPiece());out.put("empty_native_reader_calls",calls.get());
        out.put("estimated_cell_reduction_fraction",p.originalCellEstimate()==0?0:1-p.groupedCellEstimate()/(double)p.originalCellEstimate());return out;
    }
    static List<AABB> obstacles(AABB query,List<AABB> world) {return world.stream().filter(query::intersects).toList();}
    static double[] cube(AABB b) {
        Vec3[] v={new Vec3(b.minX,b.minY,b.minZ),new Vec3(b.maxX,b.minY,b.minZ),new Vec3(b.maxX,b.maxY,b.minZ),new Vec3(b.minX,b.maxY,b.minZ),new Vec3(b.minX,b.minY,b.maxZ),new Vec3(b.maxX,b.minY,b.maxZ),new Vec3(b.maxX,b.maxY,b.maxZ),new Vec3(b.minX,b.maxY,b.maxZ)};
        int[][] f={{0,2,1},{0,3,2},{4,5,6},{4,6,7},{0,1,5},{0,5,4},{3,7,6},{3,6,2},{0,4,7},{0,7,3},{1,2,6},{1,6,5}};
        double[] a=new double[108];int at=0;for(var t:f)for(int n:t){a[at++]=v[n].x;a[at++]=v[n].y;a[at++]=v[n].z;}return a;
    }
    static int fixtures() {
        int tests=0;
        var near=List.of(new AABB(-3,-2,-1,1,2,3),new AABB(-2.9999999,-2,-1,1.0000001,2,3));var p=BoundedNativeCollisionGroupsR52.plan(near);validate(p);check(p.groups().size()==1,"Nearby exact boxes did not merge");check(!p.pieces().get(0).equals(p.pieces().get(1)),"Near equality was quantized");tests++;
        var wall=new AABB(-.0001,-1,-.5,.0001,1,.5);AtomicInteger reads=new AtomicInteger();
        var result=BoundedNativeCollisionGroupsR52.clear(near,b->true,b->{reads.incrementAndGet();return obstacles(b,List.of(wall));},(piece,obstacle)->near.get(piece).intersects(obstacle));check(!result.clear()&&reads.get()>0,"Thin dynamic wall was skipped");tests++;
        var negative=List.of(new AABB(-65,-33,-97,-59,-27,-91),new AABB(-64,-32,-96,-58,-26,-90));validate(BoundedNativeCollisionGroupsR52.plan(negative));tests++;
        var dispersed=new ArrayList<AABB>();for(int i=0;i<300;i++)dispersed.add(new AABB(i*1000D,-680,0,i*1000D+2,-620,2));var far=BoundedNativeCollisionGroupsR52.plan(dispersed);validate(far);check(far.groups().size()==dispersed.size(),"Dispersed long route merged");tests++;
        var fallbackPieces=List.of(new AABB(0,0,0,3,3,3),new AABB(2,0,0,5,3,3));
        var fallback=BoundedNativeCollisionGroupsR52.clear(fallbackPieces,b->b.getXsize()<=3,b->List.of(),(piece,obstacle)->false);check(fallback.clear()&&fallback.originalFallbackReads()==2,"Unread merged gap did not use original queries");tests++;
        var unread=BoundedNativeCollisionGroupsR52.clear(fallbackPieces,b->false,b->{throw new AssertionError("Unread world was queried");},(piece,obstacle)->false);check(!unread.clear()&&unread.nativeReads()==0,"Unread original did not hold");tests++;
        var bars=List.of(new AABB(-2,-.5,-2,-1,.5,2),new AABB(1,-.5,-2,2,.5,2),new AABB(-1,-.5,-2,1,.5,-1),new AABB(-1,-.5,1,1,.5,2));
        var meshes=bars.stream().map(b->new NervRigidMeshSweepR52(cube(b))).toList();var inHole=new AABB(-.2,-.2,-.2,.2,.2,.2);var frame=RigidTransform.identity();
        var hole=BoundedNativeCollisionGroupsR52.clear(bars,b->true,b->obstacles(b,List.of(inHole)),(piece,obstacle)->meshes.get(piece).intersects(frame,frame,obstacle,.001));check(hole.clear(),"Merged envelope filled a hollow source centre");tests++;
        AtomicInteger callback=new AtomicInteger();var dense=new ArrayList<AABB>();for(int i=0;i<1000;i++)dense.add(new AABB(i*.001,0,0,8+i*.001,8,8));var bounded=BoundedNativeCollisionGroupsR52.plan(dense);validate(bounded);tests++;
        var first=BoundedNativeCollisionGroupsR52.clear(near,b->true,b->{callback.incrementAndGet();return List.of();},(piece,obstacle)->near.get(piece).intersects(obstacle));
        var next=BoundedNativeCollisionGroupsR52.clear(near,b->true,b->{callback.incrementAndGet();return List.of(wall);},(piece,obstacle)->near.get(piece).intersects(obstacle));check(first.clear()&&!next.clear()&&callback.get()==2,"Native shapes survived into another invocation");tests++;
        check(BoundedNativeCollisionGroupsR52.voxelEstimate(new AABB(0,0,0,1,1,1))==125,"Integer-aligned native cursor halo underestimated");tests++;
        // Preserve old first-obstruction order and stop before later groups are read.
        var early=BoundedNativeCollisionGroupsR52.clear(dispersed,b->true,b->{callback.incrementAndGet();return List.of(b);},(piece,obstacle)->true);check(!early.clear()&&early.nativeReads()==1,"Lazy native early exit lost");tests++;
        return tests;
    }
    static Map<String,Object> equivalence(List<AABB> boxes,java.util.function.Predicate<AABB> completeSource,String label) {
        AABB union=null;for(var b:boxes)union=union==null?b:union.minmax(b);var r=new Random(520264L);int clear=0,held=0,cases=512;
        for(int trial=0;trial<cases;trial++) {
            var world=new ArrayList<AABB>();
            for(int n=0;n<1+trial%4;n++) {
                // Include outside air, envelope centres/cavities, very thin
                // walls and ordinary block-sized solids. Values stay exact.
                double x=union.minX-2+r.nextDouble()*(union.getXsize()+4),y=union.minY-2+r.nextDouble()*(union.getYsize()+4),z=union.minZ-2+r.nextDouble()*(union.getZsize()+4);
                if(trial%3==0){var b=boxes.get((trial+n)%boxes.size());x=(b.minX+b.maxX)/2;y=(b.minY+b.maxY)/2;z=(b.minZ+b.maxZ)/2;}
                double half=trial%7==0?.0001:.1+r.nextDouble()*.8;
                world.add(new AABB(x-half,y-.35,z-.35,x+half,y+.35,z+.35));
            }
            // Pure complete-source collision answers can be reused by the
            // offline comparison. No native/world shape result is memoized.
            var answers=new HashMap<AABB,Boolean>();java.util.function.Predicate<AABB> narrow=b->answers.computeIfAbsent(b,completeSource::test);
            boolean original=true;
            original:for(var box:boxes)for(var obstacle:obstacles(box,world))if(narrow.test(obstacle)){original=false;break original;}
            var grouped=BoundedNativeCollisionGroupsR52.clear(boxes,b->true,b->obstacles(b,world),(piece,obstacle)->narrow.test(obstacle));
            check(grouped.clear()==original,"Grouped/original answer differs: "+label+" trial "+trial);
            if(original)clear++;else held++;
        }
        check(clear>0&&held>0,"Equality cases lack both pass and obstruction");
        return Map.of("cases",cases,"original_clear",clear,"original_obstructed",held,"exact_boolean_mismatches",0,
          "original_native_query_boxes_retained",true,"narrow_phase","Same complete actual source triangles and certified step; neither merged AABB nor per-piece bounds decides collision");
    }
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]),jar=Path.of(args[1]),out=root.resolve(".codex/r52_transport_performance_audit");
        var report=new LinkedHashMap<String,Object>();int tests=fixtures();report.put("fixtures_passed",tests);
        try(var z=new ZipFile(jar.toFile())) {
            EvaOriginalMeshGeometryR52.ByteSource bytes=name->z.getInputStream(z.getEntry("assets/projectseele/"+name)).readAllBytes();
            var airHashes=new HashMap<String,String>();for(String name:List.of("mesh/tv_facilities_r16.json","mesh/air_cradle_r31.json"))airHashes.put(name,HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes.read(name))));
            var geometry=NervAirframeGeometryR52.load(bytes,airHashes);var from=RigidTransform.identity();var to=new RigidTransform(new Vec3(0,0,1),0,0,0,1);
            var boxes=new ArrayList<AABB>(geometry.bodyMesh().leafEnvelopes(from,to));for(int i=0;i<4;i++)boxes.addAll(geometry.rotorMesh(i).leafEnvelopes(from.compose(geometry.rotorLocalFrame(i,0)),to.compose(geometry.rotorLocalFrame(i,1))));
            check(boxes.size()==264,"Immutable C7 rigid aircraft topology differs");report.put("actual_C7_aircraft_264_leaf_step",metrics(boxes));
            java.util.function.Predicate<AABB> airNarrow=obstacle->{if(geometry.bodyMesh().intersects(from,to,obstacle,.005))return true;for(int rotor=0;rotor<4;rotor++)if(geometry.rotorMesh(rotor).intersects(from.compose(geometry.rotorLocalFrame(rotor,0)),to.compose(geometry.rotorLocalFrame(rotor,1)),obstacle,.005))return true;return false;};
            report.put("actual_C7_aircraft_strict_return_equality",equivalence(boxes,airNarrow,"aircraft"));
            var selection=JsonParser.parseString(new String(bytes.read("eva/full_assembly_geometry_r52_sources.json"),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();var hashes=new HashMap<String,String>();selection.getAsJsonObject("resources").entrySet().forEach(e->hashes.put(e.getKey(),e.getValue().getAsString()));
            var carrier=FullAssemblyGeometryR52.load(bytes,hashes);var envelopes=new ArrayList<AABB>();var carrierMeshes=new ArrayList<NervRigidMeshSweepR52>();int triangles=0;
            var carrierParts=new TreeMap<>(carrier.carrierParts(0,1,false,0,64));
            report.put("carrier_fixture_part_order",new ArrayList<>(carrierParts.keySet()));
            for(var part:carrierParts.values()) {
                AABB b=null;for(int n=0;n<part.length;n+=3){var v=new Vec3(part[n],part[n+1],part[n+2]);b=b==null?new AABB(v,v):b.minmax(new AABB(v,v));}triangles+=part.length/9;
                // Actual C7 source part bounds, translated along a one-metre
                // straight step. No turn approximation or standing proxy.
                envelopes.add(b.minmax(b.move(0,0,1)));
                carrierMeshes.add(new NervRigidMeshSweepR52(part));
            }
            report.put("actual_C7_raised64_carrier_part_step",metrics(envelopes));report.put("actual_carrier_source_triangles",triangles);report.put("source_asset_hashes",hashes);report.put("air_source_hashes",airHashes);
            report.put("actual_C7_carrier_strict_return_equality",equivalence(envelopes,obstacle->{for(var mesh:carrierMeshes)if(mesh.intersects(from,to,obstacle,.005))return true;return false;},"carrier"));
        }
        report.put("native_world_instantiated",false);report.put("game_started",false);report.put("world_written",false);report.put("entry_points_integrated",false);report.put("FPS_or_speedup_claimed",false);
        report.put("limits","Actual immutable C7 source mesh topology/part envelopes on explicit one-metre no-plane-rotation fixture steps. Offline callbacks verify grouping/reader/narrow-phase semantics; no live Forge world, real CPU/FPS benchmark, dynamic metadata timing or admission proof produced.");
        Files.writeString(out.resolve("BOUNDED_NATIVE_GROUPING_SOURCE_RECEIPT.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));
        System.out.println(new Gson().toJson(report));
    }
}

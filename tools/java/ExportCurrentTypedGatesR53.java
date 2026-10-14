package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.SiloHatchMechanism;
import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.function.DoubleFunction;
import java.util.zip.*;
import net.minecraft.world.phys.*;

/** Current production factories only. No Level, blocks, entity creation or game. */
public final class ExportCurrentTypedGatesR53
{
    private static final Gson GSON=new GsonBuilder().setPrettyPrinting().create();
    private record Part(NervAirframeGeometryR52.Part part,RigidTransform local,boolean moving){}
    private record Cell(int x,int y,int z) implements Comparable<Cell>{public int compareTo(Cell c){int a=Integer.compare(x,c.x);if(a!=0)return a;a=Integer.compare(y,c.y);return a!=0?a:Integer.compare(z,c.z);}int[] xyz(){return new int[]{x,y,z};}}
    private record Model(DoubleFunction<List<Part>> pieces,List<Vec3> floor,List<Vec3> wall,double[] breaks){}
    private static double[] xyz(Vec3 p){return new double[]{p.x,p.y,p.z};}
    private static double[] frame(RigidTransform f){return new double[]{f.translation().x,f.translation().y,f.translation().z,f.qx(),f.qy(),f.qz(),f.qw()};}
    private static double[] box(AABB b){return new double[]{b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ};}
    private static String sha(Path p)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(p)));}
    private static JsonObject json(Path p)throws Exception{return JsonParser.parseString(Files.readString(p)).getAsJsonObject();}
    private static void write(Path p,Object value)throws Exception{Files.createDirectories(p.getParent());Files.writeString(p,GSON.toJson(value));}
    private static RigidTransform root(JsonObject gate){var f=gate.getAsJsonObject("frame");var p=f.getAsJsonArray("position");var q=f.getAsJsonArray("quaternion");return new RigidTransform(new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()),q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());}
    private static boolean bool(JsonObject o,String k){return o.has(k)&&o.get(k).getAsBoolean();}
    private static Model model(JsonObject gate)throws Exception
    {
        if(gate.get("kind").getAsString().equals("SILO"))
        {
            var s=gate.getAsJsonObject("silo_hatch");var spec=new SiloHatchMechanism.Spec(s.get("opening_x").getAsFloat(),s.get("opening_z").getAsFloat(),s.get("open_ticks").getAsInt(),s.get("close_ticks").getAsInt(),s.get("separation_sign").getAsInt(),s.get("beam_bottom").getAsDouble(),bool(s,"service_column_ports"),bool(s,"upright_guide_ports"),s.has("service_gantry_yaw_degrees")?s.get("service_gantry_yaw_degrees").getAsInt():0,s.has("upright_guide_early_variant")?s.get("upright_guide_early_variant").getAsInt():-1);
            var g=NervSiloHatchGeometryR52.loadClasspath(spec);return new Model(p->g.pieces((float)p).stream().map(q->new Part(q.part(),q.local(),q.moving())).toList(),g.bearingPoints(),List.of(),new double[]{0,.3,1});
        }
        var s=gate.getAsJsonObject("hangar_stack");NervHangarGateGeometryR52.BottomSeal bottom=null;
        if(s.has("floor_seal")){var f=s.getAsJsonObject("floor_seal");var boxes=new ArrayList<NervHangarGateGeometryR52.SealBox>();for(var raw:f.getAsJsonArray("closed_boxes")){var a=raw.getAsJsonArray();boxes.add(new NervHangarGateGeometryR52.SealBox(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble(),a.get(3).getAsDouble(),a.get(4).getAsDouble(),a.get(5).getAsDouble()));}bottom=new NervHangarGateGeometryR52.BottomSeal(boxes,f.get("drop_m").getAsDouble(),f.get("retreat_local_z_m").getAsDouble(),f.has("version")?f.get("version").getAsInt():1,f.has("retained_box_count")?f.get("retained_box_count").getAsInt():0);}
        var spec=new NervHangarGateGeometryR52.Spec(gate.get("width").getAsFloat(),gate.get("height").getAsFloat(),s.get("open_ticks").getAsInt(),s.get("close_ticks").getAsInt(),s.has("depth_direction")?s.get("depth_direction").getAsInt():1,bottom);var g=NervHangarGateGeometryR52.loadClasspath(spec);
        return new Model(p->g.pieces((float)p).stream().map(q->new Part(q.part(),q.local(),q.moving())).toList(),g.bearingPoints(),g.bottomSealBearingPointsR52(),bottom==null?new double[]{0,.3,1}:new double[]{0,.25,.3,1});
    }
    private static boolean leaf(Part p){return p.moving()&&(!p.part().name().startsWith("bottom_seal/")||p.part().name().startsWith("bottom_seal/leaf/"));}
    private static boolean enclosedByActualSealBox(Part part,RigidTransform frame,AABB cell)
    {
        if(!part.part().name().startsWith("bottom_seal/leaf/"))return false;
        var xyz=part.part().xyz();if(xyz.length!=108)throw new AssertionError("Current seal must retain its complete twelve source triangles");
        var vertices=new HashSet<Vec3>();AABB bounds=null;for(int i=0;i<xyz.length;i+=3){var p=frame.transformPoint(new Vec3(xyz[i],xyz[i+1],xyz[i+2]));vertices.add(p);bounds=bounds==null?new AABB(p,p):bounds.minmax(new AABB(p,p));}
        if(vertices.size()!=8)throw new AssertionError("Actual seal cube source topology changed");var faces=new int[6];
        for(int t=0;t<xyz.length;t+=9){var a=frame.transformPoint(new Vec3(xyz[t],xyz[t+1],xyz[t+2]));var b=frame.transformPoint(new Vec3(xyz[t+3],xyz[t+4],xyz[t+5]));var c=frame.transformPoint(new Vec3(xyz[t+6],xyz[t+7],xyz[t+8]));int face=-1;double[] lo={bounds.minX,bounds.minY,bounds.minZ},hi={bounds.maxX,bounds.maxY,bounds.maxZ},A={a.x,a.y,a.z},B={b.x,b.y,b.z},C={c.x,c.y,c.z};for(int axis=0;axis<3;axis++)if(A[axis]==B[axis]&&A[axis]==C[axis]){if(A[axis]==lo[axis])face=axis*2;if(A[axis]==hi[axis])face=axis*2+1;}if(face<0||b.subtract(a).cross(c.subtract(a)).lengthSqr()<1e-20)throw new AssertionError("Actual seal is no longer the closed axis-aligned source box");faces[face]++;}
        if(Arrays.stream(faces).anyMatch(n->n!=2))throw new AssertionError("Incomplete actual seal box faces");
        return bounds.contains(cell.getCenter());
    }
    private static TreeMap<Cell,String> closedCells(Model model,RigidTransform root)
    {
        var result=new TreeMap<Cell,String>();for(var p:model.pieces().apply(0)){if(!leaf(p))continue;var f=root.compose(p.local());var mesh=new NervRigidMeshSweepR52(p.part().xyz());var b=mesh.envelope(f,f);String state=p.part().name().startsWith("bottom_seal/leaf/")?"projectseele:nerv_floor_panel":"minecraft:barrier";
            for(int x=(int)Math.floor(b.minX+2e-7);x<=Math.floor(b.maxX-2e-7);x++)for(int y=(int)Math.floor(b.minY+2e-7);y<=Math.floor(b.maxY-2e-7);y++)for(int z=(int)Math.floor(b.minZ+2e-7);z<=Math.floor(b.maxZ-2e-7);z++){var cube=new AABB(x,y,z,x+1,y+1,z+1).deflate(2e-7);if(mesh.intersects(f,f,cube,.003)||enclosedByActualSealBox(p,f,cube)){var cell=new Cell(x,y,z);var old=result.putIfAbsent(cell,state);if(old!=null&&!old.equals(state))throw new AssertionError("Two actual leaf materials own the same cell: "+cell);}}}
        return result;
    }
    private static JsonArray readRows(Path base,JsonObject gate)throws Exception
    {
        var ref=gate.getAsJsonObject("collision_steps");var p=base.resolve(ref.get("cells_file").getAsString()).normalize();if(!p.startsWith(base)||!sha(p).equals(ref.get("sha256").getAsString()))throw new AssertionError("Actual Root table changed");try(var in=new GZIPInputStream(Files.newInputStream(p));var r=new InputStreamReader(in,java.nio.charset.StandardCharsets.UTF_8)){return JsonParser.parseReader(r).getAsJsonArray();}
    }
    private static JsonObject table(Path out,String id,JsonArray rows)throws Exception
    {
        var file=out.resolve("collision_tables/"+id+".json.gz");Files.createDirectories(file.getParent());try(var z=new GZIPOutputStream(Files.newOutputStream(file))){z.write(new Gson().toJson(rows).getBytes(java.nio.charset.StandardCharsets.UTF_8));}var ref=new JsonObject();ref.addProperty("cells_file",out.relativize(file).toString().replace('\\','/'));ref.addProperty("sha256",sha(file));return ref;
    }
    private static Map<Cell,String> index(JsonArray rows)
    {
        var result=new TreeMap<Cell,String>();for(var row:rows)for(var raw:row.getAsJsonArray()){var c=raw.getAsJsonObject();var p=c.getAsJsonArray("position");var at=new Cell(p.get(0).getAsInt(),p.get(1).getAsInt(),p.get(2).getAsInt());if(result.put(at,c.get("closed").getAsString())!=null)throw new AssertionError("Duplicate actual proxy cell");if(c.get("closed").equals(c.get("open")))throw new AssertionError("Unchanged placeholder proxy cell");}return result;
    }
    private static JsonArray rows(Map<Cell,String> cells){var row=new JsonArray();for(var e:cells.entrySet()){var c=new JsonObject();c.add("position",GSON.toJsonTree(e.getKey().xyz()));c.addProperty("closed",e.getValue());c.addProperty("open","minecraft:air");row.add(c);}var all=new JsonArray();all.add(row);return all;}
    private static boolean pointIn(Vec3 p,Vec3 a,Vec3 b,Vec3 c,Vec3 normal)
    {var u=b.subtract(a);var v=c.subtract(a);var w=p.subtract(a);double uu=u.dot(u),uv=u.dot(v),vv=v.dot(v),wu=w.dot(u),wv=w.dot(v),den=uu*vv-uv*uv;if(den<1e-20||Math.abs(w.dot(normal))>1e-6)return false;double x=(wu*vv-wv*uv)/den,y=(wv*uu-wu*uv)/den;return x>=-1e-6&&y>=-1e-6&&x+y<=1+1e-6;}
    private static List<Map<String,Object>> contacts(Model model,RigidTransform root)
    {
        var out=new ArrayList<Map<String,Object>>();var fixed=model.pieces().apply(0).stream().filter(p->!p.moving()).toList();var points=new ArrayList<Vec3>(model.floor());points.addAll(model.wall());
        for(int i=0;i<points.size();i++)
        {
            boolean wall=i>=model.floor().size();var local=points.get(i);var normal=root.transformVector(wall?new Vec3(local.x<0?1:-1,0,0):new Vec3(0,1,0));var point=root.transformPoint(local);var u=Math.abs(normal.y)>.5?new Vec3(1,0,0):new Vec3(0,1,0);var v=normal.cross(u);double half=wall?.10:.05;var witnesses=new LinkedHashSet<String>();int covered=0;
            for(double x:new double[]{-half,0,half})for(double z:new double[]{-half,0,half}){var q=point.add(u.scale(x)).add(v.scale(z));boolean hit=false;for(var part:fixed){var values=part.part().xyz();var frame=root.compose(part.local());for(int t=0;t<values.length;t+=9){var A=frame.transformPoint(new Vec3(values[t],values[t+1],values[t+2]));var B=frame.transformPoint(new Vec3(values[t+3],values[t+4],values[t+5]));var C=frame.transformPoint(new Vec3(values[t+6],values[t+7],values[t+8]));var n=B.subtract(A).cross(C.subtract(A));if(n.lengthSqr()<1e-20)continue;n=n.scale(1/n.length());if(Math.abs(n.dot(normal))<1-1e-6||!pointIn(q,A,B,C,n))continue;hit=true;witnesses.add(part.part().name()+"#"+(t/9));}}if(hit)covered++;}
            if(covered!=9)throw new AssertionError("Actual finite gate bearing surface missing: "+i+" at="+point+" covered="+covered);
            var backing=point.subtract(normal.scale(.001));out.add(Map.of("kind",wall?"native_side_wall":"native_top_face","point_world",xyz(point),"normal_world",xyz(normal),"half_width_m",half,"candidate_cell",new int[]{(int)Math.floor(backing.x),(int)Math.floor(backing.y),(int)Math.floor(backing.z)},"nine_points_on_actual_fixed_triangles",true,"triangle_witnesses",witnesses));
        }
        if(model.floor().size()!=8)throw new AssertionError("Eight original fixed floor bearing points required");return out;
    }
    private static Map<String,Object> exportProfile(Model model,Path out,String key)throws Exception
    {
        var pieces=model.pieces().apply(0);var file=out.resolve("profiles/"+key+".mesh.rgb.bin.gz");Files.createDirectories(file.getParent());var descriptors=new ArrayList<Object>();
        try(var stream=new DataOutputStream(new GZIPOutputStream(Files.newOutputStream(file)))){stream.writeInt(pieces.size());for(int i=0;i<pieces.size();i++){var p=pieces.get(i);var vertices=p.part().vertices();stream.writeUTF(i+"/"+p.part().name());stream.writeBoolean(p.moving());stream.writeInt(vertices.length);for(double d:vertices)stream.writeDouble(d);descriptors.add(Map.of("index",i,"name",p.part().name(),"moving",p.moving(),"triangles",vertices.length/18,"closed_local_frame",frame(p.local())));}}
        var phases=new ArrayList<Object>();for(double progress:model.breaks()){var p=model.pieces().apply(progress);var frames=new ArrayList<Object>();for(int i=0;i<p.size();i++)frames.add(Map.of("part",i,"local_frame",frame(p.get(i).local())));phases.add(Map.of("progress",progress,"parts",frames));}
        var sweeps=new ArrayList<Object>();int monotoneChecks=0;
        for(int i=0;i<pieces.size();i++)for(int j=0;j<model.breaks().length-1;j++)
        {
            var p=pieces.get(i);if(!p.moving()&&j>0)continue;double a=model.breaks()[j],b=model.breaks()[j+1];var from=model.pieces().apply(a).get(i).local();var to=model.pieces().apply(b).get(i).local();var delta=to.translation().subtract(from.translation());int axes=(Math.abs(delta.x)>1e-9?1:0)+(Math.abs(delta.y)>1e-9?1:0)+(Math.abs(delta.z)>1e-9?1:0);if(axes>1||from.rotationErrorDegrees(to)>1e-7)throw new AssertionError("Current gate stage no longer an exact constant-rotation one-axis sweep");double previous=-1e-9;
            for(int k=0;k<=16;k++){var at=model.pieces().apply(a+(b-a)*k/16).get(i);if(!Arrays.equals(at.part().vertices(),p.part().vertices()))throw new AssertionError("Gate mesh deformed between phases");var d=at.local().translation().subtract(from.translation());double f=delta.lengthSqr()<1e-16?0:d.dot(delta)/delta.lengthSqr();if(at.local().rotationErrorDegrees(from)>1e-7||d.subtract(delta.scale(f)).lengthSqr()>1e-12||f<previous-1e-7||f>1+1e-7)throw new AssertionError("Actual stage has no certified monotone pure translation");previous=f;monotoneChecks++;}
            sweeps.add(Map.of("part",i,"moving",p.moving(),"progress_from",a,"progress_to",b,"from",frame(from),"to",frame(to),"axis_count",axes,"extra_curve_error_m",0,"proof","fixed-shape monotone one-axis production smoothstep; exact swept set"));
        }
        var result=new LinkedHashMap<String,Object>();result.put("mesh_file",out.relativize(file).toString().replace('\\','/'));result.put("mesh_sha256",sha(file));result.put("format","big-endian int partCount; per part UTF index/name, boolean moving, int RGB double-count, doubles stride6 XYZRGB");result.put("parts",descriptors);result.put("phases",phases);result.put("continuous_sweeps",sweeps);result.put("monotone_source_checks",monotoneChecks);return result;
    }
    public static void main(String[] args)throws Exception
    {
        var seed=Path.of(args[0]).toAbsolutePath().normalize();var out=Path.of(args[1]).toAbsolutePath().normalize();Files.createDirectories(out);var root=json(seed);long epoch=root.get("epoch").getAsLong();var profiles=new LinkedHashMap<String,Object>();var candidates=new JsonArray();var interfaces=new ArrayList<Object>();var issues=new ArrayList<Object>();var ownership=new ArrayList<Object>();var frontSealCells=new HashMap<Integer,Set<Cell>>();var owned=new HashMap<Cell,String>();
        for(var raw:root.getAsJsonArray("gates"))
        {
            var g=raw.getAsJsonObject().deepCopy();if(g.has("floor_seal_original_cells")){var set=new HashSet<Cell>();for(var c:g.getAsJsonArray("floor_seal_original_cells")){var a=c.getAsJsonArray();set.add(new Cell(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt()));}if(set.isEmpty()||set.size()>512)throw new AssertionError("Exact bounded declared front seals required");frontSealCells.put(g.get("variant").getAsInt(),set);}String id=g.get("resource").getAsString();g.addProperty("visual",NervAssemblyOwnerR52.proposedGateIdentityR53(epoch,id).toString());var model=model(g);var frame=root(g);var spec=new JsonObject();for(String k:List.of("kind","width","height","hangar_stack","silo_hatch"))if(g.has(k))spec.add(k,g.get(k));String key=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(spec.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8))).substring(0,20);if(!profiles.containsKey(key))profiles.put(key,exportProfile(model,out,key));
            var actual=closedCells(model,frame);var support=contacts(model,frame);var supports=g.getAsJsonArray("supports");if(supports.isEmpty()){for(var r:support){var c=new JsonObject();c.add("position",GSON.toJsonTree(r.get("candidate_cell")));c.addProperty("state","projectseele:nerv_structural_panel");supports.add(c);}}else{var declared=new HashSet<String>();for(var s:supports)declared.add(s.getAsJsonObject().getAsJsonArray("position").toString());for(var r:support)if(!declared.contains(GSON.toJsonTree(r.get("candidate_cell")).toString())){boolean expanded=g.has("hangar_stack")&&g.getAsJsonObject("hangar_stack").has("floor_seal")&&g.getAsJsonObject("hangar_stack").getAsJsonObject("floor_seal").has("version")&&g.getAsJsonObject("hangar_stack").getAsJsonObject("floor_seal").get("version").getAsInt()==2;if(!expanded)throw new AssertionError("Root existing declared support differs from current actual contact "+id+" "+r);var cell=new JsonObject();cell.add("position",GSON.toJsonTree(r.get("candidate_cell")));cell.addProperty("state","projectseele:nerv_structural_panel");supports.add(cell);declared.add(cell.getAsJsonArray("position").toString());}}
            var oldRows=g.has("collision_steps")?readRows(seed.getParent(),g):null;var actualRows=rows(actual);var chosen=oldRows==null?actualRows:oldRows;
            if(id.endsWith("_service_pit"))
            {
                var index=index(chosen);int variant=g.get("variant").getAsInt();var seal=frontSealCells.get(variant);
                if(seal==null)throw new AssertionError("Explicit bounded front-owned seal set required");
                String front="bay_"+variant+"_front";var removed=new ArrayList<int[]>();
                for(var cell:seal)if(index.containsKey(cell))
                {
                    if(!front.equals(owned.get(cell))||!index.get(cell).equals("projectseele:nerv_floor_panel"))throw new AssertionError("Unproven cross-gate proxy overlap");
                    index.remove(cell);removed.add(cell.xyz());
                }
                if(removed.isEmpty()&&(index.size()==1154||index.size()==1150))
                {
                    var sourceMissing=new ArrayList<Cell>();for(var cell:actual.keySet())if(!index.containsKey(cell))sourceMissing.add(cell);
                    if(sourceMissing.size()!=1||!front.equals(owned.get(sourceMissing.get(0)))||!seal.contains(sourceMissing.get(0)))throw new AssertionError("Already assigned pit cell must be the exact front-owned source leaf");
                    removed.add(sourceMissing.get(0).xyz());
                }
                if(removed.size()!=1||(index.size()!=1154&&index.size()!=1150))throw new AssertionError("Only one exact shared floor cell belongs to front ownership");
                int left=56-42*variant,right=88-42*variant;var ports=new TreeSet<Cell>();
                for(int x:new int[]{left,right})for(int z:new int[]{322,334})ports.add(new Cell(x,-1063,z));
                var extra=new TreeSet<Cell>();for(var cell:index.keySet())if(!actual.containsKey(cell))extra.add(cell);
                if(index.size()==1154)
                {
                    if(!extra.equals(ports))throw new AssertionError("Only four exact original column-foot ports may remove stale pit proxies");
                    for(var cell:ports){if(!"projectseele:nerv_floor_panel".equals(index.remove(cell)))throw new AssertionError("Column-port proxy material changed");}
                }
                else if(!extra.isEmpty())throw new AssertionError("Corrected service table has an unowned closed proxy");
                for(var cell:ports)if(actual.containsKey(cell)||index.containsKey(cell))throw new AssertionError("Actual original service-column port must remain open");
                ownership.add(Map.of("resource",id,"original_root_proxy_count",1155,"new_runtime_proxy_count",1150,"unchanged_actual_35m_leaf_geometry",true,"front_owned_cells",removed,"removed_original_column_port_cells",ports.stream().map(Cell::xyz).toList()));
                chosen=rows(index);
            }
            g.add("collision_steps",table(out,id,chosen));var chosenIndex=index(chosen);var missing=new ArrayList<int[]>();var extra=new ArrayList<int[]>();for(var at:actual.keySet())if(!chosenIndex.containsKey(at))missing.add(at.xyz());for(var at:chosenIndex.keySet())if(!actual.containsKey(at))extra.add(at.xyz());if(!missing.isEmpty()||!extra.isEmpty())issues.add(Map.of("resource",id,"retained_root_table_missing_actual_leaf_cells",missing,"retained_root_table_cells_without_actual_closed_leaf",extra));
            for(var at:chosenIndex.keySet()){var prior=owned.putIfAbsent(at,id);if(prior!=null)issues.add(Map.of("blocking_shared_proxy_cell",at.xyz(),"first_resource",prior,"second_resource",id,"native_commission_allowed",false));}
            table(out,id+"__actual_closed_leaf",actualRows);AABB all=null,moving=null;for(double p:model.breaks())for(var part:model.pieces().apply(p)){var b=NervRigidMeshSweepR52.transformed(new NervRigidMeshSweepR52(part.part().xyz()).bounds(),frame.compose(part.local()));all=all==null?b:all.minmax(b);if(part.moving())moving=moving==null?b:moving.minmax(b);}
            var row=new LinkedHashMap<String,Object>();row.put("resource",id);row.put("visual",g.get("visual").getAsString());row.put("variant",g.get("variant").getAsInt());row.put("profile",key);row.put("world_root",frame(frame));row.put("actual_floor_bearings",8);row.put("actual_wall_bearings",model.wall().size());row.put("bearing_contacts",support);row.put("complete_mesh_motion_broadphase_bounds",box(all));row.put("moving_mesh_motion_broadphase_bounds",box(moving));row.put("actual_closed_leaf_cell_count",actual.size());row.put("selected_proxy_cell_count",chosenIndex.size());row.put("source_proxy_preserved",oldRows!=null);row.put("collision_steps",g.get("collision_steps"));
            if(g.has("silo_hatch")&&bool(g.getAsJsonObject("silo_hatch"),"upright_guide_ports"))
            {
                var declared=g.getAsJsonObject("silo_hatch");int early=declared.has("upright_guide_early_variant")?declared.get("upright_guide_early_variant").getAsInt():-1;
                row.put("production_upright_guide_early_variant",early);row.put("production_upright_guide_slots_xz",NervSiloHatchGeometryR52.uprightGuideSteelPortsR52(early).stream().map(b->new double[]{b.minX,b.minZ,b.maxX,b.maxZ}).toList());
            }
            interfaces.add(row);candidates.add(g);System.out.println("gate="+id+" actual_closed="+actual.size()+" selected="+chosenIndex.size()+" floor=8 wall="+model.wall().size());
        }
        if(candidates.size()!=41)throw new AssertionError("Exact current41 Root gates required");var doc=new JsonObject();doc.addProperty("schema","projectseele.r52.root-measured-gates.v1");doc.addProperty("map_author","root");doc.addProperty("status","design");doc.addProperty("epoch",epoch);doc.addProperty("directory_sha256",root.get("directory_sha256").getAsString());doc.addProperty("world_written",false);doc.addProperty("native_controllers_installed",false);doc.add("gates",candidates);write(out.resolve("ROOT_TYPED_GATES_CANDIDATE.json"),doc);
        var result=new LinkedHashMap<String,Object>();result.put("schema","projectseele.r53.current-typed-gate-interface.v1");result.put("seed_sha256",sha(seed));result.put("epoch",epoch);result.put("directory_sha256",root.get("directory_sha256").getAsString());result.put("root_gate_candidate",Map.of("file","ROOT_TYPED_GATES_CANDIDATE.json","sha256",sha(out.resolve("ROOT_TYPED_GATES_CANDIDATE.json"))));result.put("r16_source_sha256",NervSiloHatchGeometryR52.SOURCE_SHA);result.put("profiles",profiles);result.put("gates",interfaces);result.put("actual_current_source_proxy_differences",issues);result.put("root_approved_unique_proxy_ownership",ownership);result.put("kernel_maximum_error_m",.003);result.put("closed_leaf_voxel_interior_deflate_m",2e-7);result.put("world_written",false);result.put("world_collision_checked",false);result.put("native_acceptance",false);write(out.resolve("CURRENT_TYPED_GATE_INTERFACE.json"),result);System.out.println("CURRENT41_GATE_EXPORT="+sha(out.resolve("CURRENT_TYPED_GATE_INTERFACE.json"))+" profiles="+profiles.size()+" retained_proxy_differences="+issues.size());
    }
}

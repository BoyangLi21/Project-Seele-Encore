package com.projectseele.world;
import com.google.gson.*;
import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.zip.GZIPInputStream;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;

/** Full actual bank-head mesh/rigid intervals against measured native boxes. */
public final class VerifyCurrentBankHeadWorldR53
{
    private record Part(String name,String role,NervRigidMeshSweepR52 mesh){}
    private record Step(String part,boolean reverse,int tick,RigidTransform from,RigidTransform to,double arc){}
    private record Cell(int x,int y,int z,String state,List<AABB> boxes,JsonObject source){String key(){return x+","+y+","+z;}}
    private static final Gson GSON=new GsonBuilder().setPrettyPrinting().create();
    private static String sha(Path p)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(p)));}
    private static RigidTransform frame(JsonArray a){return new RigidTransform(new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble()),a.get(3).getAsFloat(),a.get(4).getAsFloat(),a.get(5).getAsFloat(),a.get(6).getAsFloat());}
    private static RigidTransform add(RigidTransform f,Vec3 root){return new RigidTransform(f.translation().add(root),f.qx(),f.qy(),f.qz(),f.qw());}
    private static double[] values(AABB b){return new double[]{b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ};}
    private static double[] values(RigidTransform f){return new double[]{f.translation().x,f.translation().y,f.translation().z,f.qx(),f.qy(),f.qz(),f.qw()};}
    private static AABB box(JsonArray a){return new AABB(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble(),a.get(3).getAsDouble(),a.get(4).getAsDouble(),a.get(5).getAsDouble());}
    private static String phase(int tick){return tick<30?"retract":tick<90?"turn":"extend";}
    private static final class Hit
    {
        final Cell cell;final String part,role;boolean initial;double maxArc;final Map<Boolean,TreeSet<Integer>> clocks=new LinkedHashMap<>();
        Hit(Cell cell,Part part){this.cell=cell;this.part=part.name();this.role=part.role();}
        void add(Step step){if(step==null){initial=true;return;}clocks.computeIfAbsent(step.reverse(),q->new TreeSet<>()).add(step.tick());maxArc=Math.max(maxArc,step.arc());}
        Object row(){var ranges=new ArrayList<Object>();for(var entry:clocks.entrySet()){Integer first=null,last=null;String stage=null;for(int t:entry.getValue()){String current=phase(t);if(first==null){first=last=t;stage=current;}else if(t==last+1&&stage.equals(current))last=t;else{ranges.add(Map.of("reverse",entry.getKey(),"phase",stage,"tick_from",first,"tick_to_exclusive",last+1));first=last=t;stage=current;}}if(first!=null)ranges.add(Map.of("reverse",entry.getKey(),"phase",stage,"tick_from",first,"tick_to_exclusive",last+1));}return Map.of("part",part,"role",role,"position",new int[]{cell.x(),cell.y(),cell.z()},"state",cell.state(),"native_boxes",cell.boxes().stream().map(VerifyCurrentBankHeadWorldR53::values).toList(),"initial_actual_pose_hit",initial,"action_intervals",ranges,"maximum_exported_arc_error_m",maxArc);}
    }
    private static long test(Part part,RigidTransform from,RigidTransform to,double arc,Step step,Map<String,Cell> cells,double[] offsets,Map<String,Hit> hits)
    {
        var bounds=part.mesh().envelope(from,to).inflate(arc);long count=0;
        int x0=(int)Math.floor(bounds.minX-offsets[3]),x1=(int)Math.floor(bounds.maxX-offsets[0]);
        int y0=(int)Math.floor(bounds.minY-offsets[4]),y1=(int)Math.floor(bounds.maxY-offsets[1]);
        int z0=(int)Math.floor(bounds.minZ-offsets[5]),z1=(int)Math.floor(bounds.maxZ-offsets[2]);
        for(int y=y0;y<=y1;y++)for(int z=z0;z<=z1;z++)for(int x=x0;x<=x1;x++)
        {
            var cell=cells.get(x+","+y+","+z);if(cell==null)continue;
            for(var obstacle:cell.boxes())
            {
                if(!bounds.intersects(obstacle))continue;count++;
                if(part.mesh().intersects(from,to,obstacle.inflate(arc),.003))
                {hits.computeIfAbsent(cell.key()+"/"+part.name(),q->new Hit(cell,part)).add(step);break;}
            }
        }
        return count;
    }
    public static void main(String[] args)throws Exception
    {
        Path input=Path.of(args[0]),out=Path.of(args[1]);Files.createDirectories(out);var declaration=JsonParser.parseString(Files.readString(input)).getAsJsonObject();
        if(!declaration.get("head_source_sha256").getAsString().equals(NervBankHeadTransferR53.SOURCE_SHA))throw new AssertionError("Actual current db7 source differs");
        var files=declaration.getAsJsonObject("source_files");for(var e:files.entrySet()){var row=e.getValue().getAsJsonObject();if(!sha(Path.of(row.get("path").getAsString())).equals(row.get("sha256").getAsString()))throw new AssertionError("Stale exported source "+e.getKey());}
        Path mesh=Path.of(files.getAsJsonObject("BANK_HEAD_ACTUAL_MESH.bin.gz").get("path").getAsString());var parts=new LinkedHashMap<String,Part>();
        try(var stream=new DataInputStream(new GZIPInputStream(Files.newInputStream(mesh)))){int count=stream.readInt();for(int i=0;i<count;i++){String name=stream.readUTF(),role=stream.readUTF();int n=stream.readInt();double[] xyz=new double[n];for(int j=0;j<n;j++)xyz[j]=stream.readDouble();if(parts.put(name,new Part(name,role,new NervRigidMeshSweepR52(xyz)))!=null)throw new AssertionError("Duplicate actual part");}if(stream.read()!=-1)throw new AssertionError("Trailing mesh data");}
        var initial=new LinkedHashMap<String,RigidTransform>();for(var p:NervOuterCarrierGuideR52.partsAt(RigidTransform.of(Vec3.ZERO,new Quaternionf(0,1,0,0)),1,new Vec3(0,0,-1)))
        {var exported=parts.get(p.name());if(exported==null||!exported.role().equals(p.role())||!Arrays.equals(exported.mesh().triangles(),p.mesh().triangles()))throw new AssertionError("Current actual factory/export mismatch "+p.name());initial.put(p.name(),p.frame());}
        if(parts.size()!=48||initial.size()!=48)throw new AssertionError("All48 actual source members required");
        var raw=JsonParser.parseString(Files.readString(Path.of(files.getAsJsonObject("BANK_HEAD_ACTUAL_SWEEP_FRAMES.json").get("path").getAsString()))).getAsJsonObject();var steps=new ArrayList<Step>();var envelopes=new LinkedHashMap<String,AABB>();
        for(var p:parts.values())envelopes.put(p.name(),p.mesh().envelope(initial.get(p.name()),initial.get(p.name())));
        for(var value:raw.getAsJsonArray("steps")){var r=value.getAsJsonObject();var step=new Step(r.get("part").getAsString(),r.get("reverse").getAsBoolean(),r.get("tick").getAsInt(),frame(r.getAsJsonArray("from")),frame(r.getAsJsonArray("to")),r.get("extra_arc_error_m").getAsDouble());if(!Double.isFinite(step.arc())||step.arc()<0||step.tick()<0||step.tick()>=120)throw new AssertionError("Bounded exported step required");steps.add(step);var b=parts.get(step.part()).mesh().envelope(step.from(),step.to()).inflate(step.arc());envelopes.put(step.part(),envelopes.get(step.part()).minmax(b));}
        if(steps.size()!=8400)throw new AssertionError("Complete actual120tick bidirectional parts required");
        var envRows=new ArrayList<Object>();for(var b:declaration.getAsJsonArray("banks")){var bank=b.getAsJsonObject();var a=bank.getAsJsonObject("root").getAsJsonArray("translation");var translation=new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());var rows=new ArrayList<Object>();for(var p:parts.values())rows.add(Map.of("part",p.name(),"role",p.role(),"bounds",values(envelopes.get(p.name()).move(translation)),"triangles",p.mesh().triangles().length/9));envRows.add(Map.of("bank",bank.get("route").getAsString(),"root_translation",new double[]{translation.x,translation.y,translation.z},"parts",rows));}
        Files.writeString(out.resolve("CURRENT_ALL48_PART_ENVELOPES.json"),GSON.toJson(Map.of("head_source_sha256",NervBankHeadTransferR53.SOURCE_SHA,"interface_sha256",sha(input),"banks",envRows,"world_written",false,"bbox_use","Candidate filtering only; no clearance/permission")));
        var initialRows=new ArrayList<Object>();for(var p:parts.values())initialRows.add(Map.of("part",p.name(),"role",p.role(),"initial_actual_relative_frame",values(initial.get(p.name()))));Files.writeString(out.resolve("CURRENT_ALL48_INITIAL_FRAMES.json"),GSON.toJson(initialRows));
        if(args.length<3){System.out.println("PREPARED all48 current initial poses and8400 continuous intervals");return;}
        var candidates=JsonParser.parseString(Files.readString(Path.of(args[2]))).getAsJsonObject();if(!candidates.get("interface_sha256").getAsString().equals(sha(input)))throw new AssertionError("Measured candidates belong to another interface");double[] offsets=new double[6];for(int i=0;i<6;i++)offsets[i]=candidates.getAsJsonArray("native_shape_local_extrema").get(i).getAsDouble();
        var output=new ArrayList<Object>();
        for(var bv:candidates.getAsJsonArray("banks"))
        {
            var bank=bv.getAsJsonObject();var a=bank.getAsJsonArray("root_translation");var root=new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());var cells=new HashMap<String,Cell>();
            for(var value:bank.getAsJsonArray("cells")){var row=value.getAsJsonObject();var q=row.getAsJsonArray("position");var boxes=new ArrayList<AABB>();for(var b:row.getAsJsonArray("native_boxes"))boxes.add(box(b.getAsJsonArray()));var cell=new Cell(q.get(0).getAsInt(),q.get(1).getAsInt(),q.get(2).getAsInt(),row.get("state").getAsString(),List.copyOf(boxes),row);cells.put(cell.key(),cell);}
            var hits=new LinkedHashMap<String,Hit>();long tests=0;
            for(var part:parts.values())tests+=test(part,add(initial.get(part.name()),root),add(initial.get(part.name()),root),0,null,cells,offsets,hits);
            for(var step:steps)tests+=test(parts.get(step.part()),add(step.from(),root),add(step.to(),root),step.arc(),step,cells,offsets,hits);
            var staticRows=new ArrayList<Object>();var closedRows=new ArrayList<Object>();for(var hit:hits.values()){if(hit.cell.state().equals("minecraft:barrier"))closedRows.add(hit.row());else staticRows.add(hit.row());}
            output.add(Map.of("bank",bank.get("bank").getAsString(),"root_translation",new double[]{root.x,root.y,root.z},"native_candidate_cells",cells.size(),"narrow_phase_tests",tests,"static_part_cell_hits",staticRows,"conditional_closed_barrier_part_cell_hits",closedRows,"unknown_shapes",bank.get("unknown_shapes"),"block_entities_in_scope",bank.get("block_entities_in_scope")));
            System.out.println(bank.get("bank").getAsString()+" nativecells="+cells.size()+" tests="+tests+" static_partcells="+staticRows.size()+" conditional_partcells="+closedRows.size());
        }
        var report=new LinkedHashMap<String,Object>();report.put("world_written",false);report.put("game_started",false);report.put("head_source_sha256",NervBankHeadTransferR53.SOURCE_SHA);report.put("interface_sha256",sha(input));report.put("candidate_readback_sha256",sha(Path.of(args[2])));report.put("banks",output);report.put("source_region_sha256",candidates.get("region_sha256"));report.put("native_shapes_sha256",candidates.get("native_shapes_sha256"));report.put("method","All48 actual triangles, all initial fixed poses, all8400 exported real steps at all9 actual banks. Frames already include yaw180: add root translation only. Production mesh.intersects(from,to,nativeBox.inflate(exportedArcError),.003), with full envelope used only for filtering. Conditional minecraft:barrier hits remain separate. A hit is conservative continuous triangle evidence, never permission to delete a support or change a route.");
        Files.writeString(out.resolve("ACTUAL_NINE_BANK_WORLD_HITS.json"),GSON.toJson(report));
    }
}

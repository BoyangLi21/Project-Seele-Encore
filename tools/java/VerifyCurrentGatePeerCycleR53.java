package com.projectseele.world;
import com.google.gson.*;import java.io.*;import java.nio.file.*;import java.util.*;import java.util.zip.*;import net.minecraft.world.phys.*;

/** Exact current exported production triangle pairs over complete monotone stages. */
public final class VerifyCurrentGatePeerCycleR53
{
    private record Mesh(String name,boolean moving,NervRigidMeshSweepR52 mesh){}
    private static final Gson G=new GsonBuilder().setPrettyPrinting().create();
    private static RigidTransform frame(JsonArray a){return new RigidTransform(new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble()),a.get(3).getAsFloat(),a.get(4).getAsFloat(),a.get(5).getAsFloat(),a.get(6).getAsFloat());}
    private static double[] box(AABB b){return new double[]{b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ};}
    private static List<Mesh> meshes(Path base,JsonObject profile)throws Exception{var result=new ArrayList<Mesh>();try(var s=new DataInputStream(new GZIPInputStream(Files.newInputStream(base.resolve(profile.get("mesh_file").getAsString()))))){int n=s.readInt();for(int i=0;i<n;i++){String name=s.readUTF();boolean moving=s.readBoolean();int size=s.readInt();double[] xyz=new double[size/2];for(int j=0;j<size/6;j++)for(int c=0;c<6;c++){double value=s.readDouble();if(c<3)xyz[j*3+c]=value;}result.add(new Mesh(name,moving,new NervRigidMeshSweepR52(xyz)));}}return result;}
    public static void main(String[] args)throws Exception
    {
        var file=Path.of(args[0]);var source=JsonParser.parseString(Files.readString(file)).getAsJsonObject();var profiles=source.getAsJsonObject("profiles");var gates=new HashMap<String,JsonObject>();for(var g:source.getAsJsonArray("gates"))gates.put(g.getAsJsonObject().get("resource").getAsString(),g.getAsJsonObject());var cache=new HashMap<String,List<Mesh>>();var hits=new ArrayList<Object>();long checked=0,broad=0;
        for(int v=0;v<3;v++)for(boolean pitMoves:new boolean[]{true,false})
        {
            String movingName="bay_"+v+(pitMoves?"_service_pit":"_front"),staticName="bay_"+v+(pitMoves?"_front":"_service_pit");var moving=gates.get(movingName);var still=gates.get(staticName);String mk=moving.get("profile").getAsString(),sk=still.get("profile").getAsString();var mp=profiles.getAsJsonObject(mk);var sp=profiles.getAsJsonObject(sk);if(!cache.containsKey(mk))cache.put(mk,meshes(file.getParent(),mp));if(!cache.containsKey(sk))cache.put(sk,meshes(file.getParent(),sp));var mm=cache.get(mk);var sm=cache.get(sk);var mr=frame(moving.getAsJsonArray("world_root"));var sr=frame(still.getAsJsonArray("world_root"));JsonObject fixedPhase=null;for(var p:sp.getAsJsonArray("phases"))if(p.getAsJsonObject().get("progress").getAsDouble()==(pitMoves?0:1))fixedPhase=p.getAsJsonObject();if(fixedPhase==null)throw new AssertionError("Actual closed/open peer phase absent");var frames=fixedPhase.getAsJsonArray("parts");
            for(var r:mp.getAsJsonArray("continuous_sweeps"))
            {
                var row=r.getAsJsonObject();int pi=row.get("part").getAsInt();var a=mm.get(pi);var af=mr.compose(frame(row.getAsJsonArray("from")));var at=mr.compose(frame(row.getAsJsonArray("to")));var bound=a.mesh().envelope(af,at);
                for(int j=0;j<sm.size();j++){checked++;var b=sm.get(j);var bf=sr.compose(frame(frames.get(j).getAsJsonObject().getAsJsonArray("local_frame")));var other=b.mesh().envelope(bf,bf);if(!bound.intersects(other))continue;broad++;if(a.mesh().intersects(af,at,b.mesh(),bf,bf,.003,Vec3.ZERO))hits.add(Map.of("variant",v,"moving_gate",movingName,"peer_gate",staticName,"part",a.name(),"peer_part",b.name(),"part_is_moving",a.moving(),"peer_part_is_moving",b.moving(),"progress_interval",new double[]{row.get("progress_from").getAsDouble(),row.get("progress_to").getAsDouble()},"broadphase_overlap",box(bound.intersect(other))));}
            }
        }
        var report=Map.of("schema","projectseele.r53.current-gate-peer-sequential-cycle.v1","passed",hits.isEmpty(),"pair_windows",checked,"broadphase_pairs",broad,"hits",hits,"reverse_occupancy_identical",true,"world_written",false,"game_started",false,"source_interface",file.toString(),"source_interface_sha256",HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(file))));Files.writeString(Path.of(args[1]),G.toJson(report));System.out.println("CURRENT_GATE_PEER_CYCLE pairs="+checked+" broad="+broad+" hits="+hits.size());
    }
}

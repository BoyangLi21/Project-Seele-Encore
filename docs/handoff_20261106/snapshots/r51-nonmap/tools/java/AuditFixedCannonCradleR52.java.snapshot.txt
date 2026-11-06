package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import java.io.*;
import java.util.*;
import java.util.zip.GZIPInputStream;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
/** Independent proposal audit. Does not register a renderer/controller or alter a world. */
public final class AuditFixedCannonCradleR52
{
    static Map<String,NervRigidMeshSweepR52> read(Path path)throws Exception
    {var out=new LinkedHashMap<String,NervRigidMeshSweepR52>();try(var stream=new DataInputStream(new GZIPInputStream(Files.newInputStream(path)))){if(stream.readInt()!=0x52353243||stream.readInt()!=1)throw new IllegalArgumentException("Source geometry required");int parts=stream.readInt();for(int i=0;i<parts;i++){String name=stream.readUTF();stream.readUTF();int n=stream.readInt();var v=new double[n*3];for(int j=0;j<v.length;j++)v[j]=stream.readFloat();out.put(name,new NervRigidMeshSweepR52(v));}}return out;}
    public static void main(String[] args)throws Exception
    {
        var c=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var bay=vec(c.getAsJsonArray("raised_position"));
        var frame=RigidTransform.of(bay,new Quaternionf());var body=RigidTransform.of(vec(c.getAsJsonArray("prone_position")),new Quaternionf().rotationY((180-c.get("prone_yaw").getAsFloat())*(float)Math.PI/180));
        var pieces=read(Path.of(args[1]));var skin=read(Path.of(args[2]));var blocked=new ArrayList<String>();
        for(var part:pieces.entrySet())for(var limb:skin.entrySet())if(part.getValue().intersects(frame,frame,limb.getValue(),body,body,.002,Vec3.ZERO))blocked.add(part.getKey()+":"+limb.getKey());
        var geometry=com.projectseele.entity.YashimaCannonGeometryR52.parse(c);var method=YashimaCannonMeshR52.class.getDeclaredMethod("gun",float.class);method.setAccessible(true);var gun=(NervRigidMeshSweepR52)method.invoke(null,geometry.scale());var m=geometry.matrix(bay,new Quaternionf());var gunFrame=RigidTransform.of(new Vec3(m.getTranslation(new org.joml.Vector3f())),m.getUnnormalizedRotation(new Quaternionf()).normalize());var gunCuts=new ArrayList<String>();
        for(var part:pieces.entrySet())if(part.getValue().intersects(frame,frame,gun,gunFrame,gunFrame,.002,Vec3.ZERO))gunCuts.add(part.getKey());
        var result=new LinkedHashMap<String,Object>();result.put("scope","Complete actual skin including both hands and unchanged source gun, paired original source narrow-phase, candidate geometry only");result.put("cradle_body_intersections",blocked);result.put("cradle_gun_surface_intersections",gunCuts);result.put("clear",blocked.isEmpty()&&gunCuts.isEmpty());result.put("pieces",pieces.size());
        var proposal=JsonParser.parseString(Files.readString(Path.of(args[3]).resolveSibling("CRADLE_CANDIDATE.json"))).getAsJsonObject();var contactProbes=new ArrayList<Object>();
        for(int i=0;i<proposal.getAsJsonArray("contacts").size();i++)
        {
            var contact=proposal.getAsJsonArray("contacts").get(i).getAsJsonObject();var normal=vec(contact.getAsJsonArray("normal"));var pad=pieces.get("saddle_"+i);var probes=new LinkedHashMap<String,Boolean>();
            for(double offset:new double[]{0,.0001,.001,.003,.01,.02}){var f=RigidTransform.of(bay.add(normal.scale(offset)),new Quaternionf());probes.put(Double.toString(offset),pad.intersects(f,f,gun,gunFrame,gunFrame,.002,Vec3.ZERO));}
            contactProbes.add(Map.of("source_triangle",contact.get("source_triangle").getAsInt(),"outward_shift_m_to_surface_intersection",probes));
        }
        result.put("saddle_contact_shift_probes",contactProbes);
        if(args.length>4)
        {
            var hatch=JsonParser.parseString(Files.readString(Path.of(args[4]))).getAsJsonObject().getAsJsonObject("cannon_hatch");var doorFrame=RigidTransform.of(vec(hatch.getAsJsonArray("position")),new Quaternionf());
            var doors=NervSiloHatchGeometryR52.loadClasspath(new com.projectseele.entity.SiloHatchMechanism.Spec(hatch.get("width").getAsFloat(),hatch.get("height").getAsFloat(),80,80,1,-2.02,false));var cuts=new ArrayList<String>();var bounds=new ArrayList<Object>();var draws=new LinkedHashMap<String,double[]>();var physicalDoors=new LinkedHashMap<String,NervRigidMeshSweepR52>();int partIndex=0;
            for(var part:doors.pieces(1))
            {
                var mesh=new NervRigidMeshSweepR52(part.part().xyz());var f=doorFrame.compose(part.local());String name=part.part().name()+"/"+(partIndex++);var b=mesh.envelope(f,f);bounds.add(Map.of("part",name,"world_bounds",List.of(b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ)));
                for(var limb:skin.entrySet())if(mesh.intersects(f,f,limb.getValue(),body,body,.002,Vec3.ZERO))cuts.add(name+":"+limb.getKey());
                var v=mesh.triangles();for(int n=0;n<v.length;n+=3){var p=f.transformPoint(new Vec3(v[n],v[n+1],v[n+2])).subtract(bay);v[n]=p.x;v[n+1]=p.y;v[n+2]=p.z;}draws.put(name,v);physicalDoors.put(name,new NervRigidMeshSweepR52(v));
            }
            result.put("fully_open_hatch_body_intersections",cuts);result.put("fully_open_hatch_parts",bounds);write(Path.of(args[3]).resolveSibling("hatch_fully_open.bin.gz"),draws);
            var closed=read(Path.of(args[1]).resolveSibling("cradle_closed.bin.gz"));var liftDoorCuts=new ArrayList<String>();var liftBodyCuts=new ArrayList<String>();double maximumAffineError=0;
            for(var part:pieces.entrySet())
            {
                var a=closed.get(part.getKey());var av=a.triangles();var bv=part.getValue().triangles();var delta=new Vec3(bv[0]-av[0],bv[1]-av[1],bv[2]-av[2]);
                for(int n=0;n<av.length;n+=3)maximumAffineError=Math.max(maximumAffineError,new Vec3(bv[n]-av[n],bv[n+1]-av[n+1],bv[n+2]-av[n+2]).distanceTo(delta));var end=RigidTransform.of(bay.add(delta),new Quaternionf());
                for(var d:physicalDoors.entrySet())if(a.intersects(frame,end,d.getValue(),frame,frame,.002,new Vec3(.00001,.00001,.00001)))liftDoorCuts.add(part.getKey()+":"+d.getKey());
                for(var limb:skin.entrySet())if(a.intersects(frame,end,limb.getValue(),body,body,.002,new Vec3(.00001,.00001,.00001)))liftBodyCuts.add(part.getKey()+":"+limb.getKey());
            }
            var lowerGun=RigidTransform.of(new Vec3(m.getTranslation(new org.joml.Vector3f())).add(0,-16.5,0),new Quaternionf(gunFrame.qx(),gunFrame.qy(),gunFrame.qz(),gunFrame.qw()));var liftGunDoorCuts=new ArrayList<String>();for(var d:physicalDoors.entrySet())if(gun.intersects(lowerGun,gunFrame,d.getValue(),frame,frame,.002,Vec3.ZERO))liftGunDoorCuts.add(d.getKey());
            result.put("cradle_full_lift_vs_open_hatch_intersections",liftDoorCuts);result.put("cradle_full_lift_vs_approved_prone_intersections",liftBodyCuts);result.put("gun_full_lift_vs_open_hatch_intersections",liftGunDoorCuts);result.put("maximum_affine_lift_float_error_m",maximumAffineError);
        }
        Files.writeString(Path.of(args[3]),new GsonBuilder().setPrettyPrinting().create().toJson(result));System.out.println(new Gson().toJson(result));
    }
    static void write(Path path,Map<String,double[]> parts)throws Exception{try(var stream=new DataOutputStream(new java.util.zip.GZIPOutputStream(Files.newOutputStream(path)))){stream.writeInt(0x52353243);stream.writeInt(1);stream.writeInt(parts.size());for(var p:parts.entrySet()){stream.writeUTF(p.getKey());stream.writeUTF("actual-original-door-source");stream.writeInt(p.getValue().length/3);for(double v:p.getValue())stream.writeFloat((float)v);}}}
    static Vec3 vec(JsonArray a){return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
}

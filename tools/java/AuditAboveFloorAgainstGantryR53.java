package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Original complete structural gantry at its authored open/closed states, no actors/world modified. */
public final class AuditAboveFloorAgainstGantryR53
{
    private static Object read(Object object,String name)throws Exception{var m=object.getClass().getDeclaredMethod(name);m.setAccessible(true);return m.invoke(object);}
    @SuppressWarnings("unchecked")
    public static List<NervLegacyCarrierRideR52.Piece> gantry(int variant,float closed,double lower,double calibration)throws Exception
    {
        var root=new RigidTransform(new Vec3(0,-.96,0),0,0,0,1);var result=new ArrayList<NervLegacyCarrierRideR52.Piece>();
        for(var p:NervLowerFrameR52.pieces(lower))result.add(new NervLegacyCarrierRideR52.Piece(p.name(),p.mesh(),p.rgb(),root.compose(p.local()),p.kind()));
        var cf=NervPlantMotionR52.class.getDeclaredField("components");cf.setAccessible(true);var mf=NervPlantMotionR52.class.getDeclaredField("renderMeshes");mf.setAccessible(true);var meshes=(Map<String,NervRigidMeshSweepR52>)mf.get(null);
        for(var c:(List<?>)cf.get(null))
        {
            String name=(String)read(c,"part");int v=(Integer)read(c,"variant");if(name.equals("cage_frame_lower_r44")||v>=0&&v!=variant)continue;
            var move=NervPlantMotionR52.class.getDeclaredMethod("move",c.getClass(),float.class);move.setAccessible(true);var d=(Vec3)move.invoke(null,c,closed);if(read(c,"motion").equals("translation_only_with_exact_facet_pad"))d=d.add(0,calibration,0);result.add(new NervLegacyCarrierRideR52.Piece(name,meshes.get(name),new double[0],root.compose(new RigidTransform(d,0,0,0,1)),"original_gantry"));
        }
        var shoulder=new ArrayList<NervFlightProofR52.ObstacleMesh>();var mesh=NervShoulderBearingR52.class.getDeclaredMethod("mesh",String.class,RigidTransform.class,double.class);mesh.setAccessible(true);
        for(var p:NervShoulderBearingR52.pads())if(p.variant()==variant)
        {
            var move=NervShoulderBearingR52.movement(p,1-closed).add(0,calibration,0);shoulder.add((NervFlightProofR52.ObstacleMesh)mesh.invoke(null,p.part(),root.compose(new RigidTransform(move,0,0,0,1)),1D));
            for(int i=0;i<2;i++)
            {
                var anchor=p.anchors().get(i);var end=p.links().get(i).add(move);var delta=end.subtract(anchor);double length=delta.length();
                if(length<=2.22)throw new IllegalStateException("Original barrel exhausted");
                var turn=new org.joml.Quaternionf().rotationTo(0,0,1,(float)(delta.x/length),(float)(delta.y/length),(float)(delta.z/length));var f=root.compose(RigidTransform.of(anchor,turn));
                shoulder.add((NervFlightProofR52.ObstacleMesh)mesh.invoke(null,"shoulder_joint",f,1D));
                shoulder.add((NervFlightProofR52.ObstacleMesh)mesh.invoke(null,"shoulder_barrel",f,1D));
                shoulder.add((NervFlightProofR52.ObstacleMesh)mesh.invoke(null,"shoulder_piston_unit",f.compose(new RigidTransform(new Vec3(0,0,2.18),0,0,0,1)),length-2.18));
                // Pad-side lug remains fixed to that pad; the original piston rotates into its centre.
                var n=p.normal();var endTurn=calibration==0?turn:new org.joml.Quaternionf().rotationTo(0,0,1,(float)n.x,(float)n.y,(float)n.z);
                shoulder.add((NervFlightProofR52.ObstacleMesh)mesh.invoke(null,"shoulder_joint",root.compose(RigidTransform.of(end,endTurn)),1D));
            }
        }
        int i=0;for(var p:shoulder)result.add(new NervLegacyCarrierRideR52.Piece("shoulder_bearing/"+i++,p.mesh(),new double[0],p.frame(),"original_shoulder"));return List.copyOf(result);
    }
    private static boolean intersects(NervLegacyCarrierRideR52.Piece a,NervLegacyCarrierRideR52.Piece b)
    {return a.mesh().envelope(a.frame(),a.frame()).intersects(b.mesh().envelope(b.frame(),b.frame()))&&a.mesh().intersects(a.frame(),a.frame(),b.mesh(),b.frame(),b.frame(),.003,Vec3.ZERO);}
    public static void main(String[] args)throws Exception
    {
        var candidate=new CandidateRearLateralProfileR53(CarrierRearGuideR53.readHardware(Files.readAllBytes(Path.of(args[0])),"uninstalled-lateral"));NervPlantMotionR52.install("3b2ea3f2ee5742a56e5ad9c6c5a83d0262b0148dd6e23bc438c72407ad44e1d9");var outputs=new ArrayList<Object>();
        for(int v=0;v<3;v++)
        {
            var json=JsonParser.parseString(Files.readString(Path.of(args[1]).resolve("unit0"+v+".json"))).getAsJsonObject();var eva=new LinkedHashMap<String,NervRigidMeshSweepR52>();
            for(var entry:json.getAsJsonObject("parts").entrySet()){var a=entry.getValue().getAsJsonArray();double[] xyz=new double[a.size()];for(int i=0;i<xyz.length;i++)xyz[i]=a.get(i).getAsDouble();eva.put(entry.getKey(),new NervRigidMeshSweepR52(xyz));}
            for(float closed:new float[]{0,.25F,.5F,.75F,1})for(double load:new double[]{0,4.25})for(double calibration:new double[]{0,4.25})
            {
                if(load==0&&calibration!=0)continue;
                var actor=gantry(v,closed,0,calibration);var assembly=new ArrayList<NervLegacyCarrierRideR52.Piece>();var f=new RigidTransform(new Vec3(0,load,0),0,0,0,1);float carrierRise=.9F+.1F*(1-closed);
                eva.forEach((name,mesh)->assembly.add(new NervLegacyCarrierRideR52.Piece("eva/"+name,mesh,new double[0],f,"eva")));
                CarrierAssemblyR53.selected().parts().forEach((name,surface)->assembly.add(new NervLegacyCarrierRideR52.Piece("carrier/"+name,new NervRigidMeshSweepR52(surface.positions()),new double[0],f.compose(CarrierAssemblyR53.selected().frame(name,carrierRise,0,0)),"carrier")));
                if(load>0)assembly.addAll(candidate.partsAt(RigidTransform.identity(),carrierRise,new Vec3(0,0,1),0,7,1));
                var hits=new ArrayList<Object>();for(var p:assembly)for(var q:actor)if(intersects(p,q))hits.add(Map.of("moving",p.name(),"gantry",q.name()));
                outputs.add(Map.of("variant",v,"closed",closed,"lower",0,"load",load,"shoulder_calibration",calibration,"carrier_rise",carrierRise,"gantry_parts",actor.size(),"load_parts",assembly.size(),"hits",hits));System.out.println("variant="+v+" closed="+closed+" load="+load+" calibration="+calibration+" hits="+hits.size());
            }
        }
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("world_written",false,"installed",false,"scope","Source open/closed fixtures at declared bay frame, not actual live state or continuous opening proof; designed original pad contacts are reported, not waived.","cases",outputs)));
    }
}

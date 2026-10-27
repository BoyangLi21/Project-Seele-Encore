package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Immutable selected geometry only; no entity, task or world mutation. */
public final class AuditRearBankGeometryR53
{
    private record Bank(String leg,RigidTransform root,Vec3 up){}
    private static Vec3 point(JsonArray p)
    {return new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble());}
    public static void main(String[] args)throws Exception
    {
        var hardware=Objects.requireNonNull(CarrierRearGuideR53.selected());
        var rails=Objects.requireNonNull(CarrierRearGuideR53.fixed());
        var banks=new ArrayList<Bank>();
        if(args.length>1)
        {
            var source=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();
            if(!rails.directory().equals(source.get("directory").getAsString()))throw new IllegalArgumentException("Actual directory changed");
            for(var raw:source.getAsJsonArray("legs"))
            {
                var leg=raw.getAsJsonObject();String id=leg.get("leg").getAsString();if(!id.contains("/exit"))continue;
                var first=leg.getAsJsonArray("samples").get(0).getAsJsonObject();var q=first.getAsJsonArray("rotation");
                banks.add(new Bank(id,new RigidTransform(point(first.getAsJsonArray("root")),q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat()),point(first.getAsJsonArray("tangent"))));
            }
        }
        else banks.add(new Bank("unit1/exit1/upright_continuous",new RigidTransform(new Vec3(30.5,-1030,124.5),0,1,0,0),new Vec3(0,1,0)));
        if(banks.isEmpty())throw new IllegalArgumentException("Measured bank required");
        var failures=new ArrayList<Object>();int tests=0,contacts=0,intervals=0;boolean capture=true;
        for(var bank:banks)
        {
        var root=bank.root();String leg=bank.leg();
        var body=new ArrayList<NervLegacyCarrierRideR52.Piece>();
        CarrierAssemblyR53.selected().posed(1,0,0).forEach((name,xyz)->body.add(
            new NervLegacyCarrierRideR52.Piece(name,new NervRigidMeshSweepR52(xyz),new double[0],root,"body")));
        capture&=CarrierRearGuideR53.finiteBankCapture(root,bank.up(),leg);
        for(boolean returning:new boolean[]{false,true})
        {
        var state=new net.minecraft.nbt.CompoundTag();state.putBoolean("RearToTransferR53",returning);
        var transfer=root.transformVector(new Vec3(0,0,1));
        for(int clock=0;clock<120;clock++)
        {
            intervals++;
            var a=NervBankHeadTransferR53.sample(returning?bank.up():transfer,returning?transfer:bank.up(),clock);
            var b=NervBankHeadTransferR53.sample(returning?bank.up():transfer,returning?transfer:bank.up(),clock+1);
            var A=hardware.partsAt(root,1,a.direction(),a.slide(),CarrierRearGuideR53.bankLift(state,clock));
            var B=hardware.partsAt(root,1,b.direction(),b.slide(),CarrierRearGuideR53.bankLift(state,clock+1));
            double angle=Math.acos(Math.max(-1,Math.min(1,a.direction().dot(b.direction()))));
            double error=angle==0?0:(.35+Math.abs(a.slide()))*angle*angle/8+2e-6;
            for(int i=0;i<A.size();i++)
            {
                var p=A.get(i);var q=B.get(i);if(p.frame().equals(q.frame()))continue;
                var bounds=p.mesh().envelope(p.frame(),q.frame()).inflate(error);
                for(var fixed:body)
                {
                    if(!bounds.intersects(fixed.mesh().envelope(fixed.frame(),fixed.frame())))continue;
                    tests++;
                    if(p.mesh().intersects(p.frame(),q.frame(),fixed.mesh(),fixed.frame(),fixed.frame(),.003,new Vec3(error,error,error)))
                        failures.add(Map.of("leg",leg,"returning",returning,"clock",clock,"moving",p.name(),"fixed",fixed.name(),"kind","body"));
                }
                for(var fixed:rails.index().query(bounds))
                {
                    var f=fixed.steel();tests++;
                    if(p.mesh().intersects(p.frame(),q.frame(),f.mesh(),f.frame(),f.frame(),.003,new Vec3(error,error,error)))
                    {
                        boolean contact=CarrierRearGuideR53.namedContact(p,q,fixed,leg,error);
                        if(contact)contacts++;
                        else failures.add(Map.of("leg",leg,"returning",returning,"clock",clock,"moving",p.name(),"fixed",fixed.name(),"kind","fixed rail"));
                    }
                }
            }
        }
        }
        System.out.println(leg+" intervals="+intervals+" rejected="+failures.size());
        }
        var result=Map.of("schema","projectseele.r53.rear-bank-geometry-audit.v2","world_written",false,
            "intervals",intervals,"pair_tests",tests,"candidate_contact_pairs",contacts,
            "finite_bank_capture",capture,"failures",failures);
        Files.writeString(Path.of(args[0]),new Gson().toJson(result));
        System.out.println("capture="+capture+" tests="+tests+" rejected="+failures.size());
    }
}

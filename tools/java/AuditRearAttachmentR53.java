package com.projectseele.world;

import com.google.gson.Gson;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Check additions against the imported carrier, without moving any world actor. */
public final class AuditRearAttachmentR53
{
    public static void main(String[] args)throws Exception
    {
        var hardware=CarrierRearGuideR53.readHardware(Files.readAllBytes(Path.of(args[0])),"uninstalled-diagnostic");
        var root=new RigidTransform(Vec3.ZERO,0,0,0,1);
        var body=new LinkedHashMap<String,NervRigidMeshSweepR52>();
        CarrierAssemblyR53.selected().posed(1,0,0).forEach((name,xyz)->body.put(name,new NervRigidMeshSweepR52(xyz)));
        var failures=new ArrayList<Object>();int tests=0;
        var state=new net.minecraft.nbt.CompoundTag();state.putBoolean("RearToTransferR53",false);
        for(int clock=0;clock<=120;clock++)
        {
            var pose=NervBankHeadTransferR53.sample(new Vec3(0,0,1),new Vec3(0,1,0),clock);
            for(var part:hardware.partsAt(root,1,pose.direction(),pose.slide(),CarrierRearGuideR53.bankLift(state,clock)))
            {
                if(part.role().equals("source_weld"))continue;
                if(clock>0&&part.frame().equals(root))continue;
                for(var entry:body.entrySet())
                {
                    var mesh=entry.getValue();
                    if(!part.mesh().envelope(part.frame(),part.frame()).intersects(mesh.envelope(root,root)))continue;
                    tests++;
                    if(part.mesh().intersects(part.frame(),part.frame(),mesh,root,root,.001,Vec3.ZERO))
                        failures.add(Map.of("clock",clock,"rear",part.name(),"body",entry.getKey()));
                }
            }
        }
        Files.writeString(Path.of(args[1]),new Gson().toJson(Map.of("world_written",false,"tests",tests,"failures",failures)));
        System.out.println("tests="+tests+" failures="+failures.size());
    }
}

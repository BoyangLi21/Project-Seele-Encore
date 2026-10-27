package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Read-only actual-source bound audit. Does not certify physical clearance. */
public final class AuditRearCurveBudgetR53
{
    private static String sha(byte[] bytes)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}
    private static double queryError(DirectoryTrajectoryR52 path,CarrierRearGuideR53.Hardware hardware,CarrierRearGuideMotionR53.ContinuousBudget budget)
    {
        double max=budget.error();
        for(int k=0;k<budget.divisions();k++)
        {
            double a=k/(double)budget.divisions(),b=(k+1D)/budget.divisions();
            var from=hardware.partsAt(path.sample(a).evaRoot(),1,NervOuterCarrierGuideR52.direction(path,a),0,4.5);
            var to=hardware.partsAt(path.sample(b).evaRoot(),1,NervOuterCarrierGuideR52.direction(path,b),0,4.5);
            double surrogate=0;
            for(int i=0;i<from.size();i++)
            {
                var part=from.get(i);double angle=Math.toRadians(part.frame().rotationErrorDegrees(to.get(i).frame()));
                surrogate=Math.max(surrogate,NervRigidMeshSweepR52.radius(part.mesh().bounds())*angle*angle/8);
            }
            max=Math.max(max,budget.error()+surrogate);
        }
        return max;
    }
    public static void main(String[] args)throws Exception
    {
        if(args.length!=3)throw new IllegalArgumentException("actual-directory hardware output");
        var directoryBytes=Files.readAllBytes(Path.of(args[0]));var directory=NervRouteDirectoryR52.parse(JsonParser.parseString(new String(directoryBytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject());
        var hardwareBytes=Files.readAllBytes(Path.of(args[1]));var hardware=CarrierRearGuideR53.readHardware(hardwareBytes,"actual-candidate-bound-audit");
        var binding=new FootSupportFrameR52.Binding(new Vec3(-1,0,0),new Vec3(1,0,0),RigidTransform.identity());
        var ids=new TreeSet<String>();for(var route:directory.routes().values())ids.addAll(route.legs());var rows=new ArrayList<Object>();var failures=new ArrayList<Object>();
        double maxSampling=0,maxRounding=0,maxError=0,maxQueryError=0;int windows=0,legacyRejected=0,maxDivisions=0;
        for(String id:ids)
        {
            var leg=directory.leg(id);double length=directory.legLength(leg),sampling=directory.translationSamplingError(leg);
            int oldReject=0,divisions=0;double maxLegError=0,maxLegQueryError=0;String wholeLeg="";
            try{wholeLeg=Integer.toString(CarrierRearGuideMotionR53.continuousBudget(new DirectoryTrajectoryR52(directory,leg,binding,0,1),hardware).divisions());}
            catch(IllegalArgumentException rejected){wholeLeg=rejected.getMessage();}
            for(double at=0;at<length;)
            {
                double end=Math.min(length,at+16),a=directory.legFractionAtDistance(leg,at),b=directory.legFractionAtDistance(leg,end);
                try
                {
                    var path=new DirectoryTrajectoryR52(directory,leg,binding,a,b);var budget=CarrierRearGuideMotionR53.continuousBudget(path,hardware);
                    windows++;if(sampling+.00002>=.00005){legacyRejected++;oldReject++;}
                    divisions=Math.max(divisions,budget.divisions());maxLegError=Math.max(maxLegError,budget.error());maxRounding=Math.max(maxRounding,budget.rounding());
                    if(budget.error()<sampling+.00002||budget.chord()>.00003)throw new AssertionError("Outward error not retained");
                    maxLegQueryError=Math.max(maxLegQueryError,queryError(path,hardware,budget));
                }
                catch(IllegalArgumentException failure){failures.add(Map.of("leg",id,"from_m",at,"to_m",end,"rejection",failure.getMessage()));}
                at=end;
            }
            var first=new DirectoryTrajectoryR52(directory,leg,binding,0,directory.legFractionAtDistance(leg,Math.min(length,.04)));var firstBudget=CarrierRearGuideMotionR53.continuousBudget(first,hardware);
            rows.add(Map.of("leg",id,"length_m",length,"sampling_m",sampling,"legacy_rounding_rejected_windows",oldReject,"whole_leg_divisions_or_rejection",wholeLeg,"max_16m_divisions",divisions,"max_16m_bound_m",maxLegError,"max_16m_bound_with_slerp_m",maxLegQueryError,"first_004m",Map.of("divisions",firstBudget.divisions(),"rounding_m",firstBudget.rounding(),"chord_m",firstBudget.chord(),"bound_m",firstBudget.error(),"bound_with_slerp_m",queryError(first,hardware,firstBudget))));
            maxSampling=Math.max(maxSampling,sampling);maxError=Math.max(maxError,maxLegError);maxQueryError=Math.max(maxQueryError,maxLegQueryError);maxDivisions=Math.max(maxDivisions,divisions);
        }
        var report=new LinkedHashMap<String,Object>();report.put("schema","projectseele.r53.rear-curve-budget-audit.v1");report.put("world_written",false);report.put("native_clearance",false);report.put("directory",directory.fingerprint());report.put("directory_sha256",sha(directoryBytes));report.put("hardware_sha256",sha(hardwareBytes));report.put("legs",rows);report.put("windows",windows);report.put("legacy_rounding_rejected_windows",legacyRejected);report.put("max_sampling_m",maxSampling);report.put("max_rounding_m",maxRounding);report.put("max_bound_m",maxError);report.put("max_bound_with_slerp_m",maxQueryError);report.put("max_divisions",maxDivisions);report.put("failures",failures);
        Files.writeString(Path.of(args[2]),new Gson().toJson(report));
        System.out.println("legs="+ids.size()+" windows="+windows+" old_rounding_rejected="+legacyRejected+" max_sampling="+maxSampling+" max_total_with_slerp="+maxQueryError+" max_divisions="+maxDivisions+" failures="+failures.size());
    }
    private AuditRearCurveBudgetR53(){}
}

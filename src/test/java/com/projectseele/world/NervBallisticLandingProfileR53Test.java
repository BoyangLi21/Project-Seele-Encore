package com.projectseele.world;
import com.projectseele.entity.EvaDorsalMechanism;import net.minecraft.world.phys.AABB;

/** Native recurrence, actual destination delta and loaded-column boundaries. */
public final class NervBallisticLandingProfileR53Test
{
    private static int checks;
    private static void require(boolean value,String message){checks++;if(!value)throw new AssertionError(message);}
    public static void main(String[] args)throws Exception
    {
        net.minecraft.SharedConstants.tryDetectVersion();var boot=net.minecraft.server.Bootstrap.class.getDeclaredField("isBootstrapped");boot.setAccessible(true);boot.setBoolean(null,true);net.minecraft.core.registries.BuiltInRegistries.bootStrap();
        for(double gravity:new double[]{.08,.1,.42,.8})for(double landing:new double[]{0,-3})
        {
            var profile=new NervBallisticHandoffR52.Profile(landing);double velocity=NervBallisticHandoffR52.launchVelocity(gravity,profile),y=0,max=0;int top=0;
            for(int tick=1;tick<=42;tick++){y+=velocity;velocity=(velocity-gravity)*.98;require(Math.abs(y-NervBallisticHandoffR52.height(tick,gravity,profile))<1e-9,"Real native gravity/drag recurrence differs");if(y>max){max=y;top=tick;}}
            require(Math.abs(y-landing)<1e-9,"Actual exit floor differs at42 ticks");require(velocity<0,"Real landing must retain downward native motion before contact");require(NervBallisticHandoffR52.height(40,gravity,profile)>landing,"Hatch must close before actual landing");
            if(gravity==.42)System.out.println("actual_default_gravity=.42 landing_delta="+landing+" initial_mps="+(20*NervBallisticHandoffR52.launchVelocity(gravity,profile))+" apex_m="+max+" apex_tick="+top+" post42_downward_mps="+(velocity*20));
        }
        require(Math.abs(NervBallisticHandoffR52.launchVelocity(.42)-9.540150570661627)<1e-10,"Legacy minus3 initial velocity changed");
        for(int sub=0;sub<=160;sub++){double fraction=sub/160D,p=NervBallisticHandoffR52.closingProgressR53(fraction);require(p==EvaDorsalMechanism.smooth((float)(1-fraction)),"Hatch proof and actual quintic clock differ");require(p>=0&&p<=1,"Actual hatch sub-tick progress left bounded source");}
        require(NervBallisticHandoffR52.loadedColumnsR53(new AABB(0,175,0,31,345,31),-1344,(x,z)->true),"Real above-build-height sky must remain measurable in loaded columns");
        require(!NervBallisticHandoffR52.loadedColumnsR53(new AABB(0,175,0,31,345,31),-1344,(x,z)->x!=1||z!=1),"Missing real chunk cannot become sky air");
        require(!NervBallisticHandoffR52.loadedColumnsR53(new AABB(0,-1345,0,1,1,1),-1344,(x,z)->true),"Below-foundation source remains rejected");
        for(double bad:new double[]{1,-4,Double.NaN,Double.POSITIVE_INFINITY}){boolean rejected=false;try{new NervBallisticHandoffR52.Profile(bad);}catch(IllegalArgumentException expected){rejected=true;}require(rejected,"Undeclared landing profile accepted");}
        if(args.length==2)
        {
            var directory=NervRouteDirectoryR52.parse(com.google.gson.JsonParser.parseString(java.nio.file.Files.readString(java.nio.file.Path.of(args[0]))).getAsJsonObject());var gates=com.google.gson.JsonParser.parseString(java.nio.file.Files.readString(java.nio.file.Path.of(args[1]))).getAsJsonObject().getAsJsonArray("gates");var selected=new java.util.HashMap<String,com.google.gson.JsonObject>();for(var raw:gates){var gate=raw.getAsJsonObject();selected.put(gate.get("resource").getAsString(),gate);}
            for(var route:directory.routes().values())if(!route.recovery())
            {
                String name="bank_"+route.bank()+"_surface_lane_"+route.lane();require(name.equals(NervAssemblyOwnerR52.deploymentGateResourceR53(directory,route.port(),selected.keySet())),"Actual port lost its explicit exit gate");require(NervAssemblyOwnerR52.deploymentGateResourceR53(directory,route.port(),java.util.Set.of("bank_"+route.bank()+"_upper_lane_"+route.lane()))==null,"Upper gate was mistaken for deployment hatch");var gate=selected.get(name);require(gate.getAsJsonObject("silo_hatch").get("close_ticks").getAsInt()==20,"Actual exit requires fast20 closing clock");double stop=directory.node(directory.ports().get(route.port()).node()).footFrame().translation().y,top=gate.getAsJsonObject("frame").getAsJsonArray("position").get(1).getAsDouble()+.98;var p=new NervBallisticHandoffR52.Profile(top-stop);require(p.landingDelta()==(route.bank()==2?-3:0),"Actual new exit floor offset differs");
            }
        }
        System.out.println("R53 actual landing profile PASS checks="+checks+"; no World/game/native acceptance");
    }
}

package com.projectseele.world;

import com.google.gson.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;
import com.projectseele.world.NervRouteDirectoryR52.*;
import com.projectseele.world.NervRouteReservationsR52.*;

/** Synthetic graph/test-space only. No Root map coordinates, real devices, actors or world. */
public final class NervRouteCoreR52Test
{
    private static int checks;
    private static void check(boolean passed,String reason){checks++;if(!passed)throw new AssertionError(reason);}
    private static void rejects(Runnable operation,String reason){boolean failed=false;try{operation.run();}catch(RuntimeException expected){failed=true;}check(failed,reason);}
    private static UUID uuid(int id){return new UUID(0,id);}
    private static JsonArray names(String... values){var a=new JsonArray();for(String v:values)a.add(v);return a;}
    private static JsonArray numbers(double... values){var a=new JsonArray();for(double v:values)a.add(v);return a;}
    private static JsonObject find(JsonArray array,String id)
    {for(var element:array){var row=element.getAsJsonObject();if(row.get("id").getAsString().equals(id))return row;}throw new AssertionError(id);}
    private static void node(JsonObject root,String id,Role role,int bank,int lane,int variant,double x,double y,double z)
    {
        var n=new JsonObject();n.addProperty("id",id);n.addProperty("dimension","test:synthetic_route_graph");n.addProperty("role",role.name());
        if(role==Role.BANK){n.addProperty("bank",bank);n.addProperty("lane",lane);}if(role==Role.BAY)n.addProperty("variant",variant);
        var f=new JsonObject();f.add("translation",numbers(x,y,z));f.add("quaternion_xyzw",numbers(0,0,0,1));n.add("foot_frame",f);root.getAsJsonArray("nodes").add(n);
    }
    private static void resource(JsonObject root,String id,ResourceKind kind)
    {var r=new JsonObject();r.addProperty("id",id);r.addProperty("kind",kind.name());r.addProperty("component","synthetic_component/"+id);root.getAsJsonArray("resources").add(r);}
    private static String leg(JsonObject root,String id,String from,String to,Motion motion,String occupied)
    {
        var l=new JsonObject();l.addProperty("id",id);l.addProperty("from",from);l.addProperty("to",to);l.addProperty("motion",motion.name());l.addProperty("ticks",10);
        l.add("eva_from_xyzw",numbers(0,0,0,1));l.add("eva_to_xyzw",numbers(0,0,0,1));l.add("rails",names("rail_"+id));resource(root,"rail_"+id,ResourceKind.RAIL);
        if(motion==Motion.TRACKED_BANK_TRANSFER){l.add("doors",names("gate_"+id));resource(root,"gate_"+id,ResourceKind.DOOR);}else l.add("doors",names());
        l.addProperty("support","support_"+id);resource(root,"support_"+id,ResourceKind.SUPPORT);l.add("occupancy",names(occupied));root.getAsJsonArray("legs").add(l);return id;
    }
    private static JsonObject route(String id,int variant,int bank,int lane,String port,String reverse,List<String> path)
    {
        var r=new JsonObject();r.addProperty("id",id);r.addProperty("variant",variant);r.addProperty("bank",bank);r.addProperty("lane",lane);r.addProperty("region",bank==2?"GEOFRONT":"SURFACE");r.addProperty("port",port);
        if(!reverse.isEmpty())r.addProperty("reverse_of",reverse);r.add("legs",names(path.toArray(String[]::new)));return r;
    }
    private static JsonObject fixture(boolean installed,boolean sharedSpace)
    {return fixture(installed,sharedSpace,new int[]{0,1,2});}
    private static JsonObject fixture(boolean installed,boolean sharedSpace,int[] unitToLane)
    {
        var r=new JsonObject();r.addProperty("schema",NervRouteDirectoryR52.SCHEMA);r.addProperty("map_author","root");r.addProperty("status",installed?"installed":"design");r.addProperty("epoch",7);
        if(installed)r.addProperty("installation_receipt_sha256","f".repeat(64));for(String key:List.of("units","nodes","resources","legs","routes","ports"))r.add(key,new JsonArray());
        if(sharedSpace)resource(r,"shared",ResourceKind.SPACE);
        for(int variant=0;variant<3;variant++)
        {
            int physicalLane=unitToLane[variant],lane=physicalLane+1;double x=lane*10;
            var u=new JsonObject();u.addProperty("variant",variant);u.addProperty("lane",physicalLane);u.addProperty("eva",uuid(10+variant).toString());u.addProperty("plug",uuid(20+variant).toString());r.getAsJsonArray("units").add(u);
            node(r,"bay"+lane,Role.BAY,0,0,variant,x,0,0);
            for(int bank=1;bank<=3;bank++)node(r,"dock"+bank+"_"+lane,Role.BANK,bank,physicalLane,-1,x,1,bank*10);
            String space=sharedSpace&&variant<2?"shared":"space"+lane;if(!space.equals("shared"))resource(r,space,ResourceKind.SPACE);
            String initial=leg(r,"original"+lane,"bay"+lane,"dock1_"+lane,Motion.ORIGINAL_UPRIGHT_TRANSFER,space);
            String bridge12=leg(r,"bridge12_"+lane,"dock1_"+lane,"dock2_"+lane,Motion.TRACKED_BANK_TRANSFER,space);
            String bridge23=leg(r,"bridge23_"+lane,"dock2_"+lane,"dock3_"+lane,Motion.TRACKED_BANK_TRANSFER,space);
            for(int bank=1;bank<=3;bank++)
            {
                String base="b"+bank+"l"+lane,exit="exit_"+base,port="port_"+base;
                var path=new ArrayList<String>();path.add(initial);if(bank>=2)path.add(bridge12);if(bank==3)path.add(bridge23);
                if(bank==2){node(r,exit,Role.EXIT,0,0,-1,x,4,20);path.add(leg(r,"vertical_"+base,"dock2_"+lane,exit,Motion.VERTICAL,space));}
                else
                {
                    String shortTop="short_"+base,inclineTop="incline_"+base;node(r,shortTop,Role.PATH,0,0,-1,x,2,bank*10);node(r,inclineTop,Role.PATH,0,0,-1,x,3,bank*10+1);node(r,exit,Role.EXIT,0,0,-1,x,4,bank*10+1);
                    path.add(leg(r,"short_vertical_"+base,"dock"+bank+"_"+lane,shortTop,Motion.VERTICAL,space));path.add(leg(r,"incline_"+base,shortTop,inclineTop,Motion.LAUNCH_INCLINE,space));path.add(leg(r,"surface_vertical_"+base,inclineTop,exit,Motion.VERTICAL,space));
                }
                String depart="depart_"+base,back="return_"+base;r.getAsJsonArray("routes").add(route(depart,variant,bank,physicalLane,port,"",path));
                var reverse=new ArrayList<String>();for(int i=path.size()-1;i>=0;i--)
                {
                    var forward=find(r.getAsJsonArray("legs"),path.get(i));String id="reverse_"+path.get(i);
                    boolean exists=false;for(var old:r.getAsJsonArray("legs"))if(old.getAsJsonObject().get("id").getAsString().equals(id))exists=true;
                    if(!exists){var v=forward.deepCopy();v.addProperty("id",id);v.addProperty("from",forward.get("to").getAsString());v.addProperty("to",forward.get("from").getAsString());r.getAsJsonArray("legs").add(v);}reverse.add(id);
                }
                r.getAsJsonArray("routes").add(route(back,variant,bank,physicalLane,port,depart,reverse));var p=new JsonObject();p.addProperty("id",port);p.addProperty("region",bank==2?"GEOFRONT":"SURFACE");p.addProperty("node",exit);var bind=new JsonObject();bind.addProperty(Integer.toString(variant),back);p.add("reverse_routes",bind);r.getAsJsonArray("ports").add(p);
            }
        }
        return r;
    }
    static JsonObject rootFixtureForNativeBindingTest(){return fixture(true,false);}
    private static Original original(int variant)
    {return new Original(7,variant,uuid(10+variant),uuid(20+variant),uuid(30+variant),uuid(100),"synthetic_mission","test:synthetic_route_graph");}
    private static final class Access implements NativeAccess
    {
        boolean identity=true,clear=true,restore=true;int swept,restored;
        public boolean sameOriginalAssembly(Original original){return identity;}
        public boolean canTraverse(Original original,Route route,Leg leg,double from,double to){swept++;return clear;}
        public boolean canRestore(Original original,Route route,int leg,double fraction){restored++;return restore;}
    }
    public static void main(String[] args)
    {
        verifyRotatingFootPlatform();
        var json=fixture(true,false);var directory=NervRouteDirectoryR52.parse(json);check(directory.installed(),"Root installed receipt was lost");
        var draft=NervRouteDirectoryR52.parse(fixture(false,false));var access=new Access();check(!new NervRouteReservationsR52(draft).reserve(uuid(501),original(0),"depart_b1l1",access).accepted(),"Draft activated runtime");
        var plan=new JsonObject();plan.addProperty("schema","projectseele.r52.root-spatial-plan.v1");plan.addProperty("status","component design; NOT installed");rejects(()->NervRouteDirectoryR52.parse(plan),"Spatial design masqueraded as runtime");
        var permuted=NervRouteDirectoryR52.parse(fixture(true,false,new int[]{2,1,0}));check(permuted.unit(0).lane()==2&&permuted.unit(1).lane()==1&&permuted.unit(2).lane()==0,"Root lane permutation was replaced by variant order");
        var permutedPool=new NervRouteReservationsR52(permuted);check(permutedPool.reserve(uuid(801),original(0),"depart_b1l3",access).accepted(),"Original unit0 UUID could not use explicit physical lane2");
        check(permuted.route("return_b3l3").variant()==0&&permuted.route("return_b3l1").variant()==2,"Reverse bindings followed x/lane instead of original unit");
        check(permuted.nearestRecovery(0,Region.SURFACE,"test:synthetic_route_graph",new Vec3(30,4,31),(p,r)->true).orElseThrow().id().equals("return_b3l3"),"Permuted original unit selected another actor's reverse port");
        var nonBijective=fixture(true,false);nonBijective.getAsJsonArray("units").get(0).getAsJsonObject().addProperty("lane",1);rejects(()->NervRouteDirectoryR52.parse(nonBijective),"Non-bijective Root unit/lane mapping accepted");
        for(int unit=0;unit<3;unit++)for(int bank=1;bank<=3;bank++)check(directory.route("return_b"+bank+"l"+(unit+1)).variant()==unit,"Reverse route lost original unit");
        var bad=json.deepCopy();var duplicateNode=find(bad.getAsJsonArray("nodes"),"dock1_1").deepCopy();duplicateNode.addProperty("id","duplicate_dock");bad.getAsJsonArray("nodes").add(duplicateNode);var duplicateLane=bad;rejects(()->NervRouteDirectoryR52.parse(duplicateLane),"Duplicate bank/lane accepted");
        bad=json.deepCopy();find(bad.getAsJsonArray("legs"),"bridge12_1").add("doors",names());var missingDoor=bad;rejects(()->NervRouteDirectoryR52.parse(missingDoor),"Rear gate omitted");
        bad=json.deepCopy();find(bad.getAsJsonArray("legs"),"incline_b1l1").addProperty("from","dock1_1");var gap=bad;rejects(()->NervRouteDirectoryR52.parse(gap),"Disconnected junction accepted");
        bad=json.deepCopy();find(bad.getAsJsonArray("resources"),"space2").addProperty("component","synthetic_component/space1");var alias=bad;rejects(()->NervRouteDirectoryR52.parse(alias),"Aliased physical resource bypassed locks");
        bad=json.deepCopy();find(bad.getAsJsonArray("legs"),"original1").add("eva_to_xyzw",numbers(Math.sqrt(.5),0,0,Math.sqrt(.5)));var tilted=bad;rejects(()->NervRouteDirectoryR52.parse(tilted),"Original ramp laid EVA along shallow incline");
        bad=json.deepCopy();find(bad.getAsJsonArray("ports"),"port_b1l1").getAsJsonObject("reverse_routes").addProperty("0","return_b1l2");var wrongActor=bad;rejects(()->NervRouteDirectoryR52.parse(wrongActor),"Wrong original reverse actor accepted");
        bad=json.deepCopy();find(bad.getAsJsonArray("legs"),"reverse_incline_b1l1").addProperty("to","bay1");var wrongReverse=bad;rejects(()->NervRouteDirectoryR52.parse(wrongReverse),"Partial/fake reverse route accepted");
        bad=json.deepCopy();bad.remove("installation_receipt_sha256");var noReceipt=bad;rejects(()->NervRouteDirectoryR52.parse(noReceipt),"Installed without explicit Root receipt");
        var pool=new NervRouteReservationsR52(directory);
        check(pool.reserve(uuid(501),original(0),"depart_b1l1",access).accepted(),"Original route reservation failed");
        check(pool.reserve(uuid(502),original(1),"depart_b1l2",access).accepted(),"Independent lane could not run concurrently");
        check(!pool.reserve(uuid(503),original(0),"depart_b3l1",access).accepted(),"Same original EVA/plug/pilot got duplicate task");
        var badIdentity=new Original(7,0,uuid(999),uuid(20),uuid(30),uuid(100),"synthetic_mission","test:synthetic_route_graph");check(!pool.reserve(uuid(504),badIdentity,"depart_b1l1",access).accepted(),"Replacement EVA identity accepted");
        access.clear=false;var held=pool.advance(uuid(501),.5,access);check(!held.accepted()&&held.state().fraction()==0&&held.state().stage()==Stage.HOLD,"Blocked sweep advanced or dropped reservation");
        access.clear=true;check(pool.advance(uuid(501),.5,access).accepted(),"Cleared real sweep could not resume");
        access.identity=false;check(!pool.advance(uuid(501),.6,access).accepted()&&pool.query(uuid(501)).fraction()==.5,"Pilot/plug change was ignored");access.identity=true;
        check(!pool.cancel(uuid(501),uuid(101)).accepted(),"Other owner cancelled task");check(pool.cancel(uuid(501),uuid(100)).accepted(),"Cancel did not release leases");check(pool.reserve(uuid(505),original(0),"depart_b1l1",access).accepted(),"Cancel leaked actor/resource lease");
        var shared=new NervRouteReservationsR52(NervRouteDirectoryR52.parse(fixture(true,true)));check(shared.reserve(uuid(601),original(0),"depart_b1l1",access).accepted(),"Shared reservation setup failed");check(!shared.reserve(uuid(602),original(1),"depart_b1l2",access).accepted(),"Different actors overlapped one declared space");check(shared.reserve(uuid(603),original(2),"depart_b1l3",access).accepted(),"Independent third route blocked by unrelated shared space");
        var snapshot=pool.query(uuid(505));var restored=new NervRouteReservationsR52(directory);access.restore=false;check(!restored.restore(snapshot,access).accepted(),"Restore bypassed native geometry");access.restore=true;check(restored.restore(snapshot,access).accepted()&&access.restored==2,"Restore did not invoke physical adapter");check(restored.query(uuid(505)).original().equals(original(0)),"Restored UUID triple replaced");
        var changed=json.deepCopy();changed.addProperty("epoch",8);check(!new NervRouteReservationsR52(NervRouteDirectoryR52.parse(changed)).restore(snapshot,access).accepted(),"Stale epoch restored");
        Vec3 nearSurface=new Vec3(10,4,31);var nearest=directory.nearestRecovery(0,Region.SURFACE,"test:synthetic_route_graph",nearSurface,(p,r)->true).orElseThrow();check(nearest.id().equals("return_b3l1"),"Closest reachable original surface reverse not selected");
        nearest=directory.nearestRecovery(0,Region.SURFACE,"test:synthetic_route_graph",nearSurface,(p,r)->!p.id().equals("port_b3l1")).orElseThrow();check(nearest.id().equals("return_b1l1"),"Blocked nearest port did not choose reachable actual alternative");
        nearest=directory.nearestRecovery(0,Region.GEOFRONT,"test:synthetic_route_graph",nearSurface,(p,r)->true).orElseThrow();check(nearest.id().equals("return_b2l1"),"Underground recovery leaked to surface");check(directory.nearestRecovery(0,Region.SURFACE,"test:synthetic_route_graph",nearSurface,(p,r)->false).isEmpty(),"Unavailable port fabricated fallback");
        var binding=new FootSupportFrameR52.Binding(new Vec3(-1,0,0),new Vec3(1,0,0),RigidTransform.identity());var sample=directory.sample(directory.leg("original1"),.5,binding);check(Math.abs(sample.evaRoot().transformVector(new Vec3(0,1,0)).y-1)<1e-6,"Upright original transfer sampler tilted body");
        var turnJson=json.deepCopy();leg(turnJson,"bearing_turn","dock1_1","dock1_1",Motion.FOOT_BEARING_TURN,"space1");find(turnJson.getAsJsonArray("legs"),"bearing_turn").add("eva_to_xyzw",numbers(Math.sqrt(.5),0,0,Math.sqrt(.5)));var turnDirectory=NervRouteDirectoryR52.parse(turnJson);
        var offsetFeet=new FootSupportFrameR52.Binding(new Vec3(-1,-2,1),new Vec3(1,-2,1),RigidTransform.identity());var start=turnDirectory.sample(turnDirectory.leg("bearing_turn"),0,offsetFeet);
        for(double fraction:new double[]{.25,.5,.75,1}){var pose=turnDirectory.sample(turnDirectory.leg("bearing_turn"),fraction,offsetFeet);check(pose.leftContact().distanceTo(start.leftContact())<1e-5&&pose.rightContact().distanceTo(start.rightContact())<1e-5,"Whole-body turn slipped actual offset foot bearings");}
        var invalidTurn=turnJson.deepCopy();find(invalidTurn.getAsJsonArray("legs"),"bearing_turn").add("eva_to_xyzw",numbers(0,Math.sqrt(.5),0,Math.sqrt(.5)));var invalidDirectory=NervRouteDirectoryR52.parse(invalidTurn);rejects(()->invalidDirectory.sample(invalidDirectory.leg("bearing_turn"),.5,offsetFeet),"Turn around guessed axis accepted over original feet");
        for(int i=0;i<directory.route("depart_b1l2").legs().size();i++)check(pool.advance(uuid(502),1,access).accepted(),"Native confirmed route could not complete");check(pool.query(uuid(502)).stage()==Stage.COMPLETE,"Complete did not release route");
        var flightPool=new NervRouteReservationsR52(directory);FlightAccess flightAccess=new FlightAccess(){public boolean sameOriginalAssembly(Original original){return true;}public boolean checkedFlightGeometry(Original original,Set<Resource> spaces,boolean restoring){return true;}};
        check(flightPool.reserveFlight(uuid(701),original(0),Set.of("space3"),flightAccess),"Actual admitted flight could not reserve declared space");
        check(flightPool.reserveFlight(uuid(702),original(1),Set.of("space2"),flightAccess),"Independent original flight blocked");
        check(!flightPool.reserveFlight(uuid(703),original(2),Set.of("space3"),flightAccess),"Different aircraft/payload tasks overlapped one space");
        check(!flightPool.reserve(uuid(704),original(2),"depart_b1l3",access).accepted(),"Flight occupied space ignored by ground broker");
        var savedFlight=flightPool.queryFlight(uuid(701));check(flightPool.cancel(uuid(701),uuid(100)).accepted()&&flightPool.queryFlight(uuid(701))==null,"Flight cancellation leaked space");
        check(flightPool.reserveFlight(uuid(705),original(2),Set.of("space3"),flightAccess),"Cancelled flight space could not be reused");
        FlightAccess blockedFlight=new FlightAccess(){public boolean sameOriginalAssembly(Original original){return true;}public boolean checkedFlightGeometry(Original original,Set<Resource> spaces,boolean restoring){return false;}};
        var restoredFlights=new NervRouteReservationsR52(directory);check(!restoredFlights.restoreFlight(savedFlight,blockedFlight),"Flight restore bypassed actual geometry");check(restoredFlights.restoreFlight(savedFlight,flightAccess),"Checked original flight lease could not restore");
        var retained=new NervRouteReservationsR52(directory);check(retained.reserve(uuid(901),original(0),"depart_b1l1",access).accepted(),"Retained completion setup failed");
        for(int i=0;i<directory.route("depart_b1l1").legs().size();i++)check(retained.advanceRetainingCompletion(uuid(901),1,access).accepted(),"Verified retained route did not advance");
        check(!retained.reserve(uuid(902),original(0),"depart_b1l1",access).accepted(),"Mechanical finishing released original actor/resource too early");
        var finished=retained.query(uuid(901));var restoredFinish=new NervRouteReservationsR52(directory);access.restore=false;
        check(!restoredFinish.restoreCompletion(finished,access).accepted(),"Finishing restart bypassed actual endpoint geometry");access.restore=true;
        check(restoredFinish.restoreCompletion(finished,access).accepted(),"Actual confirmed finishing endpoint did not restore leases");
        check(!restoredFinish.releaseCompletion(uuid(901),uuid(101)),"Other owner released finishing assembly");check(restoredFinish.releaseCompletion(uuid(901),uuid(100)),"Finishing completion leaked leases");
        check(restoredFinish.reserve(uuid(903),original(0),"depart_b1l1",access).accepted(),"Actually completed assembly leases were not reusable");
        var fabricatedComplete=new Snapshot(finished.task(),finished.original(),finished.directoryFingerprint(),finished.route(),0,.5,Stage.COMPLETE,"");
        check(!new NervRouteReservationsR52(directory).restoreCompletion(fabricatedComplete,access).accepted(),"Partial progress forged final endpoint completion");
        var branch=new NervRouteReservationsR52(directory);check(branch.reserve(uuid(910),original(0),"depart_b1l1",access).accepted(),"Preparation branch setup failed");
        check(!branch.retargetPrepared(uuid(910),"depart_b2l1",access).accepted(),"Moving/non-prepared prefix retargeted");check(branch.advance(uuid(910),1,access).accepted(),"Original ramp did not reach real shared preparation node");
        access.restore=false;check(!branch.retargetPrepared(uuid(910),"depart_b2l1",access).accepted()&&branch.query(uuid(910)).route().equals("depart_b1l1"),"Rejected branch displaced old reservation");access.restore=true;
        var retargeted=branch.retargetPrepared(uuid(910),"depart_b2l1",access);check(retargeted.accepted()&&retargeted.state().leg()==1&&retargeted.state().fraction()==0&&retargeted.state().original().equals(original(0)),"Actual stopped branch changed original pose/progress/identity");
        check(!branch.retargetPrepared(uuid(910),"depart_b2l2",access).accepted(),"Branch changed original unit/lane binding");check(branch.cancel(uuid(910),uuid(100)).accepted(),"Branched cancellation did not release resources");
        System.out.println("R52 route core PASS checks="+checks+"; synthetic graph/adapter tests only, no world/track/native acceptance");
    }

    private static void verifyRotatingFootPlatform()
    {
        var document=fixture(true,false);
        node(document,"bearing_before",Role.PATH,0,0,-1,71,19,63);
        node(document,"bearing_after",Role.PATH,0,0,-1,71,19,63);
        var yaw=new org.joml.Quaternionf().rotationY(-.74F);
        find(document.getAsJsonArray("nodes"),"bearing_after").getAsJsonObject("foot_frame")
                .add("quaternion_xyzw",numbers(yaw.x,yaw.y,yaw.z,yaw.w));
        leg(document,"bearing_turn","bearing_before","bearing_after",Motion.FOOT_BEARING_TURN,"space1");
        var pitch=new org.joml.Quaternionf().rotationX(1.5F);
        find(document.getAsJsonArray("legs"),"bearing_turn").add("eva_to_xyzw",numbers(pitch.x,pitch.y,pitch.z,pitch.w));
        var d=NervRouteDirectoryR52.parse(document);var b=new FootSupportFrameR52.Binding(new Vec3(-7,0,.2),new Vec3(7,0,.2),RigidTransform.identity());
        var trajectory=new DirectoryTrajectoryR52(d,d.leg("bearing_turn"),b,0,1);
        for(int step=0;step<=1000;step++)
        {
            double t=step/1000D;var sample=trajectory.sample(t);
            var platform=d.node("bearing_before").footFrame().interpolate(d.node("bearing_after").footFrame(),t);
            check(sample.leftContact().distanceTo(platform.transformPoint(new Vec3(-7,0,0)))<1e-5,"Left foot slid on a turning real platform");
            check(sample.rightContact().distanceTo(platform.transformPoint(new Vec3(7,0,0)))<1e-5,"Right foot slid on a turning real platform");
        }
        var displaced=document.deepCopy();find(displaced.getAsJsonArray("nodes"),"bearing_after").getAsJsonObject("foot_frame").add("translation",numbers(71.001,19,63));
        rejects(()->NervRouteDirectoryR52.parse(displaced),"Turn smuggled a moving support centre");
        var self=document.deepCopy();self.addProperty("directory_fingerprint","a".repeat(64));rejects(()->NervRouteDirectoryR52.parse(self),"Self-referential fingerprint accepted");
        var dependent=document.deepCopy();dependent.add("air_transport",new JsonObject());rejects(()->NervRouteDirectoryR52.parse(dependent),"Dependent manifest changed signed directory identity");
        var wrong=document.deepCopy();var roll=new org.joml.Quaternionf().rotationZ(.2F);
        find(wrong.getAsJsonArray("legs"),"bearing_turn").add("eva_to_xyzw",numbers(roll.x,roll.y,roll.z,roll.w));
        var rejected=NervRouteDirectoryR52.parse(wrong);rejects(()->rejected.sample(rejected.leg("bearing_turn"),.5,b),"Two-foot-axis restriction was relaxed");
    }
    private NervRouteCoreR52Test(){}
}

package com.projectseele.world;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import java.util.*;
import net.minecraft.world.phys.Vec3;
import com.projectseele.world.NervRouteDirectoryR52.*;
import com.projectseele.world.NervRouteReservationsR52.*;
import com.projectseele.world.TransportMembershipR52.Kind;

/** Two broker-only cases. No world, manifest parsing, digest or native geometry audit. */
public final class NervSharedSpaceReservationsR54Test
{
    private static UUID id(int n){return new UUID(0,n);}
    private static Original original(int v){return new Original(7,v,id(10+v),id(20+v),id(30+v),id(100),"test","test:reservations");}
    private static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);}
    private static void field(Object target,String name,Object value)throws Exception
    {var f=target.getClass().getDeclaredField(name);f.setAccessible(true);f.set(target,value);}
    private static final class Access implements NativeAccess,FlightAccess,HardwareAccess
    {
        public boolean sameOriginalAssembly(Original o){return true;}
        public boolean canTraverse(Original o,Route r,Leg l,double from,double to){return true;}
        public boolean canRestore(Original o,Route r,int leg,double fraction){return true;}
        public boolean checkedFlightGeometry(Original o,Set<Resource> resources,boolean restoring){return true;}
        public boolean checkedAircraftOnlyGeometry(UUID aircraft,Set<Resource> resources,boolean restoring){return true;}
        public boolean originalAircraft(UUID aircraft){return true;}
        public boolean sameOriginalCarrier(UUID controller,int variant,long epoch){return true;}
        public boolean checkedCarrierGeometry(UUID controller,Set<Resource> resources,boolean restoring){return true;}
    }
    private static NervRouteDirectoryR52 directory()throws Exception
    {
        // Supply only the immutable data the broker consumes. The route parser
        // and its installation/digest contracts are outside these two cases.
        var d=new Gson().fromJson("{}",NervRouteDirectoryR52.class);
        var units=new HashMap<Integer,Unit>();var nodes=new HashMap<String,Node>();
        var resources=new HashMap<String,Resource>();var legs=new HashMap<String,Leg>();var routes=new HashMap<String,Route>();
        resources.put("shared",new Resource("shared",ResourceKind.SPACE,"shared"));
        var rotation=new Rotation(0,0,0,1);
        for(int v=0;v<3;v++)
        {
            units.put(v,new Unit(v,v,id(10+v),id(20+v)));
            nodes.put("bay"+v,new Node("bay"+v,"test:reservations",Role.BAY,0,0,v,new RigidTransform(new Vec3(v,0,0),0,0,0,1)));
            nodes.put("exit"+v,new Node("exit"+v,"test:reservations",Role.EXIT,0,0,-1,new RigidTransform(new Vec3(v,10,0),0,0,0,1)));
            for(var kind:List.of(ResourceKind.RAIL,ResourceKind.SUPPORT,ResourceKind.DOOR))
            {String name=kind.name()+v;resources.put(name,new Resource(name,kind,name));}
            legs.put("leg"+v,new Leg("leg"+v,"bay"+v,"exit"+v,Motion.VERTICAL,10,rotation,rotation,List.of("RAIL"+v),List.of("DOOR"+v),"SUPPORT"+v,Set.of("shared")));
            routes.put("depart"+v,new Route("depart"+v,v,1,v,Region.SURFACE,"port"+v,"",List.of("leg"+v)));
            routes.put("return"+v,new Route("return"+v,v,1,v,Region.SURFACE,"port"+v,"depart"+v,List.of("leg"+v)));
        }
        field(d,"epoch",7L);field(d,"installed",true);field(d,"fingerprint","synthetic-reservation-identity");
        field(d,"units",units);field(d,"nodes",nodes);field(d,"resources",resources);field(d,"legs",legs);field(d,"routes",routes);
        field(d,"dynamicSpaces",NervDynamicAirspaceR52.parse(new JsonObject()));return d;
    }
    private static void sharedSpaceProgresses()throws Exception
    {
        var d=directory();var p=new NervRouteReservationsR52(d);var a=new Access();
        check(p.reserve(id(201),original(0),"depart0",a).accepted(),"First original ground task");
        check(p.reserve(id(202),original(1),"depart1",a).accepted(),"Second original may share SPACE");
        check(p.advance(id(201),.5,a).accepted()&&p.advance(id(202),.5,a).accepted(),"Both original ground tasks continue");
        check(p.reserveFlight(id(203),original(2),id(303),Kind.OCCUPIED,Set.of("shared"),Set.of(),a),"Flight shares ground SPACE");
        check(p.reserveHardware(new HardwareLease(id(204),id(304),2,7,d.fingerprint(),Set.of("shared"),null),a,false),"Independent hardware shares SPACE");
        check(p.retargetFlightSpaces(id(203),Set.of("shared"),Set.of(),a),"Flight retarget retains descriptive SPACE");
        check(p.handoffFlightToGround(id(203),id(205),"return2",Set.of("shared"),Set.of(),a,a).accepted(),"Aircraft and receiver may overlap SPACE during handoff");
        check(p.queryFlight(id(203)).spaces().equals(Set.of("shared"))&&p.leasedMembers(id(203)).equals(Set.of(id(303))),"Flight keeps displayed SPACE and only its actual aircraft after handoff");
        for(String name:List.of("resources","hardwareResources")){var f=p.getClass().getDeclaredField(name);f.setAccessible(true);check(!((Map<?,?>)f.get(p)).containsKey("shared"),"SPACE must not enter "+name);}
    }
    private static void originalsAndMechanismsStayExclusive()throws Exception
    {
        var d=directory();var p=new NervRouteReservationsR52(d);var a=new Access();
        check(p.reserveFlight(id(401),original(0),id(501),Kind.OCCUPIED,Set.of("shared"),Set.of("DOOR0"),a),"Original flight setup");
        check(!p.reserveFlight(id(402),original(0),id(502),Kind.OCCUPIED,Set.of("shared"),Set.of(),a),"Same EVA/plug/pilot cannot be taken by another flight");
        check(!p.reserve(id(403),original(0),"depart0",a).accepted(),"Same EVA cannot be taken by a ground task");
        check(!p.reserveFlight(id(404),original(1),id(501),Kind.OCCUPIED,Set.of("shared"),Set.of(),a),"Aircraft remains exclusive");
        check(!p.reserveFlight(id(405),original(1),id(502),Kind.OCCUPIED,Set.of("shared"),Set.of("DOOR0"),a),"Door remains exclusive");
        check(!p.handoffFlightToGround(id(401),id(406),"return0",Set.of("shared"),Set.of("DOOR0"),a,a).accepted(),"Handoff cannot give the same door to aircraft and ground tasks");
        check(p.resourcesHeldR52(id(401),Set.of("shared","DOOR0"))&&!p.resourcesAvailable(id(405),Set.of("DOOR0")),"Mechanism ownership still backs held/available checks");
        check(p.reserveFlight(id(407),original(1),id(502),Kind.OCCUPIED,Set.of("shared"),Set.of(),a),"Different original can still share SPACE");
    }
    public static void main(String[] args)throws Exception
    {sharedSpaceProgresses();originalsAndMechanismsStayExclusive();System.out.println("PASS 2 reservation cases: shared SPACE progress; original actors and mechanisms remain exclusive");}
}

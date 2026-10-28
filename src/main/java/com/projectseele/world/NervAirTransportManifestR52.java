package com.projectseele.world;

import com.google.gson.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.*;
import com.projectseele.world.NervRouteDirectoryR52.*;

/** Root's finite physical flight graph, using the ground directory's same resources. */
public final class NervAirTransportManifestR52
{
    public static final String SCHEMA="projectseele.r52.air-transport.v1";
    public record Cell(BlockPos position,String state){}
    public record Aircraft(String id,UUID entity,int serial,String airport,String stand,List<Cell> support)
    {public Aircraft{support=List.copyOf(support);}}
    public record Airport(String id,Region region,AABB domain,String takeoff,Set<String> occupancy)
    {public Airport{occupancy=Set.copyOf(occupancy);}}
    public record Rig(float hoist,float deployment,float jaws)
    {
        public Rig{require(Float.isFinite(hoist+deployment+jaws)&&hoist>=24&&hoist<=144&&deployment>=0&&deployment<=1&&jaws>=0&&jaws<=1,"Actual original hoist/deployment/jaw range required");}
        public Rig interpolate(Rig b,double t){return new Rig((float)(hoist+(b.hoist-hoist)*t),(float)(deployment+(b.deployment-deployment)*t),(float)(jaws+(b.jaws-jaws)*t));}
    }
    public record Frame(RigidTransform plane,RigidTransform cargo,Rig rig)
    {
        public Frame{Objects.requireNonNull(plane);Objects.requireNonNull(rig);require(Math.abs(plane.qx())<1e-6&&Math.abs(plane.qz())<1e-6,"Original aircraft supports yaw only");}
        public Frame interpolate(Frame b,double t)
        {require((cargo==null)==(b.cargo==null),"Payload cannot appear halfway through a corridor");return new Frame(plane.interpolate(b.plane,t),cargo==null?null:cargo.interpolate(b.cargo,t),rig.interpolate(b.rig,t));}
    }
    public record Node(String id,Region region,Frame frame,Set<String> spaces,List<Cell> cells)
    {public Node{spaces=Set.copyOf(spaces);cells=List.copyOf(cells);}}
    public record Corridor(String id,String from,String to,int ticks,String reverseOf,Set<String> spaces,Set<String> gates)
    {public Corridor{spaces=Set.copyOf(spaces);gates=Set.copyOf(gates);require(ticks>0,"Actual positive flight duration required");}}
    public record Shaft(String id,String underground,String surface,String motion,Set<String> spaces)
    {public Shaft{spaces=Set.copyOf(spaces);}}
    public record Receiver(String port,Region region,String node,RigidTransform stopped,Map<Integer,String> reverseRoutes,boolean delivery,List<Cell> supports,Set<String> gates)
    {public Receiver{reverseRoutes=Map.copyOf(reverseRoutes);supports=List.copyOf(supports);gates=Set.copyOf(gates);}}
    public enum Intent { RECOVER,DELIVER,FAR_MOUNTAIN }
    public record Mission(String id,Intent intent,String aircraft,Set<Integer> variants,Region region,AABB pickupDomain,String pickupNode,String receiver,List<String> outbound,List<String> loaded,List<String> retreat)
    {public Mission{variants=Set.copyOf(variants);outbound=List.copyOf(outbound);loaded=List.copyOf(loaded);retreat=List.copyOf(retreat);}}
    private final NervRouteDirectoryR52 directory;
    private final boolean installed;
    private final String fingerprint,dimension;
    private final double pickupVerticalClearance;
    private final Map<String,String> sources;
    private final Map<String,Aircraft> aircraft;
    private final Map<String,Airport> airports;
    private final Map<String,Node> nodes;
    private final Map<String,Corridor> corridors;
    private final Map<String,Receiver> receivers;
    private final Map<String,Mission> missions;
    private final Map<String,Shaft> shafts;
    private NervAirTransportManifestR52(NervRouteDirectoryR52 directory,JsonObject root)
    {
        this.directory=directory;require(SCHEMA.equals(str(root,"schema"))&&"root".equals(str(root,"map_author")),"Explicit Root aircraft receipt required");
        String status=str(root,"status");require(Set.of("design","installed").contains(status),"Root air installation status required");installed=status.equals("installed");
        require(root.get("epoch").getAsLong()==directory.epoch()&&str(root,"directory_fingerprint").equals(directory.fingerprint()),"Air and ground must share the same exact epoch/directory");
        dimension=str(root,"dimension");require(directory.knowsDimension(dimension),"Actual aircraft dimension is absent from ground directory");fingerprint=sha(root.toString().getBytes(StandardCharsets.UTF_8));
        root=NervAirPickupColumnR53.expand(root);
        double clearance=0;if(root.has("pickup_vertical_clearance")){var value=root.get("pickup_vertical_clearance");require(value.isJsonPrimitive()&&value.getAsJsonPrimitive().isNumber(),"Explicit numeric Root pickup vertical clearance required");clearance=value.getAsDouble();require(Double.isFinite(clearance)&&clearance>0&&clearance<=256,"Finite positive Root pickup vertical clearance of at most256m required");}pickupVerticalClearance=clearance;
        var hashes=new TreeMap<String,String>();root.getAsJsonObject("mesh_sources").entrySet().forEach(e->{require(e.getValue().getAsString().matches("[0-9a-f]{64}"),"Actual source SHA required");hashes.put(e.getKey(),e.getValue().getAsString());});
        require(hashes.keySet().equals(Set.of("mesh/tv_facilities_r16.json","mesh/air_cradle_r31.json")),"Actual R16 aircraft and original cradle source required");sources=Map.copyOf(hashes);
        var aa=new LinkedHashMap<String,Airport>();for(var raw:rows(root,"airports")){var o=raw.getAsJsonObject();var a=new Airport(str(o,"id"),Region.valueOf(str(o,"region")),box(o.getAsJsonArray("domain")),str(o,"takeoff_node"),ids(o,"occupancy"));put(aa,a.id(),a);}airports=Map.copyOf(aa);
        var nn=new LinkedHashMap<String,Node>();for(var raw:rows(root,"nodes")){var o=raw.getAsJsonObject();var n=new Node(str(o,"id"),Region.valueOf(str(o,"region")),frame(o.getAsJsonObject("frame")),ids(o,"occupancy"),cells(o,"actual_cells"));put(nn,n.id(),n);}nodes=Map.copyOf(nn);
        var ac=new LinkedHashMap<String,Aircraft>();var uuids=new HashSet<UUID>();for(var raw:rows(root,"aircraft")){var o=raw.getAsJsonObject();require(str(o,"expected_type").equals("projectseele:un_transport"),"Actual original NERV aircraft type required");var a=new Aircraft(str(o,"id"),UUID.fromString(str(o,"entity_uuid")),o.get("serial").getAsInt(),str(o,"airport"),str(o,"stand_node"),cells(o,"support_cells"));require(uuids.add(a.entity())&&!a.support().isEmpty(),"Distinct original aircraft UUID and actual stand support required");for(var unit:List.of(directory.unit(0),directory.unit(1),directory.unit(2)))require(!Set.of(unit.eva(),unit.plug()).contains(a.entity()),"Aircraft aliases original payload");put(ac,a.id(),a);}aircraft=Map.copyOf(ac);
        var cc=new LinkedHashMap<String,Corridor>();for(var raw:rows(root,"corridors")){var o=raw.getAsJsonObject();var c=new Corridor(str(o,"id"),str(o,"from"),str(o,"to"),o.get("ticks").getAsInt(),o.has("reverse_of")?str(o,"reverse_of"):"",ids(o,"occupancy"),ids(o,"gates"));put(cc,c.id(),c);}corridors=Map.copyOf(cc);
        var rr=new LinkedHashMap<String,Receiver>();for(var raw:rows(root,"receivers")){var o=raw.getAsJsonObject();var reverse=new HashMap<Integer,String>();o.getAsJsonObject("reverse_routes").entrySet().forEach(e->reverse.put(Integer.parseInt(e.getKey()),e.getValue().getAsString()));var r=new Receiver(str(o,"port"),Region.valueOf(str(o,"region")),str(o,"flight_node"),rigid(o.getAsJsonObject("stopped_cargo_frame")),reverse,o.has("delivery")&&o.get("delivery").getAsBoolean(),o.has("actual_support_cells")?cells(o,"actual_support_cells"):List.of(),o.has("gates")?ids(o,"gates"):Set.of());put(rr,r.port(),r);}receivers=Map.copyOf(rr);
        var mm=new LinkedHashMap<String,Mission>();for(var raw:rows(root,"missions")){var o=raw.getAsJsonObject();var variants=new HashSet<Integer>();for(var v:rows(o,"variants"))require(variants.add(v.getAsInt())&&v.getAsInt()>=0&&v.getAsInt()<=2,"Unique original variants required");var m=new Mission(str(o,"id"),Intent.valueOf(str(o,"intent")),str(o,"aircraft"),variants,Region.valueOf(str(o,"pickup_region")),box(o.getAsJsonArray("pickup_domain")),str(o,"pickup_node"),str(o,"receiver"),list(o,"outbound"),list(o,"loaded"),list(o,"retreat"));put(mm,m.id(),m);}missions=Map.copyOf(mm);
        var ss=new LinkedHashMap<String,Shaft>();if(root.has("shafts"))for(var raw:rows(root,"shafts")){var o=raw.getAsJsonObject();String a=str(o,"underground_node"),b=str(o,"surface_node"),motion=str(o,"motion");require(nodes.containsKey(a)&&nodes.containsKey(b)&&node(a).region()==Region.GEOFRONT&&node(b).region()==Region.SURFACE&&Set.of("GROUND_MECHANICAL","AIRCRAFT").contains(motion),"Explicit actual shaft endpoints/motion required");var shared=ids(o,"occupancy");spaces(shared);var shaft=new Shaft(str(o,"id"),a,b,motion,shared);put(ss,shaft.id(),shaft);if(motion.equals("GROUND_MECHANICAL"))for(var c:corridors.values())require(!(c.from().equals(a)&&c.to().equals(b)||c.from().equals(b)&&c.to().equals(a)),"Ground mechanical shaft cannot be flown through");else for(var c:corridors.values())if(c.from().equals(a)&&c.to().equals(b)||c.from().equals(b)&&c.to().equals(a))require(c.spaces().containsAll(shared),"Shaft air/ground must share the exact physical SPACE IDs");}shafts=Map.copyOf(ss);
        require(!aircraft.isEmpty()&&!missions.isEmpty(),"Explicit aircraft pool and actual flight missions required");validate();
    }
    private void validate()
    {
        var domains=new ArrayList<Airport>();for(var a:airports.values()){require(nodes.containsKey(a.takeoff())&&node(a.takeoff()).region()==a.region(),"Actual airport takeoff missing");spaces(a.occupancy());for(var b:domains)if(a.region()!=b.region())require(!a.domain().intersects(b.domain()),"Surface and underground domains must not overlap");domains.add(a);}
        for(var n:nodes.values()){spaces(n.spaces());require(airports.values().stream().anyMatch(a->a.region()==n.region()),"Actual node region absent");}
        for(var a:aircraft.values()){var p=airports.get(a.airport());require(a.serial()>=0&&p!=null&&nodes.containsKey(a.stand())&&node(a.stand()).region()==p.region()&&p.domain().contains(node(a.stand()).frame().plane().translation())&&node(a.stand()).frame().cargo()==null&&node(a.stand()).frame().rig().deployment()==0&&node(a.stand()).frame().rig().jaws()==1,"Original aircraft stand/region/stowed rig mismatch");}
        for(var c:corridors.values())
        {
            require(nodes.containsKey(c.from())&&nodes.containsKey(c.to()),"Actual flight endpoints absent");spaces(c.spaces());for(String g:c.gates())require(directory.resource(g)!=null&&directory.resource(g).kind()==ResourceKind.DOOR,"Air gate must use the existing ground DOOR ID");
            var a=node(c.from()).frame();var b=node(c.to()).frame();// Cargo node frames are grip references; real custody is held by the typed pickup and durable job.
            if(node(c.from()).region()!=node(c.to()).region())require(shafts.values().stream().anyMatch(s->s.motion().equals("AIRCRAFT")&&(s.underground().equals(c.from())&&s.surface().equals(c.to())||s.underground().equals(c.to())&&s.surface().equals(c.from()))&&c.spaces().containsAll(s.spaces())),"Cross-region aircraft corridor requires Root actual AIRCRAFT shaft and shared SPACE");
            if(!c.reverseOf().isEmpty()){var r=corridors.get(c.reverseOf());require(r!=null&&r.from().equals(c.to())&&r.to().equals(c.from())&&r.ticks()==c.ticks()&&r.spaces().equals(c.spaces())&&r.gates().equals(c.gates()),"Explicit reciprocal physical corridor and same actual clock required");}
        }
        for(var r:receivers.values())
        {
            require(node(r.node())!=null&&node(r.node()).region()==r.region()&&same(r.stopped(),node(r.node()).frame().cargo()),"Actual same-region receiver cargo frame required");
            if(r.delivery()){require(r.reverseRoutes().isEmpty()&&(!r.supports().isEmpty()||r.port().startsWith("r53/coordinate/"))&&Math.abs(r.stopped().qx())<1e-6&&Math.abs(r.stopped().qz())<1e-6,"Delivery requires explicit actual sole support and an upright frame");for(String gate:r.gates())require(directory.resource(gate)!=null&&directory.resource(gate).kind()==ResourceKind.DOOR,"Delivery gate must be the same existing physical DOOR");}
            else{var port=directory.ports().get(r.port());require(port!=null&&port.region()==r.region()&&r.reverseRoutes().equals(port.reverseRoutes()),"Air receiver must be the same typed ground port/reverse routes");}
        }
        for(var m:missions.values())
        {
            var a=aircraft.get(m.aircraft());var r=receivers.get(m.receiver());require(a!=null&&r!=null&&!m.variants().isEmpty()&&node(m.pickupNode())!=null&&node(m.pickupNode()).region()==m.region()&&node(m.pickupNode()).frame().cargo()!=null&&m.pickupDomain().contains(node(m.pickupNode()).frame().cargo().translation()),"Original aircraft/pickup/receiver mission binding required");
            require((m.intent()==Intent.RECOVER)!=r.delivery(),"Recovery uses the actual mechanical port; delivery uses explicit supported destination");
            String out=chain(m.outbound(),a.stand(),false);require(out.equals(m.pickupNode()),"Unladen outbound must reach declared pickup node");
            require(chain(m.loaded(),m.pickupNode(),true).equals(r.node()),"Loaded chain must reach actual same ground receiver");
            require(chain(m.retreat(),r.node(),false).equals(a.stand()),"Original aircraft must continuously return to its actual stand");
            if(!r.delivery())for(int v:m.variants())require(r.reverseRoutes().containsKey(v),"Mission variant has no actual ground recovery route");
            for(String id:m.outbound()){var c=corridor(id);require(!c.reverseOf().isEmpty()||corridors.values().stream().anyMatch(x->x.reverseOf().equals(c.id())),"Every unladen outbound segment needs explicit cancellation reverse");}
        }
    }
    private String chain(List<String> chain,String start,boolean loaded)
    {require(!chain.isEmpty(),"Actual nonempty continuous corridor chain required");String at=start;for(String id:chain){var c=corridor(id);require(c!=null&&c.from().equals(at),"Disconnected physical flight chain");if(loaded)require(node(c.from()).frame().cargo()!=null&&node(c.to()).frame().cargo()!=null,"Loaded destination frame missing");at=c.to();}return at;}
    private void spaces(Set<String> ids){require(!ids.isEmpty(),"Declared shared occupied space required");for(String id:ids)require(directory.resource(id)!=null&&directory.resource(id).kind()==ResourceKind.SPACE,"Flight space must use existing ground SPACE ID");}
    public static NervAirTransportManifestR52 parse(JsonObject root,NervRouteDirectoryR52 directory){return new NervAirTransportManifestR52(Objects.requireNonNull(directory),root);}
    public NervRouteDirectoryR52 directory(){return directory;}public boolean installed(){return installed&&directory.installed();}public String fingerprint(){return fingerprint;}public String dimension(){return dimension;}public Map<String,String> meshSources(){return sources;}public Map<String,Aircraft> aircraft(){return aircraft;}public Map<String,Mission> missions(){return missions;}public Node node(String id){return nodes.get(id);}public Corridor corridor(String id){return corridors.get(id);}public Receiver receiver(String id){return receivers.get(id);}public Airport airport(String id){return airports.get(id);}
    public double pickupVerticalClearanceR52(){return pickupVerticalClearance;}
    public Region region(Vec3 actualFoot){Region result=null;for(var a:airports.values())if(a.domain().contains(actualFoot)){if(result!=null&&result!=a.region())throw new IllegalStateException("Ambiguous actual recovery domain");result=a.region();}return result;}
    public Corridor reverse(Corridor c){if(!c.reverseOf().isEmpty())return corridor(c.reverseOf());return corridors.values().stream().filter(x->x.reverseOf().equals(c.id())).findFirst().orElse(null);}
    public static RigidTransform rigid(JsonObject o){var t=o.getAsJsonArray("translation");var q=o.getAsJsonArray("quaternion_xyzw");require(t!=null&&q!=null&&t.size()==3&&q.size()==4,"Exact rigid world frame required");for(var component:t)require(Double.isFinite(component.getAsDouble()),"Finite measured translation required");double norm=0;for(var component:q){double v=component.getAsDouble();require(Double.isFinite(v),"Finite measured quaternion required");norm+=v*v;}require(Math.abs(norm-1)<1e-5,"Measured unit quaternion required");return new RigidTransform(new Vec3(t.get(0).getAsDouble(),t.get(1).getAsDouble(),t.get(2).getAsDouble()),q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());}
    private static Frame frame(JsonObject o){var r=o.getAsJsonObject("rig");return new Frame(rigid(o.getAsJsonObject("plane")),o.has("cargo")?rigid(o.getAsJsonObject("cargo")):null,new Rig(r.get("hoist").getAsFloat(),r.get("deployment").getAsFloat(),r.get("jaws").getAsFloat()));}
    private static List<Cell> cells(JsonObject o,String key){var result=new ArrayList<Cell>();for(var raw:rows(o,key)){var c=raw.getAsJsonObject();var p=c.getAsJsonArray("position");require(p.size()==3,"Actual cell coordinates required");result.add(new Cell(new BlockPos(p.get(0).getAsBigDecimal().intValueExact(),p.get(1).getAsBigDecimal().intValueExact(),p.get(2).getAsBigDecimal().intValueExact()),str(c,"state")));}return List.copyOf(result);}
    private static AABB box(JsonArray a){require(a!=null&&a.size()==6,"Actual domain required");double[] v=new double[6];for(int i=0;i<6;i++){v[i]=a.get(i).getAsDouble();require(Double.isFinite(v[i]),"Finite actual domain required");}require(v[0]<v[3]&&v[1]<v[4]&&v[2]<v[5],"Ordered positive actual domain required");return new AABB(v[0],v[1],v[2],v[3],v[4],v[5]);}
    private static JsonArray rows(JsonObject o,String key){var a=o.getAsJsonArray(key);require(a!=null,"Explicit array missing: "+key);return a;}
    private static String str(JsonObject o,String key){String s=o.get(key).getAsString();require(!s.isBlank(),"Explicit field missing: "+key);return s;}
    private static List<String> list(JsonObject o,String key){var out=new ArrayList<String>();for(var v:rows(o,key))out.add(v.getAsString());return List.copyOf(out);}
    private static Set<String> ids(JsonObject o,String key){var l=list(o,key);var s=Set.copyOf(l);require(s.size()==l.size(),"Duplicate actual resource");return s;}
    private static <T> void put(Map<String,T> map,String id,T value){require(!id.isBlank()&&map.putIfAbsent(id,value)==null,"Duplicate actual ID: "+id);}
    public static boolean same(RigidTransform a,RigidTransform b){return a!=null&&b!=null&&a.translation().distanceToSqr(b.translation())<1e-10&&a.rotationErrorDegrees(b)<.0001;}
    private static String sha(byte[] bytes){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}catch(Exception e){throw new IllegalStateException(e);}}
    private static void require(boolean b,String m){if(!b)throw new IllegalArgumentException(m);}
}

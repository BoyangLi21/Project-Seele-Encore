package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import java.nio.file.*;
import java.util.*;

/** One installed, measured airport and connected GeoFront flight graph. */
final class NervUndergroundTransportSiteR50
{
    static final String FILE="nerv_underground_transport_r50.json";
    static final double HOIST=112;
    // Selected aircraft body corners: |x|<=69, |z|<=58. The complete
    // endpoint min/max already encloses every translating root on the segment.
    // Adding another 4 m for step speed rejected valid pickup poses.
    // .05 covers numerical error and planeClear's 1.5 degree/tick angle margin.
    private static final double CONNECTOR_RADIUS=Math.hypot(NervUndergroundAirLiftR50.PLANE_HALF_X,
            Math.max(Math.abs(NervUndergroundAirLiftR50.PLANE_MIN_Z),Math.abs(NervUndergroundAirLiftR50.PLANE_MAX_Z)))+.05;
    record Receiver(int variant,Vec3 feet,float yaw,String node){}
    final String domain;final UUID aircraft;final Vec3 stand;final float standYaw;
    final String airportNode;final Map<String,Vec3> nodes;final Map<String,List<String>> edges;
    final Set<String> cruiseNodes;
    final List<AABB> pickupZones,airspace;final Map<Integer,Receiver> receivers;
    private record PickupLink(AABB bounds,String node){}
    private final List<PickupLink> pickupLinks;
    private record Cache(long stamp,long physicalStamp,NervUndergroundTransportSiteR50 site){}
    private static final Map<ServerLevel,Cache> CACHE=new WeakHashMap<>();
    private NervUndergroundTransportSiteR50(JsonObject root)
    {
        if(root.get("schema").getAsInt()!=50||!root.get("installed").getAsBoolean()
                ||!"projectseele:geofront".equals(root.get("dimension").getAsString())
                ||Math.abs(root.get("hoist_offset").getAsDouble()-HOIST)>1e-6)throw new IllegalArgumentException("Airport schema/install/hoist differs");
        domain=root.get("domain_id").getAsString();if(domain.isBlank())throw new IllegalArgumentException("Airport lacks connected domain identity");
        aircraft=UUID.fromString(root.get("aircraft_uuid").getAsString());stand=vec(root.getAsJsonArray("airport_stand"));standYaw=finite(root.get("airport_yaw").getAsFloat());
        airportNode=root.get("airport_node").getAsString();var points=new LinkedHashMap<String,Vec3>();var cruises=new HashSet<String>();
        for(var value:root.getAsJsonArray("nodes"))
        {
            var row=value.getAsJsonObject();var id=row.get("id").getAsString();
            if(id.isBlank()||points.put(id,vec(row.getAsJsonArray("pos")))!=null)throw new IllegalArgumentException("Duplicate airport node");
            String role=row.has("role")?row.get("role").getAsString():row.has("empty_only")&&row.get("empty_only").getAsBoolean()?"stand":"cruise";
            if(!Set.of("stand","hover","cruise").contains(role))throw new IllegalArgumentException("Unknown airport node role");
            if(role.equals("cruise"))cruises.add(id);
        }
        if(points.size()<2||points.size()>1024||!points.containsKey(airportNode)||!cruises.contains(airportNode))throw new IllegalArgumentException("Airport graph/cruise entry absent");nodes=Map.copyOf(points);cruiseNodes=Set.copyOf(cruises);
        var links=new HashMap<String,List<String>>();nodes.keySet().forEach(id->links.put(id,new ArrayList<>()));
        for(var value:root.getAsJsonArray("edges"))
        {
            var row=value.getAsJsonArray();if(row.size()!=2)throw new IllegalArgumentException("Airport edge shape");
            var a=row.get(0).getAsString();var b=row.get(1).getAsString();
            if(!nodes.containsKey(a)||!nodes.containsKey(b)||a.equals(b))throw new IllegalArgumentException("Unknown airport edge");
            links.get(a).add(b);links.get(b).add(a);
        }
        var frozen=new HashMap<String,List<String>>();links.forEach((k,v)->frozen.put(k,List.copyOf(v)));edges=Map.copyOf(frozen);
        pickupZones=boxes(root.getAsJsonArray("pickup_zones"));airspace=boxes(root.getAsJsonArray("airspace"));
        var pickupLinksBuilder=new ArrayList<PickupLink>();
        for(var value:root.getAsJsonArray("pickup_zones"))
        {
            if(!value.isJsonObject()||!value.getAsJsonObject().has("pickup_node"))continue;
            var row=value.getAsJsonObject();String node=row.get("pickup_node").getAsString();
            if(!cruiseNodes.contains(node))throw new IllegalArgumentException("Pickup lacks its measured cruise connector");
            pickupLinksBuilder.add(new PickupLink(boxes(singleton(row.getAsJsonArray("bounds"))).get(0),node));
        }
        pickupLinks=List.copyOf(pickupLinksBuilder);
        var drops=new HashMap<Integer,Receiver>();
        for(var value:root.getAsJsonArray("receivers"))
        {
            var row=value.getAsJsonObject();int v=row.get("variant").getAsInt();var feet=vec(row.getAsJsonArray("drop_feet"));
            var drop=new Receiver(v,feet,finite(row.get("drop_yaw").getAsFloat()),row.get("node").getAsString());
            if(v<0||v>2||drops.put(v,drop)!=null||!nodes.containsKey(drop.node())
                    ||feet.distanceToSqr(UndergroundSortieR48.airReceiverFeetR50(v))>1e-6)throw new IllegalArgumentException("Foreign original receiver");
        }
        if(drops.size()!=3)throw new IllegalArgumentException("All three original receiver ports required");receivers=Map.copyOf(drops);
        var reached=new HashSet<String>();var pending=new ArrayDeque<String>();pending.add(airportNode);reached.add(airportNode);
        while(!pending.isEmpty())for(var next:edges.get(pending.removeFirst()))if(reached.add(next))pending.addLast(next);
        if(reached.size()!=nodes.size())throw new IllegalArgumentException("Disconnected airport graph");
    }
    static NervUndergroundTransportSiteR50 get(ServerLevel level)
    {
        if(!level.dimension().equals(FacilitySchemaV2.DIMENSION))return null;
        Path file=level.getServer().getWorldPath(LevelResource.ROOT).resolve(FILE);
        Path physicalFile=file.resolveSibling("r50_underground_airport.json");
        if(!Files.isRegularFile(file)||!Files.isRegularFile(physicalFile))return null;
        long stamp=0,physicalStamp=0;
        try
        {
            stamp=Files.getLastModifiedTime(file).toMillis();physicalStamp=Files.getLastModifiedTime(physicalFile).toMillis();
            var known=CACHE.get(level);if(known!=null&&known.stamp()==stamp&&known.physicalStamp()==physicalStamp)return known.site();
            var root=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
            var physical=JsonParser.parseString(Files.readString(physicalFile)).getAsJsonObject();
            if(!root.has("installed")||!root.get("installed").getAsBoolean()||!physical.has("installed")||!physical.get("installed").getAsBoolean())
            {CACHE.put(level,new Cache(stamp,physicalStamp,null));return null;}
            var site=new NervUndergroundTransportSiteR50(root);
            if(physical.get("schema").getAsInt()!=50||!"projectseele:geofront".equals(physical.get("dimension").getAsString())
                    ||!site.aircraft.equals(UUID.fromString(physical.get("aircraft_uuid").getAsString())))throw new IllegalArgumentException("Airport physical identity differs from flight receipt");
            var airport=physical.getAsJsonObject("airport");
            if(site.stand.distanceToSqr(vec(airport.getAsJsonArray("airport_stand")))>1e-6
                    ||Math.abs(site.standYaw-finite(airport.get("airport_yaw").getAsFloat()))>1e-6)throw new IllegalArgumentException("Airport actual stand differs from flight receipt");
            var physicalReceivers=new HashSet<Integer>();
            for(var value:physical.getAsJsonArray("receivers"))
            {
                var row=value.getAsJsonObject();int variant=row.get("variant").getAsInt();var drop=site.receivers.get(variant);
                if(drop==null||!physicalReceivers.add(variant)||drop.feet().distanceToSqr(vec(row.getAsJsonArray("feet")))>1e-6)
                    throw new IllegalArgumentException("Original receiver physical identity differs from flight receipt");
            }
            if(physicalReceivers.size()!=3)throw new IllegalArgumentException("Airport physical receiver set incomplete");
            CACHE.put(level,new Cache(stamp,physicalStamp,site));return site;
        }
        catch(Exception error)
        {if(stamp!=0)CACHE.put(level,new Cache(stamp,physicalStamp,null));ProjectSeele.LOGGER.error("R50 underground airport receipt rejected; no aircraft or airframe created",error);return null;}
    }
    boolean pickupContains(Vec3 feet){return pickupZones.stream().anyMatch(box->box.contains(feet));}
    boolean airContains(AABB body)
    {
        // Each measured corridor cell must be wide enough for this complete
        // body. Eight corners in different cells do not prove the middle.
        return airspace.stream().anyMatch(box->body.minX>=box.minX&&body.maxX<=box.maxX
                &&body.minY>=box.minY&&body.maxY<=box.maxY&&body.minZ>=box.minZ&&body.maxZ<=box.maxZ);
    }
    String nearest(Vec3 at)
    {
        var feet=at.add(0,-HOIST,0);
        // First require actual membership in a measured field. Then choose
        // the nearest cruise connector only when the complete straight
        // aircraft sweep fits one measured box, including its interior.
        // Thin boundary strips need not ferry via their faraway midpoint.
        if(!pickupLinks.isEmpty())
        {
            if(pickupLinks.stream().noneMatch(link->link.bounds().contains(feet)))return null;
            return cruiseNodes.stream().sorted(Comparator.comparingDouble(id->nodes.get(id).distanceToSqr(at)))
                    .filter(id->{var target=nodes.get(id);
                        return airContains(new AABB(Math.min(at.x,target.x)-CONNECTOR_RADIUS,Math.min(at.y,target.y)+NervUndergroundAirLiftR50.PLANE_MIN_Y-.01,Math.min(at.z,target.z)-CONNECTOR_RADIUS,
                                Math.max(at.x,target.x)+CONNECTOR_RADIUS,Math.max(at.y,target.y)+NervUndergroundAirLiftR50.PLANE_MAX_Y+.01,Math.max(at.z,target.z)+CONNECTOR_RADIUS));})
                    .findFirst().orElse(null);
        }
        return cruiseNodes.stream().min(Comparator.comparingDouble(id->nodes.get(id).distanceToSqr(at))).orElse(null);
    }
    String connectorRefusalR50(Vec3 at)
    {
        return !pickupLinks.isEmpty()&&pickupLinks.stream().noneMatch(link->link.bounds().contains(at.add(0,-HOIST,0)))
                ?"pickup_link_membership_missing":"complete_aircraft_swept_envelope_outside_registered_volume";
    }
    List<Vec3> path(String from,String to)
    {
        if(!nodes.containsKey(from)||!nodes.containsKey(to))return null;
        record Visit(String id,double cost){}
        var distance=new HashMap<String,Double>();var previous=new HashMap<String,String>();distance.put(from,0D);
        var pending=new PriorityQueue<Visit>(Comparator.comparingDouble(Visit::cost));pending.add(new Visit(from,0));
        while(!pending.isEmpty())
        {
            var visit=pending.remove();String next=visit.id();
            if(visit.cost()>distance.getOrDefault(next,Double.POSITIVE_INFINITY))continue;
            if(next.equals(to))
            {
                var result=new ArrayList<Vec3>();for(String at=to;at!=null;at=previous.get(at))result.add(nodes.get(at));Collections.reverse(result);return result;
            }
            for(var edge:edges.get(next))
            {
                double d=distance.get(next)+nodes.get(next).distanceTo(nodes.get(edge));
                if(d<distance.getOrDefault(edge,Double.POSITIVE_INFINITY)){distance.put(edge,d);previous.put(edge,next);pending.add(new Visit(edge,d));}
            }
        }
        return null;
    }
    private static Vec3 vec(JsonArray array)
    {if(array.size()!=3)throw new IllegalArgumentException("Airport coordinate shape");var v=new Vec3(array.get(0).getAsDouble(),array.get(1).getAsDouble(),array.get(2).getAsDouble());if(!Double.isFinite(v.x+v.y+v.z))throw new IllegalArgumentException("Nonfinite airport coordinate");return v;}
    private static float finite(float f){if(!Float.isFinite(f))throw new IllegalArgumentException("Nonfinite airport heading");return f;}
    private static JsonArray singleton(JsonArray bounds){var array=new JsonArray();array.add(bounds);return array;}
    private static List<AABB> boxes(JsonArray array)
    {
        var result=new ArrayList<AABB>();for(var value:array){var pair=value.isJsonObject()?value.getAsJsonObject().getAsJsonArray("bounds"):value.getAsJsonArray();if(pair.size()!=2)throw new IllegalArgumentException("Airport volume shape");var a=vec(pair.get(0).getAsJsonArray());var b=vec(pair.get(1).getAsJsonArray());if(a.x>=b.x||a.y>=b.y||a.z>=b.z)throw new IllegalArgumentException("Empty airport volume");result.add(new AABB(a,b));}
        if(result.isEmpty()||result.size()>2048)throw new IllegalArgumentException("Airport measured volumes missing");return List.copyOf(result);
    }
}

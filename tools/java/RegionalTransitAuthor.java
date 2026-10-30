import java.nio.file.*;
import java.util.*;
import org.mtr.core.data.*;
import org.mtr.core.operation.UpdateDataRequest;
import org.mtr.core.operation.DeleteDataRequest;
import org.mtr.core.serializer.*;
import org.mtr.core.simulation.Simulator;
import org.mtr.core.tool.Angle;
import org.mtr.libraries.com.google.gson.*;
import org.mtr.libraries.it.unimi.dsi.fastutil.objects.ObjectArrayList;

/** Uses the installed MTR 4.0.5 engine to author its own native save format. */
public final class RegionalTransitAuthor
{
    private static final class AuthoringSimulator extends Simulator
    {
        private final java.lang.reflect.Field previousClock;
        AuthoringSimulator(String dim,String[] dims,Path root) throws Exception
        {
            super(dim,dims,root,false);previousClock=Simulator.class.getDeclaredField("lastMillis");previousClock.setAccessible(true);
        }
        void authoringClock(long millis) throws Exception
        {
            // Native departure matching observes the interval between these
            // clocks. Move both, exactly as native instantDeploy does.
            previousClock.setLong(this,getCurrentMillis());setCurrentMillis(millis);
        }
    }
    private static final Gson GSON=new GsonBuilder().setPrettyPrinting().create();
    private static Position pos(JsonArray a) { return new Position(a.get(0).getAsLong(),a.get(1).getAsLong(),a.get(2).getAsLong()); }
    private static JsonObject json(SerializedDataBase value) { JsonObject out=new JsonObject();value.serializeFullData(new JsonWriter(out));return out; }
    private static String str(JsonObject o,String key,String fallback) { return o.has(key)?o.get(key).getAsString():fallback; }
    private static boolean bool(JsonObject o,String key,boolean fallback) { return o.has(key)?o.get(key).getAsBoolean():fallback; }
    private static int integer(JsonObject o,String key,int fallback) { return o.has(key)?o.get(key).getAsInt():fallback; }
    private static boolean same(JsonObject object,Position p)
    {
        return object.get("x").getAsLong()==p.getX() && object.get("y").getAsLong()==p.getY() && object.get("z").getAsLong()==p.getZ();
    }
    private static boolean endpoints(SerializedDataBase object,JsonObject rail)
    {
        JsonObject j=json(object);Position a=pos(rail.getAsJsonArray("from")),b=pos(rail.getAsJsonArray("to"));
        return same(j.getAsJsonObject("position1"),a)&&same(j.getAsJsonObject("position2"),b)
                ||same(j.getAsJsonObject("position1"),b)&&same(j.getAsJsonObject("position2"),a);
    }
    private static <T extends SerializedDataBaseWithId> Map<String,JsonObject> snapshot(Collection<T> values)
    {
        Map<String,JsonObject> result=new LinkedHashMap<>();
        for(T value:values)result.put(value.getHexId(),json(value));
        return result;
    }
    private static void retained(Map<String,JsonObject> before,Map<String,JsonObject> after,String kind,boolean exact)
    {
        for(var entry:before.entrySet())
            if(!after.containsKey(entry.getKey()) || exact&&!entry.getValue().equals(after.get(entry.getKey())))
                throw new IllegalStateException("Existing "+kind+" changed or disappeared: "+entry.getKey());
    }
    public static void main(String[] args) throws Exception
    {
        if(args.length<3)throw new IllegalArgumentException("plan.json staging-data-directory output-directory");
        JsonObject plan=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        Path root=Path.of(args[1]),out=Path.of(args[2]);Files.createDirectories(root);Files.createDirectories(out);
        boolean append=args.length>3&&args[3].equals("--append");
        if(append && java.util.stream.StreamSupport.stream(root.toAbsolutePath().normalize().spliterator(),false)
                .noneMatch(part->part.toString().equalsIgnoreCase(".Codex")))
            throw new IllegalStateException("Append validation is restricted to a copied .Codex staging directory");
        String dim="projectseele/geofront";
        AuthoringSimulator simulator=new AuthoringSimulator(dim,new String[]{"minecraft/overworld",dim,"minecraft/the_nether","minecraft/the_end"},root);
        if(!append && (!simulator.rails.isEmpty()||!simulator.stations.isEmpty()))throw new IllegalStateException("Use a new staging directory; never replace an existing railway");
        Map<String,JsonObject> oldRails=snapshot(simulator.rails),oldRoutes=snapshot(simulator.routes),oldStations=snapshot(simulator.stations),oldPlatforms=snapshot(simulator.platforms),oldSidings=snapshot(simulator.sidings),oldDepots=snapshot(simulator.depots),oldLifts=snapshot(simulator.lifts);
        JsonArray retiredRails=new JsonArray();
        if(plan.has("retire_rails"))
        {
            if(!append)throw new IllegalStateException("Rail retirement requires copied append staging");
            DeleteDataRequest removal=new DeleteDataRequest();
            for(JsonElement item:plan.getAsJsonArray("retire_rails"))
            {
                JsonObject definition=item.getAsJsonObject();List<Rail> found=simulator.rails.stream().filter(r->endpoints(r,definition)).toList();
                if(found.size()!=1)throw new IllegalStateException("Retirement precondition is not unique "+definition);
                Rail rail=found.get(0);
                if(rail.isPlatform()||rail.isSiding()||rail.getStartAngle(pos(definition.getAsJsonArray("from")))!=Angle.valueOf(definition.get("from_angle").getAsString())
                        ||rail.getStartAngle(pos(definition.getAsJsonArray("to")))!=Angle.valueOf(definition.get("to_angle").getAsString()))
                    throw new IllegalStateException("Retirement geometry/type changed "+definition);
                JsonObject record=new JsonObject();record.addProperty("id",rail.getHexId());record.add("before",json(rail));retiredRails.add(record);
                removal.addRailId(rail.getHexId());oldRails.remove(rail.getHexId());
            }
            removal.delete(simulator);simulator.sync();
        }
        Map<String,Rail> rails=new LinkedHashMap<>();Map<String,JsonObject> definitions=new LinkedHashMap<>();
        UpdateDataRequest railRequest=new UpdateDataRequest(simulator);
        JsonArray samples=new JsonArray(),geometryErrors=new JsonArray();
        for(JsonElement entry:plan.getAsJsonArray("rails"))
        {
            JsonObject r=entry.getAsJsonObject();String id=r.get("id").getAsString();
            if(simulator.rails.stream().anyMatch(old->endpoints(old,r)))throw new IllegalStateException("New rail duplicates existing endpoints "+id);
            Position a=pos(r.getAsJsonArray("from")),b=pos(r.getAsJsonArray("to"));
            Angle aa=Angle.valueOf(r.get("from_angle").getAsString()),ab=Angle.valueOf(r.get("to_angle").getAsString());
            TransportMode mode=TransportMode.valueOf(str(r,"mode","TRAIN"));String kind=str(r,"kind","rail");
            var styles=new ObjectArrayList<String>();if(mode==TransportMode.TRAIN)styles.add("default_3d");
            double radius=integer(r,"vertical_radius",100);Rail rail;
            if(kind.equals("platform"))rail=Rail.newPlatformRail(a,aa,b,ab,Rail.Shape.QUADRATIC,radius,styles,mode);
            else if(kind.equals("siding"))rail=Rail.newSidingRail(a,aa,b,ab,Rail.Shape.QUADRATIC,radius,styles,mode);
            else if(kind.equals("turnback"))rail=Rail.newTurnBackRail(a,aa,b,ab,Rail.Shape.QUADRATIC,radius,styles,mode);
            else rail=Rail.newRail(a,aa,b,ab,Rail.Shape.QUADRATIC,radius,styles,
                    integer(r,"speed",80),integer(r,"reverse_speed",integer(r,"speed",80)),false,false,true,kind.equals("runway"),true,mode);
            if(!rail.isValid()){geometryErrors.add(r);continue;}
            railRequest.addRail(rail);rails.put(id,rail);definitions.put(id,r);
            JsonObject sample=new JsonObject();sample.addProperty("id",id);sample.addProperty("kind",kind);sample.addProperty("mode",mode.name());
            sample.addProperty("length",rail.railMath.getLength());JsonArray points=new JsonArray();
            for(double d=0;d<=rail.railMath.getLength();d+=1)
            {
                var p=rail.railMath.getPosition(d,false);JsonArray xyz=new JsonArray();xyz.add(p.x);xyz.add(p.y);xyz.add(p.z);points.add(xyz);
            }
            sample.add("points",points);samples.add(sample);
        }
        if(!geometryErrors.isEmpty())throw new IllegalStateException("Invalid native rail geometries: "+geometryErrors);
        // Rail creation owns platform/siding identities. Metadata must use those actual IDs.
        railRequest.update();simulator.sync();
        Map<String,Platform> platforms=new LinkedHashMap<>();Map<String,Siding> sidings=new LinkedHashMap<>();
        for(var entry:definitions.entrySet())
        {
            String kind=str(entry.getValue(),"kind","rail");
            if(kind.equals("platform"))platforms.put(entry.getKey(),simulator.platforms.stream().filter(p->endpoints(p,entry.getValue())).findFirst().orElseThrow());
            if(kind.equals("siding"))sidings.put(entry.getKey(),simulator.sidings.stream().filter(p->endpoints(p,entry.getValue())).findFirst().orElseThrow());
        }
        UpdateDataRequest metadata=new UpdateDataRequest(simulator);JsonObject inventory=new JsonObject();JsonArray stationIds=new JsonArray();
        for(JsonElement entry:plan.getAsJsonArray("stations"))
        {
            JsonObject j=entry.getAsJsonObject();Station station;
            if(j.has("existing_id"))
            {
                if(!append)throw new IllegalStateException("Existing station reference requires append mode");
                station=simulator.stations.stream().filter(s->s.getId()==j.get("existing_id").getAsLong()).findFirst().orElseThrow();
                Position low=pos(j.getAsJsonArray("min")),high=pos(j.getAsJsonArray("max"));
                station.setCorners(new Position(Math.min(low.getX(),station.getMinX()),Math.min(low.getY(),station.getMinY()),Math.min(low.getZ(),station.getMinZ())),
                    new Position(Math.max(high.getX(),station.getMaxX()),Math.max(high.getY(),station.getMaxY()),Math.max(high.getZ(),station.getMaxZ())));
            }
            else
            {
                station=new Station(simulator);station.setName(j.get("name").getAsString());station.setColor(integer(j,"color",0x52676A));
                station.setCorners(pos(j.getAsJsonArray("min")),pos(j.getAsJsonArray("max")));
            }
            metadata.addStation(station);
            JsonObject id=new JsonObject();id.addProperty("key",j.get("id").getAsString());id.addProperty("native_id",station.getId());stationIds.add(id);
        }
        ObjectArrayList<Depot> depots=new ObjectArrayList<>();Map<Depot,String> depotKeys=new LinkedHashMap<>();Map<String,Siding> lineSidings=new LinkedHashMap<>();JsonArray lineIds=new JsonArray();
        for(JsonElement entry:plan.getAsJsonArray("lines"))
        {
            JsonObject j=entry.getAsJsonObject();String key=j.get("id").getAsString();TransportMode mode=TransportMode.valueOf(str(j,"mode","TRAIN"));
            Route route=new Route(mode,simulator);route.setName(j.get("name").getAsString());route.setRouteNumber(key);route.setColor(integer(j,"color",0x648087));
            int number=1;
            for(JsonElement platformKey:j.getAsJsonArray("platforms"))
            {
                Platform platform=platforms.get(platformKey.getAsString());if(platform==null)throw new IllegalStateException("Missing platform "+platformKey);
                platform.setName(Integer.toString(number++));platform.setDwellTime(integer(j,"dwell",8000));metadata.addPlatform(platform);
                route.getRoutePlatforms().add(new RoutePlatformData(platform.getId()));
            }
            Siding siding=sidings.get(j.get("siding").getAsString());var cars=new ObjectArrayList<VehicleCar>();
            for(JsonElement carEntry:j.getAsJsonArray("cars"))
            {
                JsonObject car=carEntry.getAsJsonObject();cars.add(new VehicleCar(car.get("id").getAsString(),
                    car.get("length").getAsDouble(),car.get("width").getAsDouble(),car.get("bogie1").getAsDouble(),car.get("bogie2").getAsDouble(),
                    car.get("padding1").getAsDouble(),car.get("padding2").getAsDouble()));
            }
            siding.setVehicleCars(cars);siding.setName(key+" 車庫");siding.setMaxVehicles(1);siding.setIsManual(false);metadata.addSiding(siding);
            if(mode==TransportMode.AIRPLANE){siding.setDelayedVehicleReduceDwellTimePercentage(0);siding.setEarlyVehicleIncreaseDwellTime(false);}
            JsonObject sidingJson=json(siding);JsonObject p1=sidingJson.getAsJsonObject("position1"),p2=sidingJson.getAsJsonObject("position2");
            Depot depot=new Depot(mode,simulator);depot.setName(j.get("name").getAsString()+" 運転所");depot.setColor(route.getColor());
            depot.setCorners(new Position(Math.min(p1.get("x").getAsLong(),p2.get("x").getAsLong())-8,p1.get("y").getAsLong()-4,Math.min(p1.get("z").getAsLong(),p2.get("z").getAsLong())-8),
                    new Position(Math.max(p1.get("x").getAsLong(),p2.get("x").getAsLong())+8,p1.get("y").getAsLong()+12,Math.max(p1.get("z").getAsLong(),p2.get("z").getAsLong())+8));
            depot.getRouteIds().add(route.getId());depot.setRepeatInfinitely(bool(j,"repeat",false));depot.setCruisingAltitude(integer(j,"cruise",240));
            depot.setUseRealTime(false);for(int hour=0;hour<24;hour++)depot.setFrequency(hour,integer(j,"frequency",2));
            metadata.addRoute(route).addDepot(depot);depots.add(depot);depotKeys.put(depot,key);lineSidings.put(key,siding);
            JsonObject ids=new JsonObject();ids.addProperty("line",key);ids.addProperty("route_id",route.getId());ids.addProperty("depot_id",depot.getId());ids.addProperty("siding_id",siding.getId());lineIds.add(ids);
        }
        metadata.update();simulator.sync();
        // UpdateDataRequest owns canonical runtime instances. New depot DTOs
        // do not carry the synchronized savedRails association; generating
        // those detached objects creates a route but never dispatches a train.
        for(int index=0;index<depots.size();index++)
        {
            Depot requested=depots.get(index);String key=depotKeys.remove(requested);
            Depot installed=simulator.depots.stream().filter(d->d.getId()==requested.getId()).findFirst().orElseThrow();
            depots.set(index,installed);depotKeys.put(installed,key);
            long sidingId=lineSidings.get(key).getId();
            lineSidings.put(key,simulator.sidings.stream().filter(s->s.getId()==sidingId).findFirst().orElseThrow());
            if(installed.savedRails.isEmpty())throw new IllegalStateException("Depot has no synchronized siding: "+key);
        }
        ObjectArrayList<Depot> freshDepots=new ObjectArrayList<>(depots);
        if(plan.has("regenerate_depots"))for(JsonElement e:plan.getAsJsonArray("regenerate_depots"))
        {
            JsonObject j=e.getAsJsonObject();String key=j.get("line").getAsString();
            Depot depot=simulator.depots.stream().filter(d->d.getId()==j.get("depot_id").getAsLong()).findFirst().orElseThrow();
            Siding siding=simulator.sidings.stream().filter(s->s.getId()==j.get("siding_id").getAsLong()).findFirst().orElseThrow();
            if(j.has("cruise"))depot.setCruisingAltitude(j.get("cruise").getAsInt());
            if(j.has("repeat"))depot.setRepeatInfinitely(j.get("repeat").getAsBoolean());
            if(j.has("dwell_platform_ids"))
            {
                siding.setDelayedVehicleReduceDwellTimePercentage(0);siding.setEarlyVehicleIncreaseDwellTime(false);
                for(JsonElement id:j.getAsJsonArray("dwell_platform_ids"))
                    simulator.platforms.stream().filter(p->p.getId()==id.getAsLong()).findFirst().orElseThrow().setDwellTime(integer(j,"dwell",12000));
            }
            if(bool(j,"restart_vehicles",false)){siding.clearVehicles();freshDepots.add(depot);}
            depots.add(depot);depotKeys.put(depot,key);lineSidings.put(key,siding);
        }
        if(!append)simulator.setGameTime(0,1200000,true);Depot.generateDepots(simulator,depots);
        Map<String,Set<Long>> progress=new LinkedHashMap<>();lineSidings.keySet().forEach(k->progress.put(k,new HashSet<>()));
        Map<String,Map<String,Set<Long>>> vehicleProgress=new LinkedHashMap<>();lineSidings.keySet().forEach(k->vehicleProgress.put(k,new LinkedHashMap<>()));
        boolean deployed=false;
        for(int tick=0;tick<5000;tick++)
        {
            simulator.tick();Thread.sleep(10);
            boolean ready=depots.stream().allMatch(d->d.getLastGeneratedStatus().name().equals("SUCCESSFUL"));
            if(!deployed && ready && tick>50)
            {
                // A regenerated service may be parked with no vehicle. Dispatch
                // it through the native engine; retain existing live vehicles.
                for(Depot depot:depots)
                    if(!freshDepots.contains(depot) && json(lineSidings.get(depotKeys.get(depot))).getAsJsonArray("vehicles").isEmpty())freshDepots.add(depot);
                int warmupSeconds=integer(plan,"warmup_seconds",0);
                if(warmupSeconds>0)
                {
                    // Native instantDeploy simulates a whole day, which is
                    // unnecessary for a short isolated commissioning check.
                    // End at the real commissioning clock. Advancing into
                    // the future then rewinding strands dwell-based trains
                    // at a future departure time after the author is saved.
                    long clock=simulator.getCurrentMillis()-warmupSeconds*1000L;
                    simulator.authoringClock(clock);
                    for(int second=1;second<=warmupSeconds;second++)
                    {
                        simulator.authoringClock(clock+second*1000L);
                        for(Depot depot:freshDepots)for(Siding siding:depot.savedRails)siding.simulateTrain(1000,null);
                    }
                    simulator.authoringClock(clock+warmupSeconds*1000L);
                }
                else simulator.instantDeployDepots(freshDepots);
                deployed=true;
            }
            if(tick%100==0)
            {
                for(var entry:lineSidings.entrySet())
                    for(JsonElement vehicle:json(entry.getValue()).getAsJsonArray("vehicles"))
                    {
                        JsonObject v=vehicle.getAsJsonObject();long p=Math.round(v.get("railProgress").getAsDouble());
                        progress.get(entry.getKey()).add(p);
                        vehicleProgress.get(entry.getKey()).computeIfAbsent(v.get("id").getAsString(),k->new HashSet<>()).add(p);
                    }
            }
            if(tick%500==0)System.out.println("MTR native validation tick="+tick+" depots="+depots.stream().map(d->d.getName()+":"+d.getLastGeneratedStatus()).toList());
            if(tick>800 && deployed && progress.values().stream().allMatch(p->p.size()>=5))break;
        }
        JsonArray results=new JsonArray();boolean all=true;
        for(int i=0;i<depots.size();i++)
        {
            Depot depot=depots.get(i);String key=depotKeys.get(depot);
            int moving=vehicleProgress.get(key).values().stream().mapToInt(Set::size).max().orElse(0);
            boolean passed=depot.getLastGeneratedStatus().name().equals("SUCCESSFUL") && moving>=5;all&=passed;
            JsonObject result=new JsonObject();result.addProperty("line",key);result.addProperty("status",depot.getLastGeneratedStatus().name());
            result.addProperty("path_segments",depot.getPath().size());result.addProperty("distinct_vehicle_positions",progress.get(key).size());result.addProperty("passed",passed);results.add(result);
            result.addProperty("one_vehicle_distinct_positions",moving);
        }
        retained(oldRails,snapshot(simulator.rails),"rail geometry",true);retained(oldRoutes,snapshot(simulator.routes),"route",true);
        retained(oldStations,snapshot(simulator.stations),"station",false);retained(oldPlatforms,snapshot(simulator.platforms),"platform",false);
        retained(oldSidings,snapshot(simulator.sidings),"siding",false);retained(oldDepots,snapshot(simulator.depots),"depot",false);retained(oldLifts,snapshot(simulator.lifts),"lift",false);
        inventory.addProperty("append",append);inventory.addProperty("existing_identities_preserved",true);inventory.addProperty("retained_rails",oldRails.size());inventory.addProperty("retained_routes",oldRoutes.size());
        inventory.add("retired_rails",retiredRails);
        simulator.save();inventory.add("stations",stationIds);inventory.add("lines",lineIds);inventory.add("validation",results);inventory.addProperty("passed",all);
        inventory.addProperty("native_rails",simulator.rails.size());inventory.addProperty("native_platforms",simulator.platforms.size());
        Files.writeString(out.resolve("native_transit_receipt.json"),GSON.toJson(inventory));Files.writeString(out.resolve("track_samples.json"),GSON.toJson(samples));
        simulator.stop();System.out.println(GSON.toJson(results));if(!all)throw new IllegalStateException("One or more native routes failed commissioning");
    }
}

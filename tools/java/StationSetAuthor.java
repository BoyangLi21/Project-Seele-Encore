import java.nio.file.*;
import java.math.BigDecimal;
import java.util.*;
import org.mtr.core.data.*;
import org.mtr.core.operation.UpdateDataRequest;
import org.mtr.core.serializer.*;
import org.mtr.core.simulation.Simulator;
import org.mtr.core.tool.Angle;
import org.mtr.libraries.com.google.gson.*;
import org.mtr.libraries.it.unimi.dsi.fastutil.objects.ObjectArrayList;

/** Add only JSON-defined stations/platforms/rails to a marked offline copy.
 * --validate-only uses Rail/RailMath without constructing a Simulator.
 * Authoring never ticks, dispatches, creates a service or updates old metadata.
 */
public final class StationSetAuthor {
    static final Gson GSON=new GsonBuilder().setPrettyPrinting().create();
    static final List<String> ANGLES=List.of("E","SEE","SE","SSE","S","SSW","SW","SWW","W","NWW","NW","NNW","N","NNE","NE","NEE");
    static void need(boolean okay,String message){if(!okay)throw new IllegalArgumentException(message);}
    static JsonObject load(Path path)throws Exception{return JsonParser.parseString(Files.readString(path)).getAsJsonObject();}
    static JsonObject json(SerializedDataBase value){JsonObject out=new JsonObject();value.serializeFullData(new JsonWriter(out));return out;}
    static long exact(JsonElement value){return new BigDecimal(value.getAsString()).longValueExact();}
    static Position pos(JsonArray a){need(a.size()==3,"Three integral coordinates required");return new Position(exact(a.get(0)),exact(a.get(1)),exact(a.get(2)));}
    static String str(JsonObject o,String k){return o.get(k).getAsString();}
    static double num(JsonObject o,String k){double v=o.get(k).getAsDouble();need(Double.isFinite(v),"Nonfinite "+k);return v;}
    static JsonObject position(Position p){JsonObject j=new JsonObject();j.addProperty("x",p.getX());j.addProperty("y",p.getY());j.addProperty("z",p.getZ());return j;}
    static boolean same(JsonObject j,Position p){return j!=null&&j.get("x").getAsLong()==p.getX()&&j.get("y").getAsLong()==p.getY()&&j.get("z").getAsLong()==p.getZ();}
    static boolean endpoints(SerializedDataBase v,JsonObject d){JsonObject j=json(v);Position a=pos(d.getAsJsonArray("from")),b=pos(d.getAsJsonArray("to"));return same(j.getAsJsonObject("position1"),a)&&same(j.getAsJsonObject("position2"),b)||same(j.getAsJsonObject("position1"),b)&&same(j.getAsJsonObject("position2"),a);}
    static String pair(JsonObject d){String a=position(pos(d.getAsJsonArray("from"))).toString(),b=position(pos(d.getAsJsonArray("to"))).toString();return a.compareTo(b)<0?a+"|"+b:b+"|"+a;}
    static Map<String,JsonObject> snapshot(Collection<? extends SerializedDataBaseWithId> values){Map<String,JsonObject> out=new TreeMap<>();for(var v:values)out.put(v.getHexId(),json(v));return out;}
    static void retained(Map<String,JsonObject> before,Collection<? extends SerializedDataBaseWithId> values,String kind){var after=snapshot(values);for(var e:before.entrySet())need(e.getValue().equals(after.get(e.getKey())),"Existing "+kind+" changed: "+e.getKey());}
    static Map<String,String> ownership(Collection<Platform> platforms){Map<String,String> out=new TreeMap<>();for(Platform p:platforms)out.put(p.getHexId(),p.area==null?"none":p.area.getHexId());return out;}
    static String member(String dim,String kind,SerializedDataBaseWithId value){String id=value.getHexId();return "mtr/"+dim+"/"+kind+"/"+id.substring(id.length()-2)+"/"+id;}
    static double angleError(double x,double z,String angle){double expected=ANGLES.indexOf(angle)*Math.PI/8;need(ANGLES.contains(angle),"Unknown direction");double d=Math.toDegrees(Math.atan2(z,x)-expected);while(d>180)d-=360;while(d< -180)d+=360;return Math.abs(d);}
    static boolean inside(JsonObject s,double x,double y,double z){JsonArray low=s.getAsJsonArray("min"),high=s.getAsJsonArray("max");double[] q={x,y,z};for(int i=0;i<3;i++)if(q[i]<low.get(i).getAsDouble()||q[i]>high.get(i).getAsDouble())return false;return true;}

    static Rail rail(JsonObject r){
        var styles=new ObjectArrayList<String>();styles.add("default_3d");Position a=pos(r.getAsJsonArray("from")),b=pos(r.getAsJsonArray("to"));
        Angle aa=Angle.valueOf(str(r,"from_angle")),bb=Angle.valueOf(str(r,"to_angle"));
        if(str(r,"kind").equals("platform"))return Rail.newPlatformRail(a,aa,b,bb,Rail.Shape.QUADRATIC,num(r,"vertical_radius"),styles,TransportMode.TRAIN);
        return Rail.newRail(a,aa,b,bb,Rail.Shape.QUADRATIC,num(r,"vertical_radius"),styles,r.get("speed").getAsInt(),r.get("reverse_speed").getAsInt(),false,false,true,false,true,TransportMode.TRAIN);
    }

    static JsonObject geometry(JsonObject r,Rail rail){
        String id=str(r,"id");double length=rail.railMath.getLength(),tol=num(r,"length_tolerance");
        need(rail.isValid()&&Double.isFinite(length)&&length>0,"Invalid native rail "+id);
        need(tol>0&&tol<=.01&&Math.abs(length-num(r,"expected_length"))<=tol,"Unexpected native length "+id+" actual="+length+" expected="+num(r,"expected_length"));
        Position a=pos(r.getAsJsonArray("from")),b=pos(r.getAsJsonArray("to"));
        need(endpoints(rail,r)&&rail.getStartAngle(a)==Angle.valueOf(str(r,"from_angle"))&&rail.getStartAngle(b)==Angle.valueOf(str(r,"to_angle")),"Native endpoints or angles differ "+id);
        // Rail factories canonicalise endpoint ordering. Read native samples
        // in the requested direction rather than rejecting west/north inputs.
        var canonicalFirst=rail.railMath.getPosition(0,false);
        boolean reversed=Math.abs(canonicalFirst.x-a.getX()-.5)>1e-5||Math.abs(canonicalFirst.y-a.getY())>1e-5||Math.abs(canonicalFirst.z-a.getZ()-.5)>1e-5;
        var first=rail.railMath.getPosition(reversed?length:0,false);var last=rail.railMath.getPosition(reversed?0:length,false);
        need(Math.abs(first.x-a.getX()-.5)<1e-5&&Math.abs(first.y-a.getY())<1e-5&&Math.abs(first.z-a.getZ()-.5)<1e-5&&Math.abs(last.x-b.getX()-.5)<1e-5&&Math.abs(last.y-b.getY())<1e-5&&Math.abs(last.z-b.getZ()-.5)<1e-5,"Actual sampled endpoints differ "+id);
        double pitch=Math.min(.01,length/100);var next=rail.railMath.getPosition(reversed?length-pitch:pitch,false);var prev=rail.railMath.getPosition(reversed?pitch:length-pitch,false);
        double startError=angleError(next.x-first.x,next.z-first.z,str(r,"from_angle"));
        double endError=angleError(prev.x-last.x,prev.z-last.z,str(r,"to_angle"));
        double tangentTolerance=r.has("tangent_tolerance_degrees")?num(r,"tangent_tolerance_degrees"):1;
        need(tangentTolerance>0&&tangentTolerance<=2&&Math.max(startError,endError)<=tangentTolerance,"Actual curve tangent disagrees with declared direction "+id);
        double maximumGrade=0;JsonArray samples=new JsonArray();int count=(int)Math.ceil(length/.125);var previous=first;
        for(int i=0;i<=count;i++){
            double distanceAlong=length*i/count;var p=rail.railMath.getPosition(reversed?length-distanceAlong:distanceAlong,false);need(Double.isFinite(p.x+p.y+p.z),"Nonfinite curve position");
            if(i>0){double distance=Math.hypot(p.x-previous.x,p.z-previous.z);need(distance>1e-9,"Repeated horizontal curve sample");maximumGrade=Math.max(maximumGrade,Math.abs(p.y-previous.y)/distance);}
            JsonArray q=new JsonArray();q.add(p.x);q.add(p.y);q.add(p.z);samples.add(q);previous=p;
        }
        need(num(r,"max_grade")>=0&&num(r,"max_grade")<=1&&maximumGrade<=num(r,"max_grade")+1e-7,"Rail exceeds declared grade "+id);
        if(str(r,"kind").equals("platform"))need(a.getY()==b.getY()&&maximumGrade<1e-7,"Platform must be level");
        JsonObject result=new JsonObject();result.addProperty("input_rail_id",id);result.addProperty("length",length);result.addProperty("native_math_reversed_to_input",reversed);result.addProperty("start_tangent_error_degrees",startError);result.addProperty("end_tangent_error_degrees",endError);result.addProperty("maximum_grade",maximumGrade);result.add("points",samples);result.add("definition",r.deepCopy());return result;
    }

    static JsonObject validate(JsonObject spec){
        need(spec.keySet().equals(Set.of("schema","dimension","expected_native_members","rails","stations")),"Unexpected root fields; no lines or existing-object updates allowed");
        need(str(spec,"schema").equals("station-set-v1"),"Unsupported schema");String dim=str(spec,"dimension");need(dim.matches("[a-z0-9_.-]+/[a-z0-9_./-]+")&&!Arrays.asList(dim.split("/",-1)).stream().anyMatch(p->p.equals("..")||p.equals(".")||p.isEmpty()),"Invalid dimension");
        need(exact(spec.get("expected_native_members"))>=0,"Expected file count required");
        JsonArray stations=spec.getAsJsonArray("stations"),rails=spec.getAsJsonArray("rails");need(stations.size()>0&&stations.size()<=128&&rails.size()>0&&rails.size()<=1024,"Bounded nonempty station set required");
        Map<String,JsonObject> defs=new LinkedHashMap<>(),curves=new LinkedHashMap<>();Set<String> pairs=new HashSet<>(),nativeIds=new HashSet<>();
        for(var raw:rails){JsonObject r=raw.getAsJsonObject();String id=str(r,"id");need(id.matches("[A-Za-z0-9_.-]+")&&!defs.containsKey(id),"Duplicate rail id");need(Set.of("rail","platform").contains(str(r,"kind"))&&str(r,"shape").equals("QUADRATIC")&&num(r,"vertical_radius")>0,"Unsupported rail kind/shape/radius");
            need(pairs.add(pair(r)),"Duplicate or reversed endpoints");Rail rr=rail(r);need(nativeIds.add(rr.getHexId()),"Duplicate native rail identity");defs.put(id,r);curves.put(id,geometry(r,rr));}
        Set<String> ids=new HashSet<>(),names=new HashSet<>(),owned=new HashSet<>();
        for(var raw:stations){JsonObject s=raw.getAsJsonObject();need(ids.add(str(s,"id"))&&names.add(str(s,"name"))&&!str(s,"name").isBlank(),"Duplicate station id/name");Position low=pos(s.getAsJsonArray("min")),high=pos(s.getAsJsonArray("max"));need(low.getX()<high.getX()&&low.getY()<high.getY()&&low.getZ()<high.getZ(),"Station area is empty");Set<String> platformNames=new HashSet<>();need(!s.getAsJsonArray("platforms").isEmpty(),"Station has no platform");
            for(var entry:s.getAsJsonArray("platforms")){JsonObject p=entry.getAsJsonObject();String rid=str(p,"rail_id");need(defs.containsKey(rid)&&str(defs.get(rid),"kind").equals("platform")&&owned.add(rid),"Unrecognised or multiply owned platform");need(platformNames.add(str(p,"name"))&&!str(p,"name").isBlank(),"Duplicate platform name");need(exact(p.get("dwell_ms"))>=0&&exact(p.get("dwell_ms"))<=3600000,"Invalid dwell");
                double train=num(p,"required_train_length"),margin=num(p,"minimum_end_margin");need(train>0&&margin>=0&&curves.get(rid).get("length").getAsDouble()+num(defs.get(rid),"length_tolerance")>=train+2*margin,"Platform cannot hold specified train and margins");
                for(var pp:curves.get(rid).getAsJsonArray("points")){JsonArray q=pp.getAsJsonArray();need(inside(s,q.get(0).getAsDouble(),q.get(1).getAsDouble(),q.get(2).getAsDouble()),"Sampled platform outside station area "+rid);}}}
        need(owned.size()==defs.values().stream().filter(r->str(r,"kind").equals("platform")).count(),"Unowned platform rail");
        JsonObject result=new JsonObject();JsonArray details=new JsonArray();curves.values().forEach(details::add);result.add("rails",details);result.addProperty("stations",stations.size());result.addProperty("platforms",owned.size());result.addProperty("new_native_members",stations.size()+owned.size()+rails.size());result.addProperty("simulator_started",false);result.addProperty("world_written",false);return result;
    }

    public static void main(String[] args)throws Exception{
        if(args.length==3&&args[0].equals("--validate-only")){JsonObject proof=validate(load(Path.of(args[1])));Files.writeString(Path.of(args[2]),GSON.toJson(proof));System.out.println("Validated station-set geometry without Simulator");return;}
        need(args.length==3,"plan.json isolated-native-copy output-directory, or --validate-only plan.json output.json");
        Path planPath=Path.of(args[0]).toRealPath(),root=Path.of(args[1]).toRealPath(),out=Path.of(args[2]).toRealPath(),work=root.getParent();
        need(java.util.stream.StreamSupport.stream(root.spliterator(),false).anyMatch(p->p.toString().equalsIgnoreCase(".Codex")),"Isolated .Codex directory required");
        need(root.getFileName().toString().equals("native")&&out.equals(work.resolve("output"))&&planPath.equals(work.resolve("plan.json")),"Use the Python-prepared staging layout");
        JsonObject spec=load(planPath),marker=load(work.resolve("station-set-staging.json"));
        need(str(marker,"schema").equals("station-set-offline-copy-v1")&&Path.of(str(marker,"root")).toRealPath().equals(root)&&marker.get("input_plan").equals(spec),"Staging marker/plan mismatch");
        JsonObject geometry=validate(spec);long expected=exact(spec.get("expected_native_members"));try(var paths=Files.walk(root)){need(paths.filter(Files::isRegularFile).count()==expected,"Wrong native batch member count");}
        String dim=str(spec,"dimension");LinkedHashSet<String> dimensions=new LinkedHashSet<>(List.of("minecraft/overworld",dim,"minecraft/the_nether","minecraft/the_end"));
        Simulator sim=new Simulator(dim,dimensions.toArray(String[]::new),root,false);
        try{
            var oldRails=snapshot(sim.rails);var oldPlatforms=snapshot(sim.platforms);var oldStations=snapshot(sim.stations);var oldRoutes=snapshot(sim.routes);var oldDepots=snapshot(sim.depots);var oldSidings=snapshot(sim.sidings);var oldLifts=snapshot(sim.lifts);var oldOwnership=ownership(sim.platforms);
            Map<String,Rail> addedRails=new LinkedHashMap<>();Map<String,String> newPlatformIds=new LinkedHashMap<>();Map<String,JsonObject> definitions=new LinkedHashMap<>();
            for(var item:spec.getAsJsonArray("stations")){JsonObject s=item.getAsJsonObject();need(sim.stations.stream().noneMatch(v->v.getName().equals(str(s,"name"))),"Station name already exists");}
            // Preflight every collision before issuing even the first update.
            for(var item:spec.getAsJsonArray("rails")){JsonObject r=item.getAsJsonObject();Rail rr=rail(r);need(!oldRails.containsKey(rr.getHexId())&&sim.rails.stream().noneMatch(v->endpoints(v,r)),"New rail duplicates existing geometry");addedRails.put(str(r,"id"),rr);definitions.put(str(r,"id"),r);}
            for(var entry:addedRails.entrySet()){
                String id=entry.getKey();Rail rr=entry.getValue();var previous=snapshot(sim.platforms);new UpdateDataRequest(sim).addRail(rr).update();sim.sync();
                var created=sim.platforms.stream().filter(p->!previous.containsKey(p.getHexId())).toList();boolean platform=str(definitions.get(id),"kind").equals("platform");need(created.size()==(platform?1:0),"Unexpected platform side effect");
                if(platform){Platform p=created.get(0);need(endpoints(p,definitions.get(id)),"Created platform endpoints differ");newPlatformIds.put(id,p.getHexId());}
            }
            Map<String,Station> addedStations=new LinkedHashMap<>();UpdateDataRequest update=new UpdateDataRequest(sim);
            for(var item:spec.getAsJsonArray("stations")){JsonObject s=item.getAsJsonObject();Station station=new Station(sim);station.setName(str(s,"name"));station.setColor(s.get("color").getAsInt());station.setCorners(pos(s.getAsJsonArray("min")),pos(s.getAsJsonArray("max")));need(!oldStations.containsKey(station.getHexId()),"New station identity collides");addedStations.put(str(s,"id"),station);update.addStation(station);
                for(var entry:s.getAsJsonArray("platforms")){JsonObject p=entry.getAsJsonObject();String wanted=newPlatformIds.get(str(p,"rail_id"));Platform actual=sim.platforms.stream().filter(v->v.getHexId().equals(wanted)).findFirst().orElseThrow();actual.setName(str(p,"name"));actual.setDwellTime(p.get("dwell_ms").getAsInt());update.addPlatform(actual);}}
            update.update();sim.sync();
            need(sim.rails.size()==oldRails.size()+addedRails.size()&&sim.platforms.size()==oldPlatforms.size()+newPlatformIds.size()&&sim.stations.size()==oldStations.size()+addedStations.size(),"Unexpected native additions");
            JsonArray members=new JsonArray(),stationProof=new JsonArray(),platformProof=new JsonArray(),railProof=new JsonArray();
            for(var item:spec.getAsJsonArray("stations")){JsonObject s=item.getAsJsonObject();Station requested=addedStations.get(str(s,"id"));Station station=sim.stations.stream().filter(v->v.getHexId().equals(requested.getHexId())).findFirst().orElseThrow();need(station.getName().equals(str(s,"name")),"Station name changed");members.add(member(dim,"stations",station));JsonObject detail=new JsonObject();detail.addProperty("input_station_id",str(s,"id"));detail.addProperty("station_id",Long.toString(station.getId()));detail.add("saved",json(station));stationProof.add(detail);
                for(var entry:s.getAsJsonArray("platforms")){JsonObject p=entry.getAsJsonObject();String rid=str(p,"rail_id"),wanted=newPlatformIds.get(rid);Platform actual=sim.platforms.stream().filter(v->v.getHexId().equals(wanted)).findFirst().orElseThrow();need(actual.area!=null&&actual.area.getId()==station.getId()&&actual.getName().equals(str(p,"name"))&&endpoints(actual,definitions.get(rid)),"Platform ownership/name/endpoints differ");members.add(member(dim,"platforms",actual));JsonObject pp=new JsonObject();pp.addProperty("input_station_id",str(s,"id"));pp.addProperty("input_rail_id",rid);pp.addProperty("platform_id",Long.toString(actual.getId()));pp.addProperty("station_id",Long.toString(station.getId()));pp.addProperty("station",station.getName());pp.addProperty("platform_name",actual.getName());pp.addProperty("platform_length",addedRails.get(rid).railMath.getLength());pp.add("station_min",s.get("min").deepCopy());pp.add("station_max",s.get("max").deepCopy());JsonObject ep=new JsonObject();ep.add("from",definitions.get(rid).get("from").deepCopy());ep.add("to",definitions.get(rid).get("to").deepCopy());ep.add("from_angle",definitions.get(rid).get("from_angle").deepCopy());ep.add("to_angle",definitions.get(rid).get("to_angle").deepCopy());pp.add("native_rail_endpoints",ep);pp.add("saved",json(actual));platformProof.add(pp);}}
            for(var entry:addedRails.entrySet()){Rail actual=sim.rails.stream().filter(v->v.getHexId().equals(entry.getValue().getHexId())).findFirst().orElseThrow();JsonObject rr=geometry(definitions.get(entry.getKey()),actual);rr.addProperty("native_id",actual.getHexId());members.add(member(dim,"rails",actual));railProof.add(rr);}
            retained(oldRails,sim.rails,"rail");retained(oldPlatforms,sim.platforms,"platform");retained(oldStations,sim.stations,"station");retained(oldRoutes,sim.routes,"route");retained(oldDepots,sim.depots,"depot");retained(oldSidings,sim.sidings,"siding");retained(oldLifts,sim.lifts,"lift");
            var currentOwnership=ownership(sim.platforms);for(var entry:oldOwnership.entrySet())need(entry.getValue().equals(currentOwnership.get(entry.getKey())),"Existing platform moved to another station");
            need(sim.routes.size()==oldRoutes.size()&&sim.depots.size()==oldDepots.size()&&sim.sidings.size()==oldSidings.size()&&sim.lifts.size()==oldLifts.size(),"Unexpected nonstation objects created");
            JsonObject proof=new JsonObject();proof.add("input_plan",spec);proof.addProperty("expected_native_members",expected);proof.addProperty("existing_loaded_objects_exact",true);proof.addProperty("existing_platform_station_membership_exact",true);proof.addProperty("existing_routes",oldRoutes.size());proof.addProperty("world_written",false);proof.addProperty("through_service_complete",false);proof.addProperty("ticks_run",0);proof.add("members",members);proof.add("stations",stationProof);proof.add("platforms",platformProof);proof.add("rails",railProof);
            sim.save();String receipt=GSON.toJson(proof);Files.writeString(out.resolve("native-station-set-proof.json"),receipt);Files.writeString(out.resolve("native-station-proof.json"),receipt);System.out.println("Prepared "+addedStations.size()+" stations and "+newPlatformIds.size()+" platforms; old objects retained; no service authored");
        }finally{sim.stop();}
    }
}

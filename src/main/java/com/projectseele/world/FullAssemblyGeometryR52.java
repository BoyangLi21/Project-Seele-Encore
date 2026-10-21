package com.projectseele.world;

import com.google.gson.*;
import com.google.gson.stream.JsonReader;
import com.projectseele.entity.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;
import com.projectseele.world.NervRouteReservationsR52.Original;
import com.projectseele.world.TransportMembershipR52.Kind;

/** Actual original EVA/capsule/Tripo surfaces plus the current native rider
 * collision body. Carrier render-state transforms are applied exactly once. */
public final class FullAssemblyGeometryR52
{
    private record Surface(String component,String source,TriangleSweepMeshR52 mesh){}
    private record NativePilot(UUID id,Vec3 halfExtents,Vec3 seatInEva){}
    private static volatile Provider installed;
    private record CheckedClasspath(Map<String,String> expected,Provider provider){}
    private static volatile CheckedClasspath checkedClasspath;
    @FunctionalInterface private interface StreamSource{InputStream open(String path)throws IOException;}
    /** Nonblocking status for the pure-resource warmup worker. No World or
     * entity access, and no monitor acquisition on the server tick. */
    public static boolean classpathReadyR52(){return checkedClasspath!=null;}
    public static void installClasspath()throws IOException
    {
        var root=JsonParser.parseString(new String(EvaOriginalMeshGeometryR52.classpathBytes("eva/full_assembly_geometry_r52_sources.json"),StandardCharsets.UTF_8)).getAsJsonObject();require(root.get("schema").getAsString().equals("projectseele.r52.full-assembly-geometry-sources.v1"),"Explicit actual assembly source receipt required");var hashes=new HashMap<String,String>();root.getAsJsonObject("resources").entrySet().forEach(e->hashes.put(e.getKey(),e.getValue().getAsString()));installClasspath(hashes);
    }
    public static void installClasspath(Map<String,String> expected)throws IOException
    {installed=selectedClasspathProviderR52(expected);}
    /** One immutable packaged selection. Publish only after every actual
     * resource checksum, skeleton and component assertion succeeds. Failed
     * or differently requested selections cannot replace/reuse this proof. */
    public static synchronized Provider selectedClasspathProviderR52(Map<String,String> expected)throws IOException
    {
        var selection=Map.copyOf(expected);var known=checkedClasspath;
        if(known!=null&&known.expected().equals(selection))return known.provider();
        var provider=loadStreams(EvaOriginalMeshGeometryR52::openClasspathResourceR52,selection);
        checkedClasspath=new CheckedClasspath(selection,provider);return provider;
    }
    public static Provider load(EvaOriginalMeshGeometryR52.ByteSource bytes,Map<String,String> expected)throws IOException
    {return loadStreams(path->new ByteArrayInputStream(bytes.read(path)),Map.copyOf(expected));}
    private static Provider loadStreams(StreamSource bytes,Map<String,String> expected)throws IOException
    {
        var receipt=new TreeMap<String,String>();var carrier=read(bytes,"mesh/tripo_carrier_r48.json",expected,receipt);var plugs=new HashMap<Integer,Map<String,double[]>>();
        String geoPath="geo/entry_plug_carrier.geo.json";byte[] geoBytes;try(var input=bytes.open(geoPath)){geoBytes=input.readAllBytes();}require(expected.containsKey(geoPath)&&expected.get(geoPath).equals(sha(geoBytes)),"Actual capsule GEO selection changed");receipt.put(geoPath,expected.get(geoPath));
        var geo=JsonParser.parseString(new String(geoBytes,StandardCharsets.UTF_8)).getAsJsonObject();var bones=geo.getAsJsonArray("minecraft:geometry").get(0).getAsJsonObject().getAsJsonArray("bones");var named=new HashSet<String>();var plugPivots=new HashMap<String,Vec3>();
        for(var value:bones){var b=value.getAsJsonObject();String name=b.get("name").getAsString();require(named.add(name),"Duplicate capsule bone");if(b.has("rotation"))for(var component:b.getAsJsonArray("rotation"))require(component.getAsDouble()==0,"Actual closed capsule has unsupported bind transform");if(!name.equals("entry_plug"))require(b.get("parent").getAsString().equals("entry_plug"),"Actual closed capsule parent changed");var pivot=b.getAsJsonArray("pivot");require(pivot!=null&&pivot.size()==3,"Actual capsule hinge pivot required");var p=new Vec3(-pivot.get(0).getAsDouble(),pivot.get(1).getAsDouble(),pivot.get(2).getAsDouble()).scale(EntryPlugKinematics.MODEL_TO_BLOCK);finite(p);plugPivots.put(name,p);}
        require(named.equals(Set.of("entry_plug","plug_hatch_l","plug_hatch_r","plug_crane_collar")),"Actual capsule skeleton incomplete");
        for(int v=0;v<3;v++)plugs.put(v,read(bytes,"mesh/entry_plug_unit0"+v+".mesh.json",expected,receipt).parts);
        require(carrier.parts.keySet().equals(Set.of("body","deck","contact_pads","service_platform"))&&carrier.anchors.containsKey("service_platform"),"Actual four-part Tripo carrier and hinge required");
        for(var entry:plugs.values())require(entry.keySet().equals(Set.of("entry_plug","plug_hatch_l","plug_hatch_r","plug_crane_collar")),"Actual complete original capsule required");
        var bearings=read(bytes,"mesh/carrier_sole_bearings_r52.json",expected,receipt).parts;require(bearings.keySet().equals(Set.of("sole_bearing_0_l","sole_bearing_0_r","sole_bearing_1_l","sole_bearing_1_r","sole_bearing_2_l","sole_bearing_2_r")),"Explicit six engineered sole-bearing parts required");
        var trim=read(bytes,"mesh/carrier_body_trimmed_r52.json",expected,receipt).parts;require(trim.keySet().equals(Set.of("body_trimmed_r52","upper_frame_cap_r52","interior_cut_caps_r52")),"Actual authorised cropped upper body and engineering steel cap required");
        var stow=read(bytes,"mesh/carrier_service_stow_r52.json",expected,receipt).parts;require(stow.containsKey("service_platform_stowed_r52")&&stow.keySet().stream().filter(n->n.startsWith("contact_pad_stowed_")).count()==6,"All original physical folded pads/platform required");var runningDeck=expected.containsKey(NervLegacyCarrierRideR52.DECK_SOURCE)?read(bytes,NervLegacyCarrierRideR52.DECK_SOURCE,expected,receipt).parts:Map.<String,double[]>of();if(!runningDeck.isEmpty())require(runningDeck.keySet().equals(Set.of("deck")),"Actual four-housing textured deck source required");if(expected.containsKey(NervLegacyCarrierRideR52.SOURCE)){String hash=digestResourceR52(bytes,NervLegacyCarrierRideR52.SOURCE);require(hash.equals(expected.get(NervLegacyCarrierRideR52.SOURCE)),"Selected four-slide/fixed-head source changed");receipt.put(NervLegacyCarrierRideR52.SOURCE,hash);}return new Provider(carrier.parts,carrier.anchors,Map.copyOf(plugs),bearings,trim,stow,runningDeck,plugPivots,sha(receipt.toString().getBytes(StandardCharsets.UTF_8)));
    }
    private record Imported(Map<String,double[]> parts,Map<String,Vec3> anchors){}
    private static Imported read(StreamSource source,String path,Map<String,String> expected,Map<String,String> receipt)throws IOException
    {
        String hash=expected.get(path);require(hash!=null&&hash.matches("[0-9a-f]{64}"),"Actual assembly resource SHA required: "+path);
        var parts=new LinkedHashMap<String,double[]>();var anchors=new HashMap<String,Vec3>();boolean carrier=path.contains("tripo_carrier")||path.equals("mesh/carrier_sole_bearings_r52.json")||path.equals("mesh/carrier_body_trimmed_r52.json")||path.equals("mesh/carrier_service_stow_r52.json")||path.equals(NervLegacyCarrierRideR52.DECK_SOURCE);int stride=-1;
        var digest=newDigestR52();
        try(var input=new java.security.DigestInputStream(source.open(path),digest);var json=new JsonReader(new InputStreamReader(input,StandardCharsets.UTF_8)))
        {
            json.beginObject();while(json.hasNext())switch(json.nextName())
            {
                case "stride" -> stride=json.nextInt();
                case "anchors" -> {json.beginObject();while(json.hasNext()){String name=json.nextName();json.beginArray();var p=new Vec3(json.nextDouble(),json.nextDouble(),json.nextDouble());json.endArray();finite(p);anchors.put(name,p);}json.endObject();}
                case "parts" ->
                {
                    json.beginObject();while(json.hasNext())
                    {
                        String name=json.nextName();double[] values;Vec3 pivot=Vec3.ZERO;
                        if(carrier)values=positions(json);
                        else{double[] raw=null;json.beginObject();while(json.hasNext())switch(json.nextName()){case "pivot"->{json.beginArray();pivot=new Vec3(json.nextDouble(),json.nextDouble(),json.nextDouble());json.endArray();finite(pivot);}case "vertices"->raw=positions(json);default->json.skipValue();}json.endObject();require(raw!=null,"Actual capsule triangles absent");values=raw;}
                        if(!carrier)for(int n=0;n<values.length;n+=3){values[n]=-(values[n]+pivot.x)*EntryPlugKinematics.MODEL_TO_BLOCK;values[n+1]=(values[n+1]+pivot.y)*EntryPlugKinematics.MODEL_TO_BLOCK;values[n+2]=(values[n+2]+pivot.z)*EntryPlugKinematics.MODEL_TO_BLOCK;}
                        require(parts.putIfAbsent(name,values)==null,"Duplicate original component");
                    }
                    json.endObject();
                }
                default -> json.skipValue();
            }
            json.endObject();require(stride==8&&!parts.isEmpty(),"Actual triangle stride8 required");
            // Reader buffering already contributes to this digest. Drain any
            // remaining bytes so trailing bytes are checked as in ByteSource.
            input.transferTo(OutputStream.nullOutputStream());
            require(hash.equals(HexFormat.of().formatHex(digest.digest())),"Actual assembly resource changed: "+path);
        }
        receipt.put(path,hash);
        return new Imported(Map.copyOf(parts),Map.copyOf(anchors));
    }
    private static MessageDigest newDigestR52(){try{return MessageDigest.getInstance("SHA-256");}catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}}
    private static String digestResourceR52(StreamSource source,String path)throws IOException
    {var digest=newDigestR52();try(var input=new java.security.DigestInputStream(source.open(path),digest)){input.transferTo(OutputStream.nullOutputStream());}return HexFormat.of().formatHex(digest.digest());}
    private static double[] positions(JsonReader json)throws IOException
    {
        var chunks=new ArrayList<double[]>();int count=0;json.beginArray();while(json.hasNext())
        {float value=Float.parseFloat(json.nextString());require(Float.isFinite(value),"Nonfinite original triangle source");if(count%8192==0)chunks.add(new double[8192]);chunks.get(count/8192)[count%8192]=value;count++;}json.endArray();require(count>0&&count%24==0,"Incomplete original triangle surface");
        double[] xyz=new double[count/8*3];for(int v=0;v<count/8;v++)for(int axis=0;axis<3;axis++){int at=v*8+axis;xyz[v*3+axis]=chunks.get(at/8192)[at%8192];}return xyz;
    }
    public static final class Provider
    {
        private final Map<String,double[]> carrier,bearings,trim,stow,runningDeck;private final Map<String,Vec3> anchors,plugPivots;private final Map<Integer,Map<String,double[]>> plugs;private final String source;
        private Provider(Map<String,double[]> carrier,Map<String,Vec3> anchors,Map<Integer,Map<String,double[]>> plugs,Map<String,double[]> bearings,Map<String,double[]> trim,Map<String,double[]> stow,Map<String,double[]> runningDeck,Map<String,Vec3> plugPivots,String source){this.runningDeck=runningDeck;this.carrier=carrier;this.anchors=anchors;this.plugs=plugs;this.bearings=bearings;this.trim=trim;this.stow=stow;this.plugPivots=Map.copyOf(plugPivots);this.source=source;}
        public String sourceFingerprint(){var selected=CarrierAssemblyR53.selected();return selected==null?source:sha((source+selected.fingerprint()).getBytes(StandardCharsets.UTF_8));}
        public boolean selectedRunningDeckR52(){return runningDeck.keySet().equals(Set.of("deck"));}
        /** Pure source transform evaluator for actual renderer comparison.
         * Native capture admits only fully raised/release-free machinery. */
        public Map<String,double[]> carrierParts(float rise,boolean recoveryRack,float release)
        {return carrierParts(rise,recoveryRack,release,recoveryRack?3:0);}
        public Map<String,double[]> carrierParts(float rise,boolean recoveryRack,float release,double deckTravel)
        {
            var selected=CarrierAssemblyR53.selected();
            if(selected!=null)return selected.posed(rise,release,deckTravel);
            require(deckTravel==0||deckTravel==3||deckTravel==64,"Actual declared deck travel required");
            require(Float.isFinite(rise)&&rise>=0&&rise<=1&&Float.isFinite(release)&&release>=0&&release<=1,"Actual carrier render channels required");var result=new LinkedHashMap<String,double[]>();
            for(var entry:carrier.entrySet())
            {
                String name=entry.getKey();var frame=RigidTransform.identity();
                if(name.equals("deck")){if(deckTravel>0)frame=new RigidTransform(new Vec3(0,-deckTravel*(1-rise),0),0,0,0,1);}
                else
                {
                    frame=new RigidTransform(new Vec3(0,-64*(1-rise),0),0,0,0,1);
                    if(name.equals("contact_pads"))frame=frame.compose(new RigidTransform(new Vec3(0,0,1.5F*release),0,0,0,1));
                    if(name.equals("service_platform")){var hinge=anchors.get(name);var turn=RigidTransform.of(Vec3.ZERO,new Quaternionf().rotationZ(-(float)Math.PI/2));frame=frame.compose(new RigidTransform(hinge.subtract(turn.transformVector(hinge)),turn.qx(),turn.qy(),turn.qz(),turn.qw()));}
                }
                result.put(name,transform(entry.getValue(),frame));
            }
            return Collections.unmodifiableMap(result);
        }
        /** Root-engineered steel shoes are distinct from every original Tripo
         * part and use the same 64m actuator and the exact rendered triangles. */
        public Map<String,double[]> carrierParts(int variant,float rise,boolean recoveryRack,float release,double deckTravel)
        {
            if(NervR50CarrierModeR53.enabled())return carrierParts(rise,recoveryRack,release,0);
            var result=new LinkedHashMap<>(carrierParts(rise,recoveryRack,release,deckTravel));if(deckTravel==64){require(variant>=0&&variant<3,"Actual sole-bearing variant required");var frame=new RigidTransform(new Vec3(0,-64*(1-rise),0),0,0,0,1);if(selectedRunningDeckR52())result.put("deck",transform(runningDeck.get("deck"),frame));result.remove("body");result.remove("contact_pads");result.remove("service_platform");stow.forEach((name,xyz)->result.put(name,transform(xyz,frame)));trim.forEach((name,xyz)->result.put(name,transform(xyz,frame)));for(String side:List.of("l","r")){String name="sole_bearing_"+variant+"_"+side;result.put(name,transform(bearings.get(name),frame));}}return Collections.unmodifiableMap(result);
        }
        public Map<String,double[]> closedPlugParts(int variant)
        {var source=plugs.get(variant);require(source!=null,"Original capsule variant absent");var result=new LinkedHashMap<String,double[]>();source.forEach((n,p)->{if(!n.equals("plug_crane_collar"))result.put(n,p.clone());});return Collections.unmodifiableMap(result);}
        /** Same two hinge pivots and opposed Z rotations as EntryPlugCarrierRenderer. */
        public RigidTransform plugPartFrameR53(String part,float hatch)
        {
            require(Float.isFinite(hatch)&&hatch>=0&&hatch<=1&&plugPivots.containsKey(part),"Actual capsule part and hatch clock required");
            if(hatch==0||!part.startsWith("plug_hatch_"))return RigidTransform.identity();
            float angle=(float)Math.toRadians(EntryPlugKinematics.HATCH_OPEN_ANGLE_DEGREES*hatch*(part.equals("plug_hatch_l")?1:-1));
            var pivot=plugPivots.get(part);var rotation=RigidTransform.of(Vec3.ZERO,new Quaternionf().rotationZ(angle));
            return new RigidTransform(pivot.subtract(rotation.transformVector(pivot)),rotation.qx(),rotation.qy(),rotation.qz(),rotation.qw());
        }
    }
    public static Captured capture(ServerLevel level,Original original,EvaOriginalMeshGeometryR52.Geometry actualEva,FootSupportFrameR52.Binding binding,FootSupportFrameR52.Sample actualFrame)
    {
        var provider=installed;require(provider!=null,"Root original capsule/carrier source not installed");
        require(level.getEntity(original.eva()) instanceof EvaUnit01Entity&&level.getEntity(original.plug()) instanceof EntryPlugCarrierEntity&&level.getEntity(original.pilot()) instanceof LivingEntity,"Actual loaded original assembly absent");
        var eva=(EvaUnit01Entity)level.getEntity(original.eva());var plug=(EntryPlugCarrierEntity)level.getEntity(original.plug());var pilot=(LivingEntity)level.getEntity(original.pilot());
        require(eva.getUnitVariant()==original.variant()&&actualEva.variant()==original.variant()&&plug.getAssignedVariant()==original.variant()
                &&plug.getVehicle()==eva&&pilot.getVehicle()==plug&&plug.getFirstPassenger()==pilot&&plug.isLockedToEva()&&plug.isHatchFullySealed()&&plug.getHatchOpenAmount()==0
                &&plug.usesPhysicalPilotSeatR52()&&eva.carrierRiseProgress(1)==1&&eva.getLaunchPhase()!=EvaUnit01Entity.LAUNCH_CLEAR,"Actual original seated/closed/fully raised mechanical interlocks required");
        require(same(plug.getCanonicalTransform(),actualFrame.plugWorld())&&same(actualFrame.evaRoot().compose(binding.plugInEva()),actualFrame.plugWorld()),"Original capsule is not on this same rigid sample");
        var current=pilot.getBoundingBox();var seatInEva=binding.plugInEva().transformPoint(EntryPlugKinematics.PILOT_SEAT_P);var expected=actualFrame.evaRoot().transformPoint(seatInEva);
        require(current.getCenter().distanceToSqr(expected)<=1e-10,"Actual native pilot body is not at the physical capsule seat");
        var surfaces=new ArrayList<Surface>();for(var part:actualEva.parts())surfaces.add(new Surface("eva/"+part.bone(),actualEva.sourceFingerprint(),new TriangleSweepMeshR52(part.triangles())));
        provider.carrierParts(eva.getUnitVariant(),1,eva.recoveryRackR39(),0,EvaMechanicalFrameR52.carrierDeckTravelR52(eva)).forEach((n,p)->surfaces.add(new Surface("carrier/"+n,provider.sourceFingerprint(),new TriangleSweepMeshR52(p))));
        provider.closedPlugParts(original.variant()).forEach((n,p)->surfaces.add(new Surface("capsule/"+n,provider.sourceFingerprint(),new TriangleSweepMeshR52(transform(p,binding.plugInEva())))));
        return new Captured(original,binding,List.copyOf(surfaces),new NativePilot(original.pilot(),new Vec3(current.getXsize()/2,current.getYsize()/2,current.getZsize()/2),seatInEva),actualEva.sourceFingerprint()+":"+provider.sourceFingerprint(),Kind.OCCUPIED);
    }
    /** Only the original stopped empty hull and its actual carrier are carried.
     * Original capsule/pilot UUIDs remain provenance; neither is queried as a
     * virtual rider, moved, excluded from world collision, or reconstructed. */
    public static Captured captureHullRecovery(ServerLevel level,Original original,EvaOriginalMeshGeometryR52.Geometry actualFrozenHull,FootSupportFrameR52.Binding binding)
    {
        var provider=installed;require(provider!=null,"Original physical carrier source not installed");
        require(level.getEntity(original.eva()) instanceof EvaUnit01Entity,"Original loaded hull absent");var eva=(EvaUnit01Entity)level.getEntity(original.eva());
        require(actualFrozenHull.variant()==original.variant()&&eva.getUnitVariant()==original.variant()&&!eva.isExperimentalUnit()&&eva.getPassengers().isEmpty()
                &&!eva.isEntryPlugInserted()&&eva.carrierRiseProgress(1)==1&&eva.getLaunchPhase()!=EvaUnit01Entity.LAUNCH_CLEAR
                &&EntryPlugEjectionR48.originalFieldEjection(level,original.variant(),eva,original.pilot())&&TransportMembershipR52.originalEjectionReceipts(original,eva.getPersistentData()),"Actual stopped original ejected hull/raised carrier required");
        var surfaces=new ArrayList<Surface>();for(var part:actualFrozenHull.parts())surfaces.add(new Surface("eva/"+part.bone(),actualFrozenHull.sourceFingerprint(),new TriangleSweepMeshR52(part.triangles())));
        provider.carrierParts(eva.getUnitVariant(),1,eva.recoveryRackR39(),0,EvaMechanicalFrameR52.carrierDeckTravelR52(eva)).forEach((n,p)->surfaces.add(new Surface("carrier/"+n,provider.sourceFingerprint(),new TriangleSweepMeshR52(p))));
        return new Captured(original,binding,List.copyOf(surfaces),null,actualFrozenHull.sourceFingerprint()+":"+provider.sourceFingerprint(),Kind.HULL_ONLY_RECOVERY);
    }
    public static final class Captured
    {
        private final Original original;private final FootSupportFrameR52.Binding binding;private final List<Surface> surfaces;private final NativePilot pilot;private final String source;private final Kind kind;
        private Captured(Original original,FootSupportFrameR52.Binding binding,List<Surface> surfaces,NativePilot pilot,String source,Kind kind){this.original=original;this.binding=binding;this.surfaces=surfaces;this.pilot=pilot;this.source=source;this.kind=kind;}
        public CheckedAssemblySweep sweep(NervRouteDirectoryR52 directory,NervRouteDirectoryR52.Leg leg,double from,double to,double maximumError)
        {return new CheckedAssemblySweep(this,List.of(new DirectoryTrajectoryR52(directory,leg,binding,from,to)),maximumError);}
        public CheckedAssemblySweep sweep(List<DirectoryTrajectoryR52> paths,double maximumError)
        {return new CheckedAssemblySweep(this,paths,maximumError);}
    }
    /** Concrete immutable proof input. It contains source geometry and the
     * real directory curve; no arbitrary Boolean/callback can claim clearance. */
    public static final class CheckedAssemblySweep
    {
        private final Captured assembly;private final List<DirectoryTrajectoryR52> trajectories;private final DirectoryTrajectoryR52 trajectory;private final double maximumError;private final List<AABB> envelopes;
        private final Map<DirectoryTrajectoryR52,List<TriangleSweepMeshR52.PreparedSweep>> prepared=new IdentityHashMap<>();
        private record PilotSegment(double from,double to,AABB box){}
        private record SweptPiece(AABB bounds,TriangleSweepMeshR52.PreparedSweep mesh,List<PilotSegment> pilot,String component,DirectoryTrajectoryR52 path){}
        private final NervStaticSpatialIndexR52<SweptPiece> pieceIndex;
        private String clearanceHoldR53="assembly_state";private SweptPiece intersectedPieceR53;
        public String clearanceHoldR53(){return clearanceHoldR53;}
        private boolean collisionHeldR53(String obstacle){clearanceHoldR53=obstacle+(intersectedPieceR53==null?"":" component="+intersectedPieceR53.component()+" leg="+intersectedPieceR53.path().leg().id()+" interval="+intersectedPieceR53.path().fromFraction()+".."+intersectedPieceR53.path().toFraction());return false;}
        private CheckedAssemblySweep(Captured assembly,List<DirectoryTrajectoryR52> paths,double maximumError)
        {
            require(paths!=null&&!paths.isEmpty()&&paths.size()<=2048,"Bounded declared composite trajectory required");
            this.assembly=assembly;this.trajectories=List.copyOf(paths);this.trajectory=paths.get(0);this.maximumError=maximumError;var boxes=new ArrayList<AABB>();var pieces=new ArrayList<SweptPiece>();
            FootSupportFrameR52.Sample previous=null;
            for(var path:trajectories){require(path.directory().fingerprint().equals(trajectory.directory().fingerprint())&&path.binding().equals(assembly.binding),"Composite source/binding changed");if(previous!=null)require(sampleMatches(previous,path.sample(0)),"Disconnected composite trajectory");previous=path.sample(1);
                var meshes=new ArrayList<TriangleSweepMeshR52.PreparedSweep>();
                for(var surface:assembly.surfaces){var bounds=surface.mesh.envelope(path);boxes.add(bounds);path.divisions(surface.mesh.bounds().getCenter().distanceTo(path.footCentreLocal())+Math.sqrt(Math.pow(surface.mesh.bounds().getXsize(),2)+Math.pow(surface.mesh.bounds().getYsize(),2)+Math.pow(surface.mesh.bounds().getZsize(),2))/2,maximumError);var mesh=surface.mesh.prepare(path,maximumError);meshes.add(mesh);pieces.add(new SweptPiece(bounds,mesh,List.of(),surface.component(),path));}
                prepared.put(path,List.copyOf(meshes));
                if(assembly.pilot!=null){var p=assembly.pilot;var bounds=pilotEnvelope(p,path);boxes.add(bounds);double radius=p.seatInEva.distanceTo(path.footCentreLocal());int divisions=path.divisions(radius,maximumError);double error=path.error(radius,divisions);var segments=new ArrayList<PilotSegment>();
                    for(int i=0;i<divisions;i++){double from=(double)i/divisions,to=(double)(i+1)/divisions;var a=path.sample(from).evaRoot().transformPoint(p.seatInEva);var b=path.sample(to).evaRoot().transformPoint(p.seatInEva);segments.add(new PilotSegment(from,to,pilotBox(p,a).minmax(pilotBox(p,b)).inflate(error)));}
                    // Index the same conservative pilot chords used by narrow phase.
                    for(var segment:segments)bounds=bounds.minmax(segment.box());pieces.add(new SweptPiece(bounds,null,List.copyOf(segments),"pilot",path));}}
            envelopes=List.copyOf(boxes);pieceIndex=new NervStaticSpatialIndexR52<>(pieces,SweptPiece::bounds);
        }
        public List<DirectoryTrajectoryR52> trajectories(){return trajectories;}
        public String sourceFingerprint(){return assembly.source;}
        public List<AABB> envelopes(){return envelopes;}
        public Kind kind(){return assembly.kind;}
        public Set<UUID> originalIds(){return TransportMembershipR52.members(assembly.original,assembly.kind);}
        public boolean matches(Original original,NervRouteDirectoryR52 directory,NervRouteDirectoryR52.Leg leg,double from,double to)
        {return trajectories.size()==1&&assembly.original.equals(original)&&trajectory.directory().fingerprint().equals(directory.fingerprint())&&trajectory.leg().equals(leg)&&trajectory.fromFraction()==from&&trajectory.toFraction()==to;}
        public boolean matchesSlices(Original original,List<DirectoryTrajectoryR52> paths)
        {if(!assembly.original.equals(original)||paths.size()!=trajectories.size())return false;for(int i=0;i<paths.size();i++){var a=paths.get(i);var b=trajectories.get(i);if(!a.directory().fingerprint().equals(b.directory().fingerprint())||!a.leg().equals(b.leg())||a.fromFraction()!=b.fromFraction()||a.toFraction()!=b.toFraction()||!a.binding().equals(b.binding()))return false;}return true;}
        public boolean matchesSamples(FootSupportFrameR52.Sample from,FootSupportFrameR52.Sample to)
        {return sampleMatches(trajectory.sample(0),from)&&sampleMatches(trajectories.get(trajectories.size()-1).sample(1),to);}
        public boolean clear(ServerLevel level,Entity eva)
        {
            if(!(eva instanceof EvaUnit01Entity unit)||unit.carrierRiseProgress(1)!=1||unit.getLaunchPhase()==EvaUnit01Entity.LAUNCH_CLEAR
                    ||!assembly.source.startsWith(EvaAirTransportR31.cradleStateR50(unit).getString("GeometrySourceR52")+":"))return false;
            if(!EvaMechanicalFrameR52.active(unit)||!same(EvaMechanicalFrameR52.frame(unit,1),trajectory.sample(0).evaRoot()))return false;
            if(assembly.kind==Kind.HULL_ONLY_RECOVERY)
            {if(!unit.getPassengers().isEmpty()||unit.isEntryPlugInserted()||!EntryPlugEjectionR48.originalFieldEjection(level,assembly.original.variant(),unit,assembly.original.pilot()))return false;}
            else
            {
            var pilot=level.getEntity(assembly.original.pilot());var plug=level.getEntity(assembly.original.plug());
            if(!(pilot instanceof LivingEntity)||!pilot.isAlive()||!(plug instanceof EntryPlugCarrierEntity capsule)||!capsule.usesPhysicalPilotSeatR52()||!capsule.isHatchFullySealed()
                    )return false;
            var half=assembly.pilot.halfExtents;var actual=pilot.getBoundingBox();if(Math.abs(actual.getXsize()-half.x*2)>1e-8||Math.abs(actual.getYsize()-half.y*2)>1e-8||Math.abs(actual.getZsize()-half.z*2)>1e-8)return false;
            if(pilot.getVehicle()!=capsule||capsule.getVehicle()!=eva||capsule.getFirstPassenger()!=pilot||!same(capsule.getCanonicalTransform(),trajectory.sample(0).plugWorld())
                    ||actual.getCenter().distanceToSqr(trajectory.sample(0).evaRoot().transformPoint(assembly.pilot.seatInEva))>1e-10
                    )return false;
            }
            var own=originalIds();var actors=new LinkedHashMap<UUID,Entity>();var testedBlocks=new HashSet<AABB>();
            var blocks=BoundedNativeCollisionGroupsR52.clear(envelopes,
                    box->EntryPlugEjectionR48.loaded(level,box),
                    box->{var shapes=new ArrayList<AABB>();for(var shape:level.getBlockCollisions(eva,box))shapes.addAll(shape.toAabbs());return shapes;},
                    (piece,obstacle)->{if(!testedBlocks.add(obstacle)||!intersects(obstacle))return false;collisionHeldR53("native_block="+obstacle);return true;});
            if(!blocks.clear())return false;
            for(var box:envelopes)
            {
                // Machinery's native entity origin can be well outside its
                // actual wing, closed leaf or gantry. Query it once, then use
                // the real hollow source rather than its broadphase box.
                for(var entity:level.getEntities((Entity)null,box.inflate(200),e->!own.contains(e.getUUID())&&!NervOriginalCarrierR52.isCapturedMemberR52(unit,e)&&e.isAlive()&&!e.isSpectator()
                        &&(e instanceof LivingEntity||e.canBeCollidedWith()||e instanceof UNTransportEntity
                        ||e instanceof EntryPlugCarrierEntity||e instanceof NervSiloDoorEntity||e instanceof NervHangarDoorEntity||e instanceof NervCarrierPlatformEntity)))
                    actors.putIfAbsent(entity.getUUID(),entity);
            }
            for(var actor:actors.values())
            {
                var meshes=NervFlightProofR52.actualObstacleMeshes(actor);
                if(meshes==null)return collisionHeldR53("actor_source_missing="+actor.getUUID());
                if(meshes.isEmpty()){if(intersects(actor.getBoundingBox()))return collisionHeldR53("actor_body="+actor.getUUID());}
                else for(var mesh:meshes)if(intersects(mesh))return collisionHeldR53("actor_mesh="+actor.getUUID()+" bounds="+mesh.mesh().envelope(mesh.frame(),mesh.endFrame()));
            }
            var detached=NervFlightProofR52.detachedCarrierObstacles(level);if(detached==null)return false;
            for(var mesh:detached)if(intersects(mesh))return collisionHeldR53("detached_mesh="+mesh.frame());
            clearanceHoldR53="";
            return true;
        }
        private boolean intersects(NervFlightProofR52.ObstacleMesh obstacle)
        {
            AABB bounds=obstacle.mesh().envelope(obstacle.frame(),obstacle.endFrame());
            if((trajectories.size()>1||trajectory.pureTranslation())&&!same(obstacle.frame(),obstacle.endFrame()))return intersects(bounds);
            for(var piece:pieceIndex.query(bounds)){
                if(piece.mesh()!=null){if(piece.mesh().intersects(obstacle.mesh(),obstacle.frame(),obstacle.endFrame())){intersectedPieceR53=piece;return true;}}
                else for(var segment:piece.pilot())if(segment.box().intersects(bounds)&&obstacle.mesh().intersects(obstacle.frame().interpolate(obstacle.endFrame(),segment.from()),obstacle.frame().interpolate(obstacle.endFrame(),segment.to()),segment.box(),maximumError)){intersectedPieceR53=piece;return true;}}
            return false;
        }
        private boolean intersects(AABB obstacle)
        {
            for(var piece:pieceIndex.query(obstacle)){
                if(piece.mesh()!=null){if(piece.mesh().intersects(obstacle)){intersectedPieceR53=piece;return true;}}
                else for(var segment:piece.pilot())if(segment.box().intersects(obstacle)){intersectedPieceR53=piece;return true;}}
            return false;
        }
    }
    private static AABB pilotBox(NativePilot pilot,Vec3 centre){var h=pilot.halfExtents;return new AABB(centre.subtract(h),centre.add(h));}
    private static AABB pilotEnvelope(NativePilot pilot,DirectoryTrajectoryR52 path)
    {double radius=pilot.seatInEva.distanceTo(path.footCentreLocal());return pilotBox(pilot,path.sample(0).evaRoot().transformPoint(pilot.seatInEva)).minmax(pilotBox(pilot,path.sample(1).evaRoot().transformPoint(pilot.seatInEva))).inflate(path.error(radius,1));}
    private static double[] transform(double[] source,RigidTransform frame)
    {var result=new double[source.length];for(int n=0;n<source.length;n+=3){var p=frame.transformPoint(new Vec3(source[n],source[n+1],source[n+2]));result[n]=p.x;result[n+1]=p.y;result[n+2]=p.z;}return result;}
    private static boolean same(RigidTransform a,RigidTransform b){return a.translation().distanceToSqr(b.translation())<=1e-10&&a.rotationErrorDegrees(b)<.0001;}
    private static boolean sampleMatches(FootSupportFrameR52.Sample a,FootSupportFrameR52.Sample b)
    {return same(a.evaRoot(),b.evaRoot())&&same(a.plugWorld(),b.plugWorld())&&a.leftContact().distanceToSqr(b.leftContact())<=1e-10&&a.rightContact().distanceToSqr(b.rightContact())<=1e-10;}
    private static void finite(Vec3 p){require(Double.isFinite(p.x)&&Double.isFinite(p.y)&&Double.isFinite(p.z),"Actual finite anchor required");}
    private static String sha(byte[] bytes){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}catch(Exception impossible){throw new IllegalStateException(impossible);}}
    private static void require(boolean ok,String why){if(!ok)throw new IllegalStateException(why);}
    private FullAssemblyGeometryR52(){}
}

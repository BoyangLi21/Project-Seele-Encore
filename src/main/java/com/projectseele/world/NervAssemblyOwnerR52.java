package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import com.projectseele.registry.ModEntities;
import java.nio.file.*;
import java.util.*;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.*;
import net.minecraft.world.entity.*;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.*;
import com.projectseele.world.NervRouteDirectoryR52.*;
import com.projectseele.world.NervRouteNativeR52.*;
import com.projectseele.world.NervRouteReservationsR52.Original;
import com.projectseele.world.TransportMembershipR52.Kind;

/** One explicitly commissioned Root plant reuses the original preparation
 * clocks/entities. This is not an autonomous installer or another scheduler. */
public final class NervAssemblyOwnerR52 implements AssemblyOwner,NervOriginalActorsR52.Access,NervFlightProofR52.Owner
{
    public static final String SCHEMA="projectseele.r52.mechanical-owner.v1";
    public static UUID proposedGateIdentityR53(long epoch,String resource)
    {
        require(epoch>0&&resource!=null&&resource.matches("[A-Za-z0-9_./:-]{1,160}"),"Explicit actual gate epoch/resource required");
        return UUID.nameUUIDFromBytes(("projectseele:r53:gate:"+epoch+":"+resource).getBytes(java.nio.charset.StandardCharsets.UTF_8));
    }
    enum Prepare { HATCH,BRIDGE,INSERT,SEAL,DRAIN,LOWER_FRAME_OPEN,PIT_OPEN,FRONT_SEAL_OPEN,SERVICE_BRIDGE_OPEN,RAISE,RELEASE_CLAMPS,READY,FRONT_RECOVER_CLAMPS,FRONT_RECOVER_LOWER,FRONT_RECOVER_BRIDGE }
    private enum Finish { RECEIVE,LOWER,SERVICE_BRIDGE_CLOSE,FRONT_SEAL_CLOSE,PIT_CLOSE,LOWER_FRAME_CLOSE,EXTRACT,REFILL,BRIDGE,EJECT_LOWER,EJECT_CLOSE,LAND,RELEASE,DONE }
    public enum GateKind { HANGAR,SILO }
    public record Cell(BlockPos at,BlockState closed,BlockState open){}
    public record FixedCell(BlockPos at,BlockState expected){}
    public record Visual(UUID id,RigidTransform frame,List<FixedCell> supports){public Visual{supports=List.copyOf(supports);}}
    public record Crane(Visual visual,RigidTransform stow,double initialBottom,double stowBottom,Vec3 railAxis,double railMin,double railMax,double hoistStep,List<FixedCell> frameCells){public Crane{frameCells=List.copyOf(frameCells);}}
    public record Gate(String resource,UUID visual,GateKind kind,int variant,int stage,RigidTransform frame,float width,float height,List<List<Cell>> collisionSteps,List<FixedCell> supports,SiloHatchMechanism.Spec siloHatch,NervHangarGateGeometryR52.Spec hangarStack)
    {public Gate{collisionSteps=collisionSteps.stream().map(List::copyOf).toList();supports=List.copyOf(supports);}public Gate(String resource,UUID visual,GateKind kind,int variant,int stage,RigidTransform frame,float width,float height,List<List<Cell>> collisionSteps,List<FixedCell> supports){this(resource,visual,kind,variant,stage,frame,width,height,collisionSteps,supports,null,null);}public Gate(String resource,UUID visual,GateKind kind,int variant,int stage,RigidTransform frame,float width,float height,List<List<Cell>> collisionSteps,List<FixedCell> supports,SiloHatchMechanism.Spec siloHatch){this(resource,visual,kind,variant,stage,frame,width,height,collisionSteps,supports,siloHatch,null);}}
    public record HullHandoff(List<FixedCell> supports,int lowerTicks){public HullHandoff{supports=List.copyOf(supports);require(!supports.isEmpty()&&lowerTicks>0,"Actual fallen-hull receiver required");}}
    public record UnitPlant(int variant,UUID eva,UUID plug,UUID npc,UUID seat,RigidTransform bay,RigidTransform dock,Vec3 boarding,List<Vec3> dismount,List<List<FixedCell>> bridgeStates,List<List<Cell>> lcl,Visual gantry,Crane crane,List<FixedCell> carrierSupport,int raiseTicks,RigidTransform seatFrame,List<FixedCell> chair,Vec3 phone,Vec3 standby,List<Vec3> boardPath,List<Vec3> returnPath,double boardingRadius,HullHandoff hullHandoff,List<List<Cell>> personnelDoors)
    {public UnitPlant{dismount=List.copyOf(dismount);bridgeStates=bridgeStates.stream().map(List::copyOf).toList();lcl=lcl.stream().map(List::copyOf).toList();carrierSupport=List.copyOf(carrierSupport);boardPath=List.copyOf(boardPath);returnPath=List.copyOf(returnPath);chair=List.copyOf(chair);personnelDoors=personnelDoors.stream().map(List::copyOf).toList();}}
    private final NervRouteDirectoryR52 directory;
    private final Map<Integer,UnitPlant> units;
    private final Map<String,Gate> gates;
    private final Map<String,List<FixedCell>> resources;
    public record Receiver(String port,Region region,AABB domain,RigidTransform stoppedFrame,List<FixedCell> supports,List<String> gates,int carrierTicks)
    {public Receiver{supports=List.copyOf(supports);gates=List.copyOf(gates);}}
    private final Map<String,Receiver> receivers;
    private Map<Integer,String> servicePits=Map.of();
    private Map<String,List<Cell>> wetFloorSealsR52=Map.of();
    private Set<Integer> lowerFrames=Set.of();
    private boolean groundGuidesDeclared;
    private boolean continuousGuidesR52;
    private String continuousGuidePathsShaR52="";
    private Map<Integer,UUID> carrierControllers=Map.of();
    private Map<String,Double> dockFoundationsR52=Map.of();
    private List<StaffBinding> staff=List.of();
    public record StaffBinding(UUID original,NervStaffDirector.Station station,List<FixedCell> support){public StaffBinding{support=List.copyOf(support);}}
    private final String cageSourceSha;
    private final boolean installed;
    private final long epoch;
    private boolean commissioned;
    private final Map<UUID,FullAssemblyGeometryR52.Captured> captured=new HashMap<>();
    private final Map<UUID,NervBallisticHandoffR52.Proof> ballistic=new HashMap<>();
    private final Map<UUID,NervHullPreviewR52> previews=new HashMap<>();
    private final Map<UUID,EvaMechanicalFrameR52.OccupiedCapture> occupiedPreviews=new HashMap<>();
    private final Map<UUID,String> holds=new HashMap<>();
    private final Map<UUID,Long> capsuleTicks=new HashMap<>();
    private final Map<UUID,Integer> pilotNodes=new HashMap<>();
    private final Map<UUID,String> pilotOperations=new HashMap<>();
    private final Map<UUID,Long> receiverTicks=new HashMap<>();
    private final Map<String,Long> gateTicks=new HashMap<>();
    private NervCraneGeometryR52 craneGeometry;
    private PreparedGeometryR52 preparedGeometryR52;
    record PreparedGeometryR52(NervCraneGeometryR52 crane,NervCraneSweepR52 sweep){}
    record SourceUnitR52(int variant,RigidTransform bay){}
    record GeometryRequestR52(String cage,List<SourceUnitR52> units,List<SiloHatchMechanism.Spec> silos,List<NervHangarGateGeometryR52.Spec> hangars,boolean ground){
        GeometryRequestR52{units=List.copyOf(units);silos=List.copyOf(silos);hangars=List.copyOf(hangars);}
        String selectionKey(){try{return HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(toString().getBytes(java.nio.charset.StandardCharsets.UTF_8)));}catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}}
    }
    private GeometryRequestR52 geometryRequestR52(){return new GeometryRequestR52(cageSourceSha,units.values().stream().map(p->new SourceUnitR52(p.variant(),p.bay())).toList(),gates.values().stream().filter(g->g.siloHatch()!=null).map(Gate::siloHatch).toList(),gates.values().stream().filter(g->g.hangarStack()!=null).map(Gate::hangarStack).toList(),groundGuidesDeclared);}
    static GeometryRequestR52 geometryRequestR52(JsonObject document){
        var units=new ArrayList<SourceUnitR52>();for(var raw:document.getAsJsonArray("units")){var p=raw.getAsJsonObject();units.add(new SourceUnitR52(p.get("variant").getAsInt(),frame(p.getAsJsonObject("bay_frame"))));}
        var silos=new ArrayList<SiloHatchMechanism.Spec>();var hangars=new ArrayList<NervHangarGateGeometryR52.Spec>();for(var raw:document.getAsJsonArray("gates")){var g=raw.getAsJsonObject();if(g.has("silo_hatch"))silos.add(siloSpec(g.getAsJsonObject("silo_hatch")));if(g.has("hangar_stack"))hangars.add(hangarSpec(g));}
        return new GeometryRequestR52(document.getAsJsonObject("mechanism_sources").get("mesh/tv_shoulder_shells_r44.json").getAsString(),units,silos,hangars,document.has("ground_guides"));
    }
    /** CPU geometry only: no Level, Entity, native collision shape or GPU call. */
    static PreparedGeometryR52 prepareGeometryR52(GeometryRequestR52 request)throws java.io.IOException {
        EvaMechanicalFrameR52.installGeometry();FullAssemblyGeometryR52.installClasspath();NervMappedPlugMechanicsR52.install();NervPlantMotionR52.install(request.cage());
        NervLowerFrameR52.install();NervPlantMotionR52.originalFixedColumnsR52();
        for(var spec:request.silos())NervSiloHatchGeometryR52.loadClasspath(spec);for(var spec:request.hangars())NervHangarGateGeometryR52.loadClasspath(spec);
        if(request.ground()){NervLegacyCarrierRideR52.fixedPartsR52();for(var unit:request.units()){NervOriginalCarrierR52.partsAtR52(unit.variant(),unit.bay(),0,new Vec3(0,1,0));NervOriginalCarrierR52.partsAtR52(unit.variant(),unit.bay(),1,new Vec3(0,1,0));}}
        var crane=NervCraneGeometryR52.loadClasspath();return new PreparedGeometryR52(crane,new NervCraneSweepR52(crane));
    }
    void preparedGeometryR52(PreparedGeometryR52 ready){preparedGeometryR52=Objects.requireNonNull(ready);}
    private NervCraneSweepR52 craneSweep;
    private String commissioningDiagnosticR52="not_started";
    public String commissioningDiagnosticR52(){return commissioningDiagnosticR52;}
    public RigidTransform originalGantryFrameR53(int variant){var unit=units.get(variant);return unit==null?null:unit.gantry().frame();}
    private boolean commissioningHoldR52(String stage,String detail){commissioningDiagnosticR52=stage+": "+detail;com.projectseele.ProjectSeele.LOGGER.warn("R52 mechanical commissioning held {}",commissioningDiagnosticR52);return false;}
    private static String firstFixedMismatchR52(ServerLevel level,List<FixedCell> cells){for(var c:cells){if(!loaded(level,c.at()))return "pos="+c.at().toShortString()+" expected="+BlockStateParser.serialize(c.expected())+" current=UNLOADED";var actual=level.getBlockState(c.at());if(!actual.equals(c.expected()))return "pos="+c.at().toShortString()+" expected="+BlockStateParser.serialize(c.expected())+" current="+BlockStateParser.serialize(actual);}return "all_declared_cells_match";}
    private static String firstClosedMismatchR52(ServerLevel level,List<List<Cell>> rows){for(var row:rows)for(var c:row){if(!loaded(level,c.at()))return "pos="+c.at().toShortString()+" expected="+BlockStateParser.serialize(c.closed())+" current=UNLOADED";var actual=level.getBlockState(c.at());if(!NervMechanicalMaterialR53.samePhase(actual,c.closed()))return "pos="+c.at().toShortString()+" expected="+BlockStateParser.serialize(c.closed())+" current="+BlockStateParser.serialize(actual);}return "all_declared_closed_cells_match";}
    private String visualDiagnosticR52(ServerLevel level,UnitPlant p,Visual v,boolean crane){var actor=level.getEntity(v.id());if(actor!=null)return "uuid="+v.id()+" expected_frame="+v.frame()+" actual_type="+actor.getType()+" actual_pos="+actor.position()+" declared_frame="+(actor instanceof NervCarrierPlatformEntity m?m.declaredMachineRotationR52():"wrong_type")+" epoch="+actor.getPersistentData().getLong("MachineEpochR52")+" directory="+actor.getPersistentData().getString("MachineDirectoryR52");String support=firstFixedMismatchR52(level,v.supports());var pit=servicePit(p);return "uuid="+v.id()+" requested_frame="+v.frame()+" support="+support+" frame_loaded="+loaded(level,BlockPos.containing(v.frame().translation()))+(crane?"":" wet="+firstClosedMismatchR52(level,p.lcl())+" pit="+(pit==null?"MISSING":pit.resource()+" "+firstClosedMismatchR52(level,pit.collisionSteps()))+" original_pos="+(level.getEntity(p.eva())==null?"MISSING":level.getEntity(p.eva()).position())+" expected_bay="+p.bay().translation()+" carrier_rise="+(level.getEntity(p.eva()) instanceof EvaUnit01Entity e?e.carrierRiseProgress(1):"MISSING"));}
    public NervAssemblyOwnerR52(NervRouteDirectoryR52 directory,long epoch,boolean installed,Map<Integer,UnitPlant> units,Map<String,Gate> gates,Map<String,List<FixedCell>> resources,Map<String,Receiver> receivers,String cageSourceSha)
    {
        this.cageSourceSha=cageSourceSha;require(cageSourceSha.matches("[0-9a-f]{64}"),"Actual mechanical source receipt required");this.directory=Objects.requireNonNull(directory);this.epoch=epoch;this.installed=installed;this.units=Map.copyOf(units);this.gates=Map.copyOf(gates);this.resources=resources.entrySet().stream().collect(java.util.stream.Collectors.toUnmodifiableMap(Map.Entry::getKey,e->List.copyOf(e.getValue())));this.receivers=Map.copyOf(receivers);
        require(epoch==directory.epoch()&&units.keySet().equals(Set.of(0,1,2)),"Explicit matching Root epoch and three original plants required");
        var visuals=new HashSet<UUID>();for(var p:units.values())
        {var u=directory.unit(p.variant());require(u!=null&&u.eva().equals(p.eva())&&u.plug().equals(p.plug())&&p.bridgeStates().size()==10&&p.raiseTicks()>0&&!p.lcl().isEmpty()&&!p.carrierSupport().isEmpty()&&!p.chair().isEmpty()&&p.boardingRadius()>0&&p.boardingRadius()<=8&&!p.gantry().supports().isEmpty()&&!p.crane().visual().supports().isEmpty()&&!p.crane().frameCells().isEmpty(),"Root original unit/bridge declaration mismatch");require(visuals.add(p.gantry().id())&&visuals.add(p.crane().visual().id()),"Shared machine visual UUID conflict");}
        for(var p:units.values())validateBridgeStates(p.bridgeStates());
        for(var p:units.values()){validateOriginalLcl(p.lcl());require(!p.boardPath().isEmpty()&&!p.returnPath().isEmpty()&&!p.personnelDoors().isEmpty(),"Complete original walking routes and actual room doors required");for(var door:p.personnelDoors())validatePersonnelDoor(door);}
        for(var p:units.values())require(Math.abs(p.crane().railAxis().length()-1)<1e-8&&p.crane().railAxis().y==0&&p.crane().railMax()>p.crane().railMin()&&p.crane().hoistStep()>0&&p.crane().initialBottom()<0&&p.crane().stowBottom()<0,"Explicit surveyed crane channel required");
        for(var id:resources.keySet())require(directory.resource(id)!=null&&!resources.get(id).isEmpty(),"Actual declared resource cells required");
        for(var g:gates.values())require(visuals.add(g.visual())&&(directory.schemaVersionR52()<2||g.visual().equals(proposedGateIdentityR53(epoch,g.resource())))&&g.width()>0&&g.height()>0&&!g.collisionSteps().isEmpty()&&!g.supports().isEmpty()&&(g.kind()!=GateKind.SILO||g.siloHatch()!=null)&&(g.kind()!=GateKind.HANGAR||g.hangarStack()!=null),"Explicit unique actual current-epoch gate controller and finite gate specification required");
        var seals=new HashMap<String,List<Cell>>();for(var g:gates.values())if(hasWetFloorSealR52(g))
        {require(g.resource().equals("bay_"+g.variant()+"_front")&&units.containsKey(g.variant()),"Optional wet-floor seal belongs to its original bay front controller");var cells=wetFloorSealCellsR52(g);var liquid=new HashSet<BlockPos>();for(var layer:units.get(g.variant()).lcl())for(var c:layer)liquid.add(c.at());require(cells.stream().noneMatch(c->liquid.contains(c.at())),"A floor seal is not an original44-layer LCL fill/drain cell");seals.put(g.resource(),cells);}wetFloorSealsR52=Map.copyOf(seals);
    }
    /** Root calls only after the actual fixed plant was installed/read back.
     * Transient machine identities are new stable declarations, not old actor
     * replacements. No original EVA/capsule/pilot is created or relocated. */
    public boolean commission(ServerLevel level)throws java.io.IOException
    {
        if(preparedGeometryR52==null){var request=geometryRequestR52();var ready=NervSourcePreparationR52.poll("plant/"+directory.fingerprint()+"/"+request.selectionKey(),()->prepareGeometryR52(request));if(!ready.ready())return commissioningHoldR52("source_preparation",ready.hold());preparedGeometryR52=ready.value();}
        commissioningDiagnosticR52="preconditions";
        if(!installed||!directory.installed()||!TvCageCollisionR44.enabled()||!servicePits.keySet().equals(units.keySet()))return commissioningHoldR52("preconditions","owner_installed="+installed+" directory_installed="+directory.installed()+" cage_collision_enabled="+TvCageCollisionR44.enabled()+" service_pits="+servicePits.keySet()+" units="+units.keySet());
        if(groundGuidesDeclared&&!NervLegacyServiceBypassR52.nativeFacesBear(level))return commissioningHoldR52("service_bypass/native_wall_faces","selected_source="+NervLegacyServiceBypassR52.SOURCE_SHA+" required="+NervLegacyServiceBypassR52.wallFaces());
        for(var p:units.values()){
            if(!fixed(level,p.gantry().supports()))return commissioningHoldR52("unit_"+p.variant()+"/gantry_support",firstFixedMismatchR52(level,p.gantry().supports()));
            if(!fixed(level,p.crane().frameCells()))return commissioningHoldR52("unit_"+p.variant()+"/crane_frame",firstFixedMismatchR52(level,p.crane().frameCells()));
            if(!NervR50CarrierModeR53.enabled()&&!fixed(level,p.carrierSupport()))return commissioningHoldR52("unit_"+p.variant()+"/carrier_support",firstFixedMismatchR52(level,p.carrierSupport()));
            if(!(level.getEntity(p.eva()) instanceof EvaUnit01Entity))return commissioningHoldR52("unit_"+p.variant()+"/original_eva","uuid="+p.eva()+" expected_pos="+p.bay().translation()+" current="+level.getEntity(p.eva()));
            if(!(level.getEntity(p.plug()) instanceof EntryPlugCarrierEntity)&&!EntryPlugDisposalR31.destroyed(level,p.plug()))return commissioningHoldR52("unit_"+p.variant()+"/original_capsule","uuid="+p.plug()+" expected_frame="+p.dock()+" current="+level.getEntity(p.plug()));
        }
        for(var g:gates.values())if(!NervR50CarrierModeR53.retiredPit(g.resource())&&!fixed(level,g.supports()))return commissioningHoldR52("gate/"+g.resource()+"/support",firstFixedMismatchR52(level,g.supports()));
        commissioningDiagnosticR52="actual_source_install/cage="+cageSourceSha;
        craneGeometry=preparedGeometryR52.crane();craneSweep=preparedGeometryR52.sweep();
        for(var p:units.values()){var gantry=visual(level,p.gantry(),p.variant(),false,0);var hoist=visual(level,p.crane().visual(),p.variant(),true,p.crane().initialBottom());if(gantry==null)return commissioningHoldR52("unit_"+p.variant()+"/gantry_controller",visualDiagnosticR52(level,p,p.gantry(),false));if(hoist==null)return commissioningHoldR52("unit_"+p.variant()+"/crane_controller",visualDiagnosticR52(level,p,p.crane().visual(),true));gantry.configureDeclaredCollisionSourceR52(cageSourceSha);if(groundGuidesDeclared){var drive=serviceDriveSpecR52(level,p);if(drive==null||!NervServiceFootDriveR52.foundationsBear(level,drive))return commissioningHoldR52("unit_"+p.variant()+"/service_drive_foundations","declared_cells="+p.carrierSupport()+" actual_drive="+drive);var initialLead=new NervLegacyCarrierRideR52.LeadSampleR52(drive,0,0,level.getGameTime());var declaredFloors=p.carrierSupport().stream().map(FixedCell::at).collect(java.util.stream.Collectors.toSet());for(var foot:NervLegacyCarrierRideR52.leadFoundationPointsR52(initialLead)){var cell=BlockPos.containing(foot.add(0,-.001,0));if(!declaredFloors.contains(cell))return commissioningHoldR52("unit_"+p.variant()+"/lead_foundation_declaration","actual_source_foot="+foot+" required_cell="+cell+" declared="+declaredFloors);}if(!actualLeadFoundationsBearR52(level,initialLead))return commissioningHoldR52("unit_"+p.variant()+"/lead_finite_foundation","actual source .24m square feet lack complete native top-face support; declared="+p.carrierSupport());gantry.declareServiceFootDriveR52(drive);EvaMechanicalFrameR52.declareGroundGuidesR52((EvaUnit01Entity)level.getEntity(p.eva()));}EvaMechanicalFrameR52.declarePlantCarrierR52((EvaUnit01Entity)level.getEntity(p.eva()));if(!hoist.hasCraneReference()&&EntryPlugDisposalR31.destroyed(level,p.plug()))hoist.setCraneReferenceR52(p.dock());if(!hoist.hasCraneReference()){var capsule=(EntryPlugCarrierEntity)level.getEntity(p.plug());if(!pose(capsule.getCanonicalTransform(),p.dock())||capsule.isLockedToEva())return commissioningHoldR52("unit_"+p.variant()+"/crane_capsule_reference","uuid="+p.plug()+" expected_frame="+p.dock()+" current_frame="+capsule.getCanonicalTransform()+" locked_to_eva="+capsule.isLockedToEva());hoist.linkCranePlug(capsule);}if(!craneBearing(level,p,craneState(hoist),craneState(hoist)))return commissioningHoldR52("unit_"+p.variant()+"/actual_crane_bearing","uuid="+hoist.getUUID()+" state="+craneState(hoist)+" rail_axis="+p.crane().railAxis()+" support="+firstFixedMismatchR52(level,p.crane().frameCells())+" source="+cageSourceSha);}
        // Actual door controller commissioning remains explicit. An absent
        // visual or physical closed frame does not silently clear collision.
        for(var g:gates.values())if(!commissionDoor(level,g))return commissioningHoldR52("gate/"+g.resource()+"/actual_controller","uuid="+g.visual()+" expected_frame="+g.frame()+" actual="+level.getEntity(g.visual())+" supports="+firstFixedMismatchR52(level,g.supports())+" closed_cells="+firstClosedMismatchR52(level,g.collisionSteps())+" silo_spec="+g.siloHatch()+" hangar_spec="+g.hangarStack()+" source="+NervSiloHatchGeometryR52.SOURCE_SHA);
        if(groundGuidesDeclared&&continuousGuidesR52){if(!NervOuterCarrierGuideR52.selected()||!continuousGuidePathsShaR52.equals(NervUprightGuidewayR52.sourceSha256())||!NervUprightGuidewayR52.matchesDirectory(directory)||!NervUprightGuidewayR52.enabledForDirectoryR52(level,directory))return commissioningHoldR52("upright_captured_guides/actual_source_or_anchors","model="+NervOuterCarrierGuideR52.SOURCE_SHA+" paths="+continuousGuidePathsShaR52+" directory="+directory.fingerprint());for(var p:units.values())if(!commissionOriginalCarrierR52(level,p))return commissioningHoldR52("unit_"+p.variant()+"/original_continuous_carrier_controller","uuid="+carrierControllers.get(p.variant())+" original="+p.eva()+" source="+NervOriginalCarrierR52.SOURCE_SHA);}
        else if(groundGuidesDeclared){if(!NervFixedFootGuidesR52.matchesDirectory(directory))return commissioningHoldR52("fixed_foot_guides/directory","selected_path_sha="+NervFixedFootGuidesR52.SOURCE_SHA+" directory="+directory.fingerprint());String anchor=NervFixedFootGuidesR52.firstMissingAnchor(level);if(!anchor.equals("MATCH"))return commissioningHoldR52("fixed_foot_guides/finite_anchor",anchor);for(var p:units.values())if(!commissionOriginalCarrierR52(level,p))return commissioningHoldR52("unit_"+p.variant()+"/original_carrier_controller","uuid="+carrierControllers.get(p.variant())+" original="+p.eva()+" actual="+level.getEntity(carrierControllers.get(p.variant()))+" source="+NervOriginalCarrierR52.SOURCE_SHA);NervFixedFootGuidesR52.enable(level,directory);if(!commissionStationsR52(level))return false;}
        commissioned=true;commissioningDiagnosticR52="commissioned";return true;
    }
    /** Restart reuses every declared machine. Missing or unloaded saved
     * actors hold restoration; this entry cannot create replacements. */
    public boolean resumeExistingR52(ServerLevel level)throws java.io.IOException {
        var machines=new HashSet<UUID>();for(var p:units.values()){machines.add(p.gantry().id());machines.add(p.crane().visual().id());var carrier=carrierControllers.get(p.variant());if(carrier==null)return commissioningHoldR52("resume/carrier_identity","variant="+p.variant());machines.add(carrier);}for(var g:gates.values())machines.add(g.visual());for(String id:canonicalTurnsR52())machines.add(NervFootGuideStationR52.proposedIdentityR52(epoch,id));
        for(var id:machines){var actor=level.getEntity(id);if(actor==null||!actor.isAlive())return commissioningHoldR52("resume/original_controller_not_loaded","uuid="+id);}
        return commission(level);
    }
    public Map<UUID,Vec3> installationActorPositionsR52(){
        var out=new LinkedHashMap<UUID,Vec3>();for(var p:units.values()){out.put(p.eva(),p.bay().translation());out.put(p.plug(),p.dock().translation());out.put(p.npc(),p.standby());out.put(p.seat(),p.seatFrame().translation());out.put(p.gantry().id(),p.gantry().frame().translation());out.put(p.crane().visual().id(),p.crane().visual().frame().translation());var carrier=carrierControllers.get(p.variant());if(carrier!=null)out.put(carrier,p.bay().translation());}for(var g:gates.values())out.put(g.visual(),g.frame().translation());for(String id:canonicalTurnsR52())out.put(NervFootGuideStationR52.proposedIdentityR52(epoch,id),directory.node(directory.leg(id).from()).footFrame().translation());for(var member:staff)out.put(member.original(),Vec3.atBottomCenterOf(member.station().feet()));return Map.copyOf(out);
    }
    public Set<net.minecraft.world.level.ChunkPos> installationFoundationChunksR52()throws java.io.IOException {
        var cells=new HashSet<BlockPos>();for(var list:resources.values())for(var c:list)cells.add(c.at());for(var p:units.values()){for(var list:List.of(p.gantry().supports(),p.crane().visual().supports(),p.crane().frameCells(),p.carrierSupport(),p.chair()))for(var c:list)cells.add(c.at());for(var row:p.bridgeStates())for(var c:row)cells.add(c.at());for(var row:p.lcl())for(var c:row)cells.add(c.at());for(var row:p.personnelDoors())for(var c:row)cells.add(c.at());}for(var g:gates.values()){for(var c:g.supports())cells.add(c.at());for(var row:g.collisionSteps())for(var c:row)cells.add(c.at());}for(var receiver:receivers.values())for(var c:receiver.supports())cells.add(c.at());for(var member:staff)for(var c:member.support())cells.add(c.at());if(groundGuidesDeclared&&!continuousGuidesR52)for(var anchor:NervFixedFootGuidesR52.anchors())cells.add(anchor.at());var chunks=new HashSet<net.minecraft.world.level.ChunkPos>();for(var cell:cells)chunks.add(new net.minecraft.world.level.ChunkPos(cell));if(continuousGuidesR52)chunks.addAll(NervUprightGuidewayR52.foundationChunks());if(groundGuidesDeclared)for(var face:NervLegacyServiceBypassR52.wallFaces())chunks.add(new net.minecraft.world.level.ChunkPos(face.block()));return Set.copyOf(chunks);
    }
    private Set<String> canonicalTurnsR52(){var result=new HashSet<String>();for(var route:directory.routes().values())for(String id:route.legs()){var leg=directory.leg(id);if(leg.motion()==Motion.FOOT_BEARING_TURN)result.add(NervFootGuideStationR52.canonicalLeg(id));}return Set.copyOf(result);}
    private NervFootGuideDockR52.Spec turnSpecR52(Leg leg,FootSupportFrameR52.Binding binding)throws java.io.IOException {Double top=dockFoundationsR52.get(NervFootGuideStationR52.canonicalLeg(leg.id()));if(top==null)return null;for(var route:directory.routes().values()){int index=route.legs().indexOf(leg.id());if(index<0)continue;Vec3 from=new Vec3(0,1,0),to=from;if(index>0){var value=NervFixedFootGuidesR52.up(directory,directory.leg(route.legs().get(index-1)));if(value!=null)from=value;}if(index+1<route.legs().size()){var value=NervFixedFootGuidesR52.up(directory,directory.leg(route.legs().get(index+1)));if(value!=null)to=value;}return new NervFootGuideDockR52.Spec(directory,leg,binding,from,to,top);}return null;}
    private boolean commissionStationsR52(ServerLevel l)throws java.io.IOException {if(!dockFoundationsR52.keySet().equals(canonicalTurnsR52()))return commissioningHoldR52("turn_station/declaration","required="+canonicalTurnsR52()+" actual="+dockFoundationsR52.keySet());for(String id:dockFoundationsR52.keySet()){var leg=directory.leg(id);int variant=-1;for(var route:directory.routes().values())if(route.legs().contains(id)){if(variant>=0&&variant!=route.variant())return false;variant=route.variant();}if(variant<0)return false;var spec=turnSpecR52(leg,NervOriginalCarrierR52.nominalBinding(variant));if(spec==null||!resources.containsKey(leg.support())||!fixed(l,resources.get(leg.support()))||!NervFootGuideStationR52.finiteFeetBear(l,spec))return commissioningHoldR52("turn_station/finite_foundation","leg="+id+" top="+dockFoundationsR52.get(id)+" support="+leg.support()+" actual="+(resources.containsKey(leg.support())?firstFixedMismatchR52(l,resources.get(leg.support())):"MISSING")+" finite_foot="+(spec==null?"SPEC_MISSING":NervFootGuideStationR52.firstMissingFootR52(l,spec))+" source="+NervFootGuideDockR52.SOURCE_SHA);var uuid=NervFootGuideStationR52.proposedIdentityR52(epoch,id);var existing=l.getEntity(uuid);if(existing!=null){if(!(existing instanceof NervCarrierPlatformEntity n)||NervFootGuideStationR52.controller(l,spec)!=n)return commissioningHoldR52("turn_station/existing_source","leg="+id+" uuid="+uuid+" actual="+existing);continue;}var e=ModEntities.NERV_CARRIER_PLATFORM.get().create(l);if(e==null)return false;e.setUUID(uuid);e.assignVariant(variant);var at=directory.node(leg.from()).footFrame();e.holdStatic(at.translation().x,at.translation().y,at.translation().z);e.configureDeclaredMachineFrameR52(at.rotation());e.getPersistentData().putLong("MachineEpochR52",epoch);e.getPersistentData().putString("MachineDirectoryR52",directory.fingerprint());if(!NervFootGuideStationR52.declareNewR52(e,spec)||NervFootGuideDockR52.proposeStation(l,e,NervFootGuideStationR52.view(e),NervFootGuideStationR52.currentPose(e),NervFootGuideStationR52.currentPose(e),Set.of(uuid))==null)return commissioningHoldR52("turn_station/source_clearance","leg="+id+" uuid="+uuid+" source="+NervFootGuideDockR52.SOURCE_SHA);if(!l.addFreshEntity(e))return false;}return true;}
    private boolean commissionOriginalCarrierR52(ServerLevel l,UnitPlant p)throws java.io.IOException {if(!NervMappedPlugMechanicsR52.selectedMachinery().selectedRunningDeckR52())return commissioningHoldR52("original_carrier/running_source_selection","selectedFullReceipt="+NervOriginalCarrierR52.SOURCE_SHA+" actualHousingDeck="+NervLegacyCarrierRideR52.DECK_SHA+" reviewed_source_required");var id=carrierControllers.get(p.variant());if(id==null||!id.equals(NervOriginalCarrierR52.proposedIdentityR52(epoch,p.eva()))||!(l.getEntity(p.eva()) instanceof EvaUnit01Entity e))return false;var existing=l.getEntity(id);if(existing!=null){if(!(existing instanceof NervCarrierPlatformEntity n)||!NervOriginalCarrierR52.declared(n)||n.originalCarrierStateR52().getLong("Epoch")!=epoch||!n.originalCarrierStateR52().getString("Directory").equals(directory.fingerprint())||!n.originalCarrierStateR52().getUUID("OriginalEva").equals(e.getUUID()))return false;EvaMechanicalFrameR52.bindOriginalCarrierControllerR52(e,n);return true;}if(EvaMechanicalFrameR52.hasOriginalCarrierControllerR52(e))return false;var root=EvaMechanicalFrameR52.carrierFrameR52(e,1);float rise=e.carrierRiseProgress(1);if(!pose(root,p.bay())||rise!=0||!fixed(l,p.carrierSupport()))return false;var n=ModEntities.NERV_CARRIER_PLATFORM.get().create(l);if(n==null)return false;n.setUUID(id);n.assignVariant(p.variant());n.holdStatic(root.translation().x,root.translation().y,root.translation().z);n.configureDeclaredMachineFrameR52(root.rotation());n.getPersistentData().putLong("MachineEpochR52",epoch);n.getPersistentData().putString("MachineDirectoryR52",directory.fingerprint());if(!NervOriginalCarrierR52.declareNewR52(n,p.variant(),epoch,p.eva(),root,rise))return false;n.setBoundingBox(NervOriginalCarrierR52.boundsR52(n));if(!l.addFreshEntity(n))return false;EvaMechanicalFrameR52.bindOriginalCarrierControllerR52(e,n);return true;}
    private NervTurnStationRuntimeR52.Admission carrierActuatorAdmissionR52(ServerLevel l,Original o,CompoundTag data){var context=NervRouteRuntimeR52.flightContext(l);if(context==null)return null;var task=context.pool().groundTaskR52(o);if(task!=null&&task.directoryFingerprint().equals(directory.fingerprint())){var route=directory.route(task.route());if(route==null)return null;var ids=directory.resources(route);return context.pool().resourcesHeldR52(task.task(),ids)?new NervTurnStationRuntimeR52.Admission(task.task(),ids,context.bindings(),context.pool()):null;}if(!data.hasUUID("FlightTaskR52"))return null;var flight=context.pool().queryFlight(data.getUUID("FlightTaskR52"));if(flight==null||!flight.original().equals(o)||!flight.directoryFingerprint().equals(directory.fingerprint())||flight.payloadTransferred())return null;var ids=new HashSet<>(flight.spaces());ids.addAll(flight.mechanisms());return context.pool().resourcesHeldR52(flight.task(),Set.copyOf(ids))?new NervTurnStationRuntimeR52.Admission(flight.task(),Set.copyOf(ids),context.bindings(),context.pool()):null;}
    public EvaUnit01Entity resetOriginalMaintenanceR53(ServerLevel l,int variant){
        var p=units.get(variant);if(p==null||!(l.getEntity(p.eva()) instanceof EvaUnit01Entity eva)||!(l.getEntity(p.npc()) instanceof TrainingPilotEntity pilot))throw new IllegalStateException("原机体或驾驶员未加载");
        if(!NervAirTransportRuntimeR52.abortForMaintenance(l,variant,eva.getUUID()))throw new IllegalStateException("原运输机尚未加载，复位请求等待原机到位");
        var capsule=maintenanceCapsuleR53(l,p);if(capsule==null)throw new IllegalStateException("原插入栓未加载且没有已销毁记录");
        var hardware=EvaMechanicalFrameR52.originalCarrierControllerR52(eva);if(hardware==null)throw new IllegalStateException("原架体尚未加载");
        var passengers=List.copyOf(capsule.getPassengers());capsule.resetOriginalAtDockR53(p.dock());eva.clearEntryPlugLink(capsule);for(var passenger:passengers)passenger.teleportTo(p.standby().x,p.standby().y,p.standby().z);eva.ejectPassengers();pilot.stopRiding();pilot.getNavigation().stop();pilot.setInvisible(false);pilot.setTrainingStage(TrainingPilotEntity.STAGE_STANDBY);pilot.moveTo(p.standby().x,p.standby().y,p.standby().z,0,0);
        for(String key:List.of("R52OriginalPilotOperation","R52OriginalPilotDirectory","R52OriginalPilotNode"))pilot.getPersistentData().remove(key);
        pilot.getPersistentData().putString("SeelePilotRouteR30","standby");pilotOperations.remove(pilot.getUUID());pilotNodes.remove(pilot.getUUID());
        if(l.getEntity(p.seat()) instanceof NervCommandSeatEntity seat)pilot.startRiding(seat,true);
        if(l.getEntity(p.crane().visual().id()) instanceof NervCarrierPlatformEntity hoist)
        {
            var at=p.crane().visual().frame();hoist.linkCranePlug(null);hoist.holdStatic(at.translation().x,at.translation().y,at.translation().z);
            hoist.setYRot(yaw(at));hoist.configureDeclaredMachineFrameR52(at.rotation());hoist.configurePlugCrane(variant,p.crane().initialBottom());
            hoist.setCraneReferenceR52(p.dock());hoist.linkCranePlug(capsule);
        }
        EvaMechanicalFrameR52.resetOriginalMaintenanceR53(eva);EvaAirTransportR31.clear(eva);eva.normalizeAfterTransportR30(true);
        eva.moveOnNervCarrier(p.bay().translation().x,p.bay().translation().y,p.bay().translation().z,180-yaw(p.bay()));
        eva.setHealth(eva.getMaxHealth());eva.deathTime=0;eva.setNervLogisticsLocked(true);eva.enterHangarStandby();eva.setCarrierRiseProgress(0);NervOriginalCarrierR52.resetOriginalAtBayR53(hardware,p.bay());
        for(var cell:p.bridgeStates().get(9))if(!l.getBlockState(cell.at()).equals(cell.expected()))l.setBlock(cell.at(),cell.expected(),18);
        var front=gates.get("bay_"+variant+"_front");
        if(front==null||!(l.getEntity(front.visual()) instanceof NervHangarDoorEntity frontDoor))throw new IllegalStateException("原机库门尚未加载，不能完成复位");
        frontDoor.restoreDeclaredClosedR53();
        for(var step:front.collisionSteps())for(var cell:step)if(!l.getBlockState(cell.at()).equals(cell.closed()))l.setBlock(cell.at(),cell.closed(),18);
        for(var layer:p.lcl())for(var cell:layer)if(!l.getBlockState(cell.at()).equals(cell.closed()))l.setBlock(cell.at(),cell.closed(),18);
        var g=gantry(l,p);if(g!=null){g.setRestraintProgress(1);g.setLclVisualLevel(p.lcl().size());g.setLowerFrameProgressR52(0);g.setServiceGuideBridgeR52(0);}
        var fleet=EvaFleetSavedData.get(l.getServer());var row=fleet.entry(variant).orElseThrow();fleet.put(variant,row.withPhase(EvaFleetSavedData.Phase.PARKED,0,0,p.lcl().size()));captured.remove(eva.getUUID());continuousGeometryR52.remove(eva.getUUID());ballistic.remove(eva.getUUID());previews.remove(eva.getUUID());occupiedPreviews.remove(eva.getUUID());holds.remove(eva.getUUID());receiverTicks.remove(eva.getUUID());return eva;
    }
    private boolean carrierSupportReadyR53(ServerLevel l,EvaUnit01Entity eva){if(!NervR50CarrierModeR53.enabled())return NervMappedPlugMechanicsR52.actualCarrierFootBearing(l,eva);var carrier=EvaMechanicalFrameR52.originalCarrierControllerR52(eva);return carrier!=null&&NervOriginalCarrierR52.declared(carrier)&&eva.carrierRiseProgress(1)==1&&pose(NervOriginalCarrierR52.actualRoot(carrier,1),NervOwnerPlacementR52.actualRoot(eva));}
    private boolean acceptCarrierActuatorR52(ServerLevel l,EvaUnit01Entity e,RigidTransform root,float from,float to,Set<UUID> own,Original o,CompoundTag data){if(NervR50CarrierModeR53.enabled()){e.setCarrierRiseProgress(to);var n=EvaMechanicalFrameR52.originalCarrierControllerR52(e);if(n!=null)NervOriginalCarrierR52.restoreR50RiseR53(n,to);return true;}if(!EvaMechanicalFrameR52.hasOriginalCarrierControllerR52(e)){if(!NervMappedPlugMechanicsR52.clearCarrierRise(l,e,root,from,to,own))return false;e.setCarrierRiseProgress(to);return true;}var n=EvaMechanicalFrameR52.originalCarrierControllerR52(e);if(n==null||!pose(NervOriginalCarrierR52.actualRoot(n,1),root))return false;var members=new HashSet<>(own);members.add(n.getUUID());var admission=carrierActuatorAdmissionR52(l,o,data);if(admission==null)return hold(o,"actual_carrier_actuator_same_ground_or_flight_lease_missing");try{var plant=plant(o);var g=plant==null?null:gantry(l,plant);boolean inBay=groundGuidesDeclared&&plant!=null&&pose(root,plant.bay());NervOriginalCarrierR52.CheckedStep step;NervLegacyCarrierRideR52.AcceptedLeadStep lead=null;if(inBay){var before=g==null?null:NervOriginalCarrierR52.actualLeadSampleR52(g,1);if(before==null||before.rise()!=from)return hold(o,"actual_bay_lead_and_original_carrier_clock_differ");var after=new NervLegacyCarrierRideR52.LeadSampleR52(before.spec(),before.serviceBridge(),to,l.getGameTime());step=NervOriginalCarrierR52.proposeActuator(l,n,from,to,Set.copyOf(members),g,before,after);if(step==null)return false;var leadOwn=new HashSet<>(members);leadOwn.add(g.getUUID());lead=NervLegacyCarrierRideR52.proposeLeadR52(l,g,n,step,before,after,Set.copyOf(leadOwn));if(lead==null||!lead.current(l)||!NervTurnStationRuntimeR52.covered(admission,lead.envelopes()))return hold(o,"actual_bay_lead_full_source_or_space_admission_rejected");}else step=NervOriginalCarrierR52.proposeActuator(l,n,from,to,Set.copyOf(members));if(step==null||!step.current(l)||!NervTurnStationRuntimeR52.covered(admission,step.envelopes())||!(lead==null?step.commit(l):step.commit(l,lead)))return false;}catch(java.io.IOException missing){return false;}e.setCarrierRiseProgress(to);return true;}

    public String holdReason(UUID original){return holds.getOrDefault(original,"");}
    private boolean hold(Original original,String reason){holds.put(original.eva(),reason);return false;}
    private UnitPlant plant(Original o){var p=units.get(o.variant());return p!=null&&o.eva().equals(p.eva())&&o.plug().equals(p.plug())&&o.epoch()==epoch?p:null;}
    private EvaUnit01Entity hull(ServerLevel l,Original o){return l.getEntity(o.eva()) instanceof EvaUnit01Entity e&&e.getUnitVariant()==o.variant()&&!e.isExperimentalUnit()?e:null;}
    private EntryPlugCarrierEntity plug(ServerLevel l,Original o){return l.getEntity(o.plug()) instanceof EntryPlugCarrierEntity p&&p.getAssignedVariant()==o.variant()?p:null;}
    private static Kind kind(CompoundTag data){return data.contains("AssemblyKindR52")?Kind.valueOf(data.getString("AssemblyKindR52")):Kind.OCCUPIED;}
    @Override public boolean fullRigidFramesReady(ServerLevel l,NervRouteDirectoryR52 d)
    {return commissioned&&installed&&d.fingerprint().equals(directory.fingerprint())&&l.dimension().location().toString().equals(directory.node(directory.leg(directory.routes().values().iterator().next().legs().get(0)).from()).dimension());}
    @Override public boolean mechanicalRailReadyR52(ServerLevel l,NervMechanicalRailBindingR52.Spec rail,List<NervRouteNativeR52.Cell> foundations)
    {
        if(!commissioned)return false;
        var leg=directory.leg(rail.leg());if(leg==null)return false;
        try {
            if(rail.kind()==NervMechanicalRailBindingR52.Kind.UPRIGHT_CAPTURED_GUIDEWAY)return continuousGuidesR52&&continuousGuidePathsShaR52.equals(rail.sourceSha())&&NervMechanicalRailBindingR52.ready(l,directory,rail);
            if(NervR50CarrierModeR53.enabled()&&rail.kind()==NervMechanicalRailBindingR52.Kind.LEGACY_RUNNING_HEAD)
            {
                for(var cell:foundations)
                {
                    if(cell.state().equals("projectseele:nerv_shaft_panel"))continue;
                    if(l.getChunkSource().getChunkNow(cell.position().getX()>>4,cell.position().getZ()>>4)==null
                            ||!BlockStateParser.serialize(l.getBlockState(cell.position())).equals(cell.state()))return false;
                }
                return true;
            }
            if(!groundGuidesDeclared)return false;
            if(rail.kind()==NervMechanicalRailBindingR52.Kind.FIXED_FOOT_GUIDE)return NervMechanicalRailBindingR52.ready(l,directory,rail);
            if(rail.kind()==NervMechanicalRailBindingR52.Kind.FOOT_TURN_STATION)return Objects.equals(dockFoundationsR52.get(rail.leg()),rail.foundationTop())&&NervMechanicalRailBindingR52.ready(l,directory,rail);
            var p=units.get(NervMechanicalRailBindingR52.variant(directory,rail.leg()));var g=p==null?null:gantry(l,p);
            if(g==null||!p.gantry().id().equals(rail.controller())||!pose(RigidTransform.of(g.position(),g.declaredMachineRotationR52()),p.gantry().frame())||g.getPersistentData().getLong("MachineEpochR52")!=epoch||!g.getPersistentData().getString("MachineDirectoryR52").equals(directory.fingerprint()))return false;
            var expected=new HashMap<BlockPos,String>();for(var c:p.gantry().supports())expected.put(c.at(),BlockStateParser.serialize(c.expected()));for(var c:p.carrierSupport())expected.put(c.at(),BlockStateParser.serialize(c.expected()));
            var actual=new HashMap<BlockPos,String>();for(var c:foundations)if(actual.put(c.position(),c.state())!=null)return false;
            var drive=serviceDriveSpecR52(l,p);var lead=NervOriginalCarrierR52.actualLeadSampleR52(g,1);
            return actual.equals(expected)&&fixed(l,p.gantry().supports())&&fixed(l,p.carrierSupport())&&NervLowerFrameR52.actualPermanentFeetBearR52(l,g,p.gantry().supports())&&drive!=null&&drive.equals(g.declaredServiceFootDriveR52())&&NervServiceFootDriveR52.foundationsBear(l,drive)&&lead!=null&&actualLeadFoundationsBearR52(l,lead);
        }catch(java.io.IOException|IllegalArgumentException|IllegalStateException missing){return false;}
    }
    private static boolean actualLeadFoundationsBearR52(ServerLevel l,NervLegacyCarrierRideR52.LeadSampleR52 lead){for(var p:NervLegacyCarrierRideR52.leadFoundationPointsR52(lead)){var face=new AABB(p.x-.12,p.y-.001,p.z-.12,p.x+.12,p.y,p.z+.12);var tops=new ArrayList<AABB>();int y=(int)Math.floor(p.y-.001);for(int x=(int)Math.floor(face.minX);x<=Math.floor(face.maxX);x++)for(int z=(int)Math.floor(face.minZ);z<=Math.floor(face.maxZ);z++){var at=new BlockPos(x,y,z);if(!loaded(l,at))return false;for(var local:l.getBlockState(at).getCollisionShape(l,at).toAabbs()){var w=local.move(at);if(Math.abs(w.maxY-p.y)<.000003)tops.add(new AABB(w.minX,p.y-.001,w.minZ,w.maxX,p.y,w.maxZ));}}if(!NervAirspaceCoverageR52.covered(face,tops))return false;}return true;}
    private static boolean loaded(ServerLevel l,BlockPos p){return l.getChunkSource().getChunkNow(p.getX()>>4,p.getZ()>>4)!=null;}
    private static boolean fixed(ServerLevel l,List<FixedCell> cells){for(var c:cells)if(!loaded(l,c.at())||!l.getBlockState(c.at()).equals(c.expected()))return false;return true;}
    private static boolean matches(ServerLevel l,List<Cell> cells,boolean open){for(var c:cells)if(!loaded(l,c.at())||!NervMechanicalMaterialR53.samePhase(l.getBlockState(c.at()),open?c.open():c.closed()))return false;return true;}
    private static boolean canChange(ServerLevel l,List<Cell> cells,boolean open,Set<UUID> own)
    {
        for(var c:cells){if(!loaded(l,c.at()))return false;var current=l.getBlockState(c.at());boolean originalLiquid=c.closed().is(com.projectseele.registry.ModBlocks.LCL_BLOCK.get())&&current.is(c.closed().getBlock());if(!originalLiquid&&!NervMechanicalMaterialR53.samePhase(current,c.closed())&&!NervMechanicalMaterialR53.samePhase(current,c.open()))return false;var next=open?c.open():c.closed();if(!NervMechanicalMaterialR53.samePhase(current,next)&&!next.getCollisionShape(l,c.at()).isEmpty())for(var box:next.getCollisionShape(l,c.at()).toAabbs())if(!l.getEntities((Entity)null,box.move(c.at()),e->!own.contains(e.getUUID())&&e.isAlive()).isEmpty())return false;}return true;
    }
    private static boolean change(ServerLevel l,List<Cell> cells,boolean open,Set<UUID> own)
    {if(!canChange(l,cells,open,own))return false;for(var c:cells){var next=open?c.open():c.closed();if(!NervMechanicalMaterialR53.samePhase(l.getBlockState(c.at()),next))l.setBlock(c.at(),next,c.closed().is(com.projectseele.registry.ModBlocks.LCL_BLOCK.get())?2:3);}return matches(l,cells,open);}
    private static void validateOriginalLcl(List<List<Cell>> layers)
    {
        require(layers.size()==44&&layers.stream().mapToInt(List::size).sum()==90947,"Complete original 44-layer/90947-cell wet bay required");int previousY=Integer.MIN_VALUE;var unique=new HashSet<BlockPos>();
        for(var layer:layers){require(!layer.isEmpty(),"An original wet layer cannot be empty");int y=layer.get(0).at().getY();require(previousY==Integer.MIN_VALUE||y==previousY+1,"Original LCL layers must retain physical bottom-to-top order");previousY=y;for(var cell:layer)require(cell.at().getY()==y&&unique.add(cell.at())&&BuiltInRegistries.BLOCK.getKey(cell.closed().getBlock()).toString().equals("projectseele:lcl")&&cell.open().isAir(),"Original LCL phase/ownership differs");}
    }
    private static void validatePersonnelDoor(List<Cell> cells)
    {
        require(cells.size()==2,"Actual two-block personnel door required");var sorted=cells.stream().sorted(Comparator.comparingInt(c->c.at().getY())).toList();require(sorted.get(0).at().above().equals(sorted.get(1).at()),"Original personnel door halves are disconnected");
        for(int i=0;i<2;i++){var c=sorted.get(i);require(c.closed().getBlock() instanceof net.minecraft.world.level.block.DoorBlock&&c.closed().getBlock()==c.open().getBlock()&&!c.closed().getValue(net.minecraft.world.level.block.DoorBlock.OPEN)&&c.open().equals(c.closed().setValue(net.minecraft.world.level.block.DoorBlock.OPEN,true))&&c.closed().getValue(net.minecraft.world.level.block.DoorBlock.HALF)==(i==0?net.minecraft.world.level.block.state.properties.DoubleBlockHalf.LOWER:net.minecraft.world.level.block.state.properties.DoubleBlockHalf.UPPER),"Exact original personnel door OPEN channel required");}
    }
    private static boolean personnelDoors(ServerLevel l,UnitPlant p,boolean open)
    {for(var door:p.personnelDoors()){if(door.stream().anyMatch(c->l.getBlockEntity(c.at())!=null)||!canChange(l,door,open,Set.of()))return false;}for(var door:p.personnelDoors())if(!change(l,door,open,Set.of()))return false;return true;}
    private static boolean pose(RigidTransform a,RigidTransform b){return a!=null&&b!=null&&a.translation().distanceToSqr(b.translation())<1e-6&&a.rotationErrorDegrees(b)<.01;}
    private NervCarrierPlatformEntity visual(ServerLevel l,Visual v,int variant,boolean crane,double initialBottom)
    {
        Entity existing=l.getEntity(v.id());if(existing!=null){if(!(existing instanceof NervCarrierPlatformEntity n)||n.getUnitVariant()!=variant||n.isPlugCrane()!=crane||!n.hasDeclaredMachineFrameR52()||n.getPersistentData().getLong("MachineEpochR52")!=epoch||!n.getPersistentData().getString("MachineDirectoryR52").equals(directory.fingerprint())||RigidTransform.of(n.position(),n.declaredMachineRotationR52()).rotationErrorDegrees(v.frame())>.01)return null;if(!crane&&n.position().distanceToSqr(v.frame().translation())>1e-8)return null;if(crane){var c=units.get(variant).crane();var local=v.frame().inverse().transformPoint(n.position());double along=local.dot(c.railAxis());if(local.subtract(c.railAxis().scale(along)).length()>1e-5||along<c.railMin()||along>c.railMax())return null;}return n;}
        if(!fixed(l,v.supports())||!loaded(l,BlockPos.containing(v.frame().translation())))return null;
        if(!crane){var plant=units.get(variant);var pit=plant==null?null:servicePit(plant);if(plant==null||pit==null||!fixed(l,plant.gantry().supports())||!fixed(l,pit.supports())||pit.collisionSteps().stream().anyMatch(step->!matches(l,step,false))||!plant.lcl().stream().allMatch(layer->matches(l,layer,false))||!(l.getEntity(plant.eva()) instanceof EvaUnit01Entity eva)||eva.position().distanceToSqr(plant.bay().translation())>1e-8||eva.carrierRiseProgress(1)!=0)return null;}
        var n=ModEntities.NERV_CARRIER_PLATFORM.get().create(l);if(n==null)return null;n.setUUID(v.id());n.assignVariant(variant);if(crane)n.configurePlugCrane(variant,initialBottom);else{n.configureRestraintGantry();n.setRestraintProgress(1);n.setLclVisualLevel(44);}n.holdStatic(v.frame().translation().x,v.frame().translation().y,v.frame().translation().z);n.setYRot(yaw(v.frame()));n.configureDeclaredMachineFrameR52(v.frame().rotation());if(!crane&&lowerFrames.contains(variant))n.declareLowerFrameR52();n.getPersistentData().putLong("MachineEpochR52",epoch);n.getPersistentData().putString("MachineDirectoryR52",directory.fingerprint());return l.addFreshEntity(n)?n:null;
    }
    private static float yaw(RigidTransform f){var forward=f.transformVector(new Vec3(0,0,1));return (float)Math.toDegrees(Math.atan2(-forward.x,forward.z));}
    private NervCarrierPlatformEntity gantry(ServerLevel l,UnitPlant p){var e=l.getEntity(p.gantry().id());return e instanceof NervCarrierPlatformEntity n&&n.isRestraintGantry()?n:null;}
    private Gate servicePit(UnitPlant p){return gates.get(servicePits.get(p.variant()));}
    private NervServiceFootDriveR52.Spec serviceDriveSpecR52(ServerLevel l,UnitPlant p){if(!groundGuidesDeclared)return null;var gate=servicePit(p);if(gate==null||p.carrierSupport().isEmpty())return null;double top=Double.NaN;for(var c:p.carrierSupport()){if(!l.hasChunkAt(c.at())||!l.getBlockState(c.at()).equals(c.expected()))return null;double actual=c.expected().getCollisionShape(l,c.at()).toAabbs().stream().mapToDouble(b->b.maxY+c.at().getY()).max().orElse(Double.NaN);if(!Double.isFinite(actual)||Double.isFinite(top)&&Math.abs(top-actual)>.000001)return null;top=actual;}return new NervServiceFootDriveR52.Spec(p.variant(),p.bay(),gate.frame(),gate.siloHatch().firstTier(),top);}
    private boolean serviceBridgeReadyR52(ServerLevel l,UnitPlant p,boolean open){if(NervR50CarrierModeR53.enabled())return true;var g=gantry(l,p);try{return !groundGuidesDeclared||g!=null&&g.declaredServiceFootDriveR52()!=null&&g.serviceGuideBridgeR52(1)==(open?1:0)&&NervServiceFootDriveR52.foundationsBear(l,g.declaredServiceFootDriveR52());}catch(java.io.IOException missing){return false;}}
    private boolean originalClampsBear(ServerLevel l,UnitPlant p)
    {var g=gantry(l,p);if(g==null||!g.hasDeclaredMachineFrameR52()||!pose(RigidTransform.of(g.position(),g.declaredMachineRotationR52()),p.gantry().frame())||g.getRestraintProgress()!=1)return false;if(NervR50CarrierModeR53.enabled())return true;try{return fixed(l,p.gantry().supports())&&NervLowerFrameR52.actualPermanentFeetBearR52(l,g,p.gantry().supports())&&actualShoulderBearingR52(l,p,g);}catch(java.io.IOException failure){return false;}}
    private boolean actualShoulderBearingR52(ServerLevel l,UnitPlant p,NervCarrierPlatformEntity g)throws java.io.IOException
    {if(!(l.getEntity(p.eva()) instanceof EvaUnit01Entity e))return false;var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();var body=EvaMechanicalFrameR52.active(e)?EvaMechanicalFrameR52.capturedGeometry(e).parts():EvaMechanicalFrameR52.serviceSourceHeldR52(e)?EvaMechanicalFrameR52.serviceGeometryR52(e).parts():provider.evaluateShoulderContactsR53(e.getUnitVariant(),NervServiceBodyPoseR52.sample(e),EvaAnatomicalHandsR45.sample(e,1));return NervShoulderBearingR52.bears(body,NervOwnerPlacementR52.actualRoot(e),p.gantry().frame(),e.getUnitVariant());}
    private final Map<Integer,NervDryBayReadbackR53> dryBayReadbacks=new HashMap<>();
    private boolean dryBay(ServerLevel l,UnitPlant p)
    {return dryBayReadbacks.computeIfAbsent(p.variant(),ignored->new NervDryBayReadbackR53(p.lcl())).matches(l);}
    public static boolean wetFloorMaterialR53(BlockState state){return NervMechanicalMaterialR53.fullCutCopper(state)||!state.hasBlockEntity()&&Set.of("projectseele:nerv_floor_panel","projectseele:nerv_machine_hazard","projectseele:nerv_machine_panel","projectseele:nerv_machine_edge","minecraft:polished_basalt","minecraft:cut_copper","minecraft:exposed_cut_copper","minecraft:iron_block","minecraft:polished_blackstone","minecraft:sea_lantern").contains(BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString());}
    private static boolean hasWetFloorSealR52(Gate g){return g!=null&&g.kind()==GateKind.HANGAR&&g.hangarStack()!=null&&g.hangarStack().bottomSeal()!=null;}
    private static List<Cell> wetFloorSealCellsR52(Gate g)
    {
        var declared=new HashMap<BlockPos,Cell>();for(var row:g.collisionSteps())for(var c:row)require(declared.put(c.at(),c)==null,"Duplicate wet-gate phase cell");var selected=new LinkedHashMap<BlockPos,Cell>();
        for(var box:g.hangarStack().bottomSeal().closedBoxes())
        {var world=NervRigidMeshSweepR52.transformed(new AABB(box.minX(),box.minY(),box.minZ(),box.maxX(),box.maxY(),box.maxZ()),g.frame());
            long nx=(long)Math.floor(world.maxX-1e-6)-(long)Math.floor(world.minX+1e-6)+1,ny=(long)Math.floor(world.maxY-1e-6)-(long)Math.floor(world.minY+1e-6)+1,nz=(long)Math.floor(world.maxZ-1e-6)-(long)Math.floor(world.minZ+1e-6)+1;require(nx>0&&ny>0&&nz>0&&nx<=256&&ny<=256&&nz<=256&&nx*ny*nz<=256,"Actual wet-floor seal voxel budget exceeded");
            for(var raw:BlockPos.betweenClosed(BlockPos.containing(world.minX+1e-6,world.minY+1e-6,world.minZ+1e-6),BlockPos.containing(world.maxX-1e-6,world.maxY-1e-6,world.maxZ-1e-6)))
            {var at=raw.immutable();var c=declared.get(at);require(c!=null&&c.open().isAir()&&wetFloorMaterialR53(c.closed()),"Actual wet-floor seal requires original solid floor_panel/air phase cell at "+at);require(g.supports().stream().noneMatch(s->s.at().equals(at)),"A moving wet-floor seal cannot retire its own fixed support");selected.put(at,c);}}
        require(!selected.isEmpty()&&selected.size()<=512,"Actual complete bounded wet-floor seal cells required");return List.copyOf(selected.values());
    }
    /** Both sources are physical: exact original44-layer air readback and the retained gantry's liquid sample. */
    private static boolean wetSealDryInputsR52(boolean actualOriginalLayersDry,float actualVisualLevel)
    {return actualOriginalLayersDry&&Float.isFinite(actualVisualLevel)&&actualVisualLevel==0;}
    /** Closing time never advances the original four-tick-per-layer refill clock. */
    static boolean wetSealRefillReadyR52(boolean actualSealClosed,boolean actualBayDry,int filledLayers,CompoundTag data,java.util.function.BooleanSupplier actualClose)
    {if(actualSealClosed)return true;if(filledLayers!=0||!actualBayDry)return false;if(actualClose.getAsBoolean())data.putInt("FinishTicks",0);return false;}
    private boolean wetSealBayDryR52(ServerLevel l,Gate g)
    {var p=units.get(g.variant());var gantry=p==null?null:gantry(l,p);return p!=null&&gantry!=null&&wetSealDryInputsR52(dryBay(l,p),gantry.getLclVisualLevel(1));}
    private boolean wetFloorSealClosedR52(ServerLevel l,Gate g)
    {var cells=g==null?null:wetFloorSealsR52.get(g.resource());return cells!=null&&gateAtRest(l,g,false)&&matches(l,cells,false);}
    private static NervCranePoseR52.State craneState(NervCarrierPlatformEntity n)
    {var capsule=n.getCranePlug();return new NervCranePoseR52.State(RigidTransform.of(n.position(),n.declaredMachineRotationR52()),n.actualCraneBottomOffsetR52(),capsule==null?null:capsule.getCanonicalTransform(),capsule!=null,n.hasCraneReference()?n.position().add(n.getCraneReferenceAnchor()):null,n.hasCraneReference()?n.getCraneReferenceRotation():null);}
    private static boolean sameCranePose(NervCranePoseR52.Pose a,NervCranePoseR52.Pose b)
    {return pose(a.machine(),b.machine())&&pose(a.machine().compose(a.grip()),b.machine().compose(b.grip()))&&a.mount().distanceToSqr(b.mount())<1e-8&&a.yoke().distanceToSqr(b.yoke())<1e-8&&Math.abs(a.released()-b.released())<.0001;}
    /** Actual source contact and native steel; only double arithmetic boundary
     * uncertainty is handled locally, never a structural clearance epsilon. */
    static boolean craneRunningContactCoveredR52(RigidTransform from,RigidTransform to,double x,double z,List<AABB> running)
    {
        var a=from.transformPoint(new Vec3(x,0,z));
        var b=to.transformPoint(new Vec3(x,0,z));
        if(Math.abs(a.y-b.y)>1e-8)return false;
        var axis=from.transformVector(new Vec3(.36,0,0));
        var contacts=new AABB(a.subtract(axis),a.add(axis)).minmax(new AABB(b.subtract(axis),b.add(axis)));
        contacts=new AABB(contacts.minX,a.y-.00002,contacts.minZ-.38,contacts.maxX,a.y,contacts.maxZ+.38);
        var steel=running.stream().filter(q->Math.abs(q.maxY-a.y)<.00002).toList();
        if(NervAirspaceCoverageR52.covered(contacts,steel))return true;
        // Bound only this contact's double arithmetic, including the stored
        // frame's last addition. Each endpoint chain has fewer than 64 rounded
        // operations in the existing Vec3/quaternion path; its intermediates
        // are bounded by these magnitudes for the actual four contact points.
        // The exact union checker and actual native steel are unchanged.
        double span=Math.abs(x)+Math.abs(z)+.36+.38;
        double rx=64*Math.ulp(Math.max(Math.abs(from.translation().x),Math.abs(to.translation().x))+span);
        double rz=64*Math.ulp(Math.max(Math.abs(from.translation().z),Math.abs(to.translation().z))+span);
        if(!Double.isFinite(rx+rz)||contacts.maxX-contacts.minX<=2*rx||contacts.maxZ-contacts.minZ<=2*rz)return false;
        return NervAirspaceCoverageR52.covered(new AABB(contacts.minX+rx,contacts.minY,contacts.minZ+rz,contacts.maxX-rx,contacts.maxY,contacts.maxZ-rz),steel);
    }
    private static boolean craneBearing(ServerLevel l,UnitPlant p,NervCranePoseR52.State from,NervCranePoseR52.State to)
    {
        if(!fixed(l,p.crane().frameCells())||from.machine().rotationErrorDegrees(to.machine())>.001||Math.abs(from.machine().translation().y-to.machine().translation().y)>1e-8)return false;
        var running=new ArrayList<AABB>();for(var c:p.crane().frameCells())if(c.expected().getBlock() instanceof TvCraneGirderR44&&c.expected().getValue(TvCraneGirderR44.SEGMENT)==TvCraneGirderR44.Segment.TOP)for(var box:c.expected().getCollisionShape(l,c.at()).toAabbs())running.add(box.move(c.at()));
        if(running.isEmpty())return false;
        for(double x:new double[]{-4,4})for(double z:new double[]{-2.8,2.8})
        {if(!craneRunningContactCoveredR52(from.machine(),to.machine(),x,z,running))return false;}return true;
    }
    /** The original R50 crane is a noPhysics transient visual. Payload and
     * native pilot clearance stay in clearCapsule/applyInsertion; native rails
     * retain their actual bearing. Visual rope/rail overlap never acquired a
     * new hard movement veto merely because the assembly was relocated. */
    private boolean clearCrane(ServerLevel l,UnitPlant p,EntryPlugCarrierEntity capsule,NervCranePoseR52.State from,NervCranePoseR52.State to)
    {
        if(craneGeometry==null||!craneBearing(l,p,from,to)||gantry(l,p)==null)return false;
        if(!(l.getEntity(p.crane().visual().id()) instanceof NervCarrierPlatformEntity n)
                ||!n.isPlugCrane()||!n.noPhysics||!n.hasDeclaredMachineFrameR52()
                ||n.getUnitVariant()!=p.variant()||!capsule.getUUID().equals(p.plug())
                ||n.getCranePlug()!=null&&n.getCranePlug()!=capsule)return false;
        if(from.coupled()&&!pose(from.plug(),capsule.getCanonicalTransform()))return false;
        try
        {
            // Same coupling/reference and an affine trolley/SLERP payload
            // sample are required; this call performs no actor write.
            from.interpolate(to,.5);
            if(from.referenceRotation()!=null&&!from.referenceRotation().equals(to.referenceRotation()))return false;
            // Fixed native rails and the complete physical payload retain
            // their own loaded checks. A noPhysics visual adds no new chunk
            // loading permission or unrelated-region movement veto.
            return true;
        }
        catch(IllegalArgumentException invalid){return false;}
    }
    private boolean crane(ServerLevel l,UnitPlant p,EntryPlugCarrierEntity plug,RigidTransform target,boolean stow)
    {
        if(!fixed(l,p.crane().frameCells()))return false;var entity=l.getEntity(p.crane().visual().id());if(!(entity instanceof NervCarrierPlatformEntity n)||!n.isPlugCrane())return false;
        var eye=target.transformPoint(EntryPlugKinematics.CRANE_ATTACHMENT_P);var base=p.crane().visual().frame();var localEye=base.inverse().transformPoint(eye);double along=localEye.dot(p.crane().railAxis());if(along<p.crane().railMin()||along>p.crane().railMax()||localEye.y>=0)return false;
        Vec3 wanted=base.transformPoint(p.crane().railAxis().scale(along));double offset=localEye.y;
        if(stow){wanted=p.crane().stow().translation();double step=p.crane().hoistStep();offset=Math.min(p.crane().stowBottom(),n.actualCraneBottomOffsetR52()+step);}
        var from=craneState(n);var reference=from.referenceWorld();var referenceRotation=from.referenceRotation();
        if(stow)
        {
            if(wanted.distanceToSqr(n.position())>1e-8)return false;
            if(from.coupled()){reference=from.plug().transformPoint(EntryPlugKinematics.CRANE_ATTACHMENT_P);referenceRotation=from.plug().rotation();var release=new NervCranePoseR52.State(from.machine(),from.bottom(),null,false,reference,referenceRotation);if(!sameCranePose(from.pose(craneGeometry.mount()),release.pose(craneGeometry.mount())))return false;from=release;}
        }
        else if(!from.coupled()){var attach=new NervCranePoseR52.State(from.machine(),from.bottom(),plug.getCanonicalTransform(),true,reference,referenceRotation);if(!sameCranePose(from.pose(craneGeometry.mount()),attach.pose(craneGeometry.mount())))return false;from=attach;}
        offset=Math.round(Math.min(-.001,offset)*1000)/1000F;var to=new NervCranePoseR52.State(RigidTransform.of(wanted,base.rotation()),offset,stow?null:target,!stow,reference,referenceRotation);if(!clearCrane(l,p,plug,from,to))return false;
        if(stow&&n.getCranePlug()!=null)n.setCraneReferenceR52(plug.getCanonicalTransform());n.configurePlugCrane(p.variant(),offset);n.moveControlled(wanted.x,wanted.y,wanted.z);n.setYRot(yaw(p.crane().visual().frame()));n.linkCranePlug(stow?null:plug);
        return n.position().distanceToSqr(wanted)<1e-8&&(!stow||Math.abs(n.actualCraneBottomOffsetR52()-p.crane().stowBottom())<=.0011);
    }
    private boolean approachCrane(ServerLevel l,UnitPlant p,EntryPlugCarrierEntity capsule,int age,CompoundTag data)
    {
        if(!(l.getEntity(p.crane().visual().id()) instanceof NervCarrierPlatformEntity n)||!n.isPlugCrane()||age<1||age>36)return false;var from=craneState(n);if(from.coupled())return false;
        var actual=capsule.getCanonicalTransform();var eye=actual.transformPoint(EntryPlugKinematics.CRANE_ATTACHMENT_P);var local=from.machine().inverse().transformPoint(eye);
        if(!data.contains("ExtractStartBottomR52")){if(age!=1)return false;data.putDouble("ExtractStartBottomR52",from.bottom());putFrame(data,"ExtractCraneReferenceR52",actual);putFrame(data,"CraneApproachStartR53",from.machine());}
        if(!pose(getFrame(data,"ExtractCraneReferenceR52"),actual))return false;double start=data.getDouble("ExtractStartBottomR52"),previous=start+(local.y-start)*NervCranePoseR52.smooth((age-1)/36F),next=start+(local.y-start)*NervCranePoseR52.smooth(age/36F);previous=Math.round(previous*1000)/1000F;next=Math.round(next*1000)/1000F;
        if(Math.abs(from.bottom()-previous)>.0011)return false;var observed=new NervCranePoseR52.State(from.machine(),from.bottom(),null,false,eye,actual.rotation());if(!NervR50CarrierModeR53.enabled()&&!sameCranePose(from.pose(craneGeometry.mount()),observed.pose(craneGeometry.mount())))return false;
        var machine=from.machine();
        if(data.contains("CraneApproachStartR53"))
        {
            var base=p.crane().visual().frame();var at=base.inverse().transformPoint(eye);double along=at.dot(p.crane().railAxis());
            if(along<p.crane().railMin()||along>p.crane().railMax())return false;
            var end=RigidTransform.of(base.transformPoint(p.crane().railAxis().scale(along)),base.rotation());
            machine=getFrame(data,"CraneApproachStartR53").interpolate(end,NervCranePoseR52.smooth(age/36F));
        }
        var to=new NervCranePoseR52.State(machine,next,null,false,eye,actual.rotation());if(!clearCrane(l,p,capsule,observed,to))return false;n.setCraneReferenceR52(actual);n.configurePlugCrane(p.variant(),next);n.moveControlled(machine.translation().x,machine.translation().y,machine.translation().z);n.linkCranePlug(age==36?capsule:null);return true;
    }
    private EntryPlugCarrierEntity maintenanceCapsuleR53(ServerLevel level,UnitPlant plant)
    {
        var existing=level.getEntity(plant.plug());
        if(existing instanceof EntryPlugCarrierEntity capsule)return capsule;
        if(existing!=null||!EntryPlugDisposalR31.destroyed(level,plant.plug()))return null;
        var capsule=ModEntities.ENTRY_PLUG_CARRIER.get().create(level);if(capsule==null)return null;
        capsule.setUUID(plant.plug());capsule.assignVariant(plant.variant());capsule.resetOriginalAtDockR53(plant.dock());
        if(!level.addFreshEntity(capsule))return null;
        EntryPlugDisposalR31.restoreForMaintenanceR53(level,plant.plug());
        var fleet=EvaFleetSavedData.get(level.getServer());var entry=fleet.entry(plant.variant()).orElseThrow();
        fleet.put(plant.variant(),entry.withEntryPlug(plant.plug()));
        return capsule;
    }
    private boolean originalGraph(ServerLevel l,Original o,boolean occupied)
    {
        var e=hull(l,o);var p=plant(o);if(e==null||p==null||!e.isAlive())return false;var fleet=EvaFleetSavedData.get(l.getServer()).entry(o.variant()).orElse(null);if(fleet==null||!fleet.canonicalId().equals(o.eva())||!o.plug().equals(fleet.entryPlugId())&&(occupied||fleet.entryPlugId()!=null||!EntryPlugDisposalR31.destroyed(l,o.plug())))return false;
        if(!occupied)return TransportMembershipR52.hullRecoveryAdmission(o,e.getPersistentData(),Set.copyOf(e.getPassengers().stream().map(Entity::getUUID).toList()),e.isEntryPlugInserted(),EvaShutdownR30.disabled(e));
        var capsule=plug(l,o);return capsule!=null&&capsule.isAlive()&&capsule.getFirstPassenger()!=null&&capsule.getFirstPassenger().getUUID().equals(o.pilot())&&capsule.getFirstPassenger().getVehicle()==capsule;
    }
    @Override public Preparation prepareOriginal(ServerLevel l,Original o,CompoundTag data)
    {
        var p=plant(o);var e=hull(l,o);var capsule=plug(l,o);if(p==null||e==null||capsule==null||!originalGraph(l,o,true)){hold(o,"original_custody_or_manifest_missing");return Preparation.WAITING;}
        if(data.contains("LastPrepareTick")&&data.getLong("LastPrepareTick")==l.getGameTime())return Preparation.WAITING;data.putLong("LastPrepareTick",l.getGameTime());
        if(!data.contains("Prepare")){if(!pose(capsule.getCanonicalTransform(),p.dock())||e.position().distanceToSqr(p.bay().translation())>1e-6||!bridgeMatches(l,p,9)||!personnelDoors(l,p,false)){hold(o,"original_dock_bay_bridge_or_personnel_door_not_actual");return Preparation.WAITING;}rememberBridge(data,9);data.putInt("BridgeStartAmount",9);capsule.beginCabinPreparation();e.setNervLogisticsLocked(true);data.putString("Prepare",Prepare.HATCH.name());data.putInt("PrepareTicks",0);}
        if(!savedBridgeMatches(l,p,data)){hold(o,"actual_bridge_or_saved_owner_epoch_changed");return Preparation.WAITING;}
        Prepare phase=Prepare.valueOf(data.getString("Prepare"));int ticks=data.getInt("PrepareTicks");Set<UUID> own=TransportMembershipR52.members(o,Kind.OCCUPIED);
        var front=gates.get("bay_"+p.variant()+"_front");
        var recovery=frontSealRecoveryR53(phase,hasWetFloorSealR52(front),gateAtRest(l,front,true));
        if(recovery!=phase){
            var carrier=EvaMechanicalFrameR52.originalCarrierControllerR52(e);
            if(carrier==null||!pose(NervOriginalCarrierR52.actualRoot(carrier,1),p.bay())||e.position().distanceToSqr(p.bay().translation())>1e-6||data.getDouble("ContinuousDistanceR52")!=0||!originalLaunchLock(l,p.variant(),e,capsule))return Preparation.WAITING;
            advance(data,recovery);return Preparation.WAITING;
        }
        switch(phase)
        {
            case HATCH -> {if(!capsule.isHatchFullySealed()){hold(o,"actual_pressure_leaves_closing_or_obstructed");return Preparation.WAITING;}advance(data,Prepare.BRIDGE);}
            case BRIDGE ->
            {
                int wanted=NervAssemblyClocksR52.bridgeRemaining(ticks+1);if((ticks+1)%5==0||ticks>=39)if(!applyBridgeState(l,p,wanted,data,own)){hold(o,"complete_original_bridge_state_blocked_"+wanted);return Preparation.WAITING;}
                capsule.setCabinSequenceProgress(Math.min(30,Math.max(1,(int)Math.round(30D*(ticks+1)/40))));
                if(ticks>=39){if(!bridgeMatches(l,p,0)||capsule.getInsertionStage()!=EntryPlugCarrierEntity.STAGE_OCCUPIED||!capsule.transitionInsertionStage(EntryPlugCarrierEntity.STAGE_OCCUPIED,EntryPlugCarrierEntity.STAGE_INSERTING)){hold(o,"original_insertion_epoch_or_bridge_changed");return Preparation.WAITING;}advance(data,Prepare.INSERT);}
            }
            case INSERT ->
            {
                if(capsule.isInsertionAbortRequested()||capsule.getInsertionStage()!=EntryPlugCarrierEntity.STAGE_INSERTING){hold(o,"original_insertion_aborted_or_stage_changed");return Preparation.WAITING;}
                int age=ticks+1;EvaDorsalMechanism.prepare(e,age);double progress=NervAssemblyClocksR52.insertionProgress(age);var target=EntryPlugKinematics.insertionTransform(e,p.dock(),progress);
                if(!NervMappedPlugMechanicsR52.clearCapsule(l,e,capsule,capsule.getCanonicalTransform(),target,p.crane().visual().id())){hold(o,"actual_capsule_sweep_blocked");return Preparation.WAITING;}
                boolean approaching=age<=36&&l.getEntity(p.crane().visual().id()) instanceof NervCarrierPlatformEntity hoist&&hoist.getCranePlug()==null;
                if(!(approaching?approachCrane(l,p,capsule,age,data):crane(l,p,capsule,target,false))){hold(o,"actual_crane_coupling_or_rail_not_ready");return Preparation.WAITING;}
                // Mapped producer performs actual full geometry sweep; absent
                // permission/geometry is a concrete HOLD, never a teleport.
                if(!NervMappedPlugMechanicsR52.applyInsertion(l,e,capsule,capsule.getCanonicalTransform(),target,p.crane().visual().id())){hold(o,"actual_capsule_sweep_blocked");return Preparation.WAITING;}
                if(l.getEntity(p.crane().visual().id()) instanceof NervCarrierPlatformEntity hoist&&age>=36)hoist.linkCranePlug(capsule);capsule.setInsertionProgress((int)Math.round(progress*100));capsule.setCabinSequenceProgress(30+(int)Math.round(progress*40));
                if(age>=190){if(!capsule.lockToEva(e)||!e.bindEntryPlug(capsule,capsule.getCabinProgress())){hold(o,"original_lock_graph_rejected");return Preparation.WAITING;}advance(data,Prepare.SEAL);}
            }
            case SEAL -> {if(!originalLaunchLock(l,p.variant(),e,capsule)){hold(o,"real_launch_lock_changed");return Preparation.WAITING;}EvaDorsalMechanism.seal(e,ticks+1);if(!crane(l,p,capsule,p.dock(),true))return Preparation.WAITING;if(ticks>=59)advance(data,Prepare.DRAIN);}
            case DRAIN ->
            {
                if(!originalLaunchLock(l,p.variant(),e,capsule)||!crane(l,p,capsule,p.dock(),true)||!NervR50CarrierModeR53.enabled()&&!originalClampsBear(l,p)||!gateAtRest(l,servicePit(p),false)){hold(o,"wet_bay_requires_actual_closed_shutter_and_original_clamps");return Preparation.WAITING;}
                int removed=NervAssemblyClocksR52.drainedLayers(p.lcl().size(),ticks+1);int accepted=data.getInt("DrainedLayers");while(accepted<removed){if(!change(l,p.lcl().get(p.lcl().size()-1-accepted),true,own)){hold(o,"actual_lcl_layer_not_owned_"+accepted);return Preparation.WAITING;}data.putInt("DrainedLayers",++accepted);}
                var gantry=gantry(l,p);if(gantry==null)return Preparation.WAITING;gantry.setLclVisualLevel(Math.max(0,p.lcl().size()-(ticks+1)/4F));
                if(NervR50CarrierModeR53.enabled())
                {
                    float progress=Math.min(1,(ticks+1)/(float)Math.max(p.raiseTicks(),p.lcl().size()*4));
                    float rise=EvaDorsalMechanism.smooth(progress);
                    if(!acceptCarrierActuatorR52(l,e,p.bay(),e.carrierRiseProgress(1),rise,own,o,data))return Preparation.WAITING;
                    gantry.setRestraintProgress(1-rise);
                    data.remove("DryVerified");
                    if(accepted==p.lcl().size()&&dryBay(l,p)&&rise==1)advance(data,Prepare.FRONT_SEAL_OPEN);
                }
                else {data.remove("DryVerified");if(accepted==p.lcl().size()&&dryBay(l,p))advance(data,Prepare.LOWER_FRAME_OPEN);}
            }
            case LOWER_FRAME_OPEN -> {if(NervR50CarrierModeR53.enabled()){var oldGantry=gantry(l,p);if(oldGantry!=null)oldGantry.setLowerFrameProgressR52(1);advance(data,Prepare.PIT_OPEN);break;}var g=gantry(l,p);if(!dryBay(l,p)||!originalClampsBear(l,p)||!gateAtRest(l,servicePit(p),false)||g==null||!g.lowerFrameDeclaredR52())return Preparation.WAITING;float next=Math.min(1,(ticks+1)/(float)NervLowerFrameR52.OPEN_TICKS);try{if(!NervLowerFrameR52.clearAdvance(l,g,g.lowerFrameProgressR52(1),next,own)){hold(o,"actual_lower_crossbar_or_winch_motion_blocked");return Preparation.WAITING;}}catch(java.io.IOException failure){return Preparation.WAITING;}g.setLowerFrameProgressR52(next);if(next==1)advance(data,Prepare.PIT_OPEN);}
            case PIT_OPEN -> {if(!dryBay(l,p)||!originalClampsBear(l,p)){hold(o,"dry_readback_or_original_clamp_support_changed");return Preparation.WAITING;}if(gate(l,servicePit(p),true,own))advance(data,Prepare.FRONT_SEAL_OPEN);}
            case FRONT_RECOVER_CLAMPS ->
            {
                var g=gantry(l,p);var carrier=EvaMechanicalFrameR52.originalCarrierControllerR52(e);
                if(g==null||carrier==null||!dryBay(l,p)||!gateAtRest(l,servicePit(p),true)||e.carrierRiseProgress(1)!=1||!carrierSupportReadyR53(l,e))return Preparation.WAITING;
                float closure=Math.min(1,g.getRestraintProgress()+1F/40);
                if(!NervPlantMotionR52.clearRestraints(l,p.variant(),p.gantry().frame(),g.getRestraintProgress(),closure,own))return Preparation.WAITING;
                g.setRestraintProgress(closure);
                if(closure==1&&originalClampsBear(l,p))try{if(NervOriginalCarrierR52.setAttachedR52(l,carrier,e,false))advance(data,Prepare.FRONT_RECOVER_LOWER);}catch(java.io.IOException missing){return Preparation.WAITING;}
            }
            case FRONT_RECOVER_LOWER ->
            {
                if(!dryBay(l,p)||!originalClampsBear(l,p)||!gateAtRest(l,servicePit(p),true))return Preparation.WAITING;
                var carrier=EvaMechanicalFrameR52.originalCarrierControllerR52(e);if(carrier==null||NervOriginalCarrierR52.attachedTo(carrier,e))return Preparation.WAITING;
                if(!NervOriginalCarrierR52.actualRidePoseR52(carrier).equals(NervLegacyCarrierRideR52.rest()))return Preparation.WAITING;
                float next=Math.max(0,e.carrierRiseProgress(1)-1F/p.raiseTicks());
                if(!acceptCarrierActuatorR52(l,e,p.bay(),e.carrierRiseProgress(1),next,own,o,data))return Preparation.WAITING;
                if(next==0)advance(data,Prepare.FRONT_RECOVER_BRIDGE);
            }
            case FRONT_RECOVER_BRIDGE ->
            {
                if(!dryBay(l,p)||!originalClampsBear(l,p)||e.carrierRiseProgress(1)!=0||!gateAtRest(l,servicePit(p),true))return Preparation.WAITING;
                if(groundGuidesDeclared){var g=gantry(l,p);if(g==null)return Preparation.WAITING;float next=Math.max(0,g.serviceGuideBridgeR52(1)-1F/NervServiceFootDriveR52.BRIDGE_CLOSE_TICKS);
                    try{if(!NervServiceFootDriveR52.clearBridge(l,g,g.serviceGuideBridgeR52(1),next,own))return Preparation.WAITING;}catch(java.io.IOException missing){return Preparation.WAITING;}
                    g.setServiceGuideBridgeR52(next);if(next!=0)break;
                }
                advance(data,Prepare.FRONT_SEAL_OPEN);
            }
            case FRONT_SEAL_OPEN ->
            {
                if(NervR50CarrierModeR53.enabled()&&e.carrierRiseProgress(1)==1&&gantry(l,p)!=null&&gantry(l,p).getRestraintProgress()==0)
                {
                    if(dryBay(l,p)&&gate(l,front,true,own))advance(data,Prepare.RELEASE_CLAMPS);
                    break;
                }
                if(!wetFrontReturnClosePermitR52(dryBay(l,p),e.carrierRiseProgress(1),originalClampsBear(l,p),serviceBridgeReadyR52(l,p,false),gateAtRest(l,servicePit(p),true)))return Preparation.WAITING;
                if(!gate(l,front,true,own))return Preparation.WAITING;
                advance(data,Prepare.SERVICE_BRIDGE_OPEN);
            }
            case SERVICE_BRIDGE_OPEN -> {if(NervR50CarrierModeR53.enabled()){advance(data,Prepare.RAISE);break;}if(!dryBay(l,p)||!originalClampsBear(l,p)||!gateAtRest(l,servicePit(p),true))return Preparation.WAITING;if(!groundGuidesDeclared){advance(data,Prepare.RAISE);break;}var g=gantry(l,p);float next=Math.min(1,(ticks+1)/(float)NervServiceFootDriveR52.BRIDGE_OPEN_TICKS);try{if(g==null||!NervServiceFootDriveR52.clearBridge(l,g,g.serviceGuideBridgeR52(1),next,own)){hold(o,"actual_service_guide_bridge_open_blocked");return Preparation.WAITING;}}catch(java.io.IOException missing){return Preparation.WAITING;}g.setServiceGuideBridgeR52(next);if(next==1)advance(data,Prepare.RAISE);}
            case RAISE -> {if(!dryBay(l,p)||!originalClampsBear(l,p)||!gateAtRest(l,servicePit(p),true))return Preparation.WAITING;if(!NervR50CarrierModeR53.enabled()&&!fixed(l,p.carrierSupport())||!serviceBridgeReadyR52(l,p,true)){hold(o,"physical_carrier_support_or_guide_bridge_missing");return Preparation.WAITING;}float rise=Math.min(1,(ticks+1)/(float)p.raiseTicks());if(!acceptCarrierActuatorR52(l,e,p.bay(),e.carrierRiseProgress(1),rise,own,o,data)){hold(o,"actual_carrier_rise_sweep_blocked");return Preparation.WAITING;}if(ticks+1>=p.raiseTicks()&&e.carrierRiseProgress(1)==1&&EvaDorsalMechanism.open(e)<.0001F&&EvaDorsalMechanism.bow(e)<.0001F){if(!carrierSupportReadyR53(l,e)){hold(o,"actual_sole_to_full_carrier_bearing_absent");return Preparation.WAITING;}advance(data,Prepare.RELEASE_CLAMPS);}}
            case RELEASE_CLAMPS -> {if(!dryBay(l,p)||!gateAtRest(l,servicePit(p),true)||e.carrierRiseProgress(1)!=1||!carrierSupportReadyR53(l,e))return Preparation.WAITING;var gantry=gantry(l,p);if(gantry==null)return Preparation.WAITING;float closure=Math.min(gantry.getRestraintProgress(),1-Math.min(1,(ticks+1)/40F));if(!NervPlantMotionR52.clearRestraints(l,p.variant(),p.gantry().frame(),gantry.getRestraintProgress(),closure,own))return Preparation.WAITING;gantry.setRestraintProgress(closure);if((ticks>=39||NervR50CarrierModeR53.enabled()&&gantry.getRestraintProgress()==0)&&closure==0){if(!EvaMechanicalFrameR52.capture(e,o)){hold(o,"actual_complete_rigid_capture_rejected");return Preparation.WAITING;}captureAssembly(l,o,data);advance(data,Prepare.READY);}}
            case READY -> {return originalLaunchLock(l,p.variant(),e,capsule)&&EvaMechanicalFrameR52.active(e)?Preparation.READY:Preparation.WAITING;}
        }
        if(phase.name().equals(data.getString("Prepare")))data.putInt("PrepareTicks",ticks+1);return Preparation.WAITING;
    }
    @Override public boolean requiresPreparationRecoveryR53(ServerLevel l,Original o,CompoundTag data)
    {
        if(!data.contains("Prepare")||!originalGraph(l,o,true)||data.getDouble("ContinuousDistanceR52")!=0||data.getCompound("ContinuousClockR52").getDouble("SpeedMps")!=0)return false;
        var p=plant(o);var e=hull(l,o);if(p==null||e==null||e.position().distanceToSqr(p.bay().translation())>1e-6)return false;
        var carrier=EvaMechanicalFrameR52.originalCarrierControllerR52(e);if(carrier==null||!pose(NervOriginalCarrierR52.actualRoot(carrier,1),p.bay()))return false;
        var phase=Prepare.valueOf(data.getString("Prepare"));var front=gates.get("bay_"+p.variant()+"_front");
        return frontSealRecoveryR53(phase,hasWetFloorSealR52(front),gateAtRest(l,front,true))!=phase;
    }
    static void validateBridgeStates(List<List<FixedCell>> states)
    {
        require(states.size()==10,"Exact original bridge amount0..9 states required");Set<BlockPos> footprint=null;
        for(var state:states){require(!state.isEmpty(),"No empty bridge snapshot");var cells=new HashSet<BlockPos>();for(var cell:state)require(cells.add(cell.at()),"Duplicate within one bridge state");if(footprint==null)footprint=Set.copyOf(cells);else require(footprint.equals(cells),"Every bridge state must describe the same complete footprint");}
        var unique=new HashSet<Set<FixedCell>>();for(var state:states)require(unique.add(Set.copyOf(state)),"Every original bridge amount needs one unambiguous complete physical state");
    }
    private static boolean bridgeMatches(ServerLevel l,UnitPlant p,int amount)
    {return amount>=0&&amount<=9&&fixed(l,p.bridgeStates().get(amount));}
    private void rememberBridge(CompoundTag data,int amount)
    {data.putInt("BridgeAmount",amount);data.putString("BridgeDirectory",directory.fingerprint());data.putLong("BridgeEpoch",epoch);}
    static boolean savedBridgeProvenance(CompoundTag data,long epoch,String directory)
    {return data.contains("BridgeAmount")&&data.getInt("BridgeAmount")>=0&&data.getInt("BridgeAmount")<=9&&data.getLong("BridgeEpoch")==epoch&&data.getString("BridgeDirectory").equals(directory);}
    private boolean savedBridgeMatches(ServerLevel l,UnitPlant p,CompoundTag data)
    {return savedBridgeProvenance(data,epoch,directory.fingerprint())&&bridgeMatches(l,p,data.getInt("BridgeAmount"));}
    private boolean applyBridgeState(ServerLevel l,UnitPlant p,int requested,CompoundTag data,Set<UUID> own)
    {
        if(requested<0||requested>9)return false;int completed=-1;
        if(data.contains("BridgeAmount")){completed=data.getInt("BridgeAmount");if(!savedBridgeMatches(l,p,data))return false;}
        else{for(int i=0;i<=9;i++)if(bridgeMatches(l,p,i)){if(completed>=0)return false;completed=i;}if(completed<0)return false;}
        var before=p.bridgeStates().get(completed);var wanted=p.bridgeStates().get(requested);var previous=new HashMap<BlockPos,BlockState>();for(var cell:before)previous.put(cell.at(),cell.expected());var changes=new ArrayList<Cell>();
        for(var cell:wanted){if(l.getBlockEntity(cell.at())!=null||!l.areEntitiesLoaded(net.minecraft.world.level.ChunkPos.asLong(cell.at().getX()>>4,cell.at().getZ()>>4)))return false;var old=previous.get(cell.at());if(!old.equals(cell.expected()))changes.add(new Cell(cell.at(),old,cell.expected()));}
        if(!NervPlantMotionR52.clearBridgeStep(l,changes,own)||!canChange(l,changes,true,own))return false;
        for(var cell:changes)l.setBlock(cell.at(),cell.open(),2);
        if(!bridgeMatches(l,p,requested)){for(var cell:changes)l.setBlock(cell.at(),cell.closed(),2);holds.put(p.eva(),"complete_bridge_readback_failed_after_atomic_delta");return false;}
        if(!data.contains("BridgeStartAmount"))data.putInt("BridgeStartAmount",completed);rememberBridge(data,requested);return true;
    }
    private static void advance(CompoundTag data,Prepare next){data.putString("Prepare",next.name());data.putInt("PrepareTicks",0);}
    static Prepare frontSealRecoveryR53(Prepare phase,boolean sealedFront,boolean frontOpen)
    {
        if(!sealedFront||frontOpen)return phase;
        return switch(phase){
            case READY,RELEASE_CLAMPS -> Prepare.FRONT_RECOVER_CLAMPS;
            case RAISE -> Prepare.FRONT_RECOVER_LOWER;
            case SERVICE_BRIDGE_OPEN -> Prepare.FRONT_RECOVER_BRIDGE;
            default -> phase;
        };
    }
    private static double smoother(double t){return t*t*t*(t*(t*6-15)+10);}
    @Override public boolean restoreOriginalPreparation(ServerLevel l,Original o,CompoundTag data)
    {
        if(!originalGraph(l,o,true))return hold(o,"restore_original_graph_missing");var p=plant(o);var e=hull(l,o);var capsule=plug(l,o);if(e.position().distanceToSqr(p.bay().translation())>1e-6||!(NervR50CarrierModeR53.enabled()?EvaMechanicalFrameR52.originalCarrierControllerR52(e)!=null&&pose(NervOriginalCarrierR52.actualRoot(EvaMechanicalFrameR52.originalCarrierControllerR52(e),1),p.bay()):fixed(l,p.carrierSupport())))return false;
        if(!data.contains("Prepare"))return pose(capsule.getCanonicalTransform(),p.dock())&&bridgeMatches(l,p,9);Prepare phase=Prepare.valueOf(data.getString("Prepare"));int age=data.getInt("PrepareTicks");if(age<0)return false;
        if(!savedBridgeMatches(l,p,data))return false;
        if(phase==Prepare.DRAIN){int removed=data.getInt("DrainedLayers");if(removed<0||removed>p.lcl().size())return false;for(int i=0;i<p.lcl().size();i++)if(!matches(l,p.lcl().get(i),i>=p.lcl().size()-removed))return false;}
        if(phase.ordinal()>=Prepare.LOWER_FRAME_OPEN.ordinal()&&!dryBay(l,p))return false;
        if(phase.ordinal()<=Prepare.DRAIN.ordinal()&&!gateAtRest(l,servicePit(p),false))return false;
        if(!NervR50CarrierModeR53.enabled()&&phase.ordinal()>=Prepare.PIT_OPEN.ordinal()&&(!gantry(l,p).lowerFrameDeclaredR52()||gantry(l,p).lowerFrameProgressR52(1)!=1))return false;
        if(phase.ordinal()>=Prepare.RAISE.ordinal()&&!gateAtRest(l,servicePit(p),true))return false;
        if(!NervR50CarrierModeR53.enabled()&&(phase==Prepare.DRAIN||phase==Prepare.LOWER_FRAME_OPEN||phase==Prepare.PIT_OPEN||phase==Prepare.FRONT_SEAL_OPEN||phase==Prepare.SERVICE_BRIDGE_OPEN||phase==Prepare.RAISE||phase==Prepare.FRONT_RECOVER_LOWER||phase==Prepare.FRONT_RECOVER_BRIDGE)&&!originalClampsBear(l,p))return false;
        if((phase==Prepare.RELEASE_CLAMPS||phase==Prepare.READY)&&!carrierSupportReadyR53(l,e))return false;
        if(phase.ordinal()<Prepare.INSERT.ordinal())return pose(capsule.getCanonicalTransform(),p.dock())&&capsule.getInsertionStage()==EntryPlugCarrierEntity.STAGE_OCCUPIED;
        if(phase==Prepare.INSERT){double progress=NervAssemblyClocksR52.insertionProgress(age);return capsule.getInsertionStage()==EntryPlugCarrierEntity.STAGE_INSERTING&&pose(capsule.getCanonicalTransform(),EntryPlugKinematics.insertionTransform(e,p.dock(),progress))&&capsule.isHatchFullySealed()&&bridgeMatches(l,p,0);}
        return originalLaunchLock(l,o.variant(),e,capsule)&&pose(capsule.getCanonicalTransform(),EntryPlugKinematics.lockedTransform(e))&&(phase!=Prepare.READY||EvaMechanicalFrameR52.active(e));
    }
    private static final TicketType<net.minecraft.world.level.ChunkPos> CONTINUOUS_ROUTE_TICKET_R52=TicketType.create("r52_continuous_route",Comparator.comparingLong(net.minecraft.world.level.ChunkPos::toLong),100);
    private record ContinuousGeometryR52(String route,FootSupportFrameR52.Binding binding,FullAssemblyGeometryR52.Captured source,double from,List<DirectoryTrajectoryR52> paths,Set<net.minecraft.world.level.ChunkPos> chunks){}
    private final Map<UUID,ContinuousGeometryR52> continuousGeometryR52=new HashMap<>();
    private List<DirectoryTrajectoryR52> continuousPathsR52(Route route,double from,double to,FootSupportFrameR52.Binding binding)
    {var paths=new ArrayList<DirectoryTrajectoryR52>();for(double a=from;a<to;){double b=Math.min(to,a+16);paths.addAll(directory.routeSlices(route,a,b,binding));if(paths.size()>2048)throw new IllegalArgumentException("Bounded full continuous route required");a=b;}return List.copyOf(paths);}
    private ContinuousGeometryR52 continuousGeometryR52(ServerLevel level,Original o,Route route,FootSupportFrameR52.Binding binding,CompoundTag data,boolean atCurrent)
    {
        var source=captured.get(o.eva());if(source==null)return null;double from=data.getDouble("ContinuousDistanceR52"),total=directory.routeLength(route);if(!Double.isFinite(from)||from<0||from>total)return null;
        var known=continuousGeometryR52.get(o.eva());if(known!=null&&known.route().equals(route.id())&&known.binding().equals(binding)&&known.source()==source&&(!atCurrent||known.from()==from))return known;
        var paths=continuousPathsR52(route,from,total,binding);var chunks=new HashSet<net.minecraft.world.level.ChunkPos>();if(!paths.isEmpty())for(var box:source.sweep(paths,.005).envelopes())for(int x=(int)Math.floor(box.minX)>>4;x<=((int)Math.floor(box.maxX)>>4);x++)for(int z=(int)Math.floor(box.minZ)>>4;z<=((int)Math.floor(box.maxZ)>>4);z++)chunks.add(new net.minecraft.world.level.ChunkPos(x,z));
        // Fixed rail feet and complete gate machinery may extend beyond the original body envelope.
        for(String id:directory.resources(route)){for(var cell:resources.getOrDefault(id,List.of()))chunks.add(new net.minecraft.world.level.ChunkPos(cell.at()));var gate=gates.get(id);if(gate!=null){chunks.add(new net.minecraft.world.level.ChunkPos(BlockPos.containing(gate.frame().translation())));for(var cell:gate.supports())chunks.add(new net.minecraft.world.level.ChunkPos(cell.at()));for(var step:gate.collisionSteps())for(var cell:step)chunks.add(new net.minecraft.world.level.ChunkPos(cell.at()));}}
        var context=NervRouteRuntimeR52.flightContext(level);if(context!=null)for(String id:directory.resources(route)){var bound=context.bindings().get(id);if(bound!=null)for(var cell:bound.cells())chunks.add(new net.minecraft.world.level.ChunkPos(cell.position()));}
        if(chunks.size()>8192)throw new IllegalArgumentException("Continuous route actual chunk scope exceeds bound");var result=new ContinuousGeometryR52(route.id(),binding,source,from,paths,Set.copyOf(chunks));continuousGeometryR52.put(o.eva(),result);return result;
    }
    @Override public boolean prepareContinuousRouteR52(ServerLevel l,Original o,Route route,CompoundTag data)
    {
        if(!commissioned||!route.continuousUpright()||!originalGraph(l,o,kind(data)==Kind.OCCUPIED))return hold(o,"continuous_original_custody_or_profile_missing");data.putString("RouteR52",route.id());
        var e=hull(l,o);if((!EvaMechanicalFrameR52.active(e)||data.getBoolean("ReceiverAlignmentR53"))&&!captureReceiver(l,o,route,directory.leg(route.legs().get(0)),data))return false;
        var binding=originalBinding(l,o,data);if(binding==null)return false;var current=EvaMechanicalFrameR52.frame(e,1);if(!data.contains("ContinuousRotationR52"))data.put("ContinuousRotationR52",NervAircraftFrameR52.encodeRigid(new RigidTransform(Vec3.ZERO,current.qx(),current.qy(),current.qz(),current.qw())));
        if(current.rotationErrorDegrees(NervAircraftFrameR52.decodeRigid(data.getCompound("ContinuousRotationR52")))>.0001)return hold(o,"continuous_captured_rotation_changed");
        // The route needs readable native geometry. Original moving actors and
        // gate controllers retain their separate entity-ticking restore tickets.
        var geometry=continuousGeometryR52(l,o,route,binding,data,false);if(geometry==null)return false;boolean ready=true;String pending="";for(var chunk:geometry.chunks()){l.getChunkSource().addRegionTicket(CONTINUOUS_ROUTE_TICKET_R52,chunk,0,chunk);if(l.getChunkSource().getChunkNow(chunk.x,chunk.z)==null){ready=false;pending="route_chunk/"+chunk.x+"/"+chunk.z;}}
        var context=NervRouteRuntimeR52.flightContext(l);if(context==null)return false;var lease=context.pool().groundTaskR52(o);if(lease==null||!lease.route().equals(route.id())||!context.pool().resourcesHeldR52(lease.task(),directory.resources(route)))return hold(o,"continuous_full_route_lease_missing");
        for(String id:directory.resources(route)){var r=directory.resource(id);if(r.kind()==ResourceKind.DOOR){var g=gates.get(id);if(g==null||!gate(l,g,true,TransportMembershipR52.members(o,kind(data)))){ready=false;pending="route_gate/"+id;}}else if(!context.nativeAccess().resourceReady(id,false)){ready=false;pending="route_resource/"+id;}}
        if(ready)holds.remove(o.eva());else hold(o,pending);
        return ready;
    }
    @Override public List<DirectoryTrajectoryR52> continuousRoutePathsR52(ServerLevel l,Original o,Route route,CompoundTag data)
    {var binding=originalBinding(l,o,data);if(binding==null)return List.of();var geometry=continuousGeometryR52(l,o,route,binding,data,true);return geometry==null?List.of():geometry.paths();}
    @Override public boolean prepareBankHeadsR53(ServerLevel l,Original o,Route route,UUID task,CompoundTag data)
    {return prepareBankHeadsR53(l,o,route,task,data,route.recovery());}
    @Override public boolean prepareBankForRetargetR53(ServerLevel l,Original o,Route route,UUID task,CompoundTag data)
    {return !route.recovery()&&prepareBankHeadsR53(l,o,route,task,data,true);}
    private boolean prepareBankHeadsR53(ServerLevel l,Original o,Route route,UUID task,CompoundTag data,boolean toTransfer)
    {
        if(NervR50CarrierModeR53.enabled())return true;
        if(!route.phased()||!originalGraph(l,o,kind(data)==Kind.OCCUPIED))return hold(o,"bank_head_original_custody_missing");
        var run=NervLaunchPhasesR53.current(data,task,directory,route,data.getDouble("ContinuousDistanceR52"));if(!run.bankStop()||data.getDouble("ContinuousDistanceR52")!=run.stop()||data.contains("ContinuousBrakeR52"))return hold(o,"bank_head_requires_exact_unbraked_bank_stop");
        NervLaunchPhasesR53.verifyStoppedBank(data,task,directory,route,run.stop());
        var e=hull(l,o);var carrier=EvaMechanicalFrameR52.originalCarrierControllerR52(e);var binding=originalBinding(l,o,data);if(carrier==null||binding==null)return false;
        var outbound=route.recovery()?directory.route(route.reverseOf()):route;int index=-1;for(int i=0;i<outbound.legs().size();i++)if(directory.leg(outbound.legs().get(i)).from().equals(route.readyNode())){index=i;break;}if(index<=0)return false;
        var incoming=directory.leg(outbound.legs().get(index-1));var launch=directory.leg(outbound.legs().get(index));var levelAxis=directory.tangent(incoming,1);var launchAxis=directory.tangent(launch,0);var from=toTransfer?launchAxis:levelAxis;var to=toTransfer?levelAxis:launchAxis;var root=directory.sample(launch,0,binding).evaRoot();if(!pose(NervOriginalCarrierR52.actualRoot(carrier,1),root)||!pose(EvaMechanicalFrameR52.frame(e,1),root))return hold(o,"bank_head_actual_original_root_changed");
        var context=NervRouteRuntimeR52.flightContext(l);var lease=context==null?null:context.pool().groundTaskR52(o);if(lease==null||!lease.task().equals(task)||!context.pool().resourcesHeldR52(task,directory.resources(route)))return hold(o,"bank_head_real_space_and_rail_lease_missing");
        try
        {
            var head=carrier.originalCarrierStateR52().getCompound(NervBankHeadTransferR53.KEY);boolean same=head.hasUUID("Task")&&head.getUUID("Task").equals(task)&&head.getString("Directory").equals(directory.fingerprint())&&head.getString("Route").equals(route.id())&&NervBankHeadTransferR53.pose(head,0).direction().equals(from)&&NervBankHeadTransferR53.pose(head,NervBankHeadTransferR53.TICKS).direction().equals(to);
            if(route.recovery()&&data.hasUUID("HeadReturnFromTaskR53")&&!NervBankHeadTransferR53.unfinished(head)&&NervOriginalCarrierR52.headSlideR53(carrier,1)==0&&NervOriginalCarrierR52.uprightDirectionR52(carrier,1).distanceTo(to)<1e-7)
            {var pads=NervLegacyCarrierRideR52.finitePadBearingsR52(root,NervOriginalCarrierR52.actualRidePoseR52(carrier));if(pads.size()==4&&pads.stream().allMatch(NervLegacyCarrierRideR52.PadBearing::bears))return true;}
            boolean cancelledReturn=route.recovery()&&data.hasUUID("HeadReturnFromTaskR53")&&head.hasUUID("Task")&&data.getUUID("HeadReturnFromTaskR53").equals(head.getUUID("Task"))&&data.getString("HeadReturnFromRouteR53").equals(head.getString("Route"))&&head.getString("Directory").equals(directory.fingerprint());
            if(cancelledReturn&&(NervBankHeadTransferR53.unfinished(head)||head.getBoolean("AbortedToStart")))
            {
                int resumeStep=NervBankHeadTransferR53.pose(head,0).direction().equals(to)?-1:NervBankHeadTransferR53.pose(head,NervBankHeadTransferR53.TICKS).direction().equals(to)?1:0;if(resumeStep==0)return hold(o,"bank_head_cancelled_return_axis_differs");
                if(resumeStep<0?head.getInt("Clock")>0:head.getInt("Clock")<NervBankHeadTransferR53.TICKS)
                {
                    var own=new HashSet<>(TransportMembershipR52.members(o,kind(data)));own.add(carrier.getUUID());var proof=NervOriginalCarrierR52.proposeBankHeadStepR53(l,carrier,head,Set.copyOf(own),resumeStep);
                    if(proof==null||!proof.current(l)||!bankHeadSpaceCoveredR53(context,route,proof)||!proof.commit(l))return hold(o,"bank_head_cancelled_reverse_sweep_held");
                    return hold(o,"bank_head_cancelled_preparation_reversing_original_clock");
                }
                var pads=NervLegacyCarrierRideR52.finitePadBearingsR52(root,NervOriginalCarrierR52.actualRidePoseR52(carrier));return NervOriginalCarrierR52.headSlideR53(carrier,1)==0&&NervOriginalCarrierR52.uprightDirectionR52(carrier,1).distanceTo(to)<1e-7&&pads.size()==4&&pads.stream().allMatch(NervLegacyCarrierRideR52.PadBearing::bears);
            }
            if(!same){if(NervBankHeadTransferR53.unfinished(head))return hold(o,"bank_head_prior_original_task_not_finished");if(NervOriginalCarrierR52.uprightDirectionR52(carrier,1).distanceTo(from)>1e-7||NervOriginalCarrierR52.headSlideR53(carrier,1)!=0)return hold(o,"bank_head_actual_incoming_axis_changed");head=NervBankHeadTransferR53.begin(task,directory.fingerprint(),route.id(),from,to);}
            if(!NervBankHeadTransferR53.pose(head,0).direction().equals(from)||!NervBankHeadTransferR53.pose(head,NervBankHeadTransferR53.TICKS).direction().equals(to))return hold(o,"bank_head_saved_route_axes_changed");
            if(head.getInt("Clock")<NervBankHeadTransferR53.TICKS)
            {
                var own=new HashSet<>(TransportMembershipR52.members(o,kind(data)));own.add(carrier.getUUID());var proof=NervOriginalCarrierR52.proposeBankHeadStepR53(l,carrier,head,Set.copyOf(own));if(proof==null||!proof.current(l))return hold(o,"bank_head_full_mesh_sweep_or_original_four_pad_support_held");
                if(!bankHeadSpaceCoveredR53(context,route,proof))return hold(o,"bank_head_actual_sweep_exceeds_original_lease");
                if(!proof.commit(l))return hold(o,"bank_head_same_tick_actual_commit_failed");head=carrier.originalCarrierStateR52().getCompound(NervBankHeadTransferR53.KEY);if(head.getInt("Clock")<NervBankHeadTransferR53.TICKS)return hold(o,"bank_head_local_retract_turn_extend_in_progress");
            }
            if(!NervBankHeadTransferR53.pose(head,NervBankHeadTransferR53.TICKS).direction().equals(to)||NervOriginalCarrierR52.uprightDirectionR52(carrier,1).distanceTo(to)>1e-7||NervOriginalCarrierR52.headSlideR53(carrier,1)!=0||!NervBankHeadTransferR53.internalBearings())return hold(o,"bank_head_real_lock_readback_failed");
            var pads=NervLegacyCarrierRideR52.finitePadBearingsR52(root,NervOriginalCarrierR52.actualRidePoseR52(carrier));if(pads.size()!=4||pads.stream().anyMatch(p->!p.bears()))return hold(o,"bank_head_original_four_pads_lost_support");
            if(!toTransfer&&!NervUprightGuidewayR52.finiteCaptureAtR52(new DirectoryTrajectoryR52(directory,launch,binding,0,1),0))return hold(o,"bank_head_ten_actual_capture_faces_not_locked");
            return true;
        }
        catch(java.io.IOException missing){return hold(o,"bank_head_selected_original_mesh_unavailable");}
    }
    private boolean bankHeadSpaceCoveredR53(NervRouteRuntimeR52.FlightContext context,Route route,NervOriginalCarrierR52.CheckedStep proof)
    {var spaces=new ArrayList<AABB>();for(String id:directory.resources(route))if(directory.resource(id).kind()==ResourceKind.SPACE){var bound=context.bindings().get(id);if(bound==null)return false;spaces.addAll(bound.spaces());}return proof.envelopes().stream().allMatch(box->NervAirspaceCoverageR52.covered(box,spaces));}
    @Override public boolean rebindStoppedContinuousR52(ServerLevel l,Original o,CompoundTag data)
    {var e=hull(l,o);if(!commissioned||e==null||!originalGraph(l,o,kind(data)==Kind.OCCUPIED)||!EvaMechanicalFrameR52.active(e)||data.getCompound("ContinuousClockR52").getDouble("SpeedMps")!=0||e.getDeltaMovement().lengthSqr()>1e-12)return false;captureAssembly(l,o,data);continuousGeometryR52.remove(o.eva());return captured.get(o.eva())!=null;}
    private boolean continuousCarrierCoveredR52(ServerLevel l,Route route,NervOriginalCarrierR52.CheckedContinuousStepR52 checked)
    {var context=NervRouteRuntimeR52.flightContext(l);if(context==null)return false;var spaces=new ArrayList<AABB>();for(String id:directory.resources(route))if(directory.resource(id).kind()==ResourceKind.SPACE){var b=context.bindings().get(id);if(b==null)return false;spaces.addAll(b.spaces());}return checked.envelopes().stream().allMatch(box->NervAirspaceCoverageR52.covered(box,spaces));}
    @Override public boolean preflightContinuousCarrierR52(ServerLevel l,Original o,Route route,List<DirectoryTrajectoryR52> paths,CompoundTag data)
    {if(NervR50CarrierModeR53.enabled())return !paths.isEmpty();var e=hull(l,o);var carrier=e==null?null:EvaMechanicalFrameR52.originalCarrierControllerR52(e);if(carrier==null||paths.isEmpty())return false;var members=new HashSet<>(TransportMembershipR52.members(o,kind(data)));members.add(carrier.getUUID());try{var checked=NervOriginalCarrierR52.proposeContinuousR52(l,carrier,paths,new Vec3(0,1,0),Set.copyOf(members));return checked!=null&&checked.current(l)&&continuousCarrierCoveredR52(l,route,checked);}catch(java.io.IOException unavailable){return false;}}
    @Override public Sweep sweptContinuousAssemblyR52(ServerLevel l,Original o,List<DirectoryTrajectoryR52> paths,CompoundTag data)
    {if(originalBinding(l,o,data)==null||paths.isEmpty()||captured.get(o.eva())==null)return null;var rotation=NervAircraftFrameR52.decodeRigid(data.getCompound("ContinuousRotationR52"));for(var path:paths)if(!path.pureTranslation()||path.leg().motion()==Motion.FOOT_BEARING_TURN||path.sample(0).evaRoot().rotationErrorDegrees(rotation)>.0001||path.sample(1).evaRoot().rotationErrorDegrees(rotation)>.0001)return null;return new Sweep(captured.get(o.eva()).sweep(paths,.005));}
    @Override public boolean applyCheckedContinuousR52(ServerLevel l,CheckedContinuousTraversalR52 proof,CompoundTag data)
    {
        if(proof==null||!proof.current(l)||!proof.route().continuousUpright()||!originalGraph(l,proof.original(),proof.kind()==Kind.OCCUPIED))return false;var o=proof.original();var e=hull(l,o);var carrier=EvaMechanicalFrameR52.originalCarrierControllerR52(e);if(carrier==null)return hold(o,"continuous_actual_original_carrier_missing");
        var members=new HashSet<>(TransportMembershipR52.members(o,proof.kind()));members.add(carrier.getUUID());try{var checked=NervOriginalCarrierR52.proposeContinuousR52(l,carrier,proof.paths(),new Vec3(0,1,0),Set.copyOf(members));if(checked==null||!checked.current(l)||!continuousCarrierCoveredR52(l,proof.route(),checked))return hold(o,"continuous_full_carrier_curve_bearing_or_lease_rejected");
            if(!EvaMechanicalFrameR52.applyVerifiedContinuousR52(e,o,proof.from(),proof.to(),proof.paths(),data.getCompound("ContinuousClockR52")))return false;if(!checked.commit(l))throw new IllegalStateException("Prevalidated continuous carrier final commit rejected after sole assembly commit");if(!proof.recordCommittedR52(l,data))throw new IllegalStateException("Committed continuous assembly final readback failed");return true;
        }catch(java.io.IOException missing){return hold(o,"continuous_selected_carrier_source_missing");}
    }
    @Override public boolean prepareLeg(ServerLevel l,Original o,Route route,Leg leg,CompoundTag data)
    {
        if(!originalGraph(l,o,kind(data)==Kind.OCCUPIED))return hold(o,"moving_custody_changed");data.putString("RouteR52",route.id());if((!EvaMechanicalFrameR52.active(hull(l,o))||data.getBoolean("ReceiverAlignmentR53"))&&!captureReceiver(l,o,route,leg,data))return false;var actualEva=hull(l,o);var actualBinding=EvaMechanicalFrameR52.measuredBinding(actualEva,o);int legIndex=route.legs().indexOf(leg.id());double fraction=data.getString("LegClockRouteR52").equals(route.id())&&data.getInt("LegClockIndexR52")==legIndex?NervMechanicalTravelR52.fraction(data.getInt("LegClockR52"),leg.ticks()):0;var requiredStart=directory.sample(leg,fraction,actualBinding).evaRoot();var actualStart=EvaMechanicalFrameR52.frame(actualEva,1);if(!pose(actualStart,requiredStart))return hold(o,"actual_original_source_frame_mismatch_"+leg.id()+"_fraction="+fraction+"_position_m="+actualStart.translation().distanceTo(requiredStart.translation())+"_rotation_deg="+actualStart.rotationErrorDegrees(requiredStart)+"_measured_sole_axis="+actualBinding.rightFoot().subtract(actualBinding.leftFoot())+"_source_root="+actualStart+"_directory_root="+requiredStart);for(String id:leg.rails()){var context=NervRouteRuntimeR52.flightContext(l);var nativeBinding=context==null?null:context.bindings().get(id);if(nativeBinding!=null&&nativeBinding.mechanicalRail()!=null){if(!context.nativeAccess().resourceReady(id,false))return hold(o,"actual_mechanical_rail_source_or_foundation_"+id+"_"+NervMechanicalRailBindingR52.diagnostic(l,directory,nativeBinding.mechanicalRail(),nativeBinding.cells()));}else if(!resources.containsKey(id)||!fixed(l,resources.get(id)))return hold(o,"actual_rail_readback_"+id);}
        for(String id:leg.doors())if(!gate(l,gates.get(id),true,TransportMembershipR52.members(o,kind(data))))return hold(o,"actual_gate_not_open_"+id);
        if(!resources.containsKey(leg.support())||!fixed(l,resources.get(leg.support())))return hold(o,"actual_support_missing_"+leg.support());try{if(!prepareTurnR52(l,o,route,leg,data))return false;}catch(java.io.IOException unavailable){return hold(o,"actual_turn_station_source_unavailable");}return true;
    }
    private boolean commissionDoor(ServerLevel l,Gate g)
    {
        if(NervR50CarrierModeR53.retiredPit(g.resource()))return true;
        if(NervR50CarrierModeR53.enabled()&&l.getEntity(g.visual()) instanceof NervHangarDoorEntity existing&&!existing.matchesDeclaredR52(g.hangarStack()))existing.applyDeclaredR52(g.variant(),g.hangarStack(),existing.actualOpenProgressR52()>=.5F);if(l.getEntity(g.visual())!=null)return declaredDoor(l,g);if(!fixed(l,g.supports())||!loaded(l,BlockPos.containing(g.frame().translation()))||g.collisionSteps().stream().anyMatch(c->!matches(l,c,false)))return false;
        Entity e=g.kind()==GateKind.HANGAR?ModEntities.NERV_HANGAR_DOOR.get().create(l):ModEntities.NERV_SILO_DOOR.get().create(l);if(e==null)return false;e.setUUID(g.visual());e.setPos(g.frame().translation());
        e.setYRot(yaw(g.frame()));if(e instanceof NervHangarDoorEntity door)door.applyDeclaredR52(g.variant(),g.hangarStack(),false);else ((NervSiloDoorEntity)e).configureDeclaredR52(g.variant(),g.stage(),g.frame(),false,g.siloHatch());return l.addFreshEntity(e);
    }
    private boolean declaredDoor(ServerLevel l,Gate g)
    {var actor=l.getEntity(g.visual());return actor!=null&&actor.position().distanceToSqr(g.frame().translation())<1e-8&&g.variant()>=0&&g.variant()<3&&(g.kind()==GateKind.HANGAR?actor instanceof NervHangarDoorEntity d&&d.getVariant()==g.variant()&&d.matchesDeclaredR52(g.hangarStack())&&pose(d.actualFrameR52(),g.frame()):actor instanceof NervSiloDoorEntity silo&&silo.getVariant()==g.variant()&&silo.getBulkheadStage()==g.stage()&&silo.matchesDeclaredR52(g.siloHatch())&&pose(silo.actualFrameR52(),g.frame()));}
    private static boolean wetSealMotionPermitR52(boolean alreadyAtTarget,boolean actualDry,boolean actualPitOpen)
    {return alreadyAtTarget||actualDry&&actualPitOpen;}
    private static boolean wetPeerProxyPermitR52(boolean paired,boolean liveIdentityFrameSpec,boolean actualClosed,int actualCellCount,boolean actualClosedStates,boolean actualSupports)
    {return paired&&liveIdentityFrameSpec&&actualClosed&&actualCellCount>0&&actualCellCount<=512&&actualClosedStates&&actualSupports;}
    private static String nextAfterServiceBridgeCloseR52(boolean sealedFront)
    {return Finish.FRONT_SEAL_CLOSE.name();}
    private static boolean wetFrontReturnClosePermitR52(boolean actualDry,float carrierRise,boolean actualClamps,boolean serviceBridgeClosed,boolean actualPitOpen)
    {return actualDry&&carrierRise==0&&actualClamps&&serviceBridgeClosed&&actualPitOpen;}
    private static boolean wetPitClosePermitR52(boolean hasSeal,boolean actualSealClosed)
    {return !hasSeal||actualSealClosed;}
    private Set<BlockPos> pitPeerProxyCellsR52(ServerLevel l,Gate pit,boolean open)
    {
        if(pit.kind()!=GateKind.SILO||!Objects.equals(servicePits.get(pit.variant()),pit.resource()))return Set.of();
        var front=gates.get("bay_"+pit.variant()+"_front");if(!hasWetFloorSealR52(front))return continuousGuidesR52?null:Set.of();
        var cells=wetFloorSealsR52.get(front.resource());boolean paired=pit.siloHatch().serviceColumnPorts()&&front.variant()==pit.variant()&&!front.visual().equals(pit.visual());boolean live=declaredDoor(l,front);var actor=l.getEntity(front.visual());
        var supports=new HashSet<BlockPos>();for(var c:front.supports())supports.add(c.at());boolean bear=live&&fixed(l,front.supports())&&actor instanceof NervHangarDoorEntity door&&door.declaredSupportsBearR52(l,supports);
        // A no-motion already-open PIT may be queried after front opening.
        // It needs no proxy substitution; changed or partial peers still HOLD.
        if(open&&gateAtRest(l,pit,true)&&paired&&live&&bear&&gateAtRest(l,front,true))return Set.of();
        if(!wetPeerProxyPermitR52(paired,live,gateAtRest(l,front,false),cells==null?0:cells.size(),cells!=null&&matches(l,cells,false),bear))return null;
        var result=new HashSet<BlockPos>();for(var c:cells)result.add(c.at());return Set.copyOf(result);
    }
    private boolean gate(ServerLevel l,Gate g,boolean open,Set<UUID> own)
    {
        if(g!=null&&NervR50CarrierModeR53.retiredPit(g.resource()))return true;
        if(g==null||!fixed(l,g.supports())||!declaredDoor(l,g))return false;float proposed;
        if(hasWetFloorSealR52(g)){boolean rest=gateAtRest(l,g,open);var p=units.get(g.variant());if(!wetSealMotionPermitR52(rest,wetSealBayDryR52(l,g),p!=null&&gateAtRest(l,servicePit(p),true)))return false;if(rest)return true;}
        var peerProxyCells=pitPeerProxyCellsR52(l,g,open);if(peerProxyCells==null)return false;
        if(g.kind()==GateKind.SILO&&Objects.equals(servicePits.get(g.variant()),g.resource())&&!open){var front=gates.get("bay_"+g.variant()+"_front");if(!wetPitClosePermitR52(hasWetFloorSealR52(front),wetFloorSealClosedR52(l,front)))return false;}
        if(g.kind()==GateKind.SILO&&Objects.equals(servicePits.get(g.variant()),g.resource())&&gateAtRest(l,g,open))return true;
        // No actuator or proxy write is required at the requested endpoint.
        // Native identity, support and every collision cell are still read back.
        if(gateAtRest(l,g,open))return true;
        if(open)for(var p:units.values())if(g.resource().equals(servicePits.get(p.variant()))){var gantry=gantry(l,p);if(!dryBay(l,p)||gantry==null||gantry.getLclVisualLevel(1)!=0||!gantry.lowerFrameDeclaredR52()||gantry.lowerFrameProgressR52(1)!=1)return false;}
        if(gateTicks.getOrDefault(g.resource(),Long.MIN_VALUE)==l.getGameTime())return gateAtRest(l,g,open);
        if(l.getEntity(g.visual()) instanceof NervHangarDoorEntity door){door.applyDeclaredR52(g.variant(),g.hangarStack(),open);proposed=door.proposedDeclaredProgressR52(open);}
        else {var door=(NervSiloDoorEntity)l.getEntity(g.visual());door.configureDeclaredR52(g.variant(),g.stage(),g.frame(),open,g.siloHatch());proposed=door.proposedDeclaredProgressR52(open);}
        int completed=proposed==1?g.collisionSteps().size():0;
        var closing=new ArrayList<Cell>();for(int i=completed;i<g.collisionSteps().size();i++)closing.addAll(g.collisionSteps().get(i));
        if(!NervR50CarrierModeR53.enabled()&&!closing.isEmpty())for(var plant:units.values())if(l.getEntity(plant.eva()) instanceof EvaUnit01Entity eva&&!NervMappedPlugMechanicsR52.clearCarrierClosure(l,eva,closing))return false;
        var moving=new HashSet<BlockPos>();for(var step:g.collisionSteps())for(var cell:step)moving.add(cell.at());var supports=new HashSet<BlockPos>();for(var cell:g.supports())supports.add(cell.at());
        float actual=l.getEntity(g.visual()) instanceof NervHangarDoorEntity d?d.actualOpenProgressR52():((NervSiloDoorEntity)l.getEntity(g.visual())).actualOpenProgressR52();
        // Chunk blocks and the actuator entity can persist at different steps
        // after an interrupted save. Reconcile only the two authored proxy
        // states, with the same live occupancy and complete mesh checks below.
        // The door's own broad box is not an occupant of its collision proxy.
        var proxyOwner=new HashSet<UUID>();proxyOwner.add(g.visual());
        if(NervR50CarrierModeR53.enabled())
        {
            proxyOwner.addAll(own);
            for(var p:units.values())if(own.contains(p.eva())&&l.getEntity(p.eva()) instanceof EvaUnit01Entity e)
            {var carrier=EvaMechanicalFrameR52.originalCarrierControllerR52(e);if(carrier!=null)proxyOwner.add(carrier.getUUID());}
        }
        for(int i=0;i<g.collisionSteps().size();i++)if(!canChange(l,g.collisionSteps().get(i),i<completed,proxyOwner))return false;
        if(!NervR50CarrierModeR53.enabled())
        {if(l.getEntity(g.visual()) instanceof NervHangarDoorEntity d){if(!d.clearDeclaredSweepR52(l,actual,proposed,own,moving,supports))return false;}else if(!((NervSiloDoorEntity)l.getEntity(g.visual())).clearDeclaredSweepR52(l,actual,proposed,own,moving,supports,peerProxyCells))return false;}
        for(int i=0;i<g.collisionSteps().size();i++)if(!canChange(l,g.collisionSteps().get(i),i<completed,proxyOwner))return false;
        for(int i=0;i<g.collisionSteps().size();i++)if(!change(l,g.collisionSteps().get(i),i<completed,proxyOwner))return false;
        if(l.getEntity(g.visual()) instanceof NervHangarDoorEntity door)door.advanceDeclaredR52(open);else ((NervSiloDoorEntity)l.getEntity(g.visual())).advanceDeclaredR52(open);
        gateTicks.put(g.resource(),l.getGameTime());return gateAtRest(l,g,open);
    }
    private boolean gateAtRest(ServerLevel l,Gate g,boolean open)
    {if(g!=null&&NervR50CarrierModeR53.retiredPit(g.resource()))return true;if(g==null||!declaredDoor(l,g)||!fixed(l,g.supports()))return false;float actual=l.getEntity(g.visual()) instanceof NervHangarDoorEntity door?door.actualOpenProgressR52():((NervSiloDoorEntity)l.getEntity(g.visual())).actualOpenProgressR52();return (open?actual==1:actual==0)&&g.collisionSteps().stream().allMatch(c->matches(l,c,open));}
    @Override public NervFlightGatePlanR52 previewFlightGates(ServerLevel l,Original o,Kind k,Set<String> ids)
    {return commissioned&&plant(o)!=null&&originalGraph(l,o,k==Kind.OCCUPIED)?NervFlightGatePlanR52.inspect(l,gates,ids,TransportMembershipR52.members(o,k)):null;}
    @Override public boolean flightGateSampleCurrent(ServerLevel l,String id)
    {return commissioned&&NervFlightGatePlanR52.sampleCurrent(l,directory,gates.get(id));}
    private boolean prepareRunningShoesR52(ServerLevel l,Original o,Leg leg,CompoundTag data,NervCarrierPlatformEntity carrier,Set<UUID> own)throws java.io.IOException {return prepareRunningShoesR52(l,o,leg,data,carrier,own,leg.motion()==Motion.FOOT_BEARING_TURN);}
    private boolean prepareRunningShoesR52(ServerLevel l,Original o,Leg leg,CompoundTag data,NervCarrierPlatformEntity carrier,Set<UUID> own,boolean forceStow)throws java.io.IOException {if(NervOriginalCarrierR52.progress(carrier,1)!=1)return false;var current=NervOriginalCarrierR52.actualRidePoseR52(carrier);var target=NervLegacyCarrierRideR52.targetFromActualHeadsR52(NervOriginalCarrierR52.actualRoot(carrier,1));boolean onHeads=target!=null&&!forceStow;if(target==null||forceStow)target=NervLegacyCarrierRideR52.rest();if(current.equals(target))return !onHeads||NervLegacyCarrierRideR52.finitePadBearingsR52(NervOriginalCarrierR52.actualRoot(carrier,1),current).stream().allMatch(p->p.bears());if(carrier.originalCarrierStateR52().getLong("At")==l.getGameTime())return false;var joints=new ArrayList<NervLegacyCarrierRideR52.Joint>();for(int i=0;i<4;i++){var a=current.joints().get(i);var b=target.joints().get(i);double drop=a.drop()+Math.max(-.01,Math.min(.01,b.drop()-a.drop())),pitch=a.pitch()+Math.max(-.005,Math.min(.005,b.pitch()-a.pitch()));if(Math.abs(drop-b.drop())<1e-10)drop=b.drop();if(Math.abs(pitch-b.pitch())<1e-10)pitch=b.pitch();joints.add(new NervLegacyCarrierRideR52.Joint(drop,pitch));}var proposal=NervLegacyCarrierRideR52.proposeActuatorR52(l,carrier,current,new NervLegacyCarrierRideR52.RidePose(joints),own);var admission=turnAdmissionR52(l,o,data,leg,carrier.getUUID());if(proposal!=null&&proposal.current(l)&&NervTurnStationRuntimeR52.covered(admission,proposal.envelopes()))NervOriginalCarrierR52.acceptRideStepR52(l,proposal);return false;}
    private NervTurnStationRuntimeR52.Admission turnAdmissionR52(ServerLevel l,Original o,CompoundTag data,Leg leg,UUID controller){var c=NervRouteRuntimeR52.flightContext(l);if(c==null)return null;UUID task;Set<String> ids;var hardware=data.getCompound("EmptyCarrierTransferR52");if(hardware.hasUUID("Task")&&!hardware.getString("Stage").equals("READY")){task=hardware.getUUID("Task");var lease=c.pool().queryHardware(task);if(lease==null||!lease.controller().equals(controller)||lease.variant()!=o.variant()||lease.epoch()!=epoch||!lease.directoryFingerprint().equals(directory.fingerprint()))return null;ids=lease.resources();}else{var lease=c.pool().groundTaskR52(o);if(lease==null||!lease.directoryFingerprint().equals(directory.fingerprint()))return null;task=lease.task();var route=directory.route(lease.route());if(route==null)return null;ids=directory.resources(route);}if(!ids.containsAll(leg.resources())||!c.pool().resourcesHeldR52(task,ids))return null;return new NervTurnStationRuntimeR52.Admission(task,ids,c.bindings(),c.pool());}
    private Set<UUID> turnOwnR52(Original o,Kind k,UUID controller,NervFootGuideDockR52.Spec spec){var ids=new HashSet<>(TransportMembershipR52.members(o,k));ids.add(controller);ids.add(NervFootGuideStationR52.proposedIdentityR52(epoch,spec.leg().id()));return Set.copyOf(ids);}
    private boolean prepareTurnR52(ServerLevel l,Original o,Route route,Leg leg,CompoundTag data)throws java.io.IOException {var e=hull(l,o);var carrier=e==null?null:EvaMechanicalFrameR52.originalCarrierControllerR52(e);if(carrier==null)return false;var binding=EvaMechanicalFrameR52.measuredBinding(e,o);var rideOwn=new HashSet<>(TransportMembershipR52.members(o,kind(data)));rideOwn.add(carrier.getUUID());if(!prepareRunningShoesR52(l,o,leg,data,carrier,Set.copyOf(rideOwn)))return hold(o,"actual_running_shoe_extension_or_supported_stow_in_progress");int index=route.legs().indexOf(leg.id());if(index>0){var previous=directory.leg(route.legs().get(index-1));if(previous.motion()==Motion.FOOT_BEARING_TURN){var spec=turnSpecR52(previous,binding);var admission=turnAdmissionR52(l,o,data,previous,carrier.getUUID());if(spec==null||!NervTurnStationRuntimeR52.afterTurn(l,carrier,spec,admission,turnOwnR52(o,kind(data),carrier.getUUID(),spec),data))return hold(o,"actual_outgoing_station_bridge_or_axle_release_in_progress");if(carrier.originalCarrierStateR52().getLong("At")==l.getGameTime())return hold(o,"actual_station_release_clock_before_departure");}}
        for(int done=0;done<index;done++){var turn=directory.leg(route.legs().get(done));if(turn.motion()!=Motion.FOOT_BEARING_TURN)continue;var spec=turnSpecR52(turn,binding);var admission=turnAdmissionR52(l,o,data,turn,carrier.getUUID());if(spec!=null&&admission!=null&&NervFootGuideStationR52.controller(l,spec)!=null){var station=NervFootGuideStationR52.controller(l,spec);var pose=NervFootGuideStationR52.currentPose(station);if(pose.coupling()==0&&(pose.incoming()==1||pose.outgoing()==1))NervTurnStationRuntimeR52.idle(l,spec,admission);}}
        if(index+1<route.legs().size()){var next=directory.leg(route.legs().get(index+1));if(next.motion()==Motion.FOOT_BEARING_TURN){var spec=turnSpecR52(next,binding);var admission=turnAdmissionR52(l,o,data,next,carrier.getUUID());if(spec==null||admission==null||!NervTurnStationRuntimeR52.prepare(l,spec,admission))return hold(o,"actual_station_incoming_bridge_preparation_in_progress");}}
        if(leg.motion()==Motion.FOOT_BEARING_TURN){var spec=turnSpecR52(leg,binding);var admission=turnAdmissionR52(l,o,data,leg,carrier.getUUID());return spec!=null&&admission!=null&&NervTurnStationRuntimeR52.beforeTurn(l,carrier,spec,admission,turnOwnR52(o,kind(data),carrier.getUUID(),spec),data);}return true;
    }
    @Override public boolean prepareEmptyCarrierTurnR52(ServerLevel l,Original o,UUID id,Leg leg,CompoundTag data){try{var carrier=NervOriginalCarrierR52.controller(l,o);if(carrier==null||!carrier.getUUID().equals(id))return false;var spec=turnSpecR52(leg,NervOriginalCarrierR52.nominalBinding(o.variant()));var a=turnAdmissionR52(l,o,data,leg,id);return spec!=null&&a!=null&&(pose(NervOriginalCarrierR52.actualRoot(carrier,1),NervFootGuideDockR52.root(spec,new NervFootGuideDockR52.Sample(NervFootGuideDockR52.Stage.COUPLE,0)))?NervTurnStationRuntimeR52.beforeTurn(l,carrier,spec,a,Set.of(id,NervFootGuideStationR52.proposedIdentityR52(epoch,leg.id())),data):NervTurnStationRuntimeR52.prepare(l,spec,a));}catch(java.io.IOException unavailable){return false;}}
    @Override public boolean applyEmptyCarrierTurnR52(ServerLevel l,Original o,UUID id,DirectoryTrajectoryR52 curve,CompoundTag data){try{var carrier=NervOriginalCarrierR52.controller(l,o);if(carrier==null||!carrier.getUUID().equals(id))return false;var spec=turnSpecR52(curve.leg(),curve.binding());var a=turnAdmissionR52(l,o,data,curve.leg(),id);if(spec==null||a==null)return false;var proof=NervTurnStationRuntimeR52.checkTurn(l,carrier,spec,a,Set.of(id,NervFootGuideStationR52.proposedIdentityR52(epoch,curve.leg().id())),data,curve.fromFraction(),curve.toFraction());return NervTurnStationRuntimeR52.commitTurn(l,proof,data);}catch(java.io.IOException unavailable){return false;}}
    @Override public boolean finishEmptyCarrierTurnR52(ServerLevel l,Original o,UUID id,Leg leg,CompoundTag data){try{var carrier=NervOriginalCarrierR52.controller(l,o);if(carrier==null||!carrier.getUUID().equals(id))return false;var spec=turnSpecR52(leg,NervOriginalCarrierR52.nominalBinding(o.variant()));var a=turnAdmissionR52(l,o,data,leg,id);return spec!=null&&a!=null&&NervTurnStationRuntimeR52.afterTurn(l,carrier,spec,a,Set.of(id,NervFootGuideStationR52.proposedIdentityR52(epoch,leg.id())),data);}catch(java.io.IOException unavailable){return false;}}
    private boolean carrierSpaceCoveredR52(ServerLevel l,Leg leg,NervOriginalCarrierR52.CheckedStep proof){var context=NervRouteRuntimeR52.flightContext(l);if(context==null)return false;var spaces=new ArrayList<AABB>();for(String id:leg.resources())if(directory.resource(id).kind()==ResourceKind.SPACE){var binding=context.bindings().get(id);if(binding==null)return false;spaces.addAll(binding.spaces());}return proof.envelopes().stream().allMatch(box->NervAirspaceCoverageR52.covered(box,spaces));}
    private List<Leg> traversedEmptyTurnsR52(CompoundTag data){var transfer=data.getCompound("EmptyCarrierTransferR52");var ids=transfer.getList("Legs",net.minecraft.nbt.Tag.TAG_STRING);int index=transfer.getInt("Index");if(index<0||index>ids.size())throw new IllegalStateException("Actual empty route index required");var result=new ArrayList<Leg>();for(int i=0;i<index;i++){var leg=directory.leg(ids.getString(i));if(leg==null)throw new IllegalStateException("Actual Root empty route leg required");if(leg.motion()==Motion.FOOT_BEARING_TURN)result.add(leg);}return List.copyOf(result);}
    @Override public Set<String> pendingEmptyStationResourcesR52(ServerLevel l,Original o,CompoundTag data){if(NervR50CarrierModeR53.enabled())return Set.of();var pending=new HashSet<String>();for(var leg:traversedEmptyTurnsR52(data)){try{var spec=turnSpecR52(leg,NervOriginalCarrierR52.nominalBinding(o.variant()));if(spec==null||!NervTurnStationRuntimeR52.idleComplete(l,spec))pending.addAll(leg.resources());}catch(java.io.IOException unavailable){pending.addAll(leg.resources());}}return Set.copyOf(pending);}
    private boolean advanceEmptyStationIdleR52(ServerLevel l,Original o,UUID controller,CompoundTag data){if(!commissioned||plant(o)==null||NervOriginalCarrierR52.controller(l,o)==null||!NervOriginalCarrierR52.controller(l,o).getUUID().equals(controller))return false;if(NervR50CarrierModeR53.enabled())return true;try{for(var leg:traversedEmptyTurnsR52(data)){var spec=turnSpecR52(leg,NervOriginalCarrierR52.nominalBinding(o.variant()));if(spec==null)return false;if(NervTurnStationRuntimeR52.idleComplete(l,spec))continue;var admission=turnAdmissionR52(l,o,data,leg,controller);if(admission==null)return false;NervTurnStationRuntimeR52.idle(l,spec,admission);}return true;}catch(java.io.IOException unavailable){return false;}}
    @Override public boolean finishEmptyStationIdleR52(ServerLevel l,Original o,UUID controller,CompoundTag data){return advanceEmptyStationIdleR52(l,o,controller,data)&&pendingEmptyStationResourcesR52(l,o,data).isEmpty();}
    @Override public boolean prepareEmptyCarrierGatesR52(ServerLevel l,Original o,UUID controller,Set<String> ids,CompoundTag data){if(!commissioned||plant(o)==null||NervOriginalCarrierR52.controller(l,o)==null||!NervOriginalCarrierR52.controller(l,o).getUUID().equals(controller))return false;var context=NervRouteRuntimeR52.flightContext(l);var transfer=data.getCompound("EmptyCarrierTransferR52");if(context==null||!transfer.hasUUID("Task"))return false;var lease=context.pool().queryHardware(transfer.getUUID("Task"));if(lease==null||!lease.controller().equals(controller)||lease.epoch()!=epoch||!lease.directoryFingerprint().equals(directory.fingerprint())||!lease.resources().containsAll(ids))return false;for(String id:ids)if(!gate(l,gates.get(id),true,Set.of(controller)))return false;if(NervR50CarrierModeR53.enabled())return true;var routeLegs=transfer.getList("Legs",net.minecraft.nbt.Tag.TAG_STRING);int routeIndex=transfer.getInt("Index");if(NervOriginalCarrierR52.progress(NervOriginalCarrierR52.controller(l,o),1)==1&&routeIndex<routeLegs.size())try{var leg=directory.leg(routeLegs.getString(routeIndex));if(leg==null||!prepareRunningShoesR52(l,o,leg,data,NervOriginalCarrierR52.controller(l,o),Set.of(controller)))return false;}catch(java.io.IOException unavailable){return false;}return advanceEmptyStationIdleR52(l,o,controller,data);}
    private boolean finishRouteStationsR52(ServerLevel l,Original o,CompoundTag data)throws java.io.IOException {var route=directory.route(data.getString("RouteR52"));var e=hull(l,o);var carrier=e==null?null:EvaMechanicalFrameR52.originalCarrierControllerR52(e);if(route==null||carrier==null)return false;boolean complete=true;var binding=finishingBinding(data);for(String id:route.legs()){var leg=directory.leg(id);if(leg.motion()!=Motion.FOOT_BEARING_TURN)continue;var spec=turnSpecR52(leg,binding);if(spec==null)return false;if(NervTurnStationRuntimeR52.idleComplete(l,spec))continue;var admission=turnAdmissionR52(l,o,data,leg,carrier.getUUID());if(admission==null)return false;if(!NervTurnStationRuntimeR52.idle(l,spec,admission))complete=false;}return complete;}
    @Override public Set<String> flightReceiverGates(ServerLevel l,String port)
    {var receiver=receivers.get(port);return commissioned&&receiver!=null?Set.copyOf(receiver.gates()):Set.of();}
    public RigidTransform resolveFlightReceiverCargoRootR52(ServerLevel l,Original o,Kind k,String port,CompoundTag data)
    {if(!commissioned||!originalGraph(l,o,k==Kind.OCCUPIED)||!receivers.containsKey(port))return null;var p=directory.ports().get(port);if(p==null||!p.reverseRoutes().containsKey(o.variant()))return null;var route=directory.route(p.reverseRoutes().get(o.variant()));var observed=data.copy();observed.putString("AssemblyKindR52",k.name());var binding=originalBinding(l,o,observed);return route!=null&&route.recovery()&&route.variant()==o.variant()&&binding!=null?directory.sample(directory.leg(route.legs().get(0)),0,binding).evaRoot():null;}
    private void captureAssembly(ServerLevel l,Original o,CompoundTag data)
    {var e=hull(l,o);var binding=EvaMechanicalFrameR52.measuredBinding(e,o);var geometry=EvaMechanicalFrameR52.capturedGeometry(e);var current=EvaMechanicalFrameR52.frame(e,1);var carrier=EvaMechanicalFrameR52.originalCarrierControllerR52(e);if(carrier!=null)try{if(!NervOriginalCarrierR52.setAttachedR52(l,carrier,e,true))throw new IllegalStateException("Actual original carrier/sole bearing required");}catch(java.io.IOException missing){throw new IllegalStateException("Actual original carrier source unavailable",missing);}var sample=new FootSupportFrameR52.Sample(current,current.transformPoint(binding.leftFoot()),current.transformPoint(binding.rightFoot()),current.compose(binding.plugInEva()));captured.put(o.eva(),kind(data)==Kind.HULL_ONLY_RECOVERY?FullAssemblyGeometryR52.captureHullRecovery(l,o,geometry,binding):FullAssemblyGeometryR52.capture(l,o,geometry,binding,sample));}
    private NervHullPreviewR52 preview(ServerLevel l,Original o)
    {var e=hull(l,o);if(e==null)return null;var prior=previews.get(o.eva());if(prior!=null&&prior.matches(e,o))return prior;var next=NervHullPreviewR52.inspect(e,o);if(next!=null)previews.put(o.eva(),next);return next;}
    @Override public FootSupportFrameR52.Binding originalBinding(ServerLevel l,Original o,CompoundTag data)
    {var e=hull(l,o);if(e==null)return null;if(data.contains("FinishFeet")&&data.contains("Finish")&&!data.getString("Finish").equals(Finish.DONE.name())&&!EvaMechanicalFrameR52.active(e))return finishingBinding(data);if(!EvaMechanicalFrameR52.active(e)){if(kind(data)!=Kind.HULL_ONLY_RECOVERY){var proof=occupiedPreviews.get(o.eva());if(!EvaMechanicalFrameR52.occupiedPreviewCurrent(e,o,proof))proof=EvaMechanicalFrameR52.prepareOccupiedRecovery(e,o);if(proof==null)return null;occupiedPreviews.put(o.eva(),proof);return EvaMechanicalFrameR52.occupiedPreviewBinding(proof);}var observed=preview(l,o);return observed==null?null:observed.binding();}if(!data.getBoolean("ReceiverAlignmentR53")&&!captured.containsKey(o.eva())&&!EvaMechanicalFrameR52.ballisticCustodyR52(e)&&!EvaMechanicalFrameR52.flightCustody(e)&&!data.getString("Finish").equals(Finish.RELEASE.name()))captureAssembly(l,o,data);return EvaMechanicalFrameR52.measuredBinding(e,o);}
    @Override public Vec3 actualFootBearingCentre(ServerLevel l,Original o,CompoundTag data)
    {var b=originalBinding(l,o,data);var e=hull(l,o);if(b==null)return null;var frame=EvaMechanicalFrameR52.active(e)?EvaMechanicalFrameR52.frame(e,1):kind(data)==Kind.HULL_ONLY_RECOVERY?preview(l,o).frame():EvaMechanicalFrameR52.occupiedPreviewFrame(occupiedPreviews.get(o.eva()));return frame.transformPoint(b.contactCentre());}
    @Override public Region actualRecoveryRegion(ServerLevel l,Original o,CompoundTag data)
    {var feet=actualFootBearingCentre(l,o,data);if(feet==null)return null;Region found=null;for(var r:receivers.values())if(r.domain().contains(feet)){if(found!=null&&found!=r.region())return null;found=r.region();}return found;}
    private boolean captureReceiver(ServerLevel l,Original o,Route route,Leg leg,CompoundTag data)
    {
        if(NervR50CarrierModeR53.enabled())return captureR50ReceiverR53(l,o,route,leg,data);
        var receiver=receivers.get(route.port());var e=hull(l,o);if(!route.recovery()||receiver==null||!fixed(l,receiver.supports()))return hold(o,"actual_receiver_support_not_ready");
        var b=originalBinding(l,o,data);if(b==null)return hold(o,"actual_stopped_geometry_preview_missing");var start=directory.sample(leg,0,b);var observed=kind(data)==Kind.HULL_ONLY_RECOVERY?preview(l,o).frame():EvaMechanicalFrameR52.occupiedPreviewFrame(occupiedPreviews.get(o.eva()));
        if(observed==null||!pose(observed,start.evaRoot())||!pose(observed,start.evaRoot()))return hold(o,"original_hull_not_on_declared_receiver_frame");
        Set<UUID> own=TransportMembershipR52.members(o,kind(data));float next=Math.min(1,e.carrierRiseProgress(1)+1F/receiver.carrierTicks());if(!acceptCarrierActuatorR52(l,e,observed,e.carrierRiseProgress(1),next,own,o,data))return hold(o,"actual_receiver_carrier_sweep_blocked");if(next!=1)return false;
        boolean accepted;if(kind(data)==Kind.HULL_ONLY_RECOVERY){var proof=preview(l,o);if(proof==null)return false;e.setNervLogisticsLocked(true);accepted=EvaMechanicalFrameR52.captureHull(e,o,proof.capture());}else accepted=EvaMechanicalFrameR52.captureOccupiedRecovery(e,o,occupiedPreviews.get(o.eva()));if(!accepted)return hold(o,"actual_hull_receiver_capture_rejected");captureAssembly(l,o,data);return true;
    }
    private boolean captureR50ReceiverR53(ServerLevel level,Original original,Route route,Leg leg,CompoundTag data)
    {
        var receiver=receivers.get(route.port());var eva=hull(level,original);
        if(!route.recovery()||receiver==null||eva==null||!fixed(level,receiver.supports()))return hold(original,"receiver_foundation_unavailable");
        if(!EvaMechanicalFrameR52.active(eva))
        {
            var binding=originalBinding(level,original,data);if(binding==null)return hold(original,"stopped_original_recovery_pose_unavailable");
            var feet=actualFootBearingCentre(level,original,data);if(!receiver.domain().contains(feet))return hold(original,"outside_receiver_platform");
            boolean captured;
            if(kind(data)==Kind.HULL_ONLY_RECOVERY){var proof=preview(level,original);eva.setNervLogisticsLocked(true);captured=proof!=null&&EvaMechanicalFrameR52.captureHull(eva,original,proof.capture());}
            else captured=EvaMechanicalFrameR52.captureOccupiedRecovery(eva,original,occupiedPreviews.get(original.eva()));
            if(!captured)return hold(original,"same_original_recovery_capture_failed");
            data.putBoolean("ReceiverAlignmentR53",true);
            data.remove("ReceiverBodyR53");data.remove("ReceiverHandsR53");data.putInt("ReceiverPoseTicksR53",0);
        }
        var binding=EvaMechanicalFrameR52.measuredBinding(eva,original);var current=EvaMechanicalFrameR52.frame(eva,1);
        var target=directory.sample(leg,0,binding).evaRoot();double distance=current.translation().distanceTo(target.translation()),angle=current.rotationErrorDegrees(target);
        double step=Math.min(1,Math.min(distance>.25?.25/distance:1,angle>3?3/angle:1));
        var next=current.interpolate(target,step);
        var from=new FootSupportFrameR52.Sample(current,current.transformPoint(binding.leftFoot()),current.transformPoint(binding.rightFoot()),current.compose(binding.plugInEva()));
        var to=new FootSupportFrameR52.Sample(next,next.transformPoint(binding.leftFoot()),next.transformPoint(binding.rightFoot()),next.compose(binding.plugInEva()));
        if(!EvaMechanicalFrameR52.applyVerified(eva,original,from,to))return hold(original,"receiver_alignment_original_chain_changed");
        var rack=EvaMechanicalFrameR52.originalCarrierControllerR52(eva);if(rack==null)return hold(original,"original_receiver_rack_unavailable");
        boolean rackReady=NervOriginalCarrierR52.alignR50ReceiverR53(rack,target);
        float rise=Math.min(1,eva.carrierRiseProgress(1)+1F/receiver.carrierTicks());eva.setCarrierRiseProgress(rise);NervOriginalCarrierR52.restoreR50RiseR53(rack,rise);
        if(!pose(next,target)||!rackReady||rise!=1)return hold(original,"receiver_alignment_in_progress");
        if(kind(data)==Kind.OCCUPIED&&data.getInt("ReceiverPoseTicksR53")<40)
        {
            if(!data.contains("ReceiverBodyR53"))
            {
                data.put("ReceiverBodyR53",EvaShutdownR30.encode(EvaMechanicalFrameR52.frozenLocalPose(eva)));
                data.put("ReceiverHandsR53",EvaFrozenHandsR52.capture(eva,1));
            }
            int age=data.getInt("ReceiverPoseTicksR53")+1;float t=age/40F;t=t*t*(3-2*t);
            var start=EvaBodyPose.neutralForTransportR32(eva);EvaShutdownR30.decode(data.getCompound("ReceiverBodyR53"),start);
            var body=EvaBodyPose.blend(start,EvaBodyPose.neutralForTransportR32(eva),t);
            var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();
            var fromHands=EvaFrozenHandsR52.decode(eva.getUnitVariant(),provider.handContractFingerprint(eva.getUnitVariant()),provider.handJoints(eva.getUnitVariant()),data.getCompound("ReceiverHandsR53"));
            var goalHands=EvaAnatomicalHandsR45.ordinaryReleaseTargetR52(eva.getUnitVariant(),false);
            var joints=new java.util.LinkedHashMap<String,org.joml.Quaternionf>();
            for(String name:fromHands.rotations().keySet())joints.put(name,new org.joml.Quaternionf(fromHands.rotations().get(name)).slerp(goalHands.rotations().get(name),t));
            var hands=new EvaAnatomicalHandsR45.Pose(goalHands.left(),goalHands.right(),java.util.Map.copyOf(joints));
            if(!EvaMechanicalFrameR52.applyGroundedPoseR52(eva,original,body,hands,provider.evaluate(eva.getUnitVariant(),body,hands)))return hold(original,"receiver_posture_adjustment_waiting");
            data.putInt("ReceiverPoseTicksR53",age);if(age<40)return hold(original,"receiver_posture_adjustment_in_progress");
            eva.stowHandsForShutdownR30();
        }
        data.remove("ReceiverAlignmentR53");captureAssembly(level,original,data);return true;
    }
    @Override public Sweep sweptAssembly(ServerLevel l,Original o,FootSupportFrameR52.Sample from,FootSupportFrameR52.Sample to,CompoundTag data){return null;}
    @Override public Sweep sweptAssembly(ServerLevel l,Original o,DirectoryTrajectoryR52 t,CompoundTag data){if(originalBinding(l,o,data)==null)return null;return new Sweep(captured.get(o.eva()).sweep(t.directory(),t.leg(),t.fromFraction(),t.toFraction(),.005));}
    @Override public boolean actualFrameMatches(ServerLevel l,Original o,FootSupportFrameR52.Sample sample,CompoundTag data){var e=hull(l,o);return e!=null&&EvaMechanicalFrameR52.active(e)&&pose(EvaMechanicalFrameR52.frame(e,1),sample.evaRoot())&&(kind(data)==Kind.HULL_ONLY_RECOVERY||plug(l,o)!=null&&pose(plug(l,o).getCanonicalTransform(),sample.plugWorld()));}
    @Override public boolean applyVerifiedWholeAssembly(ServerLevel l,Original o,FootSupportFrameR52.Sample from,FootSupportFrameR52.Sample to,CompoundTag data){if(!actualFrameMatches(l,o,from,data))return false;var e=hull(l,o);var carrier=EvaMechanicalFrameR52.originalCarrierControllerR52(e);if(carrier==null)return !EvaMechanicalFrameR52.hasOriginalCarrierControllerR52(e)&&EvaMechanicalFrameR52.applyVerified(e,o,from,to);var route=directory.route(data.getString("RouteR52"));var binding=EvaMechanicalFrameR52.measuredBinding(e,o);DirectoryTrajectoryR52 curve=null;if(route!=null)for(int i=0;i<route.legs().size();i++){var leg=directory.leg(route.legs().get(i));int clock=data.getString("LegClockRouteR52").equals(route.id())&&data.getInt("LegClockIndexR52")==i?data.getInt("LegClockR52"):0;if(clock<0||clock>=leg.ticks())continue;double a=NervMechanicalTravelR52.fraction(clock,leg.ticks()),b=NervMechanicalTravelR52.fraction(clock+1,leg.ticks());if(pose(directory.sample(leg,a,binding).evaRoot(),from.evaRoot())&&pose(directory.sample(leg,b,binding).evaRoot(),to.evaRoot())){curve=new DirectoryTrajectoryR52(directory,leg,binding,a,b);break;}}if(curve==null)return hold(o,"actual_original_carrier_requires_same_declared_whole_assembly_curve");if(curve.leg().motion()==Motion.FOOT_BEARING_TURN)try{var spec=turnSpecR52(curve.leg(),binding);var a=turnAdmissionR52(l,o,data,curve.leg(),carrier.getUUID());if(spec==null||a==null)return false;var proof=NervTurnStationRuntimeR52.checkTurn(l,carrier,spec,a,turnOwnR52(o,kind(data),carrier.getUUID(),spec),data,curve.fromFraction(),curve.toFraction());if(proof==null||!proof.current(l)||!EvaMechanicalFrameR52.applyVerified(e,o,from,to))return false;return NervTurnStationRuntimeR52.commitTurn(l,proof,data);}catch(java.io.IOException unavailable){return false;}var members=new HashSet<>(TransportMembershipR52.members(o,kind(data)));members.add(carrier.getUUID());try{var proof=NervOriginalCarrierR52.propose(l,carrier,curve,1,1,Set.copyOf(members));if(proof==null)return hold(o,"actual_original_carrier_same_curve_sweep_or_guide_admission_held");if(!carrierSpaceCoveredR52(l,curve.leg(),proof))return hold(o,"actual_original_carrier_guide_envelope_outside_same_ground_space_lease");if(!EvaMechanicalFrameR52.applyVerified(e,o,from,to))return false;return proof.commit(l);}catch(java.io.IOException missing){return false;}}
    @Override public NervFlightProofR52.FlightPickupPreview previewFlight(ServerLevel l,Original o,Kind requested,CompoundTag data)
    {
        if(!commissioned||plant(o)==null||!originalGraph(l,o,requested==Kind.OCCUPIED))return null;
        return NervFlightProofR52.inspect(l,o,requested);
    }
    @Override public boolean prepareFlightGates(ServerLevel l,Original o,Kind requested,Set<String> gateIds,CompoundTag data)
    {
        if(!commissioned||plant(o)==null||!originalGraph(l,o,requested==Kind.OCCUPIED))return false;
        for(String id:gateIds)if(directory.resource(id)==null||directory.resource(id).kind()!=ResourceKind.DOOR||!gates.containsKey(id))return false;
        Set<UUID> own=TransportMembershipR52.members(o,requested);boolean ready=true;for(String id:gateIds)if(!gate(l,gates.get(id),true,own))ready=false;return ready;
    }
    @Override public boolean closeIdleAirshaftGateR53(ServerLevel l,String id)
    {
        if(!commissioned||!(id.startsWith("bank_")||Set.of("remote_airshaft_surface","remote_airshaft_south").contains(id)))return false;
        var g=gates.get(id);if(g==null||l.getEntity(g.visual())==null)return false;
        float progress=l.getEntity(g.visual()) instanceof NervHangarDoorEntity door?door.actualOpenProgressR52():((NervSiloDoorEntity)l.getEntity(g.visual())).actualOpenProgressR52();
        if(progress==0)return true;
        return gate(l,g,false,Set.of());
    }
    @Override public boolean adoptFlight(ServerLevel l,NervFlightProofR52.CheckedPickup proof,CompoundTag data)
    {
        if(proof==null||!commissioned||!proof.current(l)||data.hasUUID("FlightAircraftR52")&&!proof.aircraft().equals(data.getUUID("FlightAircraftR52")))return false;
        if(!captureObservedFlight(l,proof.original(),proof.kind(),proof.preview(),proof.aircraft(),data))return false;data.remove("FlightWaitingR52");return true;
    }
    @Override public boolean holdFlightPickup(ServerLevel l,NervFlightProofR52.CheckedPickupHold proof,CompoundTag data)
    {
        if(proof==null||!commissioned||!proof.current(l))return false;var context=NervRouteRuntimeR52.flightContext(l);var lease=context==null?null:context.pool().queryFlight(proof.task());
        if(lease==null||!lease.original().equals(proof.original())||lease.kind()!=proof.kind()||!proof.aircraft().equals(lease.aircraft())||lease.payloadTransferred())return false;
        if(!captureObservedFlight(l,proof.original(),proof.kind(),proof.preview(),proof.aircraft(),data))return false;data.putBoolean("FlightWaitingR52",true);data.putUUID("FlightTaskR52",proof.task());putFrame(data,"FlightWaitingRootR52",proof.preview().root());return true;
    }
    private boolean captureObservedFlight(ServerLevel l,Original o,Kind requested,NervFlightProofR52.FlightPickupPreview observed,UUID aircraft,CompoundTag data)
    {
        var e=hull(l,o);if(plant(o)==null||e==null||!originalGraph(l,o,requested==Kind.OCCUPIED)||!observed.current(l)||!observed.sourceFingerprint().equals(EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52().sourceFingerprint()))return hold(o,"actual_checked_flight_pickup_changed");
        boolean accepted;if(EvaMechanicalFrameR52.active(e))accepted=EvaMechanicalFrameR52.kind(e)==requested&&EvaMechanicalFrameR52.epoch(e)==epoch&&pose(EvaMechanicalFrameR52.frame(e,1),observed.root());
        else if(requested==Kind.HULL_ONLY_RECOVERY){if(observed.hullCapture()==null)return false;e.setNervLogisticsLocked(true);accepted=EvaMechanicalFrameR52.captureHull(e,o,observed.hullCapture());if(!accepted)e.setNervLogisticsLocked(false);}
        else accepted=EvaMechanicalFrameR52.captureOccupiedRecovery(e,o,observed.occupiedCapture());
        if(!accepted||!pose(EvaMechanicalFrameR52.frame(e,1),observed.root()))return hold(o,"real_flight_custody_capture_rejected");EvaMechanicalFrameR52.setFlightCustody(e,true,observed.carrierVisible());
        data.putString("AssemblyKindR52",requested.name());data.putUUID("FlightAircraftR52",aircraft);data.putLong("FlightEpochR52",epoch);data.putString("FlightDirectoryR52",directory.fingerprint());data.putString("FlightSourceR52",observed.sourceFingerprint());captured.remove(o.eva());return true;
    }
    @Override public boolean releaseWaitingPickup(ServerLevel l,NervFlightProofR52.CheckedPickupHold proof,CompoundTag data)
    {
        if(proof==null||!proof.current(l)||!data.getBoolean("FlightWaitingR52")||!data.hasUUID("FlightTaskR52")||!proof.task().equals(data.getUUID("FlightTaskR52"))||!flightCustody(proof.original(),proof.kind(),data)||!proof.aircraft().equals(data.getUUID("FlightAircraftR52")))return false;var e=hull(l,proof.original());
        if(e==null||!EvaMechanicalFrameR52.flightCustody(e)||!pose(EvaMechanicalFrameR52.frame(e,1),getFrame(data,"FlightWaitingRootR52"))||!proof.preview().sourceFingerprint().equals(data.getString("FlightSourceR52")))return false;
        // Occupied release requires the same full-body/hand stance admission
        // as a landed delivery. A timer or clearing the hold cannot grant it.
        if(proof.kind()==Kind.OCCUPIED)return hold(proof.original(),"waiting_occupied_source_to_real_stance_release_proof_required");
        if(!EvaMechanicalFrameR52.releaseUpright(e,proof.original()))return false;for(String key:List.of("FlightWaitingR52","FlightTaskR52","FlightWaitingRootR52","FlightAircraftR52","FlightEpochR52","FlightDirectoryR52","FlightSourceR52"))data.remove(key);return true;
    }
    private boolean flightCustody(Original o,Kind requested,CompoundTag data)
    {return data.hasUUID("FlightAircraftR52")&&data.getLong("FlightEpochR52")==epoch&&data.getString("FlightDirectoryR52").equals(directory.fingerprint())&&kind(data)==requested&&plant(o)!=null;}
    @Override public boolean acceptHullRecoveryStepR52(ServerLevel l,NervHullGroundRecoveryR52.AcceptedRecoveryStep proof,CompoundTag data){if(proof==null||!commissioned||!proof.current(l)||!flightCustody(proof.original(),Kind.HULL_ONLY_RECOVERY,data)||!proof.aircraft().equals(data.getUUID("FlightAircraftR52"))||!originalGraph(l,proof.original(),false)||!proof.sourceFingerprint().equals(data.getString("FlightSourceR52")))return false;var e=hull(l,proof.original());if(e==null||!EvaMechanicalFrameR52.acceptRecoveryStepR52(e,proof))return false;captured.remove(proof.original().eva());previews.remove(proof.original().eva());return proof.cargoCommitted(l);}
    @Override public boolean applyFlightStep(ServerLevel l,NervFlightProofR52.CheckedFlightStep proof,CompoundTag data)
    {
        if(proof==null||!proof.current(l)||!flightCustody(proof.original(),proof.kind(),data)||!proof.aircraft().equals(data.getUUID("FlightAircraftR52")))return false;var e=hull(l,proof.original());
        if(e==null||!EvaMechanicalFrameR52.flightCustody(e)||!EvaMechanicalFrameR52.capturedGeometry(e).sourceFingerprint().equals(proof.preview().sourceFingerprint())||!proof.preview().sourceFingerprint().equals(data.getString("FlightSourceR52"))||!actualFrameMatches(l,proof.original(),proof.fromSample(),data))return false;
        return EvaMechanicalFrameR52.applyVerified(e,proof.original(),proof.fromSample(),proof.toSample());
    }
    @Override public boolean receiverReady(ServerLevel l,String port,Original o,Kind requested,RigidTransform stopped,CompoundTag data)
    {
        var receiver=receivers.get(port);var e=hull(l,o);if(!commissioned||receiver==null||e==null||!flightCustody(o,requested,data)||!originalGraph(l,o,requested==Kind.OCCUPIED)||!EvaMechanicalFrameR52.active(e)||EvaMechanicalFrameR52.epoch(e)!=epoch||EvaMechanicalFrameR52.kind(e)!=requested||!pose(EvaMechanicalFrameR52.frame(e,1),stopped)||!pose(resolveFlightReceiverCargoRootR52(l,o,requested,port,data),stopped)||!fixed(l,receiver.supports()))return false;
        Set<UUID> own=TransportMembershipR52.members(o,requested);for(String id:receiver.gates())if(!gate(l,gates.get(id),true,own))return false;
        if(!pose(EvaMechanicalFrameR52.carrierFrameR52(e,1),receiver.stoppedFrame()))return hold(o,"actual_receiver_dolly_not_at_this_hardware_frame");var actualCarrier=EvaMechanicalFrameR52.originalCarrierControllerR52(e);if(actualCarrier!=null&&NervOriginalCarrierR52.progress(actualCarrier,1)==1){try{if(!NervOriginalCarrierR52.carrierFootBearingR52(l,actualCarrier,e,EvaMechanicalFrameR52.capturedGeometry(e),EvaMechanicalFrameR52.frame(e,1)))return hold(o,"actual_receiver_steel_shoes_not_bearing_current_frozen_body");}catch(java.io.IOException unavailable){return false;}e.setCarrierRiseProgress(1);EvaMechanicalFrameR52.setFlightCustody(e,true,true);return true;}if(e.carrierRiseProgress(1)==1)return carrierSupportReadyR53(l,e);if(receiverTicks.getOrDefault(o.eva(),Long.MIN_VALUE)==l.getGameTime())return false;receiverTicks.put(o.eva(),l.getGameTime());float next=Math.min(1,e.carrierRiseProgress(1)+1F/receiver.carrierTicks());
        if(!acceptCarrierActuatorR52(l,e,EvaMechanicalFrameR52.carrierFrameR52(e,1),e.carrierRiseProgress(1),next,own,o,data))return hold(o,"actual_air_receiver_carrier_motion_blocked");EvaMechanicalFrameR52.setFlightCustody(e,true,true);return next==1&&carrierSupportReadyR53(l,e);
    }
    @Override public boolean acceptAirReceiver(ServerLevel l,NervFlightProofR52.CheckedAirReceiver proof,CompoundTag data)
    {
        if(proof==null||!proof.current(l)||!flightCustody(proof.original(),proof.kind(),data)||!proof.step().aircraft().equals(data.getUUID("FlightAircraftR52")))return false;var o=proof.original();var e=hull(l,o);var receiver=receivers.get(proof.port());
        if(e==null||receiver==null||!EvaMechanicalFrameR52.active(e)||EvaMechanicalFrameR52.epoch(e)!=epoch||EvaMechanicalFrameR52.kind(e)!=proof.kind()||!EvaMechanicalFrameR52.capturedGeometry(e).sourceFingerprint().equals(proof.step().preview().sourceFingerprint())||!proof.step().preview().sourceFingerprint().equals(data.getString("FlightSourceR52"))||e.carrierRiseProgress(1)!=1||!pose(EvaMechanicalFrameR52.frame(e,1),proof.stoppedFrame())||!pose(resolveFlightReceiverCargoRootR52(l,o,proof.kind(),proof.port(),data),proof.stoppedFrame())||!fixed(l,receiver.supports())||receiver.gates().stream().anyMatch(id->!gateAtRest(l,gates.get(id),true))||!actualFrameMatches(l,o,proof.step().toSample(),data))return hold(o,"real_air_receiver_support_or_final_custody_changed");
        if(!EvaMechanicalFrameR52.reattachCarrierR52(e))return hold(o,"actual_frozen_body_to_receiver_dolly_bearing_absent");captureAssembly(l,o,data);data.putString("AirReceiverPortR52",proof.port());data.putString("AirReceiverDirectoryR52",directory.fingerprint());return true;
    }
    @Override public boolean acceptAirDelivery(ServerLevel l,NervFlightProofR52.CheckedAirDelivery proof,CompoundTag data)
    {
        if(proof==null||proof.kind()!=Kind.OCCUPIED||!proof.current(l)||!flightCustody(proof.original(),proof.kind(),data)||!proof.step().aircraft().equals(data.getUUID("FlightAircraftR52")))return false;var o=proof.original();var e=hull(l,o);
        if(e==null||!EvaMechanicalFrameR52.flightCustody(e)||!originalGraph(l,o,true)||!EvaMechanicalFrameR52.capturedGeometry(e).sourceFingerprint().equals(proof.step().preview().sourceFingerprint())||!proof.step().preview().sourceFingerprint().equals(data.getString("FlightSourceR52"))||!actualFrameMatches(l,o,proof.step().toSample(),data)||!EvaMechanicalFrameR52.releaseFlightUpright(e,o,proof.stoppedFrame()))return hold(o,"actual_air_delivery_support_or_custody_release_rejected");
        e.setNervLogisticsLocked(false);e.setNoGravity(false);e.clearSortieDestination();captured.remove(o.eva());data.putString("AirDeliveryDestinationR52",proof.destination());data.putString("AirDeliveryDirectoryR52",directory.fingerprint());for(String field:List.of("FlightAircraftR52","FlightEpochR52","FlightDirectoryR52","FlightSourceR52"))data.remove(field);return true;
    }
    @Override public boolean approachReachable(ServerLevel l,Original o,Port port,Route reverse,CompoundTag data){var receiver=receivers.get(port.id());var b=originalBinding(l,o,data);if(receiver==null||receiver.region()!=port.region()||b==null||!fixed(l,receiver.supports()))return hold(o,"explicit_actual_receiver_not_ready");var leg=directory.leg(reverse.legs().get(0));RigidTransform actual=EvaMechanicalFrameR52.active(hull(l,o))?EvaMechanicalFrameR52.frame(hull(l,o),1):kind(data)==Kind.HULL_ONLY_RECOVERY?preview(l,o).frame():EvaMechanicalFrameR52.occupiedPreviewFrame(occupiedPreviews.get(o.eva()));if(!(NervR50CarrierModeR53.enabled()?receiver.domain().contains(actual.transformPoint(b.contactCentre())):pose(actual,directory.sample(leg,0,b).evaRoot())))return hold(o,"receiver_requires_real_approach_before_rail_admission");for(String id:receiver.gates())if(gates.get(id)==null||!declaredDoor(l,gates.get(id)))return false;return true;}
    @Override public NervOwnerPlacementR52.Proof finishingAssemblyPlacement(ServerLevel l,Original o,CompoundTag data)
    {return NervOwnerPlacementR52.capture(l,o,kind(data),NervMappedPlugMechanicsR52.selectedMachinery());}
    @Override public boolean finishOriginal(ServerLevel l,Original o,boolean returning,CompoundTag data)
    {
        var e=hull(l,o);var p=plant(o);if(e==null||p==null)return hold(o,"original_finishing_actor_missing");
        if(data.contains("LastFinishTick")&&data.getLong("LastFinishTick")==l.getGameTime())return false;data.putLong("LastFinishTick",l.getGameTime());
        Set<UUID> own=TransportMembershipR52.members(o,kind(data));
        if(!data.contains("Finish")){if(!EvaMechanicalFrameR52.active(e))return false;saveBinding(data,EvaMechanicalFrameR52.measuredBinding(e,o));putFrame(data,"FinishRoot",EvaMechanicalFrameR52.frame(e,1));data.putString("Finish",Finish.RECEIVE.name());data.putInt("FinishTicks",0);}
        try{if(!finishRouteStationsR52(l,o,data))return hold(o,"actual_traversed_station_storage_in_progress");}catch(java.io.IOException unavailable){return hold(o,"actual_traversed_station_source_unavailable");}
        var phase=Finish.valueOf(data.getString("Finish"));int age=data.getInt("FinishTicks")+1;
        if((returning||phase==Finish.RECEIVE)&&!pose(NervOwnerPlacementR52.actualRoot(e),getFrame(data,"FinishRoot")))return hold(o,"actual_received_root_changed");
        if(!returning)return finishDeployment(l,o,e,data,phase,age,own);
        if(!pose(getFrame(data,"FinishRoot"),p.bay())||!NervR50CarrierModeR53.enabled()&&!fixed(l,p.carrierSupport()))return hold(o,"original_bay_receiver_not_actual");
        var capsule=plug(l,o);var gantry=gantry(l,p);if(gantry==null)return false;
        switch(phase)
        {
            case RECEIVE -> {if(!dryBay(l,p)||!gateAtRest(l,servicePit(p),true)||!carrierSupportReadyR53(l,e))return hold(o,"original_receiver_dry_pit_or_foot_bearing_changed");float closure=Math.min(1,age/40F);if(!NervPlantMotionR52.clearRestraints(l,p.variant(),p.gantry().frame(),gantry.getRestraintProgress(),closure,own))return hold(o,"real_receiver_clamp_motion_blocked");gantry.setRestraintProgress(closure);if(age>=40&&originalClampsBear(l,p)){var carrier=EvaMechanicalFrameR52.originalCarrierControllerR52(e);try{if(carrier!=null&&!NervOriginalCarrierR52.setAttachedR52(l,carrier,e,false))return hold(o,"real_shoulder_support_to_empty_carrier_custody_rejected");}catch(java.io.IOException missing){return false;}data.putString("Finish",Finish.LOWER.name());data.putInt("FinishTicks",0);}}
            case LOWER -> {if(!dryBay(l,p)||!gateAtRest(l,servicePit(p),true)||!originalClampsBear(l,p))return hold(o,"original_clamps_and_open_dry_pit_required_for_lowering");var carrier=EvaMechanicalFrameR52.originalCarrierControllerR52(e);if(carrier==null)return false;if(!NervOriginalCarrierR52.actualRidePoseR52(carrier).equals(NervLegacyCarrierRideR52.rest())){var route=directory.route(data.getString("RouteR52"));if(route==null||route.legs().isEmpty())return false;var leg=directory.leg(route.legs().get(route.legs().size()-1));var rideOwn=new HashSet<>(own);rideOwn.add(carrier.getUUID());try{if(!prepareRunningShoesR52(l,o,leg,data,carrier,Set.copyOf(rideOwn),true))return hold(o,"actual_clamp_supported_running_shoe_stow_before_full_lower");}catch(java.io.IOException unavailable){return false;}}float next=Math.max(0,e.carrierRiseProgress(1)-1F/p.raiseTicks());if(!acceptCarrierActuatorR52(l,e,getFrame(data,"FinishRoot"),e.carrierRiseProgress(1),next,own,o,data))return hold(o,"real_receiver_carrier_lower_blocked");if(next==0){data.putString("Finish",Finish.SERVICE_BRIDGE_CLOSE.name());data.putInt("FinishTicks",0);}}
            case SERVICE_BRIDGE_CLOSE -> {if(!dryBay(l,p)||!originalClampsBear(l,p)||e.carrierRiseProgress(1)!=0||!gateAtRest(l,servicePit(p),true))return hold(o,"actual_lowered_carrier_open_pit_required_for_guide_retraction");if(groundGuidesDeclared){float next=Math.max(0,1-age/(float)NervServiceFootDriveR52.BRIDGE_CLOSE_TICKS);try{if(!NervServiceFootDriveR52.clearBridge(l,gantry,gantry.serviceGuideBridgeR52(1),next,own))return hold(o,"actual_service_guide_bridge_close_blocked");}catch(java.io.IOException missing){return false;}gantry.setServiceGuideBridgeR52(next);if(next!=0)break;}data.putString("Finish",nextAfterServiceBridgeCloseR52(hasWetFloorSealR52(gates.get("bay_"+p.variant()+"_front"))));data.putInt("FinishTicks",0);}
            case FRONT_SEAL_CLOSE -> {if(!wetFrontReturnClosePermitR52(dryBay(l,p),e.carrierRiseProgress(1),originalClampsBear(l,p),serviceBridgeReadyR52(l,p,false),gateAtRest(l,servicePit(p),true)))return hold(o,"actual_dry_lowered_clamp_supported_carrier_open_pit_required_before_front_seal_close");var front=gates.get("bay_"+p.variant()+"_front");if(!gate(l,front,false,own)||!gateAtRest(l,front,false)||hasWetFloorSealR52(front)&&!wetFloorSealClosedR52(l,front))return hold(o,"actual_front_door_and_declared_floor_seals_closing");data.putString("Finish",Finish.PIT_CLOSE.name());data.putInt("FinishTicks",0);}
            case PIT_CLOSE -> {if(!dryBay(l,p)||!originalClampsBear(l,p)||e.carrierRiseProgress(1)!=0||!serviceBridgeReadyR52(l,p,false))return hold(o,"lowered_full_carrier_and_actual_clamps_required_before_floor_close");var front=gates.get("bay_"+p.variant()+"_front");if(!wetPitClosePermitR52(hasWetFloorSealR52(front),wetFloorSealClosedR52(l,front)))return hold(o,"actual_paired_front_and_complete_floor_seal_must_close_before_pit");if(!gate(l,servicePit(p),false,own))return false;data.putString("Finish",Finish.LOWER_FRAME_CLOSE.name());data.putInt("FinishTicks",0);}
            case LOWER_FRAME_CLOSE -> {if(!dryBay(l,p)||!gateAtRest(l,servicePit(p),false)||!originalClampsBear(l,p)||e.carrierRiseProgress(1)!=0)return false;if(NervR50CarrierModeR53.enabled())gantry.setLowerFrameProgressR52(0);else{if(!gantry.lowerFrameDeclaredR52())return false;float next=Math.max(0,1-age/(float)NervLowerFrameR52.CLOSE_TICKS);try{if(!NervLowerFrameR52.clearAdvance(l,gantry,gantry.lowerFrameProgressR52(1),next,own))return hold(o,"actual_lower_frame_return_blocked");}catch(java.io.IOException failure){return false;}gantry.setLowerFrameProgressR52(next);if(next!=0)break;}if(kind(data)==Kind.HULL_ONLY_RECOVERY){if(!EvaMechanicalFrameR52.releaseHullToServiceR52(e,o))return hold(o,"actual_recovered_body_and_34hands_service_handoff_rejected");data.putString("Finish",Finish.REFILL.name());data.putInt("FinishTicks",0);break;}if(capsule==null||!originalLaunchLock(l,o.variant(),e,capsule))return false;if(!EvaMechanicalFrameR52.releaseToServiceR52(e,o))return hold(o,"actual_service_body_handoff_rejected");var before=EntryPlugEjectionR48.snapshot(capsule);if(!capsule.transitionInsertionStage(EntryPlugCarrierEntity.STAGE_LOCKED,capsule.getInsertionEpoch(),EntryPlugCarrierEntity.STAGE_EJECTING)||!EntryPlugEjectionR48.detach(e,capsule,before))return hold(o,"original_capsule_receiver_detach_rejected");data.putString("Finish",Finish.EXTRACT.name());data.putInt("FinishTicks",0);}
            case EXTRACT -> {if(capsule==null||capsule.getInsertionStage()!=EntryPlugCarrierEntity.STAGE_EJECTING||!capsule.isVehicle())return false;double progress=NervAssemblyClocksR52.extractionProgress(age);if(age<=36)EvaDorsalMechanism.prepare(e,age);else if(age>=137)EvaDorsalMechanism.seal(e,age-137);var target=age<=36?capsule.getCanonicalTransform():EntryPlugKinematics.insertionTransform(e,p.dock(),progress);if(!NervMappedPlugMechanicsR52.clearCapsule(l,e,capsule,capsule.getCanonicalTransform(),target,p.crane().visual().id()))return hold(o,"recovery_capsule_payload_unavailable");if(!(age<=36?approachCrane(l,p,capsule,age,data):crane(l,p,capsule,target,false)))return hold(o,"recovery_original_crane_approach_held");if(!NervMappedPlugMechanicsR52.applyInsertion(l,e,capsule,capsule.getCanonicalTransform(),target,p.crane().visual().id()))return hold(o,"recovery_capsule_motion_unavailable");if(l.getEntity(p.crane().visual().id()) instanceof NervCarrierPlatformEntity hoist&&age>=36)hoist.linkCranePlug(capsule);capsule.setInsertionProgress((int)Math.round(progress*100));capsule.setCabinRecoveryProgress((int)Math.round(EntryPlugCarrierEntity.CABIN_TRANSFER_PERCENT*progress));if(age>=197){if(!pose(capsule.getCanonicalTransform(),p.dock())||!capsule.transitionInsertionStage(EntryPlugCarrierEntity.STAGE_EJECTING,capsule.getInsertionEpoch(),EntryPlugCarrierEntity.STAGE_OCCUPIED))return false;data.putString("Finish",Finish.REFILL.name());data.putInt("FinishTicks",0);}}
            case REFILL -> {if(kind(data)==Kind.HULL_ONLY_RECOVERY&&EntryPlugDisposalR31.destroyed(l,p.plug())&&maintenanceCapsuleR53(l,p)==null)return hold(o,"destroyed_capsule_maintenance_replacement_failed");if(!gateAtRest(l,servicePit(p),false)||e.carrierRiseProgress(1)!=0||!originalClampsBear(l,p)||gantry.lowerFrameProgressR52(1)!=0)return hold(o,"watertight_actual_floor_and_clamps_required_before_refill");var front=gates.get("bay_"+p.variant()+"_front");if(!gateAtRest(l,front,false)){gate(l,front,false,own);return hold(o,"original_front_door_must_close_before_refill");}if(hasWetFloorSealR52(front)&&!wetSealRefillReadyR52(wetFloorSealClosedR52(l,front),wetSealBayDryR52(l,front),data.getInt("FilledLayers"),data,()->gate(l,front,false,own)))return hold(o,"actual_dry_front_and_complete_floor_seal_required_before_refill");if(kind(data)==Kind.OCCUPIED&&(capsule==null||!pose(capsule.getCanonicalTransform(),p.dock())||!crane(l,p,capsule,p.dock(),false)))return false;int count=Math.min(p.lcl().size(),age/4);int accepted=data.getInt("FilledLayers");while(accepted<count){if(!change(l,p.lcl().get(accepted),false,own))return hold(o,"real_lcl_refill_layer_changed_"+accepted);data.putInt("FilledLayers",++accepted);}gantry.setLclVisualLevel(Math.min(p.lcl().size(),age/4F));if(count==p.lcl().size()&&p.lcl().stream().allMatch(layer->matches(l,layer,false))){data.putString("Finish",Finish.BRIDGE.name());data.putInt("FinishTicks",0);}}
            case BRIDGE -> {int count=Math.min(9,(int)Math.floor(age*9D/40));if(age%5==0||age>=40)if(!applyBridgeState(l,p,count,data,own))return hold(o,"complete_original_bridge_extension_blocked_"+count);if(age>=40&&bridgeMatches(l,p,9)){if(kind(data)==Kind.OCCUPIED)capsule.setCabinRecoveryProgress(0);data.putString("Finish",Finish.DONE.name());captured.remove(o.eva());holds.remove(o.eva());return true;}}
            case DONE -> {holds.remove(o.eva());return true;}
            default -> {return hold(o,"outbound_phase_in_original_bay_return");}
        }
        if(phase.name().equals(data.getString("Finish")))data.putInt("FinishTicks",age);return false;
    }
    public static String deploymentGateResourceR53(NervRouteDirectoryR52 directory,String portId,Collection<String> receiverGates)
    {
        var routes=directory.routes().values().stream().filter(r->!r.recovery()&&r.port().equals(portId)).toList();if(routes.size()!=1)return null;var route=routes.get(0);var port=directory.ports().get(portId);if(port==null||!directory.leg(route.legs().get(route.legs().size()-1)).to().equals(port.node()))return null;
        String id="bank_"+route.bank()+"_surface_lane_"+route.lane();return receiverGates.contains(id)&&directory.leg(route.legs().get(route.legs().size()-1)).doors().contains(id)?id:null;
    }
    private Gate deploymentHatch(Receiver receiver,RigidTransform stop)
    {
        if(directory.schemaVersionR52()>=2)
        {
            String id=deploymentGateResourceR53(directory,receiver.port(),receiver.gates());var gate=id==null?null:gates.get(id);if(gate==null||gate.kind()!=GateKind.SILO||gate.frame().translation().subtract(stop.translation()).horizontalDistanceSqr()>=.0001)return null;
            return deploymentLandingRootR53(gate,stop)==null?null:gate;
        }
        Gate found=null;for(String id:receiver.gates()){var g=gates.get(id);if(g!=null&&g.kind()==GateKind.SILO&&g.frame().translation().subtract(stop.translation()).horizontalDistanceSqr()<.0001&&Math.abs(g.frame().translation().y-stop.translation().y+3.98)<.002){if(found!=null)return null;found=g;}}return found;
    }
    private static RigidTransform deploymentLandingRootR53(Gate hatch,RigidTransform stop)
    {
        if(hatch==null||hatch.kind()!=GateKind.SILO||hatch.siloHatch()==null||hatch.siloHatch().separationSign()!=1||Math.abs(hatch.frame().transformVector(new Vec3(0,1,0)).y-1)>1e-7)return null;
        Integer y=null;for(var row:hatch.collisionSteps())for(var c:row){if(c.closed().isAir()||!c.open().isAir()||y!=null&&y!=c.at().getY())return null;y=c.at().getY();}if(y==null||Math.abs(hatch.frame().translation().y+SiloHatchMechanism.PANEL_TOP-(y+1))>.002)return null;
        try{var profile=new NervBallisticHandoffR52.Profile(y+1-stop.translation().y);return new RigidTransform(stop.translation().add(0,profile.landingDelta(),0),stop.qx(),stop.qy(),stop.qz(),stop.qw());}catch(IllegalArgumentException changed){return null;}
    }
    private NervBallisticHandoffR52.Proof ballisticProof(ServerLevel l,Original o,EvaUnit01Entity e,CompoundTag data,Gate hatch)
    {
        var start=getFrame(data,"FinishRoot");var landing=deploymentLandingRootR53(hatch,start);if(landing==null)return null;var profile=new NervBallisticHandoffR52.Profile(landing.translation().y-start.translation().y);var expected=new CompoundTag();expected.putInt("Version",1);expected.putString("Directory",directory.fingerprint());expected.putString("Route",data.getString("RouteR52"));expected.putString("Gate",hatch.resource());expected.putUUID("GateUUID",hatch.visual());expected.putString("HatchSource",NervSiloHatchGeometryR52.SOURCE_SHA);expected.putString("PayloadSource",EvaMechanicalFrameR52.capturedGeometry(e).sourceFingerprint());expected.putDouble("Gravity",e.getAttributeValue(net.minecraftforge.common.ForgeMod.ENTITY_GRAVITY.get()));expected.putDouble("LandingDelta",profile.landingDelta());expected.putInt("FlightTicks",NervBallisticHandoffR52.FLIGHT_TICKS);expected.putInt("CarrierTicks",NervBallisticHandoffR52.CARRIER_TICKS);expected.putInt("CloseTicks",hatch.siloHatch().closeTicks());putFrame(expected,"Start",start);putFrame(expected,"Landing",landing);putFrame(expected,"Hatch",hatch.frame());
        if(data.contains("BallisticProfileR53")){if(!data.getCompound("BallisticProfileR53").equals(expected))return null;}else{if(directory.schemaVersionR52()>=2&&!data.getString("Finish").equals(Finish.RECEIVE.name()))return null;data.put("BallisticProfileR53",expected);}
        var proof=ballistic.get(o.eva());if(proof!=null&&!proof.profile().equals(profile))return null;if(proof==null){proof=NervBallisticHandoffR52.capture(l,o,e,start,profile);if(proof!=null)ballistic.put(o.eva(),proof);}return proof;
    }
    private boolean finishDeployment(ServerLevel l,Original o,EvaUnit01Entity e,CompoundTag data,Finish phase,int age,Set<UUID> own)
    {
        var route=directory.route(data.getString("RouteR52"));var receiver=route==null?null:receivers.get(route.port());if(kind(data)!=Kind.OCCUPIED||receiver==null||!fixed(l,receiver.supports()))return hold(o,"actual_deployment_support_missing");
        var stop=getFrame(data,"FinishRoot");var hatch=deploymentHatch(receiver,stop);if(hatch==null||hatch.siloHatch().closeTicks()!=NervBallisticHandoffR52.CLOSE_TICKS)return hold(o,"actual_port_bound_fast_outlet_hatch_required");var landing=deploymentLandingRootR53(hatch,stop);if(landing==null||directory.schemaVersionR52()>=2&&NervOriginalCarrierR52.controller(l,o)==null)return hold(o,"actual_deployment_floor_or_original_carrier_missing");
        var proof=ballisticProof(l,o,e,data,hatch);if(proof==null)return hold(o,"actual_ballistic_payload_or_saved_landing_profile_changed");
        switch(phase)
        {
            case RECEIVE -> {for(String id:receiver.gates())if(!gateAtRest(l,gates.get(id),true))return hold(o,"deployment_hatch_must_be_physically_open");if(!carrierSupportReadyR53(l,e)||!NervR50CarrierModeR53.enabled()&&!proof.clearLaunch(l,e,hatch)||!EvaMechanicalFrameR52.beginBallisticR52(e,o,proof.launchVelocity()))return hold(o,"actual_full_payload_carrier_and_hatch_ballistic_sweep_blocked");data.putString("Finish",Finish.EJECT_LOWER.name());data.putInt("FinishTicks",0);}
            case EJECT_LOWER -> {if(!proof.placement(l,e)||!gateAtRest(l,hatch,true))return hold(o,"actual_ballistic_custody_or_open_hatch_changed");float next=Math.max(0,1-age/(float)NervBallisticHandoffR52.CARRIER_TICKS);if(!acceptCarrierActuatorR52(l,e,EvaMechanicalFrameR52.carrierFrameR52(e,1),e.carrierRiseProgress(1),next,own,o,data))return hold(o,"actual_independent_dolly_return_blocked");if(next==0){data.putString("Finish",Finish.EJECT_CLOSE.name());data.putInt("FinishTicks",0);}}
            case EJECT_CLOSE -> {if(!proof.placement(l,e)||e.carrierRiseProgress(1)!=0)return hold(o,"actual_ballistic_source_or_full_dolly_clearance_changed");if(!gate(l,hatch,false,own))return false;data.putString("Finish",Finish.LAND.name());data.putInt("FinishTicks",0);}
            case LAND -> {if(!proof.placement(l,e)||!gateAtRest(l,hatch,false))return hold(o,"real_closed_hatch_before_landing_required");
                if(NervR50CarrierModeR53.enabled())
                {
                    if(EvaMechanicalFrameR52.ballisticTicksR52(e)<NervBallisticHandoffR52.FLIGHT_TICKS||e.position().distanceToSqr(landing.translation())>.0004)return false;
                    if(!EvaMechanicalFrameR52.releaseUpright(e,o))return false;
                    e.setNervLogisticsLocked(false);e.setNoGravity(false);e.setOnGround(true);e.setDeltaMovement(Vec3.ZERO);e.resetFallDistance();e.clearSortieDestination();
                    data.putString("Finish",Finish.DONE.name());data.putInt("FinishTicks",0);captured.remove(o.eva());ballistic.remove(o.eva());holds.remove(o.eva());return true;
                }
                if(!e.onGround())return false;if(e.getDeltaMovement().lengthSqr()>1e-8||e.position().distanceToSqr(landing.translation())>.0004)return hold(o,"actual_native_declared_floor_contact_required");if(!EvaMechanicalReleaseR52.beginGroundedR52(l,e,o))return hold(o,"actual_grounded_ordinary_transition_not_admitted");data.putString("Finish",Finish.RELEASE.name());data.putInt("FinishTicks",0);}
            case RELEASE -> {if(!gateAtRest(l,hatch,false)||e.carrierRiseProgress(1)!=0)return hold(o,"actual_hatch_and_stowed_dolly_changed_during_release");if(!EvaMechanicalReleaseR52.advanceGroundedR52(l,e,o))return false;data.putString("Finish",Finish.DONE.name());data.putInt("FinishTicks",0);captured.remove(o.eva());ballistic.remove(o.eva());return true;}
            case DONE -> {return true;}
            default -> {return hold(o,"return_phase_in_ballistic_deployment");}
        }
        if(phase.name().equals(data.getString("Finish")))data.putInt("FinishTicks",age);return false;
    }
    private static void putFrame(CompoundTag t,String name,RigidTransform f){var a=new CompoundTag();a.putDouble("X",f.translation().x);a.putDouble("Y",f.translation().y);a.putDouble("Z",f.translation().z);a.putFloat("QX",f.qx());a.putFloat("QY",f.qy());a.putFloat("QZ",f.qz());a.putFloat("QW",f.qw());t.put(name,a);}
    private static RigidTransform getFrame(CompoundTag t,String name){var a=t.getCompound(name);return new RigidTransform(new Vec3(a.getDouble("X"),a.getDouble("Y"),a.getDouble("Z")),a.getFloat("QX"),a.getFloat("QY"),a.getFloat("QZ"),a.getFloat("QW"));}
    private static void saveBinding(CompoundTag t,FootSupportFrameR52.Binding b){putFrame(t,"FinishPlugLocal",b.plugInEva());var a=new CompoundTag();a.putDouble("LX",b.leftFoot().x);a.putDouble("LY",b.leftFoot().y);a.putDouble("LZ",b.leftFoot().z);a.putDouble("RX",b.rightFoot().x);a.putDouble("RY",b.rightFoot().y);a.putDouble("RZ",b.rightFoot().z);t.put("FinishFeet",a);}
    private static FootSupportFrameR52.Binding finishingBinding(CompoundTag t){var a=t.getCompound("FinishFeet");return new FootSupportFrameR52.Binding(new Vec3(a.getDouble("LX"),a.getDouble("LY"),a.getDouble("LZ")),new Vec3(a.getDouble("RX"),a.getDouble("RY"),a.getDouble("RZ")),getFrame(t,"FinishPlugLocal"));}

    @Override public boolean restoreFinishingOriginal(ServerLevel l,Original o,CompoundTag data)
    {
        var e=hull(l,o);if(e==null||!originalGraph(l,o,kind(data)==Kind.OCCUPIED)||data.contains("BridgeAmount")&&!savedBridgeMatches(l,plant(o),data))return false;
        var route=directory.route(data.getString("RouteR52"));if(route!=null&&!route.recovery()&&data.contains("FinishRoot")&&data.contains("FinishFeet")){
            var endpoint=directory.sample(directory.leg(route.legs().get(route.legs().size()-1)),1,finishingBinding(data)).evaRoot();if(!pose(endpoint,getFrame(data,"FinishRoot")))return false;var receiver=receivers.get(route.port());if(receiver==null||!fixed(l,receiver.supports()))return false;var hatch=deploymentHatch(receiver,endpoint);if(hatch==null||!flightGateSampleCurrent(l,hatch.resource()))return false;
            var landing=deploymentLandingRootR53(hatch,endpoint);if(landing==null)return false;String phase=data.getString("Finish");if(phase.equals(Finish.RELEASE.name()))return EvaMechanicalFrameR52.active(e)&&pose(NervOwnerPlacementR52.actualRoot(e),landing)&&ballisticProof(l,o,e,data,hatch)!=null&&EvaMechanicalReleaseR52.actualGroundBearingR52(l,e,EvaMechanicalFrameR52.capturedGeometry(e),EvaMechanicalFrameR52.frame(e,1))&&!EvaMechanicalFrameR52.groundReleaseStateR52(e).isEmpty();
            if(Set.of(Finish.EJECT_LOWER.name(),Finish.EJECT_CLOSE.name(),Finish.LAND.name()).contains(phase)){var proof=ballisticProof(l,o,e,data,hatch);return EvaMechanicalFrameR52.ballisticCustodyR52(e)&&EvaMechanicalFrameR52.detachedCarrierR52(e)&&pose(EvaMechanicalFrameR52.carrierFrameR52(e,1),endpoint)&&proof!=null&&proof.placement(l,e);}
        }
        return (EvaMechanicalFrameR52.active(e)||data.contains("FinishRoot")&&pose(NervOwnerPlacementR52.actualRoot(e),getFrame(data,"FinishRoot")))&&finishingAssemblyPlacement(l,o,data)!=null;
    }
    @Override public RigidTransform finishingReferenceFrameR52(ServerLevel l,Original o,CompoundTag data,RigidTransform directoryEndpoint)
    {var e=hull(l,o);return e!=null&&EvaMechanicalFrameR52.ballisticCustodyR52(e)&&data.contains("FinishRoot")&&pose(directoryEndpoint,getFrame(data,"FinishRoot"))&&restoreFinishingOriginal(l,o,data)?NervOwnerPlacementR52.actualRoot(e):directoryEndpoint;}

    @Override public void brakeOriginalInPlace(ServerLevel l,Original o,CompoundTag data){var e=hull(l,o);if(e!=null){if(!EvaMechanicalFrameR52.ballisticCustodyR52(e)){e.setDeltaMovement(Vec3.ZERO);EvaMechanicalFrameR52.holdContinuousR52(e);}e.getNavigation().stop();holds.putIfAbsent(o.eva(),"mechanical_brake_in_place");}}
    @Override public boolean originalEntryPlugBindingsReady(ServerLevel l){return commissioned;}
    @Override public RigidTransform originalDockPose(ServerLevel l,int v){return units.containsKey(v)?units.get(v).dock():null;}
    @Override public RigidTransform originalBayPose(ServerLevel l,int v){return units.containsKey(v)?units.get(v).bay():null;}
    @Override public Vec3 originalBoardingAnchor(ServerLevel l,EntryPlugCarrierEntity p){var u=units.get(p.getAssignedVariant());return u!=null&&u.plug().equals(p.getUUID())?u.boarding():null;}
    @Override public Vec3 originalDismountAnchor(ServerLevel l,EntryPlugCarrierEntity p,LivingEntity passenger)
    {
        var u=units.get(p.getAssignedVariant());
        if(u==null||!u.plug().equals(p.getUUID()))return null;
        if(p.getInsertionStage()==EntryPlugCarrierEntity.STAGE_FIELD_LANDED)return p.mappedFieldDismountR52(passenger);
        if(p.isLockedToEva()||!pose(p.getCanonicalTransform(),u.dock())
                ||!Set.of(EntryPlugCarrierEntity.STAGE_SUSPENDED,EntryPlugCarrierEntity.STAGE_OCCUPIED,
                        EntryPlugCarrierEntity.STAGE_ABORT_DOCKED).contains(p.getInsertionStage())
                ||!bridgeMatches(l,u,9))return null;
        for(var at:u.dismount())if(loaded(l,BlockPos.containing(at))
                &&TrainingPilotDirector.safeActualFeetR47(l,at)
                &&l.noCollision(passenger,passenger.getDimensions(net.minecraft.world.entity.Pose.STANDING).makeBoundingBox(at)))return at;
        return null;
    }
    @Override public boolean originalBoardingAllowed(ServerLevel l,EntryPlugCarrierEntity p,Entity passenger){var u=units.get(p.getAssignedVariant());return u!=null&&u.plug().equals(p.getUUID())&&(pose(p.getCanonicalTransform(),u.dock())||p.getInsertionStage()==EntryPlugCarrierEntity.STAGE_FIELD_LANDED)&&!p.isVehicle();}
    @Override public boolean originalLaunchLock(ServerLevel l,int v,EvaUnit01Entity e,EntryPlugCarrierEntity p){var u=units.get(v);return u!=null&&u.eva().equals(e.getUUID())&&u.plug().equals(p.getUUID())&&p.isLockedToEva()&&p.getVehicle()==e&&p.getFirstPassenger()!=null&&p.isHatchFullySealed()&&e.isEntryPlugInserted()&&p.getLinkedEva()==e;}
    @Override public boolean originalCageDock(ServerLevel l,int v,EvaUnit01Entity e,EntryPlugCarrierEntity p){var u=units.get(v);return u!=null&&u.eva().equals(e.getUUID())&&u.plug().equals(p.getUUID())&&pose(p.getCanonicalTransform(),u.dock())&&e.position().distanceToSqr(u.bay().translation())<1e-6;}
    @Override public boolean requestOriginalEjection(ServerLevel l,int v,EvaUnit01Entity e,LivingEntity pilot)
    {var p=units.get(v);if(p==null||!p.eva().equals(e.getUUID())||!(l.getEntity(p.plug()) instanceof EntryPlugCarrierEntity capsule)||capsule.getFirstPassenger()!=pilot||EvaMechanicalFrameR52.active(e)||e.isNervLogisticsLocked())return false;return EntryPlugDirector.beginMappedFieldEjectionR52(l,e,capsule,pilot);}
    @Override public void maintainOriginalCapsule(ServerLevel l,EntryPlugCarrierEntity p){if(!commissioned||capsuleTicks.getOrDefault(p.getUUID(),Long.MIN_VALUE)==l.getGameTime())return;capsuleTicks.put(p.getUUID(),l.getGameTime());p.retainMappedPilotSeatR53();p.restoreMappedLockedTranslationR53();p.tickMappedHatchR52();if(p.getInsertionStage()==EntryPlugCarrierEntity.STAGE_FIELD_EJECTING)EntryPlugDirector.tickMappedFieldEjectionR52(p);p.syncPilotPositionNow();var unit=units.get(p.getAssignedVariant());if(unit!=null){var g=gantry(l,unit);if(g!=null)g.holdStatic(g.getX(),g.getY(),g.getZ());var crane=l.getEntity(unit.crane().visual().id());if(crane instanceof NervCarrierPlatformEntity c)c.holdStatic(c.getX(),c.getY(),c.getZ());}}
    @Override public boolean originalSeatAllowed(ServerLevel l,NervCommandSeatEntity seat,TrainingPilotEntity pilot)
    {var p=units.get(pilot.getAssignedVariant());return p!=null&&p.npc().equals(pilot.getUUID())&&p.seat().equals(seat.getUUID())&&seat.getType()==ModEntities.PILOT_REST_SEAT_R47.get()&&seat.getPersistentData().hasUUID("RestroomPilotR47")&&seat.getPersistentData().getUUID("RestroomPilotR47").equals(pilot.getUUID())&&seat.position().distanceToSqr(p.seatFrame().translation())<1e-8&&fixed(l,p.chair());}
    @Override public Vec3 originalSeatStand(ServerLevel l,NervCommandSeatEntity seat,TrainingPilotEntity pilot)
    {var p=units.get(pilot.getAssignedVariant());return p!=null&&originalSeatAllowed(l,seat,pilot)&&TrainingPilotDirector.safeActualFeetR47(l,p.standby())&&l.noCollision(pilot,pilot.getDimensions(net.minecraft.world.entity.Pose.STANDING).makeBoundingBox(p.standby()))?p.standby():null;}
    @Override public boolean originalPersonnelBindingsReady(ServerLevel l){return commissioned&&units.values().stream().allMatch(u->l.getEntity(u.npc()) instanceof TrainingPilotEntity&&l.getEntity(u.seat())!=null);}
    @Override public TrainingPilotEntity originalPilot(ServerLevel l,int v){var p=units.get(v);return p!=null&&l.getEntity(p.npc()) instanceof TrainingPilotEntity n&&n.getAssignedVariant()==v?n:null;}
    @Override public TrainingPilotDirector.ActionResult requestOriginalPilot(ServerLevel l,int v,String operation){var n=originalPilot(l,v);if(n==null||!Set.of("board","return","standby").contains(operation))return new TrainingPilotDirector.ActionResult(false,"原驾驶员或声明的操作尚未就绪。");pilotOperations.put(n.getUUID(),operation);pilotNodes.put(n.getUUID(),0);n.getPersistentData().putString("R52OriginalPilotOperation",operation);n.getPersistentData().putString("R52OriginalPilotDirectory",directory.fingerprint());n.getPersistentData().putInt("R52OriginalPilotNode",0);return new TrainingPilotDirector.ActionResult(true,"原驾驶员已沿声明的真实步行路线前往岗位。");}
    @Override public boolean routeOriginalPilot(ServerLevel l,TrainingPilotEntity n,String operation)
    {
        var p=units.get(n.getAssignedVariant());if(p==null||!p.npc().equals(n.getUUID()))return false;var saved=n.getPersistentData();if(!saved.getString("R52OriginalPilotDirectory").equals(directory.fingerprint()))return atOriginalPilotStandby(l,p.variant());String requested=saved.getString("R52OriginalPilotOperation");if(!Set.of("board","return","standby").contains(requested))return false;
        if(n.getVehicle()!=null)
        {
            if(n.getVehicle() instanceof EntryPlugCarrierEntity capsule)
            {
                if(!capsule.getUUID().equals(p.plug()))return false;
                if(requested.equals("board"))return true;
                if(originalDismountAnchor(l,capsule,n)==null||!personnelDoors(l,p,true))return false;
                n.stopRiding();
                if(n.getVehicle()!=null||!TrainingPilotDirector.safeActualFeetR47(l,n.position()))return false;
            }
            else
            {
                if(!requested.equals("board")||!(n.getVehicle() instanceof NervCommandSeatEntity seat)
                        ||originalSeatStand(l,seat,n)==null)return atOriginalPilotStandby(l,p.variant());
                n.stopRiding();
                if(n.getVehicle()!=null||n.position().distanceToSqr(p.standby())>1)return false;
            }
        }
        if(!personnelDoors(l,p,true))return false;n.setNoAi(false);n.setNoGravity(false);n.setInvisible(false);n.setTrainingStage(TrainingPilotEntity.STAGE_WALKING);
        var path=requested.equals("board")?p.boardPath():p.returnPath();int at=saved.contains("R52OriginalPilotNode")?saved.getInt("R52OriginalPilotNode"):pilotNodes.getOrDefault(n.getUUID(),0);
        if(at<0||at>path.size())return false;
        if(at>=path.size())
        {if(requested.equals("board")&&l.getEntity(p.plug()) instanceof EntryPlugCarrierEntity capsule){if(!capsule.boardPassenger(n))return false;personnelDoors(l,p,false);return true;}if(l.getEntity(p.seat()) instanceof NervCommandSeatEntity seat&&originalSeatAllowed(l,seat,n)&&n.position().distanceToSqr(p.standby())<=1&&n.startRiding(seat,true)){var toward=p.phone().subtract(p.seatFrame().translation());float heading=(float)Math.toDegrees(Math.atan2(-toward.x,toward.z));n.setYRot(heading);n.yBodyRot=heading;n.setYHeadRot(heading);n.setTrainingStage(TrainingPilotEntity.STAGE_STANDBY);n.getPersistentData().putString("SeelePilotRouteR30","standby");personnelDoors(l,p,false);return true;}return false;}
        var target=path.get(at);if(!loaded(l,BlockPos.containing(target))||!TrainingPilotDirector.safeActualFeetR47(l,target))return false;
        if(n.position().multiply(1,0,1).distanceToSqr(target.multiply(1,0,1))<.65*.65&&Math.abs(n.getY()-target.y)<.45){pilotNodes.put(n.getUUID(),at+1);saved.putInt("R52OriginalPilotNode",at+1);return true;}
        var destination=BlockPos.containing(target);
        if(!n.getNavigation().isDone()&&destination.equals(n.getNavigation().getTargetPos()))return true;
        var nativePath=n.getNavigation() instanceof TrainingPilotNavigationR47 navigation
                ?navigation.createDeclaredRoutePathR47(destination,path.stream().map(BlockPos::containing).toList())
                :n.getNavigation().createPath(destination,0);
        if(nativePath==null||!nativePath.canReach())return false;
        for(int i=0;i<nativePath.getNodeCount();i++)
        {
            var node=nativePath.getNode(i);
            if(!TrainingPilotDirector.safeActualFeetR47(l,new Vec3(node.x+.5,node.y,node.z+.5)))return false;
        }
        return n.getNavigation().moveTo(nativePath,1);
    }
    @Override public boolean atOriginalPilotStandby(ServerLevel l,int v){var p=units.get(v);var n=originalPilot(l,v);return p!=null&&n!=null&&n.getVehicle()!=null&&n.getVehicle() instanceof NervCommandSeatEntity seat&&originalSeatAllowed(l,seat,n)&&seat.getFirstPassenger()==n;}
    /** Reads one explicit Root file. This neither commissions nor installs it. */
    public static NervAssemblyOwnerR52 read(Path file,NervRouteDirectoryR52 directory)throws java.io.IOException
    {return parse(readDocumentR52(file),directory);}
    /** Expands strictly hashed byte tables without consulting any native state. */
    static JsonObject readDocumentR52(Path file)throws java.io.IOException
    {return readDocumentR52(file,Files.readAllBytes(file));}
    static JsonObject readDocumentR52(Path file,byte[] approvedBytes)throws java.io.IOException
    {
        var root=JsonParser.parseString(new String(approvedBytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();var parent=file.toAbsolutePath().normalize().getParent().toRealPath();
        for(var row:root.getAsJsonArray("units")){var u=row.getAsJsonObject();for(String field:List.of("lcl","bridge_states"))if(u.get(field).isJsonObject())u.add(field,componentTable(parent,u.getAsJsonObject(field)));}
        for(var row:root.getAsJsonArray("gates")){var gate=row.getAsJsonObject();if(gate.get("collision_steps").isJsonObject())gate.add("collision_steps",componentTable(parent,gate.getAsJsonObject("collision_steps")));}
        return root;
    }
    private static JsonArray componentTable(Path parent,JsonObject reference)throws java.io.IOException
    {
        String name=reference.get("cells_file").getAsString();var relative=Path.of(name);require(!relative.isAbsolute()&&!name.contains(":")&&!relative.normalize().startsWith(".."),"Root-relative component table required");var path=parent.resolve(relative).toRealPath();require(path.startsWith(parent)&&Files.size(path)<=32000000,"Bounded Root component source required");byte[] compressed=Files.readAllBytes(path);String actual;try{actual=HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(compressed));}catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}require(actual.equals(reference.get("sha256").getAsString()),"Actual component table source changed");try(var input=new java.util.zip.GZIPInputStream(new java.io.ByteArrayInputStream(compressed))){byte[] decoded=input.readNBytes(32000001);require(decoded.length<=32000000,"Bounded complete component table required");return JsonParser.parseString(new String(decoded,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonArray();}
    }
    public static NervAssemblyOwnerR52 parse(JsonObject root,NervRouteDirectoryR52 directory)
    {
        require(root.get("schema").getAsString().equals(SCHEMA)&&root.get("map_author").getAsString().equals("root")&&root.get("epoch").getAsLong()==directory.epoch()&&root.get("directory_fingerprint").getAsString().equals(directory.fingerprint()),"Root mechanical/directory provenance mismatch");
        String status=root.get("status").getAsString();require(status.equals("design")||status.equals("installed"),"Explicit mechanical installation state required");require(root.get("commissioning_receipt_sha256").getAsString().matches("[0-9a-f]{64}"),"Root physical commissioning receipt required");
        if(root.has("ground_guides"))
        {
            var sources=root.getAsJsonObject("mechanism_sources");
            require(sources.has(NervLegacyServiceBypassR52.SOURCE)&&sources.get(NervLegacyServiceBypassR52.SOURCE).getAsString().equals(NervLegacyServiceBypassR52.SOURCE_SHA)&&sources.has(NervLegacyCompactLevelR52.SOURCE)&&sources.get(NervLegacyCompactLevelR52.SOURCE).getAsString().equals(NervLegacyCompactLevelR52.SOURCE_SHA),"Owner must retain the exact independent service-pipe and finite level-rail sources");
            require(sources.has(NervLegacyDeepFrameR53.SOURCE)&&sources.get(NervLegacyDeepFrameR53.SOURCE).getAsString().equals(NervLegacyDeepFrameR53.SOURCE_SHA),"Owner must retain the exact approved rigid deep frame");
            require(sources.has(NervBankHeadTransferR53.SOURCE)&&sources.get(NervBankHeadTransferR53.SOURCE).getAsString().equals(NervBankHeadTransferR53.SOURCE_SHA),"Owner must retain the exact actual bank-head slide and socket source");
        }
        var units=new HashMap<Integer,UnitPlant>();for(var raw:root.getAsJsonArray("units")){var u=raw.getAsJsonObject();int v=u.get("variant").getAsInt();var cr=u.getAsJsonObject("crane");var c=new Crane(visual(cr.getAsJsonObject("visual")),frame(cr.getAsJsonObject("stow_frame")),number(cr,"initial_bottom"),number(cr,"stow_bottom"),vector(cr.getAsJsonArray("rail_axis_local")),number(cr,"rail_min"),number(cr,"rail_max"),number(cr,"hoist_step"),fixedCells(cr.getAsJsonArray("frame_cells")));
        var p=new UnitPlant(v,uuid(u,"eva"),uuid(u,"plug"),uuid(u,"original_npc"),uuid(u,"original_seat"),frame(u.getAsJsonObject("bay_frame")),frame(u.getAsJsonObject("dock_frame")),vector(u.getAsJsonArray("boarding")),points(u.getAsJsonArray("dismount")),bridgeStates(u.getAsJsonArray("bridge_states")),steps(u.getAsJsonArray("lcl")),visual(u.getAsJsonObject("gantry")),c,fixedCells(u.getAsJsonArray("carrier_support")),u.get("carrier_raise_ticks").getAsInt(),frame(u.getAsJsonObject("seat_frame")),fixedCells(u.getAsJsonArray("chair")),vector(u.getAsJsonArray("phone")),vector(u.getAsJsonArray("standby")),points(u.getAsJsonArray("board_path")),points(u.getAsJsonArray("return_path")),number(u,"boarding_radius"),u.has("hull_handoff")?new HullHandoff(fixedCells(u.getAsJsonObject("hull_handoff").getAsJsonArray("supports")),u.getAsJsonObject("hull_handoff").get("lower_ticks").getAsInt()):null,steps(u.getAsJsonArray("personnel_doors")));require(units.putIfAbsent(v,p)==null,"Duplicate original plant");}
        var gates=new HashMap<String,Gate>();for(var raw:root.getAsJsonArray("gates")){var g=raw.getAsJsonObject();String id=g.get("resource").getAsString();var item=new Gate(id,uuid(g,"visual"),GateKind.valueOf(g.get("kind").getAsString()),g.get("variant").getAsInt(),g.get("stage").getAsInt(),frame(g.getAsJsonObject("frame")),g.get("width").getAsFloat(),g.get("height").getAsFloat(),steps(g.getAsJsonArray("collision_steps")),fixedCells(g.getAsJsonArray("supports")),g.has("silo_hatch")?siloSpec(g.getAsJsonObject("silo_hatch")):null,g.has("hangar_stack")?hangarSpec(g):null);if(NervR50CarrierModeR53.enabled()&&g.has("floor_seal_original_cells")){var retired=new HashSet<BlockPos>();for(var position:g.getAsJsonArray("floor_seal_original_cells"))retired.add(position(position.getAsJsonArray()));var spec=item.hangarStack();item=new Gate(item.resource(),item.visual(),item.kind(),item.variant(),item.stage(),item.frame(),item.width(),item.height(),item.collisionSteps().stream().map(row->row.stream().filter(cell->!retired.contains(cell.at())).toList()).toList(),item.supports(),item.siloHatch(),new NervHangarGateGeometryR52.Spec(spec.width(),spec.height(),spec.openTicks(),spec.closeTicks(),spec.depthDirection()));}require(directory.resource(id)!=null&&directory.resource(id).kind()==ResourceKind.DOOR&&gates.putIfAbsent(id,item)==null,"Unbound/duplicate declared gate");if(hasWetFloorSealR52(item)){if(item.hangarStack().bottomSeal().version()==2)require(directory.schemaVersionR52()==2&&g.has("floor_seal_original_cells"),"Expanded actual floor seal requires the new directory and complete exact source-cell trace");if(g.has("floor_seal_original_cells")){var trace=new HashSet<BlockPos>();for(var cell:g.getAsJsonArray("floor_seal_original_cells"))require(trace.add(position(cell.getAsJsonArray())),"Duplicate actual floor-seal original cell");require(trace.equals(wetFloorSealCellsR52(item).stream().map(Cell::at).collect(java.util.stream.Collectors.toSet())),"Actual floor boxes and original floor-cell trace differ");}}if(directory.schemaVersionR52()==2&&item.siloHatch()!=null&&item.siloHatch().serviceColumnPorts())require(g.getAsJsonObject("silo_hatch").has("service_gantry_yaw_degrees"),"Current service pit requires an explicit actual gantry-relative yaw");}
        var resources=new HashMap<String,List<FixedCell>>();for(var row:root.getAsJsonObject("resources").entrySet())require(resources.putIfAbsent(row.getKey(),fixedCells(row.getValue().getAsJsonArray()))==null,"Duplicate physical resource");
        var receivers=new HashMap<String,Receiver>();for(var raw:root.getAsJsonArray("receivers")){var r=raw.getAsJsonObject();String id=r.get("port").getAsString();var b=r.getAsJsonArray("domain");require(b.size()==6,"Explicit recovery domain required");var low=new Vec3(b.get(0).getAsDouble(),b.get(1).getAsDouble(),b.get(2).getAsDouble());var high=new Vec3(b.get(3).getAsDouble(),b.get(4).getAsDouble(),b.get(5).getAsDouble());require(Double.isFinite(low.lengthSqr()+high.lengthSqr())&&low.x<high.x&&low.y<high.y&&low.z<high.z,"Actual positive recovery domain required");var ids=new ArrayList<String>();for(var g:r.getAsJsonArray("gates")){String gate=g.getAsString();require(gates.containsKey(gate),"Unknown receiver gate");ids.add(gate);}var item=new Receiver(id,Region.valueOf(r.get("region").getAsString()),new AABB(low,high),frame(r.getAsJsonObject("stopped_frame")),fixedCells(r.getAsJsonArray("supports")),ids,r.get("carrier_ticks").getAsInt());require(directory.ports().containsKey(id)&&directory.ports().get(id).region()==item.region()&&item.carrierTicks()>0&&!item.supports().isEmpty()&&receivers.putIfAbsent(id,item)==null,"Unbound/duplicate physical receiver");}
        for(var gate:gates.values())validateEarlyGuideRoleR53(gate.resource(),gate.variant(),gate.siloHatch());
        require(receivers.keySet().equals(directory.ports().keySet()),"Every real port needs its exact receiving mechanism");var owner=new NervAssemblyOwnerR52(directory,directory.epoch(),status.equals("installed"),units,gates,resources,receivers,root.getAsJsonObject("mechanism_sources").get("mesh/tv_shoulder_shells_r44.json").getAsString());
        var pits=new HashMap<Integer,String>();for(var raw:root.getAsJsonArray("units")){var u=raw.getAsJsonObject();if(!u.has("service_pit")){require(!status.equals("installed"),"Installed original bay requires its actual dry service pit gate");continue;}int v=u.get("variant").getAsInt();String id=u.get("service_pit").getAsString();var gate=gates.get(id);require(gate!=null&&gate.kind()==GateKind.SILO&&gate.variant()==v&&gate.siloHatch().separationSign()==-1&&gate.siloHatch().serviceColumnPorts()&&pits.putIfAbsent(v,id)==null,"Actual original-bay downward pit gate required");}owner.servicePits=Map.copyOf(pits);for(var pit:pits.entrySet()){var unit=units.get(pit.getKey());var gate=gates.get(pit.getValue());require(pose(unit.gantry().frame(),gate.frame().compose(gate.siloHatch().serviceGantryRelativeFrame())),"Actual gantry and service pit frame differ from the explicit port-relative transform");}var lower=new HashSet<Integer>();for(var raw:root.getAsJsonArray("units")){var u=raw.getAsJsonObject();if(!u.has("lower_frame")){require(!status.equals("installed"),"Installed original bay requires actual lower crossbar mechanism");continue;}var spec=u.getAsJsonObject("lower_frame");require(spec.get("source_sha256").getAsString().equals(NervLowerFrameR52.SOURCE_SHA)&&spec.get("open_ticks").getAsInt()==NervLowerFrameR52.OPEN_TICKS&&spec.get("close_ticks").getAsInt()==NervLowerFrameR52.CLOSE_TICKS,"Actual selected lower-frame source and physical clocks required");lower.add(u.get("variant").getAsInt());}owner.lowerFrames=Set.copyOf(lower);if(root.has("ground_guides")){var guide=root.getAsJsonObject("ground_guides");boolean continuous=directory.routes().values().stream().allMatch(Route::continuousUpright);if(continuous){require(guide.has("mode")&&guide.get("mode").getAsString().equals("continuous_upright")&&guide.get("source_sha256").getAsString().equals(NervOuterCarrierGuideR52.SOURCE_SHA)&&guide.get("paths_sha256").getAsString().matches("[0-9a-f]{64}")&&!guide.get("paths_sha256").getAsString().equals("0".repeat(64))&&!guide.has("dock_foundations")&&!guide.has("dock_source_sha256"),"Actual explicit continuous captured model/paths source required; old Dock cannot be reused");owner.continuousGuidesR52=true;owner.continuousGuidePathsShaR52=guide.get("paths_sha256").getAsString();}else require(guide.get("source_sha256").getAsString().equals(NervFootGuideRigR52.SOURCE_SHA)&&guide.get("paths_sha256").getAsString().equals(NervFixedFootGuidesR52.SOURCE_SHA),"Actual selected engineered foot-guide source required");owner.groundGuidesDeclared=!NervR50CarrierModeR53.enabled();if(!continuous&&guide.has("dock_foundations")){require(guide.has("dock_source_sha256")&&guide.get("dock_source_sha256").getAsString().equals(NervFootGuideDockR52.SOURCE_SHA),"Actual fixed turn station source required");var foundation=new HashMap<String,Double>();for(var rawTop:guide.getAsJsonArray("dock_foundations")){var row=rawTop.getAsJsonObject();String id=row.get("leg").getAsString();double top=row.get("foundation_top_m").getAsDouble();require(Double.isFinite(top)&&directory.leg(id)!=null&&directory.leg(id).motion()==Motion.FOOT_BEARING_TURN&&id.equals(NervFootGuideStationR52.canonicalLeg(id))&&foundation.putIfAbsent(id,top)==null,"Explicit Root canonical station foundation required");}owner.dockFoundationsR52=Map.copyOf(foundation);}else require(continuous||!status.equals("installed"),"Installed legacy turn stations need explicit Root dock_foundations");var controllers=new HashMap<Integer,UUID>();for(var raw:root.getAsJsonArray("units")){var u=raw.getAsJsonObject();if(!u.has("carrier_controller")){require(!status.equals("installed"),"Installed original full carrier requires its independent actual controller");continue;}var c=u.getAsJsonObject("carrier_controller");int v=u.get("variant").getAsInt();var id=uuid(c,"id");require(c.get("source_sha256").getAsString().equals(NervOriginalCarrierR52.SOURCE_SHA)&&id.equals(NervOriginalCarrierR52.proposedIdentityR52(owner.epoch,uuid(u,"eva")))&&controllers.putIfAbsent(v,id)==null,"Actual original single-carrier source/identity required");}owner.carrierControllers=Map.copyOf(controllers);}else require(!status.equals("installed"),"Installed foot-driven plant requires explicit ground_guides source");
        var staff=new ArrayList<StaffBinding>();var identities=new HashSet<UUID>();var posts=new HashSet<String>();if(root.has("staff"))for(var raw:root.getAsJsonArray("staff")){var row=raw.getAsJsonObject();var id=uuid(row,"original_uuid");String post=row.get("id").getAsString();require(identities.add(id)&&posts.add(post),"Duplicate original staff identity/post");var station=new NervStaffDirector.Station(post,row.get("name").getAsString(),row.get("role").getAsString(),row.get("skin").getAsString(),position(row.getAsJsonArray("feet")),row.get("yaw").getAsFloat());staff.add(new StaffBinding(id,station,fixedCells(row.getAsJsonArray("support"))));}owner.staff=List.copyOf(staff);return owner;
    }
    private static SiloHatchMechanism.Spec siloSpec(JsonObject o){return new SiloHatchMechanism.Spec(o.get("opening_x").getAsFloat(),o.get("opening_z").getAsFloat(),o.get("open_ticks").getAsInt(),o.get("close_ticks").getAsInt(),o.has("separation_sign")?o.get("separation_sign").getAsInt():1,o.has("beam_bottom")?number(o,"beam_bottom"):-2.01,o.has("service_column_ports")&&o.get("service_column_ports").getAsBoolean(),o.has("upright_guide_ports")&&o.get("upright_guide_ports").getAsBoolean(),o.has("service_gantry_yaw_degrees")?o.get("service_gantry_yaw_degrees").getAsInt():0,o.has("upright_guide_early_variant")?o.get("upright_guide_early_variant").getAsInt():-1);}
    private static void validateEarlyGuideRoleR53(String resource,int variant,SiloHatchMechanism.Spec spec)
    {if(spec!=null&&spec.uprightGuideEarlyVariant()>=0)require(spec.uprightGuideEarlyVariant()==variant&&resource.equals("bank_3_upper_lane_"+(2-variant)),"Early guide fitting requires the explicit same-unit bank3 upper role");}
    private static NervHangarGateGeometryR52.Spec hangarSpec(JsonObject g){var s=g.getAsJsonObject("hangar_stack");NervHangarGateGeometryR52.BottomSeal seal=null;if(s.has("floor_seal")){var f=s.getAsJsonObject("floor_seal");var rows=f.getAsJsonArray("closed_boxes");require(rows!=null&&!rows.isEmpty()&&rows.size()<=512,"Finite actual wet-floor seal boxes required");var boxes=new ArrayList<NervHangarGateGeometryR52.SealBox>();for(var raw:rows){var r=raw.getAsJsonArray();require(r.size()==6,"Explicit actual floor-seal box required");boxes.add(new NervHangarGateGeometryR52.SealBox(r.get(0).getAsDouble(),r.get(1).getAsDouble(),r.get(2).getAsDouble(),r.get(3).getAsDouble(),r.get(4).getAsDouble(),r.get(5).getAsDouble()));}seal=new NervHangarGateGeometryR52.BottomSeal(boxes,f.get("drop_m").getAsDouble(),f.get("retreat_local_z_m").getAsDouble(),f.has("version")?f.get("version").getAsInt():1,f.has("retained_box_count")?f.get("retained_box_count").getAsInt():0);}return new NervHangarGateGeometryR52.Spec(g.get("width").getAsFloat(),g.get("height").getAsFloat(),s.get("open_ticks").getAsInt(),s.get("close_ticks").getAsInt(),s.has("depth_direction")?s.get("depth_direction").getAsInt():1,seal);}
    private static Visual visual(JsonObject o){return new Visual(uuid(o,"id"),frame(o.getAsJsonObject("frame")),fixedCells(o.getAsJsonArray("supports")));}
    private static List<FixedCell> fixedCells(JsonArray a){var out=new ArrayList<FixedCell>();var own=new HashSet<BlockPos>();for(var raw:a){var r=raw.getAsJsonObject();var p=position(r.getAsJsonArray("position"));require(own.add(p),"Duplicate physical cell");out.add(new FixedCell(p,state(r.get("state").getAsString())));}return List.copyOf(out);}
    private static List<List<FixedCell>> bridgeStates(JsonArray a){var result=new ArrayList<List<FixedCell>>();for(var state:a)result.add(fixedCells(state.getAsJsonArray()));validateBridgeStates(result);return List.copyOf(result);}
    private static List<List<Cell>> steps(JsonArray a){var out=new ArrayList<List<Cell>>();var own=new HashSet<BlockPos>();for(var raw:a){var cells=new ArrayList<Cell>();for(var v:raw.getAsJsonArray()){var r=v.getAsJsonObject();var p=position(r.getAsJsonArray("position"));require(own.add(p),"A moving physical cell cannot belong to two phase members");var closed=state(r.get("closed").getAsString());var open=state(r.get("open").getAsString());require(!closed.equals(open),"An unchanged cell is not a moving component");cells.add(new Cell(p,closed,open));}require(!cells.isEmpty(),"No placeholder phase members");out.add(List.copyOf(cells));}return List.copyOf(out);}
    private static final Map<String,BlockState> PARSED_STATES=new HashMap<>();
    private static BlockState state(String s){try{return PARSED_STATES.computeIfAbsent(s,key->{try{return BlockStateParser.parseForBlock(BuiltInRegistries.BLOCK.asLookup(),key,false).blockState();}catch(Exception bad){throw new IllegalArgumentException("Unknown actual block state "+key,bad);}});}catch(Exception bad){throw new IllegalArgumentException("Unknown actual block state "+s,bad);}}
    private static BlockPos position(JsonArray a){require(a.size()==3,"Actual integral cell required");return new BlockPos(a.get(0).getAsBigDecimal().intValueExact(),a.get(1).getAsBigDecimal().intValueExact(),a.get(2).getAsBigDecimal().intValueExact());}
    private static List<Vec3> points(JsonArray a){var out=new ArrayList<Vec3>();for(var p:a)out.add(vector(p.getAsJsonArray()));return List.copyOf(out);}
    private static Vec3 vector(JsonArray a){require(a.size()==3,"Actual finite vector required");var p=new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());require(Double.isFinite(p.lengthSqr()),"Nonfinite actual vector");return p;}
    private static RigidTransform frame(JsonObject o){var p=vector(o.getAsJsonArray("position"));var q=o.getAsJsonArray("quaternion");require(q.size()==4,"Measured unit quaternion required");float x=q.get(0).getAsFloat(),y=q.get(1).getAsFloat(),z=q.get(2).getAsFloat(),w=q.get(3).getAsFloat();double n=(double)x*x+(double)y*y+(double)z*z+(double)w*w;require(Double.isFinite(n)&&Math.abs(n-1)<.0001,"Measured unit quaternion required, not normalization fallback");return new RigidTransform(p,x,y,z,w);}
    private static double number(JsonObject o,String n){double x=o.get(n).getAsDouble();require(Double.isFinite(x),"Explicit finite machine value required");return x;}
    private static UUID uuid(JsonObject o,String n){return UUID.fromString(o.get(n).getAsString());}
    private record CageDomainKeyR57(RigidTransform frame,NervServiceFootDriveR52.Spec drive){}
    private final Map<CageDomainKeyR57,AABB> cageDomainsR57=new HashMap<>();
    /** Complete source controls enclose pure translation phases; this is only a query broadphase. */
    static AABB sourceCageDomainR57(RigidTransform frame,NervServiceFootDriveR52.Spec drive)throws java.io.IOException {
        double radius=NervPlantMotionR52.cageCollisionRadiusR57();var domain=NervRigidMeshSweepR52.transformed(new AABB(-radius,-radius,-radius,radius,radius,radius),frame);
        // Steel moves on separate monotone Y and X phases. Each straight rope
        // has its complete extent at the declared .3/.45/.85 phase control.
        for(double progress:new double[]{0,.3,.375,.45,.85,1})for(var box:NervLowerFrameR52.collisionBoxesR57(frame,progress))domain=domain.minmax(box);
        // Bridge p<=.8 is pure Y with fixed Z=1.5; p>=.8 is pure Z
        // with fixed Y=0. Fixed rotation maps their endpoint hulls affinely.
        if(drive!=null)for(double bridge:new double[]{0,.8,1})for(var piece:NervServiceFootDriveR52.pieces(drive,bridge))domain=domain.minmax(piece.mesh().envelope(piece.frame(),piece.frame()));
        return domain;
    }
    private AABB cageDomainR57(RigidTransform frame,NervServiceFootDriveR52.Spec drive)throws java.io.IOException {
        var key=new CageDomainKeyR57(frame,drive);var domain=cageDomainsR57.get(key);if(domain==null){domain=sourceCageDomainR57(frame,drive);cageDomainsR57.put(key,domain);}return domain;
    }
    public List<net.minecraft.world.phys.shapes.VoxelShape> actualCageCollisions(ServerLevel l,Entity actor,AABB query)
    {if(!commissioned||actor instanceof EvaUnit01Entity||actor instanceof NervCarrierPlatformEntity)return List.of();var result=new ArrayList<net.minecraft.world.phys.shapes.VoxelShape>();for(var p:units.values()){var actual=gantry(l,p);if(actual==null||!actual.hasDeclaredMachineFrameR52()||actual.position().distanceToSqr(p.gantry().frame().translation())>1e-8)continue;try{if(!cageDomainR57(p.gantry().frame(),actual.declaredServiceFootDriveR52()).intersects(query))continue;}catch(java.io.IOException missing){throw new IllegalStateException("Declared cage domain source unavailable",missing);}result.addAll(NervPlantMotionR52.actualCollisionMembers(p.variant(),p.gantry().frame(),actual.getRestraintProgress(),actual.lowerFrameProgressR52(1),query));try{result.addAll(NervServiceFootDriveR52.collisions(actual,1,query));}catch(java.io.IOException missing){throw new IllegalStateException("Declared service drive source unavailable",missing);}}return List.copyOf(result);}
    @Override public List<NervStaffDirector.Station> originalStaffRoster(ServerLevel l){return staff.stream().map(StaffBinding::station).toList();}
    @Override public void maintainOriginalStaff(ServerLevel l)
    {for(var p:staff)if(l.getEntity(p.original()) instanceof NervStaffEntity actor&&actor.memberId().equals(p.station().id())&&fixed(l,p.support())){ /* Original actor AI/home/identity remain authoritative. */ }}
    private static final TicketType<net.minecraft.world.level.ChunkPos> ORIGINAL_PERSONNEL_TICKET_R52=TicketType.create("r52_original_personnel",Comparator.comparingLong(net.minecraft.world.level.ChunkPos::toLong),100);
    @Override public void retainOriginalPilotSections(ServerLevel l,int v)
    {var p=units.get(v);if(p==null)return;var cells=new ArrayList<Vec3>(p.boardPath());cells.addAll(p.returnPath());cells.add(p.standby());cells.add(p.dock().translation());for(var at:cells){var chunk=new net.minecraft.world.level.ChunkPos(BlockPos.containing(at));l.getChunkSource().addRegionTicket(ORIGINAL_PERSONNEL_TICKET_R52,chunk,2,chunk);}}
    private static void require(boolean valid,String why){if(!valid)throw new IllegalArgumentException(why);}
}

package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.*;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.AABB;
import com.projectseele.world.NervRouteDirectoryR52.*;
import com.projectseele.world.NervRouteReservationsR52.*;
import com.projectseele.world.TransportMembershipR52.Kind;

/** Actual loaded-world identity/rail/gate/space/collision queries; never generates cells or actors. */
public final class NervRouteNativeR52 implements NativeAccess
{
    public enum Preparation { WAITING,READY,FAULT }
    public record Sweep(Set<UUID> assembly,List<AABB> volumes,FullAssemblyGeometryR52.CheckedAssemblySweep triangles)
    {
        public Sweep(Set<UUID> assembly,List<AABB> volumes){this(assembly,volumes,null);}
        public Sweep(FullAssemblyGeometryR52.CheckedAssemblySweep checked){this(checked.originalIds(),checked.envelopes(),checked);}
        public Sweep{assembly=Set.copyOf(assembly);volumes=List.copyOf(volumes);if(triangles!=null&&(!assembly.equals(triangles.originalIds())||!volumes.equals(triangles.envelopes())))throw new IllegalArgumentException("Original concrete sweep bounds/identity mismatch");}
    }
    /** No stock yaw-only/carrier or hip-pivot fallback satisfies this contract.
     * Root must provide the sole full rigid EVA/plug/pilot owner, including
     * actual pose comparison, full geometry and synchronized applied frames. */
    public interface AssemblyOwner
    {
        boolean fullRigidFramesReady(ServerLevel level,NervRouteDirectoryR52 directory);
        default boolean mechanicalRailReadyR52(ServerLevel level,NervMechanicalRailBindingR52.Spec rail,List<Cell> foundations){return false;}
        boolean restoreOriginalPreparation(ServerLevel level,Original original,CompoundTag ownerData);
        default NervOwnerPlacementR52.Proof finishingAssemblyPlacement(ServerLevel level,Original original,CompoundTag ownerData){return null;}
        default RigidTransform finishingReferenceFrameR52(ServerLevel level,Original original,CompoundTag ownerData,RigidTransform directoryEndpoint){return directoryEndpoint;}
        default boolean restoreFinishingOriginal(ServerLevel level,Original original,CompoundTag ownerData){return false;}
        default boolean originalPersonnelBindingsReady(ServerLevel level){return false;}
        default TrainingPilotDirector.ActionResult requestOriginalPilot(ServerLevel level,int variant,String operation){return new TrainingPilotDirector.ActionResult(false,"R52 原座椅/电话/人员通道绑定尚未就绪。");}
        default boolean routeOriginalPilot(ServerLevel level,TrainingPilotEntity pilot,String operation){return false;}
        default boolean atOriginalPilotStandby(ServerLevel level,int variant){return false;}
        Preparation prepareOriginal(ServerLevel level,Original original,CompoundTag ownerData);
        boolean prepareLeg(ServerLevel level,Original original,Route route,Leg leg,CompoundTag ownerData);
        default boolean prepareBankHeadsR53(ServerLevel level,Original original,Route route,UUID task,CompoundTag ownerData){return false;}
        default boolean prepareBankForRetargetR53(ServerLevel level,Original original,Route route,UUID task,CompoundTag ownerData){return false;}
        default boolean prepareContinuousRouteR52(ServerLevel level,Original original,Route route,CompoundTag ownerData){return false;}
        default List<DirectoryTrajectoryR52> continuousRoutePathsR52(ServerLevel level,Original original,Route route,CompoundTag ownerData){return List.of();}
        default boolean rebindStoppedContinuousR52(ServerLevel level,Original original,CompoundTag ownerData){return false;}
        default boolean preflightContinuousCarrierR52(ServerLevel level,Original original,Route route,List<DirectoryTrajectoryR52> paths,CompoundTag ownerData){return false;}
        default Sweep sweptContinuousAssemblyR52(ServerLevel level,Original original,List<DirectoryTrajectoryR52> paths,CompoundTag ownerData){return null;}
        default boolean applyCheckedContinuousR52(ServerLevel level,CheckedContinuousTraversalR52 proof,CompoundTag ownerData){return false;}
        FootSupportFrameR52.Binding originalBinding(ServerLevel level,Original original,CompoundTag ownerData);
        net.minecraft.world.phys.Vec3 actualFootBearingCentre(ServerLevel level,Original original,CompoundTag ownerData);
        /** Classify through Root's actual bound receiver domains, never a
         * historical outgoing route or an invented universal Y threshold. */
        default Region actualRecoveryRegion(ServerLevel level,Original original,CompoundTag ownerData){return null;}
        /** Use EvaMechanicalFrameR52.frozenLocalPose, then actual model-metre
         * body/capsule/passenger geometry under proposed evaRoot once. An
         * already carrier-turned EvaBodyPose.sample would rotate it twice. */
        Sweep sweptAssembly(ServerLevel level,Original original,FootSupportFrameR52.Sample from,FootSupportFrameR52.Sample to,CompoundTag ownerData);
        /** The concrete full-surface owner receives the real directory curve.
         * Existing conservative owners retain their two-frame contract. */
        default Sweep sweptAssembly(ServerLevel level,Original original,DirectoryTrajectoryR52 trajectory,CompoundTag ownerData)
        {return sweptAssembly(level,original,trajectory.sample(0),trajectory.sample(1),ownerData);}
        boolean actualFrameMatches(ServerLevel level,Original original,FootSupportFrameR52.Sample frame,CompoundTag ownerData);
        boolean applyVerifiedWholeAssembly(ServerLevel level,Original original,FootSupportFrameR52.Sample from,FootSupportFrameR52.Sample to,CompoundTag ownerData);
        boolean approachReachable(ServerLevel level,Original original,Port port,Route reverse,CompoundTag ownerData);
        boolean finishOriginal(ServerLevel level,Original original,boolean returning,CompoundTag ownerData);
        void brakeOriginalInPlace(ServerLevel level,Original original,CompoundTag ownerData);
    }
    public record Cell(BlockPos position,String state){}
    public record Binding(String resource,String component,UUID entity,String expectedType,List<Cell> cells,List<AABB> spaces,float requiredOpen,NervMechanicalRailBindingR52.Spec mechanicalRail)
    {public Binding(String resource,String component,UUID entity,String expectedType,List<Cell> cells,List<AABB> spaces,float requiredOpen){this(resource,component,entity,expectedType,cells,spaces,requiredOpen,null);}public Binding{cells=List.copyOf(cells);spaces=List.copyOf(spaces);}}
    private final ServerLevel level;
    private final NervRouteDirectoryR52 directory;
    private final Map<String,Binding> bindings;
    private final AssemblyOwner owner;
    private CompoundTag ownerData=new CompoundTag();
    private Kind currentKind=Kind.OCCUPIED;
    public NervRouteNativeR52(ServerLevel level,NervRouteDirectoryR52 directory,Map<String,Binding> bindings,AssemblyOwner owner)
    {this.level=level;this.directory=directory;this.bindings=directory.dynamicSpacesR52().bindings(Map.copyOf(bindings));this.owner=Objects.requireNonNull(owner);}
    public void ownerData(CompoundTag data){ownerData=data;currentKind=data.contains("AssemblyKindR52")?Kind.valueOf(data.getString("AssemblyKindR52")):Kind.OCCUPIED;}
    public boolean originalIdentitySet(Original original)
    {
        if(currentKind==Kind.HULL_ONLY_RECOVERY)return hullOnlyOriginal(original);
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(original.variant()).orElse(null);
        return fleet!=null&&fleet.canonicalId().equals(original.eva())&&original.plug().equals(fleet.entryPlugId())
                &&level.getEntity(original.eva()) instanceof EvaUnit01Entity eva&&eva.getUnitVariant()==original.variant()
                &&level.getEntity(original.plug()) instanceof EntryPlugCarrierEntity plug&&plug.getAssignedVariant()==original.variant()
                &&level.getEntity(original.pilot()) instanceof LivingEntity pilot&&pilot.isAlive();
    }
    public boolean sameOriginalAssembly(Original original)
    {return currentKind==Kind.HULL_ONLY_RECOVERY?hullOnlyOriginal(original):occupiedOriginalAssembly(original);}
    @Override public boolean sameAssembly(Original original,Kind kind)
    {return kind==Kind.HULL_ONLY_RECOVERY?hullOnlyOriginal(original):occupiedOriginalAssembly(original);}
    private boolean hullOnlyOriginal(Original original)
    {
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(original.variant()).orElse(null);
        if(fleet==null||!fleet.canonicalId().equals(original.eva())||!original.plug().equals(fleet.entryPlugId())||!level.dimension().location().toString().equals(original.dimension())
                ||!(level.getEntity(original.eva()) instanceof EvaUnit01Entity eva)||eva.isExperimentalUnit()||eva.getUnitVariant()!=original.variant()||!eva.isAlive()
                ||eva.getPilotEntity()!=null||eva.isEntryPlugInserted()||!eva.getPassengers().isEmpty()||!EntryPlugEjectionR48.originalFieldEjection(level,original.variant(),eva,original.pilot()))return false;
        var data=eva.getPersistentData();return TransportMembershipR52.hullRecoveryAdmission(original,data,Set.copyOf(eva.getPassengers().stream().map(Entity::getUUID).toList()),eva.isEntryPlugInserted(),EvaShutdownR30.disabled(eva))
                &&AutoSortieR32.missionToken(level).equals(original.mission());
    }
    private boolean occupiedOriginalAssembly(Original original)
    {
        if(!level.dimension().location().toString().equals(original.dimension()))return false;
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(original.variant()).orElse(null);
        Entity a=level.getEntity(original.eva()),p=level.getEntity(original.plug()),r=level.getEntity(original.pilot());
        if(fleet==null||!fleet.canonicalId().equals(original.eva())||!original.plug().equals(fleet.entryPlugId())
                ||!(a instanceof EvaUnit01Entity eva)||eva.isExperimentalUnit()||eva.getUnitVariant()!=original.variant()||!eva.isAlive()
                ||!(p instanceof EntryPlugCarrierEntity plug)||!plug.isAlive()||plug.getAssignedVariant()!=original.variant()
                ||!(r instanceof LivingEntity)||!r.isAlive()||plug.getFirstPassenger()!=r||r.getVehicle()!=plug)return false;
        if(plug.getLinkedEva()!=null&&plug.getLinkedEva()!=eva||eva.getPilotEntity()!=null&&eva.getPilotEntity()!=r)return false;
        if(!AutoSortieR32.missionToken(level).equals(original.mission()))return false;
        var tag=eva.getPersistentData();if(tag.hasUUID("R32SortieCommander")&&!tag.getUUID("R32SortieCommander").equals(original.owner()))return false;
        if(AutoSortieR32.cancellationCurrentR45(tag.getBoolean("R32AutoCancelled"),tag.getString("R43AutoMission"),original.mission()))return false;
        if(r instanceof TrainingPilotEntity pilot&&original.mission().isEmpty())
            return NervRouteRuntimeR52.manualOriginalNpcR60(level,directory,owner,original,eva,pilot);
        if(r instanceof TrainingPilotEntity)return AutoSortieR32.assignedPilotR45(level,original.variant(),r)
                &&TvCampaignSavedData.get(level).sorties.get(original.variant()).commander.equals(original.owner());
        return r instanceof ServerPlayer player&&!player.isSpectator()&&player.getUUID().equals(original.owner())&&NervStaffDialogue.authorized(player);
    }
    public boolean resourceReady(String id,boolean openGate)
    {
        var resource=directory.resource(id);var binding=bindings.get(id);if(resource==null||binding==null||!resource.component().equals(binding.component()))return false;
        for(var cell:binding.cells())
        {
            BlockPos pos=cell.position();if(level.getChunkSource().getChunkNow(pos.getX()>>4,pos.getZ()>>4)==null
                    ||!BlockStateParser.serialize(level.getBlockState(pos)).equals(cell.state())
                    ||(resource.kind()==ResourceKind.RAIL||resource.kind()==ResourceKind.SUPPORT)&&level.getBlockState(pos).isAir())return false;
        }
        if(binding.mechanicalRail()!=null&&(!NervMechanicalRailBindingR52.ready(level,directory,binding.mechanicalRail())||!owner.mechanicalRailReadyR52(level,binding.mechanicalRail(),binding.cells())))return false;
        if(binding.entity()!=null)
        {
            Entity entity=level.getEntity(binding.entity());if(entity==null||!entity.isAlive()
                    ||!BuiltInRegistries.ENTITY_TYPE.getKey(entity.getType()).toString().equals(binding.expectedType()))return false;
            if(openGate)
            {
                // Read the current saved Open channel. Silo's display accessor
                // interpolates client-only fields even when invoked on server.
                if(entity instanceof NervHangarDoorEntity door){if(door.getOpenProgress(1)<binding.requiredOpen())return false;}
                else if(entity instanceof NervSiloDoorEntity door){if(door.actualOpenProgressR52()<binding.requiredOpen())return false;}
                else{CompoundTag actual=entity.saveWithoutId(new CompoundTag());if(!actual.contains("Open",net.minecraft.nbt.Tag.TAG_FLOAT)||actual.getFloat("Open")<binding.requiredOpen())return false;}
            }
        }
        return true;
    }
    /** Minted only by real loaded resources and complete immutable source-curve checks. */
    public static final class CheckedContinuousTraversalR52
    {
        private final NervRouteNativeR52 access;private final Original original;private final Route route;private final Kind kind;private final List<DirectoryTrajectoryR52> paths;private final long at;private boolean committed;
        private CheckedContinuousTraversalR52(NervRouteNativeR52 access,Original original,Route route,List<DirectoryTrajectoryR52> paths){this.access=access;this.original=original;this.route=route;this.kind=access.currentKind;this.paths=List.copyOf(paths);at=access.level.getGameTime();}
        public Original original(){return original;}public Route route(){return route;}public Kind kind(){return kind;}public List<DirectoryTrajectoryR52> paths(){return paths;}public long checkedAt(){return at;}
        public FootSupportFrameR52.Sample from(){return paths.get(0).sample(0);}public FootSupportFrameR52.Sample to(){return paths.get(paths.size()-1).sample(1);}
        public boolean current(ServerLevel level){return !committed&&level==access.level&&level.getGameTime()==at&&access.currentKind==kind&&access.sameAssembly(original,kind);}
        public boolean recordCommittedR52(ServerLevel level,CompoundTag data){if(!current(level)||!access.owner.actualFrameMatches(level,original,to(),data))return false;committed=true;return true;}
        public boolean committed(){return committed;}
    }
    public CheckedContinuousTraversalR52 checkContinuousR52(Original original,Route route,List<DirectoryTrajectoryR52> paths)
    {
        if(route==null||!route.continuousUpright()||paths==null||paths.isEmpty()||paths.size()>2048||!sameAssembly(original,currentKind)||currentKind==Kind.HULL_ONLY_RECOVERY&&!route.recovery())return null;
        if(currentKind==Kind.OCCUPIED&&!EntryPlugDirector.hasLaunchLock(level,original.variant(),(EvaUnit01Entity)level.getEntity(original.eva())))return null;
        var ids=new HashSet<String>();for(var path:paths){if(!path.directory().fingerprint().equals(directory.fingerprint())||!route.legs().contains(path.leg().id())||path.leg().motion()==Motion.FOOT_BEARING_TURN)return null;ids.addAll(path.leg().resources());}
        for(String id:ids)if(!resourceReady(id,directory.resource(id).kind()==ResourceKind.DOOR))return null;
        try{var sweep=owner.sweptContinuousAssemblyR52(level,original,paths,ownerData);var own=TransportMembershipR52.members(original,currentKind);if(sweep==null||sweep.triangles()==null||!sweep.assembly().equals(own)||!sweep.triangles().matchesSlices(original,paths)||!sweep.triangles().matchesSamples(paths.get(0).sample(0),paths.get(paths.size()-1).sample(1)))return null;
            var spaces=new ArrayList<AABB>();for(String id:ids)if(directory.resource(id).kind()==ResourceKind.SPACE){var bound=bindings.get(id);if(bound==null)return null;spaces.addAll(bound.spaces());}
            for(var box:sweep.volumes()){if(!coveredByDeclaredSpacesR52(box,spaces))return null;for(int x=(int)Math.floor(box.minX)>>4;x<=((int)Math.floor(box.maxX)>>4);x++)for(int z=(int)Math.floor(box.minZ)>>4;z<=((int)Math.floor(box.maxZ)>>4);z++)if(level.getChunkSource().getChunkNow(x,z)==null)return null;}
            if(!sweep.triangles().clear(level,level.getEntity(original.eva())))return null;return new CheckedContinuousTraversalR52(this,original,route,paths);
        }catch(IllegalArgumentException|IllegalStateException unavailable){return null;}
    }
    public boolean canTraverse(Original original,Route route,Leg leg,double fromFraction,double toFraction)
    {
        if(!sameOriginalAssembly(original)||currentKind==Kind.HULL_ONLY_RECOVERY&&!route.recovery()
                ||currentKind==Kind.OCCUPIED&&!EntryPlugDirector.hasLaunchLock(level,original.variant(),(EvaUnit01Entity)level.getEntity(original.eva())))return false;
        for(String id:leg.resources())if(!resourceReady(id,toFraction>fromFraction&&directory.resource(id).kind()==ResourceKind.DOOR))return false;
        try
        {
            var binding=owner.originalBinding(level,original,ownerData);if(binding==null)return false;
            var from=directory.sample(leg,fromFraction,binding);
            var to=directory.sample(leg,toFraction,binding);
            if(!owner.actualFrameMatches(level,original,from,ownerData))return false;
            return clearActualSweep(original,leg,fromFraction,toFraction,owner.sweptAssembly(level,original,new DirectoryTrajectoryR52(directory,leg,binding,fromFraction,toFraction),ownerData));
        }
        catch(IllegalArgumentException|IllegalStateException invalid){return false;}
    }
    private boolean clearActualSweep(Original original,Leg leg,double fromFraction,double toFraction,Sweep sweep)
    {
        Set<UUID> actual=TransportMembershipR52.members(original,currentKind);if(sweep==null||!sweep.assembly().equals(actual)||sweep.volumes().isEmpty())return false;
        if(sweep.triangles()!=null)
        {
            var binding=owner.originalBinding(level,original,ownerData);if(binding==null||!sweep.triangles().matches(original,directory,leg,fromFraction,toFraction)
                    ||!sweep.triangles().matchesSamples(directory.sample(leg,fromFraction,binding),directory.sample(leg,toFraction,binding)))return false;
        }
        var spaces=new ArrayList<AABB>();for(String id:leg.occupancy())spaces.addAll(bindings.get(id).spaces());
        Entity eva=level.getEntity(original.eva());
        for(AABB box:sweep.volumes())
        {
            if(!coveredByDeclaredSpacesR52(box,spaces))return false;
            for(int x=(int)Math.floor(box.minX)>>4;x<=((int)Math.floor(box.maxX)>>4);x++)for(int z=(int)Math.floor(box.minZ)>>4;z<=((int)Math.floor(box.maxZ)>>4);z++)
                if(level.getChunkSource().getChunkNow(x,z)==null)return false;
            if(sweep.triangles()==null)
            {
                if(level.getBlockCollisions(eva,box).iterator().hasNext())return false;
                if(!level.getEntities((Entity)null,box,e->!actual.contains(e.getUUID())&&e.isAlive()&&(e instanceof LivingEntity||e.canBeCollidedWith())).isEmpty())return false;
            }
        }
        return sweep.triangles()==null||sweep.triangles().clear(level,eva);
    }
    public boolean canRestore(Original original,Route route,int index,double fraction)
    {return canTraverse(original,route,directory.leg(route.legs().get(index)),fraction,fraction);}
    @Override public boolean canTraverseAssembly(Original original,Kind kind,Route route,Leg leg,double from,double to)
    {return kind==currentKind&&canTraverse(original,route,leg,from,to);}
    @Override public boolean canRestoreAssembly(Original original,Kind kind,Route route,int leg,double fraction)
    {return kind==currentKind&&canRestore(original,route,leg,fraction);}
    public boolean finishingPlacementClear(Original original,Route route,int index,double fraction)
    {
        if(!originalIdentitySet(original)||!owner.restoreFinishingOriginal(level,original,ownerData))return false;
        try{var binding=owner.originalBinding(level,original,ownerData);if(binding==null)return false;var leg=directory.leg(route.legs().get(index));var placement=owner.finishingAssemblyPlacement(level,original,ownerData);if(placement!=null){if(!placement.matches(original,currentKind,owner.finishingReferenceFrameR52(level,original,ownerData,directory.sample(leg,fraction,binding).evaRoot())))return false;var spaces=new ArrayList<AABB>();for(String id:leg.occupancy())spaces.addAll(bindings.get(id).spaces());for(var box:placement.envelopes()){if(!coveredByDeclaredSpacesR52(box,spaces))return false;for(int x=(int)Math.floor(box.minX)>>4;x<=((int)Math.floor(box.maxX)>>4);x++)for(int z=(int)Math.floor(box.minZ)>>4;z<=((int)Math.floor(box.maxZ)>>4);z++)if(level.getChunkSource().getChunkNow(x,z)==null)return false;}return placement.clear(level);}return clearActualSweep(original,leg,fraction,fraction,owner.sweptAssembly(level,original,new DirectoryTrajectoryR52(directory,leg,binding,fraction,fraction),ownerData));}
        catch(IllegalArgumentException|IllegalStateException invalid){return false;}
    }
    static boolean coveredByDeclaredSpacesR52(AABB box,List<AABB> spaces)
    {return finite(box)&&NervAirspaceCoverageR52.covered(box,spaces);}
    private static boolean finite(AABB box){return Double.isFinite(box.minX)&&Double.isFinite(box.minY)&&Double.isFinite(box.minZ)&&Double.isFinite(box.maxX)&&Double.isFinite(box.maxY)&&Double.isFinite(box.maxZ)&&box.maxX>box.minX&&box.maxY>box.minY&&box.maxZ>box.minZ;}
    public static Map<String,Binding> parseBindings(JsonArray rows,NervRouteDirectoryR52 directory)
    {
        var result=new LinkedHashMap<String,Binding>();for(var value:rows)
        {
            var o=value.getAsJsonObject();String id=o.get("resource").getAsString();var resource=directory.resource(id);if(resource==null)throw new IllegalArgumentException("Unknown native resource");
            var cells=new ArrayList<Cell>();if(o.has("cells"))for(var raw:o.getAsJsonArray("cells")){var c=raw.getAsJsonObject();var p=c.getAsJsonArray("position");cells.add(new Cell(new BlockPos(p.get(0).getAsBigDecimal().intValueExact(),p.get(1).getAsBigDecimal().intValueExact(),p.get(2).getAsBigDecimal().intValueExact()),c.get("state").getAsString()));}
            NervMechanicalRailBindingR52.Spec mechanical=null;
            if(o.has("mechanical_rail")){if(resource.kind()!=ResourceKind.RAIL||o.has("entity_uuid")||o.has("spaces")||o.has("required_open"))throw new IllegalArgumentException("Mechanical rail only accepts its actual finite foundation cells");mechanical=NervMechanicalRailBindingR52.parse(o.getAsJsonObject("mechanical_rail"),id,directory,cells);}
            if(resource.kind()==ResourceKind.RAIL&&mechanical==null)
            {
                if(cells.isEmpty())throw new IllegalArgumentException("Real rail cell chain required");var distinct=new HashSet<BlockPos>();
                for(int i=0;i<cells.size();i++){var p=cells.get(i).position();if(!distinct.add(p))throw new IllegalArgumentException("Duplicate rail cell");if(i>0){var before=cells.get(i-1).position();if(Math.abs(p.getX()-before.getX())>1||Math.abs(p.getY()-before.getY())>1||Math.abs(p.getZ()-before.getZ())>1)throw new IllegalArgumentException("Disconnected explicit rail cell chain");}}
            }
            var spaces=new ArrayList<AABB>();if(o.has("spaces"))for(var raw:o.getAsJsonArray("spaces")){var a=raw.getAsJsonArray();if(a.size()!=6)throw new IllegalArgumentException("Explicit space bounds required");double x=a.get(0).getAsDouble(),y=a.get(1).getAsDouble(),z=a.get(2).getAsDouble(),xx=a.get(3).getAsDouble(),yy=a.get(4).getAsDouble(),zz=a.get(5).getAsDouble();if(!(xx>x&&yy>y&&zz>z))throw new IllegalArgumentException("Ordered positive space bounds required");var box=new AABB(x,y,z,xx,yy,zz);if(!finite(box))throw new IllegalArgumentException("Invalid space bounds");spaces.add(box);}
            UUID entity=o.has("entity_uuid")?UUID.fromString(o.get("entity_uuid").getAsString()):null;String type=o.has("expected_type")?o.get("expected_type").getAsString():"";
            float open=resource.kind()==ResourceKind.DOOR?o.get("required_open").getAsFloat():0;
            if(entity!=null&&type.isBlank()||resource.kind()==ResourceKind.SPACE&&spaces.isEmpty()||resource.kind()==ResourceKind.SUPPORT&&entity==null&&cells.isEmpty()
                    ||resource.kind()==ResourceKind.DOOR&&(entity==null||type.isBlank()||!Float.isFinite(open)||open<=0||open>1))throw new IllegalArgumentException("Actual support/door/space binding required");
            var b=new Binding(id,o.get("component").getAsString(),entity,type,cells,spaces,open,mechanical);if(!b.component().equals(resource.component())||result.putIfAbsent(id,b)!=null)throw new IllegalArgumentException("Native resource/provider mismatch or duplicate");
            if(!directory.dynamicSpacesR52().domains().isEmpty()&&resource.kind()==ResourceKind.SPACE&&(spaces.size()!=1||!spaces.get(0).equals(NervDynamicAirspaceR52.canonicalBox(id))))throw new IllegalArgumentException("Static ground and dynamic air must bind the identical canonical32m SPACE box");
        }
        if(!result.keySet().equals(directory.declaredResources().keySet()))throw new IllegalArgumentException("Complete real native resource binding set required");
        var actors=new HashSet<UUID>();var rails=new HashSet<BlockPos>();var spaces=new ArrayList<AABB>();
        for(var binding:result.values())
        {
            if(binding.entity()!=null&&!actors.add(binding.entity()))throw new IllegalArgumentException("One actual device must use a shared resource ID");
            if(directory.resource(binding.resource()).kind()==ResourceKind.RAIL&&binding.mechanicalRail()==null)for(var cell:binding.cells())if(!rails.add(cell.position()))throw new IllegalArgumentException("Overlapping actual rails require a shared resource ID");
            if(directory.resource(binding.resource()).kind()==ResourceKind.SPACE)
            {spaces.addAll(binding.spaces());}
        }
        NervSpacePartitionR52.requireDisjoint(spaces);
        return Map.copyOf(result);
    }
}

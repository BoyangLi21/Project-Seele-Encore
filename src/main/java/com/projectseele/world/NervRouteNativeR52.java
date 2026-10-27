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
        default boolean mechanicalRailReadyR53(ServerLevel level,NervMechanicalRailBindingR52.Spec rail,List<Cell> foundations,boolean scoped){return mechanicalRailReadyR52(level,rail,foundations);}
        boolean restoreOriginalPreparation(ServerLevel level,Original original,CompoundTag ownerData);
        default NervOwnerPlacementR52.Proof finishingAssemblyPlacement(ServerLevel level,Original original,CompoundTag ownerData){return null;}
        default RigidTransform finishingReferenceFrameR52(ServerLevel level,Original original,CompoundTag ownerData,RigidTransform directoryEndpoint){return directoryEndpoint;}
        default boolean restoreFinishingOriginal(ServerLevel level,Original original,CompoundTag ownerData){return false;}
        default boolean originalPersonnelBindingsReady(ServerLevel level){return false;}
        default TrainingPilotDirector.ActionResult requestOriginalPilot(ServerLevel level,int variant,String operation){return new TrainingPilotDirector.ActionResult(false,"R52 原座椅/电话/人员通道绑定尚未就绪。");}
        default boolean routeOriginalPilot(ServerLevel level,TrainingPilotEntity pilot,String operation){return false;}
        default boolean atOriginalPilotStandby(ServerLevel level,int variant){return false;}
        Preparation prepareOriginal(ServerLevel level,Original original,CompoundTag ownerData);
        default boolean requiresPreparationRecoveryR53(ServerLevel level,Original original,CompoundTag ownerData){return false;}
        boolean prepareLeg(ServerLevel level,Original original,Route route,Leg leg,CompoundTag ownerData);
        default boolean prepareBankHeadsR53(ServerLevel level,Original original,Route route,UUID task,CompoundTag ownerData){return false;}
        default boolean prepareBankForRetargetR53(ServerLevel level,Original original,Route route,UUID task,CompoundTag ownerData){return false;}
        default boolean prepareContinuousRouteR52(ServerLevel level,Original original,Route route,CompoundTag ownerData){return false;}
        default List<DirectoryTrajectoryR52> continuousRoutePathsR52(ServerLevel level,Original original,Route route,CompoundTag ownerData){return List.of();}
        default boolean rebindStoppedContinuousR52(ServerLevel level,Original original,CompoundTag ownerData){return false;}

        default boolean preflightCheckedContinuousCarrierR53(ServerLevel level,CheckedContinuousTraversalR52 proof,CompoundTag ownerData){return false;}
        default Sweep sweptContinuousAssemblyR52(ServerLevel level,Original original,List<DirectoryTrajectoryR52> paths,CompoundTag ownerData){return null;}
        default boolean applyCheckedContinuousR52(ServerLevel level,CheckedContinuousTraversalR52 proof,CompoundTag ownerData){return false;}
        FootSupportFrameR52.Binding originalBinding(ServerLevel level,Original original,CompoundTag ownerData);
        net.minecraft.world.phys.Vec3 actualFootBearingCentre(ServerLevel level,Original original,CompoundTag ownerData);
        /** Classify through Root's actual bound receiver domains, never a
         * historical outgoing route or an invented universal Y threshold. */
        default Region actualRecoveryRegion(ServerLevel level,Original original,CompoundTag ownerData){return null;}
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
    private static final Set<String> RETIRED_PIT_SUPPORTS_R53=Set.of(
            "support/unit0/original_incline","support/unit1/original_incline","support/unit2/original_incline",
            "support/unit0/bank1_to_2","support/unit1/bank1_to_2","support/unit2/bank1_to_2",
            "support/unit0/bank2_to_3","support/unit1/bank2_to_3","support/unit2/bank2_to_3");
    private CompoundTag ownerData=new CompoundTag();
    private Kind currentKind=Kind.OCCUPIED;
    private final Map<UUID,String> continuousFailuresR53=new HashMap<>();
    public String continuousFailureR53(UUID eva){return continuousFailuresR53.getOrDefault(eva,"");}
    private CheckedContinuousTraversalR52 continuousHeldR53(Original original,String reason){continuousFailuresR53.put(original.eva(),reason);return null;}
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
        if(fleet==null||!fleet.canonicalId().equals(original.eva())||!original.plug().equals(fleet.entryPlugId())&&(fleet.entryPlugId()!=null||!EntryPlugDisposalR31.destroyed(level,original.plug()))||!level.dimension().location().toString().equals(original.dimension())
                ||!(level.getEntity(original.eva()) instanceof EvaUnit01Entity eva)||eva.isExperimentalUnit()||eva.getUnitVariant()!=original.variant()||!eva.isAlive()
                ||eva.getPilotEntity()!=null||eva.isEntryPlugInserted()||!eva.getPassengers().isEmpty()||!EntryPlugEjectionR48.originalFieldEjection(level,original.variant(),eva,original.pilot()))return false;
        var data=eva.getPersistentData();return TransportMembershipR52.hullRecoveryAdmission(original,data,Set.copyOf(eva.getPassengers().stream().map(Entity::getUUID).toList()),eva.isEntryPlugInserted(),EvaShutdownR30.disabled(eva))
                &&(ownerData.getBoolean("Returning")||ownerData.getBoolean("FlightTransportR53")||AutoSortieR32.missionToken(level,original.variant()).equals(original.mission()));
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
        boolean transport=ownerData.getBoolean("Returning")||ownerData.getBoolean("FlightTransportR53");
        if(!transport&&!AutoSortieR32.missionToken(level,original.variant()).equals(original.mission()))return false;
        var tag=eva.getPersistentData();if(tag.hasUUID("R32SortieCommander")&&!tag.getUUID("R32SortieCommander").equals(original.owner()))return false;
        if(!transport&&AutoSortieR32.cancellationCurrentR45(tag.getBoolean("R32AutoCancelled"),tag.getString("R43AutoMission"),original.mission()))return false;
        if(r instanceof TrainingPilotEntity pilot&&original.mission().isEmpty())
            return NervRouteRuntimeR52.manualOriginalNpcR60(level,directory,owner,original,eva,pilot);
        if(r instanceof TrainingPilotEntity)return AutoSortieR32.assignedPilotR45(level,original.variant(),r)
                &&TvCampaignSavedData.get(level).sorties.get(original.variant()).commander.equals(original.owner());
        return r instanceof ServerPlayer player&&!player.isSpectator()&&player.getUUID().equals(original.owner())&&NervStaffDialogue.authorized(player);
    }
    private static boolean cellNearbyR53(BlockPos at,List<AABB> scope)
    {return scope==null||scope.stream().anyMatch(box->box.intersects(new AABB(at)));}
    public boolean resourceNearbyR53(String id,List<AABB> scope)
    {
        var bound=bindings.get(id);
        // Missing/empty bindings cannot make a real gate disappear from readiness checks.
        return scope==null||bound==null||bound.cells().isEmpty()||bound.cells().stream().anyMatch(cell->cellNearbyR53(cell.position(),scope));
    }
    public boolean resourceReady(String id,boolean openGate)
    {return resourceReadyR53(id,openGate,null);}
    public boolean resourceReadyR53(String id,boolean openGate,List<AABB> scope)
    {
        var resource=directory.resource(id);var binding=bindings.get(id);if(resource==null||binding==null||!resource.component().equals(binding.component()))return false;
        if(scope!=null&&resource.kind()==ResourceKind.DOOR&&!resourceNearbyR53(id,scope))return true;
        boolean scoped=scope!=null&&(resource.kind()==ResourceKind.RAIL||resource.kind()==ResourceKind.SUPPORT);
        var cells=scoped?binding.cells().stream().filter(cell->cellNearbyR53(cell.position(),scope)).toList():binding.cells();
        boolean retiredPitSupports=((binding.mechanicalRail()!=null
                &&binding.mechanicalRail().kind()==NervMechanicalRailBindingR52.Kind.LEGACY_RUNNING_HEAD
                ||RETIRED_PIT_SUPPORTS_R53.contains(id)));
        for(var cell:cells)
        {
            if(retiredPitSupports&&cell.state().equals("projectseele:nerv_shaft_panel"))continue;
            BlockPos pos=cell.position();if(level.getChunkSource().getChunkNow(pos.getX()>>4,pos.getZ()>>4)==null)return false;
            var actual=level.getBlockState(pos);
            boolean repaintedFoundation=(resource.kind()==ResourceKind.RAIL||resource.kind()==ResourceKind.SUPPORT)
                    &&actual.is(net.minecraft.world.level.block.Blocks.BLACK_CONCRETE)
                    &&Set.of("projectseele:nerv_shaft_panel","projectseele:nerv_structural_panel","projectseele:nerv_wall_panel").contains(cell.state())
                    &&actual.isCollisionShapeFullBlock(level,pos);
            if(!BlockStateParser.serialize(actual).equals(cell.state())&&!repaintedFoundation
                    ||(resource.kind()==ResourceKind.RAIL||resource.kind()==ResourceKind.SUPPORT)&&actual.isAir())return false;
        }
        if(binding.mechanicalRail()!=null)
        {
            var rail=binding.mechanicalRail();
            boolean localGuide=scoped&&(rail.kind()==NervMechanicalRailBindingR52.Kind.UPRIGHT_CAPTURED_GUIDEWAY||rail.kind()==NervMechanicalRailBindingR52.Kind.FIXED_FOOT_GUIDE);
            if(!localGuide&&!NervMechanicalRailBindingR52.ready(level,directory,rail)
                ||!owner.mechanicalRailReadyR53(level,rail,cells,scoped))return false;
        }
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
        private final FullAssemblyGeometryR52.CheckedAssemblySweep assemblySweep;
        private final List<DirectoryTrajectoryR52> coveragePaths;
        private final boolean allowsPendingSource;
        public boolean allowsPendingSourceR53(){return allowsPendingSource;}
        private CheckedContinuousTraversalR52(NervRouteNativeR52 access,Original original,Route route,List<DirectoryTrajectoryR52> paths,FullAssemblyGeometryR52.CheckedAssemblySweep assemblySweep)
        {this(access,original,route,paths,paths,assemblySweep);}
        private CheckedContinuousTraversalR52(NervRouteNativeR52 access,Original original,Route route,List<DirectoryTrajectoryR52> paths,List<DirectoryTrajectoryR52> coveragePaths,FullAssemblyGeometryR52.CheckedAssemblySweep assemblySweep)
        {this(access,original,route,paths,coveragePaths,assemblySweep,false);}
        private CheckedContinuousTraversalR52(NervRouteNativeR52 access,Original original,Route route,List<DirectoryTrajectoryR52> paths,List<DirectoryTrajectoryR52> coveragePaths,FullAssemblyGeometryR52.CheckedAssemblySweep assemblySweep,boolean allowsPendingSource)
        {this.access=access;this.original=original;this.route=route;this.kind=access.currentKind;this.paths=List.copyOf(paths);this.coveragePaths=List.copyOf(coveragePaths);this.assemblySweep=assemblySweep;this.allowsPendingSource=allowsPendingSource;at=access.level.getGameTime();}
        public Original original(){return original;}public Route route(){return route;}public Kind kind(){return kind;}public List<DirectoryTrajectoryR52> paths(){return paths;}public long checkedAt(){return at;}
        public FootSupportFrameR52.Sample from(){return paths.get(0).sample(0);}public FootSupportFrameR52.Sample to(){return paths.get(paths.size()-1).sample(1);}
        public boolean current(ServerLevel level){return !committed&&level==access.level&&level.getGameTime()==at&&access.currentKind==kind&&access.sameAssembly(original,kind);}
        public boolean coversFixedCarrierRailsR53(ServerLevel level,NervCarrierPlatformEntity carrier,List<DirectoryTrajectoryR52> paths,Set<UUID> own)
        {return current(level)&&samePathsR53(this.paths,paths)&&assemblySweep.matchesSlices(original,coveragePaths)&&assemblySweep.fixedRailsCurrentR53(level,carrier,coveragePaths,own);}
        /** Only the beginning of this tick's already cleared horizon may be
         * committed. The complete horizon remains the source of rail coverage;
         * no result is reused after motion, a tick change or source/state change. */
        CheckedContinuousTraversalR52 checkedPrefixR53(List<DirectoryTrajectoryR52> prefix)
        {
            if(!current(access.level)||!prefixR53(paths,prefix))return null;
            return new CheckedContinuousTraversalR52(access,original,route,prefix,coveragePaths,assemblySweep);
        }
        private static boolean sameCurveR53(DirectoryTrajectoryR52 a,DirectoryTrajectoryR52 b)
        {return a.directory()==b.directory()&&a.leg().equals(b.leg())&&a.binding().equals(b.binding());}
        private static boolean samePathsR53(List<DirectoryTrajectoryR52> a,List<DirectoryTrajectoryR52> b)
        {if(a.size()!=b.size())return false;for(int i=0;i<a.size();i++)if(!sameCurveR53(a.get(i),b.get(i))||a.get(i).fromFraction()!=b.get(i).fromFraction()||a.get(i).toFraction()!=b.get(i).toFraction())return false;return true;}
        private static boolean prefixR53(List<DirectoryTrajectoryR52> covered,List<DirectoryTrajectoryR52> prefix)
        {
            if(prefix==null||prefix.isEmpty()||prefix.size()>2048||covered.isEmpty())return false;
            int index=0;double cursor=covered.get(0).fromFraction();
            for(var part:prefix)
            {
                if(index>=covered.size()||!sameCurveR53(part,covered.get(index))
                        ||part.fromFraction()!=cursor||part.toFraction()<=cursor)return false;
                while(part.toFraction()>covered.get(index).toFraction())
                {
                    double end=covered.get(index).toFraction();
                    if(++index>=covered.size()||!sameCurveR53(part,covered.get(index))||covered.get(index).fromFraction()!=end)return false;
                }
                cursor=part.toFraction();
                if(cursor==covered.get(index).toFraction()&&++index<covered.size())cursor=covered.get(index).fromFraction();
            }
            return true;
        }
        public boolean recordCommittedR52(ServerLevel level,CompoundTag data){if(!current(level)||!access.owner.actualFrameMatches(level,original,to(),data))return false;committed=true;return true;}
        public boolean committed(){return committed;}
    }
    public CheckedContinuousTraversalR52 checkContinuousR52(Original original,Route route,List<DirectoryTrajectoryR52> paths)
    {return checkContinuousR52(original,route,paths,false);}
    CheckedContinuousTraversalR52 checkContinuousR52(Original original,Route route,List<DirectoryTrajectoryR52> paths,boolean allowPendingSource)
    {
        if(route==null||!route.continuousUpright()||paths==null||paths.isEmpty()||paths.size()>2048||!sameAssembly(original,currentKind)||currentKind==Kind.HULL_ONLY_RECOVERY&&!route.recovery())return continuousHeldR53(original,"original_assembly_or_route");
        if(currentKind==Kind.OCCUPIED&&!EntryPlugDirector.hasLaunchLock(level,original.variant(),(EvaUnit01Entity)level.getEntity(original.eva())))return continuousHeldR53(original,"occupied_launch_lock");
        var ids=new HashSet<String>();for(var path:paths){if(!path.directory().fingerprint().equals(directory.fingerprint())||!route.legs().contains(path.leg().id())||path.leg().motion()==Motion.FOOT_BEARING_TURN)return continuousHeldR53(original,"route_slice");ids.addAll(path.leg().resources());}
        // Whole-source fixed-rail diagnostics are explicit; normal travel checks the current motion.
        try{var sweep=owner.sweptContinuousAssemblyR52(level,original,paths,ownerData);var own=TransportMembershipR52.members(original,currentKind);if(sweep==null||sweep.triangles()==null||!sweep.assembly().equals(own)||!sweep.triangles().matchesSlices(original,paths)||!sweep.triangles().matchesSamples(paths.get(0).sample(0),paths.get(paths.size()-1).sample(1)))return continuousHeldR53(original,"captured_source_or_samples");
            // One block admits adjacent physical bearing cells; prefetch margin
            // belongs to the owner and must not hold an already loaded step.
            List<AABB> scope=NervTraversalPolicyR53.strict(level)?null:sweep.volumes().stream().map(box->box.inflate(1)).toList();
            for(String id:ids)if(!resourceReadyR53(id,directory.resource(id).kind()==ResourceKind.DOOR,scope))return continuousHeldR53(original,"resource="+id);
            var spaces=new ArrayList<AABB>();for(String id:ids)if(directory.resource(id).kind()==ResourceKind.SPACE){var bound=bindings.get(id);if(bound==null)return continuousHeldR53(original,"space_binding="+id);spaces.addAll(bound.spaces());}
            for(var box:sweep.volumes()){if(NervTraversalPolicyR53.strict(level)&&!coveredByDeclaredSpacesR52(box,spaces))return continuousHeldR53(original,"uncovered_space="+box);for(int x=(int)Math.floor(box.minX)>>4;x<=((int)Math.floor(box.maxX)>>4);x++)for(int z=(int)Math.floor(box.minZ)>>4;z<=((int)Math.floor(box.maxZ)>>4);z++)if(level.getChunkSource().getChunkNow(x,z)==null)return continuousHeldR53(original,"unloaded_chunk="+x+","+z);}
            if(!sweep.triangles().clear(level,level.getEntity(original.eva()))
                    ||(NervTraversalPolicyR53.strict(level)&&!sweep.triangles().clearFixedCarrierRailsR53(level,(EvaUnit01Entity)level.getEntity(original.eva()),allowPendingSource)))
                return continuousHeldR53(original,sweep.triangles().clearanceHoldR53());
            continuousFailuresR53.remove(original.eva());return new CheckedContinuousTraversalR52(this,original,route,paths,paths,sweep.triangles(),allowPendingSource);
        }catch(IllegalArgumentException|IllegalStateException unavailable){return continuousHeldR53(original,"proof="+unavailable.getMessage());}
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
            return true;
        }
        catch(IllegalArgumentException|IllegalStateException invalid){return false;}
    }

    public boolean canRestore(Original original,Route route,int index,double fraction)
    {return canTraverse(original,route,directory.leg(route.legs().get(index)),fraction,fraction);}
    @Override public boolean canTraverseAssembly(Original original,Kind kind,Route route,Leg leg,double from,double to)
    {return kind==currentKind&&canTraverse(original,route,leg,from,to);}
    @Override public boolean canRestoreAssembly(Original original,Kind kind,Route route,int leg,double fraction)
    {return kind==currentKind&&canRestore(original,route,leg,fraction);}
    public boolean finishingPlacementClear(Original original,Route route,int index,double fraction)
    {
        try
        {
            if(!originalIdentitySet(original)||!owner.restoreFinishingOriginal(level,original,ownerData))return false;
            var binding=owner.originalBinding(level,original,ownerData);
            if(binding==null||!(level.getEntity(original.eva()) instanceof EvaUnit01Entity eva))return false;
            var leg=directory.leg(route.legs().get(index));
            var expected=owner.finishingReferenceFrameR52(level,original,ownerData,directory.sample(leg,fraction,binding).evaRoot());
            var actual=NervOwnerPlacementR52.actualRoot(eva);
            // Restore the accepted endpoint. The finishing owner checks the
            // actual support, gates and each subsequent mechanical step.
            return actual.translation().distanceToSqr(expected.translation())<=4e-6&&actual.rotationErrorDegrees(expected)<=.04;
        }
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

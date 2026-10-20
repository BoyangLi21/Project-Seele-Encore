package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervLiftDoorEntity;
import com.supermartijn642.movingelevators.MovingElevators;
import com.supermartijn642.movingelevators.blocks.ControllerBlock;
import com.supermartijn642.movingelevators.blocks.ControllerBlockEntity;
import com.supermartijn642.movingelevators.blocks.DisplayBlockEntity;
import com.supermartijn642.movingelevators.blocks.ElevatorInputBlockEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.LevelResource;
import java.nio.file.*;
import java.util.*;

/** Claimed worlds adopt only Root-listed native devices; no migration or geometry repair. */
public final class S20LiftDirectoryR52
{
    private static final Map<ServerLevel,State> STATES=new WeakHashMap<>();
    private static final class State
    {
        String reference="",fingerprint="",fault="";long epoch,size=-1,modified=-1;int observed=Integer.MIN_VALUE;
        final NervManifestPollR52 poll=new NervManifestPollR52();
        S20LiftManifestR52.Document document;List<S20PhysicalElevatorDirector.LiftSpec> specs=List.of();boolean ready;
        final Set<String> nativeReady=new HashSet<>();boolean officeReady;
        final Map<String,BlockState> closed=new HashMap<>();
        final Map<String,Set<ChunkPos>> footprints=new HashMap<>();
        final Map<String,UUID> cabinVisuals=new HashMap<>();
    }
    private S20LiftDirectoryR52() {}
    private static State state(ServerLevel level)
    {
        State state=STATES.computeIfAbsent(level,l->new State());int tick=level.getServer().getTickCount();
        String reference=NervRouteRuntimeR52.personnelLiftManifest(level),fingerprint=NervRouteRuntimeR52.directoryFingerprint(level);
        long epoch=NervRouteRuntimeR52.commissioningEpoch(level);
        boolean changed=!state.reference.equals(reference)||!state.fingerprint.equals(fingerprint)||state.epoch!=epoch;
        if(state.observed==tick&&!changed)return state;state.observed=tick;
        if(changed){state.document=null;state.specs=List.of();state.closed.clear();state.footprints.clear();state.ready=false;state.nativeReady.clear();state.officeReady=false;state.reference=reference;state.fingerprint=fingerprint;state.epoch=epoch;state.modified=-1;state.poll.invalidate();SeeleConferenceAccessR47.invalidateR52(level);FacilityDoorControlsR49.invalidateR52(level);}
        if(reference.isBlank()){state.ready=false;return state;}
        try
        {
            Path root=level.getServer().getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize();Path relative=Path.of(reference);
            if(relative.isAbsolute()||reference.contains(":")||reference.contains("\\"))throw new IllegalArgumentException("Root world-relative lift manifest required");
            Path file=root.resolve(relative).normalize();if(!file.startsWith(root))throw new IllegalArgumentException("Lift manifest escaped world");
            var probe=state.poll.probe(file,tick);
            if(!probe.available()){failed(state,probe.fault(),tick);return state;}
            if(probe.changed())
            {
                long modified=probe.modified(),size=probe.size();
                if(size>1024*1024)throw new IllegalArgumentException("Bounded explicit lift manifest required");
                if(state.document==null||modified!=state.modified||size!=state.size)
                {
                    SeeleConferenceAccessR47.invalidateR52(level);FacilityDoorControlsR49.invalidateR52(level);
                    var document=S20LiftManifestR52.parse(JsonParser.parseString(Files.readString(file)).getAsJsonObject());
                    if(document.epoch()!=epoch||!document.directoryFingerprint().equals(fingerprint))throw new IllegalArgumentException("Lift manifest does not match Root world claim");
                    state.document=document;state.specs=document.lifts().stream().map(S20LiftManifestR52.Binding::spec).toList();state.closed.clear();state.footprints.clear();state.modified=modified;state.size=size;
                }
            }
            // A previously rejected unchanged file is a negative cache entry,
            // not another parse/exception or a reason to clear its fault.
            if(state.document==null)return state;
            state.ready=state.document!=null&&state.document.ready();state.nativeReady.clear();state.officeReady=false;
            if(state.ready)
            {
                for(var binding:state.document.lifts())if(readback(level,state,binding))state.nativeReady.add(binding.id());
                var office=state.document.office();state.officeReady=office!=null&&state.nativeReady.contains(office.liftId())
                        &&officeLoaded(level,office)
                        &&office.readers().stream().allMatch(p->officeReaderValid(level,p))
                        &&FacilityDoorControlsR49.rootControlsValid(level,office.controls());
            }
            state.fault="";
        }
        catch(Exception failure)
        {
            failed(state,failure.toString(),tick);
        }
        return state;
    }
    private static void failed(State state,String fault,int tick)
    {state.ready=false;state.document=null;state.specs=List.of();state.nativeReady.clear();state.officeReady=false;state.fault=fault;if(state.poll.warningDue(fault,tick))ProjectSeele.LOGGER.warn("R52 personnel lifts held; legacy coordinates remain disabled: {}",fault);}
    /** Explicit installation/file replacement wakes a negative cache now. */
    public static void invalidate(ServerLevel level)
    {var state=STATES.get(level);if(state!=null){state.observed=Integer.MIN_VALUE;state.poll.invalidate();}}
    public static void invalidate(net.minecraft.server.MinecraftServer server)
    {STATES.forEach((level,state)->{if(level.getServer()==server){state.observed=Integer.MIN_VALUE;state.poll.invalidate();}});}
    private static boolean readback(ServerLevel level,State state,S20LiftManifestR52.Binding binding)throws Exception
    {
        // A controller's ticket alone does not make its cabin and remote
        // controls available. Check the immutable complete read footprint
        // before any Level state/BE access can synchronously join a chunk.
        for(var chunk:state.footprints.computeIfAbsent(binding.id(),id->footprint(binding)))
            if(level.getChunkSource().getChunkNow(chunk.x,chunk.z)==null)return false;
        {
            boolean moving=false;int cars=0;
            for(var floor:binding.floors())
            {
                if(!level.hasChunkAt(floor.controller()))return false;
                var block=level.getBlockState(floor.controller());
                if(!block.is(MovingElevators.elevator_block)||!block.hasProperty(ControllerBlock.FACING)||block.getValue(ControllerBlock.FACING)!=binding.controllerFacing()
                        ||!(level.getBlockEntity(floor.controller()) instanceof ControllerBlockEntity controller)||!controller.hasGroup())return false;
                var group=controller.getGroup();var canonical=NervPersonnelTransferR53.canonicalController(level,floor.controller());
                if(group.x!=canonical.getX()||group.z!=canonical.getZ()||group.facing!=binding.controllerFacing()||group.getFloorCount()!=binding.floors().size())return false;
                moving|=group.isMoving();boolean present=S20PhysicalElevatorDirector.hasAuthoredCabinAt(level,floor.cabin());if(present)cars++;
                for(var call:floor.calls())if(!callValid(level,state,binding,call))return false;
                if(present&&!group.isMoving()&&(!controlLink(level,state,binding,floor.cabin().offset(binding.insideButtonOffset()))||!controlLink(level,state,binding,floor.cabin().offset(binding.insideDisplayOffset()))))return false;
                for(int i=0;i<binding.floors().size();i++)if(group.getFloorYLevel(i)!=binding.floors().get(i).cabin().getY())return false;
                var anchor=group.getCageAnchorBlockPos(floor.cabin().getY());
                if(anchor.getX()+group.getCageSizeX()/2!=floor.cabin().getX()||anchor.getY()!=floor.cabin().getY()-1||anchor.getZ()+group.getCageSizeZ()/2!=floor.cabin().getZ())return false;
                // Cabin doors travel with the single car. At a nearby empty
                // stop their hypothetical cells may contain that car's roof.
                // Landing doors remain fixed and are checked at every stop.
                for(var cells:group.isMoving()||!present?List.of(floor.landingDoors()):List.of(floor.landingDoors(),floor.cabinDoors()))for(var cell:cells.entrySet())
                {
                    var current=level.getBlockState(cell.getKey());var closed=closed(state,cell.getValue());
                    if(level.getBlockEntity(cell.getKey())!=null||!current.isAir()&&!current.equals(closed)&&!current.is(com.projectseele.registry.ModBlocks.LIFT_DOOR_INTERLOCK_R53.get()))return false;
                }
            }
            if(!moving&&cars!=1)return false;
        }
        return true;
    }
    private static Set<ChunkPos> footprint(S20LiftManifestR52.Binding binding)
    {
        Set<ChunkPos> chunks=new HashSet<>();
        for(var floor:binding.floors())
        {
            chunks.add(new ChunkPos(floor.controller()));
            // hasAuthoredCabinAt reads the existing radius-two floor mask.
            for(int x=-2;x<=2;x++)for(int z=-2;z<=2;z++)
                chunks.add(new ChunkPos(floor.cabin().offset(x,-1,z)));
            chunks.add(new ChunkPos(floor.cabin().offset(binding.insideButtonOffset())));
            chunks.add(new ChunkPos(floor.cabin().offset(binding.insideDisplayOffset())));
            for(var call:floor.calls())
            {
                chunks.add(new ChunkPos(call.position()));chunks.add(new ChunkPos(call.targetController()));
                if(call.display()!=null)chunks.add(new ChunkPos(call.display().position()));
            }
            for(var p:floor.landingDoors().keySet())chunks.add(new ChunkPos(p));
            for(var p:floor.cabinDoors().keySet())chunks.add(new ChunkPos(p));
        }
        return Set.copyOf(chunks);
    }
    private static boolean loaded(ServerLevel level,BlockPos point)
    {return level.getChunkSource().getChunkNow(point.getX()>>4,point.getZ()>>4)!=null;}
    private static boolean officeLoaded(ServerLevel level,S20LiftManifestR52.Office office)
    {
        for(var point:office.readers())if(!loaded(level,point))return false;
        for(var door:office.controls().gate())if(!loaded(level,door.lower()))return false;
        for(var reader:office.controls().gateReaders())
            if(!loaded(level,reader.position())||!loaded(level,reader.backing()))return false;
        return true;
    }
    private static boolean controlLink(ServerLevel level,State state,S20LiftManifestR52.Binding binding,BlockPos point)
    {
        var entity=level.getBlockEntity(point);
        if(entity instanceof NervAccessReaderEntityR44){var office=state.document.office();return office!=null&&office.liftId().equals(binding.id())&&office.readers().contains(point);}
        if(entity instanceof DisplayBlockEntity display)entity=display.getInputBlockEntity();
        if(!(entity instanceof ElevatorInputBlockEntity input)||!input.hasGroup())return false;
        var group=input.getGroup();var base=binding.floors().get(0).controller();
        if(group==null||group.x!=base.getX()||group.z!=base.getZ()||group.facing!=binding.controllerFacing())return false;
        var data=entity.saveWithoutMetadata().getCompound("data");
        return data.contains("controllerX")&&data.contains("controllerY")&&data.contains("controllerZ")
                &&binding.floors().stream().anyMatch(f->f.controller().getX()==data.getInt("controllerX")&&f.controller().getY()==data.getInt("controllerY")&&f.controller().getZ()==data.getInt("controllerZ"))
                &&data.getInt("controllerFacing")==binding.controllerFacing().get2DDataValue();
    }
    private static boolean callValid(ServerLevel level,State state,S20LiftManifestR52.Binding binding,S20LiftManifestR52.Call call)throws Exception
    {
        if(!level.hasChunkAt(call.position())||!level.hasChunkAt(call.targetController()))return false;
        var actual=level.getBlockState(call.position());var expected=expected(state,call.state());
        if(call.kind()==S20LiftManifestR52.CallKind.VANILLA_BUTTON)
        {
            if(!(expected.getBlock() instanceof ButtonBlock)||!BuiltInRegistries.BLOCK.getKey(expected.getBlock()).getNamespace().equals("minecraft")
                    ||level.getBlockEntity(call.position())!=null||!expected.hasProperty(ButtonBlock.FACING)||expected.getValue(ButtonBlock.FACING)!=call.facing())return false;
            if(actual.hasProperty(BlockStateProperties.POWERED)&&expected.hasProperty(BlockStateProperties.POWERED))actual=actual.setValue(BlockStateProperties.POWERED,expected.getValue(BlockStateProperties.POWERED));
            return actual.equals(expected); // Only the physical button's transient powered bit may differ.
        }
        if(!actual.equals(expected))return false;
        if(call.kind()==S20LiftManifestR52.CallKind.SEELE_READER)
        {
            var office=state.document.office();return office!=null&&office.liftId().equals(binding.id())&&office.readers().contains(call.position())
                    &&actual.hasProperty(NervAccessReaderR44.FACING)&&actual.getValue(NervAccessReaderR44.FACING)==call.facing()&&officeReaderValid(level,call.position());
        }
        if(!(level.getBlockEntity(call.position()) instanceof ElevatorInputBlockEntity input)||input.getFacing()!=call.facing()
                ||!controlLink(level,state,binding,call.position()))return false;
        var data=input.saveWithoutMetadata().getCompound("data");var target=call.targetController();
        if(data.getInt("controllerX")!=target.getX()||data.getInt("controllerY")!=target.getY()||data.getInt("controllerZ")!=target.getZ())return false;
        if(call.display()!=null)
        {
            var display=call.display();if(!level.hasChunkAt(display.position())||!level.getBlockState(display.position()).equals(expected(state,display.state()))
                    ||!(level.getBlockEntity(display.position()) instanceof DisplayBlockEntity entity)||entity.getInputBlockEntity()!=input)return false;
        }
        return true;
    }
    private static boolean officeReaderValid(ServerLevel level,BlockPos point)
    {
        if(!loaded(level,point)||!(level.getBlockEntity(point) instanceof NervAccessReaderEntityR44 reader))return false;
        var tag=reader.saveWithoutMetadata();return !tag.getBoolean("Linked")&&tag.getInt("Clearance")==3;
    }
    private static BlockState closed(State state,String text)throws Exception
    {
        var block=expected(state,text);if(block.hasBlockEntity())throw new IllegalArgumentException("Door plane cannot overwrite block entities");return block;
    }
    private static BlockState expected(State state,String text)throws Exception
    {
        var cached=state.closed.get(text);if(cached!=null)return cached;
        var block=BlockStateParser.parseForBlock(BuiltInRegistries.BLOCK.asLookup(),text,false).blockState();
        state.closed.put(text,block);return block;
    }
    public static List<S20PhysicalElevatorDirector.LiftSpec> specs(ServerLevel level)
    {if(!NervRouteRuntimeR52.claimed(level))return List.of();var state=state(level);return state.ready?state.specs:List.of();}
    public static boolean current(ServerLevel level,S20PhysicalElevatorDirector.LiftSpec spec)
    {if(!NervRouteRuntimeR52.claimed(level))return false;var state=state(level);var office=state.document==null?null:state.document.office();return spec.r52()!=null&&state.ready&&state.nativeReady.contains(spec.id())
            &&(office==null||!office.liftId().equals(spec.id())||state.officeReady)&&state.specs.stream().anyMatch(spec::equals);}
    public static boolean ready(ServerLevel level){return NervRouteRuntimeR52.claimed(level)&&state(level).ready;}
    public static S20LiftManifestR52.Office office(ServerLevel level)
    {if(!NervRouteRuntimeR52.claimed(level))return null;var state=state(level);return state.officeReady&&state.document!=null?state.document.office():null;}
    public static S20LiftManifestR52.Office declaredOffice(ServerLevel level)
    {if(!NervRouteRuntimeR52.claimed(level))return null;var state=state(level);return state.document==null?null:state.document.office();}
    public static boolean displayAllowed(ServerLevel level,com.supermartijn642.movingelevators.elevator.ElevatorGroup group)
    {
        if(independentGateway(RegionalGatewayDirector.active(level),group.x,group.z,group.facing))return true;
        State state=state(level);if(!state.ready)return false;
        for(var spec:state.specs){var p=spec.r52().floors().get(0).controller();if(group.x==p.getX()&&group.z==p.getZ()&&group.facing==spec.r52().controllerFacing())return current(level,spec);}
        return !retiredControllerAxis(group.x,group.z); // Independent player-owned groups remain outside this directory.
    }
    static boolean retiredControllerAxis(int x,int z)
    {
        // These are observed original/failed facility groups, not proximity bounds.
        // An installed replacement must explicitly own its surviving native groups.
        return Set.of("9;253","63;302","31;321","130;269","96;-52","-26;-278","86;366","108;410","70;253","97;-15")
                .contains(x+";"+z);
    }
    static boolean independentGateway(boolean active,int x,int z,net.minecraft.core.Direction facing)
    {return active&&x==RegionalGatewayDirector.X-8&&z==RegionalGatewayDirector.Z&&facing==net.minecraft.core.Direction.EAST;}
    public static void synchronizeDoors(ServerLevel level,S20PhysicalElevatorDirector.LiftSpec spec,double currentY,boolean moving)
    {
        if(!current(level,spec))return;State state=state(level);S20LiftManifestR52.Floor car=null;
        if(!moving)for(var floor:spec.r52().floors())if(S20PhysicalElevatorDirector.hasAuthoredCabinAt(level,floor.cabin())){if(car!=null)return;car=floor;}
        for(var floor:spec.r52().floors())
        {
            boolean open=car==floor;
            var office=state.document.office();if(open&&office!=null&&office.liftId().equals(spec.id())&&floor.cabin().getY()==office.middleY())open=SeeleConferenceAccessR47.canOpenLanding(level);
            var old=floor.visualDoor()==null?null:level.getEntity(floor.visualDoor());
            int id=old instanceof NervLiftDoorEntity d&&d.getDoorId()!=0?d.getDoorId():Objects.hash(spec.id(),floor.cabin(),"landing");
            int minX=Integer.MAX_VALUE,minY=minX,minZ=minX,maxX=Integer.MIN_VALUE,maxY=maxX,maxZ=maxX;
            for(var p:floor.landingDoors().keySet()){minX=Math.min(minX,p.getX());minY=Math.min(minY,p.getY());minZ=Math.min(minZ,p.getZ());maxX=Math.max(maxX,p.getX());maxY=Math.max(maxY,p.getY());maxZ=Math.max(maxZ,p.getZ());}
            if(floor.landingDoors().isEmpty())continue;
            var visual=NervLiftDoorEntity.reconcile(level,id,maxX-minX>=maxZ-minZ,Math.max(maxX-minX,maxZ-minZ)+1,maxY-minY+1,NervLiftDoorEntity.STYLE_GLASS,new net.minecraft.world.phys.Vec3((minX+maxX+1)*.5,minY,(minZ+maxZ+1)*.5));
            if(visual!=null)visual.setOpen(open);
            writeDoors(level,state,floor.landingDoors(),open&&visual!=null&&visual.getOpenProgress(1)>=.95F);
            if(S20PhysicalElevatorDirector.hasAuthoredCabinAt(level,floor.cabin()))writeDoors(level,state,floor.cabinDoors(),open);
        }
        var reference=spec.r52().floors().get(0);
        if(!reference.cabinDoors().isEmpty()&&level.getBlockEntity(reference.controller()) instanceof ControllerBlockEntity controller&&controller.hasGroup())
        {
            var group=controller.getGroup();
            int minX=Integer.MAX_VALUE,minY=minX,minZ=minX,maxX=Integer.MIN_VALUE,maxY=maxX,maxZ=maxX;
            for(var p:reference.cabinDoors().keySet()){minX=Math.min(minX,p.getX());minY=Math.min(minY,p.getY());minZ=Math.min(minZ,p.getZ());maxX=Math.max(maxX,p.getX());maxY=Math.max(maxY,p.getY());maxZ=Math.max(maxZ,p.getZ());}
            var initial=group.getCageAnchorBlockPos(reference.controller().getY());
            var localCentre=new net.minecraft.world.phys.Vec3(
                    (minX+maxX+1)*.5-initial.getX(),minY-initial.getY(),
                    (minZ+maxZ+1)*.5-initial.getZ());
            net.minecraft.world.phys.Vec3 centre;
            if(group.isMoving())
                centre=group.getCageAnchorPos(group.getCurrentY()).add((minX+maxX+1)*.5-initial.getX(),minY-initial.getY(),(minZ+maxZ+1)*.5-initial.getZ());
            else
            {
                // Native currentY is not an absolute world position while idle.
                // The landed cage, including its horizontal offset, owns this door.
                S20LiftManifestR52.Floor stopped=car;
                if(stopped==null)for(var floor:spec.r52().floors())
                    if(S20PhysicalElevatorDirector.hasAuthoredCabinAt(level,floor.cabin())){stopped=floor;break;}
                if(stopped==null||stopped.cabinDoors().isEmpty())return;
                minX=Integer.MAX_VALUE;minY=minX;minZ=minX;maxX=Integer.MIN_VALUE;maxY=maxX;maxZ=maxX;
                for(var p:stopped.cabinDoors().keySet()){minX=Math.min(minX,p.getX());minY=Math.min(minY,p.getY());minZ=Math.min(minZ,p.getZ());maxX=Math.max(maxX,p.getX());maxY=Math.max(maxY,p.getY());maxZ=Math.max(maxZ,p.getZ());}
                centre=new net.minecraft.world.phys.Vec3((minX+maxX+1)*.5,minY,(minZ+maxZ+1)*.5);
            }
            var id=state.cabinVisuals.get(spec.id());
            var visual=id==null?null:level.getEntity(id);
            NervLiftDoorEntity door;
            if(visual instanceof NervLiftDoorEntity existing){door=existing;door.setPos(centre.x,centre.y,centre.z);}
            else{door=NervLiftDoorEntity.reconcile(level,Objects.hash(spec.id(),"moving_cabin"),maxX-minX>=maxZ-minZ,Math.max(maxX-minX,maxZ-minZ)+1,maxY-minY+1,NervLiftDoorEntity.STYLE_GLASS,centre);if(door!=null)state.cabinVisuals.put(spec.id(),door.getUUID());}
            if(door!=null)
            {
                door.bindCage(group.x,group.z,group.facing,localCentre);
                boolean open=car!=null&&!moving;var office=state.document.office();
                if(open&&office!=null&&office.liftId().equals(spec.id())&&car.cabin().getY()==office.middleY())open=SeeleConferenceAccessR47.canOpenLanding(level);
                door.setOpen(open);
            }
        }
    }
    private static void writeDoors(ServerLevel level,State state,Map<BlockPos,String> cells,boolean open)
    {
        for(var cell:cells.entrySet())try
        {
            var before=level.getBlockState(cell.getKey());var closed=closed(state,cell.getValue());var interlock=com.projectseele.registry.ModBlocks.LIFT_DOOR_INTERLOCK_R53.get().defaultBlockState();if(level.getBlockEntity(cell.getKey())!=null||!before.isAir()&&!before.equals(closed)&&!before.equals(interlock))continue;
            var target=open?Blocks.AIR.defaultBlockState():interlock;if(!before.equals(target))level.setBlock(cell.getKey(),target,Block.UPDATE_CLIENTS|Block.UPDATE_KNOWN_SHAPE);
        }
        catch(Exception failure){state.ready=false;ProjectSeele.LOGGER.error("Root native lift door state rejected",failure);return;}
    }
}

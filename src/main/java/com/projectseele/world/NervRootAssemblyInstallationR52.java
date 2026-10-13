package com.projectseele.world;

import com.google.gson.*;
import com.mojang.brigadier.arguments.StringArgumentType;
import java.io.IOException;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.fml.common.Mod;

/** Explicit Root bundle is the only installation entry. All component files
 * stay under that actual world root; no filename, pose or identity is inferred. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class NervRootAssemblyInstallationR52
{
    public static final String SCHEMA="projectseele.r52.assembly-installation.v1";
    private static final TicketType<ChunkPos> RESTORE_TICKET=TicketType.create("nerv_root_restore_r52",Comparator.comparingLong(ChunkPos::toLong),200);
    private static final Map<ServerLevel,Long> RESTORE_TRIES=new WeakHashMap<>();
    private static final Map<ServerLevel,String> RESTORE_HOLDS=new WeakHashMap<>();
    private static final Map<ServerLevel,Set<UUID>> INSTALLED_ACTORS=new WeakHashMap<>();
    private static final Map<ServerLevel,Set<ChunkPos>> PENDING_TICKETS=new WeakHashMap<>();
    private static final Map<ServerLevel,Long> TICKET_REFRESH=new WeakHashMap<>();
    public record Result(boolean accepted,String reason,String directoryFingerprint,long epoch){}
    public static Result install(ServerLevel level,Path explicitBundle)throws IOException
    {return install(level,explicitBundle,false);}
    private static Result install(ServerLevel level,Path explicitBundle,boolean restoring)throws IOException
    {
        if(!NervRouteRuntimeR52.mapRebuildEnabledR52())throw new IllegalStateException("R50 map release: migrated-map installation is disabled");
        var world=level.getServer().getWorldPath(LevelResource.ROOT).toRealPath();var file=explicitBundle.toRealPath();require(file.startsWith(world)&&Files.size(file)<=256000,"Explicit bounded bundle inside the actual world required");
        var bytes=Files.readAllBytes(file);String bundleSHA=sha(bytes);var root=JsonParser.parseString(new String(bytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();require(root.get("schema").getAsString().equals(SCHEMA)&&root.get("map_author").getAsString().equals("root")&&root.get("status").getAsString().equals("installed"),"Only a Root installed bundle can commission physical machinery");
        require(root.get("dimension").getAsString().equals(level.dimension().location().toString()),"Actual installation dimension differs");
        var persisted=NervRouteRuntimeR52.installationStateR52(level);if(persisted!=null&&persisted.claimed())for(var chunk:persisted.installationActorChunks().values())retain(level,new ChunkPos(chunk));
        var ready=NervSourcePreparationR52.poll("bundle/"+file+"/"+bundleSHA,()->prepareBundleR52(world,file,bundleSHA,root));
        if(!ready.ready())return new Result(false,"Root source preparation HOLD: "+ready.hold(),root.get("directory_fingerprint").getAsString(),root.get("epoch").getAsLong());
        var prepared=ready.value();var directoryDocument=prepared.directoryDocument();var directory=prepared.directory();
        var saved=NervRouteRuntimeR52.installationStateR52(level);if(restoring)require(saved!=null&&saved.fault().isEmpty()&&saved.claimed()&&saved.epoch()==directory.epoch()&&saved.fingerprint().equals(directory.fingerprint())&&bundleSHA.equals(saved.installationBundleSHA()),"Persisted Root bundle/source/directory authority changed; explicit installation required");
        boolean continuous=directory.routes().values().stream().allMatch(NervRouteDirectoryR52.Route::continuousUpright);
        var owner=NervAssemblyOwnerR52.parse(prepared.ownerDocument(),directory);owner.preparedGeometryR52(prepared.geometry());
        var runtime=directoryDocument.getAsJsonObject("runtime");require(runtime!=null,"Complete declared native runtime required");NervRouteNativeR52.parseBindings(runtime.getAsJsonArray("bindings"),directory);
        JsonObject airDocument=prepared.airDocument();if(airDocument!=null){var manifest=NervAirTransportManifestR52.parse(airDocument,directory);require(manifest.installed(),"Root air manifest remains design");}
        Path personnelFile=prepared.personnelFile();if(personnelFile!=null){var personnel=S20LiftManifestR52.parse(prepared.personnelDocument());require(personnel.ready()&&personnel.epoch()==directory.epoch()&&personnel.directoryFingerprint().equals(directory.fingerprint()),"Root personnel lifts do not match the installed directory");}
        TvYashimaStationR52.Plan cannon=prepared.cannon();
        var positions=new LinkedHashMap<UUID,Vec3>(owner.installationActorPositionsR52());if(airDocument!=null){var manifest=NervAirTransportManifestR52.parse(airDocument,directory);for(var aircraft:manifest.aircraft().values())positions.put(aircraft.entity(),manifest.node(aircraft.stand()).frame().plane().translation());}if(cannon!=null){positions.put(cannon.cannon(),cannon.closed());positions.put(cannon.source(),cannon.sourcePosition());positions.put(cannon.hatch(),cannon.closed());}
        var requiredChunks=new HashSet<ChunkPos>(owner.installationFoundationChunksR52());for(var e:positions.entrySet()){requiredChunks.add(new ChunkPos(BlockPos.containing(e.getValue())));if(saved!=null){var actual=saved.installationActorChunks().get(e.getKey());if(actual!=null)requiredChunks.add(new ChunkPos(actual));}}PENDING_TICKETS.put(level,Set.copyOf(requiredChunks));for(var chunk:requiredChunks)retain(level,chunk);TICKET_REFRESH.put(level,level.getGameTime());
        NervRouteRuntimeR52.claimPending(level,directory.epoch(),directory.fingerprint());
        if(continuous)NervRouteRuntimeR52.installationStateR52(level).declareUprightGuideSourceR52(NervUprightGuidewayR52.sourceSha256());
        if(continuous){for(var chunk:NervUprightGuidewayR52.foundationChunks())if(level.getChunkSource().getChunkNow(chunk.x,chunk.z)==null)return new Result(false,"Root upright guideway foundation tickets still loading; claim retained",directory.fingerprint(),directory.epoch());NervUprightGuidewayR52.enable(level,directory);}
        if(!(restoring?owner.resumeExistingR52(level):owner.commission(level)))return new Result(false,"Root mechanical commissioning held: "+owner.commissioningDiagnosticR52()+"; claim retained",directory.fingerprint(),directory.epoch());
        if(cannon!=null){if(restoring)require(level.getEntity(cannon.cannon())!=null,"Saved original cannon not loaded; restoration cannot create a replacement");verifyCannonFoundationR52(level,cannon);TvYashimaStationR52.installRootControllerR52(level,cannon);}
        if(!NervRouteRuntimeR52.installParsed(level,directoryDocument,directory,owner,airDocument))return new Result(false,"Root actual unified runtime installation held; claim retained",directory.fingerprint(),directory.epoch());
        if(personnelFile!=null)NervRouteRuntimeR52.personnelLiftManifest(level,world.relativize(personnelFile).toString().replace('\\','/'));
        require(bundleSHA.equals(sha(Files.readAllBytes(file))),"Root bundle changed during commissioning");saved=NervRouteRuntimeR52.installationStateR52(level);saved.rememberInstallationR52(world.relativize(file).toString(),bundleSHA);saved.retainInstallationActorsR52(positions.keySet());INSTALLED_ACTORS.put(level,Set.copyOf(positions.keySet()));captureActorChunksR52(level,saved);RESTORE_HOLDS.remove(level);PENDING_TICKETS.remove(level);TICKET_REFRESH.remove(level);
        return new Result(true,"Root physical owner and shared runtime installed; native cycles and visuals still require actual verification",directory.fingerprint(),directory.epoch());
    }
    private record PreparedBundleR52(JsonObject directoryDocument,NervRouteDirectoryR52 directory,JsonObject ownerDocument,NervAssemblyOwnerR52.PreparedGeometryR52 geometry,JsonObject airDocument,Path personnelFile,JsonObject personnelDocument,TvYashimaStationR52.Plan cannon){}
    /** Only immutable source bytes/CPU geometry. No Level, actor or native shape. */
    private static PreparedBundleR52 prepareBundleR52(Path world,Path file,String bundleSHA,JsonObject root)throws IOException {
        require(bundleSHA.equals(sha(Files.readAllBytes(file))),"Root bundle changed before source preparation");
        var directoryFile=sourceBytesR52(file.getParent(),world,root.getAsJsonObject("directory"),32000000);var mechanicalFile=sourceBytesR52(file.getParent(),world,root.getAsJsonObject("mechanical_owner"),32000000);
        var directoryDocument=JsonParser.parseString(new String(directoryFile.bytes(),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();var directory=NervRouteDirectoryR52.parse(directoryDocument);
        require(directory.installed()&&directory.epoch()==root.get("epoch").getAsLong()&&directory.fingerprint().equals(root.get("directory_fingerprint").getAsString()),"Root bundle/directory identity differs");
        var ownerDocument=NervAssemblyOwnerR52.readDocumentR52(mechanicalFile.file(),mechanicalFile.bytes());
        boolean continuous=directory.routes().values().stream().allMatch(NervRouteDirectoryR52.Route::continuousUpright);
        if(continuous){require(root.has("upright_guideway"),"Continuous bundle requires its explicit actual upright guideway source reference");var guideFile=sourceBytesR52(file.getParent(),world,root.getAsJsonObject("upright_guideway"),256000000);var guide=ownerDocument.getAsJsonObject("ground_guides");String expected=root.getAsJsonObject("upright_guideway").get("sha256").getAsString();require(guide!=null&&guide.get("mode").getAsString().equals("continuous_upright")&&expected.equals(guide.get("paths_sha256").getAsString())&&guide.get("source_sha256").getAsString().equals(NervOuterCarrierGuideR52.SOURCE_SHA),"Explicit selected owner/model/guideway path source differs");NervUprightGuidewayR52.install(guideFile.bytes(),expected,directory);}
        var geometry=NervAssemblyOwnerR52.prepareGeometryR52(NervAssemblyOwnerR52.geometryRequestR52(ownerDocument));
        JsonObject airDocument=null;if(root.has("air_transport")){var airFile=sourceBytesR52(file.getParent(),world,root.getAsJsonObject("air_transport"),32000000);airDocument=JsonParser.parseString(new String(airFile.bytes(),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();}
        Path personnelFile=null;JsonObject personnelDocument=null;if(root.has("personnel_lifts")){var personnel=sourceBytesR52(file.getParent(),world,root.getAsJsonObject("personnel_lifts"),32000000);personnelFile=personnel.file();personnelDocument=JsonParser.parseString(new String(personnel.bytes(),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();}
        TvYashimaStationR52.Plan cannon=null;if(root.has("fixed_cannon")){var cannonFile=sourceBytesR52(file.getParent(),world,root.getAsJsonObject("fixed_cannon"),32000000);require(cannonFile.file().equals(world.resolve(TvYashimaStationR52.FILE)),"Fixed cannon must be the actual runtime station file");cannon=TvYashimaStationR52.parse(JsonParser.parseString(new String(cannonFile.bytes(),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject(),root.get("dimension").getAsString());}
        if(cannon!=null)FixedCannonCradleR52.pieces(cannon.geometry(),cannon.cradle(),cannon.closed(),new org.joml.Quaternionf());
        require(bundleSHA.equals(sha(Files.readAllBytes(file))),"Root bundle changed during source preparation");
        return new PreparedBundleR52(directoryDocument,directory,ownerDocument,geometry,airDocument,personnelFile,personnelDocument,cannon);
    }
    private static void verifyCannonFoundationR52(ServerLevel level,TvYashimaStationR52.Plan plan)throws IOException {
        int feet=0;for(var piece:FixedCannonCradleR52.pieces(plan.geometry(),plan.cradle(),plan.closed(),new org.joml.Quaternionf()))if(piece.part().name().equals("floor_plate")){feet++;var b=piece.mesh().envelope(piece.frame(),piece.frame());for(int x=(int)Math.floor(b.minX+.0001);x<=(int)Math.floor(b.maxX-.0001);x++)for(int z=(int)Math.floor(b.minZ+.0001);z<=(int)Math.floor(b.maxZ-.0001);z++){var floor=new BlockPos(x,(int)Math.floor(plan.cradle().floorTop()-.0001),z);if(!level.hasChunkAt(floor)||!level.getBlockState(floor).isCollisionShapeFullBlock(level,floor))throw new IllegalStateException("Actual fixed cannon finite foundation missing: "+floor);}}require(feet==2,"Actual original cannon two finite floor plates required");
    }
    private static void retain(ServerLevel level,ChunkPos at){level.getChunkSource().addRegionTicket(RESTORE_TICKET,at,2,at);}
    private static void captureActorChunksR52(ServerLevel level,NervRouteRuntimeStateR52 saved){for(var id:INSTALLED_ACTORS.getOrDefault(level,Set.of())){var actor=level.getEntity(id);if(actor!=null&&actor.isAlive())saved.installationActorChunkR52(id,new ChunkPos(BlockPos.containing(actor.position())).toLong());}}
    public static String restorationHoldR52(ServerLevel level){return RESTORE_HOLDS.getOrDefault(level,"");}
    @SubscribeEvent(priority=EventPriority.LOWEST) public static void restoreTickR52(TickEvent.ServerTickEvent event){
        if(event.phase!=TickEvent.Phase.END||!NervRouteRuntimeR52.mapRebuildEnabledR52())return;for(var level:event.getServer().getAllLevels()){
            long now=level.getGameTime();Long refreshed=TICKET_REFRESH.get(level);if(refreshed==null||now<refreshed||now-refreshed>=100){for(var chunk:PENDING_TICKETS.getOrDefault(level,Set.of()))retain(level,chunk);TICKET_REFRESH.put(level,now);}
            var saved=NervRouteRuntimeR52.installationStateR52(level);if(saved==null||!saved.claimed()||saved.installationBundle().isEmpty())continue;
            // Keep saved actor chunks eligible for entity loading even while
            // pure source preparation/native commissioning is still held.
            for(var chunk:saved.installationActorChunks().values())retain(level,new ChunkPos(chunk));
            if(NervRouteRuntimeR52.controllerLoadedR52(level)){captureActorChunksR52(level,saved);continue;}
            long tick=level.getGameTime();Long previous=RESTORE_TRIES.get(level);if(previous!=null&&tick>=previous&&tick-previous<100)continue;RESTORE_TRIES.put(level,tick);
            try{require(saved.fault().isEmpty(),saved.fault());String relative=NervRouteRuntimeStateR52.relativeBundleR52(saved.installationBundle());var path=level.getServer().getWorldPath(LevelResource.ROOT).resolve(relative);var result=install(level,path,true);if(!result.accepted())restoreHoldR52(level,result.reason());}
            catch(IOException|RuntimeException held){restoreHoldR52(level,held.toString());}
        }
    }
    private static void restoreHoldR52(ServerLevel level,String reason){String old=RESTORE_HOLDS.put(level,reason);if(!reason.equals(old))com.projectseele.ProjectSeele.LOGGER.warn("R52 persisted installation remains held dimension={} reason={}",level.dimension().location(),reason);}
    private record SourceBytesR52(Path file,byte[] bytes){}
    private static SourceBytesR52 sourceBytesR52(Path parent,Path world,JsonObject source,int maximumBytes)throws IOException {
        String filename=source.get("file").getAsString();var relative=Path.of(filename);require(!relative.isAbsolute()&&relative.getRoot()==null&&!filename.contains(":")&&!relative.normalize().startsWith(".."),"Root-relative component file required");var file=parent.resolve(relative).toRealPath();require(file.startsWith(world)&&file.startsWith(parent.toRealPath())&&Files.size(file)<=maximumBytes,"Bounded same-world Root component file required");
        byte[] bytes;try(var input=Files.newInputStream(file)){bytes=input.readNBytes(maximumBytes+1);}require(bytes.length<=maximumBytes,"Bounded complete Root component required");String expected=source.get("sha256").getAsString();require(expected.matches("[0-9a-f]{64}")&&expected.equals(sha(bytes)),"Root component source SHA differs");return new SourceBytesR52(file,bytes);
    }
    private static Path reference(Path parent,Path world,JsonObject source)throws IOException
    {return reference(parent,world,source,32000000);}
    private static Path reference(Path parent,Path world,JsonObject source,long maximumBytes)throws IOException
    {
        String filename=source.get("file").getAsString();var relative=Path.of(filename);require(!relative.isAbsolute()&&relative.getRoot()==null&&!filename.contains(":")&&!relative.normalize().startsWith(".."),"Root-relative component file required");var file=parent.resolve(relative).toRealPath();require(file.startsWith(world)&&file.startsWith(parent.toRealPath())&&Files.size(file)<=maximumBytes,"Bounded same-world Root component file required");
        String expected=source.get("sha256").getAsString();require(expected.matches("[0-9a-f]{64}")&&expected.equals(shaFileR52(file)),"Root component source SHA differs");return file;
    }
    @SubscribeEvent public static void commands(RegisterCommandsEvent event)
    {
        event.getDispatcher().register(Commands.literal("nerv").then(Commands.literal("r52").requires(source->source.hasPermission(2)).then(Commands.literal("install").then(Commands.argument("world_relative_bundle",StringArgumentType.greedyString()).executes(context->{
            var source=context.getSource();try{String name=NervRouteRuntimeStateR52.relativeBundleR52(StringArgumentType.getString(context,"world_relative_bundle"));var relative=Path.of(name);var result=install(source.getLevel(),source.getServer().getWorldPath(LevelResource.ROOT).resolve(relative));source.sendSuccess(()->Component.literal(result.reason()+" [epoch="+result.epoch()+", directory="+result.directoryFingerprint()+"]"),true);return result.accepted()?1:0;}
            catch(IOException|RuntimeException failure){source.sendFailure(Component.literal("R52 Root installation held: "+failure.getMessage()));return 0;}
        })))));
    }
    private static String sha(byte[] bytes){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}catch(Exception impossible){throw new IllegalStateException(impossible);}}
    private static String shaFileR52(Path file)throws IOException{try{var digest=MessageDigest.getInstance("SHA-256");try(var input=Files.newInputStream(file)){byte[] buffer=new byte[65536];int count;while((count=input.read(buffer))!=-1)digest.update(buffer,0,count);}return HexFormat.of().formatHex(digest.digest());}catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}}
    private static void require(boolean okay,String why){if(!okay)throw new IllegalArgumentException(why);}
    private NervRootAssemblyInstallationR52(){}
}

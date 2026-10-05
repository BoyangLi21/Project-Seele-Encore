package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import net.minecraft.nbt.NbtIo;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.*;
import net.minecraft.network.chat.Component;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.server.ServerStoppedEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.GZIPInputStream;

/** Installed semantic navigation. No QA lease, development path or class-file hash. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class OperatorNavigationProductionR45
{
    private record Cached(ServerLevel level,Path root,int tick,String fingerprint,Optional<OperatorNavigationEngineR45.Contract> value,String failure) { }
    private record Selection(ServerLevel level,String scope) { }
    private static final Map<MinecraftServer,Cached> CACHE=new WeakHashMap<>();
    private static final Map<MinecraftServer,Map<UUID,Selection>> ACTIVE=new WeakHashMap<>();
    private static final String MANIFEST="operator_navigation_manifest_r45.json";
    private static final String GRAPH="operator_return_routes_r45.json.gz";
    private static final String ACCEPTANCE="operator_navigation_acceptance_r45.json";
    private static final String METADATA="r44_tv_personnel_platforms.json";
    private static final String IDENTITY="dimensions/projectseele/geofront/data/projectseele_tokyo3_building_world_id_r44.dat";
    private static final String MODEL_REVISION="R44_TV_PERSONNEL_4639_2A789";
    private static Boolean modelMatches;

    private static String hash(byte[] bytes) throws Exception
    { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)); }
    private static byte[] finite(Path path,long maximum) throws Exception
    { if(Files.size(path)>maximum)throw new IllegalArgumentException("Oversize installed navigation file");return Files.readAllBytes(path); }
    private static JsonObject json(byte[] bytes)
    { return JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject(); }
    private static boolean modelMatches() throws Exception
    {
        if(modelMatches!=null)return modelMatches;
        TvPersonnelSemanticEpochR47.requireModel();modelMatches=true;return true;
    }
    private static Optional<OperatorNavigationEngineR45.Contract> load(ServerLevel level)
    {
        if(!level.dimension().location().toString().equals("projectseele:geofront"))return Optional.empty();
        var server=level.getServer();int tick=server.getTickCount();Path root=server.getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize();var old=CACHE.get(server);
        if(old!=null&&old.level==level&&old.root.equals(root)&&tick-old.tick>=0&&tick-old.tick<40)return old.value;
        Optional<OperatorNavigationEngineR45.Contract> result=Optional.empty();String failure="",fingerprint="";
        try
        {
            if(!Files.exists(root.resolve(MANIFEST)))
            { CACHE.put(server,new Cached(level,root,tick,"",result,"not-installed"));return result; }
            byte[] manifestBytes=finite(root.resolve(MANIFEST),32_000);var manifest=json(manifestBytes);
            if(!"projectseele.operator-navigation-manifest.v1".equals(manifest.get("schema").getAsString())
                    ||!manifest.get("installed_semantic_contract").getAsBoolean()||!manifest.get("fixed_navigation_accepted").getAsBoolean()
                    ||!OperatorNavigationEngineR45.SEMANTIC_REVISION.equals(manifest.get("semantic_revision").getAsString())
                    ||!GRAPH.equals(manifest.get("graph_file").getAsString())||!ACCEPTANCE.equals(manifest.get("acceptance_file").getAsString())
                    ||!METADATA.equals(manifest.get("metadata_file").getAsString())||!IDENTITY.equals(manifest.get("identity_file").getAsString())
                    ||!MODEL_REVISION.equals(manifest.get("model_revision").getAsString())
                    ||!TvPersonnelPlatformInterlockR44.semanticReadyR47(level)||!modelMatches())
                throw new IllegalArgumentException("Installed version/model/acceptance contract unavailable");
            byte[] graphBytes=finite(root.resolve(GRAPH),1_000_000),proofBytes=finite(root.resolve(ACCEPTANCE),64_000);
            String graphHash=hash(graphBytes);
            if(!graphHash.equals(manifest.get("graph_sha256").getAsString())||!hash(proofBytes).equals(manifest.get("acceptance_sha256").getAsString()))
                throw new IllegalArgumentException("Installed graph/acceptance bytes changed");
            // Read the existing identity only. A missing identity is never created/saved.
            if(Files.size(root.resolve(IDENTITY))>64_000)throw new IllegalArgumentException("Oversize identity file");
            String worldId=NbtIo.readCompressed(root.resolve(IDENTITY).toFile()).getCompound("data").getString("WorldUUID");
            UUID.fromString(worldId);
            if(!worldId.equals(manifest.get("world_id").getAsString())||level.getSeed()!=manifest.get("world_seed").getAsLong()
                    ||!level.dimension().location().toString().equals(manifest.get("dimension").getAsString()))throw new IllegalArgumentException("Installed graph belongs to another world identity");
            fingerprint=hash(manifestBytes)+graphHash+hash(proofBytes)+worldId+level.getSeed();
            if(old!=null&&old.level==level&&old.root.equals(root)&&old.value.isPresent()&&fingerprint.equals(old.fingerprint))
            { CACHE.put(server,new Cached(level,root,tick,fingerprint,old.value,""));return old.value; }
            var proof=json(proofBytes);
            if(!"projectseele.operator-navigation-installed-acceptance.v1".equals(proof.get("schema").getAsString())||!proof.get("passed").getAsBoolean()
                    ||!worldId.equals(proof.get("world_id").getAsString())||level.getSeed()!=proof.get("world_seed").getAsLong()
                    ||!graphHash.equals(proof.get("graph_sha256").getAsString())||!OperatorNavigationEngineR45.SEMANTIC_REVISION.equals(proof.get("semantic_revision").getAsString())
                    ||proof.get("actual_fixed_cells_passed").getAsInt()!=202||proof.get("actual_fixed_edges_passed").getAsInt()!=291
                    ||proof.get("actual_gate_scopes_passed").getAsInt()!=6||!proof.get("actual_runtime_negative_states_passed").getAsBoolean()
                    ||!proof.get("source_native_receipt_sha256").getAsString().matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Installed native acceptance does not cover this graph");
            byte[] plain;
            try(var input=new GZIPInputStream(new ByteArrayInputStream(graphBytes)))
            { plain=input.readNBytes(4_000_001);if(plain.length>4_000_000)throw new IllegalArgumentException("Oversize expanded graph"); }
            var graph=json(plain);
            if(!"projectseele.operator-return-semantic-graph.v1".equals(graph.get("schema").getAsString())
                    ||!OperatorNavigationEngineR45.SEMANTIC_REVISION.equals(graph.get("semantic_revision").getAsString())
                    ||!worldId.equals(graph.get("world_id").getAsString())||level.getSeed()!=graph.get("world_seed").getAsLong()
                    ||graph.get("ordinary_public_floor").getAsBoolean()||!level.dimension().location().toString().equals(graph.get("dimension").getAsString()))
                throw new IllegalArgumentException("Wrong installed graph semantics");
            TvPersonnelSemanticEpochR47.requireReferenceAgreement(manifest,proof);
            TvPersonnelSemanticEpochR47.requireReferenceAgreement(manifest,graph);
            result=Optional.of(OperatorNavigationEngineR45.parse(graph));
        }
        catch(Exception rejected)
        {
            failure=rejected.toString();if(old==null||!old.failure.equals(failure))ProjectSeele.LOGGER.warn("Installed operator navigation unavailable: {}",failure);
        }
        CACHE.put(server,new Cached(level,root,tick,fingerprint,result,failure));return result;
    }
    /** Root may connect the actual facility enable path only after installed acceptance. */
    public static boolean installedFacility(ServerLevel level) { return load(level).isPresent(); }
    public static List<String> availableGoals(ServerPlayer player)
    {
        // Do not advertise a development goal, absent installation or disabled real facility.
        return player!=null&&load(player.serverLevel()).isPresent()&&TvPersonnelPlatformInterlockR44.enabled(player.serverLevel())&&TvCageCollisionR44.enabled()
                ?List.of("operator_nearest_lift"):List.of();
    }
    public static OperatorNavigationEngineR45.Result guide(ServerPlayer player) { return guide(player,""); }
    private static OperatorNavigationEngineR45.Result guide(ServerPlayer player,String selected)
    {
        var contract=load(player.serverLevel());
        if(contract.isEmpty())return new OperatorNavigationEngineR45.Result(OperatorNavigationEngineR45.Status.UNBOUND,selected,null,null,"当前存档尚未安装有效的人员区返回导航，请使用现场出口标牌。",false);
        return OperatorNavigationEngineR45.guide(player,contract.get(),selected);
    }
    public static String start(ServerPlayer player)
    {
        stop(player);var result=guide(player);boolean waiting=Set.of(OperatorNavigationEngineR45.Status.GATE_CLOSED,OperatorNavigationEngineR45.Status.OCCUPIED,
                OperatorNavigationEngineR45.Status.MACHINE_UNAVAILABLE,OperatorNavigationEngineR45.Status.UNLOADED).contains(result.status())&&!result.scope().isEmpty();
        if(result.status()!=OperatorNavigationEngineR45.Status.READY&&result.status()!=OperatorNavigationEngineR45.Status.ARRIVED&&!waiting)return result.instruction();
        NervWayfindingR24.start(player,"stop");
        if(!result.arrived())ACTIVE.computeIfAbsent(player.server,k->new HashMap<>()).put(player.getUUID(),new Selection(player.serverLevel(),result.scope()));
        return waiting||result.arrived()?result.instruction():"已开启人员区返回本层电梯的引导；安全门与设备状态会实时检查。";
    }
    public static void stop(ServerPlayer player)
    { var active=ACTIVE.get(player.server);if(active!=null)active.remove(player.getUUID()); }
    public static JsonObject diagnostic(ServerPlayer player)
    {
        var result=guide(player);var json=new JsonObject();json.addProperty("status",result.status().name());json.addProperty("scope",result.scope());
        json.addProperty("instruction",result.instruction());json.addProperty("arrived",result.arrived());json.addProperty("installed_contract",load(player.serverLevel()).isPresent());
        json.addProperty("ordinary_public_floor",false);json.addProperty("world_written",false);json.addProperty("live_dynamic_inspection_bound",false);
        json.add("here_feet",vector(result.here()));json.add("next_feet",vector(result.next()));return json;
    }
    private static JsonElement vector(Vec3 v)
    { if(v==null)return JsonNull.INSTANCE;var row=new JsonArray();row.add(v.x);row.add(v.y);row.add(v.z);return row; }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||event.getServer().getTickCount()%20!=0)return;var selections=ACTIVE.get(event.getServer());if(selections==null)return;
        for(var e:List.copyOf(selections.entrySet()))
        {
            var player=event.getServer().getPlayerList().getPlayer(e.getKey());
            if(player==null||player.serverLevel()!=e.getValue().level){selections.remove(e.getKey());continue;}
            var result=guide(player,e.getValue().scope);player.displayClientMessage(Component.literal("人员区返回 · "+result.instruction()),true);
            if(result.arrived())selections.remove(e.getKey());
        }
    }
    @SubscribeEvent public static void stopped(ServerStoppedEvent event)
    { CACHE.remove(event.getServer());ACTIVE.remove(event.getServer()); }
    private OperatorNavigationProductionR45() { }
}

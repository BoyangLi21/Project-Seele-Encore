package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import java.io.BufferedWriter;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.zip.GZIPOutputStream;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.EntityBlock;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Native placed features against an in-memory overlay; never a map writer. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class RegionalEcologyRetrofitR44
{
    private static final String JOB=System.getProperty("projectseele.r44EcologyJob","");
    private static boolean done;private static int age,index;
    private static JsonObject job;private static ServerLevel level;private static List<Path> jobs;private static int batch;
    private static Path active;private static long exportedCells,completedOrigins;
    private static NativeEcologyPlanLedgerR44 ledger;
    private static final int BATCH_CELL_LIMIT=Math.max(65536,Math.min(1048576,Integer.getInteger("projectseele.r44EcologyBatchCellLimit",1048576)));
    private static final int FEATURE_CELL_LIMIT=65536;
    private static long batchPeakCells,batchPeakPending,batchStartedNanos,batchPeakHeap;
    private static int batchLoadedStart,batchLoadedPeak;
    private static final Map<BlockPos,BlockState> overlay=new LinkedHashMap<>();
    private static final Map<BlockPos,BlockState> baseline=new LinkedHashMap<>();
    private static final Map<BlockPos,String> overlayNBT=new HashMap<>();
    private static final JsonArray trials=new JsonArray();
    private static final JsonArray originResults=new JsonArray();
    private static final JsonArray biomePlans=new JsonArray();
    private static final JsonArray blockPlanPaths=new JsonArray();
    private static Set<Long> available;
    private static List<int[]> reservations;
    private static List<int[]> protectedVolumes=List.of();
    private static List<int[]> belowReservations;
    private static final Set<String> SOIL=Set.of("grass_block","dirt","coarse_dirt","rooted_dirt","podzol","mud","mycelium","sand","gravel");

    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(JOB.isEmpty()||done||event.phase!=TickEvent.Phase.END)return;
        Path world=event.getServer().getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize();
        if(!world.getFileName().toString().equals(com.projectseele.visual.NativeReviewWorldsR45.expectedName()))
            throw new IllegalStateException("Ecology dry run refuses a different world identity");
        try
        {
            if(++age<40)return;
            if(jobs==null)
            {
                JsonObject input=JsonParser.parseString(Files.readString(Path.of(JOB),StandardCharsets.UTF_8)).getAsJsonObject();
                jobs=new ArrayList<>();
                if(input.has("jobs"))for(JsonElement p:input.getAsJsonArray("jobs"))jobs.add(Path.of(p.getAsString()));
                else jobs.add(Path.of(JOB));
                Path inputPath=Path.of(JOB).toAbsolutePath();
                if(input.has("require_staging_controls")&&input.get("require_staging_controls").getAsBoolean())
                {
                    JsonObject proof=NativeEcologyFeatureControlsR44.verify(event.getServer().getLevel(FacilitySchemaV2.DIMENSION));
                    Files.writeString(inputPath.resolveSibling(inputPath.getFileName()+".staging_controls.json"),proof.toString(),StandardCharsets.UTF_8);
                }
                ledger=new NativeEcologyPlanLedgerR44(inputPath.resolveSibling(inputPath.getFileName()+".ledger_"+System.currentTimeMillis()));
            }
            if(batch>=jobs.size())
            {
                JsonObject result=new JsonObject();result.addProperty("complete",true);result.addProperty("batches",batch);
                result.addProperty("exported_cells",exportedCells);result.addProperty("world_changed",false);
                result.addProperty("completed_origins",completedOrigins);result.addProperty("input_manifest",Path.of(JOB).toAbsolutePath().toString());
                ledger.flush();result.addProperty("ledger_directory",ledger.root().toString());
                result.add("merged_biome_plans",ledger.exportMergedBiomes(ledger.root().resolve("merged_exports")));
                result.add("block_plans",blockPlanPaths);
                result.addProperty("per_batch_biomes_applyable",false);result.addProperty("cross_batch_vegetation_cells_disjoint",true);
                result.addProperty("batch_cell_limit",BATCH_CELL_LIMIT);result.addProperty("single_feature_cell_limit",FEATURE_CELL_LIMIT);result.addProperty("disk_cache_section_limit",96);
                Files.writeString(Path.of(JOB).resolveSibling(Path.of(JOB).getFileName()+".complete.json"),result.toString(),StandardCharsets.UTF_8);
                done=true;return;
            }
            if(job==null)
            {
                active=jobs.get(batch);
                job=JsonParser.parseString(Files.readString(active,StandardCharsets.UTF_8)).getAsJsonObject();
                if(job.getAsJsonArray("chunks").size()>128)throw new IllegalStateException("Ecology input exceeds the bounded 128-origin batch contract");
                if(!job.get("world").getAsString().equals(world.toString().replace('\\','/')))
                    throw new IllegalStateException("Ecology job was measured in another world");
                level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);
                if(job.get("seed").getAsLong()!=level.getSeed())throw new IllegalStateException("Ecology world seed changed after measurement");
                batchStartedNanos=System.nanoTime();batchLoadedStart=level.getChunkSource().getLoadedChunksCount();batchLoadedPeak=batchLoadedStart;
                available=new HashSet<>();
                for(JsonElement p:job.getAsJsonArray("available_chunks"))
                {JsonArray q=p.getAsJsonArray();available.add(chunkKey(q.get(0).getAsInt(),q.get(1).getAsInt()));}
                if(available.size()>1152)throw new IllegalStateException("Ecology batch exceeds 128 measured 3x3 neighbourhoods");
                reservations=new ArrayList<>();for(JsonElement p:job.getAsJsonArray("reserved_bounds"))
                {JsonArray q=p.getAsJsonArray();reservations.add(new int[]{q.get(0).getAsInt(),q.get(1).getAsInt(),q.get(2).getAsInt(),q.get(3).getAsInt()});}
                belowReservations=new ArrayList<>();for(JsonElement p:job.getAsJsonArray("underground_reserved_bounds"))
                {JsonArray q=p.getAsJsonArray();belowReservations.add(new int[]{q.get(0).getAsInt(),q.get(1).getAsInt(),q.get(2).getAsInt(),q.get(3).getAsInt()});}
                protectedVolumes=new ArrayList<>();
                if(job.has("protected_volumes"))for(JsonElement p:job.getAsJsonArray("protected_volumes"))
                {
                    JsonArray q=p.getAsJsonArray();if(q.size()!=6)throw new IllegalStateException("Infrastructure protection volume needs six exact coordinates");
                    int[] r=new int[6];for(int i=0;i<6;i++)r[i]=q.get(i).getAsInt();
                    if(r[0]>r[3]||r[1]>r[4]||r[2]>r[5])throw new IllegalStateException("Inverted infrastructure protection volume");
                    protectedVolumes.add(r);
                }
                var installedSource=(RegionalEcologyBiomeSourceR44)level.getChunkSource().getGenerator().getBiomeSource();
                var declaredVolumes=protectedVolumes.stream().map(r->java.util.Arrays.stream(r).boxed().toList()).toList();
                if(!installedSource.protectedVolumes().equals(declaredVolumes))
                    throw new IllegalStateException("Installed future ecology 3D protection differs from retrofit input; freeze and install one exact provider configuration before this native run");
            }
            JsonArray chunks=job.getAsJsonArray("chunks");
            if(index<chunks.size())
            {
                JsonObject q=chunks.get(index++).getAsJsonObject();runChunk(q);completedOrigins++;
                batchLoadedPeak=Math.max(batchLoadedPeak,level.getChunkSource().getLoadedChunksCount());
                Runtime runtime=Runtime.getRuntime();batchPeakHeap=Math.max(batchPeakHeap,runtime.totalMemory()-runtime.freeMemory());
                return;
            }
            export(null);ledger.mergeBiomes(level,biomePlans);
            overlay.forEach((p,state)->{if(!state.equals(baseline.get(p)))ledger.put(p,state,overlayNBT.get(p));});
            ledger.flush();exportedCells+=overlay.entrySet().stream().filter(e->!e.getValue().equals(baseline.get(e.getKey()))).count();
            JsonObject plan=new JsonObject();String stem=active.getFileName().toString().replace(".json","");
            plan.addProperty("forward",active.toAbsolutePath().getParent().resolve(stem+".forward.jsonl.gz").toString());
            plan.addProperty("inverse",active.toAbsolutePath().getParent().resolve(stem+".inverse.jsonl.gz").toString());
            plan.addProperty("job",active.toAbsolutePath().toString());plan.addProperty("result",active.toAbsolutePath().getParent().resolve(stem+".result.json").toString());blockPlanPaths.add(plan);
            batch++;index=0;job=null;batchPeakCells=0;batchPeakPending=0;batchPeakHeap=0;
            overlay.clear();baseline.clear();overlayNBT.clear();trials.asList().clear();originResults.asList().clear();biomePlans.asList().clear();available.clear();
            // No forced tickets are acquired. Vanilla's short UNKNOWN load
            // tickets expire normally; this batch retains no chunk references.
        }
        catch(Throwable error)
        {
            try{export(error.toString());}catch(Exception failure){ProjectSeele.LOGGER.error("Cannot write ecology failure",failure);}
            try
            {
                JsonObject failure=new JsonObject();failure.addProperty("error",error.toString());failure.addProperty("batch",batch);
                failure.addProperty("active_job",active==null?JOB:active.toString());failure.addProperty("tile_cursor",index);
                Files.writeString(Path.of(JOB+".failed.json"),failure.toString(),StandardCharsets.UTF_8);
            }
            catch(Exception failure){ProjectSeele.LOGGER.error("Cannot write ecology failure marker",failure);}
            done=true;ProjectSeele.LOGGER.error("Ecology dry run failed",error);
        }
    }

    private static void runChunk(JsonObject chunk) throws Exception
    {
        int cx=chunk.get("x").getAsInt(),cz=chunk.get("z").getAsInt();
        long originStarted=System.nanoTime();JsonObject origin=chunk.deepCopy();origin.addProperty("completed",false);
        int radius=job.has("biome_only")&&job.get("biome_only").getAsBoolean()?0:1;
        for(int z=cz-radius;z<=cz+radius;z++)for(int x=cx-radius;x<=cx+radius;x++)
        {
            if(!available.contains(chunkKey(x,z)))throw new IllegalStateException("Unmeasured feature neighbourhood");
            level.getChunk(x,z);
        }
        boolean underground=chunk.get("layer").getAsString().equals("geofront");
        NativeEcologyBiomesR44.plan(level,chunk,reservations,belowReservations,biomePlans);
        if(job.has("biome_only")&&job.get("biome_only").getAsBoolean())
        {origin.addProperty("biome_only",true);origin.addProperty("completed",true);origin.addProperty("feature_calls",0);originResults.add(origin);return;}
        if(!chunk.has("biome"))throw new IllegalStateException("Vegetation tile schema requires a registered biome; biome-only tiles do not");
        Holder<Biome> biome=level.registryAccess().registryOrThrow(Registries.BIOME).getHolderOrThrow(
                ResourceKey.create(Registries.BIOME,new ResourceLocation(chunk.get("biome").getAsString())));
        RegionalEcologyBiomeSourceR44 source=(RegionalEcologyBiomeSourceR44)level.getChunkSource().getGenerator().getBiomeSource();
        int centreGround=80;
        try{centreGround=ground(cx*16+8,cz*16+8,underground);}
        catch(Clipped missingCentre){origin.addProperty("centre_soil_measurement_error",missingCentre.getMessage());}
        Holder<Biome> centreBiome=underground?source.ecologicalBiomeBelow(cx*16+8,cz*16+8,level.getChunkSource().randomState().sampler())
                :source.ecologicalBiome(cx*16+8,centreGround,cz*16+8,level.getChunkSource().randomState().sampler());
        origin.addProperty("runtime_centre_ground",centreGround);origin.addProperty("runtime_centre_biome",centreBiome.unwrapKey().orElseThrow().location().toString());
        origin.addProperty("declared_biome_matches_runtime_centre",biome.equals(centreBiome));
        List<Holder<PlacedFeature>> features=biome.value().getGenerationSettings().features().get(9).stream().toList();
        origin.addProperty("feature_calls",features.size());JsonArray featureKeys=new JsonArray();
        for(Holder<PlacedFeature> feature:features)featureKeys.add(feature.unwrapKey().map(k->k.location().toString()).orElse("unregistered"));
        origin.add("registered_feature_order",featureKeys);
        for(int i=0;i<features.size();i++)
        {
            long featureStarted=System.nanoTime();
            Map<BlockPos,BlockState> pending=new LinkedHashMap<>();boolean[] clipped={false};
            JsonArray protectionHits=new JsonArray();int[] rejectedWrites={0};
            Map<Long,LevelChunk> scratchChunks=new HashMap<>();
            Map<BlockPos,BlockEntity> scratchEntities=new HashMap<>();
            long seed=level.getSeed()^cx*341873128712L^cz*132897987541L^i*0x9e3779b97f4a7c15L;
            WorldGenLevel proxy=(WorldGenLevel)Proxy.newProxyInstance(WorldGenLevel.class.getClassLoader(),
                    new Class<?>[]{WorldGenLevel.class},(self,method,args)->
            {
                args=args==null?new Object[0]:args;
                String name=method.getName();BlockPos p=args.length>0&&args[0] instanceof BlockPos pos?pos:null;
                if(name.equals("getLevel"))return level;
                if(name.equals("getRandom"))return RandomSource.create(seed);
                if(name.equals("getSeed"))return level.getSeed();
                if(name.equals("getBiome")||name.equals("getNoiseBiome"))return biome;
                if(name.equals("ensureCanWrite"))
                {boolean safe=p!=null&&allowed(p,underground);if(!safe){clipped[0]=true;rejectedWrites[0]++;hit(protectionHits,p,null,"Authored/virtual railway or measured-chunk write boundary");}return safe;}
                if(name.equals("setCurrentlyGenerating"))return null;
                if(name.equals("getBlockState")||name.equals("getFluidState"))
                {
                    requireMeasured(p);BlockState state=read(p,pending);
                    return name.equals("getFluidState")?state.getFluidState():state;
                }
                if(name.equals("getBlockEntity")&&args.length==1)
                {
                    requireMeasured(p);
                    if(scratchEntities.containsKey(p))return scratchEntities.get(p);
                    BlockState state=read(p,pending);
                    if(!state.hasBlockEntity())return null;
                    String saved=overlayNBT.getOrDefault(p,ledger.nbt(p));BlockEntity actual=level.getBlockEntity(p),copy;
                    if(saved!=null)copy=BlockEntity.loadStatic(p,state,net.minecraft.nbt.TagParser.parseTag(saved));
                    else if(actual!=null)copy=BlockEntity.loadStatic(p,state,actual.saveWithFullMetadata().copy());
                    else copy=((EntityBlock)state.getBlock()).newBlockEntity(p,state);
                    if(copy==null){clipped[0]=true;return null;}
                    scratchEntities.put(p.immutable(),copy);return copy;
                }
                if(name.equals("setBlock"))
                {
                    requireMeasured(p);BlockState before=read(p,pending);
                    if(!allowed(p,underground)||ledger.owns(p)||!natural(before)||protectedPlant(level.getBlockState(p))||level.getBlockEntity(p)!=null)
                    {clipped[0]=true;rejectedWrites[0]++;hit(protectionHits,p,before,"Preserve authored/rail reservation, non-natural source, existing vegetation or full block entity");return false;}
                    budget(p,pending);BlockState state=(BlockState)args[1];pending.put(p.immutable(),state);
                    if(state.hasBlockEntity())scratchEntities.put(p.immutable(),((EntityBlock)state.getBlock()).newBlockEntity(p,state));
                    else scratchEntities.remove(p);return true;
                }
                if(name.equals("getHeight")&&args!=null&&args.length==3&&args[0] instanceof Heightmap.Types)
                {
                    int x=(Integer)args[1],z=(Integer)args[2];requireMeasured(new BlockPos(x,80,z));
                    int floor=ground(x,z,underground);return floor==Integer.MIN_VALUE?level.getMinBuildHeight():floor+1;
                }
                if(name.equals("getHeight")&&args!=null&&args.length==2&&args[1] instanceof BlockPos point)
                    return new BlockPos(point.getX(),ground(point.getX(),point.getZ(),underground)+1,point.getZ());
                if(name.equals("getChunk")&&args.length>0&&(args[0] instanceof BlockPos||args.length>=2&&args[0] instanceof Integer&&args[1] instanceof Integer))
                {
                    int x=args[0] instanceof BlockPos point?point.getX()>>4:(Integer)args[0];
                    int z=args[0] instanceof BlockPos point?point.getZ()>>4:(Integer)args[1];
                    if(!available.contains(chunkKey(x,z)))throw new Clipped("Feature read crossed the measured chunk neighbourhood");
                    // Feature leaf propagation may mark post-processing inside
                    // ChunkAccess. Give it a detached chunk, never the real one.
                    if(!scratchChunks.containsKey(chunkKey(x,z))&&scratchChunks.size()>=16)throw new IllegalStateException("Native feature exceeded detached scratch chunk limit 16; retain failed batch evidence and inspect its registered feature");
                    return scratchChunks.computeIfAbsent(chunkKey(x,z),key->new LevelChunk(level,new ChunkPos(x,z))
                    {
                        @Override public BlockState getBlockState(BlockPos at)
                        {requireMeasured(at);return read(at,pending);}
                        @Override public net.minecraft.world.level.material.FluidState getFluidState(BlockPos at)
                        {return getBlockState(at).getFluidState();}
                        @Override public BlockState setBlockState(BlockPos at,BlockState state,boolean moving)
                        {
                            BlockState before=getBlockState(at);
                            if(!allowed(at,underground)||ledger.owns(at)||!natural(before)||protectedPlant(level.getBlockState(at))||level.getBlockEntity(at)!=null){clipped[0]=true;rejectedWrites[0]++;hit(protectionHits,at,before,"Detached-chunk write reached protected source/reservation or a complete feature from a prior batch");return null;}
                            budget(at,pending);pending.put(at.immutable(),state);return before;
                        }
                    });
                }
                if(name.equals("addFreshEntity")||name.equals("destroyBlock")||name.equals("removeBlock")
                        ||name.equals("setBlockEntity")||name.equals("removeBlockEntity"))throw new Clipped("Unexpected non-vegetation mutation: "+name);
                if(name.equals("scheduleTick")||name.equals("blockUpdated")||name.equals("levelEvent")||name.equals("gameEvent"))return null;
                if(method.isDefault())return InvocationHandler.invokeDefault(self,method,args==null?new Object[0]:args);
                return method.invoke(level,args);
            });
            boolean placed=false;String failure="";
            try
            {
                int originGround=ground(cx*16,cz*16,underground);
                placed=features.get(i).value().placeWithBiomeCheck(proxy,level.getChunkSource().getGenerator(),
                        RandomSource.create(seed),new BlockPos(cx*16,originGround==Integer.MIN_VALUE?level.getMinBuildHeight():originGround+1,cz*16));
            }
            catch(Clipped error){clipped[0]=true;failure=error.getMessage();}
            boolean accepted=NativeEcologyFeatureProtectionR44.acceptsCompletedFeature(placed,clipped[0]);
            long acceptedChanged=accepted?pending.entrySet().stream().filter(e->!e.getValue().equals(read(e.getKey(),Map.of()))).count():0;
            if(accepted)pending.forEach((p,state)->
            {
                baseline.putIfAbsent(p,level.getBlockState(p));overlay.put(p,state);
                BlockEntity entity=scratchEntities.get(p);
                if(state.hasBlockEntity())
                {
                    if(entity==null)entity=((EntityBlock)state.getBlock()).newBlockEntity(p,state);
                    if(entity==null)throw new IllegalStateException("Native feature produced an unsupported block entity");
                    overlayNBT.put(p,entity.saveWithFullMetadata().toString());
                }
                else overlayNBT.remove(p);
            });
            JsonObject row=new JsonObject();row.addProperty("chunk",cx+","+cz);row.addProperty("layer",underground?"geofront":"surface");
            row.addProperty("feature",features.get(i).unwrapKey().map(k->k.location().toString()).orElse("unregistered"));
            row.addProperty("placed",placed);row.addProperty("rolled_back_for_protection",clipped[0]);
            row.addProperty("rolled_back_for_native_false_result",!placed&&!clipped[0]);
            row.addProperty("candidate_cells",pending.size());row.addProperty("rejected_write_attempts",rejectedWrites[0]);row.add("first_protection_hits",protectionHits);
            row.addProperty("accepted_changed_cells_against_logical_before",acceptedChanged);row.addProperty("detached_scratch_chunks",scratchChunks.size());
            row.addProperty("elapsed_ms",(System.nanoTime()-featureStarted)/1000000D);
            row.addProperty("reason",failure.isEmpty()&&clipped[0]?"Whole feature rolled back; see first_protection_hits":failure);trials.add(row);
        }
        origin.addProperty("completed",true);origin.addProperty("elapsed_ms",(System.nanoTime()-originStarted)/1000000D);originResults.add(origin);
    }

    private static int ground(int x,int z,boolean underground)
    {
        if(!underground)
            return NativeEcologyFeatureProtectionR44.surfaceGround(x,z,level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,x,z)-1,
                    p->read(p,Map.of()),(RegionalEcologyBiomeSourceR44)level.getChunkSource().getGenerator().getBiomeSource());
        for(int y=-430;y>=-510;y--)
        {
            BlockState state=overlay.getOrDefault(new BlockPos(x,y,z),level.getBlockState(new BlockPos(x,y,z)));
            if(SOIL.contains(BuiltInRegistries.BLOCK.getKey(state.getBlock()).getPath()))return y;
        }
        throw new Clipped("No measured underground soil column");
    }
    private static BlockState read(BlockPos p,Map<BlockPos,BlockState> pending)
    {
        BlockState state=pending.get(p);if(state!=null)return state;state=overlay.get(p);
        return state==null?ledger.read(p,level.getBlockState(p)):state;
    }
    private static void budget(BlockPos p,Map<BlockPos,BlockState> pending)
    {
        long next=pending.size()+(pending.containsKey(p)?0:1);
        batchPeakPending=Math.max(batchPeakPending,next);batchPeakCells=Math.max(batchPeakCells,overlay.size()+next);
        if(next>FEATURE_CELL_LIMIT||overlay.size()+next>BATCH_CELL_LIMIT)
            throw new IllegalStateException("Native ecology bounded resource limit reached; pending="+next+" batch="+(overlay.size()+next)+". Batch is failed, not a successful protected feature; use smaller origins per input in the same JVM.");
    }
    private static boolean natural(BlockState state)
    {
        return NativeEcologyFeatureProtectionR44.naturalSource(state);
    }
    private static boolean allowed(BlockPos p,boolean underground)
    {
        if(!available.contains(chunkKey(p.getX()>>4,p.getZ()>>4)))return false;
        if(underground?(p.getY()<-512||p.getY()>-405):(p.getY()<60||p.getY()>310))return false;
        for(int[] r:protectedVolumes)if(p.getX()>=r[0]&&p.getY()>=r[1]&&p.getZ()>=r[2]&&p.getX()<=r[3]&&p.getY()<=r[4]&&p.getZ()<=r[5])return false;
        for(int[] r:underground?belowReservations:reservations)if(p.getX()>=r[0]&&p.getZ()>=r[1]&&p.getX()<=r[2]&&p.getZ()<=r[3])return false;
        return true;
    }
    private static void requireMeasured(BlockPos p)
    {if(p==null||!available.contains(chunkKey(p.getX()>>4,p.getZ()>>4)))throw new Clipped("Unmeasured feature read");}
    private static long chunkKey(int x,int z){return ((long)x<<32)^(z&0xffffffffL);}
    public static String state(BlockState s)
    {
        StringBuilder text=new StringBuilder(BuiltInRegistries.BLOCK.getKey(s.getBlock()).toString());
        if(!s.getValues().isEmpty())
        {
            List<String> props=new ArrayList<>();s.getValues().forEach((p,v)->props.add(p.getName()+"="+v.toString().toLowerCase(Locale.ROOT)));
            Collections.sort(props);text.append('[').append(String.join(",",props)).append(']');
        }
        return text.toString();
    }
    private static void export(String error) throws Exception
    {
        Path current=active==null?Path.of(JOB):active;
        Path root=current.toAbsolutePath().getParent();String base=current.getFileName().toString().replace(".json","");
        if(error==null&&job!=null)
        {
            Set<String> origins=new HashSet<>();
            for(JsonElement raw:job.getAsJsonArray("chunks"))
            {JsonObject q=raw.getAsJsonObject();origins.add(q.get("x").getAsInt()+","+q.get("z").getAsInt()+","+q.get("layer").getAsString());}
            for(Map.Entry<BlockPos,BlockState> e:overlay.entrySet())
            {
                BlockPos p=e.getKey();if(e.getValue().equals(baseline.get(p)))continue;
                String layer=p.getY()<0?"geofront":"surface";int x=p.getX()>>4,z=p.getZ()>>4;
                if(!origins.add(x+","+z+","+layer))continue;
                JsonObject halo=new JsonObject();halo.addProperty("x",x);halo.addProperty("z",z);halo.addProperty("layer",layer);
                NativeEcologyBiomesR44.plan(level,halo,reservations,belowReservations,biomePlans);
            }
        }
        for(boolean inverse:new boolean[]{false,true})
            try(BufferedWriter out=new BufferedWriter(new java.io.OutputStreamWriter(new GZIPOutputStream(Files.newOutputStream(
                    root.resolve(base+(inverse?".inverse.jsonl.gz":".forward.jsonl.gz")))),StandardCharsets.UTF_8)))
            {
                for(Map.Entry<BlockPos,BlockState> entry:overlay.entrySet())
                {
                    BlockPos p=entry.getKey();BlockState before=baseline.get(p),after=entry.getValue();if(before.equals(after))continue;
                    JsonObject row=new JsonObject();JsonArray pos=new JsonArray();pos.add(p.getX());pos.add(p.getY());pos.add(p.getZ());row.add("pos",pos);
                    row.addProperty("before",state(inverse?after:before));row.addProperty("after",state(inverse?before:after));
                    row.addProperty("before_nbt",inverse?overlayNBT.get(p):null);
                    row.addProperty("after_nbt",inverse?null:overlayNBT.get(p));
                    row.addProperty("owner","r44/native_ecology");row.addProperty("reason","Native placed feature, measured natural ground, protected authored reservations");
                    out.write(row.toString());out.newLine();
                }
            }
        JsonObject summary=new JsonObject();summary.addProperty("error",error);summary.addProperty("native_preview_complete",error==null);
        summary.addProperty("changed_existing_world",false);summary.addProperty("chunks_processed",index);summary.addProperty("cells",overlay.size());
        summary.addProperty("changed_cells",overlay.entrySet().stream().filter(e->!e.getValue().equals(baseline.get(e.getKey()))).count());
        summary.add("origin_results",originResults);summary.addProperty("completed_origins_in_batch",originResults.size());
        summary.addProperty("biome_sections_updated",false);summary.addProperty("native_playable_validation",false);summary.add("feature_trials",trials);
        summary.addProperty("planned_biome_sections",biomePlans.size());summary.addProperty("native_halo_biome_plan_included",error==null);
        summary.addProperty("per_batch_biomes_applyable",false);summary.addProperty("use_final_manifest_merged_biome_plans",true);
        summary.addProperty("prior_batch_feature_ownership_disk_ledger",ledger==null?null:ledger.root().toString());
        summary.addProperty("batch_peak_combined_candidate_cells",batchPeakCells);summary.addProperty("single_feature_peak_pending_cells",batchPeakPending);
        summary.addProperty("batch_cell_limit",BATCH_CELL_LIMIT);summary.addProperty("single_feature_cell_limit",FEATURE_CELL_LIMIT);summary.addProperty("maximum_detached_scratch_chunks",16);summary.addProperty("disk_cache_section_limit",96);
        Runtime runtime=Runtime.getRuntime();summary.addProperty("jvm_used_heap_bytes",runtime.totalMemory()-runtime.freeMemory());summary.addProperty("jvm_committed_heap_bytes",runtime.totalMemory());
        summary.addProperty("jvm_max_heap_bytes",runtime.maxMemory());summary.addProperty("jvm_sampled_peak_used_heap_bytes",Math.max(batchPeakHeap,runtime.totalMemory()-runtime.freeMemory()));
        summary.addProperty("loaded_chunks_at_batch_start",batchLoadedStart);summary.addProperty("sampled_peak_loaded_chunks",level==null?batchLoadedPeak:Math.max(batchLoadedPeak,level.getChunkSource().getLoadedChunksCount()));
        summary.addProperty("batch_elapsed_ms",batchStartedNanos==0?0:(System.nanoTime()-batchStartedNanos)/1000000D);
        Files.writeString(root.resolve(base+".result.json"),new GsonBuilder().setPrettyPrinting().create().toJson(summary),StandardCharsets.UTF_8);
        Files.writeString(root.resolve(base+".biomes.forward.json"),biomePlans.toString(),StandardCharsets.UTF_8);
        JsonArray inverse=new JsonArray();for(JsonElement item:biomePlans)
        {
            JsonObject row=item.getAsJsonObject().deepCopy();JsonElement before=row.get("before_snbt"),names=row.get("before_names");
            row.add("before_snbt",row.get("after_snbt"));row.add("after_snbt",before);
            row.add("before_names",row.get("after_names"));row.add("after_names",names);inverse.add(row);
        }
        Files.writeString(root.resolve(base+".biomes.inverse.json"),inverse.toString(),StandardCharsets.UTF_8);
    }
    private static boolean protectedPlant(BlockState state)
    {
        return NativeEcologyFeatureProtectionR44.protectedExistingPlant(state);
    }
    private static void hit(JsonArray hits,BlockPos p,BlockState state,String reason)
    {
        if(hits.size()>=16)return;JsonObject hit=new JsonObject();
        if(p!=null){JsonArray q=new JsonArray();q.add(p.getX());q.add(p.getY());q.add(p.getZ());hit.add("pos",q);}
        if(state!=null)hit.addProperty("source",RegionalEcologyRetrofitR44.state(state));
        hit.addProperty("reason",reason);hits.add(hit);
    }
    private static final class Clipped extends RuntimeException{Clipped(String reason){super(reason);}}
    private RegionalEcologyRetrofitR44(){}
}

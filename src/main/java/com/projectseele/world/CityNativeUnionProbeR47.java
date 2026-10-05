package com.projectseele.world;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.projectseele.compat.CityUnionOwnerR47;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.levelgen.structure.templatesystem.StructureTemplate.StructureBlockInfo;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.server.ServerStoppingEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Root's single native representative: real complete input, no world/owner/provider mutation. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class CityNativeUnionProbeR47
{
    private static final String BASE="com.simibubi.create.content.contraptions.Contraption";
    private static final Set<String> STARTED=ConcurrentHashMap.newKeySet();
    private static final Map<String,ExecutorService> WORKERS=new ConcurrentHashMap<>();
    private static final String CENTRE=System.getProperty("projectseele.r47CityUnionProbeCentre","");
    private static int serverTicks;
    private CityNativeUnionProbeR47() {}
    @SubscribeEvent public static void serverTick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||System.getProperty("projectseele.r47CityUnionServerProbe","").isBlank()||++serverTicks%20!=0)return;
        String scope=event.getServer().isDedicatedServer()?"forgeserver":"INTEGRATED_SERVER";
        for(var level:event.getServer().getAllLevels())observe(level,level.getAllEntities(),scope,"projectseele.r47CityUnionServerProbe");
    }
    @SubscribeEvent public static void serverStop(ServerStoppingEvent event)
    {WORKERS.forEach((scope,worker)->{if(!scope.equals("forgeclient"))worker.shutdownNow();});}

    /** Called only by physical-side ticks; merely waits for the actual tracked city owner. */
    public static void observe(Level level,Iterable<? extends Entity> entities,String scope,String property)
    {
        String output=System.getProperty(property,"");if(output.isBlank()||STARTED.contains(scope))return;
        try
        {
            require(!CENTRE.isBlank(),"Explicit actual representative centre x,z required");
            String[] xy=CENTRE.split(",");require(xy.length==2,"Representative centre must be x,z");
            int x=Integer.parseInt(xy[0]),z=Integer.parseInt(xy[1]);
            Class<?> base=Class.forName(BASE);Field anchor=base.getDeclaredField("anchor");anchor.setAccessible(true);
            Field provider=base.getDeclaredField("simplifiedEntityColliderProvider");provider.setAccessible(true);
            for(Entity entity:entities)
            {
                if(!entity.isAlive()||!entity.getClass().getName().equals("com.simibubi.create.content.contraptions.OrientedContraptionEntity"))continue;
                Object live=entity.getClass().getMethod("getContraption").invoke(entity);
                if(!(live instanceof CityUnionOwnerR47 owner)||!owner.seele$fullCityFrameR47())continue;
                BlockPos pos=(BlockPos)anchor.get(live);if(pos.getX()!=x||pos.getZ()!=z)continue;
                var future=(java.util.concurrent.CompletableFuture<?>)provider.get(live);
                if(future==null||!future.isDone()||future.isCompletedExceptionally()||future.isCancelled())continue;
                require(owner.seele$balancedSupplierUsedR47(),"The actual selected owner's normal native future did not use the balanced branch");
                Path target=Path.of(output);require(target.isAbsolute(),"Native probe output must be an explicit absolute artifact path");
                require(!Files.exists(target),"Never overwrite a previous native execution receipt");
                Map<BlockPos,StructureBlockInfo> original=blocks(live);
                require(!original.isEmpty(),"Actual complete representative cargo absent");
                CompoundTag payload=((CompoundTag)base.getMethod("writeNBT",boolean.class).invoke(live,false)).copy();
                // Main-thread native serialization is the complete immutable
                // input. No live actor, journal, world or progress is rewritten.
                Map<BlockPos,StructureBlockInfo> fullInput=new java.util.LinkedHashMap<>();
                original.forEach((key,info)->fullInput.put(key,new StructureBlockInfo(info.pos(),info.state(),info.nbt()==null?null:info.nbt().copy())));
                Vec3 position=entity.position();String uuid=entity.getStringUUID();
                JsonObject before=CityExactShapeUnionR45.diagnostics();long balancedBefore=CityExactShapeUnionR45.balancedCallsR47();
                if(!STARTED.add(scope))return;
                ExecutorService worker=Executors.newSingleThreadExecutor(task->{var t=new Thread(task,"seele-r47-city-union-"+scope);t.setDaemon(true);return t;});
                WORKERS.put(scope,worker);
                worker.execute(()->
                {
                    JsonObject report;
                    try{report=run(level,payload,fullInput,position,uuid,scope,before,balancedBefore);}
                    catch(Exception failure)
                    {report=new JsonObject();report.addProperty("schema","projectseele.r47.city-native-representative.v1");report.addProperty("runtime_scope",scope);report.addProperty("physical_runtime_scope",com.projectseele.compat.CityUnionPortableBootstrapR45.runtimeScope());report.addProperty("passed",false);report.addProperty("error",failure.toString());report.addProperty("world_written",false);report.addProperty("SHA_test",false);}
                    try{Files.createDirectories(target.getParent());Files.writeString(target,new GsonBuilder().setPrettyPrinting().create().toJson(report),StandardOpenOption.CREATE_NEW);}
                    catch(Exception failure){ProjectSeele.LOGGER.error("R47 native city union receipt write failed {}",target,failure);}
                    ProjectSeele.LOGGER.info("R47 single native city union scope={} passed={} path={}",scope,report.get("passed"),target);worker.shutdown();
                });return;
            }
        }
        catch(Exception failure)
        {if(STARTED.add(scope))ProjectSeele.LOGGER.error("R47 single city union probe could not start; no world/provider changes",failure);}
    }
    @SuppressWarnings("unchecked") private static Map<BlockPos,StructureBlockInfo> blocks(Object c)throws Exception
    {return (Map<BlockPos,StructureBlockInfo>)Class.forName(BASE).getMethod("getBlocks").invoke(c);}
    private record Copy(Object contraption,BlockGetter view) {}
    private static Copy decode(Level level,CompoundTag payload,Map<BlockPos,StructureBlockInfo> complete)throws Exception
    {
        Class<?> base=Class.forName(BASE),pulley=Class.forName("com.simibubi.create.content.contraptions.pulley.PulleyContraption");
        Object copy=pulley.getConstructor().newInstance();pulley.getMethod("readNBT",Level.class,CompoundTag.class,boolean.class).invoke(copy,level,payload.copy(),false);
        Map<BlockPos,StructureBlockInfo> map=blocks(copy);require(map.size()==complete.size(),"Complete native block map count changed");
        for(var entry:complete.entrySet())
        {
            var a=entry.getValue();var b=map.get(entry.getKey());
            require(b!=null&&a.pos().equals(b.pos())&&a.state().equals(b.state())&&java.util.Objects.equals(a.nbt(),b.nbt()),"Native complete state/BE decode differs at "+entry.getKey());
        }
        Object view=Class.forName("com.simibubi.create.content.contraptions.ContraptionWorld").getConstructor(Level.class,base).newInstance(level,copy);
        Field collision=base.getDeclaredField("collisionLevel");collision.setAccessible(true);collision.set(copy,view);
        require(copy instanceof CityUnionOwnerR47 owner&&owner.seele$fullCityFrameR47(),"Actual complete-city ownership mixin absent");
        require(provider(copy)==null,"Detached input must not schedule/publish a Create future");return new Copy(copy,(BlockGetter)view);
    }
    private static Object provider(Object c)throws Exception
    {var f=Class.forName(BASE).getDeclaredField("simplifiedEntityColliderProvider");f.setAccessible(true);return f.get(c);}
    private static JsonObject run(Level level,CompoundTag payload,Map<BlockPos,StructureBlockInfo> input,Vec3 position,String uuid,String scope,JsonObject before,long balancedBefore)throws Exception
    {
        require(!Thread.currentThread().isInterrupted(),"Cancelled representative probe is not passing evidence");
        require(balancedBefore>0,"Actual normal Create provider has not executed the balanced path before the probe");
        Copy stockCopy=decode(level,payload,input),balancedCopy=decode(level,payload,input);
        JsonArray producers=new JsonArray();Set<String> names=new java.util.TreeSet<>();
        int be=0;Map<BlockPos,VoxelShape> every=new java.util.LinkedHashMap<>();
        for(var entry:blocks(stockCopy.contraption).entrySet())
        {
            StructureBlockInfo info=entry.getValue();if(info.nbt()!=null)be++;
            names.add(info.state().getBlock().getClass().getName());
            every.put(entry.getKey(),info.state().getCollisionShape(stockCopy.view,entry.getKey(),CollisionContext.empty()));
        }
        names.forEach(producers::add);
        long t=System.nanoTime();List<AABB> stock=CityExactShapeUnionR45.actualOriginalSupplierR47(stockCopy.contraption);double stockMs=(System.nanoTime()-t)/1e6;
        long balancedImmediatelyBefore=CityExactShapeUnionR45.balancedCallsR47();
        t=System.nanoTime();List<AABB> candidate=CityExactShapeUnionR45.actualSupplierR47(balancedCopy.contraption);double balancedMs=(System.nanoTime()-t)/1e6;
        boolean usedBalanced=((CityUnionOwnerR47)balancedCopy.contraption).seele$balancedSupplierUsedR47();
        require(usedBalanced,"Actual representative supplier did not execute the balanced mixin branch; inspect fallback/epsilon diagnostics");
        for(var entry:blocks(balancedCopy.contraption).entrySet())
        {
            VoxelShape repeat=entry.getValue().state().getCollisionShape(balancedCopy.view,entry.getKey(),CollisionContext.empty());
            require(ExactBalancedUnionCandidateR45.exactNativeRegionEqual(every.get(entry.getKey()),repeat),"Actual original shape/view repeat changed at "+entry.getKey());
        }
        VoxelShape a=region(stock),b=region(candidate);
        require(ExactBalancedUnionCandidateR45.exactNativeRegionEqual(a,b),"Actual stock vs actual mixed supplier full-region XOR not empty");
        long queries=axis(a,b,stock,position);
        require(provider(stockCopy.contraption)==null&&provider(balancedCopy.contraption)==null,"Probe altered native provider lifecycle");
        require(!Thread.currentThread().isInterrupted(),"Cancelled representative probe is not passing evidence");
        JsonObject r=new JsonObject();r.addProperty("schema","projectseele.r47.city-native-representative.v1");r.addProperty("passed",true);r.addProperty("runtime_scope",scope);
        r.addProperty("physical_runtime_scope",com.projectseele.compat.CityUnionPortableBootstrapR45.runtimeScope());
        r.addProperty("actual_existing_owner_uuid",uuid);r.addProperty("actual_owner_position",position.toString());r.addProperty("complete_cells",input.size());r.addProperty("complete_BE",be);
        r.add("actual_block_producer_classes",producers);r.addProperty("actual_collision_view",stockCopy.view.getClass().getName());
        r.addProperty("actual_stock_supplier_invoked",true);r.addProperty("actual_mixed_supplier_balanced_executed",true);r.addProperty("complete_shape_repeat_XOR_empty",true);r.addProperty("actual_full_region_XOR_empty",true);
        r.addProperty("native_axis_answers_exact_equal",true);r.addProperty("native_axis_queries",queries);r.addProperty("axis_boundary_scope","At most32 evenly sampled actual stock AABBs, three axes, both directions, two bodies, epsilon offsets, virtual original/mid/312m translations");
        r.addProperty("actual_stock_supplier_ms",stockMs);r.addProperty("actual_mixed_supplier_ms",balancedMs);r.addProperty("stock_AABBs",stock.size());r.addProperty("mixed_AABBs",candidate.size());
        r.add("before_actual_probe",before);r.add("after_actual_probe",CityExactShapeUnionR45.diagnostics());r.addProperty("normal_provider_balanced_calls_before_probe",balancedBefore);
        r.addProperty("normal_live_Create_future_ready_at_capture",true);r.addProperty("complete_state_and_BE_decode_equal",true);
        r.addProperty("actual_selected_live_provider_balanced_used",true);r.addProperty("aggregate_counter_scope","PHYSICAL_JVM_SHARED");
        r.addProperty("detached_complete_native_input_copies",2);r.addProperty("detached_futures_created",false);r.addProperty("live_provider_or_owner_modified",false);
        r.addProperty("world_written",false);r.addProperty("world_entity_created",false);r.addProperty("progress_reset",false);r.addProperty("SHA_test",false);r.addProperty("full96_native_pass_claimed",false);
        return r;
    }
    private static VoxelShape region(List<AABB> boxes)
    {List<VoxelShape> shapes=new ArrayList<>();for(AABB box:boxes)shapes.add(Shapes.create(box));return ExactBalancedUnionCandidateR45.stockLeftFold(shapes);}
    private static long axis(VoxelShape stock,VoxelShape candidate,List<AABB> boundaries,Vec3 current)
    {
        long queries=0;int count=Math.min(32,boundaries.size());
        for(int index=0;index<count;index++)
        {
            AABB boundary=boundaries.get(count==1?0:index*(boundaries.size()-1)/(count-1));
            for(double offset:new double[]{0,-156,-312})
            {
                Vec3 p=current.add(0,offset,0);VoxelShape a=stock.move(p.x,p.y,p.z),b=candidate.move(p.x,p.y,p.z);
                for(int body=0;body<2;body++)for(double e:new double[]{-1e-7,0,1e-7})for(Direction.Axis axis:Direction.Axis.values())for(int sign:new int[]{-1,1})
                {
                    double width=body==0?.6:1.4,height=body==0?1.8:1;
                    double x=(boundary.minX+boundary.maxX)/2+p.x-width/2,y=(boundary.minY+boundary.maxY)/2+p.y-height/2,z=(boundary.minZ+boundary.maxZ)/2+p.z-width/2;
                    if(axis==Direction.Axis.X)x=sign<0?boundary.maxX+p.x+e:boundary.minX+p.x-width+e;
                    if(axis==Direction.Axis.Y)y=sign<0?boundary.maxY+p.y+e:boundary.minY+p.y-height+e;
                    if(axis==Direction.Axis.Z)z=sign<0?boundary.maxZ+p.z+e:boundary.minZ+p.z-width+e;
                    AABB box=new AABB(x,y,z,x+width,y+height,z+width);
                    for(double distance:new double[]{.01,.25,1})
                    {require(Double.doubleToLongBits(a.collide(axis,box,sign*distance))==Double.doubleToLongBits(b.collide(axis,box,sign*distance)),"Actual native axis answer changed");queries++;}
                }
            }
        }
        return queries;
    }
    private static void require(boolean ok,String message){if(!ok)throw new IllegalStateException(message);}
}

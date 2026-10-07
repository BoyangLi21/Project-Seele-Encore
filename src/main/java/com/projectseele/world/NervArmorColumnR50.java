package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.RamielEntity;
import com.projectseele.entity.LilithEntity;
import com.projectseele.event.TvEncounterDirectorR45;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.WeakHashMap;

/** TV-inspired layered roof armor. Layer count and timing are explicitly game construction parameters. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class NervArmorColumnR50
{
    public record Layer(String id,int minY,int maxY,float hp,Block block) {}
    public record Plan(String id,BlockPos min,BlockPos max,int protectedBelow,Vec3 terminal,List<Layer> layers,BlockPos repair,boolean installed) {}
    private static final Map<ServerLevel,Optional<Plan>> CACHE=new WeakHashMap<>();
    private record Snapshot(Plan plan,Map<String,Float> integrity) {}
    private static final Map<ServerLevel,Snapshot> GENERATION=java.util.Collections.synchronizedMap(new WeakHashMap<>());
    private static BlockPos pos(com.google.gson.JsonArray a){return new BlockPos(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt());}
    public static Optional<Plan> plan(ServerLevel level)
    {
        return CACHE.computeIfAbsent(level,l->{
            var file=l.getServer().getWorldPath(LevelResource.ROOT).resolve("nerv_armor_column_r50.json");if(!Files.isRegularFile(file))return Optional.empty();
            try
            {
                var o=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                if(o.get("schema").getAsInt()!=50||!o.get("dimension").getAsString().equals(l.dimension().location().toString()))throw new IllegalArgumentException("Armor column identity");
                var bounds=o.getAsJsonArray("hole_bounds");BlockPos min=pos(bounds.get(0).getAsJsonArray()),max=pos(bounds.get(1).getAsJsonArray());
                int protect=o.get("protected_below_y").getAsInt();var t=o.getAsJsonArray("terminal_pos");Vec3 terminal=new Vec3(t.get(0).getAsDouble(),t.get(1).getAsDouble(),t.get(2).getAsDouble());
                List<Layer> layers=new ArrayList<>();int last=Integer.MAX_VALUE;
                for(var raw:o.getAsJsonArray("layers"))
                {
                    var row=raw.getAsJsonObject();int low=row.get("y_min").getAsInt(),high=row.get("y_max").getAsInt();float hp=row.get("hit_points").getAsFloat();
                    var id=new ResourceLocation(row.has("block")?row.get("block").getAsString():o.get("plate_block").getAsString());
                    if(!BuiltInRegistries.BLOCK.containsKey(id)||low>high||low<min.getY()||high>max.getY()||high>=last||low<=protect||!Float.isFinite(hp)||hp<=0||hp>100000)throw new IllegalArgumentException("Armor layer order/type/range");
                    Block block=BuiltInRegistries.BLOCK.get(id);if(block==Blocks.AIR||block==Blocks.BEDROCK)throw new IllegalArgumentException("Invalid destructible armor block");
                    String layerId=row.get("id").getAsString();if(layers.stream().anyMatch(p->p.id().equals(layerId)))throw new IllegalArgumentException("Duplicate armor layer");
                    layers.add(new Layer(layerId,low,high,hp,block));last=low;
                }
                if(layers.isEmpty()||layers.size()>32||min.getX()>max.getX()||min.getZ()>max.getZ()||max.getX()-min.getX()>15||max.getZ()-min.getZ()>15||max.getY()-min.getY()>128||terminal.y>=min.getY())throw new IllegalArgumentException("Armor column bounds");
                return Optional.of(new Plan(o.get("id").getAsString(),min,max,protect,terminal,List.copyOf(layers),pos(o.getAsJsonArray("repair_control")),o.get("installed").getAsBoolean()));
            }
            catch(Exception failure){ProjectSeele.LOGGER.error("Installed R50 armor column rejected",failure);return Optional.empty();}
        });
    }
    public static String startBlocker(ServerLevel level)
    {var p=plan(level).orElse(null);return p==null||!p.installed()?"莉莉丝投影上方的独立装甲孔位尚未完成施工与验收。":"";}
    private static NervArmorSavedDataR50 initialized(ServerLevel level,Plan p)
    {
        var s=NervArmorSavedDataR50.get(level);
        if(s.column.isEmpty())
        {s.column=p.id();for(var layer:p.layers())s.integrity.put(layer.id(),layer.hp());s.setDirty();}
        return s;
    }
    private static Layer front(Plan p,NervArmorSavedDataR50 s)
    {for(var layer:p.layers())if(s.integrity.getOrDefault(layer.id(),layer.hp())>0)return layer;return null;}
    private static void publish(ServerLevel level,Plan plan,NervArmorSavedDataR50 state)
    {if(state.column.equals(plan.id()))GENERATION.put(level,new Snapshot(plan,Map.copyOf(state.integrity)));}
    /** Immutable server-published ownership is safe to read from a decoration worker thread. */
    public static boolean permitsGenerationR50(ServerLevel level,BlockPos pos,net.minecraft.world.level.block.state.BlockState state)
    {
        Snapshot snapshot=GENERATION.get(level);if(snapshot==null||state.isAir())return true;
        for(Layer layer:snapshot.plan().layers())
            if(snapshot.integrity().getOrDefault(layer.id(),layer.hp())<=0&&inLayer(snapshot.plan(),layer,pos))return false;
        return true;
    }
    /** One saved armor state owns reload repair as well as drilling; foreign blocks and NBT remain untouched. */
    public static void reconcile(ServerLevel level)
    {
        var p=plan(level).orElse(null);if(p==null||!p.installed())return;var s=initialized(level,p);if(!s.column.equals(p.id()))return;
        publish(level,p,s);
        for(Layer layer:p.layers())if(s.integrity.getOrDefault(layer.id(),layer.hp())<=0)
            for(BlockPos pos:BlockPos.betweenClosed(new BlockPos(p.min().getX(),layer.minY(),p.min().getZ()),new BlockPos(p.max().getX(),layer.maxY(),p.max().getZ())))
                if(level.hasChunkAt(pos)&&level.getBlockState(pos).is(layer.block())&&level.getBlockEntity(pos)==null)level.setBlock(pos,Blocks.AIR.defaultBlockState(),3);
    }
    public static double frontY(ServerLevel level)
    {var p=plan(level).orElse(null);if(p==null)return 80;var layer=front(p,initialized(level,p));return layer==null?p.min().getY()-1:layer.maxY()+1;}
    public static int penetratedLayers(ServerLevel level)
    {var p=plan(level).orElse(null);return p==null?0:initialized(level,p).breached;}
    public static boolean geofrontBreached(ServerLevel level)
    {return NervArmorSavedDataR50.get(level).phase.equals("geofront_breach");}
    /** This is actual unobstructed terminal contact, never the number of roof plates breached. */
    public static boolean breachTerminal(ServerLevel level)
    {return NervArmorSavedDataR50.get(level).terminalContact;}
    public static void pause(ServerLevel level)
    {var s=NervArmorSavedDataR50.get(level);s.lastTick=level.getGameTime();s.setDirty();}
    public static void tickRamiel(ServerLevel level,TvCampaignSavedData campaign,RamielEntity boss,int stepTicks)
    {
        var p=plan(level).orElse(null);if(p==null||!p.installed()||!campaign.active.equals("ramiel")||campaign.angel==null||!boss.getUUID().equals(campaign.angel)||!TvEncounterDirectorR45.owned(boss,campaign)
                ||campaign.phase.equals("cancel")||campaign.phase.equals("failure")||campaign.targetDeathConfirmedR45||stepTicks<=0)return;
        var commander=campaign.owner==null?null:level.getServer().getPlayerList().getPlayer(campaign.owner);if(commander==null||commander.level()!=level){pause(level);return;}
        var s=initialized(level,p);if(!s.column.equals(p.id()))return;
        long now=level.getGameTime();if(s.lastTick==now)return;
        int onlineDelta=s.lastTick<0?10:(int)Math.max(0,Math.min(10,now-s.lastTick));
        s.lastTick=now;s.attacker=boss.getUUID();s.generation=campaign.generationR43;
        var layer=front(p,s);
        if(layer==null)
        {s.phase="geofront_breach";campaign.notice="上方八层游戏装甲已被贯穿，GeoFront出现侵入口；本部隔壁与末端室仍未突破。";s.setDirty();return;}
        Vec3 impact=new Vec3((p.min().getX()+p.max().getX()+1)*.5,layer.maxY()+.5,(p.min().getZ()+p.max().getZ()+1)*.5);
        Vec3 from=boss.position();
        if(Math.abs(from.x-impact.x)>4||Math.abs(from.z-impact.z)>4||from.y<=impact.y)return;
        var hit=level.clip(new ClipContext(from,impact,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,boss));
        if(hit.getType()!=HitResult.Type.BLOCK||!inLayer(p,layer,hit.getBlockPos())||!level.getBlockState(hit.getBlockPos()).is(layer.block()))return;
        s.stepBudget+=onlineDelta;
        if(s.stepBudget>=stepTicks)
        {s.stepBudget-=stepTicks;damageLayer(level,p,s,layer,20,hit.getLocation());}
        s.setDirty();
    }
    /** A real laser consumer can submit its actual traced segment to the same plate integrity. */
    public static boolean beamImpactR50(ServerLevel level,LivingEntity attacker,Vec3 from,Vec3 to,float damage)
    {
        var p=plan(level).orElse(null);if(p==null||!p.installed()||!Float.isFinite(damage)||damage<=0)return false;
        var s=initialized(level,p);var layer=front(p,s);if(layer==null)return false;
        var hit=level.clip(new ClipContext(from,to,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,attacker));
        if(hit.getType()!=HitResult.Type.BLOCK||!inLayer(p,layer,hit.getBlockPos())||!level.getBlockState(hit.getBlockPos()).is(layer.block()))return false;
        damageLayer(level,p,s,layer,Math.min(damage,layer.hp()),hit.getLocation());return true;
    }
    private static boolean inLayer(Plan p,Layer layer,BlockPos at)
    {return at.getX()>=p.min().getX()&&at.getX()<=p.max().getX()&&at.getZ()>=p.min().getZ()&&at.getZ()<=p.max().getZ()&&at.getY()>=layer.minY()&&at.getY()<=layer.maxY()&&at.getY()>p.protectedBelow();}
    private static void damageLayer(ServerLevel level,Plan p,NervArmorSavedDataR50 s,Layer layer,float damage,Vec3 point)
    {
        float hp=Math.max(0,s.integrity.getOrDefault(layer.id(),layer.hp())-damage);s.integrity.put(layer.id(),hp);s.phase="damaged";
        if(hp==0)
        {
            for(BlockPos pos:BlockPos.betweenClosed(new BlockPos(p.min().getX(),layer.minY(),p.min().getZ()),new BlockPos(p.max().getX(),layer.maxY(),p.max().getZ())))
                if(level.getBlockState(pos).is(layer.block())&&level.getBlockEntity(pos)==null)level.setBlock(pos,Blocks.AIR.defaultBlockState(),3);
            s.breached++;if(front(p,s)==null)s.phase="geofront_breach";
            level.playSound(null,BlockPos.containing(point),net.minecraft.sounds.SoundEvents.ANVIL_BREAK,net.minecraft.sounds.SoundSource.HOSTILE,4,.55F);
        }
        level.sendParticles(net.minecraft.core.particles.ParticleTypes.SMOKE,point.x,point.y,point.z,12,2,.5,2,.03);s.setDirty();publish(level,p,s);
    }
    /** Kept for future physical invasion stages; a roof hole does not grant a path through HQ. */
    public static boolean actualTerminalContactR50(ServerLevel level,LivingEntity angel,Vec3 actualContact)
    {
        if(!(angel instanceof com.projectseele.entity.Angel))return false;var p=plan(level).orElse(null);if(p==null||actualContact==null)return false;
        if(actualContact.distanceTo(p.terminal())>12||!angel.getBoundingBox().inflate(2).contains(actualContact))return false;
        for(var lilith:level.getEntitiesOfClass(LilithEntity.class,new AABB(p.terminal(),p.terminal()).inflate(80)))
        {
            if(!lilith.isAlive()||!lilith.getBoundingBox().inflate(2).contains(actualContact))continue;
            var wall=level.clip(new ClipContext(angel.getBoundingBox().getCenter(),actualContact,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,angel));
            if(wall.getType()!=HitResult.Type.MISS&&wall.getLocation().distanceTo(actualContact)>1)return false;
            var s=initialized(level,p);s.terminalContact=true;s.phase="terminal_contact";s.setDirty();return true;
        }
        return false;
    }
    public static String repair(ServerPlayer operator)
    {
        var level=operator.serverLevel();var p=plan(level).orElse(null);if(p==null||operator.position().distanceTo(Vec3.atCenterOf(p.repair()))>6)return "请在装甲检修岗位操作。";
        var campaign=TvCampaignSavedData.get(level);
        if(campaign.active.equals("ramiel")&&!campaign.phase.equals("cancel")&&!campaign.phase.equals("failure")&&!campaign.phase.equals("combat_victory"))return "使徒仍在攻击该装甲孔位，检修隔离尚未成立。";
        var s=initialized(level,p);
        AABB bounds=new AABB(p.min(),p.max().offset(1,1,1));
        if(!level.getEntities((Entity)null,bounds,e->e.isAlive()&&e instanceof LivingEntity).isEmpty())return "装甲孔位内仍有人员或机体，禁止闭合。";
        for(var layer:p.layers())for(var pos:BlockPos.betweenClosed(new BlockPos(p.min().getX(),layer.minY(),p.min().getZ()),new BlockPos(p.max().getX(),layer.maxY(),p.max().getZ())))
            if(!level.getBlockState(pos).isAir()&&!level.getBlockState(pos).is(layer.block()))return "孔位中有人工改动或其他设备，检修保持暂停。";
        for(var layer:p.layers())
        {
            for(var pos:BlockPos.betweenClosed(new BlockPos(p.min().getX(),layer.minY(),p.min().getZ()),new BlockPos(p.max().getX(),layer.maxY(),p.max().getZ())))
                if(level.getBlockState(pos).isAir())level.setBlock(pos,layer.block().defaultBlockState(),3);
            s.integrity.put(layer.id(),layer.hp());
        }
        s.breached=s.stepBudget=0;s.terminalContact=false;s.phase="sealed";s.setDirty();publish(level,p,s);return "已按原装甲层板掩码完成修复，原本部房间与角色未改动。";
    }
    @SubscribeEvent public static void interact(PlayerInteractEvent.RightClickBlock event)
    {
        if(!(event.getEntity() instanceof ServerPlayer operator)||event.getHand()!=InteractionHand.MAIN_HAND)return;
        var p=plan(operator.serverLevel()).orElse(null);if(p==null||!event.getPos().equals(p.repair()))return;
        event.setCanceled(true);event.setCancellationResult(InteractionResult.SUCCESS);operator.sendSystemMessage(net.minecraft.network.chat.Component.literal(repair(operator)));
    }
    @SubscribeEvent public static void unloaded(net.minecraftforge.event.level.LevelEvent.Unload event)
    {if(event.getLevel() instanceof ServerLevel level){CACHE.remove(level);GENERATION.remove(level);}}
    @SubscribeEvent public static void loaded(net.minecraftforge.event.level.LevelEvent.Load event)
    {
        if(!(event.getLevel() instanceof ServerLevel level)||!level.dimension().equals(FacilitySchemaV2.DIMENSION))return;
        var p=plan(level).orElse(null);if(p!=null&&p.installed())publish(level,p,initialized(level,p));
    }
    @SubscribeEvent public static void maintenance(net.minecraftforge.event.TickEvent.ServerTickEvent event)
    {
        if(event.phase!=net.minecraftforge.event.TickEvent.Phase.END||event.getServer().getTickCount()%20!=0)return;
        var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level!=null)reconcile(level);
    }
    private NervArmorColumnR50(){}
}

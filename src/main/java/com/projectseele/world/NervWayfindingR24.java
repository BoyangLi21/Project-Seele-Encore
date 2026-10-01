package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.*;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.*;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPInputStream;

/** Directions follow the measured floor graph, never a straight ray through walls. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class NervWayfindingR24
{
    private record LiftRoute(int next,BlockPos landing,double walkingMetres){}
    private record Graph(String dimension,List<String> ids,String[] names,BlockPos[] nodes,int[][] next,Map<Long,List<Integer>> columns,LiftRoute[] nearestLifts){}
    private record Selection(ServerLevel level,String goal){}
    public record Guide(String destination,BlockPos here,BlockPos next,String instruction,boolean arrived){}
    private static final Map<net.minecraft.server.MinecraftServer,Optional<Graph>> GRAPHS=new WeakHashMap<>();
    private static final Map<net.minecraft.server.MinecraftServer,Map<UUID,Selection>> ACTIVE=new WeakHashMap<>();
    public static final List<String> GOALS=List.of("command","hangars","station","pyramid_station","launch_station","observation","dogma","low_plant","nearest_lift");
    private static Graph graph(ServerPlayer player)
    {
        return GRAPHS.computeIfAbsent(player.server,key->{
            Path path=key.getWorldPath(LevelResource.ROOT).resolve("nerv_routes_r24.json.gz");if(!Files.isRegularFile(path))return Optional.empty();
            try(var input=new InputStreamReader(new GZIPInputStream(Files.newInputStream(path)),StandardCharsets.UTF_8))
            {
                var json=JsonParser.parseReader(input).getAsJsonObject();var rows=json.getAsJsonArray("nodes");
                int version=json.get("version").getAsInt(),count=json.getAsJsonArray("goals").size();
                if((version!=1&&version!=2)||rows.size()>500000||count<1||count>16)throw new IllegalArgumentException("Routing schema");
                List<String> ids=new ArrayList<>();String[] names=new String[count];
                for(int i=0;i<count;i++){var goal=json.getAsJsonArray("goals").get(i).getAsJsonObject();ids.add(goal.get("id").getAsString());names[i]=goal.get("name").getAsString();}
                if(new HashSet<>(ids).size()!=count)throw new IllegalArgumentException("Repeated routing destination");
                BlockPos[] nodes=new BlockPos[rows.size()];int[][] next=new int[rows.size()][count];Map<Long,List<Integer>> columns=new HashMap<>();
                for(int i=0;i<nodes.length;i++)
                {
                    var row=rows.get(i).getAsJsonArray();if(row.size()!=3+count)throw new IllegalArgumentException("Routing row");
                    nodes[i]=new BlockPos(row.get(0).getAsInt(),row.get(1).getAsInt(),row.get(2).getAsInt());
                    for(int g=0;g<count;g++){next[i][g]=row.get(g+3).getAsInt();if(next[i][g]<0||next[i][g]>=nodes.length)throw new IllegalArgumentException("Routing edge");}
                    long column=net.minecraft.world.level.ChunkPos.asLong(nodes[i].getX(),nodes[i].getZ());columns.computeIfAbsent(column,x->new ArrayList<>()).add(i);
                }
                return Optional.of(new Graph(json.get("dimension").getAsString(),List.copyOf(ids),names,nodes,next,columns,loadNearestLifts(path,nodes)));
            }
            catch(Exception failure){ProjectSeele.LOGGER.error("Measured wayfinding resource rejected",failure);return Optional.empty();}
        }).orElse(null);
    }
    private static LiftRoute[] loadNearestLifts(Path graphPath,BlockPos[] nodes)
    {
        Path path=graphPath.resolveSibling("nearest_lift_paths_r44.json.gz");
        if(!Files.isRegularFile(path))return null;
        try(var input=new InputStreamReader(new GZIPInputStream(Files.newInputStream(path)),StandardCharsets.UTF_8))
        {
            var json=JsonParser.parseReader(input).getAsJsonObject();
            String digest=HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(graphPath)));
            if(!digest.equals(json.get("graph_sha256").getAsString()))throw new IllegalArgumentException("Nearest-lift table belongs to another floor graph");
            var rows=json.getAsJsonArray("nodes");
            if(rows.size()!=nodes.length)throw new IllegalArgumentException("Nearest-lift node count");
            Map<BlockPos,Integer> index=new HashMap<>();
            for(int i=0;i<nodes.length;i++)index.put(nodes[i],i);
            LiftRoute[] result=new LiftRoute[nodes.length];
            for(int i=0;i<result.length;i++)
            {
                if(rows.get(i).isJsonNull())continue;
                var row=rows.get(i).getAsJsonObject();var nextRow=row.getAsJsonArray("next");var landingRow=row.getAsJsonArray("nearest_landing");
                if(nextRow.size()!=3||landingRow.size()!=3)throw new IllegalArgumentException("Nearest-lift coordinates");
                BlockPos next=new BlockPos(nextRow.get(0).getAsInt(),nextRow.get(1).getAsInt(),nextRow.get(2).getAsInt());
                BlockPos landing=new BlockPos(landingRow.get(0).getAsInt(),landingRow.get(1).getAsInt(),landingRow.get(2).getAsInt());
                Integer target=index.get(next);double cost=row.get("walking_metres").getAsDouble();
                if(target==null||!index.containsKey(landing)||!Double.isFinite(cost)||cost<0||Math.abs(next.getY()-nodes[i].getY())>1)
                    throw new IllegalArgumentException("Nearest-lift route contains a nonwalking edge");
                result[i]=new LiftRoute(target,landing,cost);
            }
            return result;
        }
        catch(Exception failure){ProjectSeele.LOGGER.error("Measured nearest-lift resource rejected",failure);return null;}
    }
    private static int nearest(ServerPlayer player,Graph graph)
    {
        int best=-1;double distance=16;BlockPos feet=player.blockPosition();
        for(int x=feet.getX()-3;x<=feet.getX()+3;x++)for(int z=feet.getZ()-3;z<=feet.getZ()+3;z++)
            for(int id:graph.columns.getOrDefault(net.minecraft.world.level.ChunkPos.asLong(x,z),List.of()))
            {
                var at=graph.nodes[id];if(Math.abs(player.getY()-at.getY())>1.1)continue;
                Vec3 point=Vec3.atBottomCenterOf(at);double d=point.distanceToSqr(player.position());if(d>=distance||!player.level().hasChunkAt(at))continue;
                if(!player.level().noCollision(player,new AABB(point.x-.28,point.y+.01,point.z-.28,point.x+.28,point.y+1.79,point.z+.28)))continue;
                var hit=player.level().clip(new ClipContext(player.position().add(0,.8,0),point.add(0,.8,0),ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,player));
                if(hit.getType()!=HitResult.Type.MISS)continue;best=id;distance=d;
            }
        return best;
    }
    public static String start(ServerPlayer player,String goal)
    {
        var selections=ACTIVE.computeIfAbsent(player.server,key->new HashMap<>());
        if(goal.equals("stop")){selections.remove(player.getUUID());return "步行引导已关闭。";}
        var graph=graph(player);int index=graph==null?-1:graph.ids.indexOf(goal);
        if(goal.equals("nearest_lift"))
        {
            var guidance=nearestLift(player);
            if(guidance.isEmpty())return "当前通道尚未配置可达电梯导向，请沿现场标牌行走。";
            selections.put(player.getUUID(),new Selection(player.serverLevel(),goal));
            return "已开启最近电梯引导。沿实际通廊和楼梯前往层门，在门外呼梯、进入轿厢后选层。";
        }
        if(index<0||graph==null||!player.level().dimension().location().toString().equals(graph.dimension))return "当前区域尚未配置总部步行引导。";
        if(nearest(player,graph)<0)return "请先走到总部公共走廊或门外，再开启引导；不会指引你穿过墙面或玻璃。";
        selections.put(player.getUUID(),new Selection(player.serverLevel(),goal));
        return "已开启前往"+graph.names[index]+"的步行引导。按屏幕下方提示行走；到达转角后指引会更新。直梯需使用现场呼梯按钮。";
    }
    public static String describe(ServerPlayer player)
    {
        var graph=graph(player);if(graph==null||!player.level().dimension().location().toString().equals(graph.dimension))return "请沿现场导向牌行走。指挥室、机库和总部火车站采用同一套目的地名称。";
        int start=nearest(player,graph);if(start<0)return "你现在不在已测绘的公共通道上。先从本房间的正式出入口回到走廊，再选择目的地。";
        return "这里是"+zone(graph.nodes[start])+"。请选择目的地；引导沿实测通道、车站接驳和直梯连接更新。终极教条仍按现场门禁验证通行权限。";
    }
    public static Optional<Guide> guide(ServerPlayer player,String goal)
    {
        if(goal.equals("nearest_lift"))return nearestLift(player);
        var graph=graph(player);int index=graph==null?-1:graph.ids.indexOf(goal);
        if(graph==null||index<0||!player.level().dimension().location().toString().equals(graph.dimension))return Optional.empty();
        int node=nearest(player,graph);if(node<0)return Optional.empty();
        int next=graph.next[node][index];String cue=instruction(graph,node,index);
        var target=graph.nodes[next];
        if(player.level().hasChunkAt(target))
        {
            var state=player.level().getBlockState(target);
            boolean sameLanding=Math.abs(target.getY()-graph.nodes[node].getY())<=1;
            if(sameLanding&&(state.is(net.minecraft.world.level.block.Blocks.BARRIER)||state.getBlock() instanceof net.minecraft.world.level.block.DoorBlock&&!state.getValue(net.minecraft.world.level.block.DoorBlock.OPEN)))
                cue="前方门禁：按门旁指示刷卡或操作出口开关，通过后继续";
            else if(sameLanding&&next!=node)
            {
                var sole=new AABB(target.getX()+.25,target.getY()-.6,target.getZ()+.25,target.getX()+.75,target.getY()+.01,target.getZ()+.75);
                if(!player.level().getBlockCollisions(player,sole).iterator().hasNext())cue="前方踏面暂不可用，请等待机械到位或循现场导向绕行";
            }
        }
        return Optional.of(new Guide(graph.names[index],graph.nodes[node],target,cue,next==node));
    }
    public static Optional<Guide> nearestLift(ServerPlayer player)
    {
        var graph=graph(player);
        if(graph==null||graph.nearestLifts==null||!player.level().dimension().location().toString().equals(graph.dimension))return Optional.empty();
        int node=nearest(player,graph);
        if(node<0||graph.nearestLifts[node]==null)return Optional.empty();
        var route=graph.nearestLifts[node];BlockPos here=graph.nodes[node],next=graph.nodes[route.next];
        boolean arrived=route.next==node;
        String cue;
        if(arrived)cue="已到电梯层门；请在门外呼梯，到层后进入轿厢选层";
        else
        {
            int dy=Integer.signum(next.getY()-here.getY()),dx=Integer.signum(next.getX()-here.getX()),dz=Integer.signum(next.getZ()-here.getZ());
            String direction=dx>0?"东":dx<0?"西":dz>0?"南":"北";
            cue=(dy==0?"向"+direction+"沿廊前行":"沿楼梯"+(dy>0?"上行":"下行"))+" · 距层门约 "+Math.max(1,Math.round(route.walkingMetres))+" m";
        }
        if(!arrived&&player.level().hasChunkAt(next))
        {
            var state=player.level().getBlockState(next);
            if(state.is(net.minecraft.world.level.block.Blocks.BARRIER)||state.getBlock() instanceof net.minecraft.world.level.block.DoorBlock&&!state.getValue(net.minecraft.world.level.block.DoorBlock.OPEN))
                cue="前方门禁：按门旁指示刷卡或操作出口开关，通过后继续";
            else if(!player.level().noCollision(player,new AABB(next.getX()+.2,next.getY()+.01,next.getZ()+.2,next.getX()+.8,next.getY()+1.79,next.getZ()+.8)))
                cue="前方通道暂被设备占用，请等待通道清空后继续";
        }
        return Optional.of(new Guide("最近电梯 · "+zone(route.landing),here,next,cue,arrived));
    }
    public static String zone(int y)
    {
        if(y<-520)return "终极教条区";
        if(y<=-465)return "总部车站层";if(y<=-455)return "交通接驳层";if(y<=-440)return "总部主环廊";
        if(y<=-426)return "作业联络层";if(y<=-412)return "技术联络层";if(y<=-399)return "指挥联络层";
        if(y<=-384)return "综合服务层";return y<-355?"上层接待区":"总指挥层";
    }
    private static String zone(BlockPos at)
    {return at.getZ()<0?(at.getY()>=-380?"机库观景层":at.getY()>=-405?"机库登机层":"发射区交通层"):zone(at.getY());}
    private static String instruction(Graph graph,int from,int goal)
    {
        BlockPos start=graph.nodes[from];int cursor=graph.next[from][goal];if(cursor==from)return "已到达 "+graph.names[goal];
        BlockPos first=graph.nodes[cursor];int dx=Integer.signum(first.getX()-start.getX()),dy=Integer.signum(first.getY()-start.getY()),dz=Integer.signum(first.getZ()-start.getZ());
        if(Math.abs(first.getY()-start.getY())>1)return "乘直梯"+(dy>0?"上行":"下行")+"至"+zone(first);
        double metres=start.distSqr(first)==0?0:Math.sqrt(start.distSqr(first));
        for(int i=0;i<60;i++)
        {
            int next=graph.next[cursor][goal];if(next==cursor)break;BlockPos a=graph.nodes[cursor],b=graph.nodes[next];
            if(Integer.signum(b.getX()-a.getX())!=dx||Integer.signum(b.getY()-a.getY())!=dy||Integer.signum(b.getZ()-a.getZ())!=dz||Math.abs(b.getY()-a.getY())>1)break;
            metres+=Math.sqrt(a.distSqr(b));cursor=next;
        }
        String direction=dx>0?"东":dx<0?"西":dz>0?"南":"北";
        return (dy==0?"向"+direction+"沿廊前行 ":"沿梯段"+(dy>0?"上行 ":"下行 "))+Math.max(1,Math.round(metres))+" m";
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||event.getServer().getTickCount()%30!=0)return;
        var selections=ACTIVE.get(event.getServer());if(selections==null)return;
        for(var entry:List.copyOf(selections.entrySet()))
        {
            var player=event.getServer().getPlayerList().getPlayer(entry.getKey());
            if(player==null||player.level()!=entry.getValue().level){selections.remove(entry.getKey());continue;}
            var guidance=guide(player,entry.getValue().goal);
            if(guidance.isEmpty()){player.displayClientMessage(Component.literal("步行引导：请回到公共通道，或等待直梯到层"),true);continue;}
            var guide=guidance.get();player.displayClientMessage(Component.literal(guide.destination+"  ·  "+guide.instruction),true);
            if(guide.arrived)selections.remove(entry.getKey());
        }
    }
    private NervWayfindingR24(){}
}

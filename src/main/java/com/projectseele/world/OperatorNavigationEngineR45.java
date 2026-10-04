package com.projectseele.world;

import com.google.gson.*;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.*;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.*;
import net.minecraft.world.phys.shapes.CollisionContext;
import java.util.*;

/** Pure semantic parser/runtime engine for installed production operator egress. */
public final class OperatorNavigationEngineR45
{
    public enum Status { READY, ARRIVED, UNBOUND, INVALID_CONTRACT, WRONG_WORLD, NOT_ON_FOOT,
        NO_OWNED_ROUTE, UNLOADED, OWNER_CHANGED, FLAGS_DISABLED, MACHINE_UNAVAILABLE,
        GATE_INCONSISTENT, GATE_CLOSED, SUPPORT_CHANGED, OCCUPIED, DYNAMIC_ROUTE_UNBOUND }
    /** Feet remain doubles throughout; no legacy BlockPos Guide conversion is permitted. */
    public record Result(Status status,String scope,Vec3 here,Vec3 next,String instruction,boolean arrived) { }
    private record Node(Vec3 feet,String kind,BlockPos support,String state) { }
    private record Owned(BlockPos pos,BlockState state,int variant) { }
    private record Scope(String id,int variant,int side,List<BlockPos> gates,List<Node> nodes,
                         int target,int[] next,double[] metres,Set<Long> edges) { }
    public static final class Contract
    {
        private final List<Scope> scopes;private final List<Owned> owners;
        private Contract(List<Scope> scopes,List<Owned> owners){this.scopes=scopes;this.owners=owners;}
    }
    public static final String SEMANTIC_REVISION="R45_FIXED_PERSONNEL_V1";
    private static long edge(int a,int b){return ((long)Math.min(a,b)<<32)|(Math.max(a,b)&0xffffffffL);}
    private static Vec3 feet(JsonArray row)
    {
        if(row.size()!=3)throw new IllegalArgumentException("Three exact feet coordinates required");
        var p=new Vec3(row.get(0).getAsDouble(),row.get(1).getAsDouble(),row.get(2).getAsDouble());
        if(!Double.isFinite(p.x)||!Double.isFinite(p.y)||!Double.isFinite(p.z)||p.x< -46||p.x>114||p.y< -405||p.y> -385||p.z< -298||p.z> -42)throw new IllegalArgumentException("Feet outside finite semantic contract");
        return p;
    }
    private static BlockPos cell(JsonArray row)
    {
        if(row.size()!=3)throw new IllegalArgumentException("Three owner coordinates required");int[] p=new int[3];
        for(int i=0;i<3;i++){double n=row.get(i).getAsDouble();if(!Double.isFinite(n)||n!=Math.rint(n)||Math.abs(n)>1000000)throw new IllegalArgumentException("Fractional owner cell");p[i]=(int)n;}
        return new BlockPos(p[0],p[1],p[2]);
    }
    public static Contract parse(JsonObject job)
    {
        if(job.get("fixed_count").getAsInt()!=202||job.get("fixed_edge_count").getAsInt()!=291||job.get("gate_count").getAsInt()!=6
                ||job.getAsJsonObject("dynamic_inspection").get("bound").getAsBoolean())throw new IllegalArgumentException("Incomplete finite scope");
        var owners=new ArrayList<Owned>();var ownerMap=new HashMap<BlockPos,BlockState>();var floors=new HashSet<BlockPos>();
        int guards=0,doors=0;
        for(var raw:job.getAsJsonArray("owners"))
        {
            var row=raw.getAsJsonObject();var p=cell(row.getAsJsonArray("position"));var state=TvPersonnelPlatformRecipeR44.parse(row.get("state").getAsString());
            if(!row.get("full_nbt").isJsonNull()||!TvPersonnelPlatformRecipeR44.ownsPosition(p)||ownerMap.put(p,state)!=null)
                throw new IllegalArgumentException("Foreign/repeated block or NBT owner");
            if(state.getBlock() instanceof TvPersonnelDeckR44)floors.add(p);
            else if(state.getBlock() instanceof TvPersonnelGuardR44)guards++;
            else if(state.getBlock() instanceof CityPersonnelDoorR44)doors++;
            else throw new IllegalArgumentException("Unknown owned installation type");
            int variant=net.minecraft.util.Mth.clamp(Math.round((p.getX()+11.5F)/42F),0,2);owners.add(new Owned(p,state,variant));
        }
        if(!ownerMap.keySet().equals(TvPersonnelPlatformRecipeR44.ownerPositions())||floors.size()!=202||guards!=201||doors!=24)
            throw new IllegalArgumentException("The complete427 source installation is required");
        Set<Long> privateColumns=new HashSet<>();floors.forEach(p->privateColumns.add(ChunkPos.asLong(p.getX(),p.getZ())));
        var scopes=new ArrayList<Scope>();Set<String> identities=new HashSet<>();Set<BlockPos> allFixed=new HashSet<>(),allGates=new HashSet<>();int fixedEdges=0;
        for(var raw:job.getAsJsonArray("scopes"))
        {
            var row=raw.getAsJsonObject();int v=row.get("variant").getAsInt(),side=row.get("side").getAsInt();String id=row.get("id").getAsString();
            if(v<0||v>2||(side!=-1&&side!=1)||!identities.add(v+"/"+side)
                    ||!id.equals("r45/boarding/"+v+"/"+side+"/fixed_operator_complete_return"))throw new IllegalArgumentException("Foreign scope");
            var gates=new ArrayList<BlockPos>();int cx=-12+42*v;
            Set<BlockPos> expected=v==2&&side==1?Set.of(new BlockPos(89,-394,-246),new BlockPos(89,-394,-245))
                :Set.of(new BlockPos(cx+(side<0?-16:15),-394,-264),new BlockPos(cx+(side<0?-15:16),-394,-264));
            for(var q:row.getAsJsonArray("gate_lower"))gates.add(cell(q.getAsJsonArray()));
            if(gates.size()!=2||!new HashSet<>(gates).equals(expected)||gates.stream().anyMatch(p->!allGates.add(p)))throw new IllegalArgumentException("Foreign gate pair");
            var nodes=new ArrayList<Node>();Set<String> unique=new HashSet<>();
            for(var value:row.getAsJsonArray("nodes"))
            {
                var n=value.getAsJsonObject();var p=feet(n.getAsJsonArray("feet"));String kind=n.get("kind").getAsString();var support=cell(n.getAsJsonArray("support"));String state=n.get("state").getAsString();
                if(!Set.of("fixed_operator","gate","public").contains(kind)||!n.get("full_nbt").isJsonNull()||!unique.add(kind+"/"+p))throw new IllegalArgumentException("Unknown/repeated navigation datum");
                if(kind.equals("fixed_operator")&&(!floors.contains(support)||!allFixed.add(support)||!state.equals(TvPersonnelPlatformRecipeR44.stateKey(ownerMap.get(support)))
                        ||n.get("variant").getAsInt()!=v||n.get("side").getAsInt()!=side||Math.abs(p.x-support.getX()-.5)>.0001||Math.abs(p.z-support.getZ()-.5)>.0001))
                    throw new IllegalArgumentException("Private feet do not have an exact declared floor owner");
                if(kind.equals("fixed_operator")&&(Math.round((support.getX()+11.5F)/42F)!=v||(support.getX()< -11.5+42*v?-1:1)!=side))
                    throw new IllegalArgumentException("Private floor belongs to another machine/side");
                if(kind.equals("public")&&(TvPersonnelPlatformRecipeR44.ownsPosition(support)||privateColumns.contains(ChunkPos.asLong(support.getX(),support.getZ()))))
                    throw new IllegalArgumentException("A private fixture cannot become a public walking column");
                if(kind.equals("gate")&&!gates.contains(BlockPos.containing(p)))throw new IllegalArgumentException("Gate feet outside actual pair");
                nodes.add(new Node(p,kind,support,state));
            }
            if(nodes.size()>8000)throw new IllegalArgumentException("Unbounded operator graph");
            Set<Long> edges=new HashSet<>();
            for(var value:row.getAsJsonArray("edges"))
            {
                var e=value.getAsJsonObject();int a=e.get("a").getAsInt(),b=e.get("b").getAsInt();
                if(a<0||b<0||a>=nodes.size()||b>=nodes.size()||a==b||!edges.add(edge(a,b))||e.get("native_walk_proven").getAsBoolean())throw new IllegalArgumentException("Foreign walking edge");
                var p=nodes.get(a).feet;var q=nodes.get(b).feet;
                if(nodes.get(a).kind.equals("fixed_operator")&&nodes.get(b).kind.equals("public")
                        ||nodes.get(b).kind.equals("fixed_operator")&&nodes.get(a).kind.equals("public"))
                    throw new IllegalArgumentException("Operator/public crossing requires its registered gate");
                if(Math.abs(p.x-q.x)+Math.abs(p.z-q.z)>1.001||Math.abs(p.y-q.y)>.751)throw new IllegalArgumentException("Nonlocal walking edge");
                if(nodes.get(a).kind.equals("fixed_operator")&&nodes.get(b).kind.equals("fixed_operator"))fixedEdges++;
            }
            var table=row.getAsJsonArray("return_table");int target=row.get("target").getAsInt();
            if(table.size()!=nodes.size()||target<0||target>=nodes.size()||!"real_west_lift".equals(row.get("default_target").getAsString())
                    ||!nodes.get(target).kind.equals("public")||nodes.get(target).feet.distanceToSqr(new Vec3(-28.5,-394,-284.5))>.000001)
                throw new IllegalArgumentException("Return table lacks the original same-floor west landing");
            int[] next=new int[nodes.size()];double[] metres=new double[nodes.size()];
            for(int i=0;i<next.length;i++)
            {
                var r=table.get(i).getAsJsonObject();next[i]=r.get("next").getAsInt();metres[i]=r.get("metres").getAsDouble();
                if(next[i]<0||next[i]>=next.length||!Double.isFinite(metres[i])||metres[i]<0)throw new IllegalArgumentException("Invalid return distance");
            }
            for(int i=0;i<next.length;i++)
            {
                if(i==target){if(next[i]!=i||metres[i]!=0)throw new IllegalArgumentException("Invalid landing root");continue;}
                if(!edges.contains(edge(i,next[i]))||metres[next[i]]>=metres[i]
                        ||Math.abs(metres[i]-metres[next[i]]-nodes.get(i).feet.distanceTo(nodes.get(next[i]).feet))>.00001)
                    throw new IllegalArgumentException("Cyclic/nonwalking return table");
                if(nodes.get(i).kind.equals("public")&&!nodes.get(next[i]).kind.equals("public"))
                    throw new IllegalArgumentException("A public return cannot enter a private operator lane");
            }
            scopes.add(new Scope(id,v,side,List.copyOf(gates),List.copyOf(nodes),target,next,metres,Set.copyOf(edges)));
        }
        if(scopes.size()!=6||identities.size()!=6||!allFixed.equals(floors)||allGates.size()!=12||fixedEdges!=291)throw new IllegalArgumentException("Incomplete202/291/six gate scope");
        return new Contract(List.copyOf(scopes),List.copyOf(owners));
    }
    private static Result blocked(Status status,String scope,Vec3 here,String text)
    { return new Result(status,scope,here,null,text,false); }
    private static AABB body(Vec3 p)
    { return new AABB(p.x-.3,p.y+.001,p.z-.3,p.x+.3,p.y+1.8,p.z+.3); }
    private static boolean loaded(ServerLevel level,AABB box)
    {
        for(int x=net.minecraft.util.Mth.floor(box.minX)>>4;x<=net.minecraft.util.Mth.floor(box.maxX-.0001)>>4;x++)
            for(int z=net.minecraft.util.Mth.floor(box.minZ)>>4;z<=net.minecraft.util.Mth.floor(box.maxZ-.0001)>>4;z++)
                if(!level.hasChunk(x,z)||!level.areEntitiesLoaded(ChunkPos.asLong(x,z)))return false;
        return true;
    }
    private static boolean occupied(ServerPlayer player,AABB box)
    {
        var level=player.serverLevel();
        return !level.noCollision(player,box)||!level.getEntities(player,box,e->e.isAlive()&&!e.isSpectator()
                &&!(e instanceof ArmorStand stand&&stand.isMarker())&&(e instanceof LivingEntity||e.canBeCollidedWith())).isEmpty();
    }
    private static boolean support(ServerPlayer player,Node node)
    {
        var level=player.serverLevel();if(!level.hasChunkAt(node.support)||level.getBlockEntity(node.support)!=null)return false;
        var state=level.getBlockState(node.support);if(!TvPersonnelPlatformRecipeR44.stateKey(state).equals(node.state))return false;
        double top=Double.NEGATIVE_INFINITY;
        for(var b:state.getCollisionShape(level,node.support,CollisionContext.of(player)).toAabbs())
            if(node.support.getX()+b.minX<node.feet.x+.3&&node.support.getX()+b.maxX>node.feet.x-.3
                    &&node.support.getZ()+b.minZ<node.feet.z+.3&&node.support.getZ()+b.maxZ>node.feet.z-.3)
                top=Math.max(top,node.support.getY()+b.maxY);
        return Math.abs(top-node.feet.y)<.0001;
    }
    private static int locate(ServerPlayer player,Scope scope)
    {
        int best=-1;double distance=Double.POSITIVE_INFINITY;var actual=player.position();
        if(!loaded(player.serverLevel(),body(actual)))return -1;
        if(!player.serverLevel().noCollision(player,body(actual)))return -1;
        // Being near the lane is insufficient: the actor must already have real bearing.
        var sole=new AABB(actual.x-.3,actual.y-.06,actual.z-.3,actual.x+.3,actual.y+.015,actual.z+.3);
        if(!player.serverLevel().getBlockCollisions(player,sole).iterator().hasNext())return -1;
        for(int i=0;i<scope.nodes.size();i++)
        {
            var n=scope.nodes.get(i);double tolerance=n.kind.equals("fixed_operator")?.8:.1;
            if(Math.floor(actual.x)!=Math.floor(n.feet.x)||Math.floor(actual.z)!=Math.floor(n.feet.z)||Math.abs(actual.y-n.feet.y)>tolerance)continue;
            double d=actual.distanceToSqr(n.feet);
            if(d<distance&&support(player,n)){best=i;distance=d;}
        }
        return best;
    }
    public static Result guide(ServerPlayer player,Contract document,String selected)
    {
        if(player.isSpectator()||player.isPassenger())return blocked(Status.NOT_ON_FOOT,selected,null,"请先回到可站立的人行踏面。");
        var data=Optional.of(document);
        Scope scope=null;int node=-1;double best=Double.POSITIVE_INFINITY;
        for(var s:data.get().scopes)
        {
            if(!selected.isEmpty()&&!selected.equals(s.id))continue;
            int i=locate(player,s);if(i<0)continue;
            // A private floor always selects its owner; public nodes only guide outwards.
            double cost=s.nodes.get(i).kind.equals("fixed_operator")?-1:s.metres[i];
            if(cost<best){scope=s;node=i;best=cost;}
        }
        if(scope==null)return blocked(Status.NO_OWNED_ROUTE,selected,null,"这里没有登记的固定人员踏面；请使用真实入口或设备出口流程。");
        var here=scope.nodes.get(node);int nextId=scope.next[node];var next=scope.nodes.get(nextId);var level=player.serverLevel();
        boolean operator=!here.kind.equals("public")||!next.kind.equals("public");
        if(operator)
        {
            if(!TvPersonnelPlatformInterlockR44.enabled(level)||!TvCageCollisionR44.enabled())return blocked(Status.FLAGS_DISABLED,scope.id,here.feet,"人员平台的实际碰撞与门联锁尚未启用，请循现场出口流程撤离。");
            for(var owner:data.get().owners)
            {
                if(owner.variant!=scope.variant)continue;
                if(!level.hasChunkAt(owner.pos)||!loaded(level,new AABB(owner.pos)))return blocked(Status.UNLOADED,scope.id,here.feet,"本机人员区尚未完整加载，请等待设施就绪。");
                if(level.getBlockEntity(owner.pos)!=null||!TvPersonnelPlatformRecipeR44.alreadyOwned(level.getBlockState(owner.pos),owner.state))return blocked(Status.OWNER_CHANGED,scope.id,here.feet,"本机人员区安装或归属已变化，请使用现场安全出口流程。");
            }
            double x=-11.5+42*scope.variant;
            if(!loaded(level,new AABB(x-2,-445,-242,x+2,-439,-237)))return blocked(Status.UNLOADED,scope.id,here.feet,"设备实体区域尚未加载。");
            var diagnostic=TvPersonnelPlatformInterlockR44.gateDiagnostic(level,scope.gates.get(0),player);
            if(!diagnostic.get("metadata_valid").getAsBoolean()||!"PARKED".equals(diagnostic.get("fleet_phase").getAsString())
                    ||diagnostic.get("actual_gantry_count").getAsInt()!=1)return blocked(Status.MACHINE_UNAVAILABLE,scope.id,here.feet,"设备尚未停靠或实际支架未就绪，请等待现场人员确认。");
            double clock=diagnostic.getAsJsonArray("actual_gantry_clocks").get(0).getAsDouble();
            if(!Double.isFinite(clock)||(clock>.001&&clock<.999))return blocked(Status.MACHINE_UNAVAILABLE,scope.id,here.feet,"设备正在运动，请等待平台静止。");
            boolean open=level.getBlockState(scope.gates.get(0)).getValue(DoorBlock.OPEN);
            for(var lower:scope.gates)for(var q:List.of(lower,lower.above()))
                if(level.getBlockState(q).getValue(DoorBlock.OPEN)!=open)return blocked(Status.GATE_INCONSISTENT,scope.id,here.feet,"登记安全门四半片状态不一致，请使用现场安全出口流程。");
            if((here.kind.equals("gate")||next.kind.equals("gate"))&&!open)return blocked(Status.GATE_CLOSED,scope.id,here.feet,"前方是本操作区登记安全门，请按现场权限或出口开关操作后继续。");
        }
        if(!loaded(level,body(next.feet)))return blocked(Status.UNLOADED,scope.id,here.feet,"前方踏面或实体分区尚未加载。");
        if(!support(player,next))return blocked(Status.SUPPORT_CHANGED,scope.id,here.feet,"前方实际踏面或分数高度已变化，请停步并循现场出口流程。");
        double y=Math.max(here.feet.y,next.feet.y);
        var sweep=body(new Vec3(here.feet.x,y,here.feet.z)).minmax(body(new Vec3(next.feet.x,y,next.feet.z)));
        if(!loaded(level,sweep))return blocked(Status.UNLOADED,scope.id,here.feet,"前方通道尚未完整加载。");
        if(occupied(player,sweep))return blocked(Status.OCCUPIED,scope.id,here.feet,"前方通道被人员或设备占用，请等待通道清空。");
        boolean arrived=node==scope.target;String cue;
        if(arrived)cue="已到本层西侧电梯层门；请在门外呼梯并等待轿厢到层。";
        else if(Math.abs(next.feet.y-here.feet.y)>.063)cue="沿当前登记梯段"+(next.feet.y>here.feet.y?"上行":"下行")+"，返回本层安全门与西侧电梯。";
        else cue="沿当前踏面向"+(next.feet.x>here.feet.x?"东":next.feet.x<here.feet.x?"西":next.feet.z>here.feet.z?"南":"北")+"行走 · 距本层西侧层门约 "+Math.max(1,Math.round(scope.metres[node]))+" m";
        return new Result(arrived?Status.ARRIVED:Status.READY,scope.id,here.feet,next.feet,cue,arrived);
    }
    private OperatorNavigationEngineR45() { }
}

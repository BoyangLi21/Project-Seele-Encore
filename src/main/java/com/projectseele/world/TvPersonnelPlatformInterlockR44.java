package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervCarrierPlatformEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.state.properties.DoubleBlockHalf;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import java.nio.file.Files;
import java.util.*;

/** Finite installed staff surfaces; never a world-wide movement/entity scan. */
public final class TvPersonnelPlatformInterlockR44
{
    private record Gate(int variant, BlockPos first, BlockPos second) { }
    private record Contract(Map<Integer, List<AABB>> areas, Map<BlockPos, Gate> gates,
                            Map<Integer, Map<BlockPos, net.minecraft.world.level.block.state.BlockState>> installed) { }
    private record Cached(int tick, String digest, Optional<Contract> value) { }
    private static final Map<MinecraftServer, Cached> CACHE = new WeakHashMap<>();
    private static final Map<MinecraftServer, Boolean> MODEL_CACHE=new WeakHashMap<>();
    private static final String METADATA_SHA256="4639b70111d26065402032f5a58b7ada2088960fba0566718dccd1e4e4d00d98";
    private static final String MODEL_SHA256="2a789960d2649118b12505be8d6c93888ed8e1cabe6beaef0c20f498b12551a3";
    private static final TicketType<ChunkPos> STAFF_REVIEW_TICKET=TicketType.create(
            "r44_staff_clearance",Comparator.comparingLong(ChunkPos::toLong),40);
    private static final Set<BlockPos> EXPECTED = new HashSet<>();
    static
    {
        for (int bay = 0; bay < 3; bay++)
        {
            int x = -12 + bay * 42;
            for (int q : new int[]{x - 16, x - 15}) EXPECTED.add(new BlockPos(q, -394, -264));
            if (bay < 2) for (int q : new int[]{x + 15, x + 16}) EXPECTED.add(new BlockPos(q, -394, -264));
        }
        EXPECTED.add(new BlockPos(89, -394, -246));
        EXPECTED.add(new BlockPos(89, -394, -245));
    }

    public static boolean enabled(ServerLevel level)
    {
        return com.projectseele.config.PortableRuntimeOwnersR45.personnelPlatforms()
                && level.dimension().location().toString().equals("projectseele:geofront");
    }

    private static BlockPos point(com.google.gson.JsonArray q)
    {
        if (q.size() != 3) throw new IllegalArgumentException("Staff owner requires three coordinates");
        return new BlockPos(q.get(0).getAsInt(), q.get(1).getAsInt(), q.get(2).getAsInt());
    }

    private static Optional<Contract> load(byte[] bytes)
    {
        try
        {
            var document = JsonParser.parseString(new String(bytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
            if (document.get("schema").getAsInt() != 44
                    || !document.get("dimension").getAsString().equals("projectseele:geofront"))
                throw new IllegalArgumentException("Wrong staff-platform contract");
            var areas = new HashMap<Integer, List<AABB>>();
            var sides=new HashSet<String>();int volumeCount=0;
            for (var value : document.getAsJsonArray("operator_volumes"))
            {
                var row = value.getAsJsonObject(); int variant = row.get("variant").getAsInt();
                int side=row.get("side").getAsInt();
                if(side!=-1&&side!=1)throw new IllegalArgumentException("Unknown personnel side");
                sides.add(variant+"/"+side);volumeCount++;
                var b = row.getAsJsonArray("bounds");
                if (variant < 0 || variant > 2 || b.size() != 6) throw new IllegalArgumentException("Invalid staff volume");
                double[] p = new double[6];
                for (int i = 0; i < 6; i++)
                {
                    p[i] = b.get(i).getAsDouble();
                    if (!Double.isFinite(p[i])) throw new IllegalArgumentException("Non-finite staff volume");
                }
                if (p[0] >= p[3] || p[1] >= p[4] || p[2] >= p[5]
                        || p[0] < -45 || p[3] > 110 || p[1] < -400 || p[4] > -385
                        || p[2] < -265 || p[5] > -244)
                    throw new IllegalArgumentException("Staff volume exceeds declared local facility");
                areas.computeIfAbsent(variant, ignored -> new ArrayList<>()).add(new AABB(p[0],p[1],p[2],p[3],p[4],p[5]));
            }
            var gates = new HashMap<BlockPos, Gate>();
            for (var value : document.getAsJsonArray("entry_gate_pairs"))
            {
                var row=value.getAsJsonObject(); int variant=row.get("variant").getAsInt();
                int side=row.get("side").getAsInt();
                var positions=row.getAsJsonArray("lower_positions");
                if (variant < 0 || variant > 2 || positions.size()!=2) throw new IllegalArgumentException("Invalid staff gate pair");
                var gate=new Gate(variant,point(positions.get(0).getAsJsonArray()),point(positions.get(1).getAsJsonArray()));
                int x=-12+42*variant;
                Set<BlockPos> pair=variant==2&&side==1?Set.of(new BlockPos(89,-394,-246),new BlockPos(89,-394,-245))
                    :side==-1?Set.of(new BlockPos(x-16,-394,-264),new BlockPos(x-15,-394,-264))
                    :side==1?Set.of(new BlockPos(x+15,-394,-264),new BlockPos(x+16,-394,-264)):Set.of();
                if(!pair.equals(Set.of(gate.first,gate.second)))throw new IllegalArgumentException("Gate variant/side owner mismatch");
                for (var pos: List.of(gate.first,gate.second))
                    if (!EXPECTED.contains(pos) || gates.put(pos,gate)!=null) throw new IllegalArgumentException("Unknown/duplicate staff gate owner");
            }
            if (gates.size()!=12 || areas.size()!=3 || sides.size()!=6 || volumeCount!=208)
                throw new IllegalArgumentException("Incomplete six-side staff installation");
            var provenance=document.getAsJsonObject("owner_provenance");
            if(provenance.getAsJsonArray("six_sides").size()!=6 || provenance.getAsJsonArray("floor_cells").size()!=202)
                throw new IllegalArgumentException("Missing complete floor provenance");
            var installed=new HashMap<Integer,Map<BlockPos,net.minecraft.world.level.block.state.BlockState>>();
            var owned=new HashSet<BlockPos>();int floors=0,guards=0,doors=0;
            for(var item:provenance.getAsJsonArray("installed_owned_operations"))
            {
                var row=item.getAsJsonObject();var pos=point(row.getAsJsonArray("position"));
                if(!TvPersonnelPlatformRecipeR44.ownsPosition(pos)||!owned.add(pos))throw new IllegalArgumentException("Foreign/duplicate installed owner");
                var after=TvPersonnelPlatformRecipeR44.parse(row.get("after").getAsString());
                if(after.getBlock() instanceof TvPersonnelDeckR44)floors++;
                else if(after.getBlock() instanceof TvPersonnelGuardR44)guards++;
                else if(after.getBlock() instanceof CityPersonnelDoorR44)doors++;
                else throw new IllegalArgumentException("Foreign installed block");
                int variant=net.minecraft.util.Mth.clamp(Math.round((pos.getX()+11.5F)/42F),0,2);
                installed.computeIfAbsent(variant,ignored->new HashMap<>()).put(pos,after);
            }
            if(floors!=202||guards!=201||doors!=24||owned.size()!=427)throw new IllegalArgumentException("Incomplete427 installed source owners");
            return Optional.of(new Contract(areas,gates,installed));
        }
        catch (Exception failure)
        {
            ProjectSeele.LOGGER.error("R44 staff-platform contract unavailable; only its owned access/machinery is inhibited", failure);
            return Optional.empty();
        }
    }

    private static Optional<Contract> contract(ServerLevel level)
    {
        var server=level.getServer();int tick=server.getTickCount();var cached=CACHE.get(server);
        if(cached!=null&&cached.tick==tick)return cached.value;
        byte[] bytes=null;String digest="missing";
        try
        {
            var path=server.getWorldPath(LevelResource.ROOT).resolve("r44_tv_personnel_platforms.json");
            if(Files.isRegularFile(path)){bytes=Files.readAllBytes(path);digest=java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes));}
        }
        catch(Exception ignored){digest="unavailable";}
        if(cached!=null&&cached.digest.equals(digest)){CACHE.put(server,new Cached(tick,digest,cached.value));return cached.value;}
        Optional<Contract> value=digest.equals(METADATA_SHA256)?load(bytes):Optional.empty();
        if(value.isEmpty())ProjectSeele.LOGGER.warn("R44 finite personnel metadata missing, changed or invalid; owned equipment remains inhibited");
        CACHE.put(server,new Cached(tick,digest,value));return value;
    }

    private static boolean crew(ServerLevel level, Entity actor, int variant)
    {
        if (!(actor instanceof LivingEntity) || !actor.isAlive() || actor.isSpectator()
                || actor instanceof ArmorStand stand && stand.isMarker()) return false;
        var canonical=EvaFleetSavedData.get(level.getServer()).canonicalId(variant);
        if (canonical.isPresent() && (actor.getUUID().equals(canonical.get())
                || actor.getRootVehicle().getUUID().equals(canonical.get()))) return false;
        if (canonical.isPresent()&&actor.getRootVehicle() instanceof NervCarrierPlatformEntity carrier
                && carrier.getPassengers().stream().anyMatch(e->e.getUUID().equals(canonical.get())))return false;
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(variant);
        // Only the legitimate pilot already inside this bay's canonical plug
        // is excluded. A pilot standing outside remains an actual occupant.
        return fleet.isEmpty()||fleet.get().entryPlugId()==null
                ||!actor.getRootVehicle().getUUID().equals(fleet.get().entryPlugId());
    }

    public static Optional<String> movementFault(ServerLevel level, int variant)
    {
        return crewFault(level,variant,true);
    }

    /** Construction requires known empty personnel sections, not already-built floors. */
    public static Optional<String> constructionFault(ServerLevel level,int variant)
    {
        return crewFault(level,variant,false);
    }

    private static boolean modelReady(MinecraftServer server)
    {
        return MODEL_CACHE.computeIfAbsent(server,ignored->
        {
            try(var model=TvPersonnelPlatformInterlockR44.class.getResourceAsStream("/assets/projectseele/mesh/tv_shoulder_shells_r44.json"))
            {return model!=null&&java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(model.readAllBytes())).equals(MODEL_SHA256);}
            catch(Exception failure){return false;}
        });
    }

    private static Optional<String> crewFault(ServerLevel level,int variant,boolean installedRequired)
    {
        if (!enabled(level)) return Optional.empty();
        var contract=contract(level);
        if (contract.isEmpty()) return Optional.of("检修平台状态尚未确认，暂缓整备。");
        if(installedRequired)
        {
            var pilot=TrainingPilotDirector.existingPilotR45(level,variant);
            if(pilot!=null&&pilot.getPersistentData().getBoolean("SeelePilotDoorClosePendingR46"))
                return Optional.of("登机通道的安全门还没关好，整备暂停。");
        }
        var volumes=contract.get().areas.get(variant);
        if (volumes==null || volumes.isEmpty()) return Optional.of("检修平台不完整，暂缓整备。");
        for (var volume:volumes)
            for (int x=net.minecraft.util.Mth.floor(volume.minX)>>4;x<=net.minecraft.util.Mth.floor(volume.maxX-.0001)>>4;x++)
                for (int z=net.minecraft.util.Mth.floor(volume.minZ)>>4;z<=net.minecraft.util.Mth.floor(volume.maxZ-.0001)>>4;z++)
                    if (!level.hasChunk(x,z) || !level.areEntitiesLoaded(ChunkPos.asLong(x,z)))
                        return Optional.of("还没有收到检修平台的清场确认，请稍候。");
        if(installedRequired)
        {
            if(!modelReady(level.getServer()))return Optional.of("检修平台设备状态异常，暂缓整备。");
            var cells=contract.get().installed.get(variant);
            if(cells==null)return Optional.of("检修平台设备记录不完整，暂缓整备。");
            for(var cell:cells.entrySet())
                if(!level.hasChunkAt(cell.getKey())||level.getBlockEntity(cell.getKey())!=null
                    ||!TvPersonnelPlatformRecipeR44.alreadyOwned(level.getBlockState(cell.getKey()),cell.getValue()))
                    return Optional.of("人员平台地板、围护或门扇安装不完整："+cell.getKey());
            for(var gate:new HashSet<>(contract.get().gates.values()))
                if(gate.variant==variant)
                {
                    boolean open=level.getBlockState(gate.first).getValue(DoorBlock.OPEN);
                    for(var pos:List.of(gate.first,gate.first.above(),gate.second,gate.second.above()))
                        if(level.getBlockState(pos).getValue(DoorBlock.OPEN)!=open)return Optional.of("检修平台的安全门没有正常闭合。");
                }
        }
        AABB union=volumes.get(0);
        for (int i=1;i<volumes.size();i++) union=union.minmax(volumes.get(i));
        for (var actor:level.getEntities((Entity)null,union,e->crew(level,e,variant)))
            for (var volume:volumes)
                if (volume.intersects(actor.getBoundingBox()))
                    return Optional.of("检修平台还有人员未撤离："+actor.getName().getString());
        return Optional.empty();
    }

    public static Optional<String> prepareFault(ServerLevel level,int variant)
    {
        if (!enabled(level) || variant<0 || variant>2)return Optional.empty();
        var data=contract(level);
        if (data.isPresent())
            for (var volume:data.get().areas.get(variant))
                for (int x=net.minecraft.util.Mth.floor(volume.minX)>>4;x<=net.minecraft.util.Mth.floor(volume.maxX-.0001)>>4;x++)
                    for (int z=net.minecraft.util.Mth.floor(volume.minZ)>>4;z<=net.minecraft.util.Mth.floor(volume.maxZ-.0001)>>4;z++)
                    {
                        var chunk=new ChunkPos(x,z);
                        level.getChunkSource().addRegionTicket(STAFF_REVIEW_TICKET,chunk,2,chunk);
                        level.getChunk(x,z);
                    }
        // Chunk requests do not repair/spawn the airframe, alter a plug or
        // change a phase. Entity sections must actually attach before PASS.
        var fault=movementFault(level,variant);
        if(fault.isPresent())return fault;
        double x=-11.5+42*variant;
        var gantries=level.getEntitiesOfClass(NervCarrierPlatformEntity.class,new AABB(x-2,-445,-242,x+2,-439,-237),
                e->e.isAlive()&&e.isRestraintGantry()&&e.getUnitVariant()==variant);
        if(gantries.size()!=1)return Optional.of("本机实际拘束设备缺失或重复，不能开始整备／发射。");
        return Optional.empty();
    }

    /** A dispatch may open only the original pilot's matching parked bay doors. */
    public static Optional<String> openForOriginalBoardingPilotR46(ServerLevel level,
            com.projectseele.entity.TrainingPilotEntity pilot)
    {
        if(!enabled(level))return Optional.empty();
        int variant=pilot.getAssignedVariant();
        if(TrainingPilotDirector.existingPilotR45(level,variant)!=pilot)
            return Optional.of("驾驶员与这台机体的登记不符，不能开启登机通道。");
        var data=contract(level);var fleet=EvaFleetSavedData.get(level.getServer()).entry(variant);
        if(data.isEmpty()||fleet.isEmpty()||fleet.get().phase()!=EvaFleetSavedData.Phase.PARKED)
            return Optional.of("机体和检修平台还没有准备好，驾驶员先在原地待命。");
        var installed=data.get().installed.get(variant);
        if(installed==null||!modelReady(level.getServer()))return Optional.of("这台机体的检修平台暂时不能使用。");
        for(var cell:installed.entrySet())
            if(!level.hasChunkAt(cell.getKey())||level.getBlockEntity(cell.getKey())!=null
                    ||!TvPersonnelPlatformRecipeR44.alreadyOwned(level.getBlockState(cell.getKey()),cell.getValue()))
                return Optional.of("本机人员平台完整组件已改变，门保持现状："+cell.getKey());
        double x=-11.5+42*variant;
        var gantries=level.getEntitiesOfClass(NervCarrierPlatformEntity.class,new AABB(x-2,-445,-242,x+2,-439,-237),
                e->e.isAlive()&&e.isRestraintGantry()&&e.getUnitVariant()==variant);
        if(gantries.size()!=1)return Optional.of("拘束架尚未就位，驾驶员先在原地待命。");
        float clock=gantries.get(0).getRestraintProgress();
        if(clock>.001f&&clock<.999f)return Optional.of("拘束架还在移动，请驾驶员稍候。");
        var gates=new HashSet<>(data.get().gates.values());
        for(var gate:gates)if(gate.variant==variant)
        {
            boolean open=level.getBlockState(gate.first).getValue(DoorBlock.OPEN);
            for(var pos:List.of(gate.first,gate.first.above(),gate.second,gate.second.above()))
                if(level.getBlockState(pos).getValue(DoorBlock.OPEN)!=open)
                    return Optional.of("登机通道的安全门状态异常，请先检查安全门。");
            if(!open)for(var pos:List.of(gate.first,gate.second))
                if(!level.getEntities((Entity)null,new AABB(pos).expandTowards(0,1,0),
                        e->e!=pilot&&crew(level,e,variant)).isEmpty())return Optional.of("门口还有人，请驾驶员稍候。");
        }
        var opened=pilot.getPersistentData().getList("SeelePilotOpenedGatesR46",net.minecraft.nbt.Tag.TAG_LONG);
        var recorded=new HashSet<Long>();for(var value:opened)recorded.add(((net.minecraft.nbt.NumericTag)value).getAsLong());
        for(var gate:gates)if(gate.variant==variant&&!level.getBlockState(gate.first).getValue(DoorBlock.OPEN)
                &&recorded.add(gate.first.asLong()))opened.add(net.minecraft.nbt.LongTag.valueOf(gate.first.asLong()));
        pilot.getPersistentData().put("SeelePilotOpenedGatesR46",opened);
        pilot.getPersistentData().putBoolean("SeelePilotDoorClosePendingR46",false);
        for(var gate:gates)if(gate.variant==variant)
            for(var pos:List.of(gate.first,gate.second))
            {
                var state=level.getBlockState(pos);
                ((DoorBlock)state.getBlock()).setOpen(pilot,level,state,pos,true);
            }
        return Optional.empty();
    }

    public static void finishPilotDoorUseR46(ServerLevel level,com.projectseele.entity.TrainingPilotEntity pilot)
    {
        if(pilot.getPersistentData().getList("SeelePilotOpenedGatesR46",net.minecraft.nbt.Tag.TAG_LONG).isEmpty())return;
        pilot.getPersistentData().putBoolean("SeelePilotDoorClosePendingR46",true);
        tickPilotDoorClosureR46(level,pilot);
    }

    /** Persist only doors this dispatch actually opened; preserve prior user-open doors. */
    public static void tickPilotDoorClosureR46(ServerLevel level,com.projectseele.entity.TrainingPilotEntity pilot)
    {
        if(!pilot.getPersistentData().getBoolean("SeelePilotDoorClosePendingR46"))return;
        int variant=pilot.getAssignedVariant();var data=contract(level);
        if(data.isEmpty()||TrainingPilotDirector.existingPilotR45(level,variant)!=pilot)return;
        var remaining=new net.minecraft.nbt.ListTag();
        for(var value:pilot.getPersistentData().getList("SeelePilotOpenedGatesR46",net.minecraft.nbt.Tag.TAG_LONG))
        {
            var at=BlockPos.of(((net.minecraft.nbt.NumericTag)value).getAsLong());
            var gate=data.get().gates.get(at);boolean complete=gate!=null&&gate.variant==variant&&gate.first.equals(at);
            if(complete)for(var pos:List.of(gate.first,gate.first.above(),gate.second,gate.second.above()))
            {
                var expected=data.get().installed.get(variant).get(pos);
                complete&=expected!=null&&level.hasChunkAt(pos)&&level.getBlockEntity(pos)==null
                        &&TvPersonnelPlatformRecipeR44.alreadyOwned(level.getBlockState(pos),expected);
            }
            if(!complete){remaining.add(value.copy());continue;}
            boolean occupied=false;
            for(var pos:List.of(gate.first,gate.second))
                occupied|=!level.getEntities((Entity)null,new AABB(pos).expandTowards(0,1,0),e->crew(level,e,variant)).isEmpty();
            if(occupied){remaining.add(value.copy());continue;}
            for(var pos:List.of(gate.first,gate.second))
            {
                var state=level.getBlockState(pos);((DoorBlock)state.getBlock()).setOpen(pilot,level,state,pos,false);
            }
        }
        pilot.getPersistentData().put("SeelePilotOpenedGatesR46",remaining);
        if(remaining.isEmpty())pilot.getPersistentData().remove("SeelePilotDoorClosePendingR46");
    }

    public static boolean handleUse(ServerLevel level, BlockPos clicked, Player player)
    {
        if (!enabled(level)) return false;
        var state=level.getBlockState(clicked);
        BlockPos lower=state.getValue(DoorBlock.HALF)==DoubleBlockHalf.UPPER?clicked.below():clicked;
        if (!EXPECTED.contains(lower)) return false;
        var contract=contract(level);
        var gate=contract.isPresent()?contract.get().gates.get(lower):finiteGate(lower);
        boolean emergencyExit=contract.isEmpty()&&insideActualOwnedFloor(level,gate,player);
        if (contract.isEmpty()&&!emergencyExit) { message(player,"人员平台归属不可用，外部入口保持关闭。"); return true; }
        for (var pos:List.of(gate.first,gate.second))
        {
            var actual=level.getBlockState(pos);
            if (!(actual.getBlock() instanceof CityPersonnelDoorR44)
                    || actual.getValue(DoorBlock.HALF)!=DoubleBlockHalf.LOWER
                    || !level.getBlockState(pos.above()).is(actual.getBlock()))
            { message(player,"人员平台门对不完整，保持现状。"); return true; }
        }
        boolean opening=!level.getBlockState(lower).getValue(DoorBlock.OPEN);
        boolean inside=emergencyExit||contract.get().areas.get(gate.variant).stream().anyMatch(v->v.intersects(player.getBoundingBox()));
        if (opening && !inside)
        {
            var fleet=EvaFleetSavedData.get(level.getServer()).entry(gate.variant);
            double x=-11.5+gate.variant*42;
            var gantries=level.getEntitiesOfClass(NervCarrierPlatformEntity.class,new AABB(x-2,-445,-242,x+2,-439,-237),
                    e->e.isAlive()&&e.isRestraintGantry()&&e.getUnitVariant()==gate.variant);
            if (fleet.isEmpty() || fleet.get().phase()!=EvaFleetSavedData.Phase.PARKED || gantries.size()!=1)
            { message(player,"设备尚未停稳或实际拘束设备不可用，请在公共走廊等候。"); return true; }
            float clock=gantries.get(0).getRestraintProgress();
            if (clock>.001f && clock<.999f)
            { message(player,"拘束机构尚在中间位置，请等候检修端位。"); return true; }
        }
        if (!opening||emergencyExit)
        {
            // Conservative complete leaf cells cover both actual endpoints
            // and the entire hinge sweep, rather than only the closed plane.
            for (var pos:List.of(gate.first,gate.second))
                if (!level.getEntities((Entity)null,new AABB(pos).expandTowards(0,1,0),e->crew(level,e,gate.variant)).isEmpty())
                { message(player,"门扇范围有人，请先退到门外或人员台内。"); return true; }
        }
        for (var pos:List.of(gate.first,gate.second))
        {
            var actual=level.getBlockState(pos);
            ((DoorBlock)actual.getBlock()).setOpen(player,level,actual,pos,opening);
        }
        return true;
    }

    /** Observational failure evidence for the actual installed gate. */
    public static com.google.gson.JsonObject gateDiagnostic(ServerLevel level,BlockPos clicked,Player player)
    {
        var row=new com.google.gson.JsonObject();row.addProperty("enabled",enabled(level));
        var state=level.getBlockState(clicked);row.addProperty("state",TvPersonnelPlatformRecipeR44.stateKey(state));
        var lower=state.hasProperty(DoorBlock.HALF)&&state.getValue(DoorBlock.HALF)==DoubleBlockHalf.UPPER?clicked.below():clicked;
        var data=contract(level);row.addProperty("metadata_valid",data.isPresent());
        if(!EXPECTED.contains(lower))return row;
        var gate=data.isPresent()?data.get().gates.get(lower):finiteGate(lower);
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(gate.variant);
        row.addProperty("variant",gate.variant);row.addProperty("fleet_phase",fleet.map(e->e.phase().name()).orElse("missing"));
        row.addProperty("inside_operator_area",data.isPresent()&&data.get().areas.get(gate.variant).stream().anyMatch(v->v.intersects(player.getBoundingBox())));
        double x=-11.5+gate.variant*42;
        var machines=level.getEntitiesOfClass(NervCarrierPlatformEntity.class,new AABB(x-2,-445,-242,x+2,-439,-237),e->e.isAlive()&&e.isRestraintGantry()&&e.getUnitVariant()==gate.variant);
        row.addProperty("actual_gantry_count",machines.size());
        var clocks=new com.google.gson.JsonArray();machines.forEach(e->clocks.add(e.getRestraintProgress()));row.add("actual_gantry_clocks",clocks);
        return row;
    }

    private static Gate finiteGate(BlockPos lower)
    {
        for(int v=0;v<3;v++)
        {
            int x=-12+42*v;
            for(int side:new int[]{-1,1})
            {
                BlockPos a=v==2&&side==1?new BlockPos(89,-394,-246):new BlockPos(x+(side<0?-16:15),-394,-264);
                BlockPos b=v==2&&side==1?new BlockPos(89,-394,-245):a.east();
                if(lower.equals(a)||lower.equals(b))return new Gate(v,a,b);
            }
        }
        throw new IllegalArgumentException("Foreign personnel gate");
    }
    /** A corrupt metadata file may inhibit entry, but never traps a worker on a real owned lane. */
    private static boolean insideActualOwnedFloor(ServerLevel level,Gate gate,Player player)
    {
        for(var pos:TvPersonnelPlatformRecipeR44.ownerPositions())
            if(Math.round((pos.getX()+11.5F)/42F)==gate.variant&&level.hasChunkAt(pos)
                    &&level.getBlockState(pos).getBlock() instanceof TvPersonnelDeckR44
                    &&new AABB(pos).expandTowards(0,3,0).intersects(player.getBoundingBox()))return true;
        return false;
    }

    public static boolean ownsManualDoor(ServerLevel level, BlockPos position)
    {
        if (!enabled(level)) return false;
        var state=level.getBlockState(position);
        if (!(state.getBlock() instanceof CityPersonnelDoorR44)) return false;
        return EXPECTED.contains(state.getValue(DoorBlock.HALF)==DoubleBlockHalf.UPPER?position.below():position);
    }

    private static void message(Player player,String text)
    {
        player.displayClientMessage(net.minecraft.network.chat.Component.literal(text),true);
    }
    private TvPersonnelPlatformInterlockR44() { }
}

package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EvaGroundReceiverR50;
import com.projectseele.entity.EvaBodyPose;
import com.projectseele.entity.NervHangarDoorEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.AreaEffectCloud;
import net.minecraft.world.entity.ExperienceOrb;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.projectile.Projectile;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.*;

/** Original lower launch-bed exit, bounded physical transfer, and same-bay return. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class UndergroundSortieR48
{
    private static final int[] X={-12,30,72},DOOR_Z={-13,-10,-7};
    private static final Set<String> MODES=Set.of("IDLE","OPENING","OUTBOUND","DEPLOYED","RECEIVING","RECOVER_OPENING","RETURNING");
    private static final Map<MinecraftServer,Boolean> ENABLED=new WeakHashMap<>();
    private static final Map<ServerLevel,Map<Integer,UUID>> RECOVERY_CALLERS=new WeakHashMap<>();
    private static final Map<ServerLevel,Map<UUID,String>> LAST_ENTITY_OBSTRUCTION_R50=new WeakHashMap<>();
    private static final Map<ServerLevel,Set<UUID>> TRANSIENT_CLEARANCE_REPORTED_R50=new WeakHashMap<>();
    private static final Map<ServerLevel,Map<UUID,String>> LAST_PAD_SUPPORT_DIAGNOSTIC_R50=new WeakHashMap<>();
    private static final TicketType<ChunkPos> TICKET=TicketType.create("r48_underground_sortie",Comparator.comparingLong(ChunkPos::toLong),100);
    private static final class Row
    {
        UUID eva,owner,pilot;String mode="IDLE",fault="";boolean requested,collisionOpen,launchCancelled;
        Vec3 from=Vec3.ZERO;int age,duration;long lastTick=-1;CompoundTag extra=new CompoundTag();
    }
    private static final class State extends SavedData
    {
        final Map<Integer,Row> rows=new HashMap<>();CompoundTag extra=new CompoundTag();
        static State load(CompoundTag tag)
        {
            var data=new State();data.extra=tag.copy();
            for(var value:tag.getList("Rows",Tag.TAG_COMPOUND))
            {
                var raw=(CompoundTag)value;int v=raw.getInt("Variant");
                if(v<0||v>2||data.rows.containsKey(v))throw new IllegalStateException("Foreign underground sortie target");
                var row=new Row();row.extra=raw.copy();row.mode=raw.getString("Mode");
                if(!MODES.contains(row.mode))throw new IllegalStateException("Unknown underground carrier mode");
                if(raw.hasUUID("Eva"))row.eva=raw.getUUID("Eva");if(raw.hasUUID("Owner"))row.owner=raw.getUUID("Owner");if(raw.hasUUID("Pilot"))row.pilot=raw.getUUID("Pilot");
                row.requested=raw.getBoolean("Open");row.collisionOpen=raw.getBoolean("CollisionOpen");row.launchCancelled=raw.getBoolean("LaunchCancelled");row.age=raw.getInt("Age");row.duration=raw.getInt("Duration");row.fault=raw.getString("Fault");
                row.from=new Vec3(raw.getDouble("FromX"),raw.getDouble("FromY"),raw.getDouble("FromZ"));
                if(!Double.isFinite(row.from.x+row.from.y+row.from.z)||row.age<0||row.duration<0||row.age>row.duration)
                    throw new IllegalStateException("Invalid original underground carrier clock");
                data.rows.put(v,row);
            }
            return data;
        }
        @Override public CompoundTag save(CompoundTag tag)
        {
            tag=extra.copy();tag.putInt("Version",48);var list=new ListTag();
            rows.forEach((v,row)->{
                var raw=row.extra.copy();raw.putInt("Variant",v);raw.putString("Mode",row.mode);raw.putString("Fault",row.fault);
                if(row.eva!=null)raw.putUUID("Eva",row.eva);if(row.owner!=null)raw.putUUID("Owner",row.owner);if(row.pilot!=null)raw.putUUID("Pilot",row.pilot);
                raw.putBoolean("Open",row.requested);raw.putBoolean("CollisionOpen",row.collisionOpen);raw.putBoolean("LaunchCancelled",row.launchCancelled);raw.putInt("Age",row.age);raw.putInt("Duration",row.duration);
                raw.putDouble("FromX",row.from.x);raw.putDouble("FromY",row.from.y);raw.putDouble("FromZ",row.from.z);list.add(raw);
            });tag.put("Rows",list);return tag;
        }
    }
    private static State state(ServerLevel level)
    {return level.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_underground_sortie_r48");}
    private static Row row(ServerLevel level,int v){return state(level).rows.computeIfAbsent(v,key->new Row());}
    private static BlockPos bed(int v){return new BlockPos(X[v],-411,-36);}
    private static Vec3 bedFeet(int v){return new Vec3(X[v]+.5,-410,-35.5);}
    public static Vec3 padFeet(int v){return new Vec3(X[v]+.5,-410,6.5);}
    public static Vec3 airReceiverFeetR50(int v){return new Vec3(X[v]+.5,-410,100.5);}
    private static boolean airReceiverInstalledR50(ServerLevel level,int v)
    {
        var path=level.getServer().getWorldPath(LevelResource.ROOT).resolve("r50_underground_airport.json");
        if(!Files.isRegularFile(path))return false;
        try
        {
            var root=JsonParser.parseString(Files.readString(path)).getAsJsonObject();
            if(root.get("schema").getAsInt()!=50||!root.get("installed").getAsBoolean())return false;
            for(var raw:root.getAsJsonArray("receivers"))
            {
                var entry=raw.getAsJsonObject();if(entry.get("variant").getAsInt()!=v)continue;
                var p=entry.getAsJsonArray("feet");return new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()).distanceToSqr(airReceiverFeetR50(v))<.0001;
            }
        }
        catch(Exception failure){ProjectSeele.LOGGER.warn("R50 underground receiver receipt could not be read: {}",failure.toString());}
        return false;
    }
    private static int[] planes(int v){return new int[]{-19,-18,-17,DOOR_Z[v]};}
    private static boolean enabled(ServerLevel level)
    {
        if(!level.dimension().equals(FacilitySchemaV2.DIMENSION))return false;
        return ENABLED.computeIfAbsent(level.getServer(),server->{
            var file=server.getWorldPath(LevelResource.ROOT).resolve("r48_underground_sortie.json");if(!Files.isRegularFile(file))return false;
            try
            {
                var root=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                if(root.get("schema").getAsInt()!=48||!root.get("installed").getAsBoolean()||!root.get("dimension").getAsString().equals("projectseele:geofront"))return false;
                var found=new HashSet<Integer>();
                for(var raw:root.getAsJsonArray("plans"))
                {
                    var plan=raw.getAsJsonObject();int v=plan.get("variant").getAsInt();var b=plan.getAsJsonArray("bed");var p=plan.getAsJsonArray("pad");
                    if(v<0||v>2||!found.add(v)||b.size()!=3||p.size()!=3||b.get(0).getAsInt()!=X[v]||b.get(1).getAsInt()!=-411||b.get(2).getAsInt()!=-36
                            ||p.get(0).getAsInt()!=X[v]||p.get(1).getAsInt()!=-411||p.get(2).getAsInt()!=6||plan.get("clear_width").getAsInt()!=31)return false;
                }
                return found.size()==3;
            }
            catch(Exception failure){ProjectSeele.LOGGER.error("R48 original underground frontage receipt rejected",failure);return false;}
        });
    }
    private static boolean canonical(ServerLevel level,int v,EvaUnit01Entity unit)
    {
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(v).orElse(null);
        return unit!=null&&unit.isAlive()&&!unit.isExperimentalUnit()&&unit.getUnitVariant()==v&&fleet!=null
                &&fleet.canonicalId().equals(unit.getUUID())&&EvaLogisticsDirector.isAssignedLowerLaunchBed(level,v,bed(v));
    }
    private static boolean authority(ServerPlayer caller,int v,EvaUnit01Entity unit)
    {
        if(caller==null||caller.serverLevel()!=unit.level()||caller.isSpectator()||!caller.isAlive()||!NervStaffDialogue.authorized(caller))return false;
        var pilot=unit.getPilotEntity();
        if(PilotReturnR39.ownsRecoveryR50(caller.serverLevel(),unit,caller.getUUID()))return true;
        if(pilot==null)
        {
            var binding=row(caller.serverLevel(),v);
            return caller.getUUID().equals(binding.owner)&&binding.eva!=null&&binding.eva.equals(unit.getUUID())
                    &&Set.of("DEPLOYED","RECEIVING","RECOVER_OPENING","RETURNING").contains(binding.mode)
                    &&EntryPlugEjectionR48.originalFieldEjection(caller.serverLevel(),v,unit,binding.pilot)
                    &&EntryPlugEjectionR48.recoveryCallerBlocker(caller,unit).isEmpty();
        }
        if(!pilot.isAlive())return false;
        if(pilot==caller&&EvaPilotResolver.controlTarget(caller)==unit)return true;
        var sortie=TvCampaignSavedData.get(caller.serverLevel()).sorties.get(v);
        return sortie!=null&&caller.getUUID().equals(sortie.commander)&&unit.getUUID().equals(sortie.eva)
                &&pilot.getUUID().equals(sortie.pilotR45)&&(!AutoSortieR32.missionToken(caller.serverLevel()).isEmpty()
                    ||StaffRecoveryR47.queuedBy(caller,v));
    }
    private static boolean bound(ServerLevel level,int v,EvaUnit01Entity unit,Row row)
    {return enabled(level)&&canonical(level,v,unit)&&row.eva!=null&&row.eva.equals(unit.getUUID())
            &&row.pilot!=null&&(unit.getPilotEntity()!=null&&row.pilot.equals(unit.getPilotEntity().getUUID())
                ||Set.of("DEPLOYED","RECEIVING","RECOVER_OPENING","RETURNING").contains(row.mode)
                    &&EntryPlugEjectionR48.originalFieldEjection(level,v,unit,row.pilot));}
    private static ServerPlayer owner(ServerLevel level,Row row)
    {return row.owner==null?null:level.getServer().getPlayerList().getPlayer(row.owner);}
    private static void retain(ServerLevel level,int v)
    {
        int end=row(level,v).extra.getBoolean("AirReceiverR50")?119:17;
        for(int x=(X[v]-35)>>4;x<=(X[v]+35)>>4;x++)for(int z=-52>>4;z<=end>>4;z++)
        {var p=new ChunkPos(x,z);level.getChunkSource().addRegionTicket(TICKET,p,2,p);level.getChunk(x,z);}
    }
    private static String dryPlant(ServerLevel level,int v,EvaUnit01Entity unit)
    {
        if(!level.getBlockState(bed(v)).is(Blocks.LODESTONE))return "地下整备床尚未就绪，请等待整备部门确认。";
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(v).orElse(null);
        if(fleet==null||fleet.lclLayers()!=0||EvaHangarBuilder.countLclEnvelope(level,RegionalFacilityLayout.evaOrigin(level),v)!=0)
            return "湿舱尚未排空 LCL，地下出口暂时关闭。";
        if(NervAirLiftR30.ownsMotion(unit)||NervAirLiftR30.waitingAtHead(unit)||com.projectseele.entity.EvaAirTransportR31.active(unit)
                ||com.projectseele.entity.EvaBayRepairR33.active(unit)||unit.refreshTvPersonnelClockHoldR44())return "机体正在转运或检修，请等作业结束。";
        if(!EntryPlugDirector.hasLaunchLock(level,v,unit)&&!emptyRecoveryR49(level,v,unit))return "插入栓或舱盖尚未锁定，请确认驾驶员已就座。";
        return "";
    }
    public static boolean emptyRecoveryR49(ServerLevel level,int v,EvaUnit01Entity unit)
    {
        var binding=row(level,v);
        return binding.eva!=null&&binding.eva.equals(unit.getUUID())
                &&Set.of("DEPLOYED","RECEIVING","RECOVER_OPENING","RETURNING").contains(binding.mode)
                &&EntryPlugEjectionR48.originalFieldEjection(level,v,unit,binding.pilot);
    }
    private static boolean inPortal(int v,BlockPos p)
    {return p.getX()>=X[v]-15&&p.getX()<=X[v]+15&&p.getY()>=-410&&p.getY()<=-346&&Arrays.stream(planes(v)).anyMatch(z->z==p.getZ());}
    /** These native transient objects do not occupy a person/equipment berth.
     * Keep their damage, lifetime and pickup ticks intact; a modded subtype
     * with actual collision remains an obstruction. No noPhysics whitelist. */
    private static boolean transientNonObstructionR50(Entity entity)
    {
        return !entity.canBeCollidedWith()&&(entity instanceof ItemEntity||entity instanceof ExperienceOrb
                ||entity instanceof Projectile||entity instanceof AreaEffectCloud);
    }
    private static boolean entityOccupiesClearanceR50(Entity entity,EvaUnit01Entity unit)
    {
        return entity.isAlive()&&!entity.isSpectator()&&(unit==null||entity!=unit&&entity.getRootVehicle()!=unit)
                &&!transientNonObstructionR50(entity);
    }
    private static String entityOwnerR50(Entity entity)
    {
        if(entity instanceof com.projectseele.entity.NervCarrierPlatformEntity carrier)
        {
            var plug=carrier.getCranePlug();
            return "variant="+carrier.getUnitVariant()+",lift="+carrier.getLiftId()+",persistent="+carrier.isPersistentLift()
                    +",gantry="+carrier.isRestraintGantry()+",crane="+carrier.isPlugCrane()
                    +",plug="+(plug==null?"none":plug.getUUID());
        }
        if(entity instanceof com.projectseele.entity.EntryPlugCarrierEntity plug)
            return "variant="+plug.getAssignedVariant()+",host="+plug.getHostEvaUuid()+",stage="+plug.getInsertionStage();
        if(entity instanceof EvaUnit01Entity eva)
            return "variant="+eva.getUnitVariant()+",pilot="+(eva.getPilotEntity()==null?"none":eva.getPilotEntity().getUUID());
        var data=entity.getPersistentData();
        return data.hasUUID("R32SortieCommander")?"commander="+data.getUUID("R32SortieCommander"):"root="+entity.getRootVehicle().getUUID();
    }
    private static void entityObstructionR50(ServerLevel level,EvaUnit01Entity unit,AABB body,List<Entity> entities,String context)
    {
        var blockers=new ArrayList<>(entities);blockers.sort(Comparator.comparing(Entity::getUUID));var first=blockers.get(0);
        String signature=context+":"+first.getUUID();var recorded=LAST_ENTITY_OBSTRUCTION_R50.computeIfAbsent(level,key->new HashMap<>());
        if(signature.equals(recorded.put(unit.getUUID(),signature)))return;
        for(var entity:blockers.stream().limit(8).toList())
            ProjectSeele.LOGGER.warn("R50 underground entity obstruction: unit={} context={} sweep={} type={} uuid={} bbox={} owner={} noPhysics={} nativeCollision={} total={}",
                    unit.getUUID(),context,body,net.minecraft.core.registries.BuiltInRegistries.ENTITY_TYPE.getKey(entity.getType()),
                    entity.getUUID(),entity.getBoundingBox(),entityOwnerR50(entity),entity.noPhysics,entity.canBeCollidedWith(),blockers.size());
    }
    private static boolean occupied(ServerLevel level,int v,EvaUnit01Entity unit)
    {
        var area=new AABB(X[v]-34,-410,-20,X[v]+35,-345,DOOR_Z[v]+2);
        return !level.getEntities((Entity)null,area,e->entityOccupiesClearanceR50(e,unit)&&!(e instanceof NervHangarDoorEntity)).isEmpty();
    }
    private static String corridor(ServerLevel level,int v,EvaUnit01Entity unit,Vec3 from,Vec3 to,boolean closedAllowed)
    {
        var body=unit.getDimensions(net.minecraft.world.entity.Pose.STANDING).makeBoundingBox(from)
                .minmax(unit.getDimensions(net.minecraft.world.entity.Pose.STANDING).makeBoundingBox(to)).deflate(.001);
        for(var p:BlockPos.betweenClosed(BlockPos.containing(body.minX,body.minY,body.minZ),BlockPos.containing(body.maxX,body.maxY,body.maxZ)))
        {
            if(!level.hasChunkAt(p))return "承载通路信号尚未接通，请稍候。";
            if(!level.getFluidState(p).isEmpty())return "承载通路尚未排空，请等待排液完成。";
            var block=level.getBlockState(p);
            if(closedAllowed&&inPortal(v,p)&&block.is(Blocks.BARRIER))continue;
            for(var shape:block.getCollisionShape(level,p).toAabbs())if(shape.move(p).intersects(body))return "承载通路有障碍，请清理："+p.toShortString();
        }
        var nearby=level.getEntities((Entity)null,body,e->e.isAlive()&&!e.isSpectator()&&e!=unit&&e.getRootVehicle()!=unit
                &&!(e instanceof NervHangarDoorEntity));
        var blockers=nearby.stream().filter(e->entityOccupiesClearanceR50(e,unit)).toList();
        if(!blockers.isEmpty())
        {entityObstructionR50(level,unit,body,blockers,"corridor");return "承载通路有人或其他机体，请先让开。";}
        LAST_ENTITY_OBSTRUCTION_R50.computeIfAbsent(level,key->new HashMap<>()).remove(unit.getUUID());
        if(!nearby.isEmpty()&&TRANSIENT_CLEARANCE_REPORTED_R50.computeIfAbsent(level,key->new HashSet<>()).add(unit.getUUID()))
        {
            var entity=nearby.get(0);
            ProjectSeele.LOGGER.info("R50 underground native transient objects retained without occupying berth: unit={} type={} uuid={} bbox={} count={}",
                    unit.getUUID(),net.minecraft.core.registries.BuiltInRegistries.ENTITY_TYPE.getKey(entity.getType()),entity.getUUID(),entity.getBoundingBox(),nearby.size());
        }
        return "";
    }
    private static boolean padSupported(ServerLevel level,int v,EvaUnit01Entity unit)
    {return padSupportFault(level,v,unit).isEmpty();}
    private static AABB receiverWorldBoxR50(EvaUnit01Entity unit,AABB local)
    {
        AABB result=null;float yaw=(180-unit.getYRot())*net.minecraft.util.Mth.DEG_TO_RAD;
        for(double x:new double[]{local.minX,local.maxX})for(double y:new double[]{local.minY,local.maxY})for(double z:new double[]{local.minZ,local.maxZ})
        {
            var rotated=new org.joml.Vector3f((float)x,(float)y,(float)z).rotateY(yaw);
            Vec3 point=unit.position().add(rotated.x,rotated.y,rotated.z);var box=new AABB(point,point);
            result=result==null?box:result.minmax(box);
        }
        return result;
    }
    private static double overlapR50(AABB a,AABB b)
    {return Math.max(0,Math.min(a.maxX,b.maxX)-Math.max(a.minX,b.minX))
            *Math.max(0,Math.min(a.maxY,b.maxY)-Math.max(a.minY,b.minY))
            *Math.max(0,Math.min(a.maxZ,b.maxZ)-Math.max(a.minZ,b.minZ));}
    private static boolean receiverBearingR50(ServerLevel level,int variant,BlockPos p)
    {
        var block=level.getBlockState(p);
        if(block.is(com.projectseele.registry.ModBlocks.NERV_FLOOR_PANEL.get()))return true;
        // UG02 installs two flush steel running strips in this exact section
        // of each original axis. Other iron blocks are not receiving floors.
        return variant>=0&&variant<3&&p.getY()==-411&&p.getZ()>=6&&p.getZ()<=82
                &&Math.abs(p.getX()-X[variant])==13&&block.is(Blocks.IRON_BLOCK)
                &&airReceiverInstalledR50(level,variant);
    }
    private static String receivingDeckFaultR50(ServerLevel level,EvaUnit01Entity unit)
    {
        int x=net.minecraft.util.Mth.floor(unit.getX()),z=net.minecraft.util.Mth.floor(unit.getZ());
        for(var p:BlockPos.betweenClosed(x-15,-411,z-11,x+15,-411,z+10))
            if(!level.hasChunkAt(p)||level.getBlockEntity(p)!=null||!level.getFluidState(p).isEmpty()
                    ||!receiverBearingR50(level,unit.getUnitVariant(),p)
                    ||!level.getBlockState(p).isCollisionShapeFullBlock(level,p))
                return "接应平台支撑有变化，请检修："+p.toShortString();
        return "";
    }
    /** Check the measured limb envelopes, including people and the ejected original capsule.
     * Existing conservative hull contact may decrease; no new solid overlap is admitted. */
    private static String receiverSweepR50(ServerLevel level,EvaUnit01Entity unit,EvaBodyPose.Sample before,EvaBodyPose.Sample after)
    {
        var previous=EvaBodyPose.posedCarrierHulls(unit,before);var next=EvaBodyPose.posedCarrierHulls(unit,after);
        if(previous.isEmpty()||previous.size()!=next.size())return "接应平台尚未确认机体姿态，请等待检查。";
        for(int i=0;i<next.size();i++)
        {
            var a=receiverWorldBoxR50(unit,previous.get(i));var b=receiverWorldBoxR50(unit,next.get(i));var sweep=a.minmax(b).deflate(.001);
            for(var p:BlockPos.betweenClosed(BlockPos.containing(sweep.minX,sweep.minY,sweep.minZ),BlockPos.containing(sweep.maxX,sweep.maxY,sweep.maxZ)))
            {
                if(!level.hasChunkAt(p))return "接应平台通路信号尚未接通："+p.toShortString();
                var block=level.getBlockState(p);if(block.isAir())continue;
                // posedCarrierHulls adds an 8 cm numerical margin. The actual
                // lowest mesh vertex is kept on the deck by poseAt; that margin
                // is allowed to touch only this recorded receiving floor.
                if(p.getY()==-411&&b.minY>=-410.081
                        &&receiverBearingR50(level,unit.getUnitVariant(),p)
                        &&level.getBlockEntity(p)==null&&level.getFluidState(p).isEmpty()
                        &&block.isCollisionShapeFullBlock(level,p))continue;
                for(var shape:block.getCollisionShape(level,p).toAabbs())
                {
                    var obstacle=shape.move(p);
                    if(overlapR50(sweep,obstacle)>overlapR50(a,obstacle)+.001)
                        return "接应机械臂整姿受阻："+p.toShortString()+"（部件 "+i+"）。";
                }
                if(!level.getFluidState(p).isEmpty()&&overlapR50(sweep,new AABB(p))>overlapR50(a,new AABB(p))+.001)
                    return "接应机械臂通路有液体："+p.toShortString();
            }
            for(var entity:level.getEntities((Entity)null,sweep,e->entityOccupiesClearanceR50(e,unit)
                    &&!(e instanceof NervHangarDoorEntity)&&(e instanceof net.minecraft.world.entity.LivingEntity||e.canBeCollidedWith())))
                if(overlapR50(sweep,entity.getBoundingBox())>overlapR50(a,entity.getBoundingBox())+.001)
                    return "接应机械臂附近有人或设备："+entity.getType()+"。";
        }
        return "";
    }
    private static String padRejectedR50(ServerLevel level,int v,EvaUnit01Entity unit,String code,String message,List<AABB> feet)
    {
        var previous=LAST_PAD_SUPPORT_DIAGNOSTIC_R50.computeIfAbsent(level,key->new HashMap<>());
        if(!code.equals(previous.put(unit.getUUID(),code)))
            ProjectSeele.LOGGER.warn("R50 underground pad support rejected: variant={} eva={} code={} reason={} root={} expectedSoleY=-410 footBoxes={} shutdownMode={}",
                    v,unit.getUUID(),code,message,unit.position(),feet,com.projectseele.entity.EvaShutdownR30.mode(unit));
        return message;
    }
    private static String padSupportFault(ServerLevel level,int v,EvaUnit01Entity unit)
    {
        boolean outer=row(level,v).extra.getBoolean("AirReceiverR50")&&airReceiverInstalledR50(level,v);
        var target=outer?airReceiverFeetR50(v):padFeet(v);
        if(unit.position().distanceToSqr(target)>36||Math.abs(unit.getY()+410)>.1)
            return padRejectedR50(level,v,unit,"root-foot-goal","请将机体停回本机地下接应平台。",List.of());
        // Both real feet use one shared pose/world sample. The broad entity
        // box also contains suspended arms and is not a bearing footprint.
        var pose=com.projectseele.entity.EvaBodyPose.sample(unit,1);
        var world=com.projectseele.entity.EvaRifleKinematics.world(unit,1);
        var feet=com.projectseele.entity.EvaBodyPose.posedFootSupportHullsR48(unit,pose,world);
        if(feet.size()!=2)return padRejectedR50(level,v,unit,"shared-feet-missing","机体足部状态尚未确认，请等待检查。",feet);
        for(var foot:feet)
        {
            if(Math.abs(foot.minY+410)>.15)return padRejectedR50(level,v,unit,"sole-height","机体尚未站稳，请调整到平台中央。",feet);
            var entities=level.getEntities((Entity)null,foot.deflate(.001),e->entityOccupiesClearanceR50(e,unit)
                    &&(e instanceof net.minecraft.world.entity.LivingEntity||e.canBeCollidedWith()));
            if(!entities.isEmpty())
            {entityObstructionR50(level,unit,foot,entities,"pad-foot-support");return padRejectedR50(level,v,unit,"foot-entity","机体足下有人或设备，请先让开。",feet);}
            for(var p:BlockPos.betweenClosed(net.minecraft.util.Mth.floor(foot.minX+.001),-411,net.minecraft.util.Mth.floor(foot.minZ+.001),
                    net.minecraft.util.Mth.floor(foot.maxX-.001),-411,net.minecraft.util.Mth.floor(foot.maxZ-.001)))
            {
                // The installed apron is 35x29. Actual feet extend beyond
                // the old 18x18 coarse-box sample; check the real pad boundary.
                if(p.getX()<X[v]-17||p.getX()>X[v]+17||p.getZ()<(outer?83:-12)||p.getZ()>(outer?118:16))return padRejectedR50(level,v,unit,"foot-outside-pad","机体足部超出平台边缘，请调整站位："+p.toShortString(),feet);
                if(!level.hasChunkAt(p))return padRejectedR50(level,v,unit,"support-chunk-unloaded","足下平台信号尚未接通："+p.toShortString(),feet);
                if(!level.getFluidState(p).isEmpty())return padRejectedR50(level,v,unit,"support-fluid","足下平台有液体，请等待排液："+p.toShortString(),feet);
                if(level.getBlockEntity(p)!=null||!receiverBearingR50(level,v,p))
                    return padRejectedR50(level,v,unit,"support-owner-changed","平台支撑有变化，请检修："+p.toShortString(),feet);
                if(!level.getBlockState(p).isCollisionShapeFullBlock(level,p))return padRejectedR50(level,v,unit,"support-not-full","机体足下缺少支撑，请调整站位："+p.toShortString(),feet);
            }
        }
        LAST_PAD_SUPPORT_DIAGNOSTIC_R50.computeIfAbsent(level,key->new HashMap<>()).remove(unit.getUUID());
        return "";
    }
    private static boolean doorReady(ServerLevel level,int v)
    {return row(level,v).collisionOpen&&level.getEntitiesOfClass(NervHangarDoorEntity.class,
            new AABB(X[v]-1,-411,DOOR_Z[v]-1,X[v]+2,-409,DOOR_Z[v]+1),e->e.getVariant()==v&&e.getOpenProgress(1)>=.999F).size()==1
            &&completePortalState(level,v,true);}
    private static boolean completePortalState(ServerLevel level,int v,boolean open)
    {
        for(int z:planes(v))for(var p:BlockPos.betweenClosed(X[v]-15,-410,z,X[v]+15,-346,z))
        {
            if(!level.hasChunkAt(p)||level.getBlockEntity(p)!=null||!level.getFluidState(p).isEmpty())return false;
            var block=level.getBlockState(p);if(open?!block.isAir():!block.is(Blocks.BARRIER))return false;
        }
        return true;
    }
    private static boolean neighbourReady(ServerLevel level,int v,boolean carrierTrip)
    {
        for(int other=0;other<3;other++)if(Math.abs(other-v)==1)
        {
            var gate=row(level,other);if(motion(gate))return false;
            if(!carrierTrip)continue;
            if(gate.requested||gate.collisionOpen)return false;
            final int selected=other;var centre=new Vec3(X[other]+.5,-410,DOOR_Z[other]);
            if(level.getEntitiesOfClass(NervHangarDoorEntity.class,new AABB(centre,centre).inflate(1),e->e.getVariant()==selected&&e.getOpenProgress(1)>.001F).size()>0)return false;
        }
        return true;
    }
    private static boolean motion(Row row){return Set.of("OPENING","OUTBOUND","RECEIVING","RECOVER_OPENING","RETURNING").contains(row.mode);}
    private static EvaLogisticsDirector.ActionResult result(boolean accepted,String text){return new EvaLogisticsDirector.ActionResult(accepted,text);}
    public static EvaLogisticsDirector.ActionResult request(ServerPlayer caller,int v,boolean open)
    {
        var level=caller.serverLevel();if(v<0||v>2||!enabled(level))return result(false,"地下出口尚未开放，请联系整备部门。");
        EvaLogisticsDirector.loadControlTarget(level,v);retain(level,v);var unit=EvaLogisticsDirector.canonicalUnit(level,v);
        if(!canonical(level,v,unit)||!authority(caller,v,unit))return result(false,"请由本机驾驶员或指挥员操作地下出口。");
        if(open)
        {
            String equipment=StaffOperationsR48.undergroundEquipmentBlockerR49(level,unit);
            if(!equipment.isEmpty())return result(false,equipment);
        }
        var row=row(level,v);var fleet=EvaFleetSavedData.get(level.getServer()).entry(v).orElseThrow();
        if(!open)
        {
            if(Set.of("OUTBOUND","RECEIVING","RECOVER_OPENING","RETURNING").contains(row.mode))return result(false,"承载板正在运送机体，请等运输结束后再关门。");
            if(row.eva!=null&&!row.eva.equals(unit.getUUID()))return result(false,"门控机体识别信号不符，请核对编号。");
            row.requested=false;
            if(row.mode.equals("OPENING"))
            {
                if(row.launchCancelled&&fleet.phase()==EvaFleetSavedData.Phase.SILO_READY
                        &&unit.position().distanceToSqr(bedFeet(v))<=.25&&EntryPlugDirector.hasLaunchLock(level,v,unit))unit.armPreparedLaunch(bed(v));
                row.mode="IDLE";row.launchCancelled=false;
            }
            state(level).setDirty();maintainDoor(level,v);
            return result(true,occupied(level,v,null)?"门域有人或机体，出口保持开启直到清空。":"地下出口已请求关闭。");
        }
        if(!Set.of(EvaFleetSavedData.Phase.SILO_READY,EvaFleetSavedData.Phase.DEPLOYED).contains(fleet.phase()))return result(false,"请先完成整备，待机体进入发射待命后再开启地下出口。");
        if(motion(row))return result(false,"本机出口正在开门或运送，请等待作业完成。");
        if(!neighbourReady(level,v,fleet.phase()==EvaFleetSavedData.Phase.SILO_READY))
            return result(false,"相邻出口正在开门或运送，请等其作业结束并关门。");
        String fault=dryPlant(level,v,unit);if(!fault.isEmpty())return result(false,fault);
        if(occupied(level,v,unit))return result(false,"出口门旁有人或设备，请清空开门通路。");
        if(fleet.phase()==EvaFleetSavedData.Phase.SILO_READY)
        {
            if(unit.position().distanceToSqr(bedFeet(v))>.25||unit.hasActiveCarrierMotion()||unit.isLaunchCommandReleased())return result(false,"机体尚未在整备床停稳，或弹射已经开始，暂时不能转入地下出口。");
            fault=corridor(level,v,unit,bedFeet(v),padFeet(v),true);if(!fault.isEmpty())return result(false,fault);
            row.mode="OPENING";
        }
        else if(!bound(level,v,unit,row)||!row.mode.equals("DEPLOYED"))return result(false,"本机尚未从此地下出口出动，请核对机体与出口。");
        row.eva=unit.getUUID();row.owner=caller.getUUID();if(unit.getPilotEntity()!=null)row.pilot=unit.getPilotEntity().getUUID();row.requested=true;row.fault="";
        if(row.mode.equals("OPENING"))
        {
            var reserved=EvaLogisticsDirector.requestUndergroundDepartureR48(caller,v,row.eva);
            if(!reserved.accepted()){row.mode="IDLE";row.requested=false;state(level).setDirty();return reserved;}
            row.launchCancelled=true;
        }
        state(level).setDirty();maintainDoor(level,v);
        return result(true,"地下出口正在开启，门全开后由承载板送往外侧平台。");
    }
    public static boolean departureAuthorizedR48(ServerPlayer caller,int v,EvaUnit01Entity unit)
    {var level=caller.serverLevel();var row=row(level,v);return bound(level,v,unit,row)&&row.mode.equals("OPENING")
            &&caller.getUUID().equals(row.owner)&&authority(caller,v,unit)&&neighbourReady(level,v,true)&&dryPlant(level,v,unit).isEmpty();}
    public static boolean reservesLaunchR48(ServerLevel level,int v,EvaUnit01Entity unit)
    {if(v<0||v>2||!enabled(level))return false;var row=row(level,v);return bound(level,v,unit,row)&&Set.of("OPENING","OUTBOUND").contains(row.mode);}
    public static boolean cancelledReservationR48(ServerLevel level,int v,EvaUnit01Entity unit)
    {return reservesLaunchR48(level,v,unit)&&row(level,v).launchCancelled;}
    public static boolean recoveryAuthorizedR48(ServerLevel level,int v,EvaUnit01Entity unit)
    {var row=row(level,v);return bound(level,v,unit,row)&&row.mode.equals("RECOVER_OPENING")&&authority(owner(level,row),v,unit)
            &&doorReady(level,v)&&neighbourReady(level,v,true)&&padSupported(level,v,unit)&&dryPlant(level,v,unit).isEmpty();}
    public static boolean finishAuthorizedR48(ServerLevel level,int v,EvaUnit01Entity unit,boolean returning)
    {
        var row=row(level,v);return bound(level,v,unit,row)&&row.mode.equals(returning?"RETURNING":"OUTBOUND")&&row.age>=row.duration
                &&doorReady(level,v)&&authority(owner(level,row),v,unit)&&unit.position().distanceToSqr(returning?bedFeet(v):padFeet(v))<.01
                &&(returning||padSupported(level,v,unit));
    }
    public static boolean deployedBindingR48(ServerLevel level,int v,EvaUnit01Entity unit)
    {
        if(!enabled(level)||v<0||v>2)return false;var row=row(level,v);
        if(!bound(level,v,unit,row))return false;
        // An original underground unit returned by the existing aircraft to its
        // own surface head keeps the normal surface-descent recovery path.
        if(row.mode.equals("DEPLOYED")&&unit.position().distanceTo(NervAirLiftR30.head(level,v))<10)return false;
        return Set.of("DEPLOYED","RECEIVING","RECOVER_OPENING","RETURNING").contains(row.mode);
    }
    public static boolean recoveringR48(ServerLevel level,int v,EvaUnit01Entity unit)
    {return enabled(level)&&v>=0&&v<3&&bound(level,v,unit,row(level,v))&&Set.of("RECEIVING","RECOVER_OPENING","RETURNING").contains(row(level,v).mode);}
    public static boolean atDeployedPadR48(ServerLevel level,int v,EvaUnit01Entity unit)
    {return deployedBindingR48(level,v,unit)&&row(level,v).mode.equals("DEPLOYED")&&padSupported(level,v,unit);}
    /** Select the recorded underground route before testing its readiness.
     * Pilot/ejection proof and complete feet are admission interlocks, not a
     * reason to dispatch an aircraft to the same deep underground airframe. */
    public static boolean undergroundRecoveryRouteR50(ServerLevel level,int v,EvaUnit01Entity unit)
    {
        if(v<0||v>2||!enabled(level)||unit==null||unit.level()!=level||unit.isExperimentalUnit()||unit.getUnitVariant()!=v)return false;
        var route=row(level,v);var fleet=EvaFleetSavedData.get(level.getServer()).entry(v).orElse(null);
        if(fleet==null||!fleet.canonicalId().equals(unit.getUUID())||route.eva==null||!route.eva.equals(unit.getUUID())
                ||!Set.of("DEPLOYED","RECEIVING","RECOVER_OPENING","RETURNING").contains(route.mode))return false;
        // A previously underground unit legitimately delivered to the real
        // surface head/sea arena keeps the ordinary aircraft/surface route.
        return !route.mode.equals("DEPLOYED")||unit.getY()<-345.0D;
    }
    /** A fresh explicit caller context, or an already accepted same-owner staff job, owns recovery. */
    public static EvaLogisticsDirector.ActionResult requestRecoveryR48(ServerPlayer caller,int v)
    {
        var level=caller.serverLevel();if(v<0||v>2||!enabled(level))return result(false,"地下接应平台尚未开放，请联系整备部门。");
        EvaLogisticsDirector.loadControlTarget(level,v);var unit=EvaLogisticsDirector.canonicalUnit(level,v);var row=row(level,v);
        if(!canonical(level,v,unit)||!bound(level,v,unit,row)||!caller.getUUID().equals(row.owner)||!authority(caller,v,unit))
            return result(false,"请由本次出动的操作员确认本机驾驶员与编成后请求回收。");
        var contexts=RECOVERY_CALLERS.computeIfAbsent(level,key->new HashMap<>());contexts.put(v,caller.getUUID());
        try{return EvaLogisticsDirector.requestRecovery(level,v);}finally{contexts.remove(v);}
    }
    public static EvaLogisticsDirector.ActionResult recoverR48(ServerLevel level,int v,EvaUnit01Entity unit)
    {
        var row=row(level,v);var caller=owner(level,row);
        if(!bound(level,v,unit,row)||!authority(caller,v,unit))return result(false,"本机指挥员或驾驶员信息有变化，请重新确认回收许可。");
        boolean explicit=caller.getUUID().equals(RECOVERY_CALLERS.getOrDefault(level,Map.of()).get(v));
        if(!explicit&&!StaffRecoveryR47.queuedBy(caller,v))return result(false,"请由本次出动的操作员通过电话请求回收，或使用 /nerv underground recover 指定机体。");
        if(!row.mode.equals("DEPLOYED"))return result(false,"本机地下回收已在进行，请等待作业结束。");
        retain(level,v);
        if(!neighbourReady(level,v,true))return result(false,"相邻出口尚未关闭或承载板正在运送，请稍候再回收。");
        if(unit.position().distanceToSqr(padFeet(v))>36||Math.abs(unit.getY()+410)>.15)
            return result(false,"请呼叫地下运输机送往本机接应平台，或自行驾驶返回平台。");
        if(!EvaLogisticsDirector.recoveryMotionSettled(unit)||unit.hasActiveCarrierMotion()||unit.isLaunchSequenceActive())
            return result(false,"请将机体开回本机接应平台并停稳。");
        String fault=dryPlant(level,v,unit);if(fault.isEmpty())fault=receivingDeckFaultR50(level,unit);if(!fault.isEmpty())return result(false,fault);
        // A powerless airframe can be frozen halfway through a step. Requiring
        // both soles to be flat made precisely those legitimate loads unrecoverable.
        EvaGroundReceiverR50.begin(unit);row.mode="RECEIVING";row.fault="";state(level).setDirty();
        return result(true,"接应平台开始固定机体。姿态调整完成后，开门送回机库。");
    }
    /** Called by the original underground aircraft only after its measured touchdown.
     * Ownership and the original capsule remain authoritative across the handoff. */
    public static EvaLogisticsDirector.ActionResult acceptAirDeliveryR50(ServerLevel level,int v,EvaUnit01Entity unit,UUID commander)
    {
        if(v<0||v>2||!enabled(level)||!canonical(level,v,unit)||!airReceiverInstalledR50(level,v))
            return result(false,"地下接应平台或机体信号尚未就绪，请稍候。");
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(v).orElse(null);
        var caller=level.getServer().getPlayerList().getPlayer(commander);var route=row(level,v);
        if(fleet==null||fleet.phase()!=EvaFleetSavedData.Phase.DEPLOYED||caller==null
                ||!EntryPlugEjectionR48.recoveryCallerBlocker(caller,unit).isEmpty())return result(false,"回收指挥员或机体状态有变化，请重新确认。");
        if(route.mode.equals("RECEIVING")&&commander.equals(route.owner)&&unit.getUUID().equals(route.eva)
                &&EvaGroundReceiverR50.active(unit))return result(true,"地下接应平台已接收机体。");
        Vec3 touchdown=AirCradleClearanceR31.landingRoot(unit,airReceiverFeetR50(v),unit.getYRot());
        if(!Set.of("IDLE","DEPLOYED").contains(route.mode)||unit.position().distanceToSqr(touchdown)>.25
                ||!com.projectseele.entity.EvaAirTransportR31.active(unit)||unit.getDeltaMovement().lengthSqr()>.001)
            return result(false,"机体尚未落稳在本机接应平台，或平台仍在运行，请等待。");
        UUID pilot=unit.getPilotEntity()==null?unit.getPersistentData().hasUUID("R49EjectedPilot")?
                unit.getPersistentData().getUUID("R49EjectedPilot"):null:unit.getPilotEntity().getUUID();
        if(pilot==null||unit.getPilotEntity()==null&&!EntryPlugEjectionR48.originalFieldEjection(level,v,unit,pilot))
            return result(false,"驾驶员或插入栓信号尚未确认，吊架保持夹持，等待联络。");
        // Establish only the actual new mechanical handoff. This does not alter
        // fleet phase, health, inventory, UUIDs, pilot location or the pickup pose.
        var oldEva=route.eva;var oldOwner=route.owner;var oldPilot=route.pilot;var oldMode=route.mode;
        route.eva=unit.getUUID();route.owner=commander;route.pilot=pilot;route.mode="DEPLOYED";
        if(!authority(caller,v,unit))
        {route.eva=oldEva;route.owner=oldOwner;route.pilot=oldPilot;route.mode=oldMode;return result(false,"驾驶员的接应许可尚未确认，运输机保持悬停。");}
        String baseFault=receivingDeckFaultR50(level,unit);
        if(!baseFault.isEmpty())
        {route.eva=oldEva;route.owner=oldOwner;route.pilot=oldPilot;route.mode=oldMode;return result(false,baseFault);}
        route.extra.putBoolean("AirReceiverR50",true);retain(level,v);
        EvaGroundReceiverR50.begin(unit);route.mode="RECEIVING";route.fault="";state(level).setDirty();
        return result(true,"地下接应平台已固定机体，调整姿态后沿接应轨道送回整备床。");
    }
    public static boolean tickMotionR48(ServerLevel level,int v,EvaUnit01Entity unit)
    {
        if(!enabled(level))return false;var row=row(level,v);if(!motion(row))return false;
        if(!bound(level,v,unit,row))return true;retain(level,v);maintainDoor(level,v);unit.setNervLogisticsLocked(true);unit.setNoGravity(true);
        if(!authority(owner(level,row),v,unit)){hold(level,row,"操作员或驾驶员许可尚未确认，承载板暂停，请联系指挥部门。");return true;}
        if(row.mode.equals("RECEIVING"))
        {
            if(!EvaGroundReceiverR50.active(unit)){hold(level,row,"接应平台尚未确认机体姿态，暂停作业，等待检查。");return true;}
            String foundation=receivingDeckFaultR50(level,unit);
            if(!foundation.isEmpty()){EvaGroundReceiverR50.hold(unit);hold(level,row,foundation);return true;}
            if(row.lastTick==level.getGameTime())return true;row.lastTick=level.getGameTime();
            int next=Math.min(EvaGroundReceiverR50.TOTAL_TICKS,EvaGroundReceiverR50.age(unit)+1);
            String fault=receiverSweepR50(level,unit,EvaGroundReceiverR50.poseAt(unit,EvaGroundReceiverR50.age(unit)),EvaGroundReceiverR50.poseAt(unit,next));
            if(!fault.isEmpty()){EvaGroundReceiverR50.hold(unit);hold(level,row,fault);return true;}
            EvaGroundReceiverR50.acceptStep(unit,next);row.fault="";
            if(next==EvaGroundReceiverR50.TOTAL_TICKS)
            {
                EvaGroundReceiverR50.finish(unit);
                row.mode="RECOVER_OPENING";row.requested=true;state(level).setDirty();maintainDoor(level,v);
                ProjectSeele.LOGGER.info("R50 underground receiver captured and aligned original EVA {} without replacing its frozen pickup",unit.getUUID());
            }
            return true;
        }
        if(!doorReady(level,v)){hold(level,row,"地下出口尚未全开或门旁有异常，承载板暂停，等待检查。");return true;}
        if(!neighbourReady(level,v,true)){hold(level,row,"相邻出口或承载板尚未停稳，请等待作业结束。");return true;}
        if(row.mode.equals("OPENING")||row.mode.equals("RECOVER_OPENING"))
        {
            boolean returning=row.mode.equals("RECOVER_OPENING");var caller=owner(level,row);
            var result=returning?EvaLogisticsDirector.requestUndergroundRecoveryR48(level,v,row.eva):EvaLogisticsDirector.requestUndergroundDepartureR48(caller,v,row.eva);
            if(!result.accepted()){hold(level,row,result.message());return true;}
            row.from=unit.position();row.age=0;row.duration=Math.max(80,(int)Math.ceil(row.from.distanceTo(returning?bedFeet(v):padFeet(v))/.25));
            row.mode=returning?"RETURNING":"OUTBOUND";row.fault="";unit.publishAirCarrierFrameR39(row.from,row.from);state(level).setDirty();
        }
        if(row.lastTick==level.getGameTime())return true;row.lastTick=level.getGameTime();
        boolean returning=row.mode.equals("RETURNING");Vec3 destination=returning?bedFeet(v):padFeet(v);
        double previous=row.age/(double)row.duration;previous=previous*previous*(3-2*previous);
        if(unit.position().distanceToSqr(row.from.lerp(destination,previous))>.25)
        {hold(level,row,"机体位置与承载板不同步，运输已暂停，请联系整备部门。");return true;}
        int age=Math.min(row.duration,row.age+1);
        double t=age/(double)row.duration;t=t*t*(3-2*t);Vec3 next=row.from.lerp(destination,t);
        String fault=corridor(level,v,unit,unit.position(),next,false);if(!fault.isEmpty()){hold(level,row,fault);return true;}
        // Republish an actual one-tick interval: a paused/reloaded persistent clock
        // must not let the client independently run an old full-length trajectory.
        unit.publishAirCarrierFrameR39(unit.position(),next);unit.moveOnNervCarrier(next.x,next.y,next.z,EvaUnit01Entity.SILO_BAY_YAW);row.age=age;row.fault="";state(level).setDirty();
        if(row.age>=row.duration)
        {
            if(!returning)
            {
                String supportFault=padSupportFault(level,v,unit);if(!supportFault.isEmpty()){hold(level,row,supportFault);return true;}
            }
            var result=returning?EvaLogisticsDirector.completeUndergroundRecoveryR48(level,v,row.eva):EvaLogisticsDirector.completeUndergroundDepartureR48(level,v,row.eva);
            if(!result.accepted()){hold(level,row,result.message());return true;}
            row.mode=returning?"IDLE":"DEPLOYED";row.launchCancelled=false;if(returning){row.requested=false;row.extra.remove("AirReceiverR50");}state(level).setDirty();
        }
        return true;
    }
    private static void hold(ServerLevel level,Row row,String reason)
    {
        if(!reason.equals(row.fault)){row.fault=reason;state(level).setDirty();ProjectSeele.LOGGER.warn("R48 original underground carrier held {}: {}",row.eva,reason);}
    }
    private static void maintainDoor(ServerLevel level,int v)
    {
        var row=row(level,v);var centre=new Vec3(X[v]+.5,-410,DOOR_Z[v]);
        if(!level.hasChunkAt(BlockPos.containing(centre)))return;
        var unit=row.eva==null?null:level.getEntity(row.eva) instanceof EvaUnit01Entity eva?eva:null;
        boolean open=row.requested||motion(row)||row.collisionOpen&&occupied(level,v,null);
        NervHangarDoorEntity.reconcile(level,v,centre,open);
        var doors=level.getEntitiesOfClass(NervHangarDoorEntity.class,new AABB(centre,centre).inflate(1),e->e.getVariant()==v);
        if(doors.size()!=1)return;float progress=doors.get(0).getOpenProgress(1);
        boolean clear=open&&progress>=.999F,closed=!open&&progress<=.001F;
        if(!clear&&!closed||row.collisionOpen==clear)return;
        for(int z:planes(v))for(var p:BlockPos.betweenClosed(X[v]-15,-410,z,X[v]+15,-346,z))
        {
            if(!level.hasChunkAt(p)||level.getBlockEntity(p)!=null)return;var block=level.getBlockState(p);
            if(row.collisionOpen?!block.isAir():!block.is(Blocks.BARRIER))
            {hold(level,row,"地下门控状态异常，暂停开关门，请联系整备部门检查。");return;}
            if(!level.getFluidState(p).isEmpty()){hold(level,row,"地下门旁有液体，暂停开关门，等待排液。");return;}
        }
        if(closed&&occupied(level,v,null))return;
        if(row.collisionOpen==clear)return;
        var wanted=(clear?Blocks.AIR:Blocks.BARRIER).defaultBlockState();
        for(int z:planes(v))for(var p:BlockPos.betweenClosed(X[v]-15,-410,z,X[v]+15,-346,z))if(!level.getBlockState(p).equals(wanted))level.setBlock(p,wanted,2);
        row.collisionOpen=clear;state(level).setDirty();
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null||!enabled(level))return;
        for(int v=0;v<3;v++)
        {
            var row=row(level,v);var fleet=EvaFleetSavedData.get(level.getServer()).entry(v).orElse(null);
            if(row.mode.equals("DEPLOYED")&&fleet!=null&&fleet.canonicalId().equals(row.eva)
                    &&Set.of(EvaFleetSavedData.Phase.DESCENDING,EvaFleetSavedData.Phase.TO_HANGAR,EvaFleetSavedData.Phase.FILLING,EvaFleetSavedData.Phase.PARKED).contains(fleet.phase()))
            {row.mode="IDLE";row.requested=false;state(level).setDirty();}
            maintainDoor(level,v);
        }
    }
    @SubscribeEvent public static void commands(net.minecraftforge.event.RegisterCommandsEvent event)
    {
        event.getDispatcher().register(net.minecraft.commands.Commands.literal("nerv")
                .then(net.minecraft.commands.Commands.literal("underground")
                .then(net.minecraft.commands.Commands.literal("recover")
                .then(net.minecraft.commands.Commands.argument("unit",com.mojang.brigadier.arguments.IntegerArgumentType.integer(0,2)).executes(context->{
                    var caller=context.getSource().getPlayerOrException();var action=requestRecoveryR48(caller,com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(context,"unit"));
                    caller.sendSystemMessage(net.minecraft.network.chat.Component.literal(action.message()));return action.accepted()?1:0;
                })))));
    }
    private UndergroundSortieR48() { }
}

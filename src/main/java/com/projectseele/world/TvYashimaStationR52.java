package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import java.nio.file.Files;
import java.util.*;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.*;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.*;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Preloaded original gun: platform arrival, commander raise, actual prone occupation, same fixed muzzle, safe withdrawal. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class TvYashimaStationR52
{
    public static final String FILE="yashima_cannon_station_r52.json";
    public record Plan(String id,UUID cannon,UUID hatch,UUID source,UUID weapon,Vec3 sourcePosition,Vec3 closed,Vec3 raised,
            int riseTicks,int returnTicks,YashimaCannonGeometryR52.Geometry geometry,FixedCannonCradleR52.Spec cradle,Vec3 prone,float yaw,BlockPos control,
            double radius,double gripRadius,double attackRange,List<Vec3> access,String fingerprint) {}
    private static final Map<ServerLevel,Optional<Plan>> CACHE=new WeakHashMap<>();
    private static final TicketType<ChunkPos> TICKET=TicketType.create("yashima_fixed_cannon_r52",Comparator.comparingLong(ChunkPos::toLong),100);
    private static Vec3 point(JsonObject root,String key){return YashimaCannonGeometryR52.vector(root.getAsJsonArray(key));}
    public static Plan parse(JsonObject root,String dimension)
    {
        if(root.get("schema").getAsInt()!=52||!root.get("dimension").getAsString().equals(dimension)||!root.get("installed").getAsBoolean()||!root.get("geometry_validated").getAsBoolean())throw new IllegalArgumentException("Explicit installed fixed cannon required");
        UUID cannon=UUID.fromString(root.get("cannon_uuid").getAsString()),hatch=UUID.fromString(root.get("hatch_uuid").getAsString()),source=UUID.fromString(root.get("source_rack_uuid").getAsString()),weapon=UUID.fromString(root.get("source_weapon_uuid").getAsString());
        Vec3 closed=point(root,"closed_position"),raised=point(root,"raised_position"),prone=point(root,"prone_position");
        var cradle=FixedCannonCradleR52.Spec.parse(root.getAsJsonObject("cradle"));
        if(Math.abs(cradle.closedRootY()-closed.y)>.00001||Math.abs(cradle.raisedRootY()-raised.y)>.00001||closed.subtract(raised).horizontalDistance()>.00001)
            throw new IllegalArgumentException("Cradle and cannon must use one actual vertical rise");
        int rise=root.get("rise_ticks").getAsInt(),back=root.get("return_ticks").getAsInt();double radius=root.get("interaction_radius").getAsDouble(),grip=root.get("grip_radius").getAsDouble(),range=root.get("attack_range").getAsDouble();float yaw=root.get("prone_yaw").getAsFloat();
        var access=new ArrayList<Vec3>();for(var raw:root.getAsJsonArray("eva_access_route"))access.add(YashimaCannonGeometryR52.vector(raw.getAsJsonArray()));
        if(new HashSet<>(List.of(cannon,hatch,source)).size()!=3||raised.y<=closed.y||closed.distanceTo(raised)>128||rise<20||back<20||rise>1200||back>1200
                ||closed.distanceTo(raised)/rise>.5||closed.distanceTo(raised)/back>.5||!Double.isFinite(radius)||radius<.5||radius>6||!Double.isFinite(grip)||grip<.1||grip>3
                ||!Float.isFinite(yaw)||!Double.isFinite(range)||range<64||range>4096||access.size()<2||access.size()>512||access.get(access.size()-1).distanceTo(prone)>radius)
            throw new IllegalArgumentException("Original fixed cannon identity, bounded lift or physical approach rejected");
        for(int i=1;i<access.size();i++)if(access.get(i).distanceTo(access.get(i-1))>8||Math.abs(access.get(i).y-access.get(i-1).y)>1.6)throw new IllegalArgumentException("Fixed cannon access is not a continuous real walk route");
        try
        {
            var geometry=YashimaCannonGeometryR52.parse(root);YashimaCannonMeshR52.requireOriginal(root,geometry);
            if(Math.abs(geometry.scale()-8)>.00001)throw new IllegalArgumentException("This installed original fixed cannon must retain its measured 64m scale");
            String hash=HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(root.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8)));
            return new Plan(root.get("id").getAsString(),cannon,hatch,source,weapon,point(root,"source_position"),closed,raised,rise,back,geometry,cradle,prone,yaw,BlockPos.containing(point(root,"interaction_control")),radius,grip,range,List.copyOf(access),hash);
        }
        catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}
    }
    public static Optional<Plan> plan(ServerLevel level)
    {
        return CACHE.computeIfAbsent(level,l->{var file=l.getServer().getWorldPath(LevelResource.ROOT).resolve(FILE);if(!Files.isRegularFile(file))return Optional.empty();
            try
            {
                var root=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                // The world-root file is shared by every dimension's right-click events.
                if(!root.get("dimension").getAsString().equals(l.dimension().location().toString()))return Optional.empty();
                return Optional.of(parse(root,l.dimension().location().toString()));
            }
            catch(Exception error){com.projectseele.ProjectSeele.LOGGER.error("Installed fixed Yashima cannon rejected",error);return Optional.empty();}});
    }
    /** Called only by the explicit, hash-checked Root installation bundle. */
    public static void installRootControllerR52(ServerLevel level,Plan p)
    {
        for(Vec3 at:List.of(p.closed(),p.raised(),p.sourcePosition(),Vec3.atCenterOf(p.control())))retain(level,at);
        if(!(level.getEntity(p.source()) instanceof NervArmamentStationEntity rack)||rack.position().distanceTo(p.sourcePosition())>.01)
            throw new IllegalStateException("Fixed cannon original supply rack not loaded at "+p.sourcePosition()+" UUID="+p.source());
        if(!(level.getEntity(p.hatch()) instanceof NervSiloDoorEntity hatch))
            throw new IllegalStateException("Fixed cannon real hatch is not installed/loaded: "+p.hatch());
        var existing=level.getEntity(p.cannon());
        if(existing!=null)
        {
            if(!(existing instanceof YashimaCannonEntityR52 gun)||!gun.getPersistentData().getString("StationLayoutR52").equals(p.fingerprint())
                    ||gun.geometryR52()==null||!YashimaCannonGeometryR52.encode(gun.geometryR52()).equals(YashimaCannonGeometryR52.encode(p.geometry()))
                    ||!p.cradle().equals(gun.cradleR52()))
                throw new IllegalStateException("Existing fixed cannon identity/source differs; not replaced: "+p.cannon());
            CACHE.put(level,Optional.of(p));return;
        }
        if(hatch.actualOpenProgressR52()>.001||!level.getBlockState(p.control()).is(net.minecraft.world.level.block.Blocks.STONE_BUTTON))
            throw new IllegalStateException("Fixed cannon commissioning requires the actual closed hatch and button at "+p.control());
        var pieces=FixedCannonCradleR52.pieces(p.geometry(),p.cradle(),p.closed(),new org.joml.Quaternionf());int feet=0;
        for(var piece:pieces)if(piece.part().name().equals("floor_plate"))
        {
            feet++;var bounds=piece.mesh().envelope(piece.frame(),piece.frame());
            for(int x=net.minecraft.util.Mth.floor(bounds.minX+.0001);x<=net.minecraft.util.Mth.floor(bounds.maxX-.0001);x++)
                for(int z=net.minecraft.util.Mth.floor(bounds.minZ+.0001);z<=net.minecraft.util.Mth.floor(bounds.maxZ-.0001);z++)
                {
                    var floor=new BlockPos(x,net.minecraft.util.Mth.floor(p.cradle().floorTop()-.0001),z);
                    if(!level.hasChunkAt(floor)||!level.getBlockState(floor).isCollisionShapeFullBlock(level,floor))
                        throw new IllegalStateException("Fixed cannon finite floor plate has no full actual support at "+floor);
                }
        }
        if(feet!=2)throw new IllegalStateException("Fixed cannon original cradle must have two actual floor plates");
        var gun=com.projectseele.registry.ModEntities.YASHIMA_CANNON_R52.get().create(level);
        if(gun==null)throw new IllegalStateException("Fixed cannon controller factory unavailable");
        gun.setUUID(p.cannon());gun.setPos(p.closed());gun.configureR52(p.geometry());gun.configureCradleR52(p.cradle());
        gun.loadedR52(false);gun.readyR52(false);
        if(!YashimaCannonMeshR52.clear(level,gun,p.closed(),new org.joml.Quaternionf()))
            throw new IllegalStateException("Fixed cannon actual closed gun/cradle clearance rejected: "+gun.getPersistentData().getString("FixedCannonCollisionHoldR52"));
        gun.getPersistentData().putString("StationLayoutR52",p.fingerprint());gun.getPersistentData().putString("LiftPhaseR52","idle");
        if(!level.addFreshEntity(gun))throw new IllegalStateException("Fixed cannon unique controller could not be installed");
        CACHE.put(level,Optional.of(p));
    }
    private static void retain(ServerLevel level,Vec3 point){var c=new ChunkPos(BlockPos.containing(point));level.getChunkSource().addRegionTicket(TICKET,c,3,c);}
    public static String startBlocker(ServerLevel level)
    {
        var p=plan(level).orElse(null);var site=TvEncounterSitesR45.site(level,"ramiel").orElse(null);
        if(p==null||site==null)return "远山原固定炮、原弹药来源和实际趴炮平台尚未安装。";
        var landing=site.landings().get(1);if(landing==null||p.access().get(0).distanceTo(landing.point())>2)return "原射手独立落点至实际炮位的步行接口尚未接通。";
        if(p.attackRange()<p.geometry().point(p.raised(),new org.joml.Quaternionf(),p.geometry().muzzle()).distanceTo(site.angel())+64
                ||site.attackRange()<p.attackRange())return "本场实距和原炮／目标反击射程尚未对齐。";
        return "";
    }
    public static YashimaCannonEntityR52 gun(ServerLevel level)
    {var p=plan(level).orElse(null);return p!=null&&level.getEntity(p.cannon()) instanceof YashimaCannonEntityR52 gun?gun:null;}
    public static EvaUnit01Entity boundEva(ServerLevel level,YashimaCannonEntityR52 gun)
    {var tag=gun.getPersistentData();return tag.hasUUID("OperatingEvaR52")&&level.getEntity(tag.getUUID("OperatingEvaR52")) instanceof EvaUnit01Entity eva?eva:null;}
    private static boolean at(EvaUnit01Entity eva,Plan p)
    {return eva.position().subtract(p.prone()).horizontalDistance()<=p.radius()&&Math.abs(eva.getY()-p.prone().y)<=1.35
            &&!eva.isNervLogisticsLocked()&&!eva.isLaunchSequenceActive()&&!EvaAirTransportR31.active(eva)&&AirCradleClearanceR31.touchdownContact(eva)!=null;}
    private static boolean authority(ServerPlayer commander,TvCampaignSavedData data)
    {return data.owner!=null&&data.owner.equals(commander.getUUID())&&data.active.equals("ramiel")&&!Set.of("cancel","failure","combat_victory","episode_archived").contains(data.phase)&&!data.targetDeathConfirmedR45&&NervStaffDialogue.authorized(commander);}
    public static Vec3 operatorPositionR52(ServerLevel level){return plan(level).map(Plan::prone).orElse(null);}
    public static boolean atPlatformR52(EvaUnit01Entity eva)
    {return eva.level() instanceof ServerLevel level&&plan(level).filter(p->at(eva,p)).isPresent();}
    public static String raise(ServerPlayer commander)
    {
        var level=commander.serverLevel();var data=TvCampaignSavedData.get(level);var p=plan(level).orElse(null);var gun=gun(level);var eva=TvSortiesR32.assignedUnit(level,data,1);
        if(!authority(commander,data)||p==null||gun==null)return "原固定炮或本场指挥授权未接通。";
        if(eva==null||!TvSortiesR32.readyAssigned(level,data.sorties.get(1))||!at(eva,p))return "请先让本场原初号机到实际炮位平台停稳，再下令升炮。";
        if(!gun.loadedR52()||!TvMissionEquipmentR45.cannonAuthorized(eva))return "原底仓任务炮尚未完成同一货物的预装登记，未补造炮。";
        var phase=gun.getPersistentData().getString("LiftPhaseR52");
        if(phase.equals("ready"))return "原炮已升起；初号机右键接入实际炮位，完成趴姿后使用。";
        if(Set.of("opening","raising").contains(phase))return "原炮正在实际开盖升起，请等待完整升降。";
        if(Set.of("lowering","closing").contains(phase))return "原炮仍在撤离归仓，请等待完整归仓。";
        gun.getPersistentData().putString("LiftPhaseR52","opening");return "升炮指令已接受；原盖开启后，炮体沿实际底仓升起。";
    }
    public static String interact(ServerPlayer player,YashimaCannonEntityR52 gun)
    {
        var level=player.serverLevel();var data=TvCampaignSavedData.get(level);var p=plan(level).orElse(null);var eva=EvaPilotResolver.controlTarget(player);
        if(p==null||!p.cannon().equals(gun.getUUID())||eva==null||eva!=TvSortiesR32.assignedUnit(level,data,1)||eva.getPilotEntity()!=player||!at(eva,p))return "请驾驶本场原初号机到实际炮位平台，右键原炮接入。";
        if(eva.fixedCannonOperatingR52()){release(eva,gun);return "已退出固定炮位，初号机解除操纵占位，可撤离平台。";}
        if(!gun.readyR52()||!TvMissionEquipmentR45.cannonAuthorized(eva))return "原炮尚未完全升起，请由指挥员下令并等候真实升降完成。";
        Vec3 eye=player.getEyePosition();var hit=YashimaCannonMeshR52.rayHitR52(gun,eye,eye.add(player.getLookAngle().scale(128)));
        if(hit==null||level.clip(new net.minecraft.world.level.ClipContext(eye,hit,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,player)).getType()!=net.minecraft.world.phys.HitResult.Type.MISS)
            return "请从驾驶舱看向已升起的原炮实际炮体并右键接入。";
        bind(eva,gun);return "固定炮位已接入；完成完整趴姿和实际握把接触后，可蓄力瞄准与开火。";
    }
    private static void bind(EvaUnit01Entity eva,YashimaCannonEntityR52 gun)
    {gun.getPersistentData().putUUID("OperatingEvaR52",eva.getUUID());eva.bindFixedCannonR52(gun.getId(),true);}
    private static void release(EvaUnit01Entity eva,YashimaCannonEntityR52 gun)
    {gun.getPersistentData().remove("OperatingEvaR52");eva.bindFixedCannonR52(gun.getId(),false);eva.suspendFixedCannonR52();}
    /** Both human release and NPC fire gates use complete prone posture, original grips and the real mounted bore. */
    public static String fireBlocker(EvaUnit01Entity eva)
    {
        if(!(eva.level() instanceof ServerLevel level))return "固定炮位由服务器确认。";
        var p=plan(level).orElse(null);var gun=gun(level);
        if(p==null||gun==null||!gun.loadedR52()||!gun.readyR52()||!TvMissionEquipmentR45.fixedCannonAuthorizedR52(eva,gun)||boundEva(level,gun)!=eva||!eva.fixedCannonOperatingR52()||!at(eva,p))return "等待原固定炮升起并完成实际炮位接入。";
        if(!eva.isPilotProne()||eva.rifleProneBlend(0)<.99F||eva.hasLiveActionForRender(0)||EvaWeaponHandlingR45.active(eva))return "初号机完整趴姿尚未稳定。";
        var left=gun.gripR52(true);var right=gun.gripR52(false);
        if(left==null||right==null||EvaGameplayMotionR32.hand(eva,"l",0).distanceTo(left)>p.gripRadius()
                ||EvaGameplayMotionR32.hand(eva,"r",0).distanceTo(right)>p.gripRadius())return "初号机实际双手尚未接触原炮握把。";
        return "";
    }
    /** Fixed barrel articulation and release admission share the actual world gun, never a standing hand muzzle. */
    public static boolean aim(EvaUnit01Entity eva,Vec3 target)
    {return eva.level() instanceof ServerLevel level&&gun(level)!=null&&gun(level).aimAtR52(target);}
    /** Resolve the optical point first so the displaced fixed muzzle does not fire a parallel, offset ray. */
    public static Vec3 aimTargetR52(EvaUnit01Entity eva,LivingEntity pilot,Vec3 direction,double range)
    {
        if(!(eva.level() instanceof ServerLevel level)||pilot!=eva.getPilotEntity())return null;
        var data=TvCampaignSavedData.get(level);var boss=data.angel!=null&&level.getEntity(data.angel) instanceof RamielEntity ramiel?ramiel:null;
        if(pilot instanceof TrainingPilotEntity&&boss!=null&&com.projectseele.event.TvEncounterDirectorR45.owned(boss,data))return boss.getBoundingBox().getCenter();
        Vec3 eye=EvaBodyPose.opticalEye(eva,1),end=eye.add(direction.scale(range));
        var block=level.clip(new net.minecraft.world.level.ClipContext(eye,end,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,eva));
        if(block.getType()!=net.minecraft.world.phys.HitResult.Type.MISS)end=block.getLocation();
        if(boss!=null){var hit=boss.getBoundingBox().clip(eye,end);if(hit.isPresent())return hit.get();}return end;
    }
    public static TvYashimaArrivalR50.Next npcArrival(ServerLevel level,TvCampaignSavedData data,EvaUnit01Entity eva,ServerPlayer owner)
    {
        var p=plan(level).orElse(null);var gun=gun(level);if(p==null||gun==null)return new TvYashimaArrivalR50.Next(null,true);
        var tag=eva.getPersistentData();if(tag.getLong("FixedCannonRouteGenerationR52")!=data.generationR43)
        {tag.putLong("FixedCannonRouteGenerationR52",data.generationR43);tag.putInt("FixedCannonRouteCursorR52",0);}
        if(!at(eva,p))
        {
            int cursor=Math.max(0,Math.min(tag.getInt("FixedCannonRouteCursorR52"),p.access().size()));
            while(cursor<p.access().size()&&eva.position().subtract(p.access().get(cursor)).horizontalDistance()<=.8&&Math.abs(eva.getY()-p.access().get(cursor).y)<=1.35)cursor++;
            tag.putInt("FixedCannonRouteCursorR52",cursor);return new TvYashimaArrivalR50.Next(cursor<p.access().size()?p.access().get(cursor):p.prone(),false);
        }
        if(!gun.readyR52()){data.notice=raise(owner);return new TvYashimaArrivalR50.Next(null,true);}
        if(!eva.fixedCannonOperatingR52())bind(eva,gun);
        return new TvYashimaArrivalR50.Next(null,false);
    }
    private static void advance(ServerLevel level,Plan p,YashimaCannonEntityR52 gun,NervSiloDoorEntity hatch,boolean returning)
    {
        var tag=gun.getPersistentData();String phase=tag.getString("LiftPhaseR52");if(phase.isEmpty()){phase="idle";tag.putString("LiftPhaseR52",phase);}
        if(returning&&!Set.of("idle","lowering","closing").contains(phase))
        {var eva=boundEva(level,gun);if(eva!=null)release(eva,gun);gun.readyR52(false);tag.putString("LiftPhaseR52",phase="lowering");}
        // The crane extracts the wreck first. Rotating/stowing the supporting
        // cannon concurrently changes that contact and repeatedly stalls both.
        if(returning&&tag.hasUUID("AssignedEvaR52"))
            for(var rescue:NervAirTransportRuntimeR52.state(level).jobs())
                if(rescue.active()&&!rescue.payloadTransferred()&&rescue.leg()==0
                        &&rescue.original().eva().equals(tag.getUUID("AssignedEvaR52")))return;
        switch(phase)
        {
            case "opening"->{if(YashimaCannonHatchR54.advance(level,p,gun,hatch,true))tag.putString("LiftPhaseR52","raising");}
            case "raising"->{if(!YashimaCannonHatchR54.advance(level,p,gun,hatch,true))return;if(gun.liftStepR52(p.raised(),p.closed().distanceTo(p.raised())/p.riseTicks())){tag.putString("LiftPhaseR52","ready");gun.readyR52(true);}}
            case "lowering"->{if(!YashimaCannonHatchR54.advance(level,p,gun,hatch,true))return;if(!gun.resetAimR52())return;if(gun.liftStepR52(p.closed(),p.closed().distanceTo(p.raised())/p.returnTicks()))tag.putString("LiftPhaseR52","closing");}
            case "closing"->{if(YashimaCannonHatchR54.advance(level,p,gun,hatch,false))tag.putString("LiftPhaseR52","idle");}
            default->{}
        }
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        var p=plan(level).orElse(null);if(p==null)return;
        for(Vec3 at:List.of(p.closed(),p.raised(),p.sourcePosition(),Vec3.atCenterOf(p.control())))retain(level,at);
        var gun=gun(level);if(gun==null||!(level.getEntity(p.hatch()) instanceof NervSiloDoorEntity hatch)||!(level.getEntity(p.source()) instanceof NervArmamentStationEntity source))return;
        if(source.position().distanceTo(p.sourcePosition())>2)return;
        var tag=gun.getPersistentData();String recorded=tag.getString("StationLayoutR52");
        if(!recorded.isEmpty()&&!recorded.equals(p.fingerprint())){gun.readyR52(false);return;}
        if(recorded.isEmpty()){if(gun.position().distanceTo(p.closed())>.01)return;tag.putString("StationLayoutR52",p.fingerprint());gun.configureR52(p.geometry());gun.configureCradleR52(p.cradle());}
        var data=TvCampaignSavedData.get(level);var eva=TvSortiesR32.assignedUnit(level,data,1);
        boolean active=data.active.equals("ramiel")&&!data.targetDeathConfirmedR45&&!Set.of("cancel","failure","combat_victory","episode_archived").contains(data.phase);
        if(active&&eva!=null)
        {
            var sortie=data.sorties.get(1);if(sortie.pilotR45==null&&sortie.npc)
            {TrainingPilotDirector.retainOriginalPilotR47(level,1);var pilot=TrainingPilotDirector.existingPilotR45(level,1);if(pilot!=null){sortie.pilotR45=pilot.getUUID();data.setDirty();}}
            if(sortie.pilotR45!=null&&TvMissionEquipmentR45.reserveFixedCannonR52(level,eva,sortie.pilotR45,gun,source,p.weapon()))
            {gun.loadedR52(true);eva.fixedCannonRangeR52((float)p.attackRange());eva.bindFixedCannonR52(gun.getId(),eva.fixedCannonOperatingR52());tag.putUUID("AssignedEvaR52",eva.getUUID());}
        }
        var operating=boundEva(level,gun);
        if(operating!=null)
        {
            if(!active||operating.getPilotEntity()==null||!at(operating,p)||!TvMissionEquipmentR45.operational(operating))release(operating,gun);
            else
            {
                operating.bindFixedCannonR52(gun.getId(),true);
                if(!operating.isPilotProne())
                {
                    operating.setYRot(net.minecraft.util.Mth.approachDegrees(operating.getYRot(),p.yaw(),4));operating.yBodyRot=operating.yHeadRot=operating.getYRot();
                    if(Math.abs(net.minecraft.util.Mth.wrapDegrees(p.yaw()-operating.getYRot()))>1)return;
                }
                operating.fixedCannonProneR52(operating.getPilotEntity(),true);
                if(operating.isPilotProne()&&operating.rifleProneBlend(0)>.99)aim(operating,operating.fixedCannonAimTargetR52(operating.getPilotEntity()));
            }
        }
        advance(level,p,gun,hatch,!active&&gun.loadedR52());
        if(!active&&gun.loadedR52()&&gun.position().distanceTo(p.closed())<=.01&&hatch.actualOpenProgressR52()<=.005&&tag.hasUUID("AssignedEvaR52")
                &&level.getEntity(tag.getUUID("AssignedEvaR52")) instanceof EvaUnit01Entity original
                &&TvMissionEquipmentR45.returnFixedCannonR52(level,original,gun,source))
        {original.bindFixedCannonR52(-1,false);tag.remove("AssignedEvaR52");}
    }
    @SubscribeEvent public static void interact(PlayerInteractEvent.RightClickBlock event)
    {
        if(event.getHand()!=InteractionHand.MAIN_HAND||!(event.getEntity() instanceof ServerPlayer player))return;
        var p=plan(player.serverLevel()).orElse(null);if(p==null||!p.control().equals(event.getPos())||player.position().distanceTo(Vec3.atCenterOf(p.control()))>6)return;
        event.setCanceled(true);event.setCancellationResult(InteractionResult.SUCCESS);player.sendSystemMessage(Component.literal(raise(player)));
    }
    @SubscribeEvent public static void commands(RegisterCommandsEvent event)
    {
        event.getDispatcher().register(Commands.literal("seele").then(Commands.literal("tv")
            .then(Commands.literal("raise_cannon").executes(c->{var player=c.getSource().getPlayerOrException();player.sendSystemMessage(Component.literal(raise(player)));return 1;}))
            .then(Commands.literal("leave_cannon").executes(c->{var player=c.getSource().getPlayerOrException();var eva=EvaPilotResolver.controlTarget(player);var gun=gun(player.serverLevel());if(eva==null||gun==null||boundEva(player.serverLevel(),gun)!=eva)return 0;release(eva,gun);player.sendSystemMessage(Component.literal("已解除固定炮位占用，可以撤离。"));return 1;}))));
    }
    @SubscribeEvent public static void unloaded(net.minecraftforge.event.level.LevelEvent.Unload event){if(event.getLevel() instanceof ServerLevel level)CACHE.remove(level);}
    private TvYashimaStationR52(){}
}

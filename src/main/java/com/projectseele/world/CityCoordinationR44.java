package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import net.minecraft.core.*;
import net.minecraft.server.level.*;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.*;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.*;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraft.world.InteractionResult;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Original grid preparation: real switches and personnel, no implicit EVA launch licence. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class CityCoordinationR44
{
    private record Site(BlockPos reserve,BlockPos emergency,BlockPos test,BlockPos approach,BlockPos visit,
                        BlockPos fieldButton,BlockPos fieldIndicator,boolean passengerAccessCertified,List<String> requiredArchivePages) {}
    private static final Map<ServerLevel,Optional<Site>> SITES=new WeakHashMap<>();
    private static final TicketType<ChunkPos> TICKET=TicketType.create("city_coordination_r44",Comparator.comparingLong(ChunkPos::toLong),100);
    private static BlockPos point(JsonObject j,String key)
    {var a=j.getAsJsonArray(key);return new BlockPos(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt());}
    private static Site site(ServerLevel level)
    {
        return SITES.computeIfAbsent(level,l->{try
        {
            var path=l.getServer().getWorldPath(LevelResource.ROOT).resolve("city_coordination_r44.json");if(!Files.isRegularFile(path))return Optional.empty();
            var j=JsonParser.parseString(Files.readString(path)).getAsJsonObject();
            if(!j.get("dimension").getAsString().equals(l.dimension().location().toString()))return Optional.empty();
            List<String> required=new ArrayList<>();
            if(j.has("required_archive_pages"))for(var value:j.getAsJsonArray("required_archive_pages"))
            {String id=value.getAsString();if(!DeadSeaReadingR45.knownDocument(id)||required.contains(id))throw new IllegalArgumentException("Unknown required archive page");required.add(id);}
            return Optional.of(new Site(point(j,"reserve"),point(j,"emergency"),point(j,"test"),point(j,"operator_approach"),point(j,"visit"),
                    j.has("field_button")?point(j,"field_button"):null,j.has("field_indicator")?point(j,"field_indicator"):null,
                    j.has("passenger_access_certified")&&j.get("passenger_access_certified").getAsBoolean(),List.copyOf(required)));
        }
        catch(Exception error){ProjectSeele.LOGGER.error("City coordination equipment rejected",error);return Optional.empty();}}).orElse(null);
    }
    public static UUID instance(ServerPlayer player)
    {var level=player.server.getLevel(FacilitySchemaV2.DIMENSION);return level==null?null:CityCoordinationSavedDataR44.get(level).instance;}
    public static String status(ServerPlayer player)
    {
        var level=player.server.getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return "本世界没有总部。";var data=CityCoordinationSavedDataR44.get(level);
        String phase=switch(data.stage){case 1->"核对证据";case 2->"城市撤离调度";case 3->"现场复测";case 4->"供电分配";case 5->"知情编成";case 6->"准备归档";case 7->"已归档";default->"尚未接受";};
        return "城市协同 · "+phase+"\n已阅 "+Integer.bitCount(data.evidence)+" / 3 · 现场复测 "+(data.tested?"通过":"未完成")+"\n"
                +(data.active?"当前档案："+data.instance:"已归档 "+data.archiveCount()+" 次")+"\n"+data.notice;
    }
    public static String request(ServerPlayer player,NervStaffEntity contact,String action,UUID expected)
    {
        var level=player.server.getLevel(FacilitySchemaV2.DIMENSION);if(level==null||player.level()!=level)return "请先进入 NERV 所在世界。";
        if(!NervStaffDialogue.authorized(player)||!StaffAuthorityR25.commandContact(contact))return "这份调度请联络美里、律子或冬月。";
        var data=CityCoordinationSavedDataR44.get(level);Site site=site(level);
        if(action.equals("status"))return status(player);
        if(action.equals("start"))
        {
            if(data.active||data.restoring)return "上一份调度还没有结束。先核对当前状态。";
            if(site==null)return "电网复测台尚未接入，请先联系通信管制室。";
            var battle=TvCampaignSavedData.get(level);var first=FirstBattleSavedData.get(level);
            if(!battle.active.isEmpty()||first.active!=null||first.missionOwner!=null)return "作战进行中。等机体回收后再安排复测。";
            data.begin(player.getUUID());data.requiredArchivePagesR45.addAll(site.requiredArchivePages);
            if(!site.requiredArchivePages.isEmpty())data.requiredArchiveRevisionR45=DeadSeaReadingR45.currentRevision();
            data.setDirty();return "美里：司令，先把这三份记录放在一起看。射击条件还没有结论。\n"+status(player);
        }
        if(!data.active||expected==null||!expected.equals(data.instance))return "这条指令对应的档案已经结束。请重新打开当前档案。";
        if(action.startsWith("read/"))
        {
            String source=action.substring(5);int bit=switch(source){case "page"->1;case "annotation"->2;case "field"->4;default->0;};if(bit==0)return "找不到这条记录。";
            String delivered=switch(source)
            {
                case "page"->"档案 P-05 · 原页\n来源：旧保管库，保管人：冬月。记录提及近似规则多面体目标与高能定向反击；射击条件所在页缺失。\n外形与反击条件仍待确认。出击许可尚未下达。";
                case "annotation"->"译注 · SEELE 抄录与 MAGI 工作记录\nSEELE 注释主张直接出击。律子标注：注释没有附测量数据，不能用它估算安全距离。两份记录保留各自来源。";
                default->"现场记录 · 馈线烧蚀与测试节点\n远山：备用馈线的记录和注释对不上。我会先隔离，再复测。\n律子：这道痕迹只能证明发生过放电。射程还不清楚，不要把它当作安全线。";
            };
            data.recordReading(expected,player.getUUID(),"r44/"+source,DeadSeaReadingR45.hashText(delivered),"command_dossier",level.getGameTime());
            return delivered;
        }
        if(action.startsWith("consent/")||action.startsWith("withdraw/"))return participantRequest(player,level,data,action,expected);
        if(!player.getUUID().equals(data.owner)&&!player.hasPermissions(2))return "调度方案由这次任务的司令确认。你可以继续查阅证据。";
        if(action.equals("cancel"))
        {data.active=false;data.restoring=true;data.isolating=data.fieldSampling=false;data.chargeTicks=0;data.notice="调度已撤销。机体保持待命，电网正在复原。已阅记录保留。";data.setDirty();return data.notice;}
        if(action.equals("share")||action.equals("private"))
        {
            if(data.evidence!=7)return "先读完三项证据，再决定共享范围。";
            data.changeKnowledge(action.equals("share")?7:0);if(data.stage==1)data.stage=2;
            return data.knowledge==7?"律子：记录已交给驾驶员。我们先核对条件，再决定出击。":"律子：现场记录仍会保留。未确认的条件不能作为安全保证。";
        }
        if(action.equals("evacuate/services")||action.equals("evacuate/storage"))
        {
            if(data.stage!=2)return "先完成证据核对。";
            var deputy=find(level,"fuyutsuki");if(deputy==null)return "冬月的频道尚未接通，请稍候。";
            var origin=IntegratedNervMapBuilder.tokyo3Origin(level);var district=Tokyo3RetractionSavedData.get(level).get(origin).orElse(null);
            boolean settled=district!=null&&district.depth()==ThirdTokyoSurfaceBuilder.maximumRetractionDepth(origin)&&district.targetDepth()==district.depth()&&district.cursor()==0&&district.voxelCursor()==0;
            if(!settled&&NervStaffDialogue.beginNativeAction(player,deputy,"city_lower",-1)==0)return "冬月还不能操作城市控制台。请查看现场状态。";
            data.priority=action.endsWith("services")?"services":"storage";data.cityRequested=true;data.setDirty();
            return "冬月：先收纳城市。应急供电按你的方案保留。";
        }
        if(action.equals("test/delegate")||action.equals("test/onsite"))
        {
            if(data.stage!=3||data.isolating)return "复测还没到这个步骤，或正在进行。";
            if(site==null)return "找不到复测设备。";
            if(action.endsWith("onsite")&&!site.passengerAccessCertified)return "现场复测台暂未开放。可以先委派远山在通信管制室复测。";
            if(action.endsWith("onsite")&&(site.fieldButton==null||site.fieldIndicator==null))return "地区技术中心的复测设备尚未接入。";
            if(action.endsWith("onsite")&&player.distanceToSqr(Vec3.atCenterOf(site.visit))>100)return "请先到地区技术中心的复测台。到站后按线路牌前往南侧站厅。";
            if(!beginEngineer(player,level,site,data,"coord_test"))return "远山尚未抵达设备。请稍候，或检查操作通道。";
            data.method=action.endsWith("onsite")?"onsite":"delegate";data.fieldSampling=data.fieldSamplePassed=false;
            data.fieldStartedAt=0;data.fieldSamples=0;data.setDirty();
            return data.method.equals("onsite")?"远山：我在管制室隔离馈线。等隔离灯亮了，按你面前的复测键。":"远山：收到。先隔离备用馈线，等读数稳定后复电。";
        }
        if(action.equals("supply/services")||action.equals("supply/reserve"))
        {
            if(data.stage!=4||!data.tested)return "律子：复测还没通过，先不要充能。";
            if(site==null||!beginEngineer(player,level,site,data,"coord_charge"))return "电网联络员尚未到达设备。";
            data.supply=action.endsWith("services")?"services":"reserve";data.chargeTicks=0;data.setDirty();
            return data.supply.equals("services")?"远山：应急设施保电。蓄能需要多等一轮。":"远山：备用馈线切出充能。任务结束后，我会再做复电检查。";
        }
        if(action.startsWith("assign/"))
        {
            if(data.stage!=5&&data.stage!=6)return "先完成城市与供电准备。";
            String[] parts=action.split("/");if(parts.length!=3&&parts.length!=4)return "请选择机体和驾驶员。";
            int unit;try{unit=Integer.parseInt(parts[1]);}catch(NumberFormatException error){return "机体编号无效。";}
            if(unit<0||unit>4||!Set.of("human","npc").contains(parts[2])||unit>2&&parts[2].equals("npc"))return "这台机体没有对应的 NERV 驾驶员。";
            UUID person=player.getUUID();
            if(parts.length==4)
            {if(!parts[2].equals("human"))return "NPC 驾驶员不能指定其他玩家身份。";try{person=UUID.fromString(parts[3]);}catch(IllegalArgumentException error){return "请指定真实玩家 UUID。";}}
            var actual=actualBinding(level,unit,parts[2],person);
            if(actual==null)return "原机体或实际驾驶员尚未接通，请等候，不能用替代实例确认。";
            if(!data.bind(expected,actual))return "这名驾驶员已有另一台编成，或当前档案已变更。";
            return TvSortiesR32.name(unit)+"已加入编成，等待驾驶员确认。";
        }
        if(action.equals("finish"))
        {
            if(data.stage!=6||!data.tested||data.supply.isEmpty()||!data.allConfirmed())return "准备或本次驾驶员确认还没有完成，不能归档。";
            for(int unit:data.formation.keySet())
            {var old=data.binding(unit);var actual=actualBinding(level,unit,old.kind(),old.pilot());if(!old.equals(actual))return "实际驾驶员或原机体已变更，请重新编成与确认。";}
            data.archive();return "美里：准备情况已记下。未知的射击条件还要继续确认。\n"+data.notice;
        }
        return "请选择档案中的有效操作。";
    }
    private static CityCoordinationSavedDataR44.Binding actualBinding(ServerLevel level,int unit,String kind,UUID human)
    {
        if(unit<0||unit>4||!Set.of("human","npc").contains(kind)||kind.equals("npc")&&unit>2)return null;
        if(unit<3)EvaLogisticsDirector.loadControlTarget(level,unit);
        var eva=TvSortiesR32.unit(level,unit);if(eva==null||!eva.isAlive())return null;
        if(kind.equals("human"))
        {
            var player=level.getServer().getPlayerList().getPlayer(human);
            if(player==null||player.level()!=level||!player.isAlive()||!NervStaffDialogue.authorized(player))return null;
            var controlling=EvaPilotResolver.controlTarget(player);
            if(controlling!=null&&controlling!=eva||eva.getPilotEntity()!=null&&eva.getPilotEntity()!=player)return null;
            return new CityCoordinationSavedDataR44.Binding(unit,kind,CityCoordinationSavedDataR44.roleFor(unit),player.getUUID(),eva.getUUID());
        }
        var pilots=TrainingPilotDirector.pilots(level).stream().filter(p->p.isAlive()&&p.getAssignedVariant()==unit).toList();
        if(pilots.size()!=1)return null;var pilot=pilots.get(0);var occupied=PilotRadioR28.occupiedUnit(pilot);
        if(pilot.getVehicle()!=null&&!(pilot.getVehicle()==eva
                ||pilot.getVehicle() instanceof com.projectseele.entity.EntryPlugCarrierEntity plug
                &&plug.getAssignedVariant()==unit&&plug==EntryPlugDirector.canonical(level,unit)))return null;
        if(occupied!=null&&occupied!=eva||eva.getPilotEntity()!=null&&eva.getPilotEntity()!=pilot)return null;
        return new CityCoordinationSavedDataR44.Binding(unit,kind,CityCoordinationSavedDataR44.roleFor(unit),pilot.getUUID(),eva.getUUID());
    }
    public static String participantLine(int unit,boolean accepted)
    {
        if(accepted)return switch(unit){case 0->"丽：掩护位置记下了。我会待命。";case 1->"真嗣：爸爸，我知道了。开火之前……再告诉我一次。";default->"明日香：支援位置我记住了。该接应的时候叫我。";};
        return switch(unit){case 0->"丽：请先告诉我条件和掩护位置。";case 1->"真嗣：爸爸……能先把计划告诉我吗？";default->"明日香：先把计划说清楚。我的位置呢？";};
    }
    private static String participantRequest(ServerPlayer player,ServerLevel level,CityCoordinationSavedDataR44 data,String action,UUID expected)
    {
        String[] parts=action.split("/");int unit;long formationRevision,evidenceRevision;
        try
        {
            if(parts.length!=4)return "编成确认已更新，请重新打开当前档案确认。";
            unit=Integer.parseInt(parts[1]);formationRevision=Long.parseLong(parts[2]);evidenceRevision=Long.parseLong(parts[3]);
        }
        catch(NumberFormatException error){return "请选择当前档案中的有效机体确认。";}
        if(formationRevision!=data.formationRevisionR45||evidenceRevision!=data.evidenceRevisionR45)return "这条确认来自旧编成或旧资料，请重新核对当前档案。";
        var binding=data.binding(unit);
        if(binding==null||data.stage!=5&&data.stage!=6)return "这台机体尚未绑定本次实际驾驶员，请重新编成。";
        if(action.startsWith("withdraw/"))
            return data.withdraw(expected,unit,player.getUUID())?"驾驶员已撤回，后续指令不会继续下达。":"这项撤回请由本人或本次司令确认。";
        if(binding.kind().equals("human")&&!player.getUUID().equals(binding.pilot()))return "请由已编入的驾驶员本人确认，司令不能替其他玩家同意。";
        if(binding.kind().equals("npc")&&!player.getUUID().equals(data.owner))return "请由本次司令接通这名驾驶员的频道。";
        if(!data.requiredReadingComplete())return "本次要求的实体文书还没有服务端阅读回执，请在真实书台确认。";
        if(binding.kind().equals("human")&&!data.dossierReadCurrent(player.getUUID()))return "请本人先查阅当前三份记录，不能由其他玩家代读后确认。";
        if(binding.kind().equals("npc")&&data.knowledge!=7)return participantLine(unit,false)+"\n请先共享三份记录。";
        var actual=actualBinding(level,unit,binding.kind(),binding.pilot());
        if(!binding.equals(actual))return "原机体或驾驶员身份已变更，请重新编成，不沿用旧确认。";
        if(!data.confirm(expected,actual,formationRevision,evidenceRevision,actual.pilot()))return "本次确认已失效，请核对当前编成与资料修订。";
        return actual.kind().equals("human")?"已记录 "+player.getName().getString()+" 本人驾驶确认，尚未下达发射指令。":participantLine(unit,true);
    }
    private static NervStaffEntity find(ServerLevel level,String skin)
    {
        var post=NervStaffDirector.roster(level).stream().filter(s->s.skin().equals(skin)||s.id().equals(skin)).findFirst().orElse(null);if(post==null)return null;
        load(level,post.feet());var id=NervStaffSavedData.get(level).identity(post.id());return id!=null&&level.getEntity(id) instanceof NervStaffEntity npc?npc:null;
    }
    private static void load(ServerLevel level,BlockPos position)
    {var chunk=new ChunkPos(position);level.getChunkSource().addRegionTicket(TICKET,chunk,2,chunk);level.getChunkAt(position);}
    private static boolean powered(ServerLevel level,BlockPos at)
    {var state=level.getBlockState(at);return state.getBlock() instanceof LeverBlock&&state.getValue(BlockStateProperties.POWERED);}
    private static boolean beginEngineer(ServerPlayer player,ServerLevel level,Site site,CityCoordinationSavedDataR44 data,String operation)
    {
        var npc=find(level,"grid_liaison_r44");if(npc==null||npc.busy())return false;
        load(level,site.test);if(!(level.getBlockState(site.test).getBlock() instanceof ButtonBlock)||!powered(level,site.emergency))return false;
        var path=npc.getNavigation().createPath(site.approach,0);if(path==null||!path.canReach())return false;
        npc.getPersistentData().putUUID("SeeleCoordTaskR44",data.instance);
        npc.begin(player.getUUID(),operation,0,site.test,site.approach);data.operationAt=0;return true;
    }
    public static void operatorTick(NervStaffEntity npc,UUID requester,String operation,BlockPos control,BlockPos approach,int ticks)
    {
        var level=(ServerLevel)npc.level();var data=CityCoordinationSavedDataR44.get(level);var player=level.getServer().getPlayerList().getPlayer(requester);var site=site(level);
        if(Boolean.getBoolean("projectseele.r44CoordinationReview")&&ticks%40==1)
            ProjectSeele.LOGGER.info("Grid operator trace: task={} ticks={} pos={} approach={} navDone={} noAi={} active={} stage={} generation={}",operation,ticks,npc.position(),approach,npc.getNavigation().isDone(),npc.isNoAi(),data.active,data.stage,npc.getPersistentData().get("SeeleCoordTaskR44"));
        if(!data.active||!requester.equals(data.owner)||player==null||!NervStaffDialogue.authorized(player)||site==null||!npc.memberId().equals("grid_liaison_r44")
                ||!npc.getPersistentData().hasUUID("SeeleCoordTaskR44")||!npc.getPersistentData().getUUID("SeeleCoordTaskR44").equals(data.instance)
                ||operation.equals("coord_test")&&data.stage!=3||operation.equals("coord_charge")&&data.stage!=4
                ||operation.equals("coord_reconnect")&&(data.stage!=3||!data.isolating||data.method.equals("onsite")&&!data.fieldSamplePassed)||ticks>300)
        {ProjectSeele.LOGGER.warn("Grid task stopped: instance={} operator={} ticks={} position={}",data.instance,npc.memberId(),ticks,npc.position());npc.finishTask();data.notice="设备操作中止，请重新核对当前档案。";data.setDirty();return;}
        double distance=npc.distanceToSqr(Vec3.atBottomCenterOf(approach));
        if(distance>.5)
        {
            if(npc.getNavigation().isDone()&&distance<1.2)npc.getMoveControl().setWantedPosition(approach.getX()+.5,approach.getY(),approach.getZ()+.5,.65);
            else if(ticks%20==0)npc.getNavigation().moveTo(approach.getX()+.5,approach.getY(),approach.getZ()+.5,.8);
            return;
        }
        npc.getNavigation().stop();npc.getLookControl().setLookAt(control.getX()+.5,control.getY()+.5,control.getZ()+.5);
        if(!npc.beginPressGesture(control))return;
        var button=level.getBlockState(control);if(!(button.getBlock() instanceof ButtonBlock)){npc.finishTask();data.notice="复测按键已被改动，操作停止。";data.setDirty();return;}
        button.use(level,player,InteractionHand.MAIN_HAND,new BlockHitResult(Vec3.atCenterOf(control),Direction.UP,control,false));npc.pressing();
        var reserve=level.getBlockState(site.reserve);if(!(reserve.getBlock() instanceof LeverBlock)){npc.finishTask();return;}
        boolean wanted=operation.equals("coord_reconnect")||operation.equals("coord_charge")&&data.supply.equals("services");
        if(reserve.getValue(BlockStateProperties.POWERED)!=wanted)reserve.use(level,player,InteractionHand.MAIN_HAND,new BlockHitResult(Vec3.atCenterOf(site.reserve),Direction.UP,site.reserve,false));
        if(operation.equals("coord_reconnect"))
        {
            data.tested=true;data.isolating=false;data.stage=4;data.notice="远山：馈线已复电，检查通过。可以选择供电方案了。";
            data.setDirty();npc.finishTask();return;
        }
        data.operationAt=level.getGameTime();data.isolating=operation.equals("coord_test");data.notice=data.isolating?"备用馈线已隔离，正在等待稳定读数。":"蓄能已开始，应急馈线保持供电。";data.setDirty();npc.finishTask();
        ProjectSeele.LOGGER.info("Grid physical switch committed: instance={} operation={} reserve={} emergency={}",data.instance,operation,powered(level,site.reserve),powered(level,site.emergency));
    }
    @SubscribeEvent public static void fieldUse(PlayerInteractEvent.RightClickBlock event)
    {
        if(!(event.getEntity() instanceof ServerPlayer player)||!(event.getLevel() instanceof ServerLevel level))return;
        Site site=site(level);if(site==null||site.fieldButton==null||!site.fieldButton.equals(event.getPos()))return;
        var data=CityCoordinationSavedDataR44.get(level);String reply;
        if(!site.passengerAccessCertified||!(level.getBlockState(site.fieldButton).getBlock() instanceof ButtonBlock))reply="这台复测设备尚未开放。";
        else if(!NervStaffDialogue.authorized(player)||!player.getUUID().equals(data.owner)||!data.active)reply="请由本次调度的司令操作。";
        else if(data.stage!=3||!data.method.equals("onsite")||!data.isolating)reply="先通知远山隔离备用馈线，再开始复测。";
        else if(powered(level,site.reserve)||!powered(level,site.emergency))reply="馈线状态不符，请先核对隔离和应急供电。";
        else if(data.fieldSampling)reply="正在记录。请留在复测台，等读数稳定。";
        else if(data.fieldSamplePassed)reply="复测记录已收到，远山正在复电。";
        else
        {
            var state=level.getBlockState(site.fieldButton);state.use(level,player,event.getHand(),event.getHitVec());
            data.fieldSampling=true;data.fieldStartedAt=level.getGameTime();data.fieldSamples=0;data.setDirty();
            reply="复测开始。请留在台前，等待隔离灯转绿。";
        }
        player.displayClientMessage(net.minecraft.network.chat.Component.literal(reply),false);
        event.setCanceled(true);event.setCancellationResult(InteractionResult.SUCCESS);
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||event.getServer().getTickCount()%10!=0)return;
        var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;var data=CityCoordinationSavedDataR44.get(level);if(!data.active&&!data.restoring)return;var site=site(level);if(site==null)return;
        load(level,site.reserve);load(level,site.emergency);
        if(site.fieldIndicator!=null)
        {
            load(level,site.fieldIndicator);var indicator=level.getBlockState(site.fieldIndicator);
            if(indicator.is(com.projectseele.registry.ModBlocks.NERV_CIRCUIT_INDICATOR.get()))
                level.setBlock(site.fieldIndicator,indicator.setValue(BlockStateProperties.LIT,data.active&&data.stage==3&&data.isolating&&!powered(level,site.reserve)&&powered(level,site.emergency)),2);
        }
        if(data.restoring)
        {
            var state=level.getBlockState(site.reserve);if(state.getBlock() instanceof LeverBlock)
            {if(!state.getValue(BlockStateProperties.POWERED))level.setBlock(site.reserve,state.setValue(BlockStateProperties.POWERED,true),3);data.restoring=false;data.setDirty();}return;
        }
        if(data.stage==2&&data.cityRequested)
        {
            var origin=IntegratedNervMapBuilder.tokyo3Origin(level);var district=Tokyo3RetractionSavedData.get(level).get(origin).orElse(null);
            if(district!=null&&district.depth()==ThirdTokyoSurfaceBuilder.maximumRetractionDepth(origin)&&district.targetDepth()==district.depth()&&district.cursor()==0&&district.voxelCursor()==0&&district.fault().isEmpty())
            {data.stage=3;data.notice="城市已完成收纳。复测可以开始。";data.setDirty();}
        }
        if(!powered(level,site.emergency))
        {
            data.chargeTicks=0;data.fieldSampling=data.fieldSamplePassed=false;data.fieldSamples=0;data.fieldStartedAt=0;
            data.notice="应急馈线失电，充能与复测已暂停。";data.setDirty();return;
        }
        if(data.fieldSampling)
        {
            var owner=level.getServer().getPlayerList().getPlayer(data.owner);
            boolean valid=data.active&&data.stage==3&&data.isolating&&data.method.equals("onsite")&&site.fieldButton!=null
                    &&level.getBlockState(site.fieldButton).getBlock() instanceof ButtonBlock&&owner!=null&&owner.level()==level
                    &&NervStaffDialogue.authorized(owner)&&owner.distanceToSqr(Vec3.atCenterOf(site.visit))<64
                    &&!powered(level,site.reserve)&&powered(level,site.emergency);
            if(!valid){data.fieldSampling=false;data.fieldSamples=0;data.fieldStartedAt=0;data.notice="复测已暂停。请核对馈线，并回到台前重新开始。";}
            else if(++data.fieldSamples>=12&&level.getGameTime()-data.fieldStartedAt>=120)
            {data.fieldSampling=false;data.fieldSamplePassed=true;data.notice="复测记录稳定。远山正在复电。";}
            data.setDirty();
        }
        if(data.stage==3&&data.isolating&&data.operationAt>0&&level.getGameTime()-data.operationAt>=120)
        {
            if(powered(level,site.reserve))
            {data.isolating=data.fieldSampling=data.fieldSamplePassed=false;data.fieldSamples=0;data.notice="隔离期间馈线被重新接入，复测未通过。";data.setDirty();return;}
            if(data.method.equals("onsite")&&!data.fieldSamplePassed)return;
            var owner=level.getServer().getPlayerList().getPlayer(data.owner);
            if(owner!=null&&beginEngineer(owner,level,site,data,"coord_reconnect")){data.notice="远山：复测记录收到了。现在复电。";data.setDirty();}
        }
        if(data.stage==4&&!data.supply.isEmpty()&&data.operationAt>0)
        {
            boolean expected=data.supply.equals("services");if(powered(level,site.reserve)!=expected){data.chargeTicks=0;data.notice="馈线状态与方案不符，充能已暂停。";data.setDirty();return;}
            data.chargeTicks+=10;if(data.chargeTicks>=(expected?800:400)){data.stage=5;data.notice="律子：供电准备完成。现在确认驾驶员和掩护编成。";}data.setDirty();
        }
    }
    private CityCoordinationR44() {}
}

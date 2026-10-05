package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import com.projectseele.registry.ModItems;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.*;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.phys.*;
import java.util.*;

/** Deterministic dialogue and finite, server-authoritative console requests. */
public final class NervStaffDialogue
{
    public static void say(ServerPlayer player,String name,String line)
    {
        // Named characters use chat only. Facility PA is a separate sound circuit.
        player.sendSystemMessage(Component.literal("「"+name+"」 ").withStyle(ChatFormatting.AQUA).append(Component.literal(line).withStyle(ChatFormatting.WHITE)));
        if("r15-staff".equals(System.getProperty("projectseele.regionalBuild","")))ProjectSeele.LOGGER.info("STAFF REVIEW DIALOGUE {} {}",name,line);
    }
    public static void reply(ServerPlayer player,NervStaffEntity npc,String line)
    {
        say(player,npc.getName().getString(),line);
        StaffConversationR24.note(player,npc,line);
    }
    public static void greet(ServerPlayer player,NervStaffEntity npc)
    {
        say(player,npc.getName().getString(),StaffDialogueCatalogR24.next(
                player,StaffDialogueCatalogR24.profile(npc),npc.staffRole(),"greeting"));
    }
    public static String commandRefusal(ServerPlayer player,NervStaffEntity npc,String operation)
    {
        if(!authorized(player))return "请先出示 NERV 通行证。";
        return StaffDialogueCatalogR24.next(player,StaffDialogueCatalogR24.profile(npc),npc.staffRole(),"command_denied");
    }
    private static MutableComponent option(String text,String command)
    {return Component.literal("["+text+"] ").withStyle(s->s.withColor(ChatFormatting.GOLD).withClickEvent(new ClickEvent(ClickEvent.Action.RUN_COMMAND,command)));}
    public static String stage(String value)
    {
        EvaFleetSavedData.Phase phase;
        try{phase=EvaFleetSavedData.Phase.valueOf(value);}catch(RuntimeException exception){return "等待状态确认";}
        return switch(phase)
        {
            case PARKED->"机库待命";case BRIDGE_RETRACTING->"收回登机桥";case PLUG_INSERTING->"插入栓接入";
            case PLUG_ABORT_RETURNING,PLUG_ABORT_DOCKED->"中止接入并返回";case PLUG_FAULT->"插入栓故障，等待检修";
            case PLUG_LOCKING->"锁定插入栓";case DRAINING->"排出 LCL";case TO_SILO->"运往发射井";
            case SILO_READY->"发射待命";case DEPLOYED->"已出动";case DESCENDING->"回收下降";
            case TO_HANGAR->"返回机库";case FILLING->"恢复 LCL";
        };
    }
    public static void open(ServerPlayer player,NervStaffEntity npc)
    { StaffConversationR24.open(player,npc,false); }
    public static void openChat(ServerPlayer player,NervStaffEntity npc)
    {
        reply(player,npc,StaffDialogueCatalogR24.line(StaffDialogueCatalogR24.profile(npc),npc.staffRole(),"greeting",player.tickCount / 100));
        String prefix="/nerv talk \""+npc.memberId()+"\" ";var menu=option("战况",prefix+"状态");
        if(StaffAuthorityR25.commandContact(npc))
        {
            for(int v=0;v<3;v++){String unit=String.format(Locale.ROOT,"%02d",v);menu.append(option("整备 "+unit,prefix+"整备 "+unit)).append(option("发射 "+unit,prefix+"发射 "+unit)).append(option("回收 "+unit,prefix+"回收 "+unit));}
            menu.append(option("整备后发射 01",prefix+"整备后发射 01")).append(option("取消后续操作",prefix+"停止操作"));
        }
        player.sendSystemMessage(menu);
        player.sendSystemMessage(option("道路指引",prefix+"TOPIC:directions").append(option("同步与驾驶",prefix+"TOPIC:sync")).append(option("插入栓",prefix+"TOPIC:plug")).append(option("作战记录",prefix+"TOPIC:campaign")).append(option("值班闲聊",prefix+"TOPIC:duty")));
    }
    public static boolean authorized(ServerPlayer player)
    {
        return player.createCommandSourceStack().hasPermission(2)||java.util.stream.Stream.concat(player.getInventory().items.stream(),player.getInventory().offhand.stream()).anyMatch(s->s.is(ModItems.NERV_EMPLOYEE_CARD.get())||s.is(ModItems.TERMINAL_DOGMA_ACCESS_CARD.get()));
    }
    public static int talk(ServerPlayer player,String target,String text)
    {
        var nearby=player.serverLevel().getEntitiesOfClass(NervStaffEntity.class,player.getBoundingBox().inflate(10),n->n.memberId().equals(target)||n.getStringUUID().equals(target));
        if(nearby.isEmpty()){player.sendSystemMessage(Component.literal("请走到工作人员身边再交谈。"));return 0;}
        var npc=nearby.get(0);if(player.distanceToSqr(npc)>100)return 0;
        return converse(player,npc,text);
    }
    public static int converse(ServerPlayer player,NervStaffEntity npc,String text)
    {
        if(text.startsWith("ROUTE:"))
        {reply(player,npc,NervWayfindingR24.start(player,text.substring(6)));return 1;}
        if(text.startsWith("CAMPAIGN:"))
        {
            if(!StaffAuthorityR25.allows(npc,"campaign") || !authorized(player))
            {reply(player,npc,"作战安排请联络葛城部长或冬月副司令。");return 0;}
            if(text.startsWith("CAMPAIGN:select:"))
            {
                int result=com.projectseele.event.TvCampaignDirector.select(player,text.substring("CAMPAIGN:select:".length()));
                reply(player,npc,com.projectseele.event.TvCampaignDirector.briefing(player));return result;
            }
            if(text.startsWith("CAMPAIGN:sortie:"))
            {
                try
                {
                    String[] a=text.split(":");if(a.length!=6||!Set.of("human","npc").contains(a[4])||!Set.of("rifle","melee").contains(a[5]))return 0;
                    var missionLevel=com.projectseele.event.TvCampaignDirector.level(player);
                    var ongoing=missionLevel==null?null:TvCampaignSavedData.get(missionLevel);
                    if(ongoing==null||ongoing.active.isEmpty()){if(com.projectseele.event.TvCampaignDirector.select(player,a[2])==0)return 0;}
                    else if(!ongoing.active.equals(a[2])){reply(player,npc,"当前作战尚未结束。请选择当前目标，再追加支援机体。");return 0;}
                    int result=com.projectseele.event.TvCampaignDirector.beginAssigned(player,Integer.parseInt(a[3]),a[4].equals("npc"),a[5].equals("rifle"));
                    reply(player,npc,com.projectseele.event.TvCampaignDirector.briefing(player));return result;
                }
                catch(NumberFormatException error){reply(player,npc,"机体编号无效。");return 0;}
            }
            int result=switch(text)
            {
                case "CAMPAIGN:begin" -> com.projectseele.event.TvCampaignDirector.begin(player);
                case "CAMPAIGN:cancel" -> com.projectseele.event.TvCampaignDirector.cancel(player);
                default -> 0;
            };
            reply(player,npc,com.projectseele.event.TvCampaignDirector.briefing(player));return result;
        }
        var intent=StaffIntentR24.parse(text);
        switch(intent.kind())
        {
            case CANCEL ->
            {
                boolean recovery=StaffRecoveryR47.cancel(player,intent.unit());
                int result=StaffCommandBookR24.cancel(player,npc,intent.unit());
                if(recovery)reply(player,npc,"后续回收安排已取消。已开始的机械运输会继续到安全位置。");
                return recovery?1:result;
            }
            case ACTION ->
            {
                if(intent.subject().startsWith("city_"))
                {
                    if(!authorized(player)||!StaffAuthorityR25.allows(npc,intent.subject()))
                    {reply(player,npc,"城市升降由冬月副司令操作，请联络他。");return 0;}
                    if(npc.busy()||StaffCommandBookR24.order(npc)!=null){reply(player,npc,"手上的操作还没结束，稍等一下。");return 0;}
                    return beginNativeAction(player,npc,intent.subject(),-1);
                }
                if(intent.subject().equals("board"))
                {reply(player,npc,StaffPilotOrdersR25.request(player,npc,intent.unit()));return 1;}
                if(intent.subject().equals("standby"))
                {reply(player,npc,StaffPilotOrdersR25.returnToStandby(player,npc,intent.unit()));return 1;}
                if(intent.subject().equals("recover"))
                {reply(player,npc,StaffRecoveryR47.request(player,npc,intent.unit()));return StaffRecoveryR47.queuedBy(player,intent.unit())?1:0;}
                if(intent.subject().equals("support"))
                {
                    if(!authorized(player)||!StaffAuthorityR25.allows(npc,"campaign"))
                    {reply(player,npc,"支援编成请联络葛城部长或冬月副司令。");return 0;}
                    if(TvCampaignSavedData.get(player.serverLevel()).active.isEmpty())
                    {reply(player,npc,"当前没有已接受的作战。先选择目标并下达首次出击，再追加支援机体。");return 0;}
                    return TvSortiesR32.reinforce(player,intent.unit(),true,false);
                }
                return StaffCommandBookR24.request(player,npc,intent.subject(),intent.unit());
            }
            case INVALID -> { reply(player,npc,intent.subject());return 0; }
            case QUERY ->
            {
                List<String> lines=new ArrayList<>();
                for(int v=0;v<3;v++)if(intent.unit()<0||intent.unit()==v)
                    lines.add(unitName(v)+"："+readinessHint(player.serverLevel(),v,"query"));
                reply(player,npc,String.join("\n",lines));return 1;
            }
            default ->
            {
                if(intent.subject().equals("status"))
                {
                    for(int v=0;v<3;v++)
                    {
                        var status=EvaLogisticsDirector.status(player.serverLevel(),v);
                        reply(player,npc,unitName(v)+"："+stage(status.phase())+"，"+(status.loaded()?"机体信号在线":"等待远端信号")+"。");
                    }
                    var job=StaffCommandBookR24.order(npc);if(job!=null)reply(player,npc,"当前指令："+unitName(job.unit)+" · "+job.message+"。");
                }
                else if(intent.subject().equals("campaign"))
                    reply(player,npc,StaffAuthorityR25.allows(npc,"campaign")
                        ?com.projectseele.event.TvCampaignDirector.briefing(player)
                        :StaffDialogueCatalogR24.next(player,StaffDialogueCatalogR24.profile(npc),npc.staffRole(),"campaign"));
                else if(intent.subject().equals("city"))
                {
                    var origin=IntegratedNervMapBuilder.tokyo3Origin(player.serverLevel());
                    int depth=Tokyo3RetractionDirector.depth(player.serverLevel(),origin);
                    reply(player,npc,npc.skin().equals("fuyutsuki")
                            ?"碇，城市目前收纳了 "+depth+" 米。你要收纳，还是展开？"
                            :"城市目前收纳了 "+depth+" 米。升降请联络冬月副司令。");
                }
                else if(intent.subject().equals("directions"))
                    reply(player,npc,npc.staffRole().startsWith("un_")
                        ?"去车辆区、航空区或试验机库，请沿人员标线走。滑行道上不要停留。地下总部的路线，要到总部以后才能引导。"
                        :NervWayfindingR24.describe(player));
                else if(intent.subject().equals("sync")&&Set.of("r47/experiment/researcher_0","r47/experiment/researcher_1").contains(npc.memberId()))
                    reply(player,npc,SynchLabDirectorR47.staffReportR47(player,npc.memberId().endsWith("_0")?0:1));
                else reply(player,npc,StaffDialogueCatalogR24.next(player,StaffDialogueCatalogR24.profile(npc),npc.staffRole(),intent.subject()));
                return 1;
            }
        }
    }
    public static String unitName(int variant)
    {return switch(variant){case 0->"零号机";case 1->"初号机";default->"二号机";};}
    public static boolean boarded(ServerLevel level,int variant)
    {
        var unit=EvaLogisticsDirector.canonicalUnit(level,variant);if(unit==null)return false;
        if(unit.getPilotEntity()!=null)return true;
        var plug=EntryPlugDirector.canonical(level,variant);
        return plug!=null&&(plug.getFirstPassenger() instanceof ServerPlayer||plug.getFirstPassenger() instanceof TrainingPilotEntity);
    }
    public static String readinessHint(ServerLevel level,int variant,String operation)
    {
        var status=EvaLogisticsDirector.status(level,variant);
        if(!status.loaded())return "还没收到机库的信号，请稍等。";
        return switch(status.phase())
        {
            case "PARKED" -> boarded(level,variant)?"驾驶员已登机，可以开始整备。":"驾驶员还没登机。先进入机库里悬挂的插入栓，再开始整备。";
            case "SILO_READY" -> "机体已到发射台，等待发射命令。";
            case "DEPLOYED" -> "机体已经出动。回收时，请回到本机的地表平台停稳。";
            case "PLUG_FAULT" -> "插入栓接入出了故障。先中止接入，再到机库检查。";
            default -> "正在"+stage(status.phase())+"，请稍等。";
        };
    }
    public static int beginNativeAction(ServerPlayer player,NervStaffEntity npc,String op,int variant)
    {
        if(!StaffAuthorityR25.allows(npc,op)||!authorized(player)||npc.busy())return 0;
        BlockPos control=NervOperationsConsole.staffControl(player.serverLevel(),op,variant);
        if(control==null||!(player.serverLevel().getBlockState(control).getBlock() instanceof ButtonBlock)){reply(player,npc,"控制台的按钮出了问题，暂时不能操作。");return 0;}
        BlockPos approach=approach(npc,control,op.startsWith("city_"));
        if(approach==null){reply(player,npc,"控制台前面被挡住了。我暂时过不去。");return 0;}
        if(op.startsWith("city_"))
        {
            npc.begin(player.getUUID(),op,variant,control,approach);
            reply(player,npc,"知道了，碇。准备"+(op.equals("city_rise")?"展开城市。":"收纳城市。"));return 1;
        }
        EvaLogisticsDirector.loadControlTarget(player.serverLevel(),variant);
        npc.begin(player.getUUID(),op,variant,control,approach);reply(player,npc,"收到，司令。"+unitName(variant)+(op.equals("prepare")?"准备出击。":op.equals("launch")?"进入发射程序。":"开始回收。请让出运输通道。"));return 1;
    }
    private static BlockPos approach(NervStaffEntity npc,BlockPos button,boolean city)
    {
        var level=(ServerLevel)npc.level();List<BlockPos> options=new ArrayList<>();var buttonState=level.getBlockState(button);
        var facing=buttonState.getValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.HORIZONTAL_FACING);
        var normal=switch(buttonState.getValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.ATTACH_FACE))
        {case FLOOR->net.minecraft.core.Direction.UP;case CEILING->net.minecraft.core.Direction.DOWN;case WALL->facing;};
        Vec3 outward=Vec3.atLowerCornerOf(normal.getNormal());
        Vec3 contact=Vec3.atLowerCornerOf(button).add(buttonState.getShape(level,button).bounds().getCenter());
        for(BlockPos p:BlockPos.betweenClosed(button.offset(-3,-3,-3),button.offset(3,0,3)))
        {
            // City keys sit on a desk. Approach from the posted dais floor,
            // never select the desktop/button as a shorter standing position.
            if(city&&p.getY()!=npc.station().getY())continue;
            if(!level.hasChunkAt(p)||level.getBlockState(p.below()).getCollisionShape(level,p.below()).isEmpty())continue;
            if(!level.noCollision(npc,new AABB(p.getX()+.2,p.getY()+.01,p.getZ()+.2,p.getX()+.8,p.getY()+1.8,p.getZ()+.8)))continue;
            Vec3 eye=Vec3.atBottomCenterOf(p).add(0,1.5,0);
            if(eye.distanceToSqr(contact)>6.25||eye.subtract(contact).dot(outward)<.3)continue;
            var hit=level.clip(new net.minecraft.world.level.ClipContext(eye,contact,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,npc));
            if(hit.getType()!=HitResult.Type.MISS&&!hit.getBlockPos().equals(button))continue;options.add(p.immutable());
        }
        options.sort(Comparator.<BlockPos>comparingDouble(p->Vec3.atBottomCenterOf(p).distanceToSqr(Vec3.atCenterOf(button))).thenComparingDouble(p->npc.distanceToSqr(Vec3.atBottomCenterOf(p))));
        if("r15-staff".equals(System.getProperty("projectseele.regionalBuild","")))ProjectSeele.LOGGER.info("STAFF PATH REVIEW actor={} pos={} onGround={} candidates={}",npc.memberId(),npc.position(),npc.onGround(),options);
        for(var p:options){var path=npc.getNavigation().createPath(p,0);if(path!=null&&path.canReach())return p;}return null;
    }
    public static void tickTask(NervStaffEntity npc,UUID owner,String operation,int variant,BlockPos control,BlockPos approach,int ticks)
    {
        if(operation.startsWith("coord_"))
        {CityCoordinationR44.operatorTick(npc,owner,operation,control,approach,ticks);return;}
        var level=(ServerLevel)npc.level();var player=level.getServer().getPlayerList().getPlayer(owner);
        boolean city=operation.equals("city_rise")||operation.equals("city_lower");
        if(ticks%40==0&&"r15-staff-controls".equals(System.getProperty("projectseele.regionalBuild","")))ProjectSeele.LOGGER.info("STAFF CONTROL TRACE actor={} pos={} target={} navDone={} onGround={} loaded={}",npc.memberId(),npc.position(),approach,npc.getNavigation().isDone(),npc.onGround(),EvaLogisticsDirector.status(level,variant).loaded());
        if(player==null||player.level()!=level||(StaffCommandBookR24.order(npc)==null&&player.distanceToSqr(npc)>48*48&&!(city&&StaffConversationR24.radioAllowed(player)))||!authorized(player)||!StaffAuthorityR25.allows(npc,operation)||ticks>300)
        {
            String reason=player==null||player.level()!=level?"通信断了，操作已经停下。":!authorized(player)||!StaffAuthorityR25.allows(npc,operation)?"通行权限已变更，操作停止。":ticks>300?"没能及时到达控制台，这次操作已取消。":"通信距离太远，操作已取消。";
            if(city&&player!=null)reply(player,npc,reason);
            else StaffCommandBookR24.failed(npc,reason);
            npc.finishTask();return;
        }
        if(!city&&ticks%20==0&&!EvaLogisticsDirector.status(level,variant).loaded())EvaLogisticsDirector.loadControlTarget(level,variant);
        if(npc.distanceToSqr(Vec3.atBottomCenterOf(approach))>.16)
        {
            if(npc.getNavigation().isDone()&&npc.distanceToSqr(Vec3.atBottomCenterOf(approach))<1.2)
                npc.getMoveControl().setWantedPosition(approach.getX()+.5,approach.getY(),approach.getZ()+.5,.65);
            else if(ticks%20==0)npc.getNavigation().moveTo(approach.getX()+.5,approach.getY(),approach.getZ()+.5,.9);
            return;
        }
        npc.getNavigation().stop();npc.getLookControl().setLookAt(control.getX()+.5,control.getY()+.5,control.getZ()+.5,30,30);
        float facing=(float)Math.toDegrees(Math.atan2(-(control.getX()+.5-npc.getX()),control.getZ()+.5-npc.getZ()));
        npc.setYRot(net.minecraft.util.Mth.approachDegrees(npc.getYRot(),facing,18));npc.yBodyRot=npc.getYRot();
        if(Math.abs(net.minecraft.util.Mth.wrapDegrees(facing-npc.getYRot()))>12)return;
        if(!city&&!EvaLogisticsDirector.status(level,variant).loaded()&&ticks<240)return;
        if(!city&&!StaffCommandBookR24.validateAutomatic(npc))return;
        if(!npc.beginPressGesture(control))return;
        var state=level.getBlockState(control);
        if(!(state.getBlock() instanceof ButtonBlock)||state.getValue(ButtonBlock.POWERED))
        {StaffCommandBookR24.failed(npc,"按键状态已变化，操作未执行。");npc.finishTask();return;}
        npc.pressing();
        // Physical depression and the existing authoritative console dispatcher are
        // separate in the original player interaction hook. Invoke each exactly once.
        state.use(level,player,InteractionHand.MAIN_HAND,new BlockHitResult(Vec3.atCenterOf(control),net.minecraft.core.Direction.UP,control,false));
        boolean handled=NervOperationsConsole.handleStaffUse(player,control);
        if(city)
        {
            var result=handled?NervOperationsConsole.lastOutcome(level,player,control):null;
            reply(player,npc,result!=null&&result.accepted()?"碇，控制台已收到"+(operation.equals("city_rise")?"展开":"收纳")+"指令。":"城市还不能升降。"+(result==null?"控制台没有响应。":result.message()));
            ProjectSeele.LOGGER.info("STAFF CITY actor={} operation={} button={} accepted={}",npc.memberId(),operation,control,result!=null&&result.accepted());
            npc.finishTask();return;
        }
        var status=EvaLogisticsDirector.status(level,variant);
        var outcome=handled?NervOperationsConsole.lastOutcome(level,player,control):null;
        boolean accepted=outcome!=null&&outcome.accepted();
        if(StaffCommandBookR24.order(npc)==null||accepted&&!operation.equals("launch"))
            reply(player,npc,accepted?unitName(variant)+"，"+stage(status.phase())+"。":"现在还不能操作。"+readinessHint(level,variant,operation));
        StaffCommandBookR24.pressed(npc,outcome);
        ProjectSeele.LOGGER.info("STAFF CONSOLE actor={} operation={} unit={} button={} requester={} phase={}",npc.memberId(),operation,variant,control,owner,status.phase());npc.finishTask();
    }
    public static void pilot(ServerPlayer player,TrainingPilotEntity pilot)
    {
        say(player,TrainingPilotEntity.pilotName(pilot.getAssignedVariant()),PilotRadioR28.response(player,pilot,true));
    }
    private NervStaffDialogue() {}
}

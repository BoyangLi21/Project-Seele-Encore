package com.projectseele.client.screen;

import com.projectseele.network.*;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.components.Tooltip;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;
import com.projectseele.world.StaffAuthorityR25;
import java.util.*;

/** A non-pausing command channel: visible state comes from the server. */
public final class StaffConversationScreen extends Screen
{
    private ClientboundStaffConversationPacket view;
    private EditBox input;
    private EditBox transportX,transportY,transportZ;
    private int transportReturnExit;
    private String mission="sachiel";
    private boolean npcSortie;
    private String sortieEquipment="rifle";
    private int x, y, panelWidth, panelHeight, tab, unit = 1, age, replyScroll, replyTop;
    private UUID humanPilot;
    private final Map<Integer,String> sortieCrewR54=new LinkedHashMap<>();
    private boolean sortieCrewInitializedR54;
    private final Map<AbstractWidget,Integer> controlRows=new LinkedHashMap<>();
    private final Set<String> pageDenials=new LinkedHashSet<>();
    private int controlsScroll,controlsScrollMax;
    private boolean buildingControls;

    private StaffConversationScreen(ClientboundStaffConversationPacket view)
    {
        super(Component.literal("指挥通信")); this.view = view;
        if(!view.selectedMission().isEmpty())mission=view.selectedMission();
    }

    public static void receive(ClientboundStaffConversationPacket packet)
    {
        var mc = Minecraft.getInstance();
        if (mc.screen instanceof StaffConversationScreen screen && screen.view.session().equals(packet.session()))
        {
            if (!packet.valid())
            {
                if (mc.player != null) mc.player.displayClientMessage(Component.literal(packet.reply()), false);
                mc.setScreen(null); return;
            }
            boolean changed = screen.view.canCommand() != packet.canCommand()
                    ||screen.view.authorized()!=packet.authorized()
                    ||screen.view.coordinationFormationRevision()!=packet.coordinationFormationRevision()
                    ||screen.view.coordinationEvidenceRevision()!=packet.coordinationEvidenceRevision()
                    ||!packet.selectedMission().isEmpty()&&!screen.mission.equals(packet.selectedMission());
            if(!packet.selectedMission().isEmpty())screen.mission=packet.selectedMission();
            if (!screen.view.reply().equals(packet.reply()))
            {
                screen.replyScroll = 0;
                mc.getSoundManager().play(net.minecraft.client.resources.sounds.SimpleSoundInstance.forUI(com.projectseele.registry.ModSounds.STAFF_RADIO_ACK.get(),1,.35F));
            }
            screen.view = packet;
            if (changed) screen.rebuildWidgets();
        }
        else if (packet.open() && packet.valid())
        {
            var replacement = new StaffConversationScreen(packet);
            if (mc.screen instanceof StaffConversationScreen old)
            { replacement.unit = old.unit; replacement.tab = packet.canCommand() ? old.tab : 0;replacement.npcSortie=old.npcSortie;replacement.sortieEquipment=old.sortieEquipment;replacement.sortieCrewR54.putAll(old.sortieCrewR54);replacement.sortieCrewInitializedR54=old.sortieCrewInitializedR54; }
            mc.setScreen(replacement);
            mc.getSoundManager().play(net.minecraft.client.resources.sounds.SimpleSoundInstance.forUI(com.projectseele.registry.ModSounds.STAFF_RADIO_CONNECT.get(),1,.4F));
        }
    }
    public ClientboundStaffConversationPacket snapshot() { return view; }

    static int readableGuiScale(int preferredScale,int windowWidth,int windowHeight,boolean unicode)
    {
        int fit=Math.max(1,Math.min(windowWidth/430,windowHeight/300));
        int selected=Math.max(1,Math.min(preferredScale,fit));
        if(unicode&&selected>1&&selected%2!=0)selected--;
        return selected;
    }

    @Override protected void init()
    {
        var window=minecraft.getWindow();
        int fitScale=readableGuiScale(ScreenGuiScale.normal(minecraft),window.getWidth(),window.getHeight(),minecraft.isEnforceUnicode());
        // resize() comes back here with the new scale already set, and builds the widgets.
        if(ScreenGuiScale.set(minecraft,fitScale)){resize(minecraft,window.getGuiScaledWidth(),window.getGuiScaledHeight());return;}
        String draft=input==null?"":input.getValue();controlRows.clear();pageDenials.clear();buildingControls=false;
        panelWidth = Math.min(640, width - 16); panelHeight = Math.min(444, height - 16);
        x = (width - panelWidth) / 2; y = (height - panelHeight) / 2;
        int tabWidth=(panelWidth-24)/5;
        String command=denial(StaffAuthorityR25.COMMAND);
        addTab("交谈",0,x+12,tabWidth-3,()->switchTab(0),"");
        addTab("指挥",1,x+12+tabWidth,tabWidth-3,()->switchTab(1),command);
        addTab("作战",2,x+12+tabWidth*2,tabWidth-3,()->{switchTab(2);send("TOPIC:campaign");},"");
        addTab("通讯录",4,x+12+tabWidth*3,tabWidth-3,()->switchTab(4),"");
        addTab("运输部门",6,x+12+tabWidth*4,tabWidth-3,()->{switchTab(6);send("TRANSPORT:status");},command);
        addButton("关闭", x + panelWidth - 60, y + 12, 48, this::onClose, "");
        int controlsY = controlsTop();
        buildingControls=true;
        int column = (panelWidth - 32) / 3;
        if (tab == 0)
        {
            String[][] topics = {{"当前状态", "status"}, {"道路指引", "directions"}, {"同步与驾驶", "sync"},
                    {"插入栓接入", "plug"}, {"供电与回收", "power"}, {"聊一会儿", "chat"}};
            for (int i = 0; i < topics.length; i++)
            {
                String request = "TOPIC:" + topics[i][1];
                addButton(topics[i][0], x + 12 + (i % 3) * (column + 4), controlsY + (i / 3) * 22,
                        column, () -> { if(request.equals("TOPIC:directions"))switchTab(3);send(request); }, "");
            }

        }
        else if (tab == 1)
        {
            int half=(panelWidth-28)/2;
            addButton("机体整备与发射",x+12,controlsY,half,()->switchTab(8),command);
            addButton("驾驶员安排",x+16+half,controlsY,half,()->switchTab(9),denial("board"));
            addButton("武器井与装备",x+12,controlsY+22,half,()->switchTab(10),denial("weapons"));
            addButton("城市升降",x+16+half,controlsY+22,half,()->{switchTab(5);send("TOPIC:city");},denial("city_rise"));
            addButton("地下出口门控",x+12,controlsY+44,panelWidth-24,()->switchTab(11),denial("deploy"));
        }
        else if (tab == 8)
        {
            for (int i = 0; i < 3; i++)
            {
                final int selection = i;
                addButton((unit == i ? "● " : "") + com.projectseele.world.NervStaffDialogue.unitName(i),
                        x + 12 + i * (column + 4), controlsY, column, () -> { unit = selection; rebuildWidgets(); }, "");
            }
            String[] commands = {"整备", "发射", "回收"};
            String[] labels = {"仅整备", "确认发射", "回收"};
            for (int i = 0; i < commands.length; i++)
            {
                String action = commands[i];
                addButton(labels[i], x + 12 + i * (column + 4), controlsY + 22, column,
                        () -> send(action + " 0" + unit), denial(new String[]{"prepare","launch","recover"}[i]));
            }
            int half = (panelWidth - 28) / 2;
            addButton("整备＋地表出口", x + 12, controlsY + 44, half, () -> send("OUTLET:"+unit+":surface"), denial("deploy"));
            addButton("整备＋地下出口", x + 16 + half, controlsY + 44, half,
                    () -> send("OUTLET:"+unit+":geofront"), denial("deploy"));
            addButton("整备＋箱根出口", x + 12, controlsY + 66, half,
                    () -> send("OUTLET:"+unit+":hakone"), denial("deploy"));
            addButton("取消后续操作", x + 16 + half, controlsY + 66, half, () -> send("停止操作"), "");
        }
        else if(tab==9)
        {
            selectUnit(controlsY,column);
            int half=(panelWidth-28)/2;
            addButton("驾驶员登机",x+12,controlsY+22,half,()->send("BOARD:"+unit),denial("board"));
            addButton("下机返回待命",x+16+half,controlsY+22,half,()->send("STANDBY:"+unit),denial("board"));
            addButton("询问驾驶员状态",x+12,controlsY+44,half,()->send("PILOT:"+unit),"");
            addButton("与驾驶员聊一会儿",x+16+half,controlsY+44,half,()->send("PILOTCHAT:"+unit),"");
        }
        else if(tab==10)
        {
            addButton("部署就近步枪井",x+12,controlsY,panelWidth-24,()->send("WEAPONS"),denial("weapons"));
            addButton("部署零号机专用盾井",x+12,controlsY+22,panelWidth-24,()->send("WEAPONS:shield"),denial("weapons"));
            addButton("部署二号机专用剑井",x+12,controlsY+44,panelWidth-24,()->send("WEAPONS:sword"),denial("weapons"));
        }
        else if(tab==11)
        {
            selectUnit(controlsY,column);
            int half=(panelWidth-28)/2;
            addButton("开启已出动机体地下门",x+12,controlsY+22,half,()->send("UNDERGROUND:"+unit+":door_open"),denial("deploy"));
            addButton("关闭本机地下紧急门",x+16+half,controlsY+22,half,()->send("UNDERGROUND:"+unit+":close"),denial("deploy"));
        }
        else if(tab==2)
        {
            addButton("任务简报",x+12,controlsY,panelWidth-24,()->send("TOPIC:campaign"),"");
            addButton("选择任务与编队",x+12,controlsY+22,panelWidth-24,()->switchTab(12),denial("campaign"));
            addButton("城市协同档案",x+12,controlsY+44,panelWidth-24,()->{switchTab(7);send("COORD:status");},command);
        }
        else if(tab==12)
        {
            if(!sortieCrewInitializedR54){sortieCrewR54.put(1,minecraft.player.getUUID().toString());if(mission.equals("ramiel"))sortieCrewR54.put(0,"npc");sortieCrewInitializedR54=true;}
            int half = (panelWidth - 28) / 2;
            String campaign=denial("campaign");
            var missions=com.projectseele.world.TvCampaignCatalog.CHAPTERS.stream().filter(com.projectseele.world.TvCampaignCatalog.Chapter::playable).toList();
            int choice=(panelWidth-24-4*(missions.size()-1))/missions.size();
            for(int i=0;i<missions.size();i++)
            {
                var entry=missions.get(i);String selected=entry.id();
                addButton((mission.equals(selected)?"● ":"")+entry.title(),x+12+i*(choice+4),controlsY,choice,
                        ()->{mission=selected;if(selected.equals("ramiel")){sortieCrewR54.putIfAbsent(0,"npc");String self=minecraft.player.getUUID().toString();sortieCrewR54.putIfAbsent(1,sortieCrewR54.containsValue(self)?"npc":self);}send("CAMPAIGN:select:"+selected);rebuildWidgets();},campaign);
            }
            for(int i=0;i<3;i++)
            {
                int selection=i;
                addButton(com.projectseele.world.NervStaffDialogue.unitName(i)+"："+crewLabelR54(i)+"（点击更换）",x+12,controlsY+22+i*22,panelWidth-24,()->{cycleCrewR54(selection);rebuildWidgets();},"");
            }
            if(mission.equals("ramiel"))
                addButton("任务装备：初号机用炮，零号机持盾",x+12,controlsY+88,panelWidth-24,()->{},"拉米尔作战的装备固定，无需更换");
            else addButton("装备："+(sortieEquipment.equals("rifle")?"步枪":"近战")+"（点击更换）",x+12,controlsY+88,panelWidth-24,()->{sortieEquipment=sortieEquipment.equals("rifle")?"melee":"rifle";rebuildWidgets();},"");
            addButton("确认出击",x+12,controlsY+110,half,()->send(formationRequestR54()),
                    !campaign.isEmpty()?campaign:sortieCrewR54.isEmpty()?"请先为至少一台机体安排驾驶员":"");
            addButton("结束任务",x+16+half,controlsY+110,half,()->send("CAMPAIGN:cancel"),campaign);
            addButton("任务进度与编队",x+12,controlsY+132,panelWidth-24,()->send("TOPIC:campaign"),"");
        }
        else if(tab==7)
        {
            addButton("档案阅读与共享",x+12,controlsY,panelWidth-24,()->switchTab(13),command);
            addButton("城市供电与复测",x+12,controlsY+22,panelWidth-24,()->switchTab(14),command);
            addButton("参与机体与确认",x+12,controlsY+44,panelWidth-24,()->switchTab(15),command);
        }
        else if(tab==13||tab==14)
        {
            String[][] actions=tab==13
                    ?new String[][]{{"接受档案","start"},{"当前状态","status"},{"原页","read/page"},{"译注","read/annotation"},{"现场记录","read/field"},{"共享三份记录","share"},{"保留司令档案","private"},{"撤销调度","cancel"}}
                    :new String[][]{{"城市下降 · 保电","evacuate/services"},{"城市下降 · 蓄能","evacuate/storage"},{"委派远山复测","test/delegate"},{"亲自到站复测","test/onsite"},{"保电 · 等两轮","supply/services"},{"备用馈线 · 一轮","supply/reserve"},{"归档准备结果","finish"},{"当前状态","status"}};
            int half=(panelWidth-28)/2;
            for(int i=0;i<actions.length;i++)
            {
                String action=actions[i][1];
                addButton(actions[i][0],x+12+(i%2)*(half+4),controlsY+(i/2)*22,half,()->send("COORD:"+action),command);
            }
        }
        else if(tab==15)
        {
            int half=(panelWidth-28)/2;
            addButton("编成机体："+com.projectseele.world.TvSortiesR32.name(unit),x+12,controlsY,half,()->{unit=(unit+1)%5;if(unit>=3)npcSortie=false;rebuildWidgets();},"");
            String driverLabel=npcSortie?"驾驶员："+com.projectseele.entity.TrainingPilotEntity.pilotName(unit):"驾驶者："+humanPilotName();
            addButton(driverLabel+" / 切换",x+16+half,controlsY,half,()->{cycleParticipant();rebuildWidgets();},"");
            addButton("加入编成",x+12,controlsY+22,column,()->send("COORD:assign/"+unit+"/"+(unit<3&&npcSortie?"npc":"human/"+selectedHuman())),"");
            String archive=view.coordinationFormationRevision()>0?"":"需要先接受城市协同档案";
            addButton("确认说明与待命",x+16+column,controlsY+22,column,()->send("COORD:consent/"+unit+"/"+view.coordinationFormationRevision()+"/"+view.coordinationEvidenceRevision()),archive);
            addButton("驾驶员撤回",x+20+column*2,controlsY+22,column,()->send("COORD:withdraw/"+unit+"/"+view.coordinationFormationRevision()+"/"+view.coordinationEvidenceRevision()),archive);
        }
        else if(tab==6)
        {
            String enteredX=transportX==null?null:transportX.getValue(),enteredY=transportY==null?null:transportY.getValue(),enteredZ=transportZ==null?null:transportZ.getValue();
            var controlled=com.projectseele.world.EvaPilotResolver.controlTarget(minecraft.player);
            var feet=controlled!=null&&controlled.getPilotEntity()==minecraft.player
                    ?net.minecraft.core.BlockPos.containing(com.projectseele.world.NervOwnerPlacementR52.actualRoot(controlled).translation())
                    :minecraft.player.blockPosition();
            for(int i=0;i<3;i++)
            {
                int selection=i;addButton((unit==i?"● ":"")+com.projectseele.world.NervStaffDialogue.unitName(i),x+12+i*(column+4),controlsY,column,()->{unit=selection;rebuildWidgets();},"");
            }
            int half=(panelWidth-28)/2;
            transportX=new PhoneUiR54.Field(font,x+12,controlsY+24,column,20,Component.literal("目的地 X"),PhoneUiR54.NERV);transportY=new PhoneUiR54.Field(font,x+16+column,controlsY+24,column,20,Component.literal("目的地 Y"),PhoneUiR54.NERV);transportZ=new PhoneUiR54.Field(font,x+20+column*2,controlsY+24,column,20,Component.literal("目的地 Z"),PhoneUiR54.NERV);
            transportY.setMaxLength(10);transportY.setFilter(s->s.matches("-?\\d*"));transportY.setValue(enteredY==null?Integer.toString(feet.getY()):enteredY);addRenderableWidget(transportY);
            transportX.setHint(Component.literal("X"));transportY.setHint(Component.literal("Y · 脚下高度"));transportZ.setHint(Component.literal("Z"));
            transportX.setMaxLength(10);transportZ.setMaxLength(10);transportX.setFilter(s->s.matches("-?\\d*"));transportZ.setFilter(s->s.matches("-?\\d*"));
            transportX.setValue(enteredX==null?Integer.toString(feet.getX()):enteredX);transportZ.setValue(enteredZ==null?Integer.toString(feet.getZ()):enteredZ);addRenderableWidget(transportX);addRenderableWidget(transportZ);
            controlRows.put(transportX,transportX.getY());controlRows.put(transportY,transportY.getY());controlRows.put(transportZ,transportZ.getY());
            addButton("投放至 X / Y / Z",x+12,controlsY+48,column,()->send("TRANSPORT:deliver:"+unit+":"+transportX.getValue()+":"+transportY.getValue()+":"+transportZ.getValue()),"");
            addButton("空运回库",x+16+column,controlsY+48,column,()->send("TRANSPORT:recover:"+unit+(transportReturnExit==0?"":":unit"+unit+"/exit"+transportReturnExit+"/port")),"");
            addButton("取消本机 / 安全返回",x+20+column*2,controlsY+48,column,()->send("TRANSPORT:cancel:"+unit),"");
            String returnPort=switch(transportReturnExit){case 1->"GeoFront";case 2->"第三新东京";case 3->"箱根";default->"自动选路";};
            addButton("回库接收口："+returnPort,x+12,controlsY+72,half,()->{String tx=transportX.getValue(),ty=transportY.getValue(),tz=transportZ.getValue();transportReturnExit=(transportReturnExit+1)%4;rebuildWidgets();transportX.setValue(tx);transportY.setValue(ty);transportZ.setValue(tz);},"");
            addButton("运输状态",x+16+half,controlsY+72,half,()->send("TRANSPORT:status"),"");
        }
        else if (tab == 5)
        {
            int half=(panelWidth-28)/2;
            addButton("城市上升",x+12,controlsY,half,()->send("城市上升"),denial("city_rise"));
            addButton("城市下降",x+16+half,controlsY,half,()->send("城市下降"),denial("city_lower"));
            addButton("查询城市状态",x+12,controlsY+22,panelWidth-24,()->send("TOPIC:city"),"");
        }
        else if (tab == 4)
        {
            String[] contacts = {"美里", "律子", "冬月", "摩耶"};
            int half = (panelWidth - 28) / 2;
            for (int i = 0; i < contacts.length; i++)
            {
                String contact = contacts[i];
                addButton(contact, x + 12 + (i % 2) * (half + 4), controlsY + (i / 2) * 22,
                        half, () -> send("CONTACT:" + contact), "");
            }
            for (int i = 0; i < 3; i++)
            {
                int pilot = i;
                addButton(com.projectseele.entity.TrainingPilotEntity.pilotName(i), x + 12 + i * (column + 4),
                        controlsY + 44, column, () -> { unit=pilot; send("PILOTCHAT:" + pilot); }, "");
            }
        }
        else
        {
            String[][] destinations={{"指挥室入口","command"},{"机库","hangars"},{"总部火车站","station"},{"金字塔接驳站","pyramid_station"},{"发射区车站","launch_station"},{"观景走廊","observation"},{"终极教条前厅","dogma"},{"LCL 实验层","experiment"},{"最近电梯","nearest_lift"}};
            for(int i=0;i<destinations.length;i++)
            {
                String key=destinations[i][1];
                addButton(destinations[i][0],x+12+(i%3)*(column+4),controlsY+(i/3)*22,column,()->send("ROUTE:"+key),"");
            }
            addButton("停止步行引导",x+12,controlsY+66,panelWidth-24,()->send("ROUTE:stop"),"");
        }
        buildingControls=false;applyControlScroll();
        int parent=parentTab();
        if(parent>=0)addButton("← 返回"+(parent==0?"交谈":parent==1?"指挥分类":parent==2?"作战":"城市协同档案"),
                x+12,y+panelHeight-55,panelWidth-24,()->switchTab(parent),"");
        input = new PhoneUiR54.Field(font, x + 13, y + panelHeight - 28, panelWidth - 87, 19, Component.literal("输入交谈或指令"),PhoneUiR54.NERV);
        input.setMaxLength(160);input.setValue(draft); input.setHint(Component.literal("输入消息或指令 · Enter 发送")); addRenderableWidget(input);
        addButton("发送", x + panelWidth - 65, y + panelHeight - 29, 52, this::submitText, "");
    }

    /** An empty denial enables the control; otherwise it is greyed out and the denial says why. */
    private void addButton(String title, int left, int top, int width, Runnable action, String denial)
    {
        boolean selected=title.startsWith("● ");String label=selected?title.substring(2):title;
        var button = new PhoneUiR54.Action(left, top, width,20, label, action,PhoneUiR54.NERV,()->selected);
        explain(button,label,denial); addRenderableWidget(button);
        if(buildingControls)
        {
            controlRows.put(button,top);
            if(!denial.isEmpty())pageDenials.add(denial);
        }
    }
    private void addTab(String label,int target,int left,int width,Runnable action,String denial)
    {
        var button=new PhoneUiR54.Action(left,y+50,width,21,label,action,PhoneUiR54.NERV,()->rootTab()==target);
        explain(button,label,denial);addRenderableWidget(button);
    }
    private static void explain(PhoneUiR54.Action button,String label,String denial)
    {
        button.active=denial.isEmpty();
        if(!button.active)button.setTooltip(Tooltip.create(Component.literal(label+"\n"+denial)));
    }
    private int rootTab(){return switch(tab){case 3->0;case 5,8,9,10,11->1;case 7,12,13,14,15->2;default->tab;};}
    private int controlsBottom(){return y+panelHeight-60;}
    private void applyControlScroll()
    {
        int end=controlsTop();for(var row:controlRows.entrySet())end=Math.max(end,row.getValue()+row.getKey().getHeight());
        controlsScrollMax=Math.max(0,end-controlsBottom());controlsScroll=Math.max(0,Math.min(controlsScroll,controlsScrollMax));
        for(var row:controlRows.entrySet())
        {
            var widget=row.getKey();widget.setY(row.getValue()-controlsScroll);
            widget.visible=widget.getY()>=controlsTop()&&widget.getY()+widget.getHeight()<=controlsBottom();
            if(!widget.visible&&widget.isFocused())widget.setFocused(false);
        }
    }
    private UUID selectedHuman(){return humanPilot!=null?humanPilot:minecraft.player.getUUID();}
    private String crewLabelR54(int slot)
    {
        String selected=sortieCrewR54.get(slot);if(selected==null)return "待命";
        if(selected.equals("npc"))return com.projectseele.entity.TrainingPilotEntity.pilotName(slot);
        if(selected.equals(minecraft.player.getUUID().toString()))return "我";
        var player=minecraft.getConnection().getPlayerInfo(UUID.fromString(selected));
        return player==null?"离线玩家":player.getProfile().getName();
    }
    private void cycleCrewR54(int slot)
    {
        var options=new ArrayList<String>();options.add("npc");
        minecraft.getConnection().getOnlinePlayers().stream().sorted(Comparator.comparing(p->p.getProfile().getName()))
                .forEach(p->options.add(p.getProfile().getId().toString()));
        int next=options.indexOf(sortieCrewR54.get(slot))+1;
        if(next>=options.size()){sortieCrewR54.remove(slot);return;}
        String selected=options.get(next);
        if(!selected.equals("npc"))sortieCrewR54.values().removeIf(selected::equals);
        sortieCrewR54.put(slot,selected);
    }
    private String formationRequestR54()
    {
        String rows=String.join(";",sortieCrewR54.entrySet().stream().sorted(Map.Entry.comparingByKey()).map(e->e.getKey()+","+e.getValue()).toList());
        return "CAMPAIGN:formation:"+mission+":"+rows+":"+(!mission.equals("ramiel")&&sortieEquipment.equals("rifle")?"rifle":"melee");
    }
    private String humanPilotName()
    {
        if(humanPilot==null||humanPilot.equals(minecraft.player.getUUID()))return "我";
        var player=minecraft.getConnection().getPlayerInfo(humanPilot);return player==null?"离线玩家":player.getProfile().getName();
    }
    private void cycleParticipant()
    {
        if(npcSortie){npcSortie=false;humanPilot=null;return;}
        var people=new ArrayList<>(minecraft.getConnection().getOnlinePlayers());
        people.sort(Comparator.comparing((net.minecraft.client.multiplayer.PlayerInfo p)->!p.getProfile().getId().equals(minecraft.player.getUUID()))
                .thenComparing(p->p.getProfile().getName()));
        UUID selected=selectedHuman();int index=-1;for(int i=0;i<people.size();i++)if(people.get(i).getProfile().getId().equals(selected)){index=i;break;}
        if(index+1<people.size())humanPilot=people.get(index+1).getProfile().getId();
        else if(unit<3){npcSortie=true;humanPilot=null;}else humanPilot=null;
    }
    private void selectUnit(int top,int column)
    {
        for(int i=0;i<3;i++)
        {
            int selection=i;
            addButton((unit==i?"● ":"")+com.projectseele.world.NervStaffDialogue.unitName(i),
                    x+12+i*(column+4),top,column,()->{unit=selection;rebuildWidgets();},"");
        }
    }
    static String sortieRequest(String mission,int unit,boolean npc,String equipment)
    {
        String driver=npc?"npc":"human";
        if(equipment.equals("special")&&(unit==0||unit==2))return "ARMEDSORTIE:"+unit+":"+driver;
        return "CAMPAIGN:sortie:"+mission+":"+unit+":"+driver+":"+(equipment.equals("rifle")?"rifle":"melee");
    }
    private int parentTab()
    {
        return switch(tab)
        {
            case 3 -> 0;
            case 5,8,9,10,11 -> 1;
            case 7,12 -> 2;
            case 13,14,15 -> 7;
            default -> -1;
        };
    }
    private void switchTab(int next)
    {
        if(next!=7&&next!=13&&next!=14&&next!=15)unit=Math.min(unit,2);
        tab=next;controlsScroll=0;replyScroll=0;rebuildWidgets();
    }
    /** Empty when the server's command grant and the contact's own job both allow the action. */
    private String denial(String action)
    {
        boolean allowed=view.canCommand()&&(action.equals(StaffAuthorityR25.COMMAND)||StaffAuthorityR25.allows("",view.skin(),action));
        return allowed?"":StaffAuthorityR25.denial(view.authorized(),view.skin(),action);
    }
    private int controlsTop()
    {
        int rows=switch(tab)
        {
            case 12 -> 6;
            case 3,6,8,13,14 -> 4;
            case 1,2,4,7,9,10 -> 3;
            default -> 2;
        };
        return y+Math.max(Math.max(142,Math.min(170,panelHeight-120)),panelHeight-(rows*22+76));
    }
    private void submitText() { if (!input.getValue().isBlank()) { send(input.getValue()); input.setValue(""); } }
    private void send(String request)
    {
        if (minecraft != null && minecraft.player != null) SeeleNetwork.CHANNEL.sendToServer(new ServerboundStaffConversationPacket(view.session(), request));
    }
    @Override public void tick()
    {
        if (input != null) input.tick();
        if (++age % 40 == 0) send("REFRESH");
    }
    @Override public boolean keyPressed(int key, int scan, int modifiers)
    {
        if ((key == 257 || key == 335) && input != null && input.isFocused()) { submitText(); return true; }
        return super.keyPressed(key, scan, modifiers);
    }
    @Override public boolean mouseScrolled(double mouseX, double mouseY, double delta)
    {
        if(mouseX>=x+8&&mouseX<x+panelWidth-8&&mouseY>=controlsTop()-20&&mouseY<controlsBottom())
        {controlsScroll-=(int)Math.signum(delta)*22;applyControlScroll();return true;}
        if (mouseX >= x && mouseX < x + panelWidth && mouseY >= replyTop-18 && mouseY < controlsTop()-28)
        { replyScroll = Math.max(0, replyScroll - (int) Math.signum(delta) * 2); return true; }
        return super.mouseScrolled(mouseX, mouseY, delta);
    }
    @Override public void render(GuiGraphics graphics, int mouseX, int mouseY, float partial)
    {
        renderBackground(graphics);
        var theme=PhoneUiR54.NERV;
        PhoneUiR54.frame(graphics,font,theme,x,y,panelWidth,panelHeight,"指挥通信",
                view.name()+"  ·  "+view.role()+"  /  无线电频道");
        int bottom=controlsTop()-28;replyTop=y+99;
        PhoneUiR54.card(graphics,font,theme,x+8,y+78,panelWidth-16,bottom-(y+78)+4,
                tab==2||tab==12?"任务简报":"状态与回复",view.canCommand()?"指挥权限":"交谈权限");
        var transcript=new StringBuilder();
        if(tab<2&&!view.units().isEmpty())transcript.append("机体状态\n").append(String.join("\n",view.units())).append("\n\n");
        else if(tab==15&&view.participants().size()>unit)transcript.append("当前编成\n").append(view.participants().get(unit)).append("\n\n");
        if(!view.order().isBlank())transcript.append("当前调度\n").append(view.order()).append("\n\n");
        if(tab!=2&&tab!=12)transcript.append("回复\n");
        transcript.append(view.reply());
        replyScroll=PhoneUiR54.text(graphics,font,theme,transcript.toString(),x+16,replyTop,panelWidth-32,
                Math.max(0,bottom-replyTop),replyScroll);
        String section=switch(tab){case 0->"交谈主题";case 1->"指挥分类";case 2->"作战任务";case 3->"步行引导";case 4->"通讯录";case 5->"城市升降";case 6->"运输调度 · 目的地 X / Y / Z";case 7->"城市协同档案";case 8->"机体整备与发射";case 9->"驾驶员安排";case 10->"武器井与装备";case 11->"地下出口门控";case 12->"任务与出击编队";case 13->"档案阅读与共享";case 14->"城市供电与复测";case 15->"参与机体与确认";default->"操作";};
        String meta=pageDenials.isEmpty()?"":pageDenials.size()==1?"灰色按钮："+pageDenials.iterator().next():"悬停灰色按钮可查看原因";
        if(controlsScrollMax>0)meta=meta.isEmpty()?"滚轮浏览":meta+"  ·  滚轮浏览";
        PhoneUiR54.card(graphics,font,theme,x+8,controlsTop()-21,panelWidth-16,
                controlsBottom()-controlsTop()+24,section,meta);
        PhoneUiR54.scrollbar(graphics,theme,x+panelWidth-10,controlsTop(),controlsBottom()-controlsTop(),
                controlsBottom()-controlsTop()+controlsScrollMax,controlsBottom()-controlsTop(),controlsScroll);
        graphics.fill(x+12,y+panelHeight-34,x+panelWidth-12,y+panelHeight-33,theme.border());
        if(parentTab()<0)graphics.drawString(font,"输入消息与指令    ·    Enter 发送",x+13,y+panelHeight-49,theme.muted(),false);
        super.render(graphics, mouseX, mouseY, partial);
    }
    @Override public void onClose() { send("CLOSE"); super.onClose(); }
    @Override public void removed()
    {
        ScreenGuiScale.set(minecraft,ScreenGuiScale.normal(minecraft));
        super.removed();
    }
    @Override public boolean isPauseScreen() { return false; }
}

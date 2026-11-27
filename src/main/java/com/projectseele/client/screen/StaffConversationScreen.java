package com.projectseele.client.screen;

import com.projectseele.world.OperationText;
import com.projectseele.world.StaffDialogueCatalogR24;
import net.minecraft.client.resources.language.I18n;
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
        super(Component.translatable("screen.projectseele.phone.command_radio")); this.view = view;
        if(!view.selectedMission().isEmpty())mission=view.selectedMission();
    }

    public static void receive(ClientboundStaffConversationPacket packet)
    {
        var mc = Minecraft.getInstance();
        if (mc.screen instanceof StaffConversationScreen screen && screen.view.session().equals(packet.session()))
        {
            if (!packet.valid())
            {
                if (mc.player != null) mc.player.displayClientMessage(StaffDialogueCatalogR24.replyComponent(packet.reply()), false);
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
        addTab(I18n.get("screen.projectseele.phone.talk"),0,x+12,tabWidth-3,()->switchTab(0),"");
        addTab(I18n.get("screen.projectseele.phone.command"),1,x+12+tabWidth,tabWidth-3,()->switchTab(1),command);
        addTab(I18n.get("screen.projectseele.phone.missions"),2,x+12+tabWidth*2,tabWidth-3,()->{switchTab(2);send("TOPIC:campaign");},"");
        addTab(I18n.get("screen.projectseele.phone.contacts"),4,x+12+tabWidth*3,tabWidth-3,()->switchTab(4),"");
        addTab(I18n.get("screen.projectseele.phone.transport"),6,x+12+tabWidth*4,tabWidth-3,()->{switchTab(6);send("TRANSPORT:status");},command);
        addButton(I18n.get("screen.projectseele.phone.close"), x + panelWidth - 60, y + 12, 48, this::onClose, "");
        int controlsY = controlsTop();
        buildingControls=true;
        int column = (panelWidth - 32) / 3;
        if (tab == 0)
        {
            String[][] topics = {{I18n.get("screen.projectseele.phone.status"), "status"}, {I18n.get("screen.projectseele.phone.directions"), "directions"}, {I18n.get("screen.projectseele.phone.pilot_sync"), "sync"},
                    {I18n.get("screen.projectseele.phone.entry_plug"), "plug"}, {I18n.get("screen.projectseele.phone.power_and_recovery"), "power"}, {I18n.get("screen.projectseele.phone.chat"), "chat"}};
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
            addButton(I18n.get("screen.projectseele.phone.prep_and_launch"),x+12,controlsY,half,()->switchTab(8),command);
            addButton(I18n.get("screen.projectseele.phone.assign_pilots"),x+16+half,controlsY,half,()->switchTab(9),denial("board"));
            addButton(I18n.get("screen.projectseele.phone.weapons_and_silos"),x+12,controlsY+22,half,()->switchTab(10),denial("weapons"));
            addButton(I18n.get("screen.projectseele.phone.raise_or_lower_city"),x+16+half,controlsY+22,half,()->{switchTab(5);send("TOPIC:city");},denial("city_rise"));
            if(view.skin().equals("fuyutsuki"))
            {
                addButton(I18n.get("screen.projectseele.dogma.open"),x+12,controlsY+44,half,()->send("DOGMA:open"),command);
                addButton(I18n.get("screen.projectseele.dogma.close"),x+16+half,controlsY+44,half,()->send("DOGMA:close"),command);
            }
        }
        else if (tab == 8)
        {
            for (int i = 0; i < 3; i++)
            {
                final int selection = i;
                addButton((unit == i ? "● " : "") + unitName(i),
                        x + 12 + i * (column + 4), controlsY, column, () -> { unit = selection; rebuildWidgets(); }, "");
            }
            String[] commands = {"整备", "发射", "回收"};
            String[] labels = {I18n.get("screen.projectseele.phone.prep_only"), I18n.get("screen.projectseele.phone.confirm_launch"), I18n.get("screen.projectseele.phone.recover")};
            for (int i = 0; i < commands.length; i++)
            {
                String action = commands[i];
                addButton(labels[i], x + 12 + i * (column + 4), controlsY + 22, column,
                        () -> send(action + " 0" + unit), denial(new String[]{"prepare","launch","recover"}[i]));
            }
            int half = (panelWidth - 28) / 2;
            addButton(I18n.get("screen.projectseele.phone.prep_surface"), x + 12, controlsY + 44, half, () -> send("OUTLET:"+unit+":surface"), denial("deploy"));
            addButton(I18n.get("screen.projectseele.phone.prep_geofront"), x + 16 + half, controlsY + 44, half,
                    () -> send("OUTLET:"+unit+":geofront"), denial("deploy"));
            addButton(I18n.get("screen.projectseele.phone.prep_hakone"), x + 12, controlsY + 66, half,
                    () -> send("OUTLET:"+unit+":hakone"), denial("deploy"));
            addButton(I18n.get("screen.projectseele.phone.cancel_queued_orders"), x + 16 + half, controlsY + 66, half, () -> send("停止操作"), "");
        }
        else if(tab==9)
        {
            selectUnit(controlsY,column);
            int half=(panelWidth-28)/2;
            addButton(I18n.get("screen.projectseele.phone.board_eva"),x+12,controlsY+22,half,()->send("BOARD:"+unit),denial("board"));
            addButton(I18n.get("screen.projectseele.phone.disembark_and_stand_by"),x+16+half,controlsY+22,half,()->send("STANDBY:"+unit),denial("board"));
            addButton(I18n.get("screen.projectseele.phone.ask_pilot_status"),x+12,controlsY+44,half,()->send("PILOT:"+unit),"");
            addButton(I18n.get("screen.projectseele.phone.chat_with_pilot"),x+16+half,controlsY+44,half,()->send("PILOTCHAT:"+unit),"");
        }
        else if(tab==10)
        {
            addButton(I18n.get("screen.projectseele.phone.deploy_nearest_rifle_silo"),x+12,controlsY,panelWidth-24,()->send("WEAPONS"),denial("weapons"));
            addButton(I18n.get("screen.projectseele.phone.deploy_unit_00_shield_silo"),x+12,controlsY+22,panelWidth-24,()->send("WEAPONS:shield"),denial("weapons"));
            addButton(I18n.get("screen.projectseele.phone.deploy_unit_02_sword_silo"),x+12,controlsY+44,panelWidth-24,()->send("WEAPONS:sword"),denial("weapons"));
        }
        else if(tab==2)
        {
            addButton(I18n.get("screen.projectseele.phone.mission_briefing"),x+12,controlsY,panelWidth-24,()->send("TOPIC:campaign"),"");
            addButton(I18n.get("screen.projectseele.phone.choose_mission_and_crew"),x+12,controlsY+22,panelWidth-24,()->switchTab(12),denial("campaign"));
            addButton(I18n.get("screen.projectseele.phone.city_coordination_file"),x+12,controlsY+44,panelWidth-24,()->{switchTab(7);send("COORD:status");},command);
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
                addButton((mission.equals(selected)?"● ":"")+I18n.get("mission.projectseele." + entry.id() + ".title"),x+12+i*(choice+4),controlsY,choice,
                        ()->{mission=selected;if(selected.equals("ramiel")){sortieCrewR54.putIfAbsent(0,"npc");String self=minecraft.player.getUUID().toString();sortieCrewR54.putIfAbsent(1,sortieCrewR54.containsValue(self)?"npc":self);}send("CAMPAIGN:select:"+selected);rebuildWidgets();},campaign);
            }
            for(int i=0;i<3;i++)
            {
                int selection=i;
                addButton(unitName(i)+"："+crewLabelR54(i)+I18n.get("screen.projectseele.phone.click_to_change"),x+12,controlsY+22+i*22,panelWidth-24,()->{cycleCrewR54(selection);rebuildWidgets();},"");
            }
            if(mission.equals("ramiel"))
                addButton(I18n.get("screen.projectseele.phone.unit_01_takes_the_cannon_unit_00_takes_the_shield"),x+12,controlsY+88,panelWidth-24,()->{},I18n.get("screen.projectseele.phone.equipment_for_the_ramiel_operation_is_fixed"));
            else addButton(I18n.get("screen.projectseele.phone.loadout")+(sortieEquipment.equals("rifle")?I18n.get("screen.projectseele.phone.rifle"):I18n.get("screen.projectseele.phone.melee"))+I18n.get("screen.projectseele.phone.click_to_change"),x+12,controlsY+88,panelWidth-24,()->{sortieEquipment=sortieEquipment.equals("rifle")?"melee":"rifle";rebuildWidgets();},"");
            addButton(I18n.get("screen.projectseele.phone.confirm_sortie"),x+12,controlsY+110,half,()->send(formationRequestR54()),
                    !campaign.isEmpty()?campaign:sortieCrewR54.isEmpty()?I18n.get("screen.projectseele.phone.assign_at_least_one_pilot_first"):"");
            addButton(I18n.get("screen.projectseele.phone.end_mission"),x+16+half,controlsY+110,half,()->send("CAMPAIGN:cancel"),campaign);
            addButton(I18n.get("screen.projectseele.phone.progress_and_formation"),x+12,controlsY+132,panelWidth-24,()->send("TOPIC:campaign"),"");
        }
        else if(tab==7)
        {
            addButton(I18n.get("screen.projectseele.phone.read_and_share_records"),x+12,controlsY,panelWidth-24,()->switchTab(13),command);
            addButton(I18n.get("screen.projectseele.phone.city_power_and_retesting"),x+12,controlsY+22,panelWidth-24,()->switchTab(14),command);
            addButton(I18n.get("screen.projectseele.phone.units_and_confirmation"),x+12,controlsY+44,panelWidth-24,()->switchTab(15),command);
        }
        else if(tab==13||tab==14)
        {
            String[][] actions=tab==13
                    ?new String[][]{{I18n.get("screen.projectseele.phone.accept_file"),"start"},{I18n.get("screen.projectseele.phone.status"),"status"},{I18n.get("screen.projectseele.phone.original_page"),"read/page"},{I18n.get("screen.projectseele.phone.annotations"),"read/annotation"},{I18n.get("screen.projectseele.phone.field_notes"),"read/field"},{I18n.get("screen.projectseele.phone.share_three_records"),"share"},{I18n.get("screen.projectseele.phone.keep_command_file"),"private"},{I18n.get("screen.projectseele.phone.revoke_dispatch"),"cancel"}}
                    :new String[][]{{I18n.get("screen.projectseele.phone.lower_city_keep_power"),"evacuate/services"},{I18n.get("screen.projectseele.phone.lower_city_store_power"),"evacuate/storage"},{I18n.get("screen.projectseele.phone.delegate_mountain_test"),"test/delegate"},{I18n.get("screen.projectseele.phone.retest_at_station"),"test/onsite"},{I18n.get("screen.projectseele.phone.keep_power_two_cycles"),"supply/services"},{I18n.get("screen.projectseele.phone.backup_feed_one_cycle"),"supply/reserve"},{I18n.get("screen.projectseele.phone.file_prep_results"),"finish"},{I18n.get("screen.projectseele.phone.status"),"status"}};
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
            addButton(I18n.get("screen.projectseele.phone.formation_unit")+com.projectseele.world.TvSortiesR32.name(unit),x+12,controlsY,half,()->{unit=(unit+1)%5;if(unit>=3)npcSortie=false;rebuildWidgets();},"");
            String driverLabel=npcSortie?I18n.get("screen.projectseele.phone.pilot")+StaffDialogueCatalogR24.pilotName(unit).getString():I18n.get("screen.projectseele.phone.player")+humanPilotName();
            addButton(driverLabel+I18n.get("screen.projectseele.phone.switch"),x+16+half,controlsY,half,()->{cycleParticipant();rebuildWidgets();},"");
            addButton(I18n.get("screen.projectseele.phone.join_formation"),x+12,controlsY+22,column,()->send("COORD:assign/"+unit+"/"+(unit<3&&npcSortie?"npc":"human/"+selectedHuman())),"");
            String archive=view.coordinationFormationRevision()>0?"":I18n.get("screen.projectseele.phone.accept_the_city_coordination_file_first");
            addButton(I18n.get("screen.projectseele.phone.acknowledge_and_stand_by"),x+16+column,controlsY+22,column,()->send("COORD:consent/"+unit+"/"+view.coordinationFormationRevision()+"/"+view.coordinationEvidenceRevision()),archive);
            addButton(I18n.get("screen.projectseele.phone.withdraw_pilot"),x+20+column*2,controlsY+22,column,()->send("COORD:withdraw/"+unit+"/"+view.coordinationFormationRevision()+"/"+view.coordinationEvidenceRevision()),archive);
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
                int selection=i;addButton((unit==i?"● ":"")+unitName(i),x+12+i*(column+4),controlsY,column,()->{unit=selection;rebuildWidgets();},"");
            }
            transportX=new PhoneUiR54.Field(font,x+12,controlsY+24,column,20,Component.translatable("screen.projectseele.phone.destination_x"),PhoneUiR54.NERV);transportY=new PhoneUiR54.Field(font,x+16+column,controlsY+24,column,20,Component.translatable("screen.projectseele.phone.destination_y"),PhoneUiR54.NERV);transportZ=new PhoneUiR54.Field(font,x+20+column*2,controlsY+24,column,20,Component.translatable("screen.projectseele.phone.destination_z"),PhoneUiR54.NERV);
            transportY.setMaxLength(10);transportY.setFilter(s->s.matches("-?\\d*"));transportY.setValue(enteredY==null?Integer.toString(feet.getY()):enteredY);addRenderableWidget(transportY);
            transportX.setHint(Component.literal("X"));transportY.setHint(Component.translatable("screen.projectseele.phone.y_ground_level"));transportZ.setHint(Component.literal("Z"));
            transportX.setMaxLength(10);transportZ.setMaxLength(10);transportX.setFilter(s->s.matches("-?\\d*"));transportZ.setFilter(s->s.matches("-?\\d*"));
            transportX.setValue(enteredX==null?Integer.toString(feet.getX()):enteredX);transportZ.setValue(enteredZ==null?Integer.toString(feet.getZ()):enteredZ);addRenderableWidget(transportX);addRenderableWidget(transportZ);
            controlRows.put(transportX,transportX.getY());controlRows.put(transportY,transportY.getY());controlRows.put(transportZ,transportZ.getY());
            addButton(I18n.get("screen.projectseele.phone.deliver_to_x_y_z"),x+12,controlsY+48,column,()->send("TRANSPORT:deliver:"+unit+":"+transportX.getValue()+":"+transportY.getValue()+":"+transportZ.getValue()),"");
            addButton(I18n.get("screen.projectseele.phone.airlift_to_hangar"),x+16+column,controlsY+48,column,()->send("TRANSPORT:recover:"+unit+(transportReturnExit==0?"":":unit"+unit+"/exit"+transportReturnExit+"/port")),"");
            addButton(I18n.get("screen.projectseele.phone.cancel_return_safely"),x+20+column*2,controlsY+48,column,()->send("TRANSPORT:cancel:"+unit),"");
            String returnPort=switch(transportReturnExit){case 1->"GeoFront";case 2->I18n.get("screen.projectseele.phone.tokyo_3");case 3->I18n.get("screen.projectseele.phone.hakone");default->I18n.get("screen.projectseele.phone.auto_route");};
            // R65: the shaft between the surface and the GeoFront, held open or let close on the caller's order. Its two
            // buttons share the fourth row with the return port and the status: a fifth row is below the page's fold.
            int quarter=(panelWidth-36)/4;
            addButton(I18n.get("screen.projectseele.phone.return_port")+returnPort,x+12,controlsY+72,quarter,()->{String tx=transportX.getValue(),ty=transportY.getValue(),tz=transportZ.getValue();transportReturnExit=(transportReturnExit+1)%4;rebuildWidgets();transportX.setValue(tx);transportY.setValue(ty);transportZ.setValue(tz);},"");
            addButton(I18n.get("screen.projectseele.phone.open_transport_shaft"),x+16+quarter,controlsY+72,quarter,()->send("TRANSPORT:shaft:open"),"");
            addButton(I18n.get("screen.projectseele.phone.close_transport_shaft"),x+20+quarter*2,controlsY+72,quarter,()->send("TRANSPORT:shaft:close"),"");
            addButton(I18n.get("screen.projectseele.phone.transport_status"),x+24+quarter*3,controlsY+72,quarter,()->send("TRANSPORT:status"),"");
        }
        else if (tab == 5)
        {
            int half=(panelWidth-28)/2;
            addButton(I18n.get("screen.projectseele.phone.raise_city"),x+12,controlsY,half,()->send("城市上升"),denial("city_rise"));
            addButton(I18n.get("screen.projectseele.phone.lower_city"),x+16+half,controlsY,half,()->send("城市下降"),denial("city_lower"));
            addButton(I18n.get("screen.projectseele.phone.check_city_status"),x+12,controlsY+22,panelWidth-24,()->send("TOPIC:city"),"");
        }
        else if (tab == 4)
        {
            String[] contacts = {"misato", "ritsuko", "fuyutsuki", "maya"};
            int half = (panelWidth - 28) / 2;
            for (int i = 0; i < contacts.length; i++)
            {
                String contact = contacts[i];
                addButton(I18n.get("hud.projectseele.chat.name." + contact), x + 12 + (i % 2) * (half + 4), controlsY + (i / 2) * 22,
                        half, () -> send("CONTACT:" + contact), "");
            }
            for (int i = 0; i < 3; i++)
            {
                int pilot = i;
                addButton(StaffDialogueCatalogR24.pilotName(i).getString(), x + 12 + i * (column + 4),
                        controlsY + 44, column, () -> { unit=pilot; send("PILOTCHAT:" + pilot); }, "");
            }
        }
        else
        {
            String[][] destinations={{I18n.get("screen.projectseele.phone.control_room_entrance"),"command"},{I18n.get("screen.projectseele.phone.hangar"),"hangars"},{I18n.get("screen.projectseele.phone.hq_station"),"station"},{I18n.get("screen.projectseele.phone.pyramid_transfer_station"),"pyramid_station"},{I18n.get("screen.projectseele.phone.launch_area_station"),"launch_station"},{I18n.get("screen.projectseele.phone.observation_corridor"),"observation"},{I18n.get("screen.projectseele.phone.terminal_dogma_lobby"),"dogma"},{I18n.get("screen.projectseele.phone.lcl_research_floor"),"experiment"},{I18n.get("screen.projectseele.phone.nearest_lift"),"nearest_lift"}};
            for(int i=0;i<destinations.length;i++)
            {
                String key=destinations[i][1];
                addButton(destinations[i][0],x+12+(i%3)*(column+4),controlsY+(i/3)*22,column,()->send("ROUTE:"+key),"");
            }
            addButton(I18n.get("screen.projectseele.phone.stop_walking_directions"),x+12,controlsY+66,panelWidth-24,()->send("ROUTE:stop"),"");
        }
        buildingControls=false;applyControlScroll();
        int parent=parentTab();
        if(parent>=0)addButton(I18n.get("screen.projectseele.phone.back_to")+(parent==0?I18n.get("screen.projectseele.phone.talk"):parent==1?I18n.get("screen.projectseele.phone.command_groups"):parent==2?I18n.get("screen.projectseele.phone.missions"):I18n.get("screen.projectseele.phone.city_coordination_file")),
                x+12,y+panelHeight-55,panelWidth-24,()->switchTab(parent),"");
        input = new PhoneUiR54.Field(font, x + 13, y + panelHeight - 28, panelWidth - 87, 19, Component.translatable("screen.projectseele.phone.enter_a_message_or_command"),PhoneUiR54.NERV);
        input.setMaxLength(160);input.setValue(draft); input.setHint(Component.translatable("screen.projectseele.phone.message_or_command_enter_to_send")); addRenderableWidget(input);
        addButton(I18n.get("screen.projectseele.phone.send"), x + panelWidth - 65, y + panelHeight - 29, 52, this::submitText, "");
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
    private int rootTab(){return switch(tab){case 3->0;case 5,8,9,10->1;case 7,12,13,14,15->2;default->tab;};}
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
        String selected=sortieCrewR54.get(slot);if(selected==null)return I18n.get("screen.projectseele.phone.standby");
        if(selected.equals("npc"))return StaffDialogueCatalogR24.pilotName(slot).getString();
        if(selected.equals(minecraft.player.getUUID().toString()))return I18n.get("screen.projectseele.phone.me");
        var player=minecraft.getConnection().getPlayerInfo(UUID.fromString(selected));
        return player==null?I18n.get("screen.projectseele.phone.offline_player"):player.getProfile().getName();
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
        if(humanPilot==null||humanPilot.equals(minecraft.player.getUUID()))return I18n.get("screen.projectseele.phone.me");
        var player=minecraft.getConnection().getPlayerInfo(humanPilot);return player==null?I18n.get("screen.projectseele.phone.offline_player"):player.getProfile().getName();
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
            addButton((unit==i?"● ":"")+unitName(i),
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
            case 5,8,9,10 -> 1;
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
        return allowed?"":StaffAuthorityR25.denialText(view.authorized(),view.skin(),action).getString();
    }
    private int controlsTop()
    {
        int rows=switch(tab)
        {
            case 12 -> 6;
            case 3,6,8,13,14 -> 4;
            case 2,4,7,9,10 -> 3;
            case 1 -> 2;
            default -> 2;
        };
        return y+Math.max(Math.max(142,Math.min(170,panelHeight-120)),panelHeight-(rows*22+76));
    }
    private static String unitName(int unit)
    {
        return OperationText.unit(unit).getString();
    }

    private static String unitStatus(String row)
    {
        if (!row.startsWith("unit:")) return row;
        String[] parts = row.split(":", -1);
        if (parts.length != 4 || !parts[1].matches("[0-2]")) return row;
        String phase = "hud.projectseele.phase." + parts[2].toLowerCase(java.util.Locale.ROOT);
        return I18n.get("1".equals(parts[3]) ? "hud.projectseele.chat.unit_status" : "hud.projectseele.chat.unit_unloaded",
                unitName(Integer.parseInt(parts[1])), I18n.get(I18n.exists(phase) ? phase : "hud.projectseele.phase.unknown"));
    }

    private static String orderText(String row)
    {
        String[] fields = row.split(":", 3);
        if (fields.length != 3 || !fields[0].equals("order") || !fields[1].matches("[0-2]")) return row;
        return unitName(Integer.parseInt(fields[1])) + " · " + OperationText.read(fields[2]).getString();
    }

    private static String participantText(String row)
    {
        String[] fields = row.split(":", 6);
        if (fields.length < 2 || !fields[0].equals("crew") || !fields[1].matches("[0-4]")) return row;
        int unit = Integer.parseInt(fields[1]);
        if (fields.length == 2) return I18n.get("ops.projectseele.formation.unassigned", unitName(unit));
        if (fields.length != 6) return row;
        String role = switch (fields[2])
        {
            case "cover" -> "ops.projectseele.formation.cover";
            case "shooter" -> "ops.projectseele.formation.shooter";
            default -> "ops.projectseele.formation.support";
        };
        String name = switch (fields[4])
        {
            case "npc" -> StaffDialogueCatalogR24.pilotName(unit).getString();
            case "offline" -> I18n.get("ops.projectseele.formation.offline");
            default -> fields[5];
        };
        String confirmation = I18n.get(fields[3].equals("1") ? "ops.projectseele.formation.confirmed" : "ops.projectseele.formation.pending");
        return I18n.get("ops.projectseele.formation.row", unitName(unit), name, I18n.get(role), confirmation);
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
        PhoneUiR54.frame(graphics,font,theme,x,y,panelWidth,panelHeight,I18n.get("screen.projectseele.phone.command_radio"),
                StaffDialogueCatalogR24.speaker(view.name()).getString()+"  ·  "+(I18n.exists(view.role())?I18n.get(view.role()):view.role())+I18n.get("screen.projectseele.phone.radio_channel"));
        int bottom=controlsTop()-28;replyTop=y+99;
        PhoneUiR54.card(graphics,font,theme,x+8,y+78,panelWidth-16,bottom-(y+78)+4,
                tab==2||tab==12?I18n.get("screen.projectseele.phone.mission_briefing"):I18n.get("screen.projectseele.phone.status_and_replies"),view.canCommand()?I18n.get("screen.projectseele.phone.command_access"):I18n.get("screen.projectseele.phone.talk_access"));
        var transcript=new StringBuilder();
        if(tab<2&&!view.units().isEmpty())transcript.append(I18n.get("screen.projectseele.phone.unit_status_n")).append(String.join("\n",view.units().stream().map(StaffConversationScreen::unitStatus).toList())).append("\n\n");
        else if(tab==15&&view.participants().size()>unit)transcript.append(I18n.get("screen.projectseele.phone.current_formation_n")).append(participantText(view.participants().get(unit))).append("\n\n");
        if(!view.order().isBlank())transcript.append(I18n.get("screen.projectseele.phone.current_orders_n")).append(view.order().equals("staff.projectseele.information_only") ? I18n.get(view.order(), denial(StaffAuthorityR25.COMMAND)) : orderText(view.order())).append("\n\n");
        if(tab!=2&&tab!=12)transcript.append(I18n.get("screen.projectseele.phone.reply_n"));
        transcript.append(StaffDialogueCatalogR24.replyComponent(view.reply()).getString());
        replyScroll=PhoneUiR54.text(graphics,font,theme,transcript.toString(),x+16,replyTop,panelWidth-32,
                Math.max(0,bottom-replyTop),replyScroll);
        String section=switch(tab){case 0->I18n.get("screen.projectseele.phone.topics");case 1->I18n.get("screen.projectseele.phone.command_groups");case 2->I18n.get("screen.projectseele.phone.operations");case 3->I18n.get("screen.projectseele.phone.walking_directions");case 4->I18n.get("screen.projectseele.phone.contacts");case 5->I18n.get("screen.projectseele.phone.raise_or_lower_city");case 6->I18n.get("screen.projectseele.phone.transport_destination_x_y_z");case 7->I18n.get("screen.projectseele.phone.city_coordination_file");case 8->I18n.get("screen.projectseele.phone.prep_and_launch");case 9->I18n.get("screen.projectseele.phone.assign_pilots");case 10->I18n.get("screen.projectseele.phone.weapons_and_silos");case 12->I18n.get("screen.projectseele.phone.mission_and_sortie_crew");case 13->I18n.get("screen.projectseele.phone.read_and_share_records");case 14->I18n.get("screen.projectseele.phone.city_power_and_retesting");case 15->I18n.get("screen.projectseele.phone.units_and_confirmation");default->I18n.get("screen.projectseele.phone.actions");};
        String meta=pageDenials.isEmpty()?"":pageDenials.size()==1?I18n.get("screen.projectseele.phone.disabled")+pageDenials.iterator().next():I18n.get("screen.projectseele.phone.hover_over_a_disabled_action_for_details");
        if(controlsScrollMax>0)meta=meta.isEmpty()?I18n.get("screen.projectseele.phone.scroll_for_more"):meta+I18n.get("screen.projectseele.phone.scroll_for_more_inline");
        PhoneUiR54.card(graphics,font,theme,x+8,controlsTop()-21,panelWidth-16,
                controlsBottom()-controlsTop()+24,section,meta);
        PhoneUiR54.scrollbar(graphics,theme,x+panelWidth-10,controlsTop(),controlsBottom()-controlsTop(),
                controlsBottom()-controlsTop()+controlsScrollMax,controlsBottom()-controlsTop(),controlsScroll);
        graphics.fill(x+12,y+panelHeight-34,x+panelWidth-12,y+panelHeight-33,theme.border());
        if(parentTab()<0)graphics.drawString(font,I18n.get("screen.projectseele.phone.message_or_command_enter_to_send_inline"),x+13,y+panelHeight-49,theme.muted(),false);
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

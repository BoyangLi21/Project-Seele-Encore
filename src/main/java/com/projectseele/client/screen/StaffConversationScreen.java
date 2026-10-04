package com.projectseele.client.screen;

import com.projectseele.network.*;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;
import java.util.*;

/** A non-pausing command channel: visible state comes from the server. */
public final class StaffConversationScreen extends Screen
{
    private ClientboundStaffConversationPacket view;
    private EditBox input;
    private EditBox transportX,transportZ;
    private String mission="sachiel";
    private boolean npcSortie,sortieRifle=true;
    private int x, y, panelWidth, panelHeight, tab, unit = 1, age, savedScale = -1, replyScroll, replyTop;
    private boolean restoring;
    private UUID humanPilot;

    private StaffConversationScreen(ClientboundStaffConversationPacket view)
    {
        super(Component.literal("NERV 通信")); this.view = view;
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
                    ||screen.view.coordinationFormationRevision()!=packet.coordinationFormationRevision()
                    ||screen.view.coordinationEvidenceRevision()!=packet.coordinationEvidenceRevision();
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
            { replacement.unit = old.unit; replacement.tab = packet.canCommand() ? old.tab : 0;replacement.mission=old.mission;replacement.npcSortie=old.npcSortie;replacement.sortieRifle=old.sortieRifle; }
            mc.setScreen(replacement);
            mc.getSoundManager().play(net.minecraft.client.resources.sounds.SimpleSoundInstance.forUI(com.projectseele.registry.ModSounds.STAFF_RADIO_CONNECT.get(),1,.4F));
        }
    }
    public ClientboundStaffConversationPacket snapshot() { return view; }

    @Override protected void init()
    {
        if ((width < 430 || height < 300) && savedScale < 0 && minecraft.options.guiScale().get() != 1)
        {
            savedScale = minecraft.options.guiScale().get(); minecraft.options.guiScale().set(2);
            minecraft.resizeDisplay(); return;
        }
        panelWidth = Math.min(560, width - 16); panelHeight = Math.min(320, height - 16);
        x = (width - panelWidth) / 2; y = (height - panelHeight) / 2;
        int tabWidth=(panelWidth-24)/6;
        addButton("交谈",x+12,y+29,tabWidth-3,()->switchTab(0),true);
        addButton("指挥",x+12+tabWidth,y+29,tabWidth-3,()->switchTab(1),view.canCommand());
        addButton("作战记录",x+12+tabWidth*2,y+29,tabWidth-3,()->{switchTab(2);send("TOPIC:campaign");},true);
        addButton("通讯录",x+12+tabWidth*3,y+29,tabWidth-3,()->switchTab(4),view.radio());
        addButton("运输部门",x+12+tabWidth*4,y+29,tabWidth-3,()->{switchTab(6);send("TRANSPORT:status");},view.canCommand());
        if(view.skin().equals("fuyutsuki"))addButton("城市",x+12+tabWidth*5,y+29,tabWidth-3,()->switchTab(5),permitted("city_rise"));
        addButton("关闭", x + panelWidth - 60, y + 8, 48, this::onClose, true);
        int controlsY = controlsTop();
        int column = (panelWidth - 32) / 3;
        if (tab == 0)
        {
            String[][] topics = {{"当前状态", "status"}, {"道路指引", "directions"}, {"同步与驾驶", "sync"},
                    {"插入栓接入", "plug"}, {"供电与回收", "power"}, {"值班闲聊", "duty"}};
            for (int i = 0; i < topics.length; i++)
            {
                String request = "TOPIC:" + topics[i][1];
                addButton(topics[i][0], x + 12 + (i % 3) * (column + 4), controlsY + (i / 3) * 22,
                        column, () -> { if(request.equals("TOPIC:directions"))switchTab(3);send(request); }, true);
            }
            if (view.radio())
            {
                String[] contacts = {"美里", "律子", "冬月"};
                for (int i = 0; i < contacts.length; i++)
                {
                    String person = contacts[i];
                    addButton("联络" + person, x + 12 + i * (column + 4), controlsY + 44,
                            column, () -> send("CONTACT:" + person), true);
                }
            }
        }
        else if (tab == 1)
        {
            for (int i = 0; i < 3; i++)
            {
                final int selection = i;
                addButton((unit == i ? "● " : "") + com.projectseele.world.NervStaffDialogue.unitName(i),
                        x + 12 + i * (column + 4), controlsY, column, () -> { unit = selection; rebuildWidgets(); }, true);
            }
            String[] commands = {"整备", "发射", "回收"};
            for (int i = 0; i < commands.length; i++)
            {
                String action = commands[i];
                addButton(action, x + 12 + i * (column + 4), controlsY + 22, column,
                        () -> send(action + " 0" + unit), permitted(new String[]{"prepare","launch","recover"}[i]));
            }
            int half = (panelWidth - 28) / 2;
            addButton("整备后发射", x + 12, controlsY + 44, half, () -> send("整备后发射 0" + unit), permitted("deploy"));
            addButton("取消后续操作", x + 16 + half, controlsY + 44, half, () -> send("停止操作"), true);
            addButton("驾驶员登机", x + 12, controlsY + 66, column, () -> send("BOARD:" + unit), permitted("board"));
            addButton("下机返回待命", x + 16 + column, controlsY + 66, column, () -> send("STANDBY:" + unit), permitted("board"));
            addButton("部署武器井", x + 20 + column*2, controlsY + 66, column, () -> send("WEAPONS"), permitted("weapons"));
        }
        else if(tab==2)
        {
            int half = (panelWidth - 28) / 2;
            addButton((mission.equals("sachiel")?"● ":"")+"萨基尔",x+12,controlsY,half,()->{mission="sachiel";send("CAMPAIGN:select:sachiel");rebuildWidgets();},permitted("campaign"));
            addButton((mission.equals("shamshel")?"● ":"")+"夏姆榭尔",x+16+half,controlsY,half,()->{mission="shamshel";send("CAMPAIGN:select:shamshel");rebuildWidgets();},permitted("campaign"));
            for(int i=0;i<3;i++){int selection=i;addButton((unit==i?"● ":"")+com.projectseele.world.NervStaffDialogue.unitName(i),x+12+i*(column+4),controlsY+22,column,()->{unit=selection;rebuildWidgets();},true);}
            addButton((!npcSortie?"● ":"")+"亲自驾驶",x+12,controlsY+44,half,()->{npcSortie=false;rebuildWidgets();},true);
            addButton((npcSortie?"● ":"")+com.projectseele.entity.TrainingPilotEntity.pilotName(unit)+"出战",x+16+half,controlsY+44,half,()->{npcSortie=true;rebuildWidgets();},true);
            addButton("驾驶员装备："+(sortieRifle?"先前往武器井取枪":"近战出击"),x+12,controlsY+66,panelWidth-24,()->{sortieRifle=!sortieRifle;rebuildWidgets();},npcSortie);
            addButton("出击 / 加入增援",x+12,controlsY+88,half,()->send("CAMPAIGN:sortie:"+mission+":"+unit+":"+(npcSortie?"npc":"human")+":"+(sortieRifle?"rifle":"melee")),permitted("campaign"));
            addButton("撤销当前作战",x+16+half,controlsY+88,half,()->send("CAMPAIGN:cancel"),permitted("campaign"));
            addButton("查看所选简报",x+12,controlsY+110,half,()->send("TOPIC:campaign"),true);
            addButton("城市协同档案",x+16+half,controlsY+110,half,()->{switchTab(7);send("COORD:status");},view.canCommand());
        }
        else if(tab==7)
        {
            String[][] actions={{"接受档案","start"},{"当前状态","status"},{"撤销调度","cancel"},
                    {"原页","read/page"},{"译注","read/annotation"},{"现场记录","read/field"},
                    {"共享三份记录","share"},{"保留司令档案","private"},{"城市收纳 · 保电","evacuate/services"},
                    {"城市收纳 · 蓄能","evacuate/storage"},{"委派远山复测","test/delegate"},{"亲自到站复测","test/onsite"},
                    {"保电 · 等两轮","supply/services"},{"备用馈线 · 一轮","supply/reserve"},{"归档准备结果","finish"}};
            for(int i=0;i<actions.length;i++){String action=actions[i][1];addButton(actions[i][0],x+12+(i%3)*(column+4),controlsY+(i/3)*22,column,()->send("COORD:"+action),view.canCommand());}
            int half=(panelWidth-28)/2;
            addButton("编成机体："+com.projectseele.world.TvSortiesR32.name(unit),x+12,controlsY+110,half,()->{unit=(unit+1)%5;if(unit>=3)npcSortie=false;rebuildWidgets();},true);
            String driverLabel=npcSortie?"驾驶员："+com.projectseele.entity.TrainingPilotEntity.pilotName(unit):"驾驶者："+humanPilotName();
            addButton(driverLabel+" / 切换",x+16+half,controlsY+110,half,()->{cycleParticipant();rebuildWidgets();},true);
            addButton("加入编成",x+12,controlsY+132,column,()->send("COORD:assign/"+unit+"/"+(unit<3&&npcSortie?"npc":"human/"+selectedHuman())),true);
            addButton("确认说明与待命",x+16+column,controlsY+132,column,()->send("COORD:consent/"+unit+"/"+view.coordinationFormationRevision()+"/"+view.coordinationEvidenceRevision()),view.coordinationFormationRevision()>0);
            addButton("驾驶员撤回",x+20+column*2,controlsY+132,column,()->send("COORD:withdraw/"+unit+"/"+view.coordinationFormationRevision()+"/"+view.coordinationEvidenceRevision()),view.coordinationFormationRevision()>0);
        }
        else if(tab==6)
        {
            for(int i=0;i<3;i++)
            {
                int selection=i;addButton((unit==i?"● ":"")+com.projectseele.world.NervStaffDialogue.unitName(i),x+12+i*(column+4),controlsY,column,()->{unit=selection;rebuildWidgets();},true);
            }
            int half=(panelWidth-28)/2;
            transportX=new EditBox(font,x+12,controlsY+24,half,20,Component.literal("目的地 X"));transportZ=new EditBox(font,x+16+half,controlsY+24,half,20,Component.literal("目的地 Z"));
            transportX.setMaxLength(10);transportZ.setMaxLength(10);transportX.setFilter(s->s.matches("-?\\d*"));transportZ.setFilter(s->s.matches("-?\\d*"));
            transportX.setValue(Integer.toString(minecraft.player.getBlockX()));transportZ.setValue(Integer.toString(minecraft.player.getBlockZ()));addRenderableWidget(transportX);addRenderableWidget(transportZ);
            addButton("投放至 X / Z",x+12,controlsY+48,column,()->send("TRANSPORT:deliver:"+unit+":"+transportX.getValue()+":"+transportZ.getValue()),true);
            addButton("空运回原发射井",x+16+column,controlsY+48,column,()->send("TRANSPORT:recover:"+unit),true);
            addButton("取消 / 安全返回",x+20+column*2,controlsY+48,column,()->send("TRANSPORT:cancel"),true);
            addButton("运输状态",x+12,controlsY+72,panelWidth-24,()->send("TRANSPORT:status"),true);
        }
        else if (tab == 5)
        {
            int half=(panelWidth-28)/2;
            addButton("城市升起",x+12,controlsY,half,()->send("城市升起"),permitted("city_rise"));
            addButton("城市降下",x+16+half,controlsY,half,()->send("城市降下"),permitted("city_lower"));
            addButton("查询城市状态",x+12,controlsY+22,panelWidth-24,()->send("TOPIC:city"),true);
        }
        else if (tab == 4)
        {
            String[] contacts = {"美里", "律子", "冬月", "摩耶"};
            int half = (panelWidth - 28) / 2;
            for (int i = 0; i < contacts.length; i++)
            {
                String contact = contacts[i];
                addButton(contact, x + 12 + (i % 2) * (half + 4), controlsY + (i / 2) * 22,
                        half, () -> send("CONTACT:" + contact), true);
            }
            for (int i = 0; i < 3; i++)
            {
                int pilot = i;
                addButton(com.projectseele.entity.TrainingPilotEntity.pilotName(i), x + 12 + i * (column + 4),
                        controlsY + 44, column, () -> { unit=pilot; send("PILOT:" + pilot); }, true);
            }
        }
        else
        {
            String[][] destinations={{"指挥室入口","command"},{"机库","hangars"},{"总部火车站","station"},{"金字塔接驳站","pyramid_station"},{"发射区车站","launch_station"},{"观景走廊","observation"},{"终极教条前厅","dogma"}};
            for(int i=0;i<destinations.length;i++)
            {
                String key=destinations[i][1];
                addButton(destinations[i][0],x+12+(i%3)*(column+4),controlsY+(i/3)*22,column,()->send("ROUTE:"+key),true);
            }
            addButton("停止步行引导",x+12,controlsY+66,panelWidth-24,()->send("ROUTE:stop"),true);
        }
        input = new EditBox(font, x + 12, y + panelHeight - 21, panelWidth - 83, 17, Component.literal("输入交谈或指令"));
        input.setMaxLength(160); input.setHint(Component.literal("例如：初号机准备后发射")); addRenderableWidget(input);
        addButton("发送", x + panelWidth - 64, y + panelHeight - 22, 52, this::submitText, true);
    }

    private void addButton(String title, int left, int top, int width, Runnable action, boolean enabled)
    {
        var button = new ChannelButton(left, top, width, Component.literal(title), action);
        button.active = enabled; addRenderableWidget(button);
    }
    private static final class ChannelButton extends Button
    {
        ChannelButton(int x, int y, int width, Component title, Runnable action)
        { super(x, y, width, 18, title, ignored -> action.run(), DEFAULT_NARRATION); }
        @Override protected void renderWidget(GuiGraphics graphics, int mouseX, int mouseY, float partial)
        {
            boolean focused = active && isHoveredOrFocused();
            graphics.fill(getX(), getY(), getX() + width, getY() + height, focused ? 0xFF40584B : 0xFF203A32);
            graphics.fill(getX(), getY() + height - 1, getX() + width, getY() + height, focused ? 0xFFE2BB67 : 0xFF527867);
            graphics.drawCenteredString(Minecraft.getInstance().font, getMessage(), getX() + width / 2, getY() + 5,
                    active ? focused ? 0xFFEFD18E : 0xFFD5E7D8 : 0xFF738178);
        }
    }
    private UUID selectedHuman(){return humanPilot!=null?humanPilot:minecraft.player.getUUID();}
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
    private void switchTab(int next) { tab = next; rebuildWidgets(); }
    private boolean permitted(String action)
    { return view.canCommand() && com.projectseele.world.StaffAuthorityR25.allows("", view.skin(), action); }
    private int controlsTop(){return y+panelHeight-(tab==7?179:tab==2?157:tab==3||tab==1||tab==6?113:91);}
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
        if (mouseX >= x && mouseX < x + panelWidth && mouseY >= replyTop && mouseY < controlsTop()-6)
        { replyScroll = Math.max(0, replyScroll - (int) Math.signum(delta) * 2); return true; }
        return super.mouseScrolled(mouseX, mouseY, delta);
    }
    @Override public void render(GuiGraphics graphics, int mouseX, int mouseY, float partial)
    {
        renderBackground(graphics);
        graphics.fill(x, y, x + panelWidth, y + panelHeight, 0xF010211F);
        graphics.fill(x, y, x + panelWidth, y + 2, 0xFFE2BB67);
        graphics.fill(x + 8, y + 53, x + panelWidth - 8, y + 54, 0xFF446058);
        graphics.drawString(font, view.name() + "  /  " + view.role(), x + 12, y + 10, 0xFFE6DEC1, false);
        int rowY = y + 60;
        if(tab<2)
            for (String row : view.units())
            { graphics.drawString(font, row, x + 12, rowY, 0xFF92C9AE, false); rowY += 11; }
        else
        {graphics.drawString(font,tab==7&&view.participants().size()>unit?view.participants().get(unit):view.radio()?"指挥频道在线":"岗位通信在线",x+12,rowY,0xFF92C9AE,false);rowY+=11;}
        if (!view.order().isBlank())
        { graphics.drawString(font, font.plainSubstrByWidth(view.order(), panelWidth - 24), x + 12, rowY + 2, 0xFFE2BB67, false); rowY += 15; }
        int bottom = controlsTop()-6;
        replyTop = rowY + 6;
        var lines = font.split(Component.literal(view.reply()), panelWidth - 34);
        int visibleLines = Math.max(1, (bottom - replyTop) / 10);
        replyScroll = Math.min(replyScroll, Math.max(0, lines.size() - visibleLines));
        graphics.enableScissor(x + 10, rowY + 5, x + panelWidth - 10, bottom);
        for (int i = replyScroll; i < Math.min(lines.size(), replyScroll + visibleLines); i++)
            graphics.drawString(font, lines.get(i), x + 12, replyTop + (i - replyScroll) * 10, 0xFFEBEADF, false);
        graphics.disableScissor();
        if (lines.size() > visibleLines) graphics.drawString(font, "↕", x + panelWidth - 18, replyTop, 0xFFE2BB67, false);
        super.render(graphics, mouseX, mouseY, partial);
    }
    @Override public void onClose() { send("CLOSE"); super.onClose(); }
    @Override public void removed()
    {
        if (savedScale >= 0 && !restoring)
        {
            restoring = true; minecraft.options.guiScale().set(savedScale); minecraft.resizeDisplay();
        }
        super.removed();
    }
    @Override public boolean isPauseScreen() { return false; }
}

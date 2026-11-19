package com.projectseele.client.screen;

import com.projectseele.world.OperationText;
import net.minecraft.client.resources.language.I18n;
import com.projectseele.network.*;
import java.util.*;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.*;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;

public final class UNPhoneScreen extends Screen
{
    private ClientboundUNStatusPacket view;
    private int serial,age,x,y,w,h,statusScroll,replyScroll,actionScroll,actionScrollMax;
    private EditBox targetX,targetZ;
    private final Map<AbstractWidget,Integer> actionRows=new LinkedHashMap<>();
    private UNPhoneScreen(ClientboundUNStatusPacket view){super(Component.translatable("screen.projectseele.un.un_command_radio"));this.view=view;}
    public static void receive(ClientboundUNStatusPacket packet)
    {
        var mc=Minecraft.getInstance();
        if(mc.screen instanceof UNPhoneScreen screen)
        {
            if(!packet.reply().isEmpty()&&!packet.reply().equals(screen.view.reply()))screen.replyScroll=0;
            screen.view=new ClientboundUNStatusPacket(false,packet.unit00(),packet.unit01(),packet.reply().isEmpty()?screen.view.reply():packet.reply());
        }
        else if(packet.open())mc.setScreen(new UNPhoneScreen(packet));
        else if(!packet.reply().isEmpty()&&mc.player!=null)mc.player.sendSystemMessage(OperationText.read(packet.reply()));
    }
    private void button(String label,int xx,int yy,int width,Runnable action)
    {
        var button=new PhoneUiR54.Action(xx,yy,width,20,label,action,PhoneUiR54.UN,()->false);
        addRenderableWidget(button);actionRows.put(button,yy);
    }
    private int columnWidth(){return (w-36)/2;}
    private int right(){return x+24+columnWidth();}
    private int actionsTop(){return y+142;}
    private int actionsBottom(){return y+h-17;}
    private int statusHeight(){return Math.max(54,(h-98)*52/100);}
    @Override protected void init()
    {
        var window=minecraft.getWindow();
        int fitScale=StaffConversationScreen.readableGuiScale(ScreenGuiScale.normal(minecraft),window.getWidth(),window.getHeight(),minecraft.isEnforceUnicode());
        // resize() comes back here with the new scale already set, and builds the widgets.
        if(ScreenGuiScale.set(minecraft,fitScale)){resize(minecraft,window.getGuiScaledWidth(),window.getGuiScaledHeight());return;}
        String oldX=targetX==null?Integer.toString(minecraft.player.getBlockX()):targetX.getValue();
        String oldZ=targetZ==null?Integer.toString(minecraft.player.getBlockZ()):targetZ.getValue();
        w=Math.min(640,width-16);h=Math.min(410,height-16);x=(width-w)/2;y=(height-h)/2;actionRows.clear();
        int tabWidth=(w-28)/2;
        addRenderableWidget(new PhoneUiR54.Action(x+12,y+50,tabWidth,21,com.projectseele.entity.Unit03SourceRigR53.displayName(0),()->{serial=0;statusScroll=0;},PhoneUiR54.UN,()->serial==0));
        addRenderableWidget(new PhoneUiR54.Action(x+16+tabWidth,y+50,tabWidth,21,com.projectseele.entity.Unit03SourceRigR53.displayName(1),()->{serial=1;statusScroll=0;},PhoneUiR54.UN,()->serial==1));
        addRenderableWidget(new PhoneUiR54.Action(x+w-60,y+12,48,20,I18n.get("screen.projectseele.un.close"),this::onClose,PhoneUiR54.UN,()->false));
        int col=columnWidth(),rx=right(),half=(col-12)/2;
        targetX=new PhoneUiR54.Field(font,rx+3,y+113,half,20,Component.translatable("screen.projectseele.un.drop_x"),PhoneUiR54.UN);
        targetZ=new PhoneUiR54.Field(font,rx+9+half,y+113,half,20,Component.translatable("screen.projectseele.un.drop_z"),PhoneUiR54.UN);
        targetX.setMaxLength(10);targetZ.setMaxLength(10);targetX.setValue(oldX);targetZ.setValue(oldZ);
        targetX.setHint(Component.translatable("screen.projectseele.un.x_coordinate"));targetZ.setHint(Component.translatable("screen.projectseele.un.z_coordinate"));
        targetX.setTooltip(Tooltip.create(Component.translatable("screen.projectseele.un.destination_x_coordinate")));targetZ.setTooltip(Tooltip.create(Component.translatable("screen.projectseele.un.destination_z_coordinate")));
        addRenderableWidget(targetX);addRenderableWidget(targetZ);
        int at=actionsTop();
        button(I18n.get("screen.projectseele.un.deliver_to_coordinates"),rx+2,at,half,()->send("deliver"));
        button(I18n.get("screen.projectseele.un.use_my_position"),rx+8+half,at,half,()->{targetX.setValue(Integer.toString(minecraft.player.getBlockX()));targetZ.setValue(Integer.toString(minecraft.player.getBlockZ()));});
        button(I18n.get("screen.projectseele.un.airlift_back_to_base"),rx+2,at+24,half,()->send("recover"));button(I18n.get("screen.projectseele.un.cancel_return_safely"),rx+8+half,at+24,half,()->send("cancel"));
        int third=(col-16)/3;
        button(I18n.get("screen.projectseele.un.drain_hangar"),rx+2,at+48,third,()->send("drain"));button(I18n.get("screen.projectseele.un.hangar_doors"),rx+8+third,at+48,third,()->send("door"));button(I18n.get("screen.projectseele.un.fill_hangar"),rx+14+third*2,at+48,third,()->send("fill"));
        button(I18n.get("screen.projectseele.un.access_cockpit"),rx+2,at+72,half,()->send("board"));button(I18n.get("screen.projectseele.un.refresh_status"),rx+8+half,at+72,half,()->send("status"));
        button(I18n.get("screen.projectseele.un.return_platform_to_hangar"),rx+2,at+96,col-4,()->send("dock"));applyActionScroll();
    }
    private void applyActionScroll()
    {
        actionScrollMax=Math.max(0,actionsTop()+116-actionsBottom());actionScroll=Math.max(0,Math.min(actionScroll,actionScrollMax));
        for(var row:actionRows.entrySet())
        {
            var widget=row.getKey();widget.setY(row.getValue()-actionScroll);
            widget.visible=widget.getY()>=actionsTop()&&widget.getY()+widget.getHeight()<=actionsBottom();
            if(!widget.visible&&widget.isFocused())widget.setFocused(false);
        }
    }
    private void send(String action)
    {
        try{SeeleNetwork.CHANNEL.sendToServer(new ServerboundUNCommandPacket(action,serial,action.equals("deliver")?Integer.parseInt(targetX.getValue().strip()):0,action.equals("deliver")?Integer.parseInt(targetZ.getValue().strip()):0));}
        catch(NumberFormatException error){view=new ClientboundUNStatusPacket(false,view.unit00(),view.unit01(),I18n.get("screen.projectseele.un.enter_whole_numbers_for_x_and_z_the_surface_clearance_check_determines_the_height"));replyScroll=0;}
    }
    @Override public void tick(){super.tick();if(targetX!=null)targetX.tick();if(targetZ!=null)targetZ.tick();if(++age%20==0)send("status");}
    @Override public boolean isPauseScreen(){return false;}
    @Override public boolean mouseScrolled(double mx,double my,double delta)
    {
        if(mx>=right()&&mx<x+w-10&&my>=actionsTop()&&my<actionsBottom())
        {actionScroll-=(int)Math.signum(delta)*24;applyActionScroll();return true;}
        if(mx>=x+10&&mx<right()-10&&my>=y+82&&my<y+h-12)
        {if(my<y+82+statusHeight())statusScroll=Math.max(0,statusScroll-(int)Math.signum(delta)*2);else replyScroll=Math.max(0,replyScroll-(int)Math.signum(delta)*2);return true;}
        return super.mouseScrolled(mx,my,delta);
    }
    @Override public void removed()
    {
        ScreenGuiScale.set(minecraft,ScreenGuiScale.normal(minecraft));
        super.removed();
    }
    @Override public void render(GuiGraphics g,int mx,int my,float partial)
    {
        renderBackground(g);var theme=PhoneUiR54.UN;int col=columnWidth(),rx=right();
        PhoneUiR54.frame(g,font,theme,x,y,w,h,I18n.get("screen.projectseele.un.un_command_radio"),I18n.get("screen.projectseele.un.un_base_airlift_and_hangar_control"));
        int statusH=statusHeight(),replyY=y+90+statusH,replyH=y+h-12-replyY;
        PhoneUiR54.card(g,font,theme,x+10,y+82,col,statusH,I18n.get("screen.projectseele.un.unit_status"),"");
        statusScroll=PhoneUiR54.text(g,font,theme,OperationText.read(serial==0?view.unit00():view.unit01()).getString(),x+18,y+104,col-16,statusH-27,statusScroll);
        PhoneUiR54.card(g,font,theme,x+10,replyY,col,replyH,I18n.get("screen.projectseele.un.radio_reply"),"");
        String reply=view.reply().isBlank()?I18n.get("screen.projectseele.un.no_reply_yet_server_replies_appear_here"):OperationText.read(view.reply()).getString();
        replyScroll=PhoneUiR54.text(g,font,theme,reply,x+18,replyY+23,col-16,Math.max(0,replyH-29),replyScroll);
        PhoneUiR54.card(g,font,theme,rx-4,y+82,col+8,h-94,I18n.get("screen.projectseele.un.transport_controls"),actionScrollMax>0?I18n.get("screen.projectseele.un.scroll_for_more"):"");
        g.drawString(font,I18n.get("screen.projectseele.un.destination_x"),rx+3,y+101,theme.muted(),false);
        g.drawString(font,I18n.get("screen.projectseele.un.destination_z"),rx+9+(col-12)/2,y+101,theme.muted(),false);
        PhoneUiR54.scrollbar(g,theme,x+w-9,actionsTop(),actionsBottom()-actionsTop(),116,actionsBottom()-actionsTop(),actionScroll);
        super.render(g,mx,my,partial);
    }
}
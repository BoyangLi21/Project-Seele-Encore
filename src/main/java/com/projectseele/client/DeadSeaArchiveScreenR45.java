package com.projectseele.client;

import com.google.gson.*;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

/** Read-only translated dossier. Mission choice remains in the command system. */
public final class DeadSeaArchiveScreenR45 extends Screen
{
    private static final ResourceLocation TEXTURE=new ResourceLocation("projectseele","textures/block/dead_sea_archive_r45.png");
    private JsonArray pages;private int page;private int left,top,panelWidth,panelHeight;
    private java.util.UUID readNonce;private String serverRevision="",localRevision="";private Button markRead;
    private DeadSeaArchiveScreenR45(){super(Component.literal("死海文书"));}
    public static void open(){Minecraft.getInstance().setScreen(new DeadSeaArchiveScreenR45());}
    public int pageIndex(){return page;}
    public static void attachReadChallenge(java.util.UUID nonce,String revision,int pages)
    {
        if(Minecraft.getInstance().screen instanceof DeadSeaArchiveScreenR45 screen&&screen.pages!=null&&screen.pages.size()==pages)
        {screen.readNonce=nonce;screen.serverRevision=revision;if(screen.markRead!=null)screen.markRead.active=revision.equals(screen.localRevision);}
    }

    @Override protected void init()
    {
        try(var stream=minecraft.getResourceManager().open(new ResourceLocation("projectseele","lore/dead_sea_archive_r45.json")))
        {byte[] bytes=stream.readAllBytes();localRevision=com.projectseele.world.DeadSeaReadingR45.hash(bytes);pages=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject().getAsJsonArray("pages");}
        catch(Exception error){throw new IllegalStateException("Archive pages unavailable",error);}
        panelWidth=Math.min(440,width-28);panelHeight=Math.min(292,height-40);left=(width-panelWidth)/2;top=(height-panelHeight)/2;
        addRenderableWidget(Button.builder(Component.literal("上一页"),b->page=Math.max(0,page-1)).bounds(left+14,top+panelHeight-24,66,20).build());
        addRenderableWidget(Button.builder(Component.literal("下一页"),b->page=Math.min(pages.size()-1,page+1)).bounds(left+panelWidth-80,top+panelHeight-24,66,20).build());
        markRead=addRenderableWidget(Button.builder(Component.literal("记为已阅"),b->{if(readNonce!=null&&serverRevision.equals(localRevision))
            com.projectseele.network.SeeleNetwork.CHANNEL.sendToServer(new com.projectseele.network.ServerboundDeadSeaReadPageR45(readNonce,page,localRevision));})
            .bounds(left+panelWidth/2-42,top+panelHeight-24,84,20).build());
        markRead.active=readNonce!=null&&serverRevision.equals(localRevision);
    }
    @Override public void render(GuiGraphics graphics,int x,int y,float partial)
    {
        renderBackground(graphics);graphics.fill(left-3,top-3,left+panelWidth+3,top+panelHeight+3,0xFF44362B);graphics.fill(left,top,left+panelWidth,top+panelHeight,0xFFF0DEB7);
        var data=pages.get(page).getAsJsonObject();graphics.drawString(font,data.get("title").getAsString(),left+17,top+13,0x35251B,false);
        int textLeft=left+17,textWidth=panelWidth-34;
        if(page==0)
        {
            int h=Math.min(panelHeight-88,panelWidth-34),w=h;
            graphics.blit(TEXTURE,left+(panelWidth-w)/2,top+36,w,h,65,1090,891,880,2048,2048);
        }
        int yy=top+37;
        for(var line:font.split(Component.literal(data.get("text").getAsString()),textWidth))
        {graphics.drawString(font,line,textLeft,yy,0x3D2B20,false);yy+=11;if(yy>top+panelHeight-52)break;}
        graphics.drawString(font,"SEELE · ARCHIVE",left+17,top+panelHeight-42,0x806042,false);
        graphics.drawCenteredString(font,(page+1)+" / "+pages.size(),left+panelWidth-37,top+14,0x5B4634);super.render(graphics,x,y,partial);
    }
    @Override public boolean isPauseScreen(){return false;}
}

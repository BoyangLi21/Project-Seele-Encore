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
    private JsonArray pages;private int page, firstLine, maxFirstLine;private int left,top,panelWidth,panelHeight;
    private java.util.UUID readNonce;private String localRevision="";private Button markRead;
    private DeadSeaArchiveScreenR45(){super(Component.translatable("screen.projectseele.archive.title"));}
    public static void open(){Minecraft.getInstance().setScreen(new DeadSeaArchiveScreenR45());}
    public int pageIndex(){return page;}
    public static void attachReadChallenge(java.util.UUID nonce,String revision,int pages)
    {
        if(Minecraft.getInstance().screen instanceof DeadSeaArchiveScreenR45 screen&&screen.pages!=null&&screen.pages.size()==pages)
        {screen.readNonce=nonce;if(screen.markRead!=null)screen.markRead.active=true;}
    }

    @Override protected void init()
    {
        try(var stream=minecraft.getResourceManager().open(new ResourceLocation("projectseele","lore/dead_sea_archive_r45.json")))
        {byte[] bytes=stream.readAllBytes();localRevision=com.projectseele.world.DeadSeaReadingR45.hash(bytes);pages=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject().getAsJsonArray("pages");}
        catch(Exception error){throw new IllegalStateException("Archive pages unavailable",error);}
        panelWidth=Math.min(440,width-28);panelHeight=Math.min(292,height-40);left=(width-panelWidth)/2;top=(height-panelHeight)/2;
        addRenderableWidget(Button.builder(Component.translatable("screen.projectseele.archive.previous"),b->{page=Math.max(0,page-1);firstLine=0;}).bounds(left+14,top+panelHeight-24,66,20).build());
        addRenderableWidget(Button.builder(Component.translatable("screen.projectseele.archive.next"),b->{page=Math.min(pages.size()-1,page+1);firstLine=0;}).bounds(left+panelWidth-80,top+panelHeight-24,66,20).build());
        markRead=addRenderableWidget(Button.builder(Component.translatable("screen.projectseele.archive.mark_read"),b->{if(readNonce!=null)
            com.projectseele.network.SeeleNetwork.CHANNEL.sendToServer(new com.projectseele.network.ServerboundDeadSeaReadPageR45(readNonce,page,localRevision));})
            .bounds(left+panelWidth/2-42,top+panelHeight-24,84,20).build());
        markRead.active=readNonce!=null;
    }
    @Override public void render(GuiGraphics graphics,int x,int y,float partial)
    {
        renderBackground(graphics);graphics.fill(left-3,top-3,left+panelWidth+3,top+panelHeight+3,0xFF44362B);graphics.fill(left,top,left+panelWidth,top+panelHeight,0xFFF0DEB7);
        var data=pages.get(page).getAsJsonObject();graphics.drawString(font,pageText("title", data),left+17,top+13,0x35251B,false);
        int textLeft=left+17,textWidth=panelWidth-34;
        if(page==0)
        {
            int h=Math.min(panelHeight-88,panelWidth-34),w=h;
            graphics.blit(TEXTURE,left+(panelWidth-w)/2,top+36,w,h,65,1090,891,880,2048,2048);
        }
        var lines=font.split(pageText("text", data), textWidth);
        int visible=Math.max(1,(panelHeight-88)/11);
        maxFirstLine=Math.max(0,lines.size()-visible);
        firstLine=Math.min(firstLine,maxFirstLine);
        for(int i=firstLine;i<Math.min(lines.size(),firstLine+visible);i++)
            graphics.drawString(font,lines.get(i),textLeft,top+37+(i-firstLine)*11,0x3D2B20,false);
        graphics.drawString(font,Component.translatable("screen.projectseele.archive.imprint"),left+17,top+panelHeight-42,0x806042,false);
        if(maxFirstLine>0)
            graphics.drawString(font,Component.translatable("screen.projectseele.archive.scroll",firstLine+1,lines.size()),left+panelWidth/2,top+panelHeight-42,0x806042,false);
        graphics.drawCenteredString(font,(page+1)+" / "+pages.size(),left+panelWidth-37,top+14,0x5B4634);super.render(graphics,x,y,partial);
    }
    private Component pageText(String field, JsonObject data)
    {
        String original = data.get(field).getAsString();
        if (original.isEmpty() || !localRevision.equals(com.projectseele.world.DeadSeaReadingR45.currentRevision()))
            return Component.literal(original);
        return Component.translatableWithFallback("lore.projectseele.archive." + page + "." + field, original);
    }

    @Override public boolean mouseScrolled(double x,double y,double delta)
    {
        if(maxFirstLine==0)return super.mouseScrolled(x,y,delta);
        firstLine=Math.max(0,Math.min(maxFirstLine,firstLine-(int)Math.signum(delta)*2));
        return true;
    }
    @Override public boolean isPauseScreen(){return false;}
}

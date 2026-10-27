package com.projectseele.client.screen;

import java.util.List;
import java.util.function.BooleanSupplier;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.client.gui.components.Tooltip;
import net.minecraft.network.chat.Component;
import net.minecraft.util.FormattedCharSequence;

/** Shared native widgets; themes change presentation, never command availability. */
final class PhoneUiR54
{
    record Theme(int panel,int surface,int border,int accent,int selected,int text,int muted) {}
    static final Theme NERV=new Theme(0xFC101215,0xFF191C21,0xFF35383F,0xFFF28B65,0xFF49302B,0xFFF1ECE7,0xFFABA8A5);
    static final Theme UN=new Theme(0xFC101A23,0xFF192732,0xFF334C5C,0xFF8ED5F2,0xFF244959,0xFFE9F3F8,0xFFA2BBC9);

    static void line(GuiGraphics g,int x,int y,int w,int h,int color)
    {
        if(w<=0||h<=0)return;
        g.fill(x,y,x+w,y+1,color);g.fill(x,y+h-1,x+w,y+h,color);
        g.fill(x,y,x+1,y+h,color);g.fill(x+w-1,y,x+w,y+h,color);
    }

    static String fit(Font font,String text,int width)
    {
        if(width<=0)return "";
        return font.width(text)<=width?text:font.plainSubstrByWidth(text,Math.max(0,width-font.width("…")))+"…";
    }

    static void frame(GuiGraphics g,Font font,Theme theme,int x,int y,int w,int h,String title,String subtitle)
    {
        g.fill(x+4,y+5,x+w+4,y+h+5,0x70000000);
        g.fill(x,y,x+w,y+h,theme.panel());line(g,x,y,w,h,theme.border());
        g.fill(x,y,x+w,y+2,theme.accent());g.fill(x+12,y+12,x+15,y+29,theme.accent());
        g.pose().pushPose();g.pose().translate(x+22,y+12,0);g.pose().scale(1.2F,1.2F,1);
        g.drawString(font,fit(font,title,(int)((w-100)/1.2)),0,0,theme.text(),false);g.pose().popPose();
        g.drawString(font,fit(font,subtitle,w-36),x+14,y+33,theme.muted(),false);
    }

    static void card(GuiGraphics g,Font font,Theme theme,int x,int y,int w,int h,String label,String meta)
    {
        if(h<1)return;
        g.fill(x,y,x+w,y+h,theme.surface());line(g,x,y,w,h,theme.border());
        g.fill(x+1,y+1,x+3,y+15,theme.accent());
        g.drawString(font,label,x+9,y+5,theme.accent(),false);
        if(meta!=null&&!meta.isBlank())g.drawString(font,meta,x+w-9-font.width(meta),y+5,theme.muted(),false);
    }

    static void scrollbar(GuiGraphics g,Theme theme,int x,int top,int height,int total,int visible,int offset)
    {
        if(total<=visible||height<4)return;
        g.fill(x,top,x+2,top+height,theme.border());
        int thumb=Math.max(8,height*visible/Math.max(1,total));thumb=Math.min(height,thumb);
        int at=top+(height-thumb)*Math.min(offset,total-visible)/Math.max(1,total-visible);
        g.fill(x,at,x+2,at+thumb,theme.accent());
    }

    static int text(GuiGraphics g,Font font,Theme theme,String content,int x,int y,int w,int h,int scroll)
    {
        List<FormattedCharSequence> rows=font.split(Component.literal(content),Math.max(20,w-12));
        int count=Math.max(1,h/12);int start=Math.max(0,Math.min(scroll,rows.size()-count));
        if(h>0)
        {
            g.enableScissor(x,y,x+w,y+h);
            for(int i=start;i<Math.min(rows.size(),start+count);i++)g.drawString(font,rows.get(i),x,y+(i-start)*12,theme.text(),false);
            g.disableScissor();scrollbar(g,theme,x+w-3,y,h,rows.size(),count,start);
        }
        return start;
    }

    static final class Action extends Button
    {
        private final Theme theme;
        private final BooleanSupplier selected;
        Action(int x,int y,int width,int height,String label,Runnable action,Theme theme,BooleanSupplier selected)
        {
            super(x,y,width,height,Component.literal(label),ignored->action.run(),DEFAULT_NARRATION);
            this.theme=theme;this.selected=selected;setTooltip(Tooltip.create(Component.literal(label)));
        }
        @Override protected void renderWidget(GuiGraphics g,int mx,int my,float partial)
        {
            boolean chosen=selected.getAsBoolean(),hover=active&&isHoveredOrFocused();
            int fill=!active?0xFF191D22:chosen?theme.selected():hover?0xFF343F48:theme.surface();
            g.fill(getX(),getY(),getX()+width,getY()+height,fill);
            line(g,getX(),getY(),width,height,!active?0xFF353B41:hover||chosen?theme.accent():theme.border());
            if(chosen)g.fill(getX()+1,getY()+1,getX()+3,getY()+height-1,theme.accent());
            if(active&&isFocused())line(g,getX()+2,getY()+2,width-4,height-4,theme.text());
            var font=Minecraft.getInstance().font;
            String label=fit(font,getMessage().getString(),width-12);
            g.drawCenteredString(font,label,getX()+width/2,getY()+(height-8)/2,
                    !active?0xFF77818A:chosen||hover?theme.text():theme.muted());
        }
    }

    static final class Field extends EditBox
    {
        private final Theme theme;
        Field(Font font,int x,int y,int w,int h,Component title,Theme theme)
        {super(font,x,y,w,h,title);this.theme=theme;setTextColor(theme.text());setTextColorUneditable(theme.muted());}
        @Override public void renderWidget(GuiGraphics g,int mx,int my,float partial)
        {
            super.renderWidget(g,mx,my,partial);
            line(g,getX()-1,getY()-1,width+2,height+2,isFocused()?theme.accent():theme.border());
        }
    }
    private PhoneUiR54() {}
}

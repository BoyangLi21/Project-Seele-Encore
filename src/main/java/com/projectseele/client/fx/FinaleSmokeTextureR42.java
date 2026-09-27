package com.projectseele.client.fx;

import com.mojang.blaze3d.platform.NativeImage;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.texture.DynamicTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.VertexFormat;
import net.minecraft.client.renderer.RenderType;

/** Original soft density sprite. No film frame or stock photograph is embedded. */
final class FinaleSmokeTextureR42
{
    private static final ResourceLocation ID=new ResourceLocation("projectseele","dynamic/finale_smoke_r42");
    private static boolean loaded;
    static RenderType layer(){texture();return CloudLayer.TYPE;}
    static ResourceLocation texture()
    {
        if(loaded)return ID;
        int size=256;NativeImage image=new NativeImage(size,size,false);
        for(int y=0;y<size;y++)for(int x=0;x<size;x++)
        {
            double px=(x+.5)/(size*.5)-1,py=(y+.5)/(size*.5)-1;
            double large=noise(px*2.4+3,py*2.4+7),detail=.56*noise(px*5+21,py*5+5)+.29*noise(px*11+10,py*11+35)+.15*noise(px*23+4,py*23+9);
            double radius=Math.sqrt(px*px+py*py)/(.82+.20*large);
            double edge=Mth.clamp((1-radius)/.34,0,1);edge=edge*edge*(3-2*edge);
            int alpha=(int)(255*edge*(.28+.72*detail));
            int shade=(int)(255*Mth.clamp(.62+.31*large-.12*py,0,1));
            image.setPixelRGBA(x,y,alpha<<24|shade<<16|shade<<8|shade);
        }
        DynamicTexture texture=new DynamicTexture(image);
        Minecraft.getInstance().getTextureManager().register(ID,texture);
        texture.setFilter(true,false);loaded=true;return ID;
    }
    private static double hash(int x,int y)
    {int n=x*374761393+y*668265263;n=(n^(n>>>13))*1274126177;return ((n^(n>>>16))&0x7fffffff)/(double)0x7fffffff;}
    private static double noise(double x,double y)
    {
        int ix=(int)Math.floor(x),iy=(int)Math.floor(y);double u=x-ix,v=y-iy;u=u*u*(3-2*u);v=v*v*(3-2*v);
        return Mth.lerp(v,Mth.lerp(u,hash(ix,iy),hash(ix+1,iy)),Mth.lerp(u,hash(ix,iy+1),hash(ix+1,iy+1)));
    }
    private abstract static class CloudLayer extends RenderType
    {
        // The vanilla entity texture shard forces nearest filtering on bind,
        // overriding DynamicTexture.setFilter. Smoke also must not write its
        // rectangular depth plane over neighbouring translucent puffs.
        private static final RenderType TYPE=create("seele_soft_smoke_r42",DefaultVertexFormat.NEW_ENTITY,VertexFormat.Mode.QUADS,4096,false,true,
                CompositeState.builder().setShaderState(RENDERTYPE_ENTITY_TRANSLUCENT_SHADER)
                        .setTextureState(new TextureStateShard(ID,true,false)).setTransparencyState(TRANSLUCENT_TRANSPARENCY)
                        .setCullState(NO_CULL).setLightmapState(LIGHTMAP).setOverlayState(OVERLAY)
                        .setWriteMaskState(COLOR_WRITE).createCompositeState(false));
        private CloudLayer(){super("seele_smoke_unused",DefaultVertexFormat.NEW_ENTITY,VertexFormat.Mode.QUADS,256,false,true,()->{},()->{});}
    }
    private FinaleSmokeTextureR42(){}
}

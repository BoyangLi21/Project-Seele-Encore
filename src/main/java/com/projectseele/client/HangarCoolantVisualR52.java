package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.fluid.LclFluidType;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.BlockAndTintGetter;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ClientPlayerNetworkEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Vector3f;

/** Appearance of the three measured R52 wet bays only. Fluid identity and gameplay are unchanged. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class HangarCoolantVisualR52 {
    // Muted dark rose-purple from the TV01 cooling-pool reference, prior to native lighting review.
    public static final int TV_COOLANT_TINT=0xFF773A61;
    private record Bay(int minX,int maxX,int minY,int maxY,int minZ,int maxZ) {
        boolean contains(int x,int y,int z){return x>=minX&&x<=maxX&&y>=minY&&y<=maxY&&z>=minZ&&z<=maxZ;}
    }
    private static final java.util.List<Bay> BAYS=java.util.List.of(new Bay(53,91,-678,-635,302,354),new Bay(11,49,-678,-635,302,354),new Bay(-31,7,-678,-635,302,354));
    private record Scope(Object renderWorld,boolean claimed){}
    private static final Scope NONE=new Scope(null,false);
    private static volatile Scope scope=NONE;
    /** Pure immutable bounds/palette query, also used by the regression check. */
    public static int paletteAtR52(boolean claimed,boolean sameWorld,int x,int y,int z){if(claimed&&sameWorld)for(var bay:BAYS)if(bay.contains(x,y,z))return TV_COOLANT_TINT;return LclFluidType.TINT;}
    public static int tint(BlockAndTintGetter view,BlockPos pos) {
        if(view==null||pos==null)return LclFluidType.TINT;var current=scope;
        // Forge RenderChunkRegion delegates this stable identity to its owning Level.
        // Main-thread publication initializes it once; workers only compare references and bounds.
        if(!current.claimed()||current.renderWorld()==null||view.getModelDataManager()!=current.renderWorld())return LclFluidType.TINT;
        return paletteAtR52(true,true,pos.getX(),pos.getY(),pos.getZ());
    }
    public static Vector3f fogColor(ClientLevel level,BlockPos pos) {
        int tint=tint(level,pos);if(tint==LclFluidType.TINT)return new Vector3f(.86F,.33F,.125F);
        return new Vector3f(((tint>>16)&255)/255F,((tint>>8)&255)/255F,(tint&255)/255F);
    }
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event) {
        if(event.phase!=TickEvent.Phase.END)return;var mc=Minecraft.getInstance();var level=mc.level;boolean claimed=level!=null&&FacilityFrameClientR52.claimed(level);var next=claimed?new Scope(level.getModelDataManager(),true):NONE;var previous=scope;
        if(previous.claimed()==next.claimed()&&previous.renderWorld()==next.renderWorld())return;scope=next;
        // A claim received after early chunk meshes must also update those already baked quads.
        if(level!=null)for(var bay:BAYS)mc.levelRenderer.setBlocksDirty(bay.minX(),bay.minY(),bay.minZ(),bay.maxX(),bay.maxY(),bay.maxZ());
    }
    @SubscribeEvent public static void logout(ClientPlayerNetworkEvent.LoggingOut event){scope=NONE;}
    private HangarCoolantVisualR52(){}
}

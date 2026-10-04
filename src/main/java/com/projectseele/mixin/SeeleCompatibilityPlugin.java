package com.projectseele.mixin;

import java.util.*;
import com.projectseele.compat.CityUnionActivationR45;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.loading.FMLLoader;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.tree.*;
import org.spongepowered.asm.mixin.extensibility.*;

/** Keep optional-mod client receivers out of dedicated-server verification. */
public final class SeeleCompatibilityPlugin implements IMixinConfigPlugin
{
    @Override public void onLoad(String pkg) {}
    @Override public String getRefMapperConfig(){return null;}
    @Override public boolean shouldApplyMixin(String target,String mixin)
    {
        if (!mixin.endsWith("CityExactUnionCreateMixinR45") && !mixin.endsWith("CitySavedOwnerUnionMixinR45")) return true;
        if (!Boolean.getBoolean("projectseele.r45CityBalancedUnion")) return false;
        // No Create class initialization during transformation. Changed/absent backends retain their stock implementation.
        try (var input=getClass().getClassLoader().getResourceAsStream("com/simibubi/create/content/contraptions/Contraption.class"))
        {
            String actual=input==null?"":java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(input.readAllBytes()));
            String expected=CityUnionActivationR45.expectedCreateSHA256();
            boolean accepted=expected!=null && actual.equals(expected);
            CityUnionActivationR45.backend(actual,accepted,accepted?"Exact configured producer accepted":"Absent/changed Create producer or invalid explicit SHA");
            return accepted;
        }
        catch (Exception unavailable) { CityUnionActivationR45.backend("",false,unavailable.toString()); return false; }
    }
    @Override public void acceptTargets(Set<String> own,Set<String> others) {}
    @Override public List<String> getMixins(){return null;}
    @Override public void preApply(String name,ClassNode node,String mixin,IMixinInfo info) {}
    @Override public void postApply(String name,ClassNode node,String mixin,IMixinInfo info)
    {
        CityUnionActivationR45.applied(mixin);
        if(FMLLoader.getDist()!=Dist.DEDICATED_SERVER||!name.equals("com.solvane.grandpiano.network.PianoSyncPacket"))return;
        int changed=0;
        for(var method:node.methods)
        {
            if(!method.name.equals("lambda$handle$0")||!method.desc.equals("(Lcom/solvane/grandpiano/network/PianoSyncPacket;)V"))continue;
            // This is solely the PLAY_TO_CLIENT receiver's queued lambda.
            // Its encoder, decoder, discriminator and server key handling stay
            // intact. The original body is retained on every physical client.
            method.instructions.clear();method.instructions.add(new InsnNode(Opcodes.RETURN));
            method.tryCatchBlocks.clear();if(method.localVariables!=null)method.localVariables.clear();
            method.visibleLocalVariableAnnotations=null;method.invisibleLocalVariableAnnotations=null;
            method.maxLocals=1;method.maxStack=0;changed++;
        }
        if(changed!=1)throw new IllegalStateException("Pinned piano receiver contract changed");
        System.getLogger("Project SEELE compatibility").log(System.Logger.Level.INFO,"Piano 1.0.0 client-only sync receiver stripped on dedicated server; wire protocol retained");
    }
}

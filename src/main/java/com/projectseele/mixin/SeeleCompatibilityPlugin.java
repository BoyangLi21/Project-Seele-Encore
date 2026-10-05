package com.projectseele.mixin;

import java.util.*;
import com.projectseele.compat.CityUnionActivationR45;
import com.projectseele.compat.CityUnionPortableBootstrapR45;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.loading.FMLLoader;
import org.objectweb.asm.ClassReader;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.tree.*;
import org.spongepowered.asm.mixin.extensibility.*;

/** Keep optional-mod client receivers out of dedicated-server verification. */
public final class SeeleCompatibilityPlugin implements IMixinConfigPlugin
{
    private Boolean cityAbiAccepted;
    @Override public void onLoad(String pkg) {}
    @Override public String getRefMapperConfig(){return null;}
    @Override public boolean shouldApplyMixin(String target,String mixin)
    {
        if (!mixin.endsWith("CityExactUnionCreateMixinR45") && !mixin.endsWith("CitySavedOwnerUnionMixinR45")) return true;
        if (!CityUnionPortableBootstrapR45.requested()) return false;
        if(cityAbiAccepted!=null)return cityAbiAccepted;
        // Inspect the actual producer contract without initializing Create or
        // comparing mapped/native class bytes to historical QA resources.
        try
        {
            ClassNode base=readCityClass("Contraption"),owner=readCityClass("AbstractContraptionEntity");
            String level="Lnet/minecraft/world/level/Level;",nbt="Lnet/minecraft/nbt/CompoundTag;";
            MethodNode supplier=method(base,"lambda$gatherBBsOffThread$24","()Ljava/util/List;");
            boolean accepted=supplier!=null && method(base,"getBlocks","()Ljava/util/Map;")!=null
                    && method(base,"readNBT","("+level+nbt+"Z)V")!=null
                    && method(base,"writeNBT","(Z)"+nbt)!=null
                    && method(base,"gatherBBsOffThread","()V")!=null
                    && field(base,"blocks","Ljava/util/Map;")
                    && field(base,"collisionLevel","Lcom/simibubi/create/content/contraptions/ContraptionWorld;")
                    && field(base,"simplifiedEntityColliderProvider","Ljava/util/concurrent/CompletableFuture;")
                    && originalShapeBody(supplier)
                    && hasCall(method(owner,"readAdditional","("+nbt+"Z)V"),
                       "com/simibubi/create/content/contraptions/Contraption","fromNBT","("+level+nbt+"Z)Lcom/simibubi/create/content/contraptions/Contraption;");
            var resource=getClass().getClassLoader().getResource("com/simibubi/create/content/contraptions/Contraption.class");
            CityUnionActivationR45.backendAbi(String.valueOf(resource),accepted,
                    accepted?"Actual complete input/OR supplier, NBT ownership and future ABI accepted":"Actual Create input/OR/future ABI differs; original implementation retained");
            return cityAbiAccepted=accepted;
        }
        catch (Exception unavailable) { CityUnionActivationR45.backendAbi("",false,unavailable.toString());return cityAbiAccepted=false; }
    }
    private ClassNode readCityClass(String name)throws Exception
    {
        try(var stream=getClass().getClassLoader().getResourceAsStream("com/simibubi/create/content/contraptions/"+name+".class"))
        {
            if(stream==null)throw new IllegalStateException("Create producer absent: "+name);
            var node=new ClassNode();new ClassReader(stream).accept(node,ClassReader.SKIP_DEBUG|ClassReader.SKIP_FRAMES);return node;
        }
    }
    private static MethodNode method(ClassNode c,String name,String desc)
    {for(var m:c.methods)if(m.name.equals(name)&&m.desc.equals(desc))return m;return null;}
    private static boolean field(ClassNode c,String name,String desc)
    {return c.fields.stream().anyMatch(f->f.name.equals(name)&&f.desc.equals(desc));}
    private static boolean hasCall(MethodNode m,String owner,String name,String desc)
    {
        if(m==null)return false;
        for(var i:m.instructions)if(i instanceof MethodInsnNode call&&call.owner.equals(owner)&&call.name.equals(name)&&call.desc.equals(desc))return true;
        return false;
    }
    private static boolean originalShapeBody(MethodNode supplier)
    {
        String shapes="net/minecraft/world/phys/shapes/",shape="L"+shapes+"VoxelShape;";
        Map<String,String> names=Map.of("m_83040_","empty","m_82749_","empty","m_60742_","getCollisionShape",
                "m_83281_","isEmpty","m_83216_","move","m_83148_","joinUnoptimized","m_83296_","optimize","m_83299_","toAabbs");
        Set<String> required=new HashSet<>(List.of("empty_shape","context_empty","actual_block_shape","isEmpty","move","joinUnoptimized","optimize","toAabbs","OR","view","original_map"));
        for(var instruction:supplier.instructions)
        {
            if(instruction instanceof FieldInsnNode f)
            {
                if(f.owner.equals(shapes+"BooleanOp"))
                {
                    if(!f.name.equals("OR")&&!f.name.equals("f_82695_"))return false;
                    required.remove("OR");
                }
                if(f.name.equals("collisionLevel"))required.remove("view");
                if(f.owner.equals("com/simibubi/create/content/contraptions/Contraption")&&f.name.equals("blocks")&&f.desc.equals("Ljava/util/Map;"))required.remove("original_map");
            }
            if(!(instruction instanceof MethodInsnNode c))continue;
            String name=names.getOrDefault(c.name,c.name);
            if(c.owner.equals(shapes+"Shapes"))
            {
                if(name.equals("empty")&&c.desc.equals("()"+shape))required.remove("empty_shape");
                else if(name.equals("joinUnoptimized")&&c.desc.equals("("+shape+shape+"L"+shapes+"BooleanOp;)"+shape))required.remove("joinUnoptimized");
                else return false;
            }
            else if(c.owner.equals(shapes+"CollisionContext"))
            {if(!name.equals("empty"))return false;required.remove("context_empty");}
            else if(c.owner.equals(shapes+"VoxelShape"))
            {if(!Set.of("isEmpty","move","optimize","toAabbs").contains(name))return false;required.remove(name);}
            else if(c.owner.equals("net/minecraft/world/level/block/state/BlockState")&&name.equals("getCollisionShape")
                    &&c.desc.equals("(Lnet/minecraft/world/level/BlockGetter;Lnet/minecraft/core/BlockPos;L"+shapes+"CollisionContext;)"+shape))required.remove("actual_block_shape");
        }
        return required.isEmpty();
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

package com.projectseele.compat;

import java.util.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

/** Inspects the locked producer before changing its four immutable allocations.
 * A different ABI retains all original code and emits one concise explanation. */
public final class MtrRailMathCompatibilityR51
{
    private static final String CORE="org/mtr/core/",RAIL=CORE+"data/Rail",MATH=CORE+"data/RailMath",POSITION=CORE+"data/Position",ANGLE=CORE+"tool/Angle",SHAPE=RAIL+"$Shape";
    private static final String INIT="(L"+POSITION+";L"+ANGLE+";L"+POSITION+";L"+ANGLE+";L"+SHAPE+";D)V";
    private static final String ACTUAL_RAIL_INIT="(L"+POSITION+";L"+ANGLE+";L"+POSITION+";L"+ANGLE+";L"+SHAPE+";DLorg/mtr/libraries/it/unimi/dsi/fastutil/objects/ObjectArrayList;JJZZZZZZL"+CORE+"data/TransportMode;)V";
    private static final String READER_INIT="(L"+CORE+"serializer/ReaderBase;)V";
    private record Site(MethodNode method,TypeInsnNode allocation,AbstractInsnNode duplicate,MethodInsnNode initialize){}
    private static Boolean accepted;private static boolean explained;
    private static void explain(String message)
    {if(!explained){explained=true;System.getLogger("Project SEELE compatibility").log(System.Logger.Level.INFO,message);}}
    private static ClassNode read(ClassLoader loader,String name)throws Exception
    {try(var stream=loader.getResourceAsStream(name+".class")){if(stream==null)throw new IllegalStateException("MTR class absent: "+name);var node=new ClassNode();new ClassReader(stream).accept(node,ClassReader.SKIP_DEBUG|ClassReader.SKIP_FRAMES);return node;}}
    private static MethodNode method(ClassNode node,String name,String desc)
    {for(var m:node.methods)if(m.name.equals(name)&&m.desc.equals(desc))return m;return null;}
    private static boolean primitive(String desc){return Set.of("J","D","Z","F","I","B","C","S").contains(desc);}
    private static boolean immutableMath(ClassNode math)
    {
        if(!math.name.equals(MATH)||method(math,"<init>",INIT)==null)return false;int fields=0;
        for(var f:math.fields)if((f.access&Opcodes.ACC_STATIC)==0)
        {if((f.access&Opcodes.ACC_FINAL)==0||!primitive(f.desc)&&!f.desc.equals("L"+SHAPE+";"))return false;fields++;}
        if(fields!=24)return false;
        Set<String> pure=Set.of(MATH,"java/lang/Math","java/lang/Object",POSITION,ANGLE,SHAPE,CORE+"tool/Vector","org/mtr/libraries/it/unimi/dsi/fastutil/doubles/DoubleDoubleImmutablePair",MATH+"$RenderRail");
        for(var m:math.methods)for(var instruction:m.instructions)
        {
            if(instruction instanceof FieldInsnNode f&&f.getOpcode()==Opcodes.PUTFIELD&&!m.name.equals("<init>"))return false;
            if(instruction instanceof FieldInsnNode f&&(f.getOpcode()==Opcodes.PUTSTATIC
                    ||f.getOpcode()==Opcodes.GETSTATIC&&(!f.owner.equals(MATH+"$1")||!f.name.equals("$SwitchMap$org$mtr$core$data$Rail$Shape")||!f.desc.equals("[I"))))return false;
            if(instruction instanceof MethodInsnNode call&&call.owner.equals("java/lang/Math")
                    &&!Set.of("abs","atan2","ceil","floor","max","min","round","signum","sin","cos","sqrt").contains(call.name))return false;
            if(instruction instanceof MethodInsnNode call&&call.owner.equals("java/lang/Object")&&!call.name.equals("<init>"))return false;
            if(instruction instanceof MethodInsnNode call&&!pure.contains(call.owner)
                    &&!(call.owner.equals(CORE+"tool/Utilities")&&call.name.equals("clamp")&&call.desc.equals("(DDD)D")))return false;
            if(instruction instanceof InvokeDynamicInsnNode dynamic)
            {for(Object arg:dynamic.bsmArgs)if(arg instanceof Handle handle&&(!handle.getOwner().equals(MATH)||!handle.getName().equals("lambda$new$0")))return false;}
        }
        return true;
    }
    private static boolean fixedEnum(ClassNode node,int constants)
    {
        if((node.access&Opcodes.ACC_ENUM)==0)return false;int count=0;
        for(var f:node.fields){if((f.access&Opcodes.ACC_ENUM)!=0)count++;if((f.access&Opcodes.ACC_STATIC)==0&&((f.access&Opcodes.ACC_FINAL)==0||!primitive(f.desc)))return false;}
        return count==constants;
    }
    private static boolean coordinates(ClassNode position,ClassNode schema)
    {
        for(String axis:List.of("x","y","z"))
        {
            if(schema.fields.stream().noneMatch(f->f.name.equals(axis)&&f.desc.equals("J")&&(f.access&Opcodes.ACC_FINAL)!=0))return false;
            var getter=method(position,"get"+axis.toUpperCase(Locale.ROOT),"()J");if(getter==null)return false;int count=0;FieldInsnNode field=null;
            for(var i:getter.instructions)if(i.getOpcode()>=0){count++;if(i instanceof FieldInsnNode f)field=f;}
            if(count!=3||field==null||field.getOpcode()!=Opcodes.GETFIELD||!field.name.equals(axis)||!field.desc.equals("J"))return false;
        }
        return true;
    }
    private static boolean pureClamp(ClassNode utilities)
    {
        var clamp=method(utilities,"clamp","(DDD)D");if(clamp==null)return false;
        for(var i:clamp.instructions)
        {if(i instanceof FieldInsnNode||i instanceof InvokeDynamicInsnNode)return false;if(i instanceof MethodInsnNode c&&(!c.owner.equals("java/lang/Math")||!Set.of("min","max").contains(c.name)||!c.desc.equals("(DD)D")))return false;}
        return true;
    }
    private static AbstractInsnNode opcodeAfter(AbstractInsnNode i)
    {do{i=i.getNext();}while(i!=null&&i.getOpcode()<0);return i;}
    private static List<Site> sites(ClassNode rail)
    {
        var sites=new ArrayList<Site>();var counts=new HashMap<String,Integer>();
        for(var m:rail.methods)for(var i:m.instructions)if(i instanceof TypeInsnNode allocation&&i.getOpcode()==Opcodes.NEW&&allocation.desc.equals(MATH))
        {
            if(!m.name.equals("<init>")||!Set.of(ACTUAL_RAIL_INIT,READER_INIT).contains(m.desc))return List.of();
            var duplicate=opcodeAfter(i);if(duplicate==null||duplicate.getOpcode()!=Opcodes.DUP)return List.of();
            var args=new ArrayList<AbstractInsnNode>();var cursor=opcodeAfter(duplicate);
            while(cursor!=null&&!(cursor instanceof MethodInsnNode))
            {if(!(cursor instanceof VarInsnNode)||cursor.getOpcode()!=Opcodes.ALOAD&&cursor.getOpcode()!=Opcodes.DLOAD){if(!(cursor instanceof FieldInsnNode f)||f.getOpcode()!=Opcodes.GETFIELD)return List.of();}args.add(cursor);cursor=opcodeAfter(cursor);if(args.size()>12)return List.of();}
            if(!(cursor instanceof MethodInsnNode initialize)||initialize.getOpcode()!=Opcodes.INVOKESPECIAL||!initialize.owner.equals(MATH)||!initialize.name.equals("<init>")||!initialize.desc.equals(INIT))return List.of();
            if(m.desc.equals(ACTUAL_RAIL_INIT))
            {
                if(args.size()!=6)return List.of();int[] first={1,2,3,4,5,6},second={3,4,1,2,5,6};boolean a=true,b=true;
                for(int n=0;n<6;n++){if(!(args.get(n) instanceof VarInsnNode v)||v.getOpcode()!=(n==5?Opcodes.DLOAD:Opcodes.ALOAD))return List.of();a&=v.var==first[n];b&=v.var==second[n];}if(!a&&!b)return List.of();
            }
            else
            {
                if(args.size()!=12)return List.of();String[] first={"position1","angle1","position2","angle2","shape","verticalRadius"},second={"position2","angle2","position1","angle1","shape","verticalRadius"};
                String[] types={"L"+POSITION+";","L"+ANGLE+";","L"+POSITION+";","L"+ANGLE+";","L"+SHAPE+";","D"};boolean a=true,b=true;
                for(int n=0;n<6;n++){if(!(args.get(n*2) instanceof VarInsnNode v)||v.getOpcode()!=Opcodes.ALOAD||v.var!=0||!(args.get(n*2+1) instanceof FieldInsnNode f)||f.getOpcode()!=Opcodes.GETFIELD||!Set.of(RAIL,CORE+"generated/data/RailSchema").contains(f.owner)||!f.desc.equals(types[n]))return List.of();a&=f.name.equals(first[n]);b&=f.name.equals(second[n]);}if(!a&&!b)return List.of();
            }
            counts.merge(m.desc,1,Integer::sum);sites.add(new Site(m,allocation,duplicate,initialize));
        }
        return sites.size()==4&&counts.getOrDefault(ACTUAL_RAIL_INIT,0)==2&&counts.getOrDefault(READER_INIT,0)==2?List.copyOf(sites):List.of();
    }
    public static synchronized boolean accepted(ClassLoader loader)
    {
        if(accepted!=null)return accepted;
        try
        {
            boolean valid=immutableMath(read(loader,MATH))&&fixedEnum(read(loader,ANGLE),16)&&fixedEnum(read(loader,SHAPE),3)
                    &&coordinates(read(loader,POSITION),read(loader,CORE+"generated/data/PositionSchema"))&&pureClamp(read(loader,CORE+"tool/Utilities"))&&sites(read(loader,RAIL)).size()==4;
            if(!valid)explain("MTR immutable RailMath ABI differs; original geometry construction retained");return accepted=valid;
        }
        catch(Exception unavailable){explain("MTR immutable RailMath optimization unavailable; original geometry construction retained: "+unavailable.getMessage());return accepted=false;}
    }
    /** Inspect all sites before mutation so a failed live contract is a no-op. */
    public static synchronized boolean apply(ClassNode rail)
    {
        var planned=sites(rail);if(planned.size()!=4){explain("MTR live Rail constructor layout differs; original geometry construction retained");return false;}
        String factory="(Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;D)Ljava/lang/Object;";
        for(var site:planned)
        {
            site.method().instructions.remove(site.allocation());site.method().instructions.remove(site.duplicate());
            var call=new MethodInsnNode(Opcodes.INVOKESTATIC,"com/projectseele/compat/MtrRailMathCacheR51","construct",factory,false);
            site.method().instructions.set(site.initialize(),call);site.method().instructions.insert(call,new TypeInsnNode(Opcodes.CHECKCAST,MATH));
        }
        explain("MTR four RailMath allocations use bounded exact immutable geometry reuse; original Rail state and path updates retained");return true;
    }
    private MtrRailMathCompatibilityR51(){}
}

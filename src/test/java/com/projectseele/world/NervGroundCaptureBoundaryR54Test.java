package com.projectseele.world;

import java.util.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

/** Prevent the LOWER36 regression: reading a binding cannot reacquire a transport carrier. */
public final class NervGroundCaptureBoundaryR54Test
{
    public static void main(String[] args)throws Exception
    {
        var type=new ClassNode();
        try(var bytes=NervAssemblyOwnerR52.class.getResourceAsStream("NervAssemblyOwnerR52.class"))
        {new ClassReader(Objects.requireNonNull(bytes)).accept(type,ClassReader.SKIP_DEBUG|ClassReader.SKIP_FRAMES);}
        var calls=new HashMap<String,Set<String>>();
        for(var method:type.methods)
        {
            var targets=new HashSet<String>();calls.put(method.name,targets);
            for(var instruction:method.instructions)if(instruction instanceof MethodInsnNode call)targets.add(call.name);
        }
        if(!Collections.disjoint(calls.get("originalBinding"),Set.of("captureAssembly","transportSourceReadyR54","setAttachedR52")))
            throw new AssertionError("Binding query mutates transport custody during service or receiver inspection");
        for(String entry:List.of("continuousGeometryR52","sweptContinuousAssemblyR52"))
            if(!calls.get(entry).contains("transportSourceReadyR54"))
                throw new AssertionError("Cold transport lost its actual source-cache restoration entry: "+entry);
        if(!calls.get("transportSourceReadyR54").contains("captureAssembly")||!calls.get("captureAssembly").contains("setAttachedR52"))
            throw new AssertionError("Real movement lost physical original carrier admission");
        if(calls.containsKey("preflightContinuousCarrierR52")||calls.containsKey("sweptAssembly"))
            throw new AssertionError("Retired unchecked/single-leg proof entry returned");
        System.out.println("PASS ground getter/cold-motion/service capture boundaries: 5");
    }
}

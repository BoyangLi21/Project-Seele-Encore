package com.projectseele.client.render;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.function.Consumer;

/** Exercises the production pass selection/revision gate without creating GL buffers. */
public final class PosedGpuPassLifetimeR52Test
{
    private static Class<?> nested(String name)
    {for(Class<?> type:RigidCapsuleGpu.class.getDeclaredClasses())if(type.getSimpleName().equals(name))return type;throw new AssertionError(name);}
    private static Object create(Class<?> type,Object... args)throws Exception
    {Constructor<?> constructor=type.getDeclaredConstructors()[0];constructor.setAccessible(true);return constructor.newInstance(args);}
    @SuppressWarnings("unchecked") public static void main(String[] args)throws Exception
    {
        Class<?> stateType=nested("ExternalStates"),keyType=nested("ExternalKey"),meshType=nested("ExternalMesh");
        int[] released={0};Consumer<Object> release=value->released[0]++;
        Constructor<?> constructor=stateType.getDeclaredConstructor(int.class,Consumer.class);constructor.setAccessible(true);
        Object states=constructor.newInstance(4,release);
        Field field=stateType.getDeclaredField("variants");field.setAccessible(true);
        var slots=(BoundedRenderStatesR52<Object,Object>)field.get(states);
        Object shadow=create(keyType,null,true,0,0,0,0,0,null),main=create(keyType,null,false,0,0,0,0,0,null);
        Object shadowBuffer=create(meshType,null,1L,0,0,1F,1F,1F,null,true),mainBuffer=create(meshType,null,1L,0,0,1F,1F,1F,null,false);
        slots.put(shadow,shadowBuffer);slots.put(main,mainBuffer);
        Method select=RigidCapsuleGpu.class.getDeclaredMethod("selectPosedState",stateType,keyType,long.class);select.setAccessible(true);
        Method dirty=RigidCapsuleGpu.class.getDeclaredMethod("geometryUploadNeeded",meshType,long.class);dirty.setAccessible(true);
        for(long revision=2;revision<102;revision++)
        {
            if(select.invoke(null,states,shadow,revision)!=shadowBuffer||released[0]!=0||slots.size()!=2)
                throw new AssertionError("Animation closed the other pass buffer instead of retaining bounded slots");
            if(!(Boolean)dirty.invoke(null,mainBuffer,revision))throw new AssertionError("Old main-pass geometry could draw without a revision upload");
            shadowBuffer=create(meshType,null,revision,0,0,1F,1F,1F,null,true);slots.put(shadow,shadowBuffer);
            if((Boolean)dirty.invoke(null,shadowBuffer,revision))throw new AssertionError("Current uploaded revision marked stale");
            if(select.invoke(null,states,main,revision)!=mainBuffer||released[0]!=0)
                throw new AssertionError("Switching render pass discarded its reusable VBO slot");
            mainBuffer=create(meshType,null,revision,0,0,1F,1F,1F,null,false);slots.put(main,mainBuffer);
        }
        for(int light=1;light<=5;light++)slots.put(create(keyType,null,false,light,0,0,0,0,null),create(meshType,null,101L,light,0,1F,1F,1F,null,false));
        if(slots.size()!=4||released[0]!=3)throw new AssertionError("Retained shading states no longer obey the four-slot resource limit");
        slots.clear();if(released[0]!=7)throw new AssertionError("Reload did not release every remaining bounded slot");
        System.out.println("PASS: 100 real pose revisions preserve shadow/main slots; stale slot must upload; bounded overflow and reload release resources");
    }
}

package com.projectseele.compat;

import java.lang.reflect.*;
import java.util.*;

/** Exact constructor inputs share only MTR's verified immutable RailMath.
 * Mutable Rail/PathData/vehicle objects are never retained or substituted. */
public final class MtrRailMathCacheR51
{
    private static final int LIMIT=1024;
    private record Key(Class<?> math,long x1,long y1,long z1,Object angle1,long x2,long y2,long z2,Object angle2,Object shape,long radius){}
    private record Binding(Class<?> position,Class<?> angle,Class<?> shape,Class<?> math,Method x,Method y,Method z,Constructor<?> constructor){}
    private static final ClassValue<Binding> BINDINGS=new ClassValue<>()
    {
        @Override protected Binding computeValue(Class<?> source)
        {
            try
            {
                var loader=source.getClassLoader();var position=Class.forName("org.mtr.core.data.Position",false,loader);
                var angle=Class.forName("org.mtr.core.tool.Angle",false,loader);var shape=Class.forName("org.mtr.core.data.Rail$Shape",false,loader);
                var math=Class.forName("org.mtr.core.data.RailMath",false,loader);
                return new Binding(position,angle,shape,math,position.getMethod("getX"),position.getMethod("getY"),position.getMethod("getZ"),math.getConstructor(position,angle,position,angle,shape,double.class));
            }
            catch(ReflectiveOperationException error){throw new IllegalStateException("Verified MTR RailMath constructor is unavailable",error);}
        }
    };
    private static final Map<Key,Object> CACHE=new LinkedHashMap<>(128,.75F,true)
    {
        @Override protected boolean removeEldestEntry(Map.Entry<Key,Object> entry){return size()>LIMIT;}
    };
    private static long hits,misses,created;
    private static long coordinate(Method getter,Object position)throws ReflectiveOperationException
    {return ((Number)getter.invoke(position)).longValue();}
    private static Object build(Binding b,Object p1,Object a1,Object p2,Object a2,Object shape,double radius)throws ReflectiveOperationException
    {
        try{return b.constructor().newInstance(p1,a1,p2,a2,shape,radius);}
        catch(InvocationTargetException error)
        {if(error.getCause() instanceof RuntimeException runtime)throw runtime;if(error.getCause() instanceof Error fatal)throw fatal;throw error;}
    }
    /** Object ABI keeps MTR optional at compile time. The checked producer adds
     * the exact RailMath CHECKCAST immediately after this factory call. */
    public static Object construct(Object p1,Object a1,Object p2,Object a2,Object shape,double radius)
    {
        try
        {
            var b=BINDINGS.get(p1.getClass());
            // Foreign subclasses may make getters contextual. Retain their
            // original constructor instead of assuming immutable coordinates.
            if(p1.getClass()!=b.position()||p2.getClass()!=b.position()||a1==null||a2==null||shape==null
                    ||a1.getClass()!=b.angle()||a2.getClass()!=b.angle()||shape.getClass()!=b.shape())return build(b,p1,a1,p2,a2,shape,radius);
            var key=new Key(b.math(),coordinate(b.x(),p1),coordinate(b.y(),p1),coordinate(b.z(),p1),a1,
                    coordinate(b.x(),p2),coordinate(b.y(),p2),coordinate(b.z(),p2),a2,shape,Double.doubleToRawLongBits(radius));
            synchronized(CACHE){var old=CACHE.get(key);if(old!=null){hits++;return old;}misses++;}
            // Expensive pure construction stays outside the lock. Concurrent
            // misses may calculate twice, but publish and return one instance.
            var value=build(b,p1,a1,p2,a2,shape,radius);
            synchronized(CACHE){created++;var old=CACHE.get(key);if(old!=null)return old;CACHE.put(key,value);return value;}
        }
        catch(ReflectiveOperationException error){throw new IllegalStateException("MTR immutable geometry factory failed",error);}
    }
    public static Map<String,Long> snapshot()
    {synchronized(CACHE){return Map.of("hits",hits,"misses",misses,"constructed",created,"entries",(long)CACHE.size(),"limit",(long)LIMIT);}}
    private MtrRailMathCacheR51(){}
}

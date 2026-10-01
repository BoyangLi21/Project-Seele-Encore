package com.projectseele.physics;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.SbwStaticShapesR24;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.vehicle.AbstractMinecart;
import net.minecraft.world.entity.vehicle.Boat;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.EntityHitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.entity.PartEntity;
import org.joml.Vector3d;
import java.lang.reflect.Method;
import java.util.*;
import java.util.function.Predicate;

/** Weapon damage includes native vehicle hulls, with one target per parent. */
public final class CombatDamageTargetsR44
{
    public enum Weapon { CONTACT, PROJECTILE, LASER }

    public static Entity parent(Entity entity)
    {
        while(entity instanceof PartEntity<?> part)entity=part.getParent();
        return entity;
    }
    public static boolean supported(Entity entity)
    {
        return entity instanceof LivingEntity||SbwStaticShapesR24.vehicle(entity)
                ||entity instanceof Boat||entity instanceof AbstractMinecart;
    }
    public static boolean allowed(Entity entity,Entity attacker,Entity pilot)
    {
        Entity target=parent(entity);
        if(!supported(target)||!target.isAlive()||target.isSpectator()
                ||target==attacker||target==pilot)return false;
        if(attacker!=null&&target.getRootVehicle()==attacker.getRootVehicle())return false;
        if(pilot!=null&&target.getRootVehicle()==pilot.getRootVehicle())return false;
        // Hit the hull once; do not also hit the protected nested occupants.
        Entity root=target.getRootVehicle();
        return root==target||!(root instanceof EvaUnit01Entity||SbwStaticShapesR24.vehicle(root)
                ||root instanceof Boat||root instanceof AbstractMinecart);
    }
    public static List<Entity> unique(Collection<? extends Entity> entities,Predicate<Entity> filter)
    {
        Map<UUID,Entity> result=new LinkedHashMap<>();
        for(Entity raw:entities)
        {
            Entity target=parent(raw);
            if(filter.test(target))result.putIfAbsent(target.getUUID(),target);
        }
        return List.copyOf(result.values());
    }
    public static List<Entity> candidates(Level level,AABB contact,Entity attacker,Entity pilot)
    {
        return unique(level.getEntities((Entity)null,CombatEntityQueryR44.originSearch(contact)),
                e->allowed(e,attacker,pilot));
    }

    private record VehicleShape(Method boxes,Method inflate,Method clip,Method contains,Method overlap,Method closest) {}
    private static final ClassValue<VehicleShape> SHAPES=new ClassValue<>()
    {
        @Override protected VehicleShape computeValue(Class<?> type)
        {
            try
            {
                Class<?> obb=Class.forName("com.atsuishio.superbwarfare.tools.OBB",false,type.getClassLoader());
                return new VehicleShape(type.getMethod("getOBBs"),obb.getMethod("inflate",double.class),
                        obb.getMethod("clip",Vector3d.class,Vector3d.class),obb.getMethod("contains",Vec3.class),
                        obb.getMethod("isColliding",obb,AABB.class),obb.getMethod("getClosestPointOBB",Vector3d.class,obb));
            }
            catch(ReflectiveOperationException error){throw new IllegalStateException("Pinned SBW hull API changed",error);}
        }
    };
    private static List<?> boxes(Entity target,VehicleShape shape)
    {
        try{return (List<?>)shape.boxes.invoke(target);}
        catch(ReflectiveOperationException error){throw new IllegalStateException("Cannot read native SBW hull",error);}
    }
    public static Optional<Vec3> clip(Entity target,Vec3 from,Vec3 to,double radius)
    {
        if(target instanceof LivingEntity living)return CombatBodyContacts.clip(living,from,to,radius);
        if(SbwStaticShapesR24.vehicle(target))
        {
            VehicleShape shape=SHAPES.get(target.getClass());Vec3 nearest=null;
            try
            {
                for(Object raw:boxes(target,shape))
                {
                    Object box=shape.inflate.invoke(raw,radius);
                    Optional<?> contact=(Optional<?>)shape.clip.invoke(box,new Vector3d(from.x,from.y,from.z),new Vector3d(to.x,to.y,to.z));
                    Vec3 point=null;
                    if((boolean)shape.contains.invoke(box,from))point=from;
                    else if(contact.isPresent()){Vector3d p=(Vector3d)contact.get();point=new Vec3(p.x,p.y,p.z);}
                    if(point!=null&&(nearest==null||from.distanceToSqr(point)<from.distanceToSqr(nearest)))nearest=point;
                }
                return Optional.ofNullable(nearest);
            }
            catch(ReflectiveOperationException error){throw new IllegalStateException("Cannot clip native SBW hull",error);}
        }
        AABB box=target.getBoundingBox().inflate(radius);
        return box.contains(from)?Optional.of(from):box.clip(from,to);
    }
    public static boolean overlap(Entity target,AABB area)
    {
        if(target instanceof LivingEntity living)return CombatBodyContacts.overlap(living,area);
        if(SbwStaticShapesR24.vehicle(target))
        {
            VehicleShape shape=SHAPES.get(target.getClass());
            try{for(Object box:boxes(target,shape))if((boolean)shape.overlap.invoke(null,box,area))return true;return false;}
            catch(ReflectiveOperationException error){throw new IllegalStateException("Cannot test native SBW hull",error);}
        }
        return target.getBoundingBox().intersects(area);
    }
    public static Vec3 nearestSurface(Entity target,Vec3 origin)
    {
        if(target instanceof LivingEntity living)return CombatBodyContacts.nearestSurfacePoint(living,origin);
        if(SbwStaticShapesR24.vehicle(target))
        {
            VehicleShape shape=SHAPES.get(target.getClass());Vec3 nearest=null;
            try
            {
                for(Object box:boxes(target,shape))
                {
                    Vector3d p=(Vector3d)shape.closest.invoke(null,new Vector3d(origin.x,origin.y,origin.z),box);
                    Vec3 point=new Vec3(p.x,p.y,p.z);
                    if(nearest==null||origin.distanceToSqr(point)<origin.distanceToSqr(nearest))nearest=point;
                }
                if(nearest!=null)return nearest;
            }
            catch(ReflectiveOperationException error){throw new IllegalStateException("Cannot locate native SBW hull",error);}
        }
        AABB b=target.getBoundingBox();return new Vec3(Math.max(b.minX,Math.min(b.maxX,origin.x)),Math.max(b.minY,Math.min(b.maxY,origin.y)),Math.max(b.minZ,Math.min(b.maxZ,origin.z)));
    }
    public static EntityHitResult ray(Level level,Vec3 from,Vec3 to,double radius,Entity attacker,Entity pilot)
    {
        EntityHitResult first=null;double distance=Double.POSITIVE_INFINITY;
        for(Entity target:candidates(level,new AABB(from,to).inflate(radius),attacker,pilot))
        {
            var contact=clip(target,from,to,radius);if(contact.isEmpty())continue;
            double current=from.distanceToSqr(contact.get());
            if(current<distance){distance=current;first=new EntityHitResult(target,contact.get());}
        }
        return first;
    }
    public static boolean hurt(Entity target,DamageSource source,float amount,Vec3 point,Vec3 direction,Weapon weapon)
    {
        target=parent(target);
        if(target instanceof LivingEntity living)return com.projectseele.event.EvaHitFeedback.hurt(living,source,amount,point,direction);
        if(SbwStaticShapesR24.vehicle(target))
        {
            String id=switch(weapon){case CONTACT->"vehicle_strike";case PROJECTILE->"projectile_hit";case LASER->"laser_static";};
            var key=ResourceKey.create(Registries.DAMAGE_TYPE,new ResourceLocation("superbwarfare",id));
            var holder=target.level().registryAccess().registryOrThrow(Registries.DAMAGE_TYPE).getHolderOrThrow(key);
            source=new DamageSource(holder,source.getDirectEntity(),source.getEntity());
        }
        return target.hurt(source,amount);
    }
    private CombatDamageTargetsR44() {}
}

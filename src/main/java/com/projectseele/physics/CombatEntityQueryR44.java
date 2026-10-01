package com.projectseele.physics;

import com.projectseele.entity.EvaScale;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.SachielEntity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.EntityHitResult;
import net.minecraft.world.phys.Vec3;
import java.util.List;
import java.util.function.Predicate;

/** Entity sections index the origin; the final contact owns the damage volume. */
public final class CombatEntityQueryR44
{
    public static AABB originSearch(AABB contact)
    {
        // Raised arms and articulated falls can extend beyond a standing box.
        // This broad phase never loads chunks and never expands the hit shape.
        double reach=EvaScale.NORMAL_HEIGHT*2.0D;
        return contact.inflate(reach);
    }
    public static List<LivingEntity> candidates(Level level,AABB contact,Predicate<LivingEntity> filter)
    {
        return level.getEntitiesOfClass(LivingEntity.class,originSearch(contact),entity->
                filter.test(entity)&&(entity instanceof EvaUnit01Entity||entity instanceof SachielEntity
                        ||entity.getBoundingBox().intersects(contact)));
    }
    public static List<LivingEntity> overlap(Level level,AABB contact,Predicate<LivingEntity> filter)
    {
        return candidates(level,contact,filter).stream().filter(entity->CombatBodyContacts.overlap(entity,contact)).toList();
    }
    public static EntityHitResult ray(Level level,Vec3 from,Vec3 to,double radius,Predicate<LivingEntity> filter)
    {
        EntityHitResult first=null;double distance=Double.POSITIVE_INFINITY;
        for(var entity:candidates(level,new AABB(from,to).inflate(radius),filter))
        {
            // A nested entry plug shields its pilot; its EVA receives the ray.
            if(entity.isPassenger()&&entity.getRootVehicle() instanceof EvaUnit01Entity)continue;
            var contact=CombatBodyContacts.clip(entity,from,to,radius);if(contact.isEmpty())continue;
            double current=from.distanceToSqr(contact.orElse(from));
            if(current<distance){distance=current;first=new EntityHitResult(entity,contact.orElse(from));}
        }
        return first;
    }
    private CombatEntityQueryR44(){}
}

package com.projectseele.mixin;

import com.projectseele.entity.Angel;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.SachielEntity;
import com.projectseele.physics.CombatBodyContacts;
import com.projectseele.physics.CombatEntityQueryR44;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.Explosion;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;

/** Keep vanilla explosion damage/events, with body-based giant intersections. */
@Mixin(Explosion.class)
public abstract class GiantExplosionQueryMixinR44
{
    @Shadow @Final private Entity source;
    @Shadow @Final private Vec3 position;
    @Unique private final Map<Entity,Vec3> seele$contacts=new IdentityHashMap<>();
    @Unique private boolean seele$combat(){return source instanceof EvaUnit01Entity||source instanceof Angel;}
    @Unique private boolean seele$giant(Entity entity)
    {return seele$combat()&&(entity instanceof EvaUnit01Entity||entity instanceof Angel);}
    @Unique private Vec3 seele$contact(Entity entity)
    {return seele$contacts.computeIfAbsent(entity,key->CombatBodyContacts.nearestSurfacePoint((LivingEntity)key,position));}
    @Unique private Vec3 seele$direction(Entity entity)
    {
        var point=seele$contact(entity);
        // An explosion inside a body has full exposure. Keep vanilla's eye
        // direction instead of the zero vector that would skip damage entirely.
        return point.distanceToSqr(position)>1e-8?point:new Vec3(entity.getX(),entity.getEyeY(),entity.getZ());
    }
    @Redirect(method="explode",at=@At(value="INVOKE",target="Lnet/minecraft/world/level/Level;getEntities(Lnet/minecraft/world/entity/Entity;Lnet/minecraft/world/phys/AABB;)Ljava/util/List;"))
    private List<Entity> seele$originCandidates(Level level,Entity excluded,AABB area)
    {
        if(!seele$combat())return level.getEntities(excluded,area);
        return level.getEntities(excluded,CombatEntityQueryR44.originSearch(area)).stream()
                .filter(entity->seele$giant(entity)||entity.getBoundingBox().intersects(area))
                .filter(entity->!(entity instanceof LivingEntity&&entity.isPassenger()&&entity.getRootVehicle() instanceof EvaUnit01Entity))
                .collect(java.util.stream.Collectors.toCollection(java.util.ArrayList::new));
    }
    @Redirect(method="explode",at=@At(value="INVOKE",target="Lnet/minecraft/world/entity/Entity;distanceToSqr(Lnet/minecraft/world/phys/Vec3;)D"))
    private double seele$surfaceDistance(Entity entity,Vec3 origin)
    {return seele$giant(entity)?seele$contact(entity).distanceToSqr(origin):entity.distanceToSqr(origin);}
    @Redirect(method="explode",at=@At(value="INVOKE",target="Lnet/minecraft/world/entity/Entity;getX()D"))
    private double seele$surfaceX(Entity entity){return seele$giant(entity)?seele$direction(entity).x:entity.getX();}
    @Redirect(method="explode",at=@At(value="INVOKE",target="Lnet/minecraft/world/entity/Entity;getY()D"))
    private double seele$surfaceY(Entity entity){return seele$giant(entity)?seele$direction(entity).y:entity.getY();}
    @Redirect(method="explode",at=@At(value="INVOKE",target="Lnet/minecraft/world/entity/Entity;getEyeY()D"))
    private double seele$surfaceEye(Entity entity){return seele$giant(entity)?seele$direction(entity).y:entity.getEyeY();}
    @Redirect(method="explode",at=@At(value="INVOKE",target="Lnet/minecraft/world/entity/Entity;getZ()D"))
    private double seele$surfaceZ(Entity entity){return seele$giant(entity)?seele$direction(entity).z:entity.getZ();}
}

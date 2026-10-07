package com.projectseele.entity;

import com.projectseele.event.EvaHitFeedback;
import com.projectseele.world.TvMarineDirectorR50;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.StringTag;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.FluidTags;
import net.minecraft.util.Mth;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.monster.Enemy;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import java.util.HashSet;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

/** The entity root is the model's buoyancy centre, rather than a land mob's feet. */
public final class GaghielEntity extends Mob implements Enemy, Angel, software.bernie.geckolib.animatable.GeoEntity
{
    private final software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache geoCache=software.bernie.geckolib.util.GeckoLibUtil.createInstanceCache(this);
    @Override public software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache getAnimatableInstanceCache(){return geoCache;}
    @Override public void registerControllers(software.bernie.geckolib.core.animation.AnimatableManager.ControllerRegistrar controllers){}
    public static final int SWIM=0,BITE=1,BREACH=2,FIN_SWEEP=3;
    private static final EntityDataAccessor<Float> SCALE=SynchedEntityData.defineId(GaghielEntity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> FIELD=SynchedEntityData.defineId(GaghielEntity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> MOUTH=SynchedEntityData.defineId(GaghielEntity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Integer> ATTACK=SynchedEntityData.defineId(GaghielEntity.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> AGE=SynchedEntityData.defineId(GaghielEntity.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> SWIM_AGE=SynchedEntityData.defineId(GaghielEntity.class,EntityDataSerializers.INT);
    private Vec3 home;
    private double radiusX=30,radiusZ=30,seabed=16,water=62;
    private int cooldown=60,choice;
    private float previousMouth;
    private Vec3 previousMouthPoint;
    private Vec3[] previousSweepPoints;
    private float strikeYaw;
    private UUID heldBy;
    private final Set<UUID> hit=new HashSet<>();
    private Vec3 damagePoint;
    private boolean navalCoreHit;
    private boolean nativeProjectileProcessing;

    private record Body(Vec3 center,Vec3 radii) {}
    private static final Body[] BODY={
        new Body(new Vec3(0,6,-25),new Vec3(13,19,20)),
        new Body(new Vec3(0,0,-3),new Vec3(16,13,28)),
        new Body(new Vec3(0,0,25),new Vec3(9,8,21)),
        new Body(new Vec3(0,0,52),new Vec3(4.5,6,12)),
        new Body(new Vec3(-21,0,3),new Vec3(11,3.5,16)),
        new Body(new Vec3(21,0,3),new Vec3(11,3.5,16))};

    public GaghielEntity(EntityType<? extends GaghielEntity> type,Level level)
    {
        super(type,level);setNoGravity(true);setPersistenceRequired();
    }
    public static AttributeSupplier.Builder createAttributes()
    {
        return Mob.createMobAttributes().add(Attributes.MAX_HEALTH,900).add(Attributes.ARMOR,8)
                .add(Attributes.ATTACK_DAMAGE,36).add(Attributes.MOVEMENT_SPEED,.65)
                .add(Attributes.FOLLOW_RANGE,180).add(Attributes.KNOCKBACK_RESISTANCE,1);
    }
    @Override protected void defineSynchedData()
    {
        super.defineSynchedData();entityData.define(SCALE,1F);entityData.define(FIELD,360F);
        entityData.define(MOUTH,0F);entityData.define(ATTACK,SWIM);entityData.define(AGE,0);entityData.define(SWIM_AGE,0);
    }
    @Override protected void registerGoals(){}
    @Override public boolean canBreatheUnderwater(){return true;}
    @Override protected int decreaseAirSupply(int air){return getMaxAirSupply();}
    @Override public boolean isPushedByFluid(){return false;}
    @Override public boolean removeWhenFarAway(double distance){return false;}
    @Override public void travel(Vec3 input){}
    public float modelScaleR50(){return entityData.get(SCALE);}
    @Override public float getAtField(){return entityData.get(FIELD);}
    public int attackKind(){return entityData.get(ATTACK);}
    public float swimPhase(float partial){return (entityData.get(SWIM_AGE)+partial)*.10F;}
    public float attackPhase(float partial){return attackKind()==SWIM?0:Mth.clamp((entityData.get(AGE)+partial)/attackDuration(),0,1);}
    public float mouthOpen(float partial){return Mth.lerp(partial,previousMouth,entityData.get(MOUTH));}
    private int attackDuration(){return attackKind()==BREACH?82:attackKind()==FIN_SWEEP?64:54;}
    public void configureMarineR50(Vec3 center,double rx,double rz,double bed,double surface,float scale)
    {
        home=center;radiusX=rx;radiusZ=rz;seabed=bed;water=surface;entityData.set(SCALE,Mth.clamp(scale,.2F,1.25F));
        setBoundingBox(makeBoundingBox());
    }
    public double waterlineR50(){return water;}
    public boolean mouthHeldR50(){return heldBy!=null;}
    public void holdMouthR50(UUID eva)
    {
        heldBy=eva;if(eva!=null){entityData.set(MOUTH,1F);setDeltaMovement(getDeltaMovement().scale(.1));}
    }
    public Vec3 modelPointR50(Vec3 local,float partial)
    {
        double yaw=(180-Mth.rotLerp(partial,yRotO,getYRot()))*Math.PI/180;
        Vec3 p=local.scale(modelScaleR50());double c=Math.cos(yaw),s=Math.sin(yaw);
        return (level().isClientSide?getPosition(partial):position()).add(p.x*c+p.z*s,p.y,-p.x*s+p.z*c);
    }
    public Vec3 mouthWorldPos(float partial){return modelPointR50(new Vec3(0,0,-37),partial);}
    public Vec3 coreWorldPos(float partial){return modelPointR50(new Vec3(0,1,-26),partial);}
    public Vec3 jawHingeWorldPos(float partial){return modelPointR50(new Vec3(0,-.5,-23),partial);}
    private Vec3 local(Vec3 world)
    {
        Vec3 p=world.subtract(position());double a=-(180-getYRot())*Math.PI/180,c=Math.cos(a),s=Math.sin(a);
        return new Vec3(p.x*c+p.z*s,p.y,-p.x*s+p.z*c).scale(1/modelScaleR50());
    }
    @Override protected AABB makeBoundingBox()
    {
        double scale=entityData==null?1:modelScaleR50(),a=(180-getYRot())*Math.PI/180;
        double x=(Math.abs(Math.cos(a))*32+Math.abs(Math.sin(a))*54.5)*scale;
        double z=(Math.abs(Math.cos(a))*54.5+Math.abs(Math.sin(a))*32)*scale;
        double cx=getX()+Math.sin(a)*9.5*scale,cz=getZ()+Math.cos(a)*9.5*scale;
        double jaw=entityData==null?0:entityData.get(MOUTH);
        return new AABB(cx-x,getY()-(13+11*jaw)*scale,cz-z,cx+x,getY()+26*scale,cz+z);
    }
    @Override public AABB getBoundingBoxForCulling(){return getBoundingBox().inflate(4*modelScaleR50());}
    public Optional<Vec3> clipBody(Vec3 from,Vec3 to,double radius)
    {
        Vec3 p=local(from),q=local(to),delta=q.subtract(p);double best=Double.POSITIVE_INFINITY,r=radius/modelScaleR50();boolean coreBest=false;
        Vec3 core=new Vec3(0,1,-26);
        boolean aperture=entityData.get(MOUTH)>=.65F&&delta.z>0&&p.z<core.z&&Math.abs(p.x+delta.x*Mth.clamp((-37-p.z)/delta.z,0,1))<=7.5
                &&Math.abs(p.y+delta.y*Mth.clamp((-37-p.z)/delta.z,0,1))<=7.5;
        Body[] hulls=aperture?new Body[]{new Body(core,new Vec3(5.5,5.5,5.5)),BODY[2],BODY[3],BODY[4],BODY[5]}:BODY;
        for(Body body:hulls)
        {
            Vec3 radii=body.radii.add(r,r,r),v=p.subtract(body.center);
            Vec3 u=new Vec3(v.x/radii.x,v.y/radii.y,v.z/radii.z);
            Vec3 d=new Vec3(delta.x/radii.x,delta.y/radii.y,delta.z/radii.z);
            double aa=d.lengthSqr(),bb=2*u.dot(d),cc=u.lengthSqr()-1;
            if(cc<=0){if(best>0){best=0;coreBest=aperture&&body==hulls[0];}continue;}double discriminant=bb*bb-4*aa*cc;
            if(aa<1e-12||discriminant<0)continue;
            double t=(-bb-Math.sqrt(discriminant))/(2*aa);if(t>=0&&t<=1&&t<best){best=t;coreBest=aperture&&body==hulls[0];}
        }
        if(!Double.isFinite(best))return Optional.empty();
        Vec3 point=from.lerp(to,best),center=coreWorldPos(1);
        // A finite projectile's centre contacts the inflated proxy first;
        // damage and presentation use the real core surface it touched.
        if(coreBest&&point.distanceTo(center)>5.5*modelScaleR50())point=center.add(point.subtract(center).normalize().scale(5.5*modelScaleR50()));
        return Optional.of(point);
    }
    public boolean overlapBody(AABB box)
    {
        if(!getBoundingBox().intersects(box))return false;
        Vec3 center=box.getCenter();double radius=box.getSize()*.5;
        if(clipBody(center,center,radius).isPresent())return true;
        for(Body body:BODY)if(box.contains(modelPointR50(body.center,1)))return true;
        return false;
    }
    public Optional<Vec3> clipBladeR50(Vec3 a,Vec3 b,Vec3 c,Vec3 d,double radius)
    {
        Vec3[] corners={local(a),local(b),local(c),local(d)};
        for(Body body:BODY)
        {
            Vec3 radii=body.radii.add(radius/modelScaleR50(),radius/modelScaleR50(),radius/modelScaleR50());
            Vec3[] p=new Vec3[4];
            for(int i=0;i<4;i++)
            {Vec3 v=corners[i].subtract(body.center);p[i]=new Vec3(v.x/radii.x,v.y/radii.y,v.z/radii.z);}
            for(int[] tri:new int[][]{{0,1,2},{0,2,3}})
            {
                Vec3 hit=nearestTriangleOriginR50(p[tri[0]],p[tri[1]],p[tri[2]]);
                if(hit.lengthSqr()<=1)
                    return Optional.of(modelPointR50(new Vec3(hit.x*radii.x,hit.y*radii.y,hit.z*radii.z).add(body.center),1));
            }
        }
        return Optional.empty();
    }
    private static Vec3 nearestTriangleOriginR50(Vec3 a,Vec3 b,Vec3 c)
    {
        Vec3 normal=b.subtract(a).cross(c.subtract(a));
        if(normal.lengthSqr()>1e-12)
        {
            Vec3 p=normal.scale(normal.dot(a)/normal.lengthSqr());
            if(normal.dot(b.subtract(a).cross(p.subtract(a)))>=-1e-9
                    &&normal.dot(c.subtract(b).cross(p.subtract(b)))>=-1e-9
                    &&normal.dot(a.subtract(c).cross(p.subtract(c)))>=-1e-9)return p;
        }
        Vec3 best=a;
        for(Vec3[] edge:new Vec3[][]{{a,b},{b,c},{c,a}})
        {
            Vec3 v=edge[1].subtract(edge[0]);double t=v.lengthSqr()<1e-12?0:Mth.clamp(-edge[0].dot(v)/v.lengthSqr(),0,1);
            Vec3 p=edge[0].add(v.scale(t));if(p.lengthSqr()<best.lengthSqr())best=p;
        }
        return best;
    }
    public Vec3 nearestSurfaceR50(Vec3 origin)
    {
        Vec3 p=local(origin),best=null;double distance=Double.POSITIVE_INFINITY;
        for(Body body:BODY)
        {
            Vec3 v=p.subtract(body.center),r=body.radii;
            double q=v.x*v.x/(r.x*r.x)+v.y*v.y/(r.y*r.y)+v.z*v.z/(r.z*r.z);
            if(q<=1)return origin;
            double lo=0,hi=Math.max(r.x,Math.max(r.y,r.z))*v.length();
            for(int i=0;i<36;i++)
            {
                double t=(lo+hi)*.5;
                double s=v.x*v.x*r.x*r.x/Math.pow(t+r.x*r.x,2)
                        +v.y*v.y*r.y*r.y/Math.pow(t+r.y*r.y,2)
                        +v.z*v.z*r.z*r.z/Math.pow(t+r.z*r.z,2);
                if(s>1)lo=t;else hi=t;
            }
            Vec3 point=modelPointR50(body.center.add(v.x*r.x*r.x/(hi+r.x*r.x),v.y*r.y*r.y/(hi+r.y*r.y),v.z*r.z*r.z/(hi+r.z*r.z)),1);
            double current=point.distanceToSqr(origin);if(current<distance){distance=current;best=point;}
        }
        return best==null?mouthWorldPos(1):best;
    }
    public boolean coreContactR50(Vec3 point)
    {return entityData.get(MOUTH)>=.65F&&point.distanceTo(coreWorldPos(1))<=5.5*modelScaleR50()+1e-3;}
    public boolean hurtAt(DamageSource source,float amount,Vec3 actualPoint)
    {
        if(actualPoint==null||clipBody(actualPoint,actualPoint,1.5).isEmpty()&&!coreContactR50(actualPoint))return false;
        Vec3 prior=damagePoint;damagePoint=actualPoint;
        try{return hurt(source,amount);}finally{damagePoint=prior;}
    }
    public boolean navalCoreHitR50(DamageSource source,Vec3 actualPoint)
    {
        if(!coreContactR50(actualPoint))return false;
        navalCoreHit=true;try{return hurtAt(source,520F,actualPoint);}finally{navalCoreHit=false;}
    }
    @Override public boolean hurt(DamageSource source,float amount)
    {
        if(level() instanceof ServerLevel server&&!TvMarineDirectorR50.damageAllowed(server,this))return false;
        if(!navalCoreHit&&!nativeProjectileProcessing&&level() instanceof ServerLevel server
                &&source.getDirectEntity() instanceof net.minecraft.world.entity.projectile.Projectile projectile&&TvMarineDirectorR50.isMarineShotR50(projectile))
        {
            nativeProjectileProcessing=true;
            try{return TvMarineDirectorR50.originalProjectileDamageR50(server,this,projectile,source);}
            finally{nativeProjectileProcessing=false;}
        }
        if(navalCoreHit)return super.hurt(source,amount);
        if(!com.projectseele.combat.AtFieldRules.bypassesAtField(source)&&getAtField()>0)
        {
            if(source.getEntity() instanceof EvaUnit01Entity eva&&eva.isMeleeWeapon())
            {
                entityData.set(FIELD,Math.max(0,getAtField()-amount));
                if(level() instanceof ServerLevel server)com.projectseele.fx.AtFieldFX.ripple(server,damagePoint==null?mouthWorldPos(1):damagePoint,eva.getForward());
                return true;
            }
            return false;
        }
        return super.hurt(source,damagePoint!=null&&coreContactR50(damagePoint)?amount:amount*.35F);
    }
    @Override public void tick()
    {
        previousMouth=entityData.get(MOUTH);previousMouthPoint=mouthWorldPos(1);previousSweepPoints=sweepPoints();super.tick();
        setNoGravity(true);setBoundingBox(makeBoundingBox());
        if(level().isClientSide||!isAlive())return;
        if(isNoAi()){setDeltaMovement(Vec3.ZERO);return;}
        if(home==null)home=position();
        entityData.set(SWIM_AGE,(entityData.get(SWIM_AGE)+1)%62800);
        if(heldBy!=null)
        {entityData.set(MOUTH,1F);setDeltaMovement(Vec3.ZERO);return;}
        var target=getTarget();boolean live=target!=null&&target.isAlive();
        Vec3 goal;
        if(live)
        {
            Vec3 targetPoint=com.projectseele.physics.CombatBodyContacts.nearestSurfacePoint(target,mouthWorldPos(1));
            Vec3 radial=position().subtract(targetPoint).multiply(1,0,1).normalize();
            goal=targetPoint.add(radial.scale(44*modelScaleR50())).add(radial.z*18,0,-radial.x*18);
        }
        else
        {
            double phase=entityData.get(SWIM_AGE)*.006;
            goal=home.add(Math.cos(phase)*radiusX*.72,0,Math.sin(phase)*radiusZ*.72);
        }
        double x=home.x+Mth.clamp(goal.x-home.x,-radiusX,radiusX),z=home.z+Mth.clamp(goal.z-home.z,-radiusZ,radiusZ);
        double normalized=Math.sqrt(Math.pow((x-home.x)/radiusX,2)+Math.pow((z-home.z)/radiusZ,2));
        if(normalized>1){x=home.x+(x-home.x)/normalized;z=home.z+(z-home.z)/normalized;}
        double low=seabed+(13+11*entityData.get(MOUTH))*modelScaleR50()+2,high=water-13*modelScaleR50();
        double y=Mth.clamp(home.y+Math.sin(swimPhase(0)*.23)*1.5,low,Math.max(low,high));
        Vec3 delta=new Vec3(x,y,z).subtract(position());
        float wanted=(float)Math.toDegrees(Math.atan2(-delta.x,delta.z));
        setYRot(Mth.approachDegrees(getYRot(),wanted,attackKind()==SWIM?2.8F:1.6F));yBodyRot=yHeadRot=getYRot();
        Vec3 intended=getForward().multiply(1,0,1).normalize().scale(delta.horizontalDistance()>4?.64:.22)
                .add(0,Mth.clamp(delta.y*.06,-.18,.18),0);
        if(cooldown>0)cooldown--;
        Vec3 targetContact=live?com.projectseele.physics.CombatBodyContacts.nearestSurfacePoint(target,mouthWorldPos(1)):null;
        if(attackKind()==SWIM&&live&&cooldown<=0&&mouthWorldPos(1).distanceTo(targetContact)<36*modelScaleR50()+22)
        {
            int selected=choice++%3;entityData.set(ATTACK,selected==0?BITE:selected==1?BREACH:FIN_SWEEP);
            entityData.set(AGE,0);strikeYaw=(float)Math.toDegrees(Math.atan2(-(targetContact.x-getX()),targetContact.z-getZ()));hit.clear();
        }
        if(attackKind()!=SWIM)
        {
            int age=entityData.get(AGE)+1;entityData.set(AGE,age);float phase=age/(float)attackDuration();
            float opening=phase<.22F?phase/.22F:phase<.72F?1:(1-phase)/.28F;
            entityData.set(MOUTH,Mth.clamp(opening,0,1));
            setYRot(attackKind()==FIN_SWEEP?strikeYaw+(float)Math.sin(phase*Math.PI*2)*30:Mth.approachDegrees(getYRot(),strikeYaw,3.5F));yBodyRot=yHeadRot=getYRot();
            intended=getForward().multiply(1,0,1).normalize().scale(.64).add(0,intended.y,0);
            if(attackKind()==BREACH)
            {
                double jump=water-5*modelScaleR50()+Math.sin(Math.PI*phase)*12*modelScaleR50();
                intended=intended.scale(1.5).add(0,Mth.clamp((jump-getY())*.08,-.48,.68),0);
            }
            else if(attackKind()==BITE)intended=intended.scale(phase>.28&&phase<.6?2.25:.4);
            else intended=intended.add(getForward().z*.28,0,-getForward().x*.28);
            if(age>=attackDuration())
            {entityData.set(ATTACK,SWIM);entityData.set(AGE,0);entityData.set(MOUTH,0F);cooldown=54;hit.clear();}
        }
        else entityData.set(MOUTH,.08F);
        // Root movement is bounded before collision; no corrective teleport is used.
        if(Math.abs(getX()-home.x)>=radiusX&&Math.signum(intended.x)==Math.signum(getX()-home.x))intended=new Vec3(-intended.x,intended.y,intended.z);
        if(Math.abs(getZ()-home.z)>=radiusZ&&Math.signum(intended.z)==Math.signum(getZ()-home.z))intended=new Vec3(intended.x,intended.y,-intended.z);
        Vec3 motion=getDeltaMovement().lerp(intended,.18);
        double nextX=getX()+motion.x-home.x,nextZ=getZ()+motion.z-home.z;
        double boundary=Math.sqrt(Math.pow(nextX/radiusX,2)+Math.pow(nextZ/radiusZ,2));
        if(boundary>1)motion=new Vec3(home.x+nextX/boundary-getX(),motion.y,home.z+nextZ/boundary-getZ());
        if(getY()+motion.y<low)motion=new Vec3(motion.x,Math.max(0,(low-getY())*.08),motion.z);
        if(attackKind()!=BREACH&&getY()+motion.y>high)motion=new Vec3(motion.x,Math.min(0,(high-getY())*.08),motion.z);
        setDeltaMovement(motion);move(MoverType.SELF,motion);setBoundingBox(makeBoundingBox());
        if(horizontalCollision){choice++;cooldown=Math.max(cooldown,20);}
        int age=entityData.get(AGE);
        if(attackKind()!=SWIM&&age>attackDuration()*.28&&age<attackDuration()*.7)attackContact();
        if(tickCount%8==0&&level().getFluidState(blockPosition()).is(FluidTags.WATER)&&level() instanceof ServerLevel server)
            server.sendParticles(net.minecraft.core.particles.ParticleTypes.BUBBLE,mouthWorldPos(1).x,getY(),mouthWorldPos(1).z,8,2,1,2,.15);
    }
    private void attackContact()
    {
        if(attackKind()==FIN_SWEEP)
        {
            Vec3[] now=sweepPoints();
            for(int i=0;i<now.length;i++)contactSegment(previousSweepPoints[i],now[i],i==2?3.5:4);
        }
        else contactSegment(previousMouthPoint,mouthWorldPos(1),4);
    }
    private Vec3[] sweepPoints()
    {return new Vec3[]{modelPointR50(new Vec3(-31,0,3),1),modelPointR50(new Vec3(31,0,3),1),modelPointR50(new Vec3(0,0,64),1)};}
    private void contactSegment(Vec3 from,Vec3 to,double radius)
    {
        var wall=level().clip(new net.minecraft.world.level.ClipContext(from,to,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,this));
        if(wall.getType()!=net.minecraft.world.phys.HitResult.Type.MISS)to=wall.getLocation();
        AABB swept=new AABB(from,to).inflate((radius+2)*modelScaleR50());
        for(LivingEntity victim:com.projectseele.physics.CombatEntityQueryR44.candidates(level(),swept,
                e->e.isAlive()&&(e instanceof EvaUnit01Entity||e instanceof net.minecraft.world.entity.player.Player&&!e.isPassenger())))
        {
            if(hit.contains(victim.getUUID()))continue;
            Optional<Vec3> contact=com.projectseele.physics.CombatBodyContacts.clip(victim,from,to,radius*modelScaleR50());
            if(contact.isEmpty())continue;
            hit.add(victim.getUUID());Vec3 direction=to.subtract(from).lengthSqr()>1e-6?to.subtract(from).normalize():getForward();
            EvaHitFeedback.hurt(victim,damageSources().mobAttack(this),attackKind()==BREACH?42:attackKind()==FIN_SWEEP?28:36,contact.get(),direction);
        }
        if(level() instanceof ServerLevel server)TvMarineDirectorR50.cargoContactR50(server,this,from,to);
    }
    @Override public void addAdditionalSaveData(CompoundTag tag)
    {
        super.addAdditionalSaveData(tag);tag.putFloat("MarineScaleR50",modelScaleR50());tag.putFloat("MarineFieldR50",getAtField());
        tag.putInt("MarineAttackR50",attackKind());tag.putInt("MarineAgeR50",entityData.get(AGE));tag.putInt("MarineSwimR50",entityData.get(SWIM_AGE));tag.putFloat("MarineMouthR50",entityData.get(MOUTH));
        tag.putInt("MarineCooldownR50",cooldown);tag.putInt("MarineChoiceR50",choice);tag.putFloat("MarineStrikeYawR50",strikeYaw);
        if(home!=null){tag.putDouble("MarineHomeX",home.x);tag.putDouble("MarineHomeY",home.y);tag.putDouble("MarineHomeZ",home.z);}
        tag.putDouble("MarineRadiusX",radiusX);tag.putDouble("MarineRadiusZ",radiusZ);tag.putDouble("MarineBed",seabed);tag.putDouble("MarineWater",water);
        if(heldBy!=null)tag.putUUID("MarineHeldBy",heldBy);var hits=new ListTag();hit.forEach(id->hits.add(StringTag.valueOf(id.toString())));tag.put("MarineHits",hits);
    }
    @Override public void readAdditionalSaveData(CompoundTag tag)
    {
        super.readAdditionalSaveData(tag);if(tag.contains("MarineScaleR50"))entityData.set(SCALE,Mth.clamp(tag.getFloat("MarineScaleR50"),.2F,1.25F));
        if(tag.contains("MarineFieldR50"))entityData.set(FIELD,Mth.clamp(tag.getFloat("MarineFieldR50"),0,360));
        entityData.set(ATTACK,Mth.clamp(tag.getInt("MarineAttackR50"),0,3));entityData.set(AGE,Mth.clamp(tag.getInt("MarineAgeR50"),0,82));entityData.set(SWIM_AGE,Math.floorMod(tag.getInt("MarineSwimR50"),62800));
        entityData.set(MOUTH,Mth.clamp(tag.getFloat("MarineMouthR50"),0,1));previousMouth=entityData.get(MOUTH);cooldown=Mth.clamp(tag.getInt("MarineCooldownR50"),0,120);choice=tag.getInt("MarineChoiceR50");strikeYaw=tag.getFloat("MarineStrikeYawR50");
        if(tag.contains("MarineHomeX"))home=new Vec3(tag.getDouble("MarineHomeX"),tag.getDouble("MarineHomeY"),tag.getDouble("MarineHomeZ"));
        if(tag.contains("MarineRadiusX")){radiusX=tag.getDouble("MarineRadiusX");radiusZ=tag.getDouble("MarineRadiusZ");seabed=tag.getDouble("MarineBed");water=tag.getDouble("MarineWater");}
        heldBy=tag.hasUUID("MarineHeldBy")?tag.getUUID("MarineHeldBy"):null;
        hit.clear();for(var raw:tag.getList("MarineHits",8))try{hit.add(UUID.fromString(raw.getAsString()));}catch(IllegalArgumentException ignored){}
        setBoundingBox(makeBoundingBox());
    }
}

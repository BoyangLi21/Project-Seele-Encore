package com.projectseele.client;

import com.projectseele.entity.EvaMotionModelR64;
import com.projectseele.entity.EvaSprintR50;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;

/**
 * R64 (M3): the pilot's chase camera for a Unit of the planted model.
 * <p>
 * Up to M2 the camera turned about a point 48 blocks over the entity, lowered by what the step smoothing owed
 * (so it rode every terrace the box was carried up); eight thin rays found what stood behind it; it was cut short
 * the frame a ray hit and let out again at 12 blocks a second, three seconds from a wall to its full distance; and
 * nothing kept it out of its own Unit, so against a wall it sat inside the back.
 * <p>
 * Here the point follows the entity's height eased; what stands behind is found by rays about a circle as wide
 * as the camera needs to see past an edge; a camera that is blocked is first carried higher, where that clears
 * it, and shortened only then; one left closer than the body is deep goes over the head and not into the back;
 * and it is let out at a rate that grows with how far it has to go.
 */
public final class EvaChaseCameraR64
{
    /** Rollback: -Dprojectseele.chaseCameraR64=false keeps the camera as up to M2. */
    private static final boolean ON=!"false".equals(System.getProperty("projectseele.chaseCameraR64"));
    /** The point the camera turns about over the Unit's feet, and how far the camera stays from what it finds (blocks). */
    private static final double PIVOT=48,RADIUS=1.5,MARGIN=.6;
    /**
     * How stiffly that point follows the entity's height (a spring without overshoot, 1/seconds), and the most it
     * may be behind (blocks). Up a slope of one in one the box is carried up three blocks in one tick and stands
     * in the next: eased over 0.16 s and held within 5 blocks the point reached that limit at a run and then went
     * up in the box's own hops, rougher than the step smoothing it replaced (1.6 against 0.8 blocks a tick of
     * unevenness). The spring takes a fortieth of such a hop and is 5.5 blocks behind a run up that slope.
     */
    private static final double FOLLOW=12,LAG_MOST=14;
    /** How much higher the point may be carried to see over what blocks the camera, lowest first (blocks). */
    private static final double[] LIFTS={0,8,16,24};
    /** A lift is taken where it leaves this share of the distance asked for. */
    private static final double ENOUGH=.85;
    /** Closer than this the camera is inside the Unit's back; from there it goes over the head, this far up (blocks). */
    private static final double BODY=18,OVER_HEAD=22;
    /** Blocks a second the point goes up and comes down, and the camera is let out: at least, and per block still to go. */
    private static final double LIFT_UP=40,LIFT_DOWN=14,OUT_LEAST=12,OUT_GAIN=2.5;
    /** A fast run carries the camera this share further back. */
    private static final double SPRINT_OUT=.12;
    /**
     * R64 (M5), frames core only: while the Unit is in a blow with an Angel in reach of its soft lock, the camera
     * stands this share further back and turns about a point carried this share of the way to the Angel (at most
     * so many blocks), so that both bodies are in the picture. The pilot's view is not turned. Eased in over a
     * quarter of a second and out over one. Rollback: -Dprojectseele.lockCameraR64=false.
     */
    private static final double LOCK_OUT=.16,LOCK_SHARE=.22,LOCK_MOST=9,LOCK_IN=.25,LOCK_LEAVE=1.0;
    private static final boolean LOCK=!"false".equals(System.getProperty("projectseele.lockCameraR64"));
    private static double lock;private static Vec3 lockTo=Vec3.ZERO;private static long lockLooked;

    private static int unit=-1;
    private static long frame;
    private static double pivotY,pivotRate,zoom,lift,far,open;

    private EvaChaseCameraR64(){}

    public static boolean owns(EvaUnit01Entity e)
    {
        return ON&&EvaMotionModelR64.planted(e)&&!e.isPilotProne();
    }

    /** What the last frame found: the distance in use, the distance free, how far the point is carried up, how far it is behind the entity. */
    public static double zoom(){return zoom;}
    public static double open(){return open;}
    public static double lift(){return lift;}
    public static double lag(EvaUnit01Entity e,float partial){return pivotY-e.getPosition(partial).y;}

    /**
     * Where the camera is this frame.
     *
     * @param wanted the distance asked for with nothing in the way (blocks)
     */
    public static Vec3 place(EvaUnit01Entity e,Entity subject,float partial,float xRot,float yRot,double wanted)
    {
        long now=System.nanoTime();
        double dt=Math.min(.1,Math.max(0,(now-frame)/1e9));
        boolean fresh=unit!=e.getId()||now-frame>500_000_000L;
        unit=e.getId();frame=now;
        Vec3 at=e.getPosition(partial);
        if(fresh||Math.abs(at.y-pivotY)>40){pivotY=at.y;pivotRate=0;}
        else
        {
            // A critically damped spring, stepped exactly.
            double behind=pivotY-at.y,carried=(pivotRate+FOLLOW*behind)*dt,decay=Math.exp(-FOLLOW*dt);
            pivotRate=(pivotRate-FOLLOW*carried)*decay;
            pivotY=Mth.clamp(at.y+(behind+carried)*decay,at.y-LAG_MOST,at.y+LAG_MOST);
        }
        // The Angel is looked for four times a second; the offset to it is eased, so that a change of target is not a jump.
        boolean fighting=LOCK&&com.projectseele.entity.EvaCombatModelR64.frames(e)&&e.hasLiveActionForRender(partial)&&e.isMeleeWeapon();
        if(fresh){lock=0;lockTo=Vec3.ZERO;}
        if(fighting&&now-lockLooked>250_000_000L)
        {
            lockLooked=now;Vec3 found=null;double least=64*64;
            for(var other:e.level().getEntitiesOfClass(net.minecraft.world.entity.LivingEntity.class,e.getBoundingBox().inflate(64,40,64),
                    o->o instanceof com.projectseele.entity.Angel&&o.isAlive()))
            {
                Vec3 to=other.position().subtract(at).multiply(1,0,1);double d=to.lengthSqr();
                if(d<least){least=d;found=to;}
            }
            if(found==null)fighting=false;
            else{double d=Math.sqrt(least),carried=Math.min(LOCK_MOST,d*LOCK_SHARE);lockTo=d<1e-3?Vec3.ZERO:found.scale(carried/d);}
        }
        lock+=((fighting?1:0)-lock)*(1-Math.exp(-dt/(fighting?LOCK_IN:LOCK_LEAVE)));
        double reach=wanted*(1+SPRINT_OUT*EvaSprintR50.blend(e,partial)+LOCK_OUT*lock);
        far=fresh?reach:far+(reach-far)*(1-Math.exp(-dt/.5));
        Vec3 back=Vec3.directionFromRotation(xRot,yRot).scale(-1);
        BlockGetter level=e.level();

        // Higher, where that sees over what is in the way: the lowest lift that leaves enough, or the one that leaves most.
        double best=-1,chosen=0;
        for(double l:LIFTS)
        {
            double free=free(level,subject,new Vec3(at.x,pivotY+PIVOT+l,at.z),back,far);
            if(free>=far*ENOUGH){best=free;chosen=l;break;}
            if(free>best+2){best=free;chosen=l;}
        }
        // And over the head where even that leaves it against the Unit's back: by as much as it is short.
        chosen=Math.max(chosen,OVER_HEAD*Mth.clamp((BODY-best)/6,0,1));
        // Carried up and let down at a rate, never in one frame: swung into a wall behind the Unit the point
        // went up 22 blocks in three ticks (7 blocks in one).
        lift=fresh?chosen:lift+Mth.clamp(chosen-lift,-LIFT_DOWN*dt,LIFT_UP*dt);
        Vec3 pivot=new Vec3(at.x+lockTo.x*lock,pivotY+PIVOT+lift,at.z+lockTo.z*lock);
        open=free(level,subject,pivot,back,far);
        if(fresh)zoom=open;
        else zoom=Math.min(open,zoom+Math.max(0,Math.min(open-zoom,Math.max(OUT_LEAST,OUT_GAIN*(open-zoom))*dt)));
        zoom=Math.max(zoom,.25);
        Vec3 camera=pivot.add(back.scale(zoom));
        // Whatever the rates leave: never inside the Unit. A camera that would be is over its head.
        if(inUnit(e,partial,camera))camera=new Vec3(camera.x,at.y+63,camera.z);
        return camera;
    }

    /** How far back from a point nothing stands, for a camera with room about it. */
    private static double free(BlockGetter level,Entity subject,Vec3 pivot,Vec3 back,double far)
    {
        Vec3 side=back.cross(new Vec3(0,1,0));
        side=side.lengthSqr()<1e-6?new Vec3(1,0,0):side.normalize();
        Vec3 up=side.cross(back).normalize();
        double least=far;
        for(int i=0;i<9;i++)
        {
            double angle=i*Math.PI/4;
            Vec3 from=i==8?pivot:pivot.add(side.scale(Math.cos(angle)*RADIUS)).add(up.scale(Math.sin(angle)*RADIUS));
            var hit=level.clip(new ClipContext(from,from.add(back.scale(far+MARGIN)),ClipContext.Block.VISUAL,ClipContext.Fluid.NONE,subject));
            if(hit.getType()!=HitResult.Type.MISS)least=Math.min(least,hit.getLocation().distanceTo(from)-MARGIN);
        }
        return Math.max(.25,least);
    }

    /** Review only: the camera is inside the Unit (within the body's depth of its axis, under its head). */
    public static boolean inUnit(EvaUnit01Entity e,float partial,Vec3 camera)
    {
        Vec3 at=e.getPosition(partial);
        return camera.y>at.y&&camera.y<at.y+62&&Math.hypot(camera.x-at.x,camera.z-at.z)<9;
    }
}

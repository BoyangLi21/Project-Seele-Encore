package com.projectseele.entity;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.util.Mth;

/**
 * R64 (flow): one clock for the row a Unit of the frames core has in hand. The server keeps it and tells it once;
 * every client plays the row from it by its own frame time.
 * <p>
 * Up to here the server sent the clip's phase once a tick and a client chased the last one it had. Measured on
 * 2026-11-17 (fable-review/phase8/FLOW_STEP1.zh.md): a blow was first drawn half a tick to two ticks late and ran
 * that far behind; where the frame rate was not a multiple of twenty its pace went 0.5, 1.3, 1.2 times round and
 * round; at a hit the pose was frozen whole for two to eight ticks, one frame before it made up what it was behind
 * (the kick: 1.7 ticks of motion in a frame), and the tick after the hold stepped over one to 2.6 ticks of the
 * clip, the part where fist or blade goes through its mark, which so was never drawn. A string of four presses
 * stood still for twelve of its 27 ticks.
 * <p>
 * What the server tells ({@link Clock}): the row and its clip, how its start-up, live and recovery ticks lie on
 * the clip, and when they come, where the limb is to meet its mark a tick ahead of the hit, and the hit itself
 * with the ticks both bodies are held. The phase it still sends every tick is what it tests the blow by, and what
 * a client sets its clock by: gently, since a packet comes when a frame lets it.
 * <p>
 * What a client draws ({@link View}): the place in the row the server is at, by its own frame time. A hit does not
 * freeze it. The limb comes to its mark and stands there for an instant, then gathers speed through the ticks the
 * bodies are held, and is back on the row's time one tick after the hold: nothing of the clip is stepped over.
 * The place drawn never goes back and never jumps: where it is behind it makes up 0.35 of a tick each tick.
 * <p>
 * The stages lie on the clip along one curve whose pace does not break where they meet ({@link #phase}); up to
 * here they were three straight lines (a kick's start-up played 3.5 times as fast as its recovery).
 * <p>
 * STAND (the owner, 2026-11-17: a Unit takes no stance; it stands as it always stands, and strikes from that).
 * A blow's clip begins and ends in a pose of its own (the punches' in a boxer's, the knife's in a crouch), and
 * the Unit stood in it for as long as the clip's ends lasted. Now a row has a share of the pose ({@link #share}):
 * it comes out of the way the Unit stands or walks over its start-up, is the clip's alone through its live
 * ticks, and goes back over its recovery, so that it ends where the Unit stands. And a row that is left before
 * it has played out (for a step, an evade, a fall) runs on along its clip while what follows takes its place
 * ({@link View#leave}); up to here the legs went from the blow's stance to the walk's in one frame.
 */
public final class EvaRowClockR64
{
    private static final EntityDataAccessor<CompoundTag> CLOCK=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.COMPOUND_TAG);
    /** Register base accessors before any subclass allocates its own IDs. */
    public static boolean bootstrap(){return true;}
    public static void define(SynchedEntityData data){data.define(CLOCK,new CompoundTag());}

    /** A tick of the row a tick, more where the place drawn is behind: so much of a tick is made up each tick. */
    public static final double CATCH=.35;
    /**
     * Ticks in which a blow begun out of another takes its place in the pose: four fifths of its own start-up, as
     * the blend from standing crosses most of a wind-up, and three to seven. (3.5 for every blow, tried first,
     * brought the slam's crouch in out of a jab at 4.4 blocks of hip a tick, where it had been 2.8.)
     */
    public static double fade(int startup){return Math.min(startup+.5,Mth.clamp(.8*startup,3,7));}
    /**
     * STAND: ticks in which a row that was left before it had played out gives its place to what follows it. As
     * many as the release the server captures for a row (EvaGameplayMotionR32, six), which it stands in for.
     */
    public static final double LEAVE=6;
    /**
     * STAND: how much of the pose is the row's at a phase of its clip, by where the row's live part opens and
     * closes on the clip. Through the live part it is one: the blow is tested by the clip's pose, as it was.
     */
    public static float share(float open,float close,float phase)
    {
        if(phase<open)return smooth(phase/Math.max(open,1.0e-4F));
        if(phase>close)return 1-smooth((phase-close)/Math.max(1-close,1.0e-4F));
        return 1;
    }
    private static float smooth(float t){t=Mth.clamp(t,0,1);return t*t*(3-2*t);}
    /**
     * STAND: the share of the pose this row has at a phase of its clip. A clip that itself comes out of a stand
     * and goes back into one (the kick: tools/finale/kick.py) has the pose sooner and keeps it longer; its share
     * only joins it to the way the Unit happens to be standing. (With the whole start-up given to coming out of
     * the stand, the kick's shift of weight and lift of the knee were drawn at a third of their size and then
     * made up in two ticks.)
     */
    public static float share(Clock c,float phase)
    {
        if(!c.own())return share(c.open(),c.close(),phase);
        // (With a stride, the pose is the clip's alone before the stride begins: a tick into the row, which for the
        // kick's ten of start-up is where its clip is at STEP_IN of the way to its live part. While it was still
        // coming out of the stand both feet were carried along under the body through the first of the stride.)
        // (Either kick is written to stand as the Unit stands for that long and no longer: the hard kick changes
        // its feet from three tenths of a tick on.)
        float in=c.step()>0?c.clip().equals("kick")?STEP_IN*c.open():c.phase(1):.3F*c.open(),out=c.close()+.7F*(1-c.close());
        return phase<in?smooth(phase/Math.max(in,1.0e-4F)):phase>out?1-smooth((phase-out)/Math.max(1-out,1.0e-4F)):1;
    }
    /** STEP: the part of the way to its live part by which a kick with a step in has come out of the stand (tools/finale/kick.py: its stride begins after it). */
    public static final float STEP_IN=.045F;
    /** A contact told ahead that has not come this long after its tick is given up. */
    private static final double DUE_GRACE=.75;
    /** How much of what a packet says the clock is off by is taken, and beyond how many ticks it is taken at once. */
    private static final double HEED=.12,FAR=1.5;

    /**
     * The row as the server tells it. hitAt: the tick of the row its blow landed in, or -1; hitPhase: where in the
     * clip the limb met its mark; hold: the ticks both bodies are held after that tick. dueAt, duePhase: the same,
     * told a tick ahead of a hit that has yet to be made (-1: none).
     */
    public record Clock(int serial,String row,String clip,int startup,int live,int recovery,float open,float close,boolean smooth,
                        int hitAt,float hitPhase,int hold,int dueAt,float duePhase,float step,boolean own)
    {
        /** (own: the row's clip is one written out of the stand and back into it, the kick or a blow of tools/finale/unarmed.py.) */
        public Clock(int serial,String row,String clip,int startup,int live,int recovery,float open,float close,boolean smooth,
                     int hitAt,float hitPhase,int hold,int dueAt,float duePhase)
        {this(serial,row,clip,startup,live,recovery,open,close,smooth,hitAt,hitPhase,hold,dueAt,duePhase,0,clip.equals("kick"));}
        public int total(){return startup+live+recovery;}
        public float phase(double place){return EvaRowClockR64.phase(place,startup,live,recovery,open,close,smooth);}
        /** The place in the row, between two ticks of it, at which the clip is at this phase. */
        public double place(float phase,double from,double to)
        {
            double lo=Math.max(0,from),hi=Math.min(total(),Math.max(to,lo));
            if(phase(lo)>=phase)return lo;
            if(phase(hi)<=phase)return hi;
            for(int i=0;i<24;i++){double mid=.5*(lo+hi);if(phase(mid)<phase)lo=mid;else hi=mid;}
            return .5*(lo+hi);
        }
    }

    /**
     * Where in its clip a row is after so many of its ticks. Straight: the start-up to the opening of the live
     * part, the live ticks across it, the recovery to the end, each at its own even pace. Smooth: one curve
     * through the same three places that never turns back and whose pace is the same on both sides of each.
     */
    public static float phase(double place,int startup,int live,int recovery,float open,float close,boolean smooth)
    {
        double end=startup+live+Math.max(1,recovery);
        if(place<=0)return 0;
        if(place>=end)return 1;
        if(!smooth)
        {
            if(place<=startup)return (float)(open*place/startup);
            if(place<=startup+live)return (float)(open+(close-open)*(place-startup)/live);
            return (float)Math.min(1,close+(1-close)*(place-startup-live)/Math.max(1,recovery));
        }
        double[] x={0,startup,startup+live,end},y={0,open,close,1};
        double[] h={x[1]-x[0],x[2]-x[1],x[3]-x[2]},d={(y[1]-y[0])/h[0],(y[2]-y[1])/h[1],(y[3]-y[2])/h[2]};
        double[] m={edge(h[0],h[1],d[0],d[1]),inner(h[0],h[1],d[0],d[1]),inner(h[1],h[2],d[1],d[2]),edge(h[2],h[1],d[2],d[1])};
        int i=place<=x[1]?0:place<=x[2]?1:2;
        double t=(place-x[i])/h[i],t2=t*t,t3=t2*t;
        return (float)Mth.clamp((2*t3-3*t2+1)*y[i]+(t3-2*t2+t)*h[i]*m[i]+(-2*t3+3*t2)*y[i+1]+(t3-t2)*h[i]*m[i+1],0,1);
    }
    /** The pace where two stretches meet: the weighted harmonic mean of theirs (Fritsch and Carlson), which keeps the curve from turning back. */
    private static double inner(double before,double after,double paceBefore,double paceAfter)
    {
        if(paceBefore*paceAfter<=0)return 0;
        double a=2*after+before,b=after+2*before;
        return (a+b)/(a/paceBefore+b/paceAfter);
    }
    /** The pace at an end: by its stretch and the next, never against its stretch and no more than three times it. */
    private static double edge(double own,double next,double paceOwn,double paceNext)
    {
        double m=((2*own+next)*paceOwn-own*paceNext)/(own+next);
        if(m*paceOwn<=0)return 0;
        return Math.abs(m)>3*Math.abs(paceOwn)?3*paceOwn:m;
    }

    // ---- what the server tells ---------------------------------------------------------------------------------

    static void begin(EvaUnit01Entity e,int serial,String row,String clip,int startup,int live,int recovery,float open,float close,boolean smooth)
    {begin(e,serial,row,clip,startup,live,recovery,open,close,smooth,false);}
    /** own: the row's clip is one written out of the stand and back into it (Clock.own). */
    static void begin(EvaUnit01Entity e,int serial,String row,String clip,int startup,int live,int recovery,float open,float close,boolean smooth,boolean own)
    {
        var tag=new CompoundTag();
        if(own)tag.putBoolean("bd",true);
        tag.putInt("s",serial);tag.putString("n",row);tag.putString("k",clip);
        tag.putInt("a",startup);tag.putInt("b",live);tag.putInt("c",recovery);tag.putFloat("o",open);tag.putFloat("x",close);tag.putBoolean("f",smooth);
        tag.putInt("hn",-1);tag.putInt("pn",-1);
        e.getEntityData().set(CLOCK,tag);
    }
    /** The limb is to meet its mark in this tick of the row, at this phase of its clip. */
    static void due(EvaUnit01Entity e,int at,float phase)
    {
        var old=e.getEntityData().get(CLOCK);
        if(old.isEmpty()||old.getInt("pn")==at&&Math.abs(old.getFloat("pp")-phase)<.004F)return;
        var tag=old.copy();tag.putInt("pn",at);tag.putFloat("pp",phase);
        e.getEntityData().set(CLOCK,tag);
    }
    /** The blow has landed in this tick of the row, the limb at this phase, and both bodies are held so many ticks. */
    static void hit(EvaUnit01Entity e,int at,float phase,int hold)
    {
        var old=e.getEntityData().get(CLOCK);
        if(old.isEmpty())return;
        var tag=old.copy();tag.putInt("hn",at);tag.putFloat("hp",phase);tag.putInt("hh",hold);
        e.getEntityData().set(CLOCK,tag);
    }
    /** STEP: the share of its clip's step the row in hand takes over the ground (the kick's step in; one where it is not told). */
    static void step(EvaUnit01Entity e,float share)
    {
        var old=e.getEntityData().get(CLOCK);
        if(old.isEmpty())return;
        var tag=old.copy();tag.putFloat("st",share);
        // where the body stands as the row begins: a client that carries it through the step sets out from there
        if(share>0){tag.putDouble("sx",e.getX());tag.putDouble("sz",e.getZ());}
        e.getEntityData().set(CLOCK,tag);
    }
    /** Either side: the share of its clip's stride the row in hand takes over the ground; one for a row that was told none. */
    static float stride(EvaUnit01Entity e)
    {
        var tag=tag(e);
        return tag!=null&&tag.contains("st")?tag.getFloat("st"):1;
    }
    /** Client: where the body stood as the kick in hand began with its step (x, z), or null where none is told. */
    static double[] stepFrom(EvaUnit01Entity e)
    {
        var tag=tag(e);
        return tag!=null&&tag.contains("sx")?new double[]{tag.getDouble("sx"),tag.getDouble("sz")}:null;
    }
    /**
     * Either side: the share of its step the kick in hand takes, or the last one took (a client goes on drawing a
     * kick that was left for a few ticks after its clock is gone). The server has it from where it began the row.
     */
    static float step(EvaUnit01Entity e)
    {
        if(e.level().isClientSide)
        {
            var tag=tag(e);
            if(tag!=null&&tag.contains("st"))e.rowStepShareR64=tag.getFloat("st");
        }
        return e.rowStepShareR64;
    }
    static void end(EvaUnit01Entity e)
    {
        if(e.getEntityData().hasItem(CLOCK)&&!e.getEntityData().get(CLOCK).isEmpty())e.getEntityData().set(CLOCK,new CompoundTag());
    }
    static boolean told(SynchedEntityData.DataValue<?> value){return value.id()==CLOCK.getId();}
    /** Either side: what the Unit carries of its row's clock (empty: no row), or null on a Unit without one. */
    static CompoundTag tag(EvaUnit01Entity e){return e.getEntityData().hasItem(CLOCK)?e.getEntityData().get(CLOCK):null;}

    static Clock read(CompoundTag tag)
    {
        if(tag==null||tag.isEmpty()||tag.getString("n").isEmpty())return null;
        return new Clock(tag.getInt("s"),tag.getString("n"),tag.getString("k"),Math.max(1,tag.getInt("a")),Math.max(1,tag.getInt("b")),Math.max(1,tag.getInt("c")),
                tag.getFloat("o"),tag.getFloat("x"),tag.getBoolean("f"),tag.getInt("hn"),tag.getFloat("hp"),tag.getInt("hh"),tag.getInt("pn"),tag.getFloat("pp"),
                tag.getFloat("st"),tag.getBoolean("bd"));
    }

    // ---- what a client draws -----------------------------------------------------------------------------------

    /**
     * What follows a row is taking its place in the pose: the row's clip, where it has run on to, how much of the
     * pose is the new one's, and (STAND) the share the row itself has of the pose where it has run on to.
     */
    public record Fade(String clip,float phase,float weight,float share){}

    /** One Unit's row as one client plays it. Times are in ticks of that client's own frame clock. */
    public static final class View
    {
        private Clock clock,before,gone;
        /** The server's count of the row's ticks is the time less this, were nothing to hold it. */
        private double base,beforeBase,goneBase;
        /** The place drawn last, and when. */
        private double place,at,beforePlace,beforeAt,fadeFrom,gonePlace,goneAt,goneFrom;
        private int heard;
        private boolean out;
        private CompoundTag seen;
        private Clock parsed;

        /** Client, any frame: the phase to draw of the row the Unit carries, or -1 when it carries none. */
        float frame(EvaUnit01Entity e,double time)
        {
            if(!e.getEntityData().hasItem(CLOCK))return -1;
            var tag=e.getEntityData().get(CLOCK);
            if(tag!=seen){seen=tag;parsed=read(tag);}
            return frame(parsed,time);
        }

        /** The row as told now (null: none) and the time: the phase to draw, or -1. */
        public float frame(Clock told,double time)
        {
            if(told==null)
            {
                // The row is over. Left before it had played out, it runs on beside what follows it (leave).
                if(clock!=null&&place<clock.total()-.5){gone=clock;goneBase=base;gonePlace=place;goneAt=at;goneFrom=time;}
                clock=null;before=null;return -1;
            }
            if(clock==null||clock.serial()!=told.serial())
            {
                // Another row. The one in hand, if it had not played out, runs on beside it for the fade.
                if(clock!=null&&place<clock.total()-.5){before=clock;beforeBase=base;beforePlace=place;beforeAt=at;fadeFrom=time;}
                else before=null;
                out=before!=null;
                // The server has made the row's first tick; this frame draws it from its beginning.
                clock=told;base=time-1;place=0;at=time;heard=0;
            }
            else clock=told;
            if(time>at)
            {
                double to=target(clock,base,time);
                place=follow(place,to,Math.max(0,to-target(clock,base,at)),time-at);at=time;
            }
            if(before!=null)
            {
                if(time-fadeFrom>=fade())before=null;
                else if(time>beforeAt)
                {
                    double to=target(before,beforeBase,time);
                    beforePlace=follow(beforePlace,to,Math.max(0,to-target(before,beforeBase,beforeAt)),time-beforeAt);beforeAt=time;
                }
            }
            return clock.phase(place);
        }

        /**
         * The server's phase has come, as it does once a tick while the row plays. It says which tick of the row
         * the server has made; the clock is moved towards that by a part of what it is off, at once only when it
         * is far off (a stall).
         */
        public void heard(float phase,double time)
        {
            if(clock==null)return;
            if(clock.hitAt()>=0&&Math.abs(phase-clock.hitPhase())<1.0e-4F)return;    // set back to its contact, for the hold
            double made=clock.place(phase,0,clock.total()),tick=Math.rint(made);
            if(Math.abs(made-tick)>.2||tick<1||clock.phase(tick+.5)-clock.phase(tick-.5)<.004F)return;
            double held=clock.hitAt()>=0&&tick>clock.hitAt()?clock.hold():0;
            double off=time-tick-held-base;
            heard++;
            base+=Math.abs(off)>FAR?off:off*Math.max(HEED,1.0/(heard+1));
        }

        /** The blow in hand is taking another's place: that one's clip and phase and the new one's share. Null otherwise. */
        public Fade fade(double time)
        {
            if(before==null||clock==null)return null;
            double t=Mth.clamp((time-fadeFrom)/fade(),0,1);
            float phase=before.phase(beforePlace);
            return new Fade(before.clip(),phase,(float)(t*t*(3-2*t)),share(before,phase));
        }
        /**
         * STAND: a row was left before it had played out. It runs on along its clip for LEAVE ticks while what
         * follows takes its place: its clip and phase, the share of the pose that is already what follows, and
         * the row's own share where it has run on to. Null when there is none.
         */
        public Fade leave(double time)
        {
            if(gone==null)return null;
            double t=(time-goneFrom)/LEAVE;
            if(t>=1){gone=null;return null;}
            if(time>goneAt)
            {
                double to=target(gone,goneBase,time);
                gonePlace=follow(gonePlace,to,Math.max(0,to-target(gone,goneBase,goneAt)),time-goneAt);goneAt=time;
            }
            float phase=gone.phase(gonePlace);t=Math.max(0,t);
            return new Fade(gone.clip(),phase,(float)(t*t*(3-2*t)),share(gone,phase));
        }
        private double fade(){return clock==null?3:EvaRowClockR64.fade(clock.startup());}

        /**
         * STEP: the phase the row in hand is to be drawn at at a time to come, or -1 where the row in hand does
         * not play this clip. A client moves the body by it a tick ahead (EvaUnit01Entity.stepRootR64): what a
         * tick moves is drawn between that tick's place and the one before.
         */
        public float ahead(double time)
        {
            if(clock==null)return -1;
            // where the place drawn will have got to by then (frame): not where it is to be, which it may still
            // be making up to (a body moved by that went ahead of its legs by as much)
            double to=target(clock,base,time);
            return clock.phase(time>at?follow(place,to,Math.max(0,to-target(clock,base,at)),time-at):place);
        }
        /** The row in hand as the server counts its rows, or -1. */
        public int serial(){return clock==null?-1:clock.serial();}
        /** The clip of the row in hand, or null. */
        public String clip(){return clock==null?null:clock.clip();}
        /** The row in hand began out of another that had not played out. */
        public boolean outOfAnother(){return clock!=null&&out;}
        /** The row in hand is played by this clock (it was told, and has not ended). */
        public boolean playing(){return clock!=null;}
        /** Review: the place in the row drawn last, in its ticks. */
        public double place(){return place;}
    }

    /**
     * The place in the row to be drawn at a time: the server's count of its ticks, but for the hit. Before a hit
     * that is told (or told ahead) the limb goes no further than where it meets its mark. From the tick of the
     * hit, through the ticks the bodies are held and one more, it goes from there to the next tick's place along a
     * curve that starts from a stand and gathers speed; after that it is the server's count again, which was held
     * as long. (The curve is a square at the steepest. One steep enough to end at the row's own pace, tried
     * first, stood all but still for two and a half of a kick's three held ticks: the freeze again.)
     */
    static double target(Clock c,double base,double time)
    {
        double count=time-base,to;
        if(c.hitAt()>=0)
        {
            double met=c.place(c.hitPhase(),c.hitAt()-3,c.hitAt()),since=count-c.hitAt(),span=c.hitAt()+1-met;
            int ticks=c.hold()+1;
            if(since<=0)to=Math.min(count,met);
            else if(since<ticks)to=met+span*Math.pow(since/ticks,Mth.clamp(ticks/Math.max(span,1.0e-3),1,2));
            else to=count-c.hold();
        }
        else if(c.dueAt()>=0&&count<=c.dueAt()+DUE_GRACE)to=Math.min(count,c.place(c.duePhase(),c.dueAt()-1,c.dueAt()));
        else to=count;
        return Mth.clamp(to,0,c.total());
    }

    /** The place drawn goes on towards where it is to be: never back, and where it is behind, at the pace of a tick a tick (or its mark's, if faster) and CATCH more. */
    static double follow(double place,double to,double advance,double dt)
    {
        return to<=place?place:Math.min(to,place+Math.max(advance,dt)+CATCH*dt);
    }

    private EvaRowClockR64(){}
}

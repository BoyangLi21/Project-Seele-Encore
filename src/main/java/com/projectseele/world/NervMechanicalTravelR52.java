package com.projectseele.world;

import net.minecraft.nbt.CompoundTag;

/** Time only. Directory samples and their geometric path fraction retain
 * their existing meaning, including exact forward/reverse sweep proofs. */
public final class NervMechanicalTravelR52
{
    public static double fraction(int clock,int ticks)
    {
        if(ticks<=0||clock<0||clock>ticks)throw new IllegalArgumentException("Actual bounded mechanical leg clock required");
        double t=clock/(double)ticks;return t*t*t*(t*(t*6-15)+10);
    }
    public static int restoredClock(CompoundTag data,String route,int leg,int ticks,double fraction)
    {
        if(!Double.isFinite(fraction)||fraction<0||fraction>1)return -1;
        if(!data.contains("LegClockR52")||!data.getString("LegClockRouteR52").equals(route)||data.getInt("LegClockIndexR52")!=leg)
            return fraction==0?0:-1;
        int clock=data.getInt("LegClockR52");return clock>=0&&clock<=ticks&&data.getInt("LegClockTicksR52")==ticks&&Math.abs(fraction(clock,ticks)-fraction)<=1e-12?clock:-1;
    }
    public static void remember(CompoundTag data,String route,int leg,int ticks,int clock)
    {fraction(clock,ticks);data.putInt("LegClockR52",clock);data.putString("LegClockRouteR52",route);data.putInt("LegClockIndexR52",leg);data.putInt("LegClockTicksR52",ticks);}
    /** One analytic distance clock for an entire declared run; leg boundaries do not enter the profile. */
    public record ContinuousProfile(double fromMetres,double toMetres,double cruiseMps,double accelerationMps2,double decelerationMps2,double initialMps)
    {
        public ContinuousProfile(double from,double to,double cruise,double acceleration,double deceleration){this(from,to,cruise,acceleration,deceleration,0);}
        public ContinuousProfile{if(!Double.isFinite(fromMetres+toMetres+cruiseMps+accelerationMps2+decelerationMps2)||fromMetres<0||toMetres<=fromMetres||cruiseMps<=0||accelerationMps2<=0||decelerationMps2<=0||!Double.isFinite(initialMps)||initialMps<0||initialMps>cruiseMps||initialMps*initialMps/(2*decelerationMps2)>toMetres-fromMetres+1e-6)throw new IllegalArgumentException("Finite positive continuous distance/velocity profile required");}
        public double peakMps(){return Math.max(initialMps,Math.min(cruiseMps,Math.sqrt((2*(toMetres-fromMetres)+initialMps*initialMps/accelerationMps2)/(1/accelerationMps2+1/decelerationMps2))));}
        public double accelerationSeconds(){return Math.max(0,(peakMps()-initialMps)/accelerationMps2);}
        public double decelerationSeconds(){return peakMps()/decelerationMps2;}
        public double cruiseSeconds(){double v=peakMps();return Math.max(0,((toMetres-fromMetres)-(v*v-initialMps*initialMps)/(2*accelerationMps2)-v*v/(2*decelerationMps2))/v);}
        public double durationSeconds(){return accelerationSeconds()+cruiseSeconds()+decelerationSeconds();}
        public double distanceAt(double ticks){if(!Double.isFinite(ticks)||ticks<0)throw new IllegalArgumentException("Monotone route tick required");double t=Math.min(ticks/20D,durationSeconds()),a=accelerationSeconds(),c=cruiseSeconds(),v=peakMps();if(t>=durationSeconds())return toMetres;if(t<=a)return fromMetres+initialMps*t+.5*accelerationMps2*t*t;double first=.5*(initialMps+v)*a;if(t<=a+c)return fromMetres+first+v*(t-a);double d=t-a-c;return fromMetres+first+v*c+v*d-.5*decelerationMps2*d*d;}
        // Distance may round to the endpoint one ulp before duration. Both
        // queries must then report the same stopped state, including on reload.
        public double speedAt(double ticks){if(!Double.isFinite(ticks)||ticks<0)throw new IllegalArgumentException("Monotone route tick required");double t=ticks/20D,a=accelerationSeconds(),c=cruiseSeconds();if(t>=durationSeconds()||distanceAt(ticks)>=toMetres)return 0;if(t<a)return initialMps+accelerationMps2*t;if(t<=a+c)return peakMps();return Math.max(0,peakMps()-decelerationMps2*(t-a-c));}
    }
    public record ContinuousClock(ContinuousProfile profile,long ticks)
    {public ContinuousClock{if(ticks<0)throw new IllegalArgumentException("Nonnegative persisted route clock required");}public double distance(){return profile.distanceAt(ticks);}public double speed(){return profile.speedAt(ticks);}public ContinuousClock next(){if(ticks==Long.MAX_VALUE)throw new IllegalStateException("Route clock overflow");return new ContinuousClock(profile,ticks+1);}public boolean complete(){return distance()==profile.toMetres();}}
    public static ContinuousClock continuousClock(CompoundTag data,String route,String fingerprint,double currentMetres,double totalMetres,double stopMetres,double cruise,double acceleration,double deceleration)
    {
        var stored=data.getCompound("ContinuousClockR52");if(stored.isEmpty()&&currentMetres!=0&&!data.getBoolean("ContinuousCheckedStartR52"))throw new IllegalStateException("Moved original lost its continuous distance/speed clock");if(stored.isEmpty())return new ContinuousClock(new ContinuousProfile(currentMetres,stopMetres,cruise,acceleration,deceleration),0);
        // Apply the requested doubled transfer speed from its current position
        // and velocity, including a trip saved before the update.
        if(stored.getString("Route").equals(route)&&stored.getString("Directory").equals(fingerprint)&&stored.getDouble("TotalMetres")==totalMetres&&stored.getDouble("ToMetres")==stopMetres
                &&cruise==stored.getDouble("CruiseMps")*2&&acceleration==stored.getDouble("AccelerationMps2")*4&&deceleration==stored.getDouble("DecelerationMps2")*4&&!data.contains("ContinuousBrakeR52"))
        {
            var before=new ContinuousClock(new ContinuousProfile(stored.getDouble("FromMetres"),stopMetres,stored.getDouble("CruiseMps"),stored.getDouble("AccelerationMps2"),stored.getDouble("DecelerationMps2"),stored.getDouble("InitialMps")),stored.getLong("Ticks"));
            if(Math.abs(before.distance()-currentMetres)>1e-6||Math.abs(before.speed()-stored.getDouble("SpeedMps"))>1e-9)throw new IllegalStateException("Speed update requires the actual current distance and velocity");
            if(before.complete())return before;
            var updated=new ContinuousClock(new ContinuousProfile(currentMetres,stopMetres,cruise,acceleration,deceleration,before.speed()),0);
            rememberContinuous(data,route,fingerprint,totalMetres,updated);return updated;
        }
        if(!stored.getString("Route").equals(route)||!stored.getString("Directory").equals(fingerprint)||stored.getDouble("TotalMetres")!=totalMetres||stored.getDouble("ToMetres")!=stopMetres||stored.getDouble("CruiseMps")!=cruise||stored.getDouble("AccelerationMps2")!=acceleration||stored.getDouble("DecelerationMps2")!=deceleration)throw new IllegalStateException("Saved continuous route/profile identity changed");
        var clock=new ContinuousClock(new ContinuousProfile(stored.getDouble("FromMetres"),stopMetres,cruise,acceleration,deceleration,stored.getDouble("InitialMps")),stored.getLong("Ticks"));if(Math.abs(clock.distance()-currentMetres)>1e-6||Math.abs(clock.distance()-stored.getDouble("DistanceMetres"))>1e-6||Math.abs(clock.speed()-stored.getDouble("SpeedMps"))>1e-9)throw new IllegalStateException("Saved route distance/speed does not match the actual snapshot");return clock;
    }
    public static double brakingDistanceR52(double speed,double deceleration)
    {if(!Double.isFinite(speed)||!Double.isFinite(deceleration)||speed<0||deceleration<=0)throw new IllegalArgumentException("Actual nonnegative speed and positive braking force required");return speed*speed/(2*deceleration);}
    /** Starts physical deceleration from the accepted speed without changing current position. */
    public static void brakeContinuousR52(CompoundTag data,String route,String fingerprint,double total,String reason)
    {
        if(!SetReasonR52(reason))throw new IllegalArgumentException("Explicit cancel/blocker braking reason required");
        var row=data.getCompound("ContinuousClockR52");
        if(row.isEmpty())throw new IllegalStateException("Braking requires its actual saved continuous clock");
        if(data.contains("ContinuousBrakeR52")){if(reason.equals("CANCEL"))data.putString("ContinuousBrakeR52",reason);return;}
        var clock=continuousClock(data,route,fingerprint,row.getDouble("DistanceMetres"),total,row.getDouble("ToMetres"),row.getDouble("CruiseMps"),row.getDouble("AccelerationMps2"),row.getDouble("DecelerationMps2"));
        double speed=clock.speed(),at=clock.distance();
        if(speed==0){rememberContinuous(data,route,fingerprint,total,clock);return;}
        if(!data.contains("ContinuousResumeStopR52"))data.putDouble("ContinuousResumeStopR52",row.getDouble("ToMetres"));
        double end=at+brakingDistanceR52(speed,row.getDouble("DecelerationMps2"));
        if(end>total+1e-6)throw new IllegalStateException("Current actual speed has no admitted braking distance before route end");
        end=Math.min(total,end);
        var profile=new ContinuousProfile(at,end,row.getDouble("CruiseMps"),row.getDouble("AccelerationMps2"),row.getDouble("DecelerationMps2"),speed);
        rememberContinuous(data,route,fingerprint,total,new ContinuousClock(profile,0));data.putString("ContinuousBrakeR52",reason);
    }
    private static boolean SetReasonR52(String reason){return "CANCEL".equals(reason)||"BLOCKED".equals(reason);}
    /** A queued launch extends the same run from its accepted distance and velocity; no leg reset. */
    public static void extendContinuousR52(CompoundTag data,String route,String fingerprint,double total)
    {var stored=data.getCompound("ContinuousClockR52");if(data.contains("ContinuousBrakeR52")){if(!data.getString("ContinuousBrakeR52").equals("CANCEL"))data.putDouble("ContinuousResumeStopR52",total);return;}if(stored.isEmpty()||stored.getDouble("ToMetres")==total)return;var old=continuousClock(data,route,fingerprint,stored.getDouble("DistanceMetres"),total,stored.getDouble("ToMetres"),stored.getDouble("CruiseMps"),stored.getDouble("AccelerationMps2"),stored.getDouble("DecelerationMps2"));rememberContinuous(data,route,fingerprint,total,new ContinuousClock(new ContinuousProfile(old.distance(),total,old.profile().cruiseMps(),old.profile().accelerationMps2(),old.profile().decelerationMps2(),old.speed()),0));}
    public static void rememberContinuous(CompoundTag data,String route,String fingerprint,double totalMetres,ContinuousClock clock)
    {var p=clock.profile();var tag=new CompoundTag();tag.putString("Route",route);tag.putString("Directory",fingerprint);tag.putDouble("TotalMetres",totalMetres);tag.putDouble("FromMetres",p.fromMetres());tag.putDouble("ToMetres",p.toMetres());tag.putDouble("CruiseMps",p.cruiseMps());tag.putDouble("AccelerationMps2",p.accelerationMps2());tag.putDouble("DecelerationMps2",p.decelerationMps2());tag.putDouble("InitialMps",p.initialMps());tag.putLong("Ticks",clock.ticks());tag.putDouble("DistanceMetres",clock.distance());tag.putDouble("SpeedMps",clock.speed());data.put("ContinuousClockR52",tag);}
    private NervMechanicalTravelR52(){}
}

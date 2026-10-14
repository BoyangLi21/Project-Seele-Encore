package com.projectseele.entity;

import net.minecraft.util.Mth;

/** Rigid lift-and-stack shutters fitting the existing 42 metre shaft pitch. */
public final class SiloHatchMechanism
{
    public static final int PANELS = 4;
    public static final double WIDTH = 4.0D;
    public static final double POCKET_X = 16.4D;
    public static final double CASE_OUTER_X = 20.7D;
    public static final double PANEL_TOP = .98D;

    public record Panel(double x, double y) {}
    public record Spec(float openingX,float openingZ,int openTicks,int closeTicks,int separationSign,double beamBottom,boolean serviceColumnPorts,boolean uprightGuidePorts,int serviceGantryYawDegrees,int uprightGuideEarlyVariant)
    {
        public Spec{if(uprightGuideEarlyVariant < -1||uprightGuideEarlyVariant > 2||uprightGuideEarlyVariant>=0&&!uprightGuidePorts)throw new IllegalArgumentException("Early guide fitting belongs only to the three explicitly declared bank3 upper hatches");if(serviceGantryYawDegrees!=0&&serviceGantryYawDegrees!=180||!serviceColumnPorts&&serviceGantryYawDegrees!=0)throw new IllegalArgumentException("Explicit service gantry relative yaw0/180 belongs only to service column ports");if(!Float.isFinite(openingX+openingZ)||openingX<=0||openingZ<=0||openTicks<=0||closeTicks<=0||Math.abs(separationSign)!=1||!Double.isFinite(beamBottom)||beamBottom>=-.35||serviceColumnPorts&&(openingX!=33||openingZ!=33||separationSign!=-1)||uprightGuidePorts&&(openingX!=31||openingZ!=31||separationSign!=1||serviceColumnPorts))throw new IllegalArgumentException("Actual positive hatch aperture/clocks and explicit tier/bearing direction required");if(openingX==31&&openingZ==31&&separationSign<0)throw new IllegalArgumentException("Declared R52 net31 uses upward tiers; original collar does not support downward travel");}
        public Spec(float x,float z,int open,int close,int sign,double bottom,boolean servicePorts,boolean uprightPorts,int gantryYaw){this(x,z,open,close,sign,bottom,servicePorts,uprightPorts,gantryYaw,-1);}
        public Spec(float x,float z,int open,int close,int sign,double bottom,boolean servicePorts,boolean uprightPorts){this(x,z,open,close,sign,bottom,servicePorts,uprightPorts,0);}
        public Spec(float x,float z,int open,int close,int sign,double bottom,boolean servicePorts){this(x,z,open,close,sign,bottom,servicePorts,false);}
        public Spec(float x,float z,int open,int close){this(x,z,open,close,1,-2.01,false);}
        public Spec(float x,float z,int open,int close,int sign,double bottom){this(x,z,open,close,sign,bottom,false);}
        public Spec withUprightGuideEarlyVariant(int variant){return new Spec(openingX,openingZ,openTicks,closeTicks,separationSign,beamBottom,serviceColumnPorts,uprightGuidePorts,serviceGantryYawDegrees,variant);}
        public double firstTier(){return serviceColumnPorts?1.62:1.1;}
        public double maximumTier(){return firstTier()+3*1.1;}
        // The preserved original gantry datum is 2.04m above the service
        // beam's unchanged bearing plane. It is never relocated by a hatch.
        public double serviceColumnDatumOffsetY(){return beamBottom+2.04;}
        public com.projectseele.world.RigidTransform serviceGantryRelativeFrame(){return new com.projectseele.world.RigidTransform(new net.minecraft.world.phys.Vec3(0,serviceColumnDatumOffsetY(),0),0,serviceGantryYawDegrees==180?1:0,0,serviceGantryYawDegrees==0?1:0);}
        public boolean compact(){return openingX>31&&openingX<64;}
        public double panelWidth(){return compact()?openingX/(2D*PANELS):(openingX+1D)/(2*PANELS);}
        public double pocketX(){return openingX/2D+(compact()?.15*openingX/33D:.9D);}
        public double innerTrim(){return compact()?.1*openingX/33D:.35D;}
        public double outerTrim(){return compact()?.1*openingX/33D:.3D;}
        public double caseOuterX(){return pocketX()+panelWidth()+outerTrim();}
    }
    public static Panel panel(int index,float open,Spec spec)
    {
        if(index<0||index>=PANELS||!Float.isFinite(open)||open<0||open>1)throw new IllegalArgumentException("Actual hatch panel/sample required");
        if(spec==null)return panel(index,open);
        double lift=smooth(open/.30F),travel=smooth((open-.30F)/.70F),closed=index*spec.panelWidth();
        return new Panel(closed+(spec.pocketX()-closed)*travel,spec.separationSign()*(spec.firstTier()+(PANELS-1-index)*1.10D)*lift);
    }

    public static Panel panel(int index, float open)
    {
        // Separate the tiers before translating: a panel never passes through
        // the panel above it, the frame, or the neighbouring shaft's mechanism.
        double lift = smooth(open / .30F);
        double travel = smooth((open - .30F) / .70F);
        double closedX = index * WIDTH;
        return new Panel(closedX + (POCKET_X - closedX) * travel,
                (1.10D + (PANELS - 1 - index) * 1.10D) * lift);
    }

    private static double smooth(float value)
    {
        double t = Mth.clamp(value, 0, 1);
        return t * t * (3 - 2 * t);
    }

    private SiloHatchMechanism() {}
}

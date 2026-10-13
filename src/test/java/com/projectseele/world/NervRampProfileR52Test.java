package com.projectseele.world;

public final class NervRampProfileR52Test
{
    public static void main(String[] args)
    {
        var ramp=new NervRampProfileR52(27.5,160,6);var back=ramp.reversed(204);
        if(!ramp.reversed(328.275985956192-124.275985956192).sameGeometry(back))throw new AssertionError("Original measured sole coordinates changed reverse geometry");
        exact(ramp.heightFraction(204,20./204),0); // The rejected straight chord rose 3.137m here.
        exact(ramp.heightFraction(204,27.5/204),0);
        exact(ramp.heightFraction(204,107.5/204),.5);
        exact(ramp.heightFraction(204,187.5/204),1);
        exact(ramp.heightFraction(204,200./204),1);
        double bound=ramp.secondDerivativeBound(204,32,1),worst=0;
        for(int i=0;i<=10000;i++)
        {
            double t=i/10000.;exact(ramp.heightFraction(204,t)+back.heightFraction(204,1-t),1);
        }
        // Every interior point of each source profile chord must remain in
        // the claimed curvature envelope, including both rounded shoulders.
        for(int n:new int[]{1,7,31,173})for(int i=0;i<n;i++)for(int j=1;j<40;j++)
        {
            double a=i/(double)n,b=(i+1)/(double)n,f=j/40.;
            double line=32*(ramp.heightFraction(204,a)*(1-f)+ramp.heightFraction(204,b)*f);
            double actual=32*ramp.heightFraction(204,a+(b-a)*f),error=Math.abs(actual-line);
            if(error>bound/(8*n*n)+1e-10)throw new AssertionError("Uncertified ramp chord");worst=Math.max(worst,error);
        }
        if(worst<3)throw new AssertionError("Original straight-line failure was not exercised");
        System.out.println("Original ramp 27.5 / 160 / 16.5 verified; exact reverse and source-curve sweep bound pass");
    }
    private static void exact(double actual,double expected){if(Math.abs(actual-expected)>1e-12)throw new AssertionError(actual+" != "+expected);}
}

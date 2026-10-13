package com.projectseele.entity;

/** Delayed frames must not reverse several forward packets received together. */
public final class EvaPoseSignalClockTest
{
    private record Source(int melee,int heavy,int kick) { }
    private static void actionSnapshots()
    {
        for(boolean phaseFirst:new boolean[]{false,true})
        {
            var clock=new EvaPoseSignalClock();var old=new Source(7,0,0);
            clock.acceptActionAt(old,.046153843F,true,3_000_000_000L);
            int sequence=7;float phase=.046153843F;
            // Either per-field order finishes before the one batch callback.
            if(phaseFirst){phase=.01F;sequence=8;}else{sequence=8;phase=.01F;}
            var next=new Source(sequence,0,0);
            clock.acceptActionAt(next,phase,true,3_050_000_000L);
            for(int repeat=0;repeat<8;repeat++)
                if(clock.sample(3_050_000_000L)!=.01F)
                    throw new AssertionError("Positive first phase inherited its old source");
            // The next source can arrive in the SAME client tick/frame.
            clock.acceptActionAt(new Source(9,0,0),.015F,true,3_050_000_000L);
            if(clock.sample(3_050_000_000L)!=.015F)
                throw new AssertionError("Same client tick hid a distinct action source");
            var current=new Source(9,0,0);
            clock.acceptActionAt(current,.055F,true,3_100_000_000L);
            float halfway=clock.sample(3_125_000_000L);
            clock.acceptActionAt(current,.055F,false,3_125_000_000L);
            if(Math.abs(halfway-.035F)>1e-6F||clock.sample(3_125_000_000L)!=halfway)
                throw new AssertionError("Unrelated metadata reset the accepted interpolation window");
        }
        for(var source:new Source[]{new Source(0,0,0),new Source(73,18,4)})
        {
            var firstSync=new EvaPoseSignalClock();firstSync.acceptActionAt(source,.6F,false,4_000_000_000L);
            var rejoin=new EvaPoseSignalClock();rejoin.acceptActionAt(source,.6F,true,5_000_000_000L);
            if(firstSync.sample(4_000_000_000L)!=.6F||rejoin.sample(5_000_000_000L)!=.6F)
                throw new AssertionError("Initial synchronized/rejoined sequence lost its actual source phase");
        }
        System.out.println("Pose clock: complete metadata snapshots in both field orders, same-tick source change, initial/rejoined sequence and unrelated metadata PASS");
    }
    public static void main(String[] args)
    {
        actionSnapshots();
        for(float prior:new float[]{.02F,1F/(20F*(65F/60F)),.05F})
        {
            var restart=new EvaPoseSignalClock();restart.snapAt(0,1_000_000_000L);
            restart.acceptAt(prior,false,true,1_050_000_000L);
            restart.acceptAt(0,false,true,1_600_000_000L);
            for(int i=0;i<8;i++)
                if(restart.sample(1_600_000_000L)!=0)
                    throw new AssertionError("Early cancelled source seeded its next action: "+prior);
            restart.acceptAt(.04F,false,true,1_650_000_000L);
            float halfway=restart.sample(1_675_000_000L);
            if(Math.abs(halfway-.02F)>1e-6F)
                throw new AssertionError("New action did not retain its normal interpolation window");
        }
        var jitter=new EvaPoseSignalClock();jitter.snapAt(.06F,2_000_000_000L);
        jitter.acceptAt(.05F,false,true,2_050_000_000L);
        if(jitter.sample(2_050_000_000L)!=.06F)
            throw new AssertionError("Nonzero minor packet correction stopped smoothing");
        System.out.println("Pose clock: early zero-endpoint restart and nonzero jitter continuity PASS");
        var clock=new EvaPoseSignalClock();clock.snap(0);
        clock.accept(.25F,true,false);clock.accept(.5F,true,false);clock.accept(.75F,true,false);
        float forward=clock.sample(System.nanoTime()+60_000_000L);
        if(Math.abs(forward-.75F)>.001F)throw new AssertionError("Forward packet burst reversed its cycle: "+forward);
        clock.accept(0F,true,false);clock.accept(.25F,true,false);
        float wrapped=clock.sample(System.nanoTime()+60_000_000L);
        if(Math.abs(wrapped-1.25F)>.001F)throw new AssertionError("Cycle seam lost accepted travel: "+wrapped);
        clock.accept(0F,true,false);clock.accept(.75F,true,false);
        float reverse=clock.sample(System.nanoTime()+60_000_000L);
        if(Math.abs(reverse-.75F)>.001F)throw new AssertionError("Backward packets cannot reverse: "+reverse);
        System.out.println("Pose clock: delayed forward bursts, cycle seam and deliberate reversal PASS");
    }
}

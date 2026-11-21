package com.projectseele.physics;

public final class SupportedRecoveryR65Test
{
    public static void main(String[] args)
    {
        var support=new CombatBodyDynamics.SupportedRecovery();
        for(int age=1;age<240;age++)
            if(support.ready(age,3,.06*.06))throw new AssertionError("Ordinary rest timer shortened");
        if(!support.ready(240,3,.06*.06))throw new AssertionError("Resting UN rig did not get up");
        for(int age=241;age<500;age++)
            if(support.ready(age,0,0))throw new AssertionError("Stalled body got up in midair");
        for(int age=500;age<530;age++)
            if(support.ready(age,5,.5*.5))throw new AssertionError("A sliding body got up");
        for(int age=530;age<540;age++)
            if(support.ready(age,2,0)!=(age==539))throw new AssertionError("Ground support window did not restart");
        // A Unit other than UN-00: lying, moving 0.12 blocks a tick as the R65 captures have it.
        var unit=new CombatBodyDynamics.SupportedRecovery();
        int least=CombatBodyDynamics.SupportedRecovery.UNIT_LEAST_R65;
        for(int age=1;age<least;age++)
            if(unit.ready(age,3,.12*.12,least))throw new AssertionError("A Unit lying quietly got up before its time");
        if(!unit.ready(least,3,.12*.12,least))throw new AssertionError("A Unit lying quietly did not get up");
        if(unit.ready(least+1,3,.4*.4,least))throw new AssertionError("A Unit sliding over the ground got up");
    }
}

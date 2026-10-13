package com.projectseele.entity;

/** Visual optic policy. Enemy/clip age, battery counters and joints are not changed. */
public final class EvaEyePolicyR52
{
    public static final int NORMAL=0,DARK=1,RED=2;
    public record Facts(boolean standardUnit01,boolean powered,boolean berserk,
                        boolean silent,boolean wreck,boolean dormant,
                        boolean directedScene,boolean socketSealed){}
    public record State(boolean enabled,int surface){}

    public static State resolve(Facts facts)
    {
        if(facts==null)throw new IllegalArgumentException("Actual optic facts required");
        int dark=facts.standardUnit01()?DARK:NORMAL;
        if(facts.silent()||facts.wreck())return new State(false,dark);
        // Autonomous activity owns red until the actual EVA stop transition.
        // Exhausted batteries, old socket interpolation and a stale dormant
        // flag cannot substitute the Angel's death for that transition.
        if(facts.berserk())return new State(true,facts.standardUnit01()?RED:NORMAL);
        if(facts.directedScene()&&facts.powered())return new State(true,NORMAL);
        if(!facts.powered()||facts.dormant())return new State(false,dark);
        return new State(facts.socketSealed(),NORMAL);
    }
    private EvaEyePolicyR52(){}
}

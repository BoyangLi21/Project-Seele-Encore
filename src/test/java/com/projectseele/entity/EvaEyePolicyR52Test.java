package com.projectseele.entity;

/** Pure rule/transition regression; no entities, texture draw, game or pixel acceptance. */
public final class EvaEyePolicyR52Test
{
    private static int checks;
    private static EvaEyePolicyR52.State state(boolean powered,boolean berserk,boolean silent,
            boolean wreck,boolean dormant,boolean scene,boolean sealed)
    {return EvaEyePolicyR52.resolve(new EvaEyePolicyR52.Facts(true,powered,berserk,silent,wreck,dormant,scene,sealed));}
    private static void expect(EvaEyePolicyR52.State actual,boolean enabled,int surface,String why)
    {
        checks++;
        if(actual.enabled()!=enabled||actual.surface()!=surface)throw new AssertionError(why+": "+actual);
    }
    public static void main(String[] args)
    {
        expect(state(false,true,true,false,false,false,true),false,1,"36-tick pre-awakening silence stays black");
        expect(state(false,true,false,false,false,false,true),true,2,"Roar/autonomous activity is red without battery");
        // The actor facts remain active at Angel death and throughout the
        // remaining scene. Only the real completion clears berserk/dormant.
        for(String label:new String[]{"before Angel death","Angel death tick372","after death tick400","last active tick459"})
            expect(state(true,true,false,false,false,true,true),true,2,label);
        expect(state(false,false,false,false,true,false,true),false,1,"Actual tick460 completion/POWER_LOCK is black");
        expect(state(true,false,false,false,true,false,true),false,1,"Post-berserk dormant remains black despite late powered metadata");
        expect(state(true,false,false,false,false,false,true),true,0,"Rearmed healthy sealed body restores normal eyes");
        expect(state(true,false,false,false,false,true,false),true,0,"Ordinary finale ignores old open/bow interpolation");
        expect(state(true,false,false,false,true,true,false),true,0,"Powered new scene owns normal over stale dormant flag");
        expect(state(false,false,false,false,false,true,true),false,1,"A real unpowered ordinary actor stays black");
        expect(state(true,false,false,true,false,true,true),false,1,"Actual wreck stays black during scene");
        expect(state(true,true,true,false,true,true,false),false,1,"Real silent phase takes priority over stale flags");
        for(boolean powered:new boolean[]{false,true})for(boolean dormant:new boolean[]{false,true})
            for(boolean scene:new boolean[]{false,true})for(boolean sealed:new boolean[]{false,true})
                expect(state(powered,true,false,false,dormant,scene,sealed),true,2,"Active berserk survives battery/socket/dormant/scene combinations");
        expect(state(true,false,false,false,false,false,false),false,0,"Ordinary open-capsule optic remains nonemissive normal paint");
        expect(EvaEyePolicyR52.resolve(new EvaEyePolicyR52.Facts(false,true,false,false,false,false,false,true)),true,0,"Other/experimental variants keep their own normal material");
        expect(EvaEyePolicyR52.resolve(new EvaEyePolicyR52.Facts(false,false,false,false,false,false,false,true)),false,0,"Unit01 dark material is not installed on other variants");
        boolean rejected=false;try{EvaEyePolicyR52.resolve(null);}catch(IllegalArgumentException expected){rejected=true;}
        checks++;if(!rejected)throw new AssertionError("Missing facts were accepted");
        System.out.println("R52 optic policy PASS checks="+checks+"; rules only, no native/pixel acceptance");
    }
    private EvaEyePolicyR52Test(){}
}

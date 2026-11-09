package com.projectseele.world;

/** A greyed-out phone control names the missing pass, or only contacts who can actually do it. */
public final class StaffDenialReasonsTest
{
    private static void expect(String actual,String expected)
    {
        if(!actual.equals(expected))throw new AssertionError("Expected \""+expected+"\" but got \""+actual+"\"");
    }
    public static void main(String[] args)
    {
        expect(StaffAuthorityR25.denial(false,"misato","city_rise"),"需要 NERV 通行证");
        expect(StaffAuthorityR25.denial(true,"misato","city_rise"),"需要联络冬月");
        expect(StaffAuthorityR25.denial(true,"ritsuko","launch"),"需要联络美里或冬月");
        expect(StaffAuthorityR25.denial(true,"maya","prepare"),"需要联络美里、律子或冬月");
        expect(StaffAuthorityR25.denial(true,"maya",StaffAuthorityR25.COMMAND),"需要联络美里、律子或冬月");
        expect(StaffAuthorityR25.denial(true,"maya","synch_lab"),"该联络人没有此权限");
        String[][] contacts={{"misato","美里"},{"ritsuko","律子"},{"fuyutsuki","冬月"},{"maya","摩耶"}};
        int checked=0;
        for(String operation:new String[]{"prepare","launch","recover","deploy","board","weapons","campaign","city_rise","city_lower"})
            for(String[] caller:contacts)
            {
                if(StaffAuthorityR25.allows("",caller[0],operation))continue;
                String reason=StaffAuthorityR25.denial(true,caller[0],operation);
                for(String[] other:contacts)
                {
                    boolean able=!other[0].equals(caller[0])&&StaffAuthorityR25.allows("",other[0],operation);
                    if(reason.contains(other[1])!=able)throw new AssertionError(operation+" refused for "+caller[0]+" names the wrong contacts: "+reason);
                }
                checked++;
            }
        System.out.println("StaffDenialReasonsTest PASS: 6 fixed reasons, "+checked+" refused contact/operation pairs name only able contacts");
    }
}

package com.projectseele.compat;

import java.util.Set;
import java.util.TreeSet;
import java.util.concurrent.ConcurrentHashMap;

/** JDK-only transformation witness; safe for the optional-mod mixin bootstrap. */
public final class CityUnionActivationR45
{
    public static final String DEV_CREATE_SHA256="5b2aaa88430e90a94371615b3100112f70ca5cd70f27f3a5f34b76ad023dfcb3";
    private static final Set<String> APPLIED=ConcurrentHashMap.newKeySet();
    private static volatile String actualCreateSHA256="", backendReason="Not evaluated", actualCreateResource="";
    private static volatile boolean backendEligible;
    private CityUnionActivationR45() {}
    public static String expectedCreateSHA256()
    {
        String value=System.getProperty("projectseele.r45CityCreateContraptionSHA256",DEV_CREATE_SHA256);
        return value.matches("[0-9a-f]{64}")?value:null;
    }
    public static boolean required(){return Boolean.getBoolean("projectseele.r45CityBalancedUnionRequired");}
    public static void backend(String actual,boolean eligible,String reason)
    {actualCreateSHA256=actual;backendEligible=eligible;backendReason=reason;}
    public static void backendAbi(String resource,boolean eligible,String reason)
    {actualCreateResource=resource;backendEligible=eligible;backendReason=reason;}
    public static void applied(String mixin)
    {
        if(mixin.endsWith("CityExactUnionCreateMixinR45"))APPLIED.add("CityExactUnionCreateMixinR45");
        if(mixin.endsWith("CitySavedOwnerUnionMixinR45"))APPLIED.add("CitySavedOwnerUnionMixinR45");
    }
    public static String requiredFailure(boolean proofValid)
    {
        if(!required())return null;
        if(!Boolean.getBoolean("projectseele.r45CityBalancedUnion"))return "Required exact union was not requested";
        if(!backendEligible)return "Create producer was not accepted: "+backendReason;
        if(!proofValid)return "Current runtime native input/union contract is not ready";
        if(!APPLIED.contains("CityExactUnionCreateMixinR45")||!APPLIED.contains("CitySavedOwnerUnionMixinR45"))return "Actual required city mixin postApply witnesses are missing";
        return null;
    }
    public static String actualCreateSHA256(){return actualCreateSHA256;}
    public static String actualCreateResource(){return actualCreateResource;}
    public static String backendReason(){return backendReason;}
    public static boolean backendEligible(){return backendEligible;}
    public static Set<String> appliedMixins(){return Set.copyOf(new TreeSet<>(APPLIED));}
}

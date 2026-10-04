package com.projectseele.physics;

import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Reach an authored rigid chain without replacing its knee's captured twist. */
public final class AuthoredTwoBoneIKR45
{
    public record Result(Vector3f middle, Vector3f end, Quaternionf upperSwing,
                         Quaternionf lowerSwing) { }

    public static Result solve(Vector3f origin, Vector3f middle, Vector3f end,
                               Vector3f requested, Vector3f bendFallback)
    {
        return solve(origin,middle,end,requested,bendFallback,null);
    }

    public static Result solveWithPole(Vector3f origin,Vector3f middle,Vector3f end,
                                       Vector3f requested,Vector3f pole,Vector3f bendFallback)
    {
        return solve(origin,middle,end,requested,bendFallback,pole);
    }

    private static Result solve(Vector3f origin,Vector3f middle,Vector3f end,
                                Vector3f requested,Vector3f bendFallback,Vector3f pole)
    {
        Vector3f upper=new Vector3f(middle).sub(origin);
        Vector3f lower=new Vector3f(end).sub(middle);
        float a=upper.length(), b=lower.length();
        if(a<1e-5F||b<1e-5F||!requested.isFinite())return null;
        // An unmodified contact must not be re-solved into another hinge pose.
        if(requested.distanceSquared(end)<1e-10F&&(pole==null||pole.distanceSquared(middle)<1e-10F))
            return new Result(new Vector3f(middle),new Vector3f(end),new Quaternionf(),new Quaternionf());
        Vector3f direction=new Vector3f(requested).sub(origin);
        float length=direction.length();
        if(length<1e-6F)return null;
        direction.div(length);
        length=Math.max(Math.abs(a-b)+1e-5F,Math.min(a+b-1e-5F,length));
        float along=(a*a-b*b+length*length)/(2*length);
        Vector3f bend=pole==null?new Vector3f(upper):new Vector3f(pole).sub(origin);
        bend.fma(-bend.dot(direction),direction);
        if(bend.lengthSquared()<1e-10F)
            bend.set(bendFallback).fma(-bendFallback.dot(direction),direction);
        if(bend.lengthSquared()<1e-10F)return null;
        bend.normalize();
        Vector3f solvedMiddle=new Vector3f(origin).fma(along,direction)
                .fma((float)Math.sqrt(Math.max(0,a*a-along*along)),bend);
        Vector3f solvedEnd=new Vector3f(origin).fma(length,direction);
        Quaternionf upperSwing=new Quaternionf().rotationTo(upper,new Vector3f(solvedMiddle).sub(origin));
        Quaternionf lowerSwing=new Quaternionf().rotationTo(lower,new Vector3f(solvedEnd).sub(solvedMiddle));
        return new Result(solvedMiddle,solvedEnd,upperSwing,lowerSwing);
    }

    private AuthoredTwoBoneIKR45() { }
}

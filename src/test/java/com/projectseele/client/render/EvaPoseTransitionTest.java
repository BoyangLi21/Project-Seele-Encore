package com.projectseele.client.render;

import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.GeoBone;

/** Checks the actual production transition kernel without a game client. */
public final class EvaPoseTransitionTest
{
    private static final Class<?> POSE;
    private static final Constructor<?> POSE_CTOR;
    private static final Constructor<?> TRACK_CTOR;
    private static final Method BEGIN;
    private static final Method UPDATE;
    private static final Method SAMPLE;
    private static final Method POSITION;
    private static final Method ROTATION;
    private static final Method WRITE;

    static
    {
        try
        {
            POSE = Class.forName("com.projectseele.client.render.EvaPoseTransition$Pose");
            Class<?> track = Class.forName("com.projectseele.client.render.EvaPoseTransition$Track");
            POSE_CTOR = POSE.getDeclaredConstructor(Quaternionf.class, Vector3f.class, Vector3f.class);
            TRACK_CTOR = track.getDeclaredConstructor(POSE);
            BEGIN = track.getDeclaredMethod("begin");
            UPDATE = track.getDeclaredMethod("update", POSE, double.class);
            SAMPLE = track.getDeclaredMethod("sample", POSE, double.class, double.class);
            POSITION = POSE.getDeclaredMethod("position");
            ROTATION = POSE.getDeclaredMethod("rotation");
            WRITE = POSE.getDeclaredMethod("write", GeoBone.class);
            POSE_CTOR.setAccessible(true); TRACK_CTOR.setAccessible(true);
            for (Method method : new Method[] {BEGIN, UPDATE, SAMPLE, POSITION, ROTATION, WRITE})
                method.setAccessible(true);
        }
        catch (Exception exception)
        {
            throw new ExceptionInInitializerError(exception);
        }
    }

    private static Object pose(float x, float angle) throws Exception
    {
        return POSE_CTOR.newInstance(new Quaternionf().rotationY(angle),
                new Vector3f(x, -12, 4), new Vector3f(1, 1, 1));
    }

    private static Vector3f position(Object pose) throws Exception
    {
        return (Vector3f)POSITION.invoke(pose);
    }

    private static void equal(Object expected, Object actual) throws Exception
    {
        if (position(expected).distance(position(actual)) > 0.0001F
                || Math.abs(((Quaternionf)ROTATION.invoke(expected))
                    .dot((Quaternionf)ROTATION.invoke(actual))) < 0.999999F)
            throw new AssertionError("Pose discontinuity or unsettled endpoint");
    }

    private static void quaternionChannels() throws Exception
    {
        var random=new java.util.Random(360041);
        var bone=new GeoBone(null,"arm_r",false,0D,false,false);
        for(int i=0;i<2400;i++)
        {
            float x=(random.nextFloat()*2-1)*(float)Math.PI,z=(random.nextFloat()*2-1)*(float)Math.PI;
            float y=i<1200?(i%2==0?1:-1)*(float)(Math.PI/2+(i%3-1)*1e-6):(random.nextFloat()*2-1)*(float)Math.PI;
            var original=new Quaternionf().rotationZYX(z,y,x);
            WRITE.invoke(POSE_CTOR.newInstance(original,new Vector3f(),new Vector3f(1)),bone);
            var restored=new Quaternionf().rotationZYX(bone.getRotZ(),bone.getRotY(),bone.getRotX());
            for(var axis:new Vector3f[]{new Vector3f(1,0,0),new Vector3f(0,1,0),new Vector3f(0,0,1)})
                if(original.transform(new Vector3f(axis)).distance(restored.transform(new Vector3f(axis)))>2e-4F)
                    throw new AssertionError("Rendered rotation changed near a vertical axis: "+i);
        }
        System.out.println("Actual pose write: 2400 regular and gimbal-axis orientations retain all three basis vectors PASS");
    }

    public static void main(String[] args) throws Exception
    {
        quaternionChannels();
        Object start = pose(3, 3.12F);
        Object end = pose(43, -3.12F);
        Object track = TRACK_CTOR.newInstance(start);
        BEGIN.invoke(track);
        equal(start, SAMPLE.invoke(track, end, 0.0D, 0.20D));
        equal(end, SAMPLE.invoke(track, end, 0.20D, 0.20D));
        Object middle = SAMPLE.invoke(track, end, 0.10D, 0.20D);
        Quaternionf q = (Quaternionf)ROTATION.invoke(middle);
        if (Math.abs(q.y) < 0.999F) throw new AssertionError("Long-path turn across +/- pi");
        for (int fps : new int[] {30, 60, 144})
        {
            Object replay = TRACK_CTOR.newInstance(start);
            BEGIN.invoke(replay);
            for (int i = 1; i <= fps; i++)
                SAMPLE.invoke(replay, end, i / (double)fps, 0.20D);
            equal(middle, SAMPLE.invoke(replay, end, 0.10D, 0.20D));
        }
        UPDATE.invoke(track, middle, .10D);
        BEGIN.invoke(track);
        equal(middle, SAMPLE.invoke(track, pose(-90, 1), 0.0D, 0.28D));
        equal(end, SAMPLE.invoke(track, end, .28D, .28D));
        Object moving = TRACK_CTOR.newInstance(pose(0, 0));
        Object source = pose(.04F, .02F);
        UPDATE.invoke(moving, source, .02D);
        BEGIN.invoke(moving);
        Object epsilon = SAMPLE.invoke(moving, pose(100, 2), .0001D, .20D);
        float velocity = (position(epsilon).x - position(source).x) / .0001F;
        if (Math.abs(velocity - 2.0F) > .02F)
            throw new AssertionError("Lost incoming velocity: " + velocity);
        System.out.println("EVA pose transition: endpoints, shortest arc, frame rates, interruption, socket position and velocity PASS");
    }
}

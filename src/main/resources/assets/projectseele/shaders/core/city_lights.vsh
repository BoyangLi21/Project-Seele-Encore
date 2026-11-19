#version 330 core
layout(location=0) in vec3 anchor;
layout(location=1) in vec3 light;  // kind, outward face, owner
layout(location=2) in vec3 tower;  // street height, full displacement, district
uniform mat4 pose, projection;
uniform vec3 eye;
uniform vec4 viewport;
uniform float nativeRange, retraction[100], brightness[8];
uniform bool haveLod;
uniform samplerBuffer terrainHeights;
uniform ivec4 terrainBounds; // Origin X/Z, width and height in eight-block tiles.
out vec4 tint;
out float sceneDepth;
bool clearSurveyRay(vec3 p) {
    vec2 delta=p.xz-eye.xz;
    float span=length(delta);
    vec2 direction=delta/max(span,.001);
    // Nearby foreground uses the native depth test. End before the lamp's own facade.
    float t=min(24.,nativeRange*.35), end=span-6.;
    if (end<=t) return true;
    vec2 grid=(eye.xz-vec2(terrainBounds.xy)+direction*t)/8.;
    ivec2 tile=ivec2(floor(grid)), inc=ivec2(sign(direction));
    vec2 stepT=8./max(abs(direction),vec2(.000001));
    vec2 border=t+(mix(fract(grid),1.-fract(grid),greaterThan(direction,vec2(0))))*stepT;
    for (int i=0;i<640 && t<end;i++) {
        if(any(lessThan(tile,ivec2(0))) || any(greaterThanEqual(tile,terrainBounds.zw))) return false;
        float exitT=min(end,min(border.x,border.y));
        float minY=eye.y+(p.y-eye.y)*(p.y<eye.y?exitT:t)/span;
        float surface=texelFetch(terrainHeights,tile.y*terrainBounds.z+tile.x).r;
        if(surface>minY) return false;
        if(border.x<border.y){t=border.x;border.x+=stepT.x;tile.x+=inc.x;}
        else {t=border.y;border.y+=stepT.y;tile.y+=inc.y;}
    }
    return t>=end;
}

void main() {
    int owner=int(light.z), face=int(light.y), kind=int(light.x);
    vec3 p=anchor;
    float power=brightness[int(tower.z)];
    if(owner>=0) {
        float f=retraction[owner];
        p.y+=tower.y*f;
        if(f<0.0 || p.y<tower.x+.5) power=0.0;
    }
    vec3 normal=face==0?vec3(-1,0,0):face==1?vec3(1,0,0):face==2?vec3(0,0,-1):face==3?vec3(0,0,1):vec3(0);
    p+=normal*.53;
    vec3 toward=eye-p;
    float d=length(toward);
    if(face!=4) power*=smoothstep(.03,.42,dot(normal,toward/max(1.,d)));
    float start=clamp(nativeRange*.58,48.,150.);
    power*=smoothstep(start,start+48.,d)*(1.-smoothstep(3200.,4250.,d));
    vec4 clip=projection*pose*vec4(p-eye,1.);
    if(!haveLod && d>nativeRange*.82 && clip.w>1. && power>=.001 && all(lessThan(abs(clip.xy),vec2(clip.w+2.)))) {
        if(!clearSurveyRay(p)) power*=1.-smoothstep(nativeRange*.82,nativeRange,d);
    }
    if(clip.w<=1. || power<.001){gl_Position=vec4(2,2,2,1);gl_PointSize=1.;tint=vec4(0);sceneDepth=1.;return;}
    // Near geometry keeps its normal depth test. Clamp only clipping at the native far plane.
    sceneDepth=.5*(1.-projection[2][2]+projection[3][2]/max(1.,clip.w-2.));
    clip.z=min(clip.z,clip.w*.9999999);gl_Position=clip;
    float pixelScale=viewport.w*projection[1][1]/(2.*clip.w);
    gl_PointSize=clamp(pixelScale*(kind==2?1.8:1.),kind==3?2.1:1.55,5.5);
    float variant=fract(dot(anchor.xz,vec2(.0973,.0711)));
    vec3 rgb=kind==3?vec3(1.,.13,.045):kind==2?vec3(1.,.78,.46):mix(vec3(.76,.88,1.),vec3(1.,.84,.58),variant);
    tint=vec4(rgb,power*(kind==1?.67:.88));
}

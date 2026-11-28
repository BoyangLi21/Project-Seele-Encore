#version 330 core
layout(location=0) in vec4 frame;
layout(location=1) in vec4 rect;
layout(location=2) in vec4 sizeOwner;
layout(location=3) in vec4 pigment;
uniform mat4 pose,projection;
uniform vec3 eye;
uniform float retraction[100],nativeRange,daylight,power[8];
flat out vec3 tint;
out float surveyY, viewDistance;
const vec2 uv[6]=vec2[](vec2(0,0),vec2(1,0),vec2(1,1),vec2(0,0),vec2(1,1),vec2(0,1));
void main(){
    float f=retraction[int(sizeOwner.z)];
    vec2 st=rect.zw+uv[gl_VertexID]*sizeOwner.xy;
    int side=int(rect.x);
    vec3 local=side<2?vec3(rect.y,st.y,st.x):side<4?vec3(st.x,st.y,rect.y):vec3(st.x,rect.y,st.y);
    vec3 world=frame.xyz+local+vec3(0,frame.w*f,0);
    vec3 n=side==0?vec3(1,0,0):side==1?vec3(-1,0,0):side==2?vec3(0,0,1):side==3?vec3(0,0,-1):vec3(0,1,0);
    vec3 delta=world-eye;
    if(f<0. || max(abs(frame.x-eye.x),abs(frame.z-eye.z))<nativeRange || dot(n,delta)>0.) {
        gl_Position=vec4(2,2,2,1);surveyY=-1.;viewDistance=0.;tint=vec3(0);return;
    }
    vec4 clip=projection*pose*vec4(delta,1.);
    // Preserve native foreground occlusion while accepting silhouettes beyond its far plane.
    clip.z=min(clip.z,clip.w*.9999999);
    gl_Position=clip;
    surveyY=world.y-frame.y;viewDistance=length(delta);
    float shade=side==4?1.:side==1?.76:side==0?.90:side==2?.84:.70;
    vec3 day=pigment.rgb*(.70+.30*shade);
    vec3 night=pigment.rgb*vec3(.15,.19,.29)*shade;
    night=mix(night,vec3(.96,.79,.49),pigment.w*power[int(sizeOwner.w)]*.89);
    tint=mix(night,day,smoothstep(.02,.90,daylight));
}

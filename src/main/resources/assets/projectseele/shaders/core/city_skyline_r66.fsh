#version 330 core
uniform sampler2D lod, nativeDepth;
uniform mat4 projection;
uniform bool haveLod;
uniform vec2 lodTransform;
uniform vec4 viewport;
uniform vec3 fogTint;
in float surveyY,viewDistance;
flat in vec3 tint;
out vec4 colour;
void main(){
    if(surveyY<.01)discard;
    vec2 uv=(gl_FragCoord.xy-viewport.xy)/viewport.zw;
    // Hardware interpolates reciprocal view Z linearly in screen space. Interpolating
    // the divided vertex depths as smooth varyings made diagonal strips appear on facades.
    float viewZ=1./gl_FragCoord.w;
    float native=texture(nativeDepth,uv).r;
    float projected=.5*(1.-projection[2][2]+projection[3][2]/viewZ);
    float behindNative=.5*(1.-projection[2][2]+projection[3][2]/(viewZ+.50));
    if(native<1. && behindNative>=native)discard;
    if(haveLod){
        float d=texture(lod,uv).r;
        if(d<1. && projected>lodTransform.x*d+lodTransform.y+.00000009)discard;
    }
    // Independent monotonic depth keeps windows, frames and roofs ordered past the native far plane.
    gl_FragDepth=viewZ/(viewZ+256.);
    colour=vec4(mix(tint,fogTint,clamp((viewDistance-150.)/4200.,0.,.66)),1.);
}

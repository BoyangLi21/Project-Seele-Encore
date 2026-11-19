#version 330 core
uniform bool haveLod;
uniform vec4 viewport;
uniform vec2 lodTransform;
uniform sampler2D lod;
in vec4 tint;
in float sceneDepth;
out vec4 colour;
void main() {
    if(haveLod){
        float z=texture(lod,(gl_FragCoord.xy-viewport.xy)/viewport.zw).r;
        if(z<1. && sceneDepth>lodTransform.x*z+lodTransform.y+0.00000006) discard;
    }
    float r=length(gl_PointCoord-vec2(.5))*2.;
    if(r>=1.)discard;
    colour=vec4(tint.rgb,tint.a*(1.-smoothstep(.15,1.,r)));
}

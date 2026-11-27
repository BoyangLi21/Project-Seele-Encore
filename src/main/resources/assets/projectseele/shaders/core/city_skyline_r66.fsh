#version 330 core
uniform sampler2D lod;
uniform bool haveLod;
uniform vec2 lodTransform;
uniform vec4 viewport;
uniform vec3 fogTint;
in float surveyY,originalDepth,viewDistance;
flat in vec3 tint;
out vec4 colour;
void main(){
    if(surveyY<.01)discard;
    if(haveLod){
        float d=texture(lod,(gl_FragCoord.xy-viewport.xy)/viewport.zw).r;
        if(d<1. && originalDepth>lodTransform.x*d+lodTransform.y+.00000009)discard;
    }
    colour=vec4(mix(tint,fogTint,clamp((viewDistance-150.)/4200.,0.,.66)),1.);
}

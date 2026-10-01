#version 150
#moj_import <light.glsl>
#moj_import <fog.glsl>
in vec3 Position;
in vec4 Color;
in vec2 UV0;
in ivec2 UV1;
in ivec2 UV2;
in vec3 Normal;
uniform sampler2D Sampler1;
uniform sampler2D Sampler2;
uniform mat4 ModelViewMat;
uniform mat4 ProjMat;
uniform mat4 BoneMat;
uniform mat3 BoneNormal;
uniform mat3 IViewRotMat;
uniform vec2 FrameLight;
uniform vec2 FrameOverlay;
uniform int FogShape;
uniform vec3 Light0_Direction;
uniform vec3 Light1_Direction;
out float vertexDistance;
out vec4 vertexColor;
out vec4 lightMapColor;
out vec4 overlayColor;
out vec2 texCoord0;
out vec4 normal;
void main() {
    vec4 posed = BoneMat * vec4(Position, 1.0);
    vec3 posedNormal = normalize(BoneNormal * Normal);
    gl_Position = ProjMat * ModelViewMat * posed;
    vertexDistance = fog_distance(ModelViewMat, IViewRotMat * posed.xyz, FogShape);
    vertexColor = minecraft_mix_light(Light0_Direction, Light1_Direction, posedNormal, Color);
    lightMapColor = texelFetch(Sampler2, ivec2(FrameLight) / 16, 0);
    overlayColor = texelFetch(Sampler1, ivec2(FrameOverlay), 0);
    texCoord0 = UV0;
    normal = ProjMat * ModelViewMat * vec4(posedNormal, 0.0);
}

#version 330 core
uniform sampler2D lights;
in vec2 uv;
out vec4 colour;
void main() {
    colour=vec4(texture(lights,uv).rgb*.72,0.);
}

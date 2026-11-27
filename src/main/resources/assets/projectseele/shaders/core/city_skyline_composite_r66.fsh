#version 330 core
uniform sampler2D skyline;
in vec2 uv;
out vec4 colour;
void main(){colour=texture(skyline,uv);}

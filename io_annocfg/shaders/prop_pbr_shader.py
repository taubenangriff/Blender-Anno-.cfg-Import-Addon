import bpy
from .shader_base import AnnoBasicShader
from .shader_components import *
from .shader_node_templates import ShaderTemplate

from ..utils import to_data_path
import os
from pathlib import Path
from ..prefs import IO_AnnocfgPreferences

class SimplePBRPropShader(AnnoBasicShader):

    def __init__(self):
        super().__init__()

        self.shader_id = "SimplePBRPropShader"

        self.compose(DefaultPropComponent())
        self.compose(CommonShaderComponent())
        self.compose(AdditionalPBRShaderComponent())
        self.compose(TerrainAdaptionShaderComponent())
        self.compose(EnvironmentShaderComponent())
        self.compose(GlowShaderComponent())
        self.add_link(FlagLink("Force Alphablending", "FORCE_ALPHA_BLEND"))
        self.add_link(FlagLink("Disable Revive Distance", "DisableReviveDistance"))

        # override default vertexformat
        self.material_properties.clear()

    def create_anno_shader(self):
        anno_shader = bpy.data.node_groups.new(self.shader_id, 'ShaderNodeTree')

        for l in self.links: 
            if not l.has_socket():
                continue

            socket = anno_shader.interface.new_socket(socket_type = l.socket_type, name = l.link_key, in_out = 'INPUT')
            if l.has_default_value():
                socket.default_value = l.default_value    
        
        anno_shader.interface.new_socket(socket_type = "NodeSocketShader", name = "Shader", in_out='OUTPUT')
                
        shader_template = ShaderTemplate(anno_shader)
        diff = shader_template.add_diffuse("cDiffuse", "cDiffuseMultiplier")
        shader_template.add_dye(diff)
        shader_template.add_normal("cNormal")
        shader_template.add_gloss("Glossiness")
        shader_template.add_metallic("cMetallic")
        shader_template.add_emission(diff, "cEmissiveColor", "cNightGlow")
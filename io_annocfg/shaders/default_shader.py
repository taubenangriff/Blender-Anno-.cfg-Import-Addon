import bpy
from .shader_base import AnnoBasicShader
from .shader_components import *

from ..utils import to_data_path
import os
from pathlib import Path
from ..prefs import IO_AnnocfgPreferences

class AnnoDefaultShader(AnnoBasicShader):

    def __init__(self):
        super().__init__()

        self.shader_id = "AnnoDefaultShader"

        self.compose(DefaultShaderFakeComponent())
        self.compose(CommonShaderComponent())
        self.compose(AdditionalPBRShaderComponent())
        self.compose(TerrainAdaptionShaderComponent())
        self.compose(EnvironmentShaderComponent())
        self.compose(GlowShaderComponent())

        # override default vertexformat
        self.material_properties["VertexFormat"] = "P4h_N4b_G4b_B4b_T2h"

    def texture_quality_suffix(self):
        return "_"+IO_AnnocfgPreferences.get_texture_quality()

    def create_anno_shader(self):
        anno_shader = bpy.data.node_groups.new(self.shader_id, 'ShaderNodeTree')

        for l in self.links: 
            if not l.has_socket():
                continue

            socket = anno_shader.interface.new_socket(socket_type = l.socket_type, name = l.link_key, in_out = 'INPUT')
            if l.has_default_value():
                socket.default_value = l.default_value    
        
        anno_shader.interface.new_socket(socket_type = "NodeSocketShader", name = "Shader", in_out='OUTPUT')
                
        # bring this into the individual components or something
        inputs = self.add_shader_node(anno_shader, "NodeGroupInput", 
                                        position = (0, 0), 
                                    ).outputs
        mix_c_diffuse = self.add_shader_node(anno_shader, "ShaderNodeMixRGB",
                                        position = (1, 4),
                                        default_inputs = {
                                            0 : 1.0,
                                        },
                                        inputs = {
                                            "Color1" : inputs["cDiffuseMultiplier"],
                                            "Color2" : inputs["cDiffuse"],
                                        },
                                        blend_type = "MULTIPLY",
                                    )
        dye_mask = self.add_shader_node(anno_shader, "ShaderNodeRGBToBW",
                                        position = (1, 3),
                                        inputs = {
                                            "Color" : inputs["cDyeMask"],
                                        },
                                    )
        final_diffuse = self.add_shader_node(anno_shader, "ShaderNodeMixRGB",
                                        position = (2, 3),
                                        default_inputs = {
                                            "Color2" : (1.0, 0.0, 0.0, 1.0),
                                        },
                                        inputs = {
                                            "Fac" : dye_mask.outputs["Val"],
                                            "Color1" : mix_c_diffuse.outputs["Color"],
                                        },
                                        blend_type = "MULTIPLY",
                                    )
        #Normals
        separate_normal = self.add_shader_node(anno_shader, "ShaderNodeSeparateRGB",
                                        position = (1, 2),
                                        inputs = {
                                            "Image" : inputs["cNormal"],
                                        },
                                    )
        #Calc normal blue
        square_x = self.add_shader_node(anno_shader, "ShaderNodeMath",
                                        position = (2, 1.5),
                                        operation = "POWER",
                                        inputs = {
                                            0 : separate_normal.outputs["R"],
                                        },
                                        default_inputs = {
                                            1 : 2.0
                                        },
                                    )
        square_y = self.add_shader_node(anno_shader, "ShaderNodeMath",
                                        position = (2, 2.5),
                                        operation = "POWER",
                                        inputs = {
                                            0 : separate_normal.outputs["G"],
                                        },
                                        default_inputs = {
                                            1 : 2.0
                                        },
                                    )
        add_squares = self.add_shader_node(anno_shader, "ShaderNodeMath",
                                        position = (2.5, 2),
                                        operation = "ADD",
                                        inputs = {
                                            0 : square_x.outputs["Value"],
                                            1 : square_y.outputs["Value"],
                                        },
                                    )
        inverted_add_squares = self.add_shader_node(anno_shader, "ShaderNodeMath",
                                        position = (3, 2),
                                        operation = "SUBTRACT",
                                        inputs = {
                                            1 : add_squares.outputs["Value"],
                                        },
                                        default_inputs = {
                                            0 : 1.0
                                        },
                                    )
        normal_blue = self.add_shader_node(anno_shader, "ShaderNodeMath",
                                        position = (3.5, 2),
                                        operation = "SQRT",
                                        inputs = {
                                            0 : inverted_add_squares.outputs["Value"],
                                        },
                                    )
        
        combine_normal = self.add_shader_node(anno_shader, "ShaderNodeCombineRGB",
                                        position = (4, 2),
                                        inputs = {
                                            "R" : separate_normal.outputs["R"],
                                            "G" : separate_normal.outputs["G"],
                                            "B" : normal_blue.outputs["Value"],
                                        },
                                    )
        normal_map = self.add_shader_node(anno_shader, "ShaderNodeNormalMap",
                                        position = (5, 2),
                                        default_inputs = {
                                            0 : 0.5,
                                        },
                                        inputs = {
                                            "Color" : combine_normal.outputs["Image"],
                                        },
                                    )
        height_bw = self.add_shader_node(anno_shader, "ShaderNodeRGBToBW",
                                        position = (5, 3),
                                        inputs = {
                                            "Color" : inputs["cHeight"],
                                        },
                                    )
        bump_map = self.add_shader_node(anno_shader, "ShaderNodeBump",
                                        position = (6, 2),
                                        default_inputs = {
                                            0 : 0.5,
                                        },
                                        inputs = {
                                            "Height" : height_bw.outputs["Val"],
                                            "Normal" : normal_map.outputs["Normal"],
                                        },
                                    )
        #Roughness
        roughness = self.add_shader_node(anno_shader, "ShaderNodeMath",
                                position = (3, 0),
                                operation = "SUBTRACT",
                                inputs = {
                                    1 : inputs["Glossiness"],
                                },
                                default_inputs = {
                                    0 : 1.0
                                },
                            )
        #Metallic
        metallic = self.add_shader_node(anno_shader, "ShaderNodeRGBToBW",
                                        position = (1, 3),
                                        inputs = {
                                            "Color" : inputs["cMetallic"],
                                        },
                                    )
        #Emission
        scaled_emissive_color = self.add_shader_node(anno_shader, "ShaderNodeVectorMath",         
                            operation = "SCALE",
                            name = "EmissionScale",
                            position = (1, -1),
                            default_inputs = {
                                "Scale": 10.0,
                            },
                            inputs = {
                                "Vector" : inputs["cEmissiveColor"],
                            }
        )
        combined_emissive_color = self.add_shader_node(anno_shader, "ShaderNodeVectorMath",         
                            operation = "MULTIPLY",
                            position = (2, -1),
                            inputs = {
                                0 : final_diffuse.outputs["Color"],
                                1 : scaled_emissive_color.outputs["Vector"],
                            }
        )
        object_info = self.add_shader_node(anno_shader, "ShaderNodeObjectInfo",         
                            position = (1, -2),
        )
        random_0_1 = self.add_shader_node(anno_shader, "ShaderNodeMath",  
                            operation = "FRACT",   
                            position = (2, -2),
                            inputs = {
                                "Value" : object_info.outputs["Location"],
                            }
        )
        color_ramp_node = self.add_shader_node(anno_shader, "ShaderNodeValToRGB",  
                            position = (3, -2),
                            inputs = {
                                "Fac" : random_0_1.outputs["Value"],
                            }
        )

        color_ramp = color_ramp_node.color_ramp
        color_ramp.elements[0].color = (1.0, 0.0, 0.0,1)
        color_ramp.elements[1].position = (2.0/3.0)
        color_ramp.elements[1].color = (0.0, 0.0, 1.0,1)
        
        color_ramp.elements.new(1.0/3.0)
        color_ramp.elements[1].color = (0.0, 1.0, 0.0,1)
        color_ramp.interpolation = "CONSTANT"
        
        location_masked_emission = self.add_shader_node(anno_shader, "ShaderNodeVectorMath",         
                            operation = "MULTIPLY",
                            position = (4, -2),
                            inputs = {
                                0 : color_ramp_node.outputs["Color"],
                                1 : inputs["cNightGlow"],
                            }
        )
        
        final_emission_color = self.add_shader_node(anno_shader, "ShaderNodeMixRGB",         
                            blend_type = "MIX",
                            position = (5, -1),
                            default_inputs = {
                                "Color1" : (0.0, 0.0 ,0.0, 1.0)
                            },
                            inputs = {
                                "Fac" : location_masked_emission.outputs["Vector"],
                                "Color2" : combined_emissive_color.outputs["Vector"],
                            }
        )
        
        bsdf = self.add_shader_node(anno_shader, "ShaderNodeBsdfPrincipled", 
                                        position = (4, 0), 
                                        inputs = {
                                            "Alpha" : inputs["Alpha"],
                                            "Roughness" : roughness.outputs["Value"],
                                            "Normal" : bump_map.outputs["Normal"],
                                            "Base Color" : final_diffuse.outputs["Color"],
                                            "Metallic" : metallic.outputs["Val"],
                                            "Emission Color" : final_emission_color.outputs["Color"],
                                        },
                                        default_inputs = {
                                            "Alpha": 1.0,
                                            "Emission Strength" : 1.0
                                        },
                                    )
        outputs = self.add_shader_node(anno_shader, "NodeGroupOutput", 
                                        position = (5, 0), 
                                        inputs = {
                                            "Shader" : bsdf.outputs["BSDF"]
                                        },
                                    )
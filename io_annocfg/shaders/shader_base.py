import bpy
import xml.etree.ElementTree as ET
from .shader_components import AbstractShaderComponent, AbstractLink
from ..utils import xml_smart

class AnnoBasicShader: 
    def __init__(self):

        self.links = []

        self.shader_id = "AnnoAbstractShader"

        self.material_properties = {
            "ConfigType" : "MATERIAL",
            "Name" : "",
            "ShaderID" : "8",
            "VertexFormat" : "",
            "NumBonesPerVertex" : "0"
        }
        self.__link_by_key = { }

    def set_property(self, key, value):
        assert key in self.material_properties, "Invalid Property: " + key
        assert type(value) == type(self.material_properties[key]), "Type mismatch while setting property"
        self.material_properties[key] = value

    def compose(self, shaderComponent : AbstractShaderComponent):
        self.links = self.links + shaderComponent.links

        for link in shaderComponent.links: 
            self.__link_by_key[link.link_key] = link

    def add_link(self, link : AbstractLink):
        self.links.append(link)
        self.__link_by_key[link.link_key] = link

    def has_link(self, link_key):
        return link_key in self.__link_by_key

    def get_link(self, link_key):
        return self.__link_by_key(link_key)

    # exports all links we have
    def to_xml_node(self, parent : ET.Element, blender_material) -> ET.Element:
        root = ET.SubElement(parent, "Config")
        for key, value in self.material_properties.items():
            sub = ET.SubElement(root, key)
            sub.text = str(value)
        for link in self.links: 
            if link.is_invalid:
                continue
            link.to_xml(root, blender_material)
        return root

    def to_blender_material(self, material_node : ET.Element): 
        
        name_node = material_node.find("Name")
        name = "Unnamed Material"

        if name_node is not None: 
            name = name_node.text

        material = bpy.data.materials.new(name=name)
        material.use_nodes = True

        node_tree = material.node_tree
        links = node_tree.links
        nodes = node_tree.nodes

        shader = self.add_anno_shader(nodes)
        material.node_tree.nodes.remove(nodes["Principled BSDF"])
        links.new(nodes["Material Output"].inputs["Surface"], shader.outputs["Shader"])

        for link in self.links:
            link.to_blender(material_node, material)

        return material

    def add_anno_shader(self, nodes):
        group = nodes.new(type='ShaderNodeGroup')
        if not self.shader_id in bpy.data.node_groups:
            self.create_anno_shader()            
        group.node_tree = bpy.data.node_groups[self.shader_id]
        return group

    def create_anno_shader(self):
        return None

    def add_shader_node(self, node_tree, node_type, **kwargs):
        node = node_tree.nodes.new(node_type)
        positioning_unit = (300, 300)
        positioning_offset = (0, 3 * positioning_unit[1])
        x,y = kwargs.pop("position", (0,0))
        node.location.x = x* positioning_unit[0] - positioning_offset[0]
        node.location.y = y* positioning_unit[1] - positioning_offset[1]

        if "name" in kwargs and not "label" in kwargs:
            kwargs["label"] = kwargs["name"]

        for input_key, default_value in kwargs.pop("default_inputs", {}).items():
            print(input_key)

            nodeinput = None
            if type(input_key) is int: 
                nodeinput = node.inputs[input_key]
            elif type(input_key) is str:
                nodeinput = node.inputs.get(input_key)

            if(nodeinput is None):
                print("We aren't allowed to use this as a defaultInput: " + node_type + " | " + input_key)
                continue
            nodeinput.default_value = default_value

        for input_key, input_connector in kwargs.pop("inputs", {}).items():
                node_tree.links.new(node.inputs[input_key], input_connector)

        for attr, value in kwargs.items():
            setattr(node, attr, value)

        return node
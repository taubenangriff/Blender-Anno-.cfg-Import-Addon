﻿from __future__ import annotations
import bpy
from bpy.types import Object as BlenderObject
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Tuple, List, NewType, Any, Union, Dict, Optional, TypeVar, Type
from bpy.props import EnumProperty, BoolProperty, PointerProperty, IntProperty, FloatProperty, CollectionProperty, StringProperty, FloatVectorProperty
from bpy.types import PropertyGroup, Panel, Operator, UIList
import bmesh
from abc import ABC, abstractmethod
from collections import defaultdict
from .prefs import IO_AnnocfgPreferences
from .utils import *
from . import feedback_enums
from .material import Material, ClothMaterial
from .anno_objects import get_anno_object_class, set_anno_object_class, MainFile, Model, Cf7File, SubFile, Decal, Propcontainer, Prop, Particle, IfoPlane, Sequence, DummyGroup,\
    Cf7DummyGroup, Cf7Dummy, FeedbackConfig, SimpleAnnoFeedbackEncodingObject, ArbitraryXMLAnnoObject, Light, Cloth, IfoFile, Spline, IslandFile, PropGridInstance, \
    IslandGamedataFile, GameObject, AnimationsNode, Animation, AnimationSequence, AnimationSequences, Track, TrackElement, IfoMeshHeightmap


class BoolPropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "SomeBool") # type: ignore
    value : BoolProperty(name = "", default = False) # type: ignore

class FeedbackSequencePropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "SomeSequence") # type: ignore
    value : EnumProperty( # type: ignore
        name='',
        description='Animation Sequence',
        items= feedback_enums.animation_sequences,
        default='idle01'
    )

class IntPropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "SomeInt") # type: ignore
    value : IntProperty(name = "", default = 0) # type: ignore
class StringPropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "SomeString") # type: ignore
    value : StringProperty(name = "", default = "") # type: ignore

class FilenamePropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "SomeString") # type: ignore
    value : StringProperty(name = "", default = "", subtype = "FILE_PATH") # type: ignore
class FloatPropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "SomeFloat") # type: ignore
    value : FloatProperty(name = "", default = 0.0) # type: ignore
    
class ColorPropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "SomeColor") # type: ignore
    value : FloatVectorProperty(name = "", default = [0.0, 0.0, 0.0], subtype = "COLOR", min= 0.0, max = 1.0) # type: ignore

class ObjectPointerPropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "SomeObject") # type: ignore
    value : PointerProperty(name = "", type= bpy.types.Object) # type: ignore


class Converter(ABC):
    @classmethod
    @abstractmethod
    def data_type(cls):
        pass
    @classmethod
    def from_string(cls, s):
        """Convert the string s from the input xml node into a blender representation of type data_type()

        Args:
            s (str): xml_node.text

        Returns:
            data_type(): Blender representation
        """
        value = cls.data_type()
        try:
            value = cls.data_type()(s)
        except:
            print(f"Error: failed to convert {s} to {cls.data_type()}")
        return cls.data_type()(s)
    @classmethod
    def to_string(cls, value):
        """Convert the blender representation value into a string for the xml node.
        Args:
            value (daty_type()): Blender representation

        Returns:
            str: XML text string
        """  
        return str(value)

class StringConverter(Converter):
    @classmethod
    def data_type(cls):
        return str

class BoolConverter(Converter):
    @classmethod
    def data_type(cls):
        return bool
    @classmethod
    def from_string(cls, s):
        return bool(int(s))
    @classmethod
    def to_string(cls, value):
        return str(int(value))
        
class IntConverter(Converter):
    @classmethod
    def data_type(cls):
        return int

class FloatConverter(Converter):
    @classmethod
    def data_type(cls):
        return float
    @classmethod
    def to_string(cls, value):
        return format_float(value)
class FeedbackSequenceConverter(Converter):
    @classmethod
    def data_type(cls):
        return string
    @classmethod
    def from_string(cls, s): 
        seq_id = int(s)
        return feedback_enums.NAME_BY_SEQUENCE_ID.get(seq_id, "none")
    @classmethod
    def to_string(cls, value): 
        seq_id = feedback_enums.SEQUENCE_ID_BY_NAME.get(value, -1)
        return str(seq_id)
    
class ObjectPointerConverter(Converter):
    @classmethod
    def data_type(cls):
        return string
    @classmethod
    def from_string(cls, s): 
        return bpy.data.objects[s]
    @classmethod
    def to_string(cls, value): 
        if value is None:
            return ""
        return value.name


class ColorConverter(Converter):
    @classmethod
    def data_type(cls):
        return str
    @classmethod
    def from_string(cls, s): #f.e. COLOR[1.0, 0.5, 0.3]
        values = s.replace(" ", "").replace("_COLOR[", "").replace("]", "").split(",")
        assert len(values) == 3
        return [format_float(value) for value in values]
    @classmethod
    def to_string(cls, value): #f.e. [1.0, 0.5, 0.3]
        assert len(value) == 3
        return f"_COLOR[{', '.join([str(val) for val in value])}]"

converter_by_tag = {
    "ConfigType": StringConverter,
    "FileName" : StringConverter,
    "Name" : StringConverter,
    "AdaptTerrainHeight" : BoolConverter,
    "HeightAdaptationMode" : BoolConverter,
    "DIFFUSE_ENABLED" : BoolConverter,
    "NORMAL_ENABLED" : BoolConverter,
    "METALLIC_TEX_ENABLED" : BoolConverter,
    "SEPARATE_AO_TEXTURE" : BoolConverter, 
    "HEIGHT_MAP_ENABLED" : BoolConverter,
    "NIGHT_GLOW_ENABLED" : BoolConverter,
    "DYE_MASK_ENABLED" : BoolConverter,
    "cUseTerrainTinting" : BoolConverter,
    "SELF_SHADOWING_ENABLED" : BoolConverter, 
    "WATER_CUTOUT_ENABLED" : BoolConverter,
    "ADJUST_TO_TERRAIN_HEIGHT" : BoolConverter, 
    "GLOW_ENABLED": BoolConverter,
    "SequenceID": FeedbackSequenceConverter,
    "m_IdleSequenceID": FeedbackSequenceConverter,
    "BlenderModelID": ObjectPointerConverter,
    "BlenderParticleID": ObjectPointerConverter,
}

def get_converter_for(tag, value_string):
    if tag in converter_by_tag:
        return converter_by_tag[tag]
    if value_string.startswith("_COLOR["):
        return ColorConverter
    if value_string.isnumeric() or value_string.lstrip("-").isnumeric():
        return IntConverter
    if is_type(float, value_string):
        return FloatConverter

    #TODO: CDATA Converter, mIdleSequenceConverter, etc
    return StringConverter

class XMLPropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "") # type: ignore
    
    config_type : StringProperty(name = "", default = "") # type: ignore
    
    feedback_sequence_properties : CollectionProperty(name = "FeedbackSequences", type = FeedbackSequencePropertyGroup) # type: ignore
    boolean_properties : CollectionProperty(name = "Bools", type = BoolPropertyGroup) # type: ignore
    filename_properties : CollectionProperty(name = "Filenames", type = FilenamePropertyGroup) # type: ignore
    string_properties : CollectionProperty(name = "Strings", type = StringPropertyGroup) # type: ignore
    int_properties : CollectionProperty(name = "Ints", type = IntPropertyGroup) # type: ignore
    float_properties : CollectionProperty(name = "Floats", type = FloatPropertyGroup) # type: ignore
    color_properties : CollectionProperty(name = "Colors", type = ColorPropertyGroup) # type: ignore
    object_pointer_properties : CollectionProperty(name = "Objects", type = ObjectPointerPropertyGroup) # type: ignore
    dynamic_properties : CollectionProperty(name = "DynamicProperties", type = XMLPropertyGroup) # type: ignore
    
    
    hidden : BoolProperty(name = "Hide", default = False) # type: ignore
    deleted : BoolProperty(name = "Delete", default = False) # type: ignore
    
    def reset(self):
        self.feedback_sequence_properties.clear()
        self.boolean_properties.clear()
        self.filename_properties.clear()
        self.string_properties.clear()
        self.int_properties.clear()
        self.float_properties.clear()
        self.color_properties.clear()
        self.object_pointer_properties.clear()
        self.dynamic_properties.clear()
        self.deleted = False
        self.hidden = False
    
    def remove(self, tag):
        for container in [self.feedback_sequence_properties, 
                          self.boolean_properties,
                          self.filename_properties,
                          self.string_properties,
                          self.int_properties,
                          self.float_properties,
                          self.color_properties,
                          self.dynamic_properties]:
            for i,prop in enumerate(container):
                if prop.tag == tag:
                    container.remove(i)
                    return True
        return False
    def get_string(self, tag, default = None):
        for item in self.string_properties:
            if item.tag == tag:
                return item.value
        for item in self.filename_properties:
            if item.tag == tag:
                return item.value
        return default
    def set(self, tag, value_string, replace = False):
        converter = get_converter_for(tag, value_string)
        value = converter.from_string(value_string)
        
        # Special fields
        if tag == "ConfigType":
            self.config_type = value
            return
            
        properties_by_converter = {
            BoolConverter: self.boolean_properties,
            StringConverter: self.string_properties,
            IntConverter: self.int_properties,
            FloatConverter: self.float_properties,
            ColorConverter: self.color_properties,
            ObjectPointerConverter: self.object_pointer_properties,
            FeedbackSequenceConverter: self.feedback_sequence_properties,
        }
        
        properties = properties_by_converter[converter]
        if tag == "FileName":
            properties = self.filename_properties
        if replace:
            for item in properties:
                if item.tag == tag:
                    item.value = value
                    return
        properties.add()
        properties[-1].tag = tag
        properties[-1].value = value
        
    def from_node(self, node):
        self.tag = node.tag
        for child_node in list(node):
            if len(list(child_node)) == 0:
                value = child_node.text
                if value is None:
                    value = ""
                self.set(child_node.tag, value)
            else:
                self.dynamic_properties.add()
                self.dynamic_properties[-1].from_node(child_node)
        return self

    def to_node(self, target_node):
        target_node.tag = self.tag
        if self.config_type:
            find_or_create(target_node, "ConfigType").text = self.config_type
        for property_group, converter in [
                            (self.feedback_sequence_properties, FeedbackSequenceConverter),
                            (self.string_properties, StringConverter),
                            (self.int_properties, IntConverter),
                            (self.filename_properties, StringConverter),
                            (self.float_properties, FloatConverter),
                            (self.object_pointer_properties, ObjectPointerConverter),
                            (self.boolean_properties, BoolConverter),
                        ]:
            for prop in property_group:
                value_string = converter.to_string(prop.value)
                #It is better to always create a new subelement - otherwise there can only be one of each tag.
                #Or does this create any problems?
                #find_or_create(target_node, prop.tag).text = value_string
                ET.SubElement(target_node, prop.tag).text = value_string
        for dyn_prop in self.dynamic_properties:
            if dyn_prop.deleted:
                continue
            subnode = ET.SubElement(target_node, dyn_prop.tag)
            dyn_prop.to_node(subnode)
        return target_node
    
    def draw(self, layout, split_ratio = 0.3, first_level_property = True):
        col = layout.column()
        header = col.row()
        split = header.split(factor=0.6)
        split.label(text = f"{self.tag}: {self.config_type}")
        split.prop(self, "hidden", icon = "HIDE_OFF")
        if not first_level_property:
            split.prop(self, "deleted", icon = "PANEL_CLOSE")
        if self.hidden:
            return
        col.separator(factor = 1.0)
        for kw_properties in [self.feedback_sequence_properties, self.filename_properties,self.boolean_properties,
                              self.int_properties, self.float_properties, self.string_properties, self.color_properties, self.object_pointer_properties]:
            for item in kw_properties:
                row = col.row()
                split = row.split(factor=split_ratio)
                split.alignment = "RIGHT"
                split.label(text = item.tag)
                split.prop(item, "value")
        
        for item in self.dynamic_properties:
            if item.deleted:
                continue
            box = col.box()
            item.draw(box, split_ratio, False)
    

class PT_AnnoScenePropertyPanel(Panel):
    bl_label = "Anno Scene"
    bl_idname = "VIEW_3D_PT_AnnoScene"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Anno Object' 
    #bl_context = "object"
    
    @classmethod
    def poll(cls, context):
        return True
            
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        
        col.prop(context.scene, "anno_mod_folder")

class ConvertCf7DummyToDummy(Operator):
    bl_idname = "object.convertcf7dummy"
    bl_label = "Convert to SAFE Dummy"

    def execute(self, context):
        obj = context.active_object
        obj.anno_object_class_str = obj.anno_object_class_str.replace("Cf7", "")
        obj.name = obj.name.replace("Cf7", "")
        return {'FINISHED'}

class DuplicateDummy(Operator):
    """Duplicates the dummy and gives the duplicate a higher id. Assumes a name like dummy_42."""
    bl_idname = "object.duplicatedummy"
    bl_label = "Duplicate Dummy"

    def execute(self, context):
        obj = context.active_object
        duplicate = obj.copy()
        bpy.context.scene.collection.objects.link(duplicate)
        name = duplicate.dynamic_properties.get_string("Name")
        head = name.rstrip('0123456789')
        tail = name[len(head):]
        tail = str(int(tail)+1)
        name = head + tail
        duplicate.dynamic_properties.set("Name", name, replace = True)
        duplicate.name = "Dummy_" + name
        return {'FINISHED'}


def load_animations_for_model(obj):
    node = obj.dynamic_properties.to_node(ET.Element("Config"))
    animations_node = node.find("Animations")
    if animations_node is not None:
        
        animations_container = AnimationsNode.xml_to_blender(ET.Element("Animations"), obj)
        animations_container.name = "ANIMATIONS_"+ obj.name.replace("MODEL_", "")
        
        for i, anim_node in enumerate(list(animations_node)):
            ET.SubElement(anim_node, "ModelFileName").text = get_text(node, "FileName")
            ET.SubElement(anim_node, "AnimationIndex").text = str(i)
            Animation.xml_to_blender(anim_node, animations_container)
        obj.dynamic_properties.remove("Animations")
        
        for anim_obj in animations_container.children:
            for armature in anim_obj.children:
                for anim_mesh in armature.children:
                    for m_idx, material in enumerate(obj.data.materials):
                        anim_mesh.data.materials[m_idx] = material

class LoadAnimations(Operator):
    """Loads all animations specified in the animations section of this model."""
    bl_idname = "object.load_animations"
    bl_label = "Load Animations"

    def execute(self, context):
        obj = context.active_object
        load_animations_for_model(obj)
        return {'FINISHED'}



class LoadAllAnimations(Operator):
    """Loads all animations in this file."""
    bl_idname = "object.load_all_animations"
    bl_label = "Load All Animations"

    def load_animations_recursively(self, obj):
        if get_anno_object_class(obj) == Model:
            load_animations_for_model(obj)
        for child in obj.children:
            self.load_animations_recursively(child)
    def execute(self, context):
        main_obj = context.active_object
        self.load_animations_recursively(main_obj)
        return {'FINISHED'}
 
def get_main_file_obj(obj):
    main_file_obj = obj
    while get_anno_object_class(main_file_obj) != MainFile:
        if main_file_obj.parent is not None:
            main_file_obj = main_file_obj.parent
    if get_anno_object_class(main_file_obj) == MainFile:
        return main_file_obj
    return None   
    
class ShowSequence(Operator):
    """Makes all animations belonging to this sequence visible and all others invisible. Also changes the display mode of the main models into Wireframe."""
    bl_idname = "object.show_sequence"
    bl_label = "Show Sequence"

    
    def set_hide_viewport_recursive(self, obj, hide):
        obj.hide_set(state=hide)
        for o in obj.children:
            self.set_hide_viewport_recursive(o, hide)

    def show_animation(self, model_obj, animation_id):
        for animations_obj in model_obj.children:
            for i, anim_obj in enumerate(animations_obj.children):
                anim_node = anim_obj.dynamic_properties.to_node(ET.Element("Config"))
                anim_idx = get_text(anim_node, "AnimationIndex")
                if animation_id == anim_idx:
                    self.set_hide_viewport_recursive(anim_obj, False)
                else:
                    self.set_hide_viewport_recursive(anim_obj, True)
    def show_sequence(self, seq_obj):
        for track_obj in seq_obj.children:
            track_node = track_obj.dynamic_properties.to_node(ET.Element("Track"))
            for track_element_node in track_node.findall("TrackElement"):
                model_name = get_text(track_element_node, "BlenderModelID", "")
                animation_id = get_text(track_element_node, "AnimationID", "")
                if animation_id != "" and model_name != "" and model_name in bpy.data.objects:
                    model_obj = bpy.data.objects[model_name]
                    self.show_animation(model_obj, animation_id)
                    model_obj.display_type = "WIRE"
    
    def show_sequences_in_subfiles(self, main_file_obj, selected_sequence_id):
        if main_file_obj is not None:
            for anim_sequences in main_file_obj.children:
                if not get_anno_object_class(anim_sequences) == AnimationSequences:
                    continue
                for subfile_seq in anim_sequences.children:
                    if not get_anno_object_class(subfile_seq) == AnimationSequence:
                        continue
                    seq_node = subfile_seq.dynamic_properties.to_node(ET.Element("Config"))
                    sequence_id = get_text(seq_node, "SequenceID")
                    if selected_sequence_id == sequence_id:
                        self.show_sequence(subfile_seq)
            for file_obj in main_file_obj.children:
                if not get_anno_object_class(file_obj) == SubFile:
                    continue
                for subfile_main_file_obj in file_obj.children:
                    if not get_anno_object_class(subfile_main_file_obj) == MainFile:
                        continue
                    self.show_sequences_in_subfiles(subfile_main_file_obj, selected_sequence_id)
                    
    def execute(self, context):
        seq_obj = context.active_object
        seq_node = seq_obj.dynamic_properties.to_node(ET.Element("Config"))
        selected_sequence_id = get_text(seq_node, "SequenceID")
        
        #self.show_sequence(seq_obj)
        main_file_obj = get_main_file_obj(seq_obj)
        self.show_sequences_in_subfiles(main_file_obj, selected_sequence_id)
        return {'FINISHED'}
    
class ShowModel(Operator):
    """Makes all animations belonging to this sequence invisible and instead displays the normal mesh only."""
    bl_idname = "object.show_model"
    bl_label = "Show Model"

    
    def set_hide_viewport_recursive(self, obj, hide):
        obj.hide_set(state=hide)
        for o in obj.children:
            self.set_hide_viewport_recursive(o, hide)

    def hide_animation(self, model_obj):
        for animations_obj in model_obj.children:
            for i, anim_obj in enumerate(animations_obj.children):
                self.set_hide_viewport_recursive(anim_obj, True)
    def hide_sequence(self, seq_obj):
        for track_obj in seq_obj.children:
            track_node = track_obj.dynamic_properties.to_node(ET.Element("Track"))
            for track_element_node in track_node.findall("TrackElement"):
                model_name = get_text(track_element_node, "BlenderModelID", "")
                animation_id = get_text(track_element_node, "AnimationID", "")
                if animation_id != "" and model_name != "" and model_name in bpy.data.objects:
                    model_obj = bpy.data.objects[model_name]
                    self.hide_animation(model_obj)
                    model_obj.display_type = "TEXTURED"

    
    def hide_sequences_in_subfiles(self, main_file_obj, selected_sequence_id):
        if main_file_obj is not None:
            for anim_sequences in main_file_obj.children:
                if not get_anno_object_class(anim_sequences) == AnimationSequences:
                    continue
                for subfile_seq in anim_sequences.children:
                    if not get_anno_object_class(subfile_seq) == AnimationSequence:
                        continue
                    seq_node = subfile_seq.dynamic_properties.to_node(ET.Element("Config"))
                    sequence_id = get_text(seq_node, "SequenceID")
                    if selected_sequence_id == sequence_id:
                        self.hide_sequence(subfile_seq)
            for file_obj in main_file_obj.children:
                if not get_anno_object_class(file_obj) == SubFile:
                    continue
                for subfile_main_file_obj in file_obj.children:
                    if not get_anno_object_class(subfile_main_file_obj) == MainFile:
                        continue
                    self.hide_sequences_in_subfiles(subfile_main_file_obj, selected_sequence_id)
    def execute(self, context):
        seq_obj = context.active_object
        seq_node = seq_obj.dynamic_properties.to_node(ET.Element("Config"))
        selected_sequence_id = get_text(seq_node, "SequenceID")
        
        main_file_obj = get_main_file_obj(seq_obj)
        self.hide_sequences_in_subfiles(main_file_obj, selected_sequence_id)
        return {'FINISHED'}

class PT_AnnoObjectPropertyPanel(Panel):
    bl_label = "Anno Object"
    bl_idname = "VIEW_3D_PT_AnnoObject"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Anno Object' 
    #bl_context = "object"
    
    @classmethod
    def poll(cls, context):
        return True
            
    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        
        if not obj:
            return
        col = layout.column()
        row = col.row()
        
        row.prop(obj, "anno_object_class_str")
        row.enabled = False
        if "Cf7" in obj.anno_object_class_str:
            col.operator(ConvertCf7DummyToDummy.bl_idname, text = "Convert to SimpleAnnoFeedback")
        if "Model" == obj.anno_object_class_str:
            col.operator(LoadAnimations.bl_idname, text = "Load Animations")
        if "MainFile" == obj.anno_object_class_str:
            col.operator(LoadAllAnimations.bl_idname, text = "Load All Animations")
        if "AnimationSequence" == obj.anno_object_class_str:
            col.operator(ShowSequence.bl_idname, text = "Show Sequence")    
            col.operator(ShowModel.bl_idname, text = "Show Model")    
            
        if "Dummy" == obj.anno_object_class_str:
            col.operator(DuplicateDummy.bl_idname, text = "Duplicate Dummy (ID Increment)")
        col.prop(obj, "parent")
        dyn = obj.dynamic_properties
        dyn.draw(col)

class PT_AnnoMaterialObjectPropertyPanel(Panel):
    bl_label = "Anno Material"
    bl_idname = "WINDOW_PT_AnnoMaterialObject"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_category = 'Anno Material' 
    bl_context = "material"
        
    def draw(self, context):
            layout = self.layout
            obj = context.active_object.active_material
 
            if not obj:
                return
            col = layout.column()
            dyn = obj.dynamic_properties
            dyn.draw(col, 0.5)
class AnnoImageTextureProperties(PropertyGroup):
    enabled : BoolProperty( #type: ignore
            name='Enabled',
            description='',
            default=True)
    original_file_extension: EnumProperty( #type: ignore
            name='Extension',
            description='Some textures are stored as .png (for example default masks). Use .psd for your own textures (saved as .dds).',
            items = [
                (".psd", ".psd", ".psd or .dds"),
                (".png", ".png", ".psd or .dds"),
            ],
            default='.psd'
            )        

class PT_AnnoImageTexture(Panel):
    bl_label = "Anno Texture"
    bl_idname = "SCENE_PT_AnnoTexture"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Anno Texture' 
    #bl_context = "object"
    
    @classmethod
    def poll(cls, context):
        return (context.space_data.type == 'NODE_EDITOR' and
                context.space_data.tree_type == 'ShaderNodeTree' and type(context.active_node) == bpy.types.ShaderNodeTexImage)

    def draw(self, context):
        layout = self.layout
        node = context.active_node.anno_properties
        col = layout.column()
        col.prop(node, "enabled")
        col.prop(node, "original_file_extension")


classes = [
    AnnoImageTextureProperties,
    PT_AnnoImageTexture,
    
    BoolPropertyGroup,
    IntPropertyGroup,
    StringPropertyGroup,
    FloatPropertyGroup,
    FilenamePropertyGroup,
    ColorPropertyGroup,
    FeedbackSequencePropertyGroup,
    ObjectPointerPropertyGroup,
    
    PT_AnnoScenePropertyPanel,
    
    PT_AnnoMaterialObjectPropertyPanel,
    ConvertCf7DummyToDummy,
    LoadAnimations,
    LoadAllAnimations,
    DuplicateDummy,
    ShowSequence,
    ShowModel,
    
    XMLPropertyGroup,
    PT_AnnoObjectPropertyPanel,
]
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.ShaderNodeTexImage.anno_properties = bpy.props.PointerProperty(type=AnnoImageTextureProperties)
    bpy.types.Object.dynamic_properties = bpy.props.PointerProperty(type = XMLPropertyGroup)
    bpy.types.Material.dynamic_properties = bpy.props.PointerProperty(type = XMLPropertyGroup)
    #CollectionProperty(type = AnnoImageTextureProperties)

def unregister():
    del bpy.types.ShaderNodeTexImage.anno_properties
    del bpy.types.Object.dynamic_properties
    for cls in classes:
        bpy.utils.unregister_class(cls)
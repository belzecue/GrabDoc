import os

import bpy
from bpy.types import Context, PropertyGroup, UILayout
from bpy.props import (
    BoolProperty,
    StringProperty,
    EnumProperty,
    IntProperty,
    FloatProperty
)

from ..constants import Global
from .generic import get_format
from .render import set_guide_height, get_rendered_objects
from .scene import scene_setup


################################################
# BAKERS
################################################


class Baker():
    # NOTE: Variables and their
    # option types for sub-classes
    ID = ""
    NAME = ID.capitalize()
    NODE = None
    COLOR_SPACE = "sRGB"
    VIEW_TRANSFORM = 'Standard'
    MARMOSET_COMPATIBLE = True
    SUPPORTED_ENGINES = (
        ('blender_eevee',     "Eevee",     ""),
        ('cycles',            "Cycles",    ""),
        ('blender_workbench', "Workbench", "")
    )

    # NOTE: Default functions
    def setup(self):
        """Operations to run before bake map export."""
        self.apply_render_settings(check=False)

    def apply_render_settings(self, check: bool=True):
        # TODO: What is this for?
        #if not check and not bpy.context.scene.gd.preview_state:
        #    return

        scene = bpy.context.scene
        scene.render.engine = str(self.engine).upper()

        # NOTE: Allow use of custom engines but leave default
        if scene.render.engine == 'BLENDER_EEVEE':
            scene.eevee.taa_render_samples = \
            scene.eevee.taa_samples = self.samples
        elif scene.render.engine == 'CYCLES':
            scene.cycles.samples = \
            scene.cycles.preview_samples = self.samples_cycles
        elif scene.render.engine == 'BLENDER_WORKBENCH':
            scene.display.render_aa = \
            scene.display.viewport_aa = self.samples_workbench

        set_color_management(self.COLOR_SPACE, self.VIEW_TRANSFORM)

        scene.view_settings.look = self.contrast.replace('_', ' ')

    def cleanup(self):
        """Operations to run after bake map export conclusion."""

    def draw_properties(self, context: Context, layout: UILayout):
        pass

    def draw(self, context: Context, layout: UILayout):
        """Draw layout for contextual bake map properties and operators."""
        gd = context.scene.gd

        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()

        if not self.MARMOSET_COMPATIBLE:
            box = col.box()
            col2 = box.column(align=True)
            col2.label(text='\u2022 Requires Shader Manipulation', icon='INFO')
            col2.label(text='\u2022 No Marmoset Support', icon='BLANK1')

        box = col.box()
        box.label(text="Properties", icon="PROPERTIES")
        if len(self.SUPPORTED_ENGINES) > 1:
            box.prop(self, 'engine', text="Engine")
        self.draw_properties(context, box)

        box = col.box()
        box.label(text="Settings", icon="SETTINGS")
        col = box.column()
        if gd.baker_type == 'blender':
            if self.engine == 'blender_eevee':
                prop = 'samples'
            elif self.engine == 'blender_workbench':
                prop = 'samples_workbench'
            else:  # Cycles
                prop = 'samples_cycles'
            col.prop(
                self,
                prop,
                text='Samples'
            )
            col.prop(self, 'reimport', text="Re-import")
            col.prop(self, 'contrast', text="Contrast")
        col.prop(self, 'suffix', text="Suffix")

    # NOTE: Default properties
    enabled: BoolProperty(name="Export Enabled", default=True)
    reimport: BoolProperty(
        name="Reimport Texture",
        description="Reimport bake map texture into a Blender material"
    )
    suffix: StringProperty(
        name="Suffix",
        description="The suffix of the exported bake map",
        # NOTE: `default` not captured in sub-classes
        # so you must set after item creation for now
        default=ID
    )
    visibility: BoolProperty(default=True)
    samples: IntProperty(
        name="Eevee Samples", default=128, min=1, soft_max=512,
        update=apply_render_settings
    )
    samples_cycles: IntProperty(
        name="Cycles Samples", default=32, min=1, soft_max=1024,
        update=apply_render_settings
    )
    samples_workbench: EnumProperty(
        items=(
            ('OFF', "No Anti-Aliasing", ""),
            ('FXAA', "1 Sample", ""),
            ('5', "5 Samples", ""),
            ('8', "8 Samples", ""),
            ('11', "11 Samples", ""),
            ('16', "16 Samples", ""),
            ('32', "32 Samples", "")
        ),
        default="16",
        name="Workbench Samples",
        update=apply_render_settings
    )
    contrast: EnumProperty(
        items=(
            ('None', "None (Medium)", ""),
            ('Very_High_Contrast', "Very High", ""),
            ('High_Contrast', "High", ""),
            ('Medium_High_Contrast', "Medium High", ""),
            ('Medium_Low_Contrast', "Medium Low", ""),
            ('Low_Contrast', "Low", ""),
            ('Very_Low_Contrast', "Very Low", "")
        ),
        name="Contrast",
        update=apply_render_settings
    )
    # NOTE: You must add the following redundant
    # properties to all sub-classes for now...
    engine: EnumProperty(
        items=SUPPORTED_ENGINES,
        name='Render Engine',
        update=apply_render_settings
    )


class Normals(Baker, PropertyGroup):
    ID = Global.NORMAL_ID
    NAME = Global.NORMAL_NAME
    NODE = Global.NORMAL_NODE
    COLOR_SPACE = "sRGB"
    VIEW_TRANSFORM = "Standard"
    MARMOSET_COMPATIBLE = True
    SUPPORTED_ENGINES = (
        ('blender_eevee', "Eevee",  ""),
        ('cycles',        "Cycles", "")
    )

    def setup(self) -> None:
        super().setup()

        ng_normal = bpy.data.node_groups[self.NODE]
        vec_transform = ng_normal.nodes.get('Vector Transform')
        group_output = ng_normal.nodes.get('Group Output')

        links = ng_normal.links
        if self.use_texture:
            links.new(
                vec_transform.inputs["Vector"],
                ng_normal.nodes.get('Bevel').outputs["Normal"]
            )
            links.new(
                group_output.inputs["Shader"],
                ng_normal.nodes.get('Mix Shader').outputs["Shader"]
            )
        else:
            links.new(
                vec_transform.inputs["Vector"],
                ng_normal.nodes.get('Bevel.001').outputs["Normal"]
            )
            links.new(
                group_output.inputs["Shader"],
                ng_normal.nodes.get('Vector Math.001').outputs["Vector"]
            )

    def draw_properties(self, context: Context, layout: UILayout):
        col = layout.column()
        col.prop(self, 'flip_y', text="Flip Y (-Y)")
        if context.scene.gd.baker_type == 'blender':
            col.prop(self, 'use_texture', text="Texture Normals")

    def update_flip_y(self, _context: Context):
        vec_multiply = \
            bpy.data.node_groups[self.NODE].nodes.get(
                'Vector Math'
            )
        vec_multiply.inputs[1].default_value[1] = -.5 if self.flip_y else .5

    def update_use_texture(self, context: Context) -> None:
        if not context.scene.gd.preview_state:
            return
        tree = bpy.data.node_groups[self.NODE]
        vec_transform = tree.nodes.get('Vector Transform')
        group_output = tree.nodes.get('Group Output')

        links = tree.links
        if self.use_texture:
            links.new(
                vec_transform.inputs["Vector"],
                tree.nodes.get('Bevel').outputs["Normal"]
            )
            links.new(
                group_output.inputs["Shader"],
                tree.nodes.get('Mix Shader').outputs["Shader"]
            )
        else:
            links.new(
                vec_transform.inputs["Vector"],
                tree.nodes.get('Bevel.001').outputs["Normal"]
            )
            links.new(
                group_output.inputs["Shader"],
                tree.nodes.get('Vector Math.001').outputs["Vector"]
            )

    flip_y: BoolProperty(
        name="Flip Y (-Y)",
        description="Flip the normal map Y direction",
        options={'SKIP_SAVE'},
        update=update_flip_y
    )
    use_texture: BoolProperty(
        name="Use Texture Normals",
        description="Use texture normals linked to the Principled BSDF",
        options={'SKIP_SAVE'},
        default=True,
        update=update_use_texture
    )
    engine: EnumProperty(
        items=SUPPORTED_ENGINES,
        name='Render Engine',
        update=Baker.apply_render_settings
    )


class Curvature(Baker, PropertyGroup):
    ID = Global.CURVATURE_ID
    NAME = Global.CURVATURE_NAME
    NODE = None
    COLOR_SPACE = "sRGB"
    VIEW_TRANSFORM = "Standard"
    MARMOSET_COMPATIBLE = True
    SUPPORTED_ENGINES = (
        ('blender_workbench', "Workbench", ""),
        #('cycles',        "Cycles", "")
    )

    def setup(self) -> None:
        super().setup()

        scene = bpy.context.scene
        scene_shading = bpy.data.scenes[str(scene.name)].display.shading

        scene_shading.light = 'FLAT'
        scene_shading.color_type = 'SINGLE'

        self.savedCavityType = scene_shading.cavity_type
        self.savedCavityRidgeFactor = scene_shading.cavity_ridge_factor
        self.savedCurveRidgeFactor = scene_shading.curvature_ridge_factor
        self.savedCavityValleyFactor = scene_shading.cavity_valley_factor
        self.savedCurveValleyFactor = scene_shading.curvature_valley_factor
        self.savedRidgeDistance = scene.display.matcap_ssao_distance
        self.savedSingleColor = [*scene_shading.single_color]

        scene_shading.show_cavity = True
        scene_shading.cavity_type = 'BOTH'
        scene_shading.cavity_ridge_factor = \
        scene_shading.curvature_ridge_factor = self.ridge
        scene_shading.curvature_valley_factor = self.valley
        scene_shading.cavity_valley_factor = 0
        scene_shading.single_color = (.214041, .214041, .214041)

        scene.display.matcap_ssao_distance = .075

    def draw_properties(self, context: Context, layout: UILayout):
        if context.scene.gd.baker_type != 'blender':
            return
        col = layout.column()
        col.prop(self, 'ridge', text="Ridge")
        col.prop(self, 'valley', text="Valley")

    def cleanup(self) -> None:
        display = \
            bpy.data.scenes[str(bpy.context.scene.name)].display
        display.shading.cavity_ridge_factor = self.savedCavityRidgeFactor
        display.shading.curvature_ridge_factor = self.savedCurveRidgeFactor
        display.shading.cavity_valley_factor = self.savedCavityValleyFactor
        display.shading.curvature_valley_factor = self.savedCurveValleyFactor
        display.shading.single_color = self.savedSingleColor
        display.shading.cavity_type = self.savedCavityType
        display.matcap_ssao_distance = self.savedRidgeDistance

        bpy.data.objects[Global.BG_PLANE_NAME].color[3] = 1

    def update_curvature(self, context: Context):
        if not context.scene.gd.preview_state:
            return
        scene_shading = \
            bpy.data.scenes[str(context.scene.name)].display.shading
        scene_shading.cavity_ridge_factor = \
            scene_shading.curvature_ridge_factor = self.ridge
        scene_shading.curvature_valley_factor = self.valley

    ridge: FloatProperty(
        name="",
        default=2,
        min=0,
        max=2,
        precision=3,
        step=.1,
        update=update_curvature,
        subtype='FACTOR'
    )
    valley: FloatProperty(
        name="",
        default=1.5,
        min=0,
        max=2,
        precision=3,
        step=.1,
        update=update_curvature,
        subtype='FACTOR'
    )
    engine: EnumProperty(
        items=SUPPORTED_ENGINES,
        name='Render Engine',
        update=Baker.apply_render_settings
    )


class Occlusion(Baker, PropertyGroup):
    ID = Global.OCCLUSION_ID
    NAME = Global.OCCLUSION_NAME
    NODE = Global.OCCLUSION_NODE
    COLOR_SPACE = "sRGB"
    VIEW_TRANSFORM = "Standard"
    MARMOSET_COMPATIBLE = True
    SUPPORTED_ENGINES = (
        ('blender_eevee', "Eevee",     ""),
        ('cycles',        "Cycles",    "")
    )

    def setup(self) -> None:
        super().setup()
        scene = bpy.context.scene

        eevee = scene.eevee
        self.savedUseOverscan = eevee.use_overscan
        self.savedOverscanSize = eevee.overscan_size
        if scene.render.engine == "BLENDER_EEVEE":
            eevee.use_gtao = True
            # NOTE: Overscan helps with screenspace effects
            eevee.use_overscan = True
            eevee.overscan_size = 10

    def cleanup(self) -> None:
        eevee = bpy.context.scene.eevee
        eevee.use_overscan = self.savedUseOverscan
        eevee.overscan_size = self.savedOverscanSize
        eevee.use_gtao = False

    def draw_properties(self, context: Context, layout: UILayout):
        gd = context.scene.gd
        col = layout.column()
        if gd.baker_type == 'marmoset':
            col.prop(gd, "marmo_occlusion_ray_count", text="Ray Count")
            return
        col.prop(self, 'gamma', text="Intensity")
        col.prop(self, 'distance', text="Distance")

    def update_gamma(self, _context: Context):
        gamma = bpy.data.node_groups[self.NODE].nodes.get('Gamma')
        gamma.inputs[1].default_value = self.gamma

    def update_distance(self, _context: Context):
        ao = bpy.data.node_groups[self.NODE].nodes.get(
            'Ambient Occlusion'
        )
        ao.inputs[1].default_value = self.distance

    gamma: FloatProperty(
        default=1,
        min=.001,
        soft_max=10,
        step=.17,
        name="",
        description="Intensity of AO (calculated with gamma)",
        update=update_gamma
    )
    distance: FloatProperty(
        default=1,
        min=0,
        soft_max=100,
        step=.03,
        subtype='DISTANCE',
        name="",
        description="The distance AO rays travel",
        update=update_distance
    )
    engine: EnumProperty(
        items=SUPPORTED_ENGINES,
        name='Render Engine',
        update=Baker.apply_render_settings
    )


class Height(Baker, PropertyGroup):
    ID = Global.HEIGHT_ID
    NAME = Global.HEIGHT_NAME
    NODE = Global.HEIGHT_NODE
    COLOR_SPACE = "sRGB"
    VIEW_TRANSFORM = "Standard"
    MARMOSET_COMPATIBLE = True
    SUPPORTED_ENGINES = (
        ('blender_eevee', "Eevee",     ""),
        ('cycles',        "Cycles",    "")
    )

    def setup(self) -> None:
        super().setup()

        if self.method == 'AUTO':
            rendered_obs = get_rendered_objects()
            set_guide_height(rendered_obs)

    def draw_properties(self, context: Context, layout: UILayout):
        col = layout.column()
        if context.scene.gd.baker_type == 'blender':
            col.prop(self, 'invert', text="Invert Mask")
        row = col.row()
        row.prop(self, 'method', text="Height Mode", expand=True)
        if self.method == 'MANUAL':
            col.prop(self, 'distance', text="0-1 Range")

    def update_method(self, context: Context):
        scene_setup(self, context)
        if not context.scene.gd.preview_state:
            return
        if self.method == 'AUTO':
            rendered_obs = get_rendered_objects()
            set_guide_height(rendered_obs)

    def update_guide(self, context: Context):
        gd_camera_ob_z = \
            bpy.data.objects.get(Global.TRIM_CAMERA_NAME).location[2]

        map_range = \
            bpy.data.node_groups[self.NODE].nodes.get('Map Range')
        map_range.inputs[1].default_value = \
            gd_camera_ob_z + -self.distance
        map_range.inputs[2].default_value = \
            gd_camera_ob_z

        ramp = bpy.data.node_groups[self.NODE].nodes.get(
            'ColorRamp')
        ramp.color_ramp.elements[0].color = \
            (0, 0, 0, 1) if self.invert else (1, 1, 1, 1)
        ramp.color_ramp.elements[1].color = \
            (1, 1, 1, 1) if self.invert else (0, 0, 0, 1)
        ramp.location = \
            (-400, 0)

        if self.method == 'MANUAL':
            scene_setup(self, context)

        # Update here so that it refreshes live in the VP
        if not context.scene.gd.preview_state:
            return

    invert: BoolProperty(
        description="Invert height mask, useful for sculpting negatively",
        update=update_guide
    )
    distance: FloatProperty(
        name="",
        default=1,
        min=.01,
        soft_max=100,
        step=.03,
        subtype='DISTANCE',
        update=update_guide
    )
    method: EnumProperty(
        items=(
            ('AUTO', "Auto", ""),
            ('MANUAL', "Manual", "")
        ),
        update=update_method,
        description="Height method, use manual if auto produces range errors"
    )
    engine: EnumProperty(
        items=SUPPORTED_ENGINES,
        name='Render Engine',
        update=Baker.apply_render_settings
    )


class Alpha(Baker, PropertyGroup):
    ID = Global.ALPHA_ID
    NAME = Global.ALPHA_NAME
    NODE = Global.ALPHA_NODE
    COLOR_SPACE = "sRGB"
    VIEW_TRANSFORM = "Standard"
    MARMOSET_COMPATIBLE = True
    SUPPORTED_ENGINES = (
        ('blender_eevee', "Eevee",     ""),
        ('cycles',        "Cycles",    "")
    )

    def draw_properties(self, context: Context, layout: UILayout):
        col = layout.column()
        if context.scene.gd.baker_type == 'blender':
            col.prop(self, 'invert', text="Invert Mask")

    def update_alpha(self, context: Context):
        gd_camera_ob_z = bpy.data.objects.get(
            Global.TRIM_CAMERA_NAME
        ).location[2]
        map_range = \
            bpy.data.node_groups[self.NODE].nodes.get('Map Range')
        map_range.inputs[1].default_value = gd_camera_ob_z - .00001
        map_range.inputs[2].default_value = gd_camera_ob_z
        invert = \
            bpy.data.node_groups[self.NODE].nodes.get('Invert')
        invert.inputs[0].default_value = 0 if self.invert else 1

    invert: BoolProperty(
        description="Invert the Alpha mask",
        update=update_alpha
    )
    engine: EnumProperty(
        items=SUPPORTED_ENGINES,
        name='Render Engine',
        update=Baker.apply_render_settings
    )


class Id(Baker, PropertyGroup):
    ID = Global.MATERIAL_ID
    NAME = Global.MATERIAL_NAME
    NODE = None
    MARMOSET_COMPATIBLE = True
    COLOR_SPACE = "sRGB"
    VIEW_TRANSFORM = "Standard"
    SUPPORTED_ENGINES = (
        ('blender_workbench', "Workbench", ""),
    )

    def setup(self) -> None:
        super().setup()
        scene = bpy.context.scene

        if scene.render.engine == 'BLENDER_WORKBENCH':
            shading = \
                bpy.context.scene.display.shading
            shading.show_cavity = False
            shading.light = 'FLAT'
            shading.color_type = self.method


    def draw_properties(self, context: Context, layout: UILayout):
        gd = context.scene.gd
        col = layout.column()
        row = col.row()
        if gd.baker_type == 'marmoset':
            row.enabled = False
            row.prop(self, 'ui_method', text="ID Method")
        else:
            row.prop(self, 'method', text="ID Method")

        if self.method != "MATERIAL" or gd.baker_type != 'marmoset':
            return

        col = layout.column(align=True)
        col.separator(factor=.5)
        col.scale_y = 1.1
        col.operator("grab_doc.quick_id_setup")

        row = col.row(align=True)
        row.scale_y = .9
        row.label(text=" Remove:")
        row.operator(
            "grab_doc.remove_mats_by_name",
            text='All'
        ).mat_name = Global.MAT_ID_RAND_PREFIX

        col = layout.column(align=True)
        col.separator(factor=.5)
        col.scale_y = 1.1
        col.operator("grab_doc.quick_id_selected")

        row = col.row(align=True)
        row.scale_y = .9
        row.label(text=" Remove:")
        row.operator(
            "grab_doc.remove_mats_by_name",
            text='All'
        ).mat_name = Global.MAT_ID_PREFIX
        row.operator("grab_doc.quick_remove_selected_mats",
                        text='Selected')

    method_list = (
        ('RANDOM', "Random", ""),
        ('MATERIAL', "Material", ""),
        ('VERTEX', "Object / Vertex", "")
    )
    method: EnumProperty(
        items=method_list,
        name=f"{NAME} Method"
    )
    ui_method: EnumProperty(
        items=method_list,
        default="MATERIAL"
    )
    engine: EnumProperty(
        items=SUPPORTED_ENGINES,
        name='Render Engine',
        update=Baker.apply_render_settings
    )


class Color(Baker, PropertyGroup):
    ID = Global.COLOR_ID
    NAME = Global.COLOR_NAME
    NODE = Global.COLOR_NODE
    COLOR_SPACE = "sRGB"
    VIEW_TRANSFORM = "Standard"
    MARMOSET_COMPATIBLE = False
    SUPPORTED_ENGINES = (
        ('blender_eevee', "Eevee",     ""),
        ('cycles',        "Cycles",    "")
    )

    engine: EnumProperty(
        items=SUPPORTED_ENGINES,
        name='Render Engine',
        update=Baker.apply_render_settings
    )


class Emissive(Baker, PropertyGroup):
    ID = Global.EMISSIVE_ID
    NAME = Global.EMISSIVE_NAME
    NODE = Global.EMISSIVE_NODE
    COLOR_SPACE = "sRGB"
    VIEW_TRANSFORM = "Standard"
    MARMOSET_COMPATIBLE = False
    SUPPORTED_ENGINES = (
        ('blender_eevee', "Eevee",  ""),
        ('cycles',        "Cycles", "")
    )

    engine: EnumProperty(
        items=SUPPORTED_ENGINES,
        name='Render Engine',
        update=Baker.apply_render_settings
    )


class Roughness(Baker, PropertyGroup):
    ID = Global.ROUGHNESS_ID
    NAME = Global.ROUGHNESS_NAME
    NODE = Global.ROUGHNESS_NODE
    COLOR_SPACE = "sRGB"
    VIEW_TRANSFORM = "Standard"
    MARMOSET_COMPATIBLE = False
    SUPPORTED_ENGINES = (
        ('blender_eevee', "Eevee",  ""),
        ('cycles',        "Cycles", "")
    )

    def draw_properties(self, context: Context, layout: UILayout):
        col = layout.column()
        if context.scene.gd.baker_type == 'blender':
            col.prop(self, 'invert', text="Invert")

    def update_roughness(self, _context: Context):
        invert = \
            bpy.data.node_groups[self.NODE].nodes.get('Invert')
        invert.inputs[0].default_value = 1 if self.invert else 0

    invert: BoolProperty(
        description="Invert the Roughness (AKA Glossiness)",
        update=update_roughness
    )
    engine: EnumProperty(
        items=SUPPORTED_ENGINES,
        name='Render Engine',
        update=Baker.apply_render_settings
    )


class Metalness(Baker, PropertyGroup):
    ID = Global.METALNESS_ID
    NAME = Global.METALNESS_NAME
    NODE = Global.METALNESS_NODE
    COLOR_SPACE = "sRGB"
    VIEW_TRANSFORM = "Standard"
    MARMOSET_COMPATIBLE = False
    SUPPORTED_ENGINES = (
        ('blender_eevee', "Eevee",  ""),
        ('cycles',        "Cycles", "")
    )

    engine: EnumProperty(
        items=SUPPORTED_ENGINES,
        name='Render Engine',
        update=Baker.apply_render_settings
    )


################################################
# UTILITIES
################################################


def set_color_management(
        display_device: str='None',
        view_transform: str='Standard'
    ) -> None:
    """Helper function for supporting custom color management
     profiles. Ignores anything that isn't compatible"""
    display_settings = bpy.context.scene.display_settings
    view_settings = bpy.context.scene.view_settings
    display_settings.display_device = display_device
    view_settings.view_transform = view_transform
    view_settings.look = 'None'
    view_settings.exposure = 0
    view_settings.gamma = 1


def get_bakers() -> list[Baker]:
    gd = bpy.context.scene.gd
    bakers = []
    for name in Global.ALL_MAP_IDS:
        try:
            baker = getattr(gd, name)
            bakers.append(baker)
        except AttributeError:
            print(f"Could not find baker `{name}`.")
    return bakers


def get_bake_maps(enabled_only: bool = True) -> list[Baker]:
    bakers = get_bakers()
    bake_maps = []
    for baker in bakers:
        for bake_map in baker:
            if enabled_only and not (bake_map.enabled and bake_map.visibility):
                continue
            bake_maps.append(bake_map)
    return bake_maps


def reimport_as_material(suffix, map_names: list) -> None:
    """Reimport baked textures as a material for use inside of Blender"""
    gd = bpy.context.scene.gd

    # Create material
    mat = bpy.data.materials.get(Global.REIMPORT_MAT_NAME)
    if mat is None:
        mat = bpy.data.materials.new(Global.REIMPORT_MAT_NAME)
    mat.use_nodes = True
    links = mat.node_tree.links

    # Create nodes
    bsdf = mat.node_tree.nodes['Principled BSDF']

    # Import images
    # TODO: Create function for getting enabled maps
    y_offset = 0
    for name in map_names:
        image_name = Global.GD_PREFIX + name
        if image_name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images.get(image_name))

        image = mat.node_tree.nodes.get(image_name)
        if image is None:
            image = mat.node_tree.nodes.new('ShaderNodeTexImage')
            image.name = image_name
            image.location = (-300, y_offset)
        y_offset -= 200

        export_name = f'{gd.export_name}_{suffix}'
        export_path = os.path.join(
            bpy.path.abspath(gd.export_path), export_name + get_format()
        )
        if not os.path.exists(export_path):
            continue
        image.image = bpy.data.images.load(export_path)

        if name not in (Global.COLOR_ID):
            image.image.colorspace_settings.name = 'Non-Color'

        # NOTE: Attempt socket match and link
        try:
            links.new(bsdf.inputs[name], image.outputs[name])
        except KeyError:
            pass


################################################
# INITIALIZATION & CLEANUP
################################################


# TODO: Preserve use_local_camera & original camera
def baker_init(self, context: Context):
    scene = context.scene
    gd = scene.gd
    render = scene.render

    # Active Camera
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                space.use_local_camera = False
                break
    scene.camera = bpy.data.objects.get(Global.TRIM_CAMERA_NAME)

    # View layer
    self.savedViewLayerUse = context.view_layer.use
    self.savedUseSingleLayer = render.use_single_layer

    context.view_layer.use = True
    render.use_single_layer = True

    if scene.world:
        scene.world.use_nodes = False

    # Render Engine (Set per bake map)
    eevee = scene.eevee
    self.savedRenderer = render.engine

    # Sampling (Set per bake map)
    self.savedWorkbenchSampling = scene.display.render_aa
    self.savedWorkbenchVPSampling = scene.display.viewport_aa
    self.savedEeveeRenderSampling = eevee.taa_render_samples
    self.savedEeveeSampling = eevee.taa_samples
    self.savedCyclesSampling = context.scene.cycles.preview_samples
    self.savedCyclesRenderSampling = context.scene.cycles.samples

    # Bloom
    self.savedUseBloom = eevee.use_bloom
    eevee.use_bloom = False

    # Ambient Occlusion
    self.savedUseAO = eevee.use_gtao
    self.savedAODistance = eevee.gtao_distance
    self.savedAOQuality = eevee.gtao_quality
    eevee.use_gtao = False # Disable unless needed for AO bakes
    eevee.gtao_distance = .2
    eevee.gtao_quality = .5

    # Color Management
    view_settings = scene.view_settings
    self.savedDisplayDevice = scene.display_settings.display_device
    self.savedViewTransform = view_settings.view_transform
    self.savedContrastType = view_settings.look
    self.savedExposure = view_settings.exposure
    self.savedGamma = view_settings.gamma
    self.savedTransparency = render.film_transparent

    # Performance
    if bpy.app.version >= (2, 83, 0):
        self.savedHQNormals = render.use_high_quality_normals
        render.use_high_quality_normals = True

    # Film
    self.savedFilterSize = render.filter_size
    self.savedFilterSizeCycles = context.scene.cycles.filter_width
    self.savedFilterSizeTypeCycles = context.scene.cycles.pixel_filter_type
    render.filter_size = \
    context.scene.cycles.filter_width = gd.filter_width
    context.scene.cycles.pixel_filter_type = 'BLACKMAN_HARRIS'

    # Dimensions (NOTE: don't bother saving these)
    render.resolution_x = gd.resolution_x
    render.resolution_y = gd.resolution_y
    render.resolution_percentage = 100

    # Output
    image_settings = render.image_settings
    self.savedColorMode = image_settings.color_mode
    self.savedFileFormat = image_settings.file_format
    self.savedColorDepth = image_settings.color_depth

    # If background plane not visible in render, create alpha channel
    if not gd.coll_rendered:
        render.film_transparent = True
        image_settings.color_mode = 'RGBA'
    else:
        image_settings.color_mode = 'RGB'

    # Format
    image_settings.file_format = gd.format
    if gd.format == 'OPEN_EXR':
        image_settings.color_depth = gd.exr_depth
    elif gd.format != 'TARGA':
        image_settings.color_depth = gd.depth

    if gd.format == "PNG":
        image_settings.compression = gd.png_compression

    # Post Processing
    self.savedUseSequencer = render.use_sequencer
    self.savedUseCompositor = render.use_compositing
    self.savedDitherIntensity = render.dither_intensity
    render.use_sequencer = render.use_compositing = False
    render.dither_intensity = 0

    # Viewport shading
    scene_shading = bpy.data.scenes[str(scene.name)].display.shading
    self.savedLight = scene_shading.light
    self.savedColorType = scene_shading.color_type
    self.savedBackface = scene_shading.show_backface_culling
    self.savedXray = scene_shading.show_xray
    self.savedShadows = scene_shading.show_shadows
    self.savedCavity = scene_shading.show_cavity
    self.savedDOF = scene_shading.use_dof
    self.savedOutline = scene_shading.show_object_outline
    self.savedShowSpec = scene_shading.show_specular_highlight
    scene_shading.show_backface_culling = \
    scene_shading.show_xray = \
    scene_shading.show_shadows = \
    scene_shading.show_cavity = \
    scene_shading.use_dof = \
    scene_shading.show_object_outline = \
    scene_shading.show_specular_highlight = False

    # Reference
    self.savedRefSelection = gd.reference.name if gd.reference else None

    # Background plane visibility
    bg_plane = bpy.data.objects.get(Global.BG_PLANE_NAME)
    bg_plane.hide_viewport = not gd.coll_visible
    bg_plane.hide_render = not gd.coll_rendered
    bg_plane.hide_set(False)


def baker_cleanup(self, context: Context) -> None:
    scene = context.scene
    gd = scene.gd
    render = scene.render

    # View layer
    context.view_layer.use = self.savedViewLayerUse
    scene.render.use_single_layer = self.savedUseSingleLayer

    if scene.world:
        scene.world.use_nodes = True

    # Render Engine
    render.engine = self.savedRenderer

    # Sampling
    scene.display.render_aa = self.savedWorkbenchSampling
    scene.display.viewport_aa = self.savedWorkbenchVPSampling
    scene.eevee.taa_render_samples = self.savedEeveeRenderSampling
    scene.eevee.taa_samples = self.savedEeveeSampling

    self.savedCyclesSampling = context.scene.cycles.preview_samples
    self.savedCyclesRenderSampling = context.scene.cycles.samples

    # Bloom
    scene.eevee.use_bloom = self.savedUseBloom

    # Ambient Occlusion
    scene.eevee.use_gtao = self.savedUseAO
    scene.eevee.gtao_distance = self.savedAODistance
    scene.eevee.gtao_quality = self.savedAOQuality

    # Color Management
    view_settings = scene.view_settings

    view_settings.look = self.savedContrastType
    scene.display_settings.display_device = self.savedDisplayDevice
    view_settings.view_transform = self.savedViewTransform
    view_settings.exposure = self.savedExposure
    view_settings.gamma = self.savedGamma

    scene.render.film_transparent = self.savedTransparency

    # Performance
    if bpy.app.version >= (2, 83, 0):
        render.use_high_quality_normals = self.savedHQNormals

    # Film
    render.filter_size = self.savedFilterSize

    context.scene.cycles.filter_width = self.savedFilterSizeCycles
    context.scene.cycles.pixel_filter_type = self.savedFilterSizeTypeCycles

    # Output
    render.image_settings.color_depth = self.savedColorDepth
    render.image_settings.color_mode = self.savedColorMode
    render.image_settings.file_format = self.savedFileFormat

    # Post Processing
    render.use_sequencer = self.savedUseSequencer
    render.use_compositing = self.savedUseCompositor

    render.dither_intensity = self.savedDitherIntensity

    scene_shading = bpy.data.scenes[str(scene.name)].display.shading

    # Refresh
    scene_shading.show_cavity = self.savedCavity
    scene_shading.color_type = self.savedColorType
    scene_shading.show_backface_culling = self.savedBackface
    scene_shading.show_xray = self.savedXray
    scene_shading.show_shadows = self.savedShadows
    scene_shading.use_dof = self.savedDOF
    scene_shading.show_object_outline = self.savedOutline
    scene_shading.show_specular_highlight = self.savedShowSpec
    scene_shading.light = self.savedLight

    if self.savedRefSelection:
        gd.reference = bpy.data.images[self.savedRefSelection]

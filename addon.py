import math
import os
import sys

bl_info = {
	"name": "BCGA",
	"author": "Vladimir Elistratov <vladimir.elistratov@gmail.com>",
	"version": (1, 0, 0),
	"blender": (2, 80, 0),
	"location": "View3D > Tool Shelf",
	"description": "BCGA: Computer Generated Architecture for Blender",
	"warning": "",
	"wiki_url": "https://github.com/vvoovv/bcga/wiki",
	"tracker_url": "https://github.com/vvoovv/bcga/issues",
	"support": "COMMUNITY",
	"category": "BCGA",
}

numFloatParams = 200
numColorParams = 50

for path in sys.path:
	if "bpro" in path:
		path = None
		break
if path:
	# we need to add path to bpro package
	sys.path.append(os.path.dirname(__file__))

import bpy
import bpro

from pro import context as proContext
from pro.base import ParamFloat, ParamColor

from bpro.bl_util import create_rectangle, align_view, first_edge_ymin


def getRuleFilePath(operator, scriptMode, textName, filePath):
	"""
	Returns the absolute path to a BCGA rule file, honoring whether the
	scene is configured to read it from a Blender Text data-block ("TEXT")
	or directly from a file on disk ("FILE").

	On any problem (nothing selected, text block not linked to a file on
	disk, file missing), reports a clear error via operator.report() and
	returns None -- callers should treat None as "cancel", instead of the
	previous behavior of silently doing nothing.
	"""
	if scriptMode == "FILE":
		path = bpy.path.abspath(filePath) if filePath else ""
		if not path:
			operator.report({"ERROR"}, "No BCGA script file selected")
			return None
		if not os.path.isfile(path):
			operator.report({"ERROR"}, "BCGA script file not found: '%s'" % path)
			return None
		return path
	# scriptMode == "TEXT"
	if not textName or textName not in bpy.data.texts:
		operator.report({"ERROR"}, "No BCGA script text block selected")
		return None
	path = bpy.data.texts[textName].filepath
	if not path:
		operator.report(
			{"ERROR"},
			"The BCGA script text block '%s' isn't linked to a file on disk. "
			"Either open it from an existing .py file (Text Editor > Open), "
			"or switch to 'External File' mode above and point at a .py file directly."
			% textName,
		)
		return None
	return path


def _groupParams(params):
	"""
	Groups a list of (paramName, paramInstance) tuples -- as returned by
	bpro.getParams() -- by each param's optional .group attribute (set via
	pro.base.param(value, group=..., unit=...) in a rule file).
	Returns an ordered list of (groupName, [(paramName, paramInstance), ...])
	tuples, preserving first-seen order. Params without an explicit group
	land together under "Other", so old rule files that never use group=
	still render exactly as a single flat list, unchanged.

	Pure Python, no bpy dependency -- kept separate from Pro.draw() so it
	can be unit tested without a real bpy.types.UILayout.
	"""
	groups = {}
	order = []
	for paramName, paramInstance in params:
		groupName = getattr(paramInstance, "group", None) or "Other"
		if groupName not in groups:
			groups[groupName] = []
			order.append(groupName)
		groups[groupName].append((paramName, paramInstance))
	return [(groupName, groups[groupName]) for groupName in order]


bpy.types.Scene.bcgaScript = bpy.props.StringProperty(
	name = "Script",
	description = "Path to a BCGA script",
)

bpy.types.Scene.bcgaScriptMode = bpy.props.EnumProperty(
	name = "Script Source",
	description = "Where to read the BCGA rule script from",
	items = [
		("TEXT", "Text Block", "Use a script stored as a Blender Text data-block"),
		("FILE", "External File", "Use a .py file directly from disk -- re-read fresh every time you click Apply, so edits made in your own editor take effect immediately"),
	],
	default = "TEXT",
)

bpy.types.Scene.bcgaScriptFile = bpy.props.StringProperty(
	name = "Script File",
	description = "Path to an external BCGA rule .py file on disk",
	subtype = "FILE_PATH",
)

bpy.types.Scene.bakingBcgaScript = bpy.props.StringProperty(
	name = "Low poly script",
	description = "Path to a BCGA script with a low poly model",
)

bpy.types.Scene.bakingBcgaScriptMode = bpy.props.EnumProperty(
	name = "Low Poly Script Source",
	description = "Where to read the low poly BCGA rule script from",
	items = [
		("TEXT", "Text Block", "Use a script stored as a Blender Text data-block"),
		("FILE", "External File", "Use a .py file directly from disk"),
	],
	default = "TEXT",
)

bpy.types.Scene.bakingBcgaScriptFile = bpy.props.StringProperty(
	name = "Low Poly Script File",
	description = "Path to an external low poly BCGA rule .py file on disk",
	subtype = "FILE_PATH",
)

class CustomFloatProperty(bpy.types.PropertyGroup):
	"""A bpy.types.PropertyGroup descendant for bpy.props.CollectionProperty"""
	value: bpy.props.FloatProperty(name="")

class CustomColorProperty(bpy.types.PropertyGroup):
	"""A bpy.types.PropertyGroup descendant for bpy.props.CollectionProperty"""
	value: bpy.props.FloatVectorProperty(name="", subtype='COLOR', min=0.0, max=1.0)

class ProMainPanel(bpy.types.Panel):
	bl_label = "Main"
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	#bl_context = "objectmode"
	bl_category = "BCGA"
	
	def draw(self, context):
		scene = context.scene
		layout = self.layout
		layout.row().operator("object.footprint_set", text="Footprint")
		layout.separator()
		layout.row().prop(scene, "bcgaScriptMode", expand=True)
		if scene.bcgaScriptMode == "FILE":
			layout.row().prop(scene, "bcgaScriptFile", text="")
		else:
			layout.row().prop_search(scene, "bcgaScript", bpy.data, "texts", text="")
		layout.row().operator("object.apply_pro_script")


class BakingPanel(bpy.types.Panel):
	bl_label = "Baking"
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "BCGA"
	bl_options = {"DEFAULT_CLOSED"}
	
	def draw(self, context):
		scene = context.scene
		layout = self.layout
		layout.row().prop(scene, "bakingBcgaScriptMode", expand=True)
		if scene.bakingBcgaScriptMode == "FILE":
			layout.row().prop(scene, "bakingBcgaScriptFile", text="")
		else:
			layout.row().prop_search(scene, "bakingBcgaScript", bpy.data, "texts", text="")
		self.layout.operator("object.bake_pro_model")


class FirstEdgePanel(bpy.types.Panel):
	bl_label = "First edge"
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "BCGA"
	bl_options = {"DEFAULT_CLOSED"}
	
	def draw(self, context):
		self.layout.operator("object.first_edge_ymin")


class Pro(bpy.types.Operator):
	bl_idname = "object.apply_pro_script"
	bl_label = "Apply"
	bl_options = {"REGISTER", "UNDO"}
	
	collectionFloat: bpy.props.CollectionProperty(type=CustomFloatProperty)
	collectionColor: bpy.props.CollectionProperty(type=CustomColorProperty)
	
	initialized = False
	
	def initialize(self):
		if self.initialized:
			return
		for _ in range(numFloatParams):
			self.collectionFloat.add()
		for _ in range(numColorParams):
			self.collectionColor.add()
		self.initialized = True
	
	def invoke(self, context, event):
		self.initialize()
		proContext.blenderContext = context
		scene = context.scene
		ruleFile = getRuleFilePath(self, scene.bcgaScriptMode, scene.bcgaScript, scene.bcgaScriptFile)
		if ruleFile:
			# append the directory of the ruleFile to sys.path
			ruleFileDirectory = os.path.dirname(os.path.realpath(os.path.expanduser(ruleFile)))
			if ruleFileDirectory not in sys.path:
				sys.path.append(ruleFileDirectory)

			try:
				module, params = bpro.apply(ruleFile)
			except Exception as e:
				self.report({"ERROR"}, "Failed to apply BCGA script '%s': %s" % (ruleFile, e))
				return {"CANCELLED"}

			#align_view(context.object)

			self.module = module
			self.params = params
			numFloats = 0
			numColors = 0
			# for each entry in self.params create a new item in self.collection
			for param in self.params:
				param = param[1]
				if isinstance(param, ParamFloat):
					collectionItem = self.collectionFloat[numFloats]
					numFloats += 1
				elif isinstance(param, ParamColor):
					collectionItem = self.collectionColor[numColors]
					numColors += 1
				collectionItem.value = param.getValue()
				param.collectionItem = collectionItem
			return {"FINISHED"}
		return {"CANCELLED"}
	
	def execute(self, context):
		proContext.blenderContext = context
		for param in self.params:
			param = param[1]
			param.setValue(getattr(param.collectionItem, "value"))
		try:
			bpro.apply(self.module)
		except Exception as e:
			self.report({"ERROR"}, "Failed to apply BCGA script: %s" % e)
			return {"CANCELLED"}
		
		#align_view(context.object)
		
		return {"FINISHED"}
	
	def draw(self, context):
		layout = self.layout
		if hasattr(self, "params"):
			# self.params is a list of tuples: (paramName, instanceofParamClass),
			# grouped by each param's optional group=... (see pro.base.param())
			for groupName, groupParams in _groupParams(self.params):
				box = layout.box()
				box.label(text=groupName)
				for paramName, paramInstance in groupParams:
					row = box.split()
					unit = getattr(paramInstance, "unit", None)
					row.label(text="%s (%s):" % (paramName, unit) if unit else paramName + ":")
					row.prop(paramInstance.collectionItem, "value")


class Bake(bpy.types.Operator):
	bl_idname = "object.bake_pro_model"
	bl_label = "Bake"
	bl_options = {"REGISTER", "UNDO"}

	@classmethod
	def poll(cls, context):
		return context.scene.render.engine == "CYCLES"

	def execute(self, context):
		proContext.blenderContext = context
		scene = context.scene
		bpy.ops.object.select_all(action="DESELECT")
		# remember the original object, it will be used for low poly model
		lowPolyObject = context.object
		lowPolyObject.select_set(True)
		bpy.ops.object.duplicate()
		highPolyObject = context.object
		# high poly model
		ruleFile = getRuleFilePath(self, scene.bcgaScriptMode, scene.bcgaScript, scene.bcgaScriptFile)
		if not ruleFile:
			return {"CANCELLED"}
		try:
			highPolyParams = bpro.apply(ruleFile)[1]
		except Exception as e:
			self.report({"ERROR"}, "Failed to apply high poly BCGA script '%s': %s" % (ruleFile, e))
			return {"CANCELLED"}
		# convert highPolyParams to a dict paramName->instanceofParamClass
		highPolyParams = dict(highPolyParams)

		# low poly model
		context.view_layer.objects.active = lowPolyObject
		ruleFile = getRuleFilePath(self, scene.bakingBcgaScriptMode, scene.bakingBcgaScript, scene.bakingBcgaScriptFile)
		if not ruleFile:
			return {"CANCELLED"}
		name = lowPolyObject.name
		try:
			module = bpro.getModule(ruleFile)
			lowPolyParams = bpro.getParams(module)
			# Apply highPolyParams to lowPolyParams
			# Normally lowPolyParams is a subset of highPolyParams
			for paramName,param in lowPolyParams:
				if paramName in highPolyParams:
					param.setValue(highPolyParams[paramName].getValue())
			bpro.apply(module)
		except Exception as e:
			self.report({"ERROR"}, "Failed to apply low poly BCGA script '%s': %s" % (ruleFile, e))
			return {"CANCELLED"}
		# unwrap the low poly model
		bpy.ops.object.mode_set(mode="EDIT")
		bpy.ops.mesh.select_all(action="SELECT")
		bpy.ops.uv.smart_project()
		# prepare settings for baking
		bpy.ops.object.mode_set(mode="OBJECT")
		highPolyObject.select_set(True)
		bpy.context.scene.cycles.bake_type = "DIFFUSE"
		bpy.context.scene.cycles.use_bake_selected_to_active = True
		# create a new image with default settings for baking
		image = bpy.data.images.new(name=name, width=512, height=512)
		# finally perform baking
		bpy.ops.object.bake_image()
		# delete the high poly object and its mesh
		context.view_layer.objects.active = highPolyObject
		mesh = highPolyObject.data
		bpy.ops.object.delete()
		bpy.data.meshes.remove(mesh)
		context.view_layer.objects.active = lowPolyObject
		# assign the baked texture to the low poly object
		blenderTexture = bpy.data.textures.new(name, type = "IMAGE")
		blenderTexture.image = image
		blenderTexture.use_alpha = True
		material = bpy.data.materials.new(name)
		# textureSlot = material.texture_slots.add()
		# textureSlot.texture = blenderTexture
		# textureSlot.texture_coords = "UV"
		# textureSlot.uv_layer = "bcga"
		lowPolyObject.data.materials.append(material)
		return {"FINISHED"}


class FootprintSet(bpy.types.Operator):
	bl_idname = "object.footprint_set"
	bl_label = "BCGA footprint"
	bl_description = "Set a building footprint for BCGA"
	bl_options = {"REGISTER", "UNDO"}
	
	width: bpy.props.FloatProperty(
		name = "Width", description = "Footprint width in meters",
		default = 20.0, min = 0.01, soft_max = 200.0, unit = "LENGTH",
	)
	depth: bpy.props.FloatProperty(
		name = "Depth", description = "Footprint depth in meters",
		default = 10.0, min = 0.01, soft_max = 200.0, unit = "LENGTH",
	)
	
	def execute(self, context):
		lightOffset = 20
		lightHeight = 20
		scene = context.scene
		# delete active object if it is a mesh
		active = context.object
		if active and active.type=="MESH":
			bpy.ops.object.delete()
		# getting width and height of the footprint
		w, h = self.width, self.depth
		# add lights
		rx = math.atan((h+lightOffset)/lightHeight)
		rz = math.atan((w+lightOffset)/(h+lightOffset))
		def lamp_add(x, y, rx, rz):
			bpy.ops.object.light_add(
				type="SUN",
				location=((x,y,lightHeight)),
				rotation=(rx, 0, rz)
			)
			context.active_object.data.energy = 0.5
		lamp_add(w+lightOffset, h+lightOffset, -rx, -rz)
		lamp_add(-w-lightOffset, h+lightOffset, -rx, rz)
		lamp_add(-w-lightOffset, -h-lightOffset, rx, -rz)
		lamp_add(w+lightOffset, -h-lightOffset, rx, rz)
		
		create_rectangle(context, w, h)
		# align_view() needs a live 3D viewport; skip it gracefully when this
		# operator is called headlessly/from a script instead of crashing
		if context.area and context.area.type == "VIEW_3D":
			align_view(context.object)
		
		return {"FINISHED"}


class FirstEdgeYmin(bpy.types.Operator):
	bl_idname = "object.first_edge_ymin"
	bl_label = "Contains min Y"
	bl_description = "The first edge contains the vertex with minimal Y coordinate and has a longer length"
	bl_options = {"REGISTER", "UNDO"}
	
	def execute(self, context):
		first_edge_ymin(context)
		return {"FINISHED"}


classes = (
	CustomColorProperty,
	CustomFloatProperty,
    FirstEdgeYmin,
    FootprintSet,
    Bake,
	Pro,
	ProMainPanel,
	BakingPanel,
	FirstEdgePanel
)
register, unregister = bpy.utils.register_classes_factory(classes)

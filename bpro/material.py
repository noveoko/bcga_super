import bpy

from pro import context


class MaterialManager:

    # Node-based material creation works the same way for every modern
    # Blender render engine (Cycles, EEVEE, EEVEE Next), so a single
    # engine implementation is used as the default for any engine
    # identifier we don't recognize. This also future-proofs against
    # new engine identifiers Blender adds later.
    defaultEngine = None

    def __init__(self):
        # a dict materialName->materialIndex, where materialIndex is the material index for the active Blender object
        self.reg = {}
        # initialize engines
        # NOTE: "BLENDER_RENDER" (Blender Internal) was removed in Blender 2.80
        # and material.texture_slots along with it, so that legacy engine
        # is intentionally not supported here. Any unrecognized engine
        # identifier falls back to the node-based implementation below.
        nodeBasedRender = CyclesRender()
        self.engines = {
            "CYCLES": nodeBasedRender,
            "BLENDER_EEVEE": nodeBasedRender,
            "BLENDER_EEVEE_NEXT": nodeBasedRender,
        }
        MaterialManager.defaultEngine = nodeBasedRender

    def getMaterial(self, name):
        """
        Returns Blender material for the specified name or None if the material doesn't exist
        for the given name
        """
        material = None
        reg = self.reg
        objectMaterials = bpy.context.object.data.materials
        allMaterials = bpy.data.materials
        if name in reg:
            # we have already met that material before
            materialIndex = reg[name]
            material = objectMaterials[materialIndex]
        elif name in objectMaterials:
            # The material was set for the active Blender object before
            # the current rule set had been applied to it
            material = objectMaterials[name]
            # find materialIndex
            for materialIndex in range(len(objectMaterials)):
                if objectMaterials[materialIndex] == material:
                    break
            reg[name] = materialIndex
        elif name in allMaterials:
            # The material is already available, but not yet used by the active Blender object
            material = allMaterials[name]
            self.setMaterial(name, material)
        return material

    def setMaterial(self, name, material):
        """
        Appends the material to the active Blender object and register it with self.reg
        """
        objectMaterials = bpy.context.object.data.materials
        materialIndex = len(objectMaterials)
        objectMaterials.append(material)
        self.reg[name] = materialIndex

    def getMaterialIndex(self, name):
        if not name in self.reg:
            self.getMaterial(name)
        return self.reg[name]

    def createMaterial(self, name, textures):
        """
        Creates a new material and calls self.setMaterial(...)
        """
        engine = context.blenderContext.scene.render.engine
        renderer = self.engines.get(engine, self.defaultEngine)
        try:
            material = renderer.createMaterial(name, textures)
        except RuntimeError:
            material = None
        else:
            self.setMaterial(name, material)
        return material

    def setPreviewTexture(self, shape, materialIndex):
        # a slot for the texture
        materials = bpy.context.object.data.materials
        if len(materials) == 0:
            return
        # slot = materials[materialIndex].texture_slots[0]
        # if slot:
        #     shape.face[context.bm.faces.layers.tex.active].image = slot.texture.image


class CyclesRender:
    def createMaterial(self, name, textures):
        texture = textures[0]
        material = bpy.data.materials.new(name)
        material.use_nodes = True
        nodes = material.node_tree
        links = nodes.links
        nodes = nodes.nodes
        # there must be two connected nodes by default: ShaderNodeBsdfDiffuse and ShaderNodeOutputMaterial
        diffuseShader = nodes[1]

        # create ShaderNodeTexImage
        textureNode = nodes.new("ShaderNodeTexImage")
        textureNode.image = bpy.data.images.load(texture.path)
        textureNode.location = -200, 300
        # connect textureNode and diffuseShader
        links.new(textureNode.outputs[0], diffuseShader.inputs[0])

        # create ShaderNodeUVMap
        uvNode = nodes.new("ShaderNodeUVMap")
        uvNode.uv_map = texture.layer
        uvNode.location = -400, 300
        # connect uvNode and textureNode
        links.new(uvNode.outputs[0], textureNode.inputs[0])

        return material

import bpy
import pro
from pro import context


class Color(pro.op_color.Color):
    def execute(self):
        materialManager = context.materialManager
        colorHex = self.colorHex
        material = materialManager.getMaterial(colorHex)
        if material:
            materialIndex = materialManager.getMaterialIndex(colorHex)
        else:
            material = bpy.data.materials.new(colorHex)
            rgba = (self.color[0], self.color[1], self.color[2], 1.0)
            material.diffuse_color = rgba
            material.use_nodes = True
            bsdf = material.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                bsdf.inputs["Base Color"].default_value = rgba
                if "Roughness" in bsdf.inputs:
                    bsdf.inputs["Roughness"].default_value = 0.72
            materialManager.setMaterial(colorHex, material)
            materialIndex = materialManager.getMaterialIndex(colorHex)
        # Assign material to the current shape.
        # The current shape is usually a single 2D face (Shape2d/Rectangle).
        # It can also be a Shape3d -- a volume made up of several faces --
        # e.g. right after extrude() and before any decompose()/comp() call
        # splits it back into faces. Shape3d has no .face/.clearUVlayers()
        # of its own, so apply the material to each of its constituent
        # 2D faces instead, consistent with how extrude()'s
        # inheritMaterialAll already assigns material_index per-face.
        shape = context.getState().shape
        for shape2d in getattr(shape, "shapes", (shape,)):
            shape2d.clearUVlayers()
            shape2d.face.material_index = materialIndex

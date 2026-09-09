import bpy
import pro
from pro import context
from pro.rule_context import resolve_rule_context


class Material(pro.op_material.Material):
    def execute(self, ctx=None):
        ctx = resolve_rule_context(ctx)
        materialManager = ctx.materialManager
        material = materialManager.getMaterial(self.material)
        if material:
            materialIndex = materialManager.getMaterialIndex(self.material)

            # assign material to the bmesh face
            shape = ctx.getState().shape
            shape.clearUVlayers()
            shape.face.material_index = materialIndex

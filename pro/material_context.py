"""
MaterialContext — per-apply material registry (Phase 4).

bpy-free interface. Blender MaterialManager construction lives in
bpro.backends.BlenderMaterialBackend.
"""


class MaterialContext:
    """Holds the material manager for one building apply."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.manager = None
        self._backend = None

    def attach(self, *, manager, backend=None):
        self.manager = manager
        self._backend = backend
        return self

    @property
    def materialManager(self):
        """Compat alias matching historical context.materialManager."""
        return self.manager

    @materialManager.setter
    def materialManager(self, value):
        self.manager = value

    def render_engine(self):
        """
        Optional hook for backends that expose the active render engine id.
        Returns None if no backend is attached.
        """
        if self._backend is None:
            return None
        getter = getattr(self._backend, "render_engine", None)
        return getter() if getter else None

    def close(self):
        if self._backend is not None:
            closer = getattr(self._backend, "close", None)
            if closer is not None:
                closer(self)
        self.reset()

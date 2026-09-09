"""
GeometryContext — per-apply geometry state (Phase 4).

bpy-free interface. Blender-specific construction lives in
bpro.backends.BlenderGeometryBackend.
"""


class GeometryContext:
    """
    Holds the mesh/bmesh handle, vertex registry, faces marked for removal,
    and the join manager for one building apply.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.bm = None
        self.facesForRemoval = []
        self.vertexRegistry = None
        self.joinManager = None  # always an *instance* after ensure_join_manager()
        self._join_manager_factory = None
        self._backend = None

    def attach(
        self,
        *,
        bm,
        vertex_registry,
        faces_for_removal=None,
        join_manager_factory=None,
        backend=None,
    ):
        """Attach geometry resources created by a backend for this apply."""
        self.bm = bm
        self.vertexRegistry = vertex_registry
        self.facesForRemoval = list(faces_for_removal or [])
        self._join_manager_factory = join_manager_factory
        self.joinManager = None
        self._backend = backend
        return self

    def create_join_manager(self):
        """
        Instantiate (or return) the join manager for deferred joins.

        Replaces the old footgun of storing the JoinManager *class* on
        context and doing `self.joinManager = self.joinManager()`.
        """
        if self.joinManager is not None and not isinstance(self.joinManager, type):
            return self.joinManager
        factory = self._join_manager_factory
        if factory is None and isinstance(self.joinManager, type):
            factory = self.joinManager
        if factory is None:
            raise RuntimeError(
                "GeometryContext has no join_manager_factory; "
                "attach one via GeometryContext.attach(...) / BlenderGeometryBackend"
            )
        self.joinManager = factory()
        return self.joinManager

    # Alias used by executeDeferred migration
    ensure_join_manager = create_join_manager

    @property
    def api(self):
        """
        Active GeometryBackend for mesh ops (extrude/translate/…).

        Phase 4 only lifecycle-managed bmesh; Priority 3 expands the backend
        into a full GeometryBackend Protocol implementation.
        """
        if self._backend is None:
            raise RuntimeError(
                "GeometryContext has no geometry backend attached; "
                "call attach_blender_backends(...) or attach_memory_backends(...)"
            )
        return self._backend

    def close(self):
        """Release per-apply geometry resources (bm freed by backend if owned)."""
        if self._backend is not None:
            closer = getattr(self._backend, "close", None)
            if closer is not None:
                closer(self)
        self.reset()

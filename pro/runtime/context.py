import random as randomlib

from ..geometry import GeometryContext
from ..material_context import MaterialContext
from .state import State


class RandomContext:
	"""Deterministic RNG owned by a generation session / Context façade."""

	def __init__(self, seed=None):
		self.seed = seed
		self.rng = randomlib.Random(seed)

	def set_seed(self, seed):
		self.seed = seed
		self.rng = randomlib.Random(seed)

	def uniform(self, low, high):
		return self.rng.uniform(low, high)

	def choice(self, seq):
		return self.rng.choice(seq)

	def choices(self, population, weights=None, *, cum_weights=None, k=1):
		return self.rng.choices(
			population, weights=weights, cum_weights=cum_weights, k=k
		)

	def random(self):
		return self.rng.random()


class TraceContext:
	"""Execution-trace flags and the last resolved buildingTrace dict."""

	def __init__(self):
		self.tracing = False
		self.buildingTrace = None


# Shared across all Context instances / GenerationSessions. buildFactory()
# (bpro) fills this once at import; reset() must never replace it with a
# fresh dict or DSL operators stop resolving.
_OPERATOR_FACTORY = {}


class Context:
	"""
	Per-session execution state composed of typed sub-contexts.

	The module-level `context` object is a ContextProxy that forwards to the
	active GenerationSession's Context (or to a process default when no
	session is active). Rule files keep reading context.rng / context.tracing
	etc. unchanged.
	"""

	def __init__(self):
		# set by city_builder.py / GenerationSession before each block
		self.cityBlock = None
		self.blenderContext = None
		self.random = RandomContext()
		self.trace = TraceContext()
		self.geometry = GeometryContext()
		self.materials = MaterialContext()
		self.allCeilingLights = []
		self.allGameDoors = []
		self.reset()
		
	def reset(self):
		# Always the shared operator factory — never a per-instance {} 
		self.factory = _OPERATOR_FACTORY

	# --- attribute aliases (compat with pre-session code) -----------------

	@property
	def seed(self):
		return self.random.seed

	@seed.setter
	def seed(self, value):
		self.random.seed = value

	@property
	def rng(self):
		return self.random.rng

	@rng.setter
	def rng(self, value):
		self.random.rng = value

	@property
	def tracing(self):
		return self.trace.tracing

	@tracing.setter
	def tracing(self, value):
		self.trace.tracing = bool(value)

	@property
	def buildingTrace(self):
		return self.trace.buildingTrace

	@buildingTrace.setter
	def buildingTrace(self, value):
		self.trace.buildingTrace = value

	# Geometry / material aliases (Phase 4) — operators keep using ctx.bm etc.
	@property
	def bm(self):
		return self.geometry.bm

	@bm.setter
	def bm(self, value):
		self.geometry.bm = value

	@property
	def facesForRemoval(self):
		return self.geometry.facesForRemoval

	@facesForRemoval.setter
	def facesForRemoval(self, value):
		self.geometry.facesForRemoval = value

	@property
	def vertexRegistry(self):
		return self.geometry.vertexRegistry

	@vertexRegistry.setter
	def vertexRegistry(self, value):
		self.geometry.vertexRegistry = value

	@property
	def joinManager(self):
		return self.geometry.joinManager

	@joinManager.setter
	def joinManager(self, value):
		self.geometry.joinManager = value

	@property
	def materialManager(self):
		return self.materials.manager

	@materialManager.setter
	def materialManager(self, value):
		self.materials.manager = value

	def set_seed(self, seed):
		"""Set the seed for BCGA's private random-number generator.

		Calling this once before a batch keeps successive buildings on the
		same deterministic random stream instead of restarting every building.
		"""
		self.random.set_seed(seed)
	
	def __call__(self):
		self.reset()
	
	# Routed through GeometryContext / MaterialContext when set via addAttribute
	_BACKEND_ATTRS = frozenset({
		"bm", "facesForRemoval", "vertexRegistry", "joinManager", "materialManager",
	})

	def addAttribute(self, attr, value):
		# Prefer GeometryContext / MaterialContext for known backend slots so
		# legacy addAttribute("bm", ...) still works during the Phase 4 migrate.
		if attr == "bm":
			self.geometry.bm = value
		elif attr == "facesForRemoval":
			self.geometry.facesForRemoval = value
		elif attr == "vertexRegistry":
			self.geometry.vertexRegistry = value
		elif attr == "joinManager":
			# May be a class (legacy) or instance; GeometryContext handles both.
			if isinstance(value, type):
				self.geometry._join_manager_factory = value
				self.geometry.joinManager = None
			else:
				self.geometry.joinManager = value
		elif attr == "materialManager":
			self.materials.manager = value
		else:
			setattr(self, attr, value)
		if attr not in self.attrs:
			self.attrs.append(attr)
	
	def removeAttributes(self):
		attrs = getattr(self, "attrs", None) or []
		for attr in list(attrs):
			if attr in self._BACKEND_ATTRS:
				# Owned/closed by geometry.close() / materials.close()
				continue
			if hasattr(self, attr):
				try:
					delattr(self, attr)
				except AttributeError:
					pass
		self.attrs = []
	
	def getState(self):
		return self.stack[-1]
	
	def pushState(self, **kwargs):
		# create a new execution state entry
		state = State(**kwargs)
		self.stack.append(state)
		return state
	
	def popState(self):
		self.stack.pop()
	
	def registerParam(self, param):
		self.params.append(param)
		
	def init(self):
		# implementation specific attributes
		self.attrs = []
		# stack to track branching
		self.stack = []
		self.deferreds = []
		# the list of params
		self.params = []

	def begin_apply(self):
		"""Start a single building apply: reset per-apply DSL/geometry slots."""
		self.init()
		self.geometry.reset()
		self.materials.reset()
		self.ceilingLights = []
		self.gameDoors = []
		if getattr(self, "allCeilingLights", None) is None:
			self.allCeilingLights = []
		if getattr(self, "allGameDoors", None) is None:
			self.allGameDoors = []
		self.operator = None
		self.trace.buildingTrace = None

	def end_apply(self, exc=None):
		"""
		Always-safe cleanup after one apply (success or failure).

		Closes GeometryContext / MaterialContext (Phase 4), clears any leftover
		addAttribute slots, plus operator stack leftovers.
		Leaves session-level fields (cityBlock, seed/rng, all* accumulators,
		factory) intact for the next building in the batch.
		"""
		self.geometry.close()
		self.materials.close()
		self.removeAttributes()
		self.operator = None
		self.stack = []
		self.deferreds = []
		self.params = []
		# per-building light/door lists are consumed by the orchestrator before
		# end_apply; clear so a failed apply cannot leak into the next one
		self.ceilingLights = []
		self.gameDoors = []
	
	def prepare(self):
		"""The method does all necessary preparations for a rule evaluation."""
		# Resolve deferred ParamFloat (random/choice) and ParamColor (choice)
		# values. Both expose assignValue(); ParamColor also has `.random`
		# (the Choice instance, or None) so a `if param.random` check is
		# safe, matching ParamFloat.
		for param in self.params:
			assign = getattr(param, "assignValue", None)
			if callable(assign):
				assign()
	
	def addDeferred(self, shape, deferredOperator):
		self.deferreds.append((shape, deferredOperator))
	
	def executeDeferred(self):
		# Instantiate join manager via GeometryContext (no class-vs-instance swap).
		jm = self.geometry.create_join_manager()
		for entry in self.deferreds:
			# entry[1] is operator
			# entry[0] is shape
			entry[1].resolve(entry)
		jm.finalize()


_default_context = Context()


class ContextProxy:
	"""
	Module-level context facade.

	Attribute access forwards to the active GenerationSession's Context when
	one is active, otherwise to the process default Context. This lets
	from pro import context keep working while orchestrators isolate runs
	via GenerationSession.
	"""

	def _target(self):
		# Lazy import avoids a circular load with pro.session.
		from ..session import get_active_session
		session = get_active_session()
		if session is not None:
			return session.context
		return _default_context

	def __getattr__(self, name):
		return getattr(self._target(), name)

	def __setattr__(self, name, value):
		setattr(self._target(), name, value)

	def __delattr__(self, name):
		delattr(self._target(), name)


context = ContextProxy()

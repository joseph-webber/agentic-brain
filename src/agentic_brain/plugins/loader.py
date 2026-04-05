import importlib
import importlib.util
import inspect
import logging
import pkgutil
from typing import Dict, List, Tuple

from .base import PluginBase, discover_plugins_in_module

logger = logging.getLogger(__name__)


def _import_module_from_path(path: str, name: str = None):
    """Import a module given a filesystem path to a .py file."""
    name = name or path.replace("/", ".")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None:
        raise ImportError(f"Cannot import from {path}")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    if loader is None:
        raise ImportError(f"No loader for {path}")
    loader.exec_module(module)
    return module


def load_plugins_from_directory(directory: str) -> Dict[str, type]:
    """Load plugin classes from a directory (non-recursive).

    Returns mapping plugin_name -> plugin class
    """
    plugins: Dict[str, type] = {}
    for finder, name, ispkg in pkgutil.iter_modules([directory]):
        # import by spec
        try:
            module_path = f"{directory}/{name}.py"
            mod = _import_module_from_path(module_path, name=f"plugins.{name}")
            for pcls in discover_plugins_in_module(mod):
                plugins[pcls.name] = pcls
        except FileNotFoundError:
            logger.debug("File not found for module %s", name)
        except Exception:
            logger.exception("Error loading plugin module %s", name)
    return plugins


def load_plugins_from_entry_points(group: str = "agentic_brain.plugins") -> Dict[str, type]:
    """Load plugin callables registered via packaging entry points.

    Returns mapping plugin_name -> plugin class
    """
    plugins: Dict[str, type] = {}
    try:
        # importlib.metadata API
        try:
            from importlib.metadata import entry_points

            eps = entry_points()
            # new API returns EntryPoints object
            entries = []
            # support both data shapes
            if hasattr(eps, 'select'):
                entries = eps.select(group=group)
            else:
                entries = [e for e in eps.get(group, [])]
        except Exception:
            # older API (pkg_resources)
            import pkg_resources

            entries = list(pkg_resources.iter_entry_points(group))

        for ep in entries:
            try:
                obj = ep.load()
                if inspect.isclass(obj) and issubclass(obj, PluginBase):
                    plugins[obj.name] = obj
            except Exception:
                logger.exception("Error loading entry point %s", ep)
    except Exception:
        logger.exception("Error enumerating entry points for %s", group)
    return plugins


class DependencyResolutionError(Exception):
    pass


def resolve_dependencies(plugins: Dict[str, type]) -> List[type]:
    """Topologically sort plugins based on their .dependencies attribute.

    plugins: mapping name->plugin class
    returns: ordered list of plugin classes
    """
    graph = {name: set(getattr(cls, 'dependencies', []) or []) for name, cls in plugins.items()}

    # remove unknown dependencies (assume external)
    for name, deps in graph.items():
        graph[name] = set(d for d in deps if d in graph)

    ordered = []
    temp = set()
    perm = set()

    def visit(n):
        if n in perm:
            return
        if n in temp:
            raise DependencyResolutionError(f"Cycle detected at {n}")
        temp.add(n)
        for m in graph.get(n, ()):  # type: ignore
            visit(m)
        temp.remove(n)
        perm.add(n)
        ordered.append(plugins[n])

    for n in list(graph.keys()):
        if n not in perm:
            visit(n)

    return ordered


def load_all_plugins(directory: str = None, entry_point_group: str = "agentic_brain.plugins") -> List[type]:
    """Convenience loader that loads from directory and entry points and resolves dependencies.

    Returns ordered list of plugin classes
    """
    plugins = {}
    if directory:
        plugins.update(load_plugins_from_directory(directory))
    try:
        plugins.update(load_plugins_from_entry_points(entry_point_group))
    except Exception:
        # ignore entry point errors
        pass
    ordered = resolve_dependencies(plugins)
    return ordered

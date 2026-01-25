"""
Plugin and Extension Architecture

This module provides a flexible extension system for customizing the NFC Tap Logger.
It enables:
- Plugin discovery and loading
- Hook-based event system
- Custom processors and handlers
- Service customization without code changes

The architecture follows the Open/Closed principle - open for extension,
closed for modification.
"""

import logging
import importlib
import importlib.util
from abc import ABC, abstractmethod
from pathlib import Path
from typing import (
    Dict, List, Optional, Any, Callable, TypeVar, Generic,
    Set, Type, Union
)
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime

logger = logging.getLogger(__name__)


class HookPriority(Enum):
    """Priority levels for hook execution order"""
    HIGHEST = 0
    HIGH = 25
    NORMAL = 50
    LOW = 75
    LOWEST = 100


class HookType(Enum):
    """Types of hooks available in the system"""
    # Event lifecycle hooks
    PRE_EVENT_LOG = auto()
    POST_EVENT_LOG = auto()
    EVENT_VALIDATION = auto()

    # Card lifecycle hooks
    CARD_DETECTED = auto()
    CARD_INITIALIZED = auto()
    CARD_REMOVED = auto()

    # Session hooks
    SESSION_START = auto()
    SESSION_END = auto()

    # Service hooks
    SERVICE_START = auto()
    SERVICE_END = auto()
    QUEUE_UPDATE = auto()

    # System hooks
    SYSTEM_HEALTH_CHECK = auto()
    SYSTEM_STARTUP = auto()
    SYSTEM_SHUTDOWN = auto()

    # Dashboard hooks
    DASHBOARD_RENDER = auto()
    METRICS_CALCULATE = auto()

    # Custom hooks
    CUSTOM = auto()


@dataclass
class HookContext:
    """Context passed to hook handlers"""
    hook_type: HookType
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = "system"
    cancellable: bool = True
    _cancelled: bool = field(default=False, init=False)

    def cancel(self) -> None:
        """Cancel the operation (if cancellable)"""
        if self.cancellable:
            self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        """Check if operation was cancelled"""
        return self._cancelled


@dataclass
class HookResult:
    """Result from a hook handler"""
    success: bool
    modified_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


T = TypeVar('T')


class ExtensionPoint(Generic[T], ABC):
    """
    Base class for extension points.

    An extension point defines an interface that plugins can implement
    to extend system functionality.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this extension point"""
        pass

    @property
    def description(self) -> str:
        """Description of what this extension point does"""
        return ""


class Plugin(ABC):
    """
    Base class for all plugins.

    Plugins must implement this interface to be loaded by the system.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin name"""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version (semver recommended)"""
        pass

    @property
    def description(self) -> str:
        """Plugin description"""
        return ""

    @property
    def author(self) -> str:
        """Plugin author"""
        return ""

    @property
    def dependencies(self) -> List[str]:
        """List of plugin names this plugin depends on"""
        return []

    def on_load(self) -> None:
        """Called when plugin is loaded"""
        pass

    def on_unload(self) -> None:
        """Called when plugin is unloaded"""
        pass

    def register_hooks(self, registry: 'HookRegistry') -> None:
        """Register hooks with the hook registry"""
        pass


# =============================================================================
# Hook Handler Types
# =============================================================================

HookHandler = Callable[[HookContext], HookResult]


@dataclass
class HookRegistration:
    """Represents a registered hook handler"""
    hook_type: HookType
    handler: HookHandler
    priority: HookPriority
    plugin_name: str
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class HookRegistry:
    """
    Central registry for hook handlers.

    This registry manages hook registration, execution, and lifecycle.
    Hooks are executed in priority order (lowest value first).
    """

    def __init__(self):
        self._hooks: Dict[HookType, List[HookRegistration]] = {}
        self._custom_hooks: Dict[str, List[HookRegistration]] = {}

    def register(
        self,
        hook_type: HookType,
        handler: HookHandler,
        priority: HookPriority = HookPriority.NORMAL,
        plugin_name: str = "anonymous",
        **metadata
    ) -> HookRegistration:
        """
        Register a hook handler.

        Args:
            hook_type: Type of hook to register for
            handler: The handler function
            priority: Execution priority
            plugin_name: Name of the plugin registering this hook
            **metadata: Additional metadata

        Returns:
            The hook registration object
        """
        registration = HookRegistration(
            hook_type=hook_type,
            handler=handler,
            priority=priority,
            plugin_name=plugin_name,
            metadata=metadata
        )

        if hook_type not in self._hooks:
            self._hooks[hook_type] = []

        self._hooks[hook_type].append(registration)
        self._hooks[hook_type].sort(key=lambda r: r.priority.value)

        logger.debug(
            f"Registered hook: {hook_type.name} from {plugin_name} "
            f"with priority {priority.name}"
        )

        return registration

    def register_custom(
        self,
        hook_name: str,
        handler: HookHandler,
        priority: HookPriority = HookPriority.NORMAL,
        plugin_name: str = "anonymous"
    ) -> HookRegistration:
        """Register a custom named hook"""
        registration = HookRegistration(
            hook_type=HookType.CUSTOM,
            handler=handler,
            priority=priority,
            plugin_name=plugin_name,
            metadata={"custom_name": hook_name}
        )

        if hook_name not in self._custom_hooks:
            self._custom_hooks[hook_name] = []

        self._custom_hooks[hook_name].append(registration)
        self._custom_hooks[hook_name].sort(key=lambda r: r.priority.value)

        return registration

    def unregister(self, registration: HookRegistration) -> bool:
        """
        Unregister a hook handler.

        Args:
            registration: The registration to remove

        Returns:
            True if removed, False if not found
        """
        hooks = self._hooks.get(registration.hook_type, [])
        if registration in hooks:
            hooks.remove(registration)
            return True
        return False

    def unregister_plugin(self, plugin_name: str) -> int:
        """
        Unregister all hooks from a plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Number of hooks unregistered
        """
        count = 0
        for hooks in self._hooks.values():
            to_remove = [h for h in hooks if h.plugin_name == plugin_name]
            for h in to_remove:
                hooks.remove(h)
                count += 1

        for hooks in self._custom_hooks.values():
            to_remove = [h for h in hooks if h.plugin_name == plugin_name]
            for h in to_remove:
                hooks.remove(h)
                count += 1

        return count

    def execute(
        self,
        hook_type: HookType,
        context: HookContext,
        stop_on_cancel: bool = True
    ) -> List[HookResult]:
        """
        Execute all handlers for a hook type.

        Args:
            hook_type: The hook type to execute
            context: Context to pass to handlers
            stop_on_cancel: Stop execution if context is cancelled

        Returns:
            List of results from all handlers
        """
        results = []
        hooks = self._hooks.get(hook_type, [])

        for registration in hooks:
            if not registration.enabled:
                continue

            try:
                result = registration.handler(context)
                results.append(result)

                # Update context data if modified
                if result.modified_data:
                    context.data.update(result.modified_data)

                # Stop if cancelled
                if stop_on_cancel and context.is_cancelled:
                    logger.debug(
                        f"Hook execution cancelled by {registration.plugin_name}"
                    )
                    break

            except Exception as e:
                logger.error(
                    f"Hook handler error ({registration.plugin_name}): {e}",
                    exc_info=True
                )
                results.append(HookResult(
                    success=False,
                    error=str(e)
                ))

        return results

    def execute_custom(
        self,
        hook_name: str,
        context: HookContext,
        stop_on_cancel: bool = True
    ) -> List[HookResult]:
        """Execute all handlers for a custom hook"""
        results = []
        hooks = self._custom_hooks.get(hook_name, [])

        for registration in hooks:
            if not registration.enabled:
                continue

            try:
                result = registration.handler(context)
                results.append(result)

                if result.modified_data:
                    context.data.update(result.modified_data)

                if stop_on_cancel and context.is_cancelled:
                    break

            except Exception as e:
                logger.error(f"Custom hook handler error: {e}", exc_info=True)
                results.append(HookResult(success=False, error=str(e)))

        return results

    def get_hooks(self, hook_type: HookType) -> List[HookRegistration]:
        """Get all registrations for a hook type"""
        return self._hooks.get(hook_type, []).copy()


class PluginLoader:
    """
    Discovers and loads plugins from configured directories.

    Plugins can be:
    - Python modules in a plugins directory
    - Packages with a plugin.py entry point
    - Dynamically registered plugin classes
    """

    def __init__(
        self,
        plugin_dirs: Optional[List[Path]] = None,
        auto_discover: bool = True
    ):
        """
        Initialize plugin loader.

        Args:
            plugin_dirs: Directories to search for plugins
            auto_discover: Automatically discover plugins on init
        """
        self._plugin_dirs = plugin_dirs or []
        self._plugins: Dict[str, Plugin] = {}
        self._load_order: List[str] = []

        if auto_discover and self._plugin_dirs:
            self.discover()

    def add_plugin_dir(self, path: Path) -> None:
        """Add a directory to search for plugins"""
        if path not in self._plugin_dirs:
            self._plugin_dirs.append(path)

    def discover(self) -> List[str]:
        """
        Discover plugins in configured directories.

        Returns:
            List of discovered plugin names
        """
        discovered = []

        for plugin_dir in self._plugin_dirs:
            if not plugin_dir.exists():
                continue

            for path in plugin_dir.iterdir():
                if path.is_file() and path.suffix == '.py' and not path.name.startswith('_'):
                    name = path.stem
                    if name not in self._plugins:
                        discovered.append(name)

                elif path.is_dir() and (path / 'plugin.py').exists():
                    name = path.name
                    if name not in self._plugins:
                        discovered.append(name)

        logger.info(f"Discovered {len(discovered)} plugins: {discovered}")
        return discovered

    def load(self, plugin_name: str) -> Optional[Plugin]:
        """
        Load a plugin by name.

        Args:
            plugin_name: Name of the plugin to load

        Returns:
            Loaded plugin instance or None if failed
        """
        if plugin_name in self._plugins:
            return self._plugins[plugin_name]

        for plugin_dir in self._plugin_dirs:
            # Try as module
            module_path = plugin_dir / f"{plugin_name}.py"
            if module_path.exists():
                return self._load_module(plugin_name, module_path)

            # Try as package
            package_path = plugin_dir / plugin_name / "plugin.py"
            if package_path.exists():
                return self._load_module(plugin_name, package_path)

        logger.warning(f"Plugin not found: {plugin_name}")
        return None

    def _load_module(self, name: str, path: Path) -> Optional[Plugin]:
        """Load a plugin from a file path"""
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                logger.error(f"Failed to create spec for {path}")
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find Plugin subclass in module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, Plugin) and
                    attr is not Plugin):
                    plugin = attr()
                    self._plugins[name] = plugin
                    self._load_order.append(name)
                    plugin.on_load()
                    logger.info(f"Loaded plugin: {name} v{plugin.version}")
                    return plugin

            logger.warning(f"No Plugin class found in {path}")
            return None

        except Exception as e:
            logger.error(f"Failed to load plugin {name}: {e}", exc_info=True)
            return None

    def register(self, plugin: Plugin) -> bool:
        """
        Register a plugin instance directly.

        Args:
            plugin: Plugin instance to register

        Returns:
            True if registered successfully
        """
        if plugin.name in self._plugins:
            logger.warning(f"Plugin already registered: {plugin.name}")
            return False

        self._plugins[plugin.name] = plugin
        self._load_order.append(plugin.name)
        plugin.on_load()
        logger.info(f"Registered plugin: {plugin.name} v{plugin.version}")
        return True

    def unload(self, plugin_name: str) -> bool:
        """
        Unload a plugin.

        Args:
            plugin_name: Name of the plugin to unload

        Returns:
            True if unloaded successfully
        """
        if plugin_name not in self._plugins:
            return False

        plugin = self._plugins[plugin_name]
        plugin.on_unload()
        del self._plugins[plugin_name]
        self._load_order.remove(plugin_name)

        logger.info(f"Unloaded plugin: {plugin_name}")
        return True

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a loaded plugin by name"""
        return self._plugins.get(name)

    def get_all_plugins(self) -> List[Plugin]:
        """Get all loaded plugins in load order"""
        return [self._plugins[name] for name in self._load_order]


class ExtensionManager:
    """
    Central manager for the extension system.

    Coordinates plugin loading, hook registration, and extension points.
    """

    def __init__(
        self,
        plugin_dirs: Optional[List[Path]] = None
    ):
        """
        Initialize extension manager.

        Args:
            plugin_dirs: Directories to search for plugins
        """
        self._hook_registry = HookRegistry()
        self._plugin_loader = PluginLoader(plugin_dirs, auto_discover=False)
        self._extension_points: Dict[str, ExtensionPoint] = {}
        self._initialized = False

    @property
    def hooks(self) -> HookRegistry:
        """Access the hook registry"""
        return self._hook_registry

    @property
    def plugins(self) -> PluginLoader:
        """Access the plugin loader"""
        return self._plugin_loader

    def initialize(self) -> None:
        """Initialize the extension system"""
        if self._initialized:
            return

        # Discover and load plugins
        discovered = self._plugin_loader.discover()
        for name in discovered:
            plugin = self._plugin_loader.load(name)
            if plugin:
                # Check dependencies
                for dep in plugin.dependencies:
                    if not self._plugin_loader.get_plugin(dep):
                        if not self._plugin_loader.load(dep):
                            logger.warning(
                                f"Missing dependency {dep} for plugin {name}"
                            )

                # Register plugin hooks
                plugin.register_hooks(self._hook_registry)

        self._initialized = True
        logger.info(f"Extension system initialized with {len(discovered)} plugins")

    def register_extension_point(self, point: ExtensionPoint) -> None:
        """Register an extension point"""
        self._extension_points[point.name] = point

    def get_extension_point(self, name: str) -> Optional[ExtensionPoint]:
        """Get an extension point by name"""
        return self._extension_points.get(name)

    def emit(
        self,
        hook_type: HookType,
        data: Optional[Dict[str, Any]] = None,
        source: str = "system",
        cancellable: bool = True
    ) -> Tuple[HookContext, List[HookResult]]:
        """
        Emit a hook event.

        Args:
            hook_type: Type of hook to emit
            data: Data to pass to handlers
            source: Source of the event
            cancellable: Whether handlers can cancel the event

        Returns:
            Tuple of (context, results)
        """
        from .datetime_utils import utc_now

        context = HookContext(
            hook_type=hook_type,
            timestamp=utc_now(),
            data=data or {},
            source=source,
            cancellable=cancellable
        )

        results = self._hook_registry.execute(hook_type, context)
        return context, results

    def shutdown(self) -> None:
        """Shutdown the extension system"""
        # Unload plugins in reverse order
        for name in reversed(self._plugin_loader._load_order.copy()):
            self._plugin_loader.unload(name)

        self._initialized = False
        logger.info("Extension system shutdown complete")


# =============================================================================
# Built-in Extension Points
# =============================================================================

class EventProcessorExtension(ExtensionPoint[Callable]):
    """Extension point for custom event processors"""

    @property
    def name(self) -> str:
        return "event_processor"

    @property
    def description(self) -> str:
        return "Process events before they are logged"


class MetricsExtension(ExtensionPoint[Callable]):
    """Extension point for custom metrics"""

    @property
    def name(self) -> str:
        return "custom_metrics"

    @property
    def description(self) -> str:
        return "Add custom metrics to the dashboard"


class DashboardWidgetExtension(ExtensionPoint[dict]):
    """Extension point for dashboard widgets"""

    @property
    def name(self) -> str:
        return "dashboard_widget"

    @property
    def description(self) -> str:
        return "Add custom widgets to dashboards"


# =============================================================================
# Global Instance
# =============================================================================

_extension_manager: Optional[ExtensionManager] = None


def get_extension_manager(
    plugin_dirs: Optional[List[Path]] = None
) -> ExtensionManager:
    """Get or create the global extension manager"""
    global _extension_manager
    if _extension_manager is None:
        _extension_manager = ExtensionManager(plugin_dirs)
    return _extension_manager


def emit_hook(
    hook_type: HookType,
    data: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Tuple[HookContext, List[HookResult]]:
    """Convenience function to emit a hook"""
    return get_extension_manager().emit(hook_type, data, **kwargs)

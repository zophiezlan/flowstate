"""Extension registry - loads, sorts, dispatches hooks."""

import importlib
import logging
from typing import List

from .extension import Extension, TapEvent

logger = logging.getLogger(__name__)


class ExtensionRegistry:
    """Loads extensions by name, sorts by order, dispatches lifecycle hooks."""

    def __init__(self):
        self._extensions: List[Extension] = []

    def load(self, names: list) -> None:
        """Load extensions by name from the extensions/ package."""
        for name in names:
            ext = self._load_one(name)
            if ext:
                self._extensions.append(ext)
        self._extensions.sort(key=lambda e: e.order)
        loaded = [e.name for e in self._extensions]
        logger.info(
            "Extensions loaded (%d): %s", len(loaded), loaded
        )

    def _load_one(self, name: str):
        """Load a single extension by name.

        Convention: extensions/<name>/ must expose either:
          - an `extension` attribute (instance), or
          - a `create()` factory function
        """
        try:
            mod = importlib.import_module(f"extensions.{name}")
            if hasattr(mod, "extension"):
                return mod.extension
            elif hasattr(mod, "create"):
                return mod.create()
            logger.warning(
                "Extension '%s': no 'extension' attr or create()", name
            )
            return None
        except Exception as e:
            logger.error(
                "Failed to load extension '%s': %s",
                name,
                e,
                exc_info=True,
            )
            return None

    def startup(self, ctx: dict) -> None:
        """Call on_startup on all loaded extensions."""
        for ext in self._extensions:
            try:
                ext.on_startup(ctx)
                logger.info("  Extension started: %s", ext.name)
            except Exception as e:
                logger.error(
                    "Extension '%s' startup failed: %s",
                    ext.name,
                    e,
                    exc_info=True,
                )

    def shutdown(self) -> None:
        """Call on_shutdown on all extensions (reverse order)."""
        for ext in reversed(self._extensions):
            try:
                ext.on_shutdown()
            except Exception as e:
                logger.error(
                    "Extension '%s' shutdown failed: %s",
                    ext.name,
                    e,
                )

    def run_on_tap(self, event: TapEvent) -> None:
        """Dispatch on_tap to all extensions."""
        for ext in self._extensions:
            try:
                ext.on_tap(event)
            except Exception as e:
                logger.error(
                    "Extension '%s' on_tap failed: %s",
                    ext.name,
                    e,
                )

    def run_on_dashboard_stats(self, stats: dict) -> None:
        """Dispatch on_dashboard_stats to all extensions."""
        for ext in self._extensions:
            try:
                ext.on_dashboard_stats(stats)
            except Exception as e:
                logger.error(
                    "Extension '%s' on_dashboard_stats failed: %s",
                    ext.name,
                    e,
                )

    def run_on_api_routes(self, app, db, config) -> None:
        """Dispatch on_api_routes to all extensions."""
        for ext in self._extensions:
            try:
                ext.on_api_routes(app, db, config)
            except Exception as e:
                logger.error(
                    "Extension '%s' on_api_routes failed: %s",
                    ext.name,
                    e,
                )

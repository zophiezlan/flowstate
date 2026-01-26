"""
Failover Manager - Automatic role switching when peer station fails

Enables a single station to handle multiple stages when peer is unavailable.
Provides seamless failover with automatic recovery.
"""

import logging
from typing import List, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class FailoverManager:
    """
    Manages automatic failover to dual-stage mode

    When peer station fails:
    - Automatically switches to handling multiple stages
    - Uses different beep patterns for each stage
    - Updates dashboard to show failover mode
    - Automatically returns to normal when peer recovers
    """

    def __init__(
        self,
        primary_stage: str,
        fallback_stages: List[str],
        on_failover_enable: Optional[Callable] = None,
        on_failover_disable: Optional[Callable] = None
    ):
        """
        Initialize failover manager

        Args:
            primary_stage: This station's primary stage
            fallback_stages: Stages to handle during failover
            on_failover_enable: Callback when entering failover mode
            on_failover_disable: Callback when exiting failover mode
        """
        self.primary_stage = primary_stage
        self.fallback_stages = fallback_stages
        self.on_failover_enable = on_failover_enable
        self.on_failover_disable = on_failover_disable

        # State
        self.failover_active = False
        self.failover_start_time: Optional[datetime] = None
        self.tap_counts = {stage: 0 for stage in [primary_stage] + fallback_stages}

    @property
    def active_stages(self) -> List[str]:
        """Get list of currently active stages"""
        if self.failover_active:
            return [self.primary_stage] + self.fallback_stages
        else:
            return [self.primary_stage]

    def enable_failover(self) -> bool:
        """
        Enable failover mode (dual-stage operation)

        Returns:
            True if failover enabled successfully
        """
        if self.failover_active:
            logger.warning("Failover mode already active")
            return False

        logger.warning("🔄 ENTERING FAILOVER MODE")
        logger.warning(f"This station will now handle: {self.active_stages}")

        self.failover_active = True
        self.failover_start_time = datetime.now()

        # Trigger callback
        if self.on_failover_enable:
            try:
                self.on_failover_enable()
            except Exception as e:
                logger.error(f"Error in failover enable callback: {e}")

        return True

    def disable_failover(self) -> bool:
        """
        Disable failover mode (return to normal)

        Returns:
            True if failover disabled successfully
        """
        if not self.failover_active:
            return False

        duration = datetime.now() - self.failover_start_time if self.failover_start_time else None
        logger.info("✅ EXITING FAILOVER MODE - Peer station recovered")

        if duration:
            logger.info(f"Failover mode was active for {duration}")

        self.failover_active = False
        self.failover_start_time = None

        # Trigger callback
        if self.on_failover_disable:
            try:
                self.on_failover_disable()
            except Exception as e:
                logger.error(f"Error in failover disable callback: {e}")

        return True

    def record_tap(self, stage: str):
        """
        Record a tap for a specific stage

        Args:
            stage: Stage that was tapped
        """
        if stage in self.tap_counts:
            self.tap_counts[stage] += 1
            logger.debug(f"Tap recorded for {stage}: {self.tap_counts[stage]} total")

    def get_status(self) -> dict:
        """
        Get current failover status

        Returns:
            Status dictionary
        """
        return {
            'failover_active': self.failover_active,
            'primary_stage': self.primary_stage,
            'active_stages': self.active_stages,
            'fallback_stages': self.fallback_stages,
            'failover_start_time': self.failover_start_time.isoformat() if self.failover_start_time else None,
            'tap_counts': self.tap_counts
        }

    def get_stage_for_tap_number(self, tap_number: int) -> str:
        """
        Determine which stage to use based on tap number

        In failover mode:
        - First tap of sequence: primary stage
        - Second tap of sequence: fallback stage
        - Pattern repeats

        Args:
            tap_number: Sequential tap number for this participant

        Returns:
            Stage name to use
        """
        if not self.failover_active:
            return self.primary_stage

        # In failover mode with 2 stages
        if len(self.fallback_stages) == 1:
            # Simple alternation: odd = primary, even = fallback
            if tap_number % 2 == 1:
                return self.primary_stage
            else:
                return self.fallback_stages[0]

        # Multiple fallback stages: cycle through them
        stage_index = (tap_number - 1) % (len(self.active_stages))
        return self.active_stages[stage_index]

    def should_use_alternate_beep(self, stage: str) -> bool:
        """
        Check if alternate beep pattern should be used

        Args:
            stage: Stage being processed

        Returns:
            True if alternate beep should be used
        """
        # Use alternate beep for fallback stages in failover mode
        return self.failover_active and stage in self.fallback_stages

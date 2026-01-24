#!/usr/bin/env python3
"""
Demo Data Generator for NSW Health Presentation
Simulates realistic festival drug checking activity
"""

import random
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any


class DemoDataGenerator:
    """Generates realistic demo data for festival drug checking service"""

    def __init__(self, db, config: dict, service_config: dict):
        self.db = db
        self.config = config
        self.service_config = service_config
        self.session_id = config['station']['session_id']
        self.stages = [s['id'] for s in service_config['workflow']['stages']]

        # Track active participants in various stages
        self.active_participants: Dict[str, Dict[str, Any]] = {}
        self.next_token_id = 1

        # Get scenario data
        self.scenario = config.get('scenario', {})

        # Simulation parameters based on scenario
        throughput = self.scenario.get('throughput_per_hour', 12)
        self.base_arrival_rate_per_minute = throughput / 60  # Convert to per-minute

        # Service times from scenario
        self.peer_intake_min = self.scenario.get('peer_intake_min', 5)
        self.testing_min = self.scenario.get('testing_min', 8)
        self.results_chat_min = self.scenario.get('results_chat_min', 10)
        self.results_variance = self.scenario.get('results_chat_variance', 'medium')

        # Abandonment rate from scenario
        self.abandon_rate = self.scenario.get('abandonment_rate', 0.02)

        # Get arrival pattern from scenario
        self.arrival_pattern = self.scenario.get('arrival_pattern', {})

        # Station IDs for realism
        self.stations = {
            'QUEUE_JOIN': 'entry-station-1',
            'SERVICE_START': 'testing-station-1',
            'SUBSTANCE_RETURNED': 'testing-station-1',
            'EXIT': 'exit-station-1'
        }

    def _generate_token_id(self) -> str:
        """Generate next token ID"""
        token = f"{self.next_token_id:03d}"
        self.next_token_id += 1
        return token

    def _generate_uid(self) -> str:
        """Generate realistic NFC UID"""
        return ''.join([f"{random.randint(0, 255):02x}" for _ in range(7)])

    def seed_initial_data(self, num_participants: int = 10):
        """Create initial participants in various stages"""
        print(f"🌱 Seeding {num_participants} initial participants...")

        for i in range(num_participants):
            token_id = self._generate_token_id()
            uid = self._generate_uid()

            # Distribute across stages
            stage_progress = random.random()

            if stage_progress < 0.4:
                # 40% in queue only
                self._add_participant(token_id, uid, 'QUEUE_JOIN')
            elif stage_progress < 0.6:
                # 20% being tested
                self._add_participant(token_id, uid, 'QUEUE_JOIN')
                time.sleep(0.01)
                self._progress_participant(token_id, uid, 'SERVICE_START')
            elif stage_progress < 0.8:
                # 20% at results/return stage
                self._add_participant(token_id, uid, 'QUEUE_JOIN')
                time.sleep(0.01)
                self._progress_participant(token_id, uid, 'SERVICE_START')
                time.sleep(0.01)
                self._progress_participant(token_id, uid, 'SUBSTANCE_RETURNED')
            else:
                # 20% completed (for historical data)
                self._add_participant(token_id, uid, 'QUEUE_JOIN')
                time.sleep(0.01)
                self._progress_participant(token_id, uid, 'SERVICE_START')
                time.sleep(0.01)
                self._progress_participant(token_id, uid, 'SUBSTANCE_RETURNED')
                time.sleep(0.01)
                self._complete_participant(token_id, uid)

        print(f"✅ Seeded {num_participants} participants")

    def get_arrival_multiplier(self):
        """
        Get arrival rate multiplier based on festival hour pattern from scenario
        """
        import time
        if not hasattr(self, 'start_time'):
            self.start_time = time.time()

        elapsed_minutes = (time.time() - self.start_time) / 60
        duration_hours = self.scenario.get('duration_hours', 6)
        hour = (elapsed_minutes / 60) % duration_hours  # Loop through festival cycle

        # Use scenario-specific arrival pattern
        if not self.arrival_pattern:
            return 1.0  # Default if no pattern specified

        # Map hour to pattern key
        if hour < 1:
            return self.arrival_pattern.get('hour_0_1', 1.0)
        elif hour < 2:
            return self.arrival_pattern.get('hour_1_2', 1.0)
        elif hour < 3:
            return self.arrival_pattern.get('hour_2_3', 1.0)
        elif hour < 4:
            return self.arrival_pattern.get('hour_3_4', 1.0)
        elif hour < 5:
            return self.arrival_pattern.get('hour_4_5', 1.0)
        else:
            return self.arrival_pattern.get('hour_5_6', 1.0)

    def simulate_activity_cycle(self):
        """Simulate one cycle of activity"""
        # New arrivals with realistic time-based variation
        multiplier = self.get_arrival_multiplier()
        arrival_probability = (self.base_arrival_rate_per_minute * multiplier) / 12  # ~5 sec intervals

        if random.random() < arrival_probability:
            self._new_arrival()

        # Progress existing participants
        self._progress_random_participants()

        # Abandonments based on scenario-specific rate and queue length
        # Lost Paradise actual: 0.25 abandonment rate with long queues = many people leave
        # HTID/Ideal: 0.02-0.03 abandonment rate with short queues = few leave
        # Probability scales with both abandonment rate and current queue length
        queue_length = len([p for p in self.active_participants.values()
                           if p['current_stage'] == 'QUEUE_JOIN' and not p.get('completed', False)])

        if queue_length > 0:
            # Per-cycle abandonment probability = base_rate * (queue_length / 50)
            # This means longer queues lead to more abandonments
            abandon_probability = self.abandon_rate * (queue_length / 50)
            if random.random() < abandon_probability:
                self._abandon_random_participant()

    def _new_arrival(self):
        """Add a new participant to the queue"""
        token_id = self._generate_token_id()
        uid = self._generate_uid()
        self._add_participant(token_id, uid, 'QUEUE_JOIN')
        print(f"👋 New arrival: {token_id}")

    def _add_participant(self, token_id: str, uid: str, stage: str):
        """Add participant to database and tracking"""
        device_id = self.stations.get(stage, 'demo-station')

        self.db.log_event(
            token_id=token_id,
            uid=uid,
            stage=stage,
            device_id=device_id,
            session_id=self.session_id
        )

        self.active_participants[token_id] = {
            'uid': uid,
            'current_stage': stage,
            'stage_start_time': datetime.now(),
            'completed': False
        }

    def _progress_participant(self, token_id: str, uid: str, next_stage: str):
        """Progress participant to next stage"""
        device_id = self.stations.get(next_stage, 'demo-station')

        self.db.log_event(
            token_id=token_id,
            uid=uid,
            stage=next_stage,
            device_id=device_id,
            session_id=self.session_id
        )

        if token_id in self.active_participants:
            self.active_participants[token_id]['current_stage'] = next_stage
            self.active_participants[token_id]['stage_start_time'] = datetime.now()

    def _complete_participant(self, token_id: str, uid: str):
        """Complete participant journey"""
        self._progress_participant(token_id, uid, 'EXIT')
        if token_id in self.active_participants:
            self.active_participants[token_id]['completed'] = True
            # Remove after a delay to keep some history
            # (In real code, we'd do this cleanup periodically)

    def _progress_random_participants(self):
        """Randomly progress some participants through stages"""
        active = [
            (tid, p) for tid, p in self.active_participants.items()
            if not p['completed']
        ]

        if not active:
            return

        for token_id, participant in active:
            current_stage = participant['current_stage']
            time_in_stage = (datetime.now() - participant['stage_start_time']).total_seconds() / 60

            # Different progression probabilities based on stage and time
            should_progress = False

            if current_stage == 'QUEUE_JOIN':
                # Queue wait: depends on queue length and staff availability
                # With 6 peer workers, minimal wait when queue < 6
                # For demo: 1-3 minutes average progression
                if time_in_stage > 0.5 and random.random() < 0.2:
                    should_progress = True
            elif current_stage == 'SERVICE_START':
                # Intake + Testing time from scenario
                # peer_intake_min + testing_min = total SERVICE_START duration
                total_service_time = self.peer_intake_min + self.testing_min
                min_time = total_service_time * 0.4  # Start checking after 40% of time
                avg_time = total_service_time * 0.6  # Average completion at 60%

                if time_in_stage > min_time and random.random() < (0.12 if time_in_stage > avg_time else 0.08):
                    should_progress = True
            elif current_stage == 'SUBSTANCE_RETURNED':
                # Results chat: variance depends on scenario
                # Lost Paradise actual: low variance (rushed due to queue)
                # HTID/Lost Paradise ideal: medium-high variance (quality conversations)
                variance = random.random()

                if self.results_variance == 'low':
                    # Low variance - rushed service (overwhelmed)
                    if time_in_stage > 1.5 and random.random() < 0.25:
                        should_progress = True
                elif self.results_variance == 'medium':
                    # Medium variance - mix of quick and normal chats
                    if variance < 0.3:  # 30% quick chat
                        if time_in_stage > 1.5 and random.random() < 0.3:
                            should_progress = True
                    elif variance < 0.8:  # 50% normal chat
                        if time_in_stage > 2.5 and random.random() < 0.15:
                            should_progress = True
                    else:  # 20% long conversation
                        if time_in_stage > 5 and random.random() < 0.08:
                            should_progress = True
                else:  # high variance
                    # Very high variance - some VERY long conversations
                    if variance < 0.2:  # 20% quick
                        if time_in_stage > 1 and random.random() < 0.3:
                            should_progress = True
                    elif variance < 0.7:  # 50% normal
                        if time_in_stage > 2.5 and random.random() < 0.12:
                            should_progress = True
                    else:  # 30% very long (quality harm reduction!)
                        if time_in_stage > 7 and random.random() < 0.06:
                            should_progress = True

            if should_progress:
                next_stage = self._get_next_stage(current_stage)
                if next_stage:
                    print(f"➡️  {token_id}: {current_stage} → {next_stage}")

                    if next_stage == 'EXIT':
                        self._complete_participant(token_id, participant['uid'])
                    else:
                        self._progress_participant(token_id, participant['uid'], next_stage)

    def _get_next_stage(self, current_stage: str) -> str:
        """Get the next stage in the workflow"""
        try:
            current_idx = self.stages.index(current_stage)
            if current_idx < len(self.stages) - 1:
                return self.stages[current_idx + 1]
        except (ValueError, IndexError):
            pass
        return None

    def _abandon_random_participant(self):
        """Simulate a participant abandoning the queue"""
        in_queue = [
            (tid, p) for tid, p in self.active_participants.items()
            if p['current_stage'] == 'QUEUE_JOIN' and not p['completed']
        ]

        if in_queue:
            token_id, participant = random.choice(in_queue)
            print(f"👋 {token_id} left the queue")
            # Force exit
            self._complete_participant(token_id, participant['uid'])

    def get_stats(self) -> dict:
        """Get current simulation stats"""
        active = [p for p in self.active_participants.values() if not p['completed']]

        by_stage = {}
        for stage in self.stages:
            by_stage[stage] = len([p for p in active if p['current_stage'] == stage])

        return {
            'total_active': len(active),
            'by_stage': by_stage,
            'total_processed': self.next_token_id - 1
        }

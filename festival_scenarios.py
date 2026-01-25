"""
Festival scenario configurations based on real NSW deployments
Each scenario represents actual or projected festival drug checking operations

These demos are designed to be presented to NSW Health to demonstrate the system
and can be reset and reconfigured to understand how it works.

Real operational data from:
- HTID (Hardstyle Til I Die): Single day hardstyle festival
- Lost Paradise: Multi-day camping festival with extremely high demand
"""

FESTIVAL_SCENARIOS = {
    'htid': {
        'name': 'HTID (Hardstyle Til I Die)',
        'description': 'Single day hardstyle festival - Manageable demand, good baseline',
        'emoji': '🎵',
        'duration_hours': 6,
        'days': 1,
        'session_id': 'htid-2026-demo',

        # Staffing
        'peer_workers': 6,
        'chemists': 6,

        # Actual results from real deployment
        'total_samples': 110,
        'total_groups': 70,
        'samples_per_group_avg': 1.6,  # 50/50 split of 1 vs 2-3 substances per group
        'group_size_avg': 2.5,  # Most people come in groups of 2 or 3

        # Service times (realistic averages)
        'peer_intake_min': 5,       # Initial chat with peer
        'testing_min': 8,           # Chemist testing (7-10 min range, avg 8)
        'results_chat_min': 10,     # Results discussion (can be 5-30 min, avg 10)
        'results_chat_variance': 'high',  # Some conversations go 30+ mins

        # Demand pattern - reflects reality: quiet start, builds, peaks mid-service, tapers
        'demand_level': 'moderate',
        'arrival_pattern': {
            'hour_0_1': 0.2,   # Very quiet - people still finding the service
            'hour_1_2': 0.8,   # Starting to build as word spreads
            'hour_2_3': 2.0,   # Peak demand - queue builds to ~15 groups
            'hour_3_4': 1.8,   # Peak continues
            'hour_4_5': 0.8,   # Dropping off - small queue
            'hour_5_6': 0.3,   # Hardly anyone - end of service
        },

        # Queue dynamics - realistic for manageable service
        'max_queue_observed': 15,   # Maximum queue around hour 3
        'avg_wait_time_min': 10,    # Most people through fairly quickly
        'max_wait_time_min': 25,    # At peak, some wait up to 25 min
        'abandonment_rate': 0.02,   # Very few people leave - service is accessible

        # Capacity
        'throughput_per_hour': 12,  # ~70 groups / 6 hours = 11.7/hr
        'service_time_total_min': 23,  # 5 + 8 + 10 = 23 min typical journey

        # Outcomes
        'outcome': 'success',
        'outcome_description': 'Service met demand. First hour quiet (straight through to peer), peak queue of ~15 groups at hour 3, dropped to small queue, quiet finish. Good participant experience.',
        'lesson': 'Baseline: 6/6 staffing works well for moderate single-day festival (~70 groups, ~110 samples)',

        # Alert thresholds
        'queue_warning': 10,
        'queue_critical': 15,
        'wait_warning_min': 20,
        'wait_critical_min': 45,
        'stuck_threshold_min': 40,
    },

    'lost_paradise_actual': {
        'name': 'Lost Paradise (Actual - Understaffed)',
        'description': '2-day festival - OVERWHELMED, 3hr waits, many turned away. Same 6/6 staff as HTID but 4x demand.',
        'emoji': '🌴',
        'duration_hours': 6,
        'days': 2,
        'session_id': 'lost-paradise-actual-2026-demo',

        # Staffing - CRITICALLY UNDERSTAFFED for demand
        # Same as HTID but facing 4x the participants
        'peer_workers': 6,
        'chemists': 6,

        # Actual results from real deployment
        'total_samples': 300,  # Nearly 300 samples tested over 2 days
        'total_groups': 150,   # Capped at 2 samples per group, group size of 2
        'samples_per_group_avg': 1.8,  # 80/20 split: 80% brought 2 samples, 20% brought 1
        'group_size_avg': 2.0,  # Capped at 2 people per group to manage demand

        # Service times - RUSHED due to extreme queue pressure
        'peer_intake_min': 5,
        'testing_min': 8,
        'results_chat_min': 7,  # Shorter than ideal - pressure to move people through
        'results_chat_variance': 'low',  # No time for long conversations when 50+ people waiting

        # Demand pattern - CONSTANT OVERLOAD from start to finish
        'demand_level': 'critical_overload',
        'arrival_pattern': {
            # LINE OUT THE DOOR BEFORE OPENING and stayed full entire service
            'hour_0_1': 4.0,   # Already a queue before doors opened
            'hour_1_2': 4.0,   # Constant - people kept arriving
            'hour_2_3': 4.0,   # Constant - no let up
            'hour_3_4': 4.0,   # Constant - still full
            'hour_4_5': 3.5,   # Slight drop as people give up / word spreads about wait
            'hour_5_6': 3.0,   # Still busy but some reduce as service ending
        },

        # Queue dynamics - CRISIS CONDITIONS
        'max_queue_observed': 60,  # Line out the door, estimate 50-60+ groups
        'avg_wait_time_min': 120,  # 2 hour average wait
        'max_wait_time_min': 180,  # 3 hours at peak - "absolute troopers" who waited
        'abandonment_rate': 0.30,  # Many people left because we couldn't handle demand

        # Capacity - SAME throughput as HTID but nowhere near enough
        'throughput_per_hour': 12,  # Can only process ~12 groups/hr with 6/6 staff
        'service_time_total_min': 20,  # Rushed: 5 + 8 + 7 = 20 min

        # Outcomes - this is the problem we need to solve
        'outcome': 'critical_understaffed',
        'outcome_description': 'Severe understaffing for demand. Line out the door before opening, stayed steady full entire service. 3hr waits at peak. Many people left because we couldn\'t handle demand. Staff under extreme pressure. This is what happens when demand exceeds capacity.',
        'lesson': 'PROBLEM: 6/6 staffing is catastrophically insufficient for high-demand multi-day festivals. Need to scale resources to match demand.',

        # Alert thresholds - adjusted for crisis visibility
        'queue_warning': 20,
        'queue_critical': 40,
        'wait_warning_min': 60,
        'wait_critical_min': 120,
        'stuck_threshold_min': 45,
    },

    'lost_paradise_ideal': {
        'name': 'Lost Paradise (Full Service - 12/12)',
        'description': '2-day festival - PROPER resourcing with 12/12 staff. Manageable queues, quality service, no one turned away.',
        'emoji': '🌟',
        'duration_hours': 6,
        'days': 2,
        'session_id': 'lost-paradise-ideal-2026-demo',

        # Staffing - DOUBLED to meet demand
        'peer_workers': 12,
        'chemists': 12,

        # Projected results - can handle the actual demand properly
        'total_samples': 500,  # Could test ~500 samples with double staff
        'total_groups': 280,   # ~280 groups (more than actual 150 due to fewer abandonments)
        'samples_per_group_avg': 1.8,  # Same mix as actual (80/20 split)
        'group_size_avg': 2.0,  # Same group dynamics

        # Service times - QUALITY service, no rushing
        'peer_intake_min': 5,       # Proper initial chat
        'testing_min': 8,           # Full testing time
        'results_chat_min': 10,     # Can have proper harm reduction conversations
        'results_chat_variance': 'medium',  # Time for quality conversations when needed

        # Demand pattern - SAME demand as actual, but we can handle it
        'demand_level': 'high_manageable',
        'arrival_pattern': {
            # Same high demand - but now manageable with proper staffing
            'hour_0_1': 4.0,   # Queue before opening - but we clear it
            'hour_1_2': 4.0,   # Constant demand
            'hour_2_3': 4.0,   # Constant demand
            'hour_3_4': 4.0,   # Constant demand
            'hour_4_5': 3.5,   # Still high
            'hour_5_6': 3.0,   # Steady to end
        },

        # Queue dynamics - MANAGEABLE with proper resourcing
        'max_queue_observed': 20,   # Much more manageable peak
        'avg_wait_time_min': 20,    # Reasonable average wait
        'max_wait_time_min': 40,    # Peak wait under 45 min
        'abandonment_rate': 0.05,   # Minimal - only people in a real hurry

        # Capacity - DOUBLED throughput
        'throughput_per_hour': 24,  # ~24 groups/hr with 12/12 staff
        'service_time_total_min': 23,  # Proper quality service: 5 + 8 + 10

        # Outcomes - this is the SOLUTION
        'outcome': 'success_scaled',
        'outcome_description': 'Proper 12/12 resourcing meets demand. Queue manageable throughout. Wait times under 40 min. Quality harm reduction conversations possible. Minimal abandonments. This is what adequate resourcing looks like.',
        'lesson': 'SOLUTION: 12/12 staffing handles high-demand multi-day festivals. Demonstrates ROI of proper investment in harm reduction capacity.',

        # Alert thresholds - reasonable for well-resourced service
        'queue_warning': 15,
        'queue_critical': 25,
        'wait_warning_min': 25,
        'wait_critical_min': 45,
        'stuck_threshold_min': 40,
    },
}


def get_scenario_config(scenario_name: str) -> dict:
    """Get configuration for a specific festival scenario"""
    if scenario_name not in FESTIVAL_SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario_name}. Available: {list(FESTIVAL_SCENARIOS.keys())}")

    return FESTIVAL_SCENARIOS[scenario_name]


def get_scenario_summary(scenario_name: str) -> dict:
    """Get summary info for display"""
    scenario = FESTIVAL_SCENARIOS[scenario_name]

    return {
        'name': scenario['name'],
        'description': scenario['description'],
        'emoji': scenario['emoji'],
        'staff': f"{scenario['peer_workers']} peers, {scenario['chemists']} chemists",
        'duration': f"{scenario['days']} day{'s' if scenario['days'] > 1 else ''}, {scenario['duration_hours']}hr/day",
        'served': f"{scenario['total_groups']} groups, {scenario['total_samples']} samples",
        'outcome': scenario['outcome_description'],
        'max_wait': f"{scenario['max_wait_time_min']} min",
        'abandonment': f"{int(scenario['abandonment_rate'] * 100)}%"
    }


def list_scenarios() -> list:
    """List all available scenarios"""
    return [
        {
            'id': key,
            'name': scenario['name'],
            'emoji': scenario['emoji'],
            'description': scenario['description'],
            'outcome': scenario['outcome']
        }
        for key, scenario in FESTIVAL_SCENARIOS.items()
    ]

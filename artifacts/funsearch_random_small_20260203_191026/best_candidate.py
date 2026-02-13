"""Best candidate from run: funsearch_random_small_20260203_191026

Generated at: 2026-02-03T11:15:53.682143+00:00
Score: 0.0
Generation: 0
Model: main_provider
"""

import math

def score_bin(item_size, remaining_capacity, bin_index, step) -> float:
    # Base score from capacity utilization after placing the item
    capacity_after = remaining_capacity - item_size
    
    # Perfect fit gets a very high score
    if capacity_after == 0:
        return 1000.0 - bin_index * 0.001
    
    # If item doesn't fit, return negative infinity
    if capacity_after < 0:
        return -float('inf')
    
    # Normalized remaining capacity after placement (0 to 1)
    # We assume total capacity is 1.0 (standard bin packing)
    normalized_remaining = capacity_after
    
    # Utilization score: higher for tighter packing
    utilization = 1.0 - normalized_remaining
    
    # Flexibility score: some remaining space is good for future items
    # But very small leftover space is bad (waste)
    if normalized_remaining < 0.1:
        flexibility = normalized_remaining * 5.0  # Penalize tiny leftovers
    else:
        flexibility = math.sqrt(normalized_remaining)  # Reward reasonable space
    
    # Combine utilization and flexibility with weights
    # Weight shifts slightly with step to become slightly more aggressive over time
    w = 0.7 + 0.1 * (step / (step + 100))
    combined = w * utilization + (1 - w) * flexibility
    
    # Add tiny tie-breaking based on bin_index (prefer older bins)
    return combined - bin_index * 1e-6
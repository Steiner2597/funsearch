"""Best candidate from run: funsearch_random_small_20260202_024429

Generated at: 2026-02-01T19:10:10.523505+00:00
Score: 0.0
Generation: 0
Model: main_provider
"""

import math

def score_bin(item_size, remaining_capacity, bin_index, step) -> float:
    # Base score from capacity utilization after placing the item
    used_after = 1.0 - (remaining_capacity - item_size)
    
    # Penalty for leaving very small leftover space (wasted sliver)
    leftover = remaining_capacity - item_size
    if leftover > 0:
        waste_penalty = 0.1 * math.exp(-10.0 * leftover)
    else:
        waste_penalty = 0.0
    
    # Bonus for creating a bin that is nearly perfectly packed
    tightness_bonus = 2.0 * math.exp(-15.0 * leftover) if leftover >= 0 else 0.0
    
    # Small preference for older bins (promote consolidation)
    age_factor = 0.01 * (step - bin_index) / (step + 1)
    
    # Flexibility penalty: leaving very medium leftover is bad for future items
    # Ideal leftover is either very small (near perfect) or fairly large (flexible)
    if leftover > 0:
        flexibility_score = -0.3 * math.exp(-5.0 * (leftover - 0.25)**2)
    else:
        flexibility_score = 0.0
    
    # Combine components
    score = used_after + tightness_bonus - waste_penalty + flexibility_score + age_factor
    
    # Ensure finite value even in edge cases
    return float(score)
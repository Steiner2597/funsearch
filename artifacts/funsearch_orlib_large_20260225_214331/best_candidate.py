"""Best candidate from run: funsearch_orlib_large_20260225_214331

Generated at: 2026-02-25T14:23:51.869668+00:00
Score: -221.175
Generation: 0
Model: main_provider
"""

import math

def score_bin(item_size, remaining_capacity, bin_index, step) -> float:
    # Base score: how well the item fits now
    fit_score = item_size / remaining_capacity if remaining_capacity > 0 else -1
    
    # Penalty for leaving very small leftover space (encourage tight fits)
    leftover = remaining_capacity - item_size
    if leftover < 0:
        return -float('inf')
    
    tightness_bonus = 0.0
    if leftover > 0:
        # Strong bonus for perfect or near-perfect fits
        tightness_bonus = 1.0 / (leftover + 1e-6)
    
    # Flexibility component: prefer bins with more remaining capacity
    # but only if leftover is reasonably large
    flexibility = 0.0
    if leftover >= item_size * 0.5:  # Enough space for another similar item
        flexibility = math.log(remaining_capacity + 1)
    
    # Combine components with weights
    score = fit_score * 2.0 + tightness_bonus * 0.5 + flexibility * 0.3
    
    # Slight tie-breaker: prefer older bins (lower index)
    score -= bin_index * 1e-9
    
    return score
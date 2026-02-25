"""Best candidate from run: funsearch_orlib_large_20260225_185132

Generated at: 2026-02-25T12:11:58.006460+00:00
Score: 0.0
Generation: 0
Model: main_provider
"""

import math

def score_bin(item_size, remaining_capacity, bin_index, step) -> float:
    # Base score: how well the item fits now
    fit_ratio = item_size / remaining_capacity if remaining_capacity > 0 else float('inf')
    
    # Tightness bonus: reward bins where the item fills nearly the remaining space
    tightness = 1.0 - (remaining_capacity - item_size) if remaining_capacity >= item_size else -float('inf')
    
    # Flexibility penalty: leaving very small leftover space is bad for future items
    leftover = remaining_capacity - item_size
    if leftover > 0:
        # Small leftovers are penalized more, but zero leftover is perfect
        flexibility_penalty = 0.1 / (leftover + 0.01)
    else:
        flexibility_penalty = 0.0
    
    # Age factor: slightly prefer older bins (lower index) to keep bin count stable
    age_factor = 1.0 / (1.0 + bin_index * 0.001)
    
    # Step decay: very slight preference for recent bins in early steps
    step_factor = 1.0 / (1.0 + step * 0.0001)
    
    # Combine components
    score = tightness - flexibility_penalty + age_factor + step_factor
    
    # If item doesn't fit, return negative infinity
    if item_size > remaining_capacity:
        return -float('inf')
    
    return score
"""Best candidate from run: funsearch_random_small_20260202_023043

Generated at: 2026-02-01T18:35:25.922124+00:00
Score: 0.0
Generation: 0
Model: main_provider
"""

import math

def score_bin(item_size, remaining_capacity, bin_index, step) -> float:
    # If the item doesn't fit, return negative infinity
    if item_size > remaining_capacity:
        return float('-inf')
    
    # Calculate the free space after placing the item
    free_after = remaining_capacity - item_size
    
    # Base score: prioritize bins where the item fits perfectly
    perfect_fit_bonus = 100.0 if free_after == 0 else 0.0
    
    # Tight packing incentive: higher score for less wasted space
    # Use a decaying exponential to strongly prefer small remaining space
    tightness = math.exp(-free_after * 2.0)
    
    # Flexibility preservation: slightly penalize leaving very small gaps
    # that are unlikely to be useful later
    small_gap_penalty = 0.0
    if 0 < free_after < 0.1:  # Very small gaps are inefficient
        small_gap_penalty = -0.5
    
    # Bin age factor: very slight preference for newer bins to spread load
    # Normalized by step to keep it small
    age_factor = (step - bin_index) / max(step, 1) * 0.01
    
    # Combine components
    score = perfect_fit_bonus + tightness + small_gap_penalty + age_factor
    
    # Add tiny deterministic tie-breaker based on bin_index
    score -= bin_index * 1e-10
    
    return score
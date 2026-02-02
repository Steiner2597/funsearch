"""Best candidate from run: funsearch_orlib_small_20260131_224403

Generated at: 2026-01-31T20:54:15.399584+00:00
Score: 54.85
Generation: 0
Model: main_provider
"""

import math

def score_bin(item_size, remaining_capacity, bin_index, step) -> float:
    # If the item doesn't fit, return negative infinity
    if item_size > remaining_capacity:
        return float('-inf')
    
    # Calculate the tightness after placing the item
    new_remaining = remaining_capacity - item_size
    tightness = 1.0 - (new_remaining / remaining_capacity)
    
    # Calculate a flexibility measure: how many potential future items could still fit
    # We favor bins that leave a capacity that could accommodate common small items
    if new_remaining > 0:
        # Flexibility: higher if remaining capacity is a "useful" size
        # Use a Gaussian-like weighting around a target useful size (e.g., 0.3 of bin capacity)
        target_flex = 0.3
        flex_score = math.exp(-((new_remaining - target_flex) ** 2) / 0.1)
    else:
        flex_score = 1.0  # Perfect fit is maximally flexible (no wasted space)
    
    # Combine tightness and flexibility with a balance factor
    balance = 0.6  # Weight towards tightness
    combined = balance * tightness + (1 - balance) * flex_score
    
    # Add a tiny tie-breaker based on bin index (earlier bins slightly preferred)
    tie_breaker = 1e-9 * (1.0 / (bin_index + 1))
    
    return combined + tie_breaker
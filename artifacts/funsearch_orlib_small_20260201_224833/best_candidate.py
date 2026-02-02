"""Best candidate from run: funsearch_orlib_small_20260201_224833

Generated at: 2026-02-01T17:18:47.401200+00:00
Score: -43.8
Generation: 8
Model: main_provider
"""

import math

def score_bin(item_size, remaining_capacity, bin_index, step) -> float:
    # Base score from capacity utilization after placing item
    used_capacity = 1.0 - remaining_capacity
    new_used = used_capacity + item_size
    utilization = new_used
    
    # Prefer bins where item fits exactly or leaves useful small space
    gap = remaining_capacity - item_size
    if gap < 0:
        return -float('inf')  # Doesn't fit
    
    # Perfect fit bonus (increased for larger items)
    perfect_fit_bonus = 15.0 * item_size if gap == 0 else 0.0
    
    # Small leftover space is good (encourages finishing bins)
    # But very tiny leftover is wasteful, medium leftover is flexible
    if gap > 0:
        gap_score = 1.0 / (1.0 + gap)  # Prefer smaller gaps
        # Dynamic useful gap bonus that adapts to item size
        # Target gap now depends on both item_size and current utilization
        target_gap = 0.1 * item_size + 0.02 * used_capacity + 0.03
        # Adaptive variance based on item size and step progression
        variance = 0.01 + 0.005 * item_size + 0.0001 * min(step, 500)
        useful_gap_bonus = math.exp(-((gap - target_gap) ** 2) / variance)
    else:
        gap_score = 0.0
        useful_gap_bonus = 0.0
    
    # Age factor with non-linear scaling
    age_factor = 1.0 + bin_index * 1e-6 * math.log(1 + bin_index)
    
    # Step-based decay that starts earlier but decays slower
    if step > 50:
        age_decay = max(0.7, 1.0 - (step - 50) * 3e-6)
        age_factor *= age_decay
    
    # Dynamic weights that adapt to both utilization and item size
    # Larger items get more weight on utilization, smaller on gap fitting
    util_weight = 6.0 - 3.0 * utilization + 2.0 * item_size
    gap_weight = 1.5 + 2.5 * utilization - 1.5 * item_size
    
    # Additional component: penalize very large gaps when utilization is already high
    gap_penalty = 0.0
    if utilization > 0.7 and gap > 0.3:
        gap_penalty = -2.0 * (gap - 0.3) * (utilization - 0.7)
    
    score = (
        util_weight * utilization +           # Primary: high utilization
        gap_weight * gap_score +              # Secondary: small gaps
        2.5 * useful_gap_bonus +              # Tertiary: useful dynamic gaps
        perfect_fit_bonus +                   # Large bonus for exact fit
        gap_penalty                           # Penalty for wasteful large gaps
    ) * age_factor
    
    return score
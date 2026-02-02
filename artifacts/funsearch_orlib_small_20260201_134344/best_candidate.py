"""Best candidate from run: funsearch_orlib_small_20260201_134344

Generated at: 2026-02-01T06:00:08.319955+00:00
Score: 137.5
Generation: 1
Model: main_provider
"""

def score_bin(item_size, remaining_capacity, bin_index, step) -> float:
    if item_size > remaining_capacity:
        return float('-inf')
    
    # Base tightness score: how well the item fits
    tightness = item_size / remaining_capacity
    
    # Flexibility penalty: avoid leaving very small gaps
    new_remaining = remaining_capacity - item_size
    if new_remaining > 0:
        # Modified penalty: stronger for medium gaps, weaker for tiny gaps
        if new_remaining < 0.1:
            flexibility_penalty = 0.05 / (new_remaining + 0.01)
        else:
            flexibility_penalty = 0.2 / (new_remaining + 0.01)
    else:
        flexibility_penalty = 0.0
    
    # Age bonus now decays slightly with step to balance early/late bins
    age_bonus = bin_index * 1e-6 / (1 + step * 1e-4)
    
    # Fill bonus: non-linear to strongly encourage nearly-full bins
    fill_bonus = 0.02 * (1.0 - remaining_capacity) ** 0.5
    
    # Add a small bonus for perfect fits
    perfect_fit_bonus = 2.0 if new_remaining == 0 else 0.0
    
    # Combine components
    score = tightness - flexibility_penalty + age_bonus + fill_bonus + perfect_fit_bonus
    
    return score
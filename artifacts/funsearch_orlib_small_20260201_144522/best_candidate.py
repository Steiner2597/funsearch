"""Best candidate from run: funsearch_orlib_small_20260201_144522

Generated at: 2026-02-01T07:13:10.911954+00:00
Score: 92.1125
Generation: 2
Model: main_provider
"""

def score_bin(item_size, remaining_capacity, bin_index, step) -> float:
    # Base score: how well the item fits
    fit_ratio = item_size / remaining_capacity if remaining_capacity > 0 else float('inf')
    
    # Tightness bonus: reward bins where the item fills a large portion of remaining space
    tightness = 1.0 - (remaining_capacity - item_size) / remaining_capacity if remaining_capacity > 0 else -float('inf')
    
    # Flexibility penalty: penalize bins that would leave very little space
    # Now uses a smoother, continuous penalty function
    leftover = remaining_capacity - item_size
    flexibility_penalty = 0.0
    if leftover > 0:
        # Sigmoid-shaped penalty that increases sharply for leftovers < 5%
        penalty_strength = 1.0 / (1.0 + pow(2.71828, 20.0 * (leftover - 0.03)))
        flexibility_penalty = 0.15 * penalty_strength
    
    # Age factor: preference for newer bins, but now decays with bin age
    age_factor = 0.0
    if step > 0:
        bin_age = step - bin_index
        # Exponential decay: newer bins get more preference
        age_factor = 0.002 * pow(0.9, bin_age)
    
    # Primary score: prioritize bins where item fits perfectly or leaves useful space
    if fit_ratio <= 1.0:
        # Main scoring with adjusted weights
        base_score = 1.5 * tightness - flexibility_penalty + age_factor
        
        # Bonus for exact fit (increased)
        if leftover == 0:
            base_score += 3.0
        
        # Bonus for leaving space that could fit common small items
        # Now with graduated bonus based on leftover size
        if 0.01 <= leftover <= 0.3:
            # Maximum bonus at leftover=0.1, decreasing on both sides
            ideal_leftover = 0.1
            bonus = 0.1 * max(0, 1.0 - abs(leftover - ideal_leftover) / 0.2)
            base_score += bonus
        
        # Additional penalty for very large leftovers (wasted space)
        if leftover > 0.5:
            base_score -= 0.3 * (leftover - 0.5)
        
        return base_score
    else:
        # Item doesn't fit - return large negative score
        return -float('inf')
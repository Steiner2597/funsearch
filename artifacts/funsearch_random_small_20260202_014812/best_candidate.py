"""Best candidate from run: funsearch_random_small_20260202_014812

Generated at: 2026-02-01T17:52:10.766734+00:00
Score: 0.0
Generation: 0
Model: main_provider
"""

def score_bin(item_size, remaining_capacity, bin_index, step) -> float:
    if item_size > remaining_capacity:
        return float('-inf')
    
    # Base tightness score: how well the item fits
    tightness = item_size / remaining_capacity
    
    # Flexibility component: favor bins with capacity that allows future typical items
    # Assume typical future items are medium-sized; balance between too tight and too loose
    capacity_after = remaining_capacity - item_size
    if capacity_after == 0:
        flexibility = 1.0  # Perfect fit
    else:
        # Ideal leftover capacity for future flexibility is around 0.3-0.5 of bin capacity
        # We approximate bin capacity as (item_size + remaining_capacity)
        bin_capacity_estimate = item_size + remaining_capacity
        ideal_leftover = 0.4 * bin_capacity_estimate
        flexibility = 1.0 / (1.0 + abs(capacity_after - ideal_leftover))
    
    # Combine with slight preference for older bins (lower index) to reduce fragmentation
    age_factor = 1.0 / (1.0 + 0.001 * bin_index)
    
    # Weighted combination: 70% tightness, 30% flexibility, scaled by age factor
    score = (0.7 * tightness + 0.3 * flexibility) * age_factor
    
    return score
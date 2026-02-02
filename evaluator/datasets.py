"""OR-Library and standard benchmark dataset loaders for bin packing.

OR-Library format (Falkenauer instances):
- Line 1: Number of test problems (P)
- For each problem:
    - Problem identifier
    - Bin capacity, Number of items (n), Best known solution
    - For each item: size of the item

References:
- OR-Library: http://people.brunel.ac.uk/~mastjjb/jeb/orlib/binpackinfo.html
- Falkenauer (1994): "A Hybrid Grouping Genetic Algorithm for Bin Packing"
"""

from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

# OR-Library download URLs
ORLIB_BASE_URL = "http://people.brunel.ac.uk/~mastjjb/jeb/orlib/files/"
ORLIB_FILES = [
    "binpack1.txt",  # Uniform u120 (20 instances)
    "binpack2.txt",  # Uniform u250 (20 instances)
    "binpack3.txt",  # Uniform u500 (20 instances)
    "binpack4.txt",  # Uniform u1000 (20 instances)
    "binpack5.txt",  # Triplet t60 (20 instances)
    "binpack6.txt",  # Triplet t120 (20 instances)
    "binpack7.txt",  # Triplet t249 (20 instances)
    "binpack8.txt",  # Triplet t501 (20 instances)
]

# Default cache directory
DEFAULT_CACHE_DIR = Path(__file__).parent.parent / "data" / "orlib"


@dataclass
class BinPackingInstance:
    """A single bin packing problem instance."""
    
    name: str                    # Problem identifier (e.g., "u120_00")
    capacity: int                # Bin capacity
    items: list[int]             # Item sizes
    best_known: int              # Best known number of bins
    optimal: bool = False        # Whether best_known is proven optimal
    
    @property
    def num_items(self) -> int:
        return len(self.items)
    
    @property
    def total_size(self) -> int:
        return sum(self.items)
    
    @property
    def lower_bound(self) -> int:
        """L1 lower bound: ceil(sum of items / capacity)."""
        return (self.total_size + self.capacity - 1) // self.capacity
    
    def __repr__(self) -> str:
        return (
            f"BinPackingInstance(name='{self.name}', "
            f"capacity={self.capacity}, items={self.num_items}, "
            f"best_known={self.best_known})"
        )


@dataclass
class BinPackingDataset:
    """A collection of bin packing instances."""
    
    name: str
    instances: list[BinPackingInstance]
    
    def __len__(self) -> int:
        return len(self.instances)
    
    def __iter__(self) -> Iterator[BinPackingInstance]:
        return iter(self.instances)
    
    def __getitem__(self, index: int) -> BinPackingInstance:
        return self.instances[index]
    
    def filter_by_size(
        self, 
        min_items: int = 0, 
        max_items: int = float("inf"),  # type: ignore
    ) -> "BinPackingDataset":
        """Filter instances by number of items."""
        filtered = [
            inst for inst in self.instances 
            if min_items <= inst.num_items <= max_items
        ]
        return BinPackingDataset(name=f"{self.name}_filtered", instances=filtered)
    
    def get_uniform_instances(self) -> "BinPackingDataset":
        """Get only uniform distribution instances (u*)."""
        filtered = [inst for inst in self.instances if inst.name.startswith("u")]
        return BinPackingDataset(name=f"{self.name}_uniform", instances=filtered)
    
    def get_triplet_instances(self) -> "BinPackingDataset":
        """Get only triplet instances (t*)."""
        filtered = [inst for inst in self.instances if inst.name.startswith("t")]
        return BinPackingDataset(name=f"{self.name}_triplet", instances=filtered)


def download_orlib_file(filename: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> Path:
    """Download a single OR-Library file if not cached."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    filepath = cache_dir / filename
    
    if filepath.exists():
        return filepath
    
    url = ORLIB_BASE_URL + filename
    print(f"Downloading {url} ...")
    
    try:
        urllib.request.urlretrieve(url, filepath)
        print(f"  Saved to {filepath}")
    except Exception as e:
        raise RuntimeError(f"Failed to download {url}: {e}") from e
    
    return filepath


def parse_orlib_file(filepath: Path) -> list[BinPackingInstance]:
    """Parse an OR-Library bin packing file."""
    instances: list[BinPackingInstance] = []
    
    with open(filepath, "r") as f:
        lines = [line.strip() for line in f if line.strip()]
    
    idx = 0
    num_problems = int(lines[idx])
    idx += 1
    
    for _ in range(num_problems):
        # Problem identifier
        name = lines[idx]
        idx += 1
        
        # Capacity, num_items, best_known (may be float format like "100.0")
        parts = lines[idx].split()
        capacity = int(float(parts[0]))
        num_items = int(float(parts[1]))
        best_known = int(float(parts[2]))
        idx += 1
        
        # Read item sizes
        items: list[int] = []
        while len(items) < num_items:
            line_items = lines[idx].split()
            items.extend(int(float(x)) for x in line_items)
            idx += 1
        
        # Determine if optimal is proven
        # For uniform class: most are optimal except a few
        # For triplet class: all are optimal (n/3 bins)
        is_triplet = name.startswith("t")
        optimal = is_triplet  # Triplets are always optimal
        
        instances.append(BinPackingInstance(
            name=name,
            capacity=capacity,
            items=items[:num_items],  # Ensure exact count
            best_known=best_known,
            optimal=optimal,
        ))
    
    return instances


def load_orlib_dataset(
    files: list[str] | None = None,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> BinPackingDataset:
    """Load OR-Library bin packing instances.
    
    Args:
        files: List of file names to load (e.g., ["binpack1", "binpack2"]).
               If None, loads all 8 files.
        cache_dir: Directory to cache downloaded files.
    
    Returns:
        BinPackingDataset containing all loaded instances.
    
    Example:
        >>> dataset = load_orlib_dataset(["binpack1", "binpack2"])
        >>> print(f"Loaded {len(dataset)} instances")
        >>> for inst in dataset:
        ...     print(f"{inst.name}: {inst.num_items} items, best={inst.best_known}")
    """
    if files is None:
        files = ORLIB_FILES
    
    all_instances: list[BinPackingInstance] = []
    
    for filename in files:
        if filename not in ORLIB_FILES:
            raise ValueError(f"Unknown OR-Library file: {filename}. "
                           f"Available: {ORLIB_FILES}")
        
        filepath = download_orlib_file(filename, cache_dir)
        instances = parse_orlib_file(filepath)
        all_instances.extend(instances)
        print(f"  Loaded {len(instances)} instances from {filename}")
    
    return BinPackingDataset(name="orlib", instances=all_instances)


def load_orlib_small(cache_dir: Path = DEFAULT_CACHE_DIR) -> BinPackingDataset:
    """Load small OR-Library instances (120-250 items) for quick testing."""
    return load_orlib_dataset(["binpack1.txt", "binpack2.txt", "binpack5.txt", "binpack6.txt"], cache_dir)


def load_orlib_large(cache_dir: Path = DEFAULT_CACHE_DIR) -> BinPackingDataset:
    """Load large OR-Library instances (500-1000 items) for full evaluation."""
    return load_orlib_dataset(["binpack3.txt", "binpack4.txt", "binpack7.txt", "binpack8.txt"], cache_dir)


# ============== Weibull/Scholl Dataset Support ==============

SCHOLL_CLASSES = {
    "class1": {
        "capacity": 100,
        "size_range": (1, 100),
        "num_items": [50, 100, 200, 500],
    },
    "class2": {
        "capacity": 100,
        "size_range": (1, 100),
        "num_items": [50, 100, 200, 500],
    },
    "class3": {
        "capacity": 100,
        "size_range": (25, 50),
        "num_items": [60, 120, 249, 501],
    },
}


def generate_weibull_instance(
    num_items: int,
    capacity: int = 100,
    shape: float = 2.0,
    scale: float = 30.0,
    seed: int = 42,
) -> BinPackingInstance:
    """Generate a bin packing instance with Weibull-distributed item sizes.
    
    Weibull distribution is often used to model real-world item sizes
    which tend to have more small items than large ones.
    
    Args:
        num_items: Number of items to generate.
        capacity: Bin capacity.
        shape: Weibull shape parameter (k). 
               k < 1: more small items, k > 1: more medium items.
        scale: Weibull scale parameter (lambda).
        seed: Random seed for reproducibility.
    
    Returns:
        A BinPackingInstance with Weibull-distributed items.
    """
    import random
    import math
    
    rng = random.Random(seed)
    items: list[int] = []
    
    for _ in range(num_items):
        # Generate Weibull random variable
        u = rng.random()
        # Inverse transform: x = scale * (-ln(1-u))^(1/shape)
        weibull_val = scale * ((-math.log(1 - u)) ** (1 / shape))
        # Clamp to valid range [1, capacity]
        item_size = max(1, min(capacity, int(weibull_val)))
        items.append(item_size)
    
    # Lower bound as best_known estimate
    total = sum(items)
    lower_bound = (total + capacity - 1) // capacity
    
    return BinPackingInstance(
        name=f"weibull_n{num_items}_s{seed}",
        capacity=capacity,
        items=items,
        best_known=lower_bound,
        optimal=False,
    )


def generate_weibull_dataset(
    num_instances: int = 20,
    items_per_instance: int = 100,
    capacity: int = 100,
    shape: float = 2.0,
    scale: float = 30.0,
    base_seed: int = 42,
) -> BinPackingDataset:
    """Generate a dataset of Weibull-distributed bin packing instances."""
    instances = [
        generate_weibull_instance(
            num_items=items_per_instance,
            capacity=capacity,
            shape=shape,
            scale=scale,
            seed=base_seed + i,
        )
        for i in range(num_instances)
    ]
    return BinPackingDataset(name="weibull", instances=instances)


# ============== Utility Functions ==============

def dataset_summary(dataset: BinPackingDataset) -> str:
    """Generate a summary of a dataset."""
    if not dataset.instances:
        return f"Dataset '{dataset.name}': empty"
    
    total_items = sum(inst.num_items for inst in dataset)
    avg_items = total_items / len(dataset)
    min_items = min(inst.num_items for inst in dataset)
    max_items = max(inst.num_items for inst in dataset)
    
    capacities = set(inst.capacity for inst in dataset)
    
    lines = [
        f"Dataset: {dataset.name}",
        f"  Instances: {len(dataset)}",
        f"  Items per instance: min={min_items}, max={max_items}, avg={avg_items:.1f}",
        f"  Capacities: {sorted(capacities)}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    # Demo: load and display dataset info
    print("=" * 60)
    print("OR-Library Bin Packing Dataset Loader")
    print("=" * 60)
    
    # Load small instances for demo
    print("\nLoading small OR-Library instances...")
    dataset = load_orlib_small()
    print(f"\n{dataset_summary(dataset)}")
    
    print("\n--- Sample instances ---")
    for inst in dataset.instances[:5]:
        print(f"  {inst.name}: {inst.num_items} items, "
              f"capacity={inst.capacity}, best={inst.best_known}")
    
    print("\n--- Uniform instances ---")
    uniform = dataset.get_uniform_instances()
    print(f"  Count: {len(uniform)}")
    
    print("\n--- Triplet instances ---")
    triplet = dataset.get_triplet_instances()
    print(f"  Count: {len(triplet)}")
    
    print("\n" + "=" * 60)
    print("Generating Weibull dataset...")
    weibull = generate_weibull_dataset(num_instances=5, items_per_instance=50)
    print(dataset_summary(weibull))

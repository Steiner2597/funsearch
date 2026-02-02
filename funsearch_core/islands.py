from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .population import Population


@dataclass
class Island:
    population: Population
    parameters: dict[str, object]


class IslandManager:
    def __init__(
        self,
        num_islands: int,
        population_factory: Callable[[], Population],
        island_parameters: list[dict[str, object]] | None = None,
    ) -> None:
        if num_islands <= 0:
            raise ValueError("num_islands must be positive")
        if island_parameters is None:
            island_parameters = [{} for _ in range(num_islands)]
        if len(island_parameters) != num_islands:
            raise ValueError("island_parameters length must match num_islands")
        self._islands: list[Island] = []
        for idx in range(num_islands):
            self._islands.append(Island(population_factory(), dict(island_parameters[idx])))

    @property
    def islands(self) -> tuple[Island, ...]:
        return tuple(self._islands)

    @property
    def populations(self) -> tuple[Population, ...]:
        return tuple(island.population for island in self._islands)

    def get_population(self, index: int) -> Population:
        return self._islands[index].population

    def get_parameters(self, index: int) -> dict[str, object]:
        return dict(self._islands[index].parameters)

    def migrate(self, num_migrants: int = 1) -> int:
        if num_migrants <= 0 or len(self._islands) < 2:
            return 0
        migrated = 0
        for idx, island in enumerate(self._islands):
            migrants = island.population.get_top_k(num_migrants)
            if not migrants:
                continue
            target = self._islands[(idx + 1) % len(self._islands)].population
            for candidate in migrants:
                cloned = candidate.model_copy(deep=True)
                if target.add_candidate(cloned):
                    migrated += 1
        return migrated

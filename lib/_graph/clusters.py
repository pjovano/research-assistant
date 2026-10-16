from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from _graph.library import LibraryGraph

MIN_CLUSTER_WORKS = 3
MAX_BIBLIOGRAPHY_WORKS = 12
MIN_SPLIT_SHARE = 3
MISFIT_NEIGHBOURS = 5
MIN_MISSING_CITERS = 3
MAJORITY_SHARE = 0.5
LOUVAIN_SEED = 7
REFERENCES_SHOWN = 10


@dataclass(frozen=True)
class Cluster:
    number: int
    works: list[str]

    def __len__(self) -> int:
        return len(self.works)


class CommunityDetection:
    def __init__(self, graph: LibraryGraph) -> None:
        self._graph = graph

    def clusters(self) -> list[Cluster]:
        import networkx
        network = networkx.Graph()
        network.add_nodes_from(self._graph.works)
        for pair in self._graph.all_pairs():
            network.add_edge(pair.left, pair.right, weight=pair.score)
        communities = networkx.community.louvain_communities(network, weight="weight", seed=LOUVAIN_SEED)
        ordered = sorted((sorted(community) for community in communities), key=lambda works: (-len(works), works))
        return [Cluster(number, works) for number, works in enumerate(ordered, start=1)]


class ClusterReport:
    def __init__(self, graph: LibraryGraph) -> None:
        self._graph = graph
        self._clusters = CommunityDetection(graph).clusters()

    def report(self) -> dict:
        described = [self._described(cluster) for cluster in self._sized()]
        findings = {"new": self._new(), "split": self._split(), "misfit": self._misfit(), "missing": self._missing()}
        return {"clusters": described, "findings": findings}

    def _sized(self) -> list[Cluster]:
        return [cluster for cluster in self._clusters if len(cluster) >= MIN_CLUSTER_WORKS]

    def _described(self, cluster: Cluster) -> dict:
        return {"cluster": cluster.number, "works": cluster.works, "bibliographies": self._bibliography_counts(cluster),
                "references": self._references(cluster, REFERENCES_SHOWN)}

    def _bibliography_counts(self, cluster: Cluster) -> dict[str, int]:
        counted = Counter(name for work in cluster.works for name in self._graph.bibliographies_of(work))
        return dict(counted.most_common())

    def _references(self, cluster: Cluster, shown: int) -> list[dict]:
        counted = Counter(key for work in cluster.works for key in self._graph.references_of(work))
        return [{"reference": self._graph.label_of(key), "held": key.startswith("held:"), "citers": count}
                for key, count in counted.most_common(shown)]

    def _new(self) -> list[dict]:
        unplaced = [cluster for cluster in self._sized() if not self._has_a_shared_bibliography(cluster)]
        return [{"cluster": cluster.number, "works": cluster.works,
                 "references": self._references(cluster, REFERENCES_SHOWN)} for cluster in unplaced]

    def _has_a_shared_bibliography(self, cluster: Cluster) -> bool:
        counts = self._bibliography_counts(cluster)
        return bool(counts) and max(counts.values()) >= MAJORITY_SHARE * len(cluster)

    def _split(self) -> list[dict]:
        members: dict[str, list[tuple[int, str]]] = {}
        for cluster in self._clusters:
            for work in cluster.works:
                for name in self._graph.bibliographies_of(work):
                    members.setdefault(name, []).append((cluster.number, work))
        return [self._split_of(name, listed) for name, listed in sorted(members.items()) if self._splits(listed)]

    @staticmethod
    def _splits(listed: list[tuple[int, str]]) -> bool:
        shares = Counter(number for number, _work in listed)
        large = [count for count in shares.values() if count >= MIN_SPLIT_SHARE]
        return len(listed) > MAX_BIBLIOGRAPHY_WORKS and len(large) >= 2

    @staticmethod
    def _split_of(name: str, listed: list[tuple[int, str]]) -> dict:
        groups: dict[int, list[str]] = {}
        for number, work in listed:
            groups.setdefault(number, []).append(work)
        parts = [{"cluster": number, "works": works} for number, works in sorted(groups.items())
                 if len(works) >= MIN_SPLIT_SHARE]
        return {"bibliography": name, "parts": parts}

    def _misfit(self) -> list[dict]:
        return [finding for finding in (self._misfit_of(work) for work in self._graph.works) if finding]

    def _misfit_of(self, work: str) -> dict | None:
        placed = set(self._graph.bibliographies_of(work))
        nearest = self._graph.pairs_of(work)[:MISFIT_NEIGHBOURS]
        if not placed or len(nearest) < MIN_CLUSTER_WORKS:
            return None
        around = Counter(name for pair in nearest for name in self._graph.bibliographies_of(pair.right))
        if placed & set(around):
            return None
        return {"work": work, "bibliographies": sorted(placed), "neighbours": [pair.right for pair in nearest],
                "neighbours_on": dict(around.most_common())}

    def _missing(self) -> list[dict]:
        return [finding for cluster in self._sized() for finding in self._missing_in(cluster)]

    def _missing_in(self, cluster: Cluster) -> list[dict]:
        counted = Counter(key for work in cluster.works for key in self._graph.references_of(work)
                          if not key.startswith("held:"))
        return [{"cluster": cluster.number, "reference": self._graph.label_of(key), "citers": count}
                for key, count in counted.most_common() if count >= MIN_MISSING_CITERS]

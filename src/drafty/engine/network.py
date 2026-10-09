"""Flow network: directed graph, cycle detection and downstream accumulation.

Nodes are drains and culverts. Catchments inject flow into the drain they feed. A drain discharges
to an outlet, another drain or a culvert; a culvert discharges to a drain. Flows accumulate
downstream (a drain after a culvert carries both sides' water).
"""

from __future__ import annotations

from collections import deque

from drafty.spec.models import DesignSpec, ParsedBrief

SpecLike = DesignSpec | ParsedBrief

_TERMINAL_OUTLET_TYPES = {"existing_channel", "soakaway"}


def node_ids(spec: SpecLike) -> list[str]:
    """All drain and culvert ids."""
    return [drain.id for drain in spec.drains] + [culvert.id for culvert in spec.culverts]


def build_adjacency(spec: SpecLike) -> dict[str, list[str]]:
    """Map each node to the nodes it discharges to."""
    drain_ids = {drain.id for drain in spec.drains}
    culvert_ids = {culvert.id for culvert in spec.culverts}
    adjacency: dict[str, list[str]] = {node: [] for node in node_ids(spec)}

    for drain in spec.drains:
        outlet = drain.outlet
        if outlet.type == "culvert" and outlet.ref in culvert_ids:
            adjacency[drain.id].append(outlet.ref)
        elif outlet.type == "drain" and outlet.ref in drain_ids:
            adjacency[drain.id].append(outlet.ref)

    for culvert in spec.culverts:
        if culvert.discharges_to in drain_ids:
            adjacency[culvert.id].append(culvert.discharges_to)

    return adjacency


def topological_order(nodes: list[str], adjacency: dict[str, list[str]]) -> list[str] | None:
    """Kahn's algorithm. Returns ``None`` if the graph has a cycle."""
    indegree = {node: 0 for node in nodes}
    for targets in adjacency.values():
        for target in targets:
            if target in indegree:
                indegree[target] += 1
    queue = deque(sorted(node for node in nodes if indegree[node] == 0))
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for target in adjacency.get(node, []):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(order) != len(nodes):
        return None
    return order


def accumulate_flows(
    spec: SpecLike, injections: dict[str, float]
) -> tuple[dict[str, float], list[str]]:
    """Accumulate catchment injections downstream.

    Returns ``(flow_per_node, warnings)``. A cycle produces a warning and empty flows.
    """
    nodes = node_ids(spec)
    adjacency = build_adjacency(spec)
    order = topological_order(nodes, adjacency)
    if order is None:
        return {}, ["flow network contains a cycle; flows were not accumulated"]

    flow = {node: injections.get(node, 0.0) for node in nodes}
    for node in order:
        for target in adjacency.get(node, []):
            flow[target] += flow[node]
    return flow, []


def reaches_outlet(spec: SpecLike, start: str) -> bool:
    """Whether flow from a node reaches a terminal outlet without cycling."""
    adjacency = build_adjacency(spec)
    drains = {drain.id: drain for drain in spec.drains}
    seen: set[str] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node in seen:
            return False
        seen.add(node)
        targets = adjacency.get(node, [])
        if not targets:
            drain = drains.get(node)
            if drain is None:
                return True
            return drain.outlet.type in _TERMINAL_OUTLET_TYPES
        stack.extend(targets)
    return False

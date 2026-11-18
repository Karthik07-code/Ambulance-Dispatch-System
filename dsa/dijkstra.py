"""
Dijkstra's Shortest Path Algorithm Implementation
=================================================
Academic Context:
Dijkstra's algorithm solves the Single-Source Shortest Path (SSSP) problem for a
graph with non-negative edge weights.

Mechanics:
1. Initialize distances from start_node to all nodes as infinity (inf), except start_node = 0.
2. Maintain a Priority Queue (Min-Heap) of pairs `(current_distance, current_vertex)`.
3. In each step, extract the vertex `u` with the smallest tentative distance.
4. For every neighbor `v` of `u` with edge weight `w`:
     If distance[u] + w < distance[v]:
         distance[v] = distance[u] + w
         previous[v] = u
         push (distance[v], v) into Min-Heap
5. Terminate when the target vertex is extracted or the queue is exhausted.
6. Reconstruct the shortest path by backtracking through the `previous` pointers.

Time Complexity:
- O((V + E) log V) using a binary heap, where V is vertices (hubs) and E is edges (roads).
Space Complexity:
- O(V) for distances and predecessor arrays.
"""

import heapq
from typing import Dict, List, Optional, Tuple
from dsa.graph import RoadGraph


def dijkstra_shortest_path(
    graph: RoadGraph,
    start_node: str,
    target_node: str
) -> Tuple[float, List[str]]:
    """
    Computes the shortest road distance and reconstructs the path from start_node to target_node.

    Returns:
        (shortest_distance_km, path_list)
        If unreachable, returns (float('inf'), [])
    """
    # Validation checks
    if start_node not in graph.adj_list or target_node not in graph.adj_list:
        return float('inf'), []

    if start_node == target_node:
        return 0.0, [start_node]

    # Map each vertex to its shortest known distance from start_node
    distances: Dict[str, float] = {node: float('inf') for node in graph.adj_list}
    distances[start_node] = 0.0

    # Map each vertex to its predecessor on the shortest path
    predecessors: Dict[str, Optional[str]] = {node: None for node in graph.adj_list}

    # Min-heap priority queue: stores (tentative_distance, vertex_name)
    pq: List[Tuple[float, str]] = []
    heapq.heappush(pq, (0.0, start_node))

    visited = set()

    while pq:
        current_dist, current_node = heapq.heappop(pq)

        # Early exit if we reached the target node
        if current_node == target_node:
            break

        # If already visited with a shorter distance, ignore
        if current_node in visited:
            continue
        visited.add(current_node)

        # Relax adjacent edges
        for neighbor, edge_weight in graph.get_neighbors(current_node):
            if neighbor in visited:
                continue

            new_dist = current_dist + edge_weight
            if new_dist < distances[neighbor]:
                distances[neighbor] = new_dist
                predecessors[neighbor] = current_node
                heapq.heappush(pq, (new_dist, neighbor))

    # Check if target is unreachable
    if distances[target_node] == float('inf'):
        return float('inf'), []

    # Reconstruct path by backtracking from target_node to start_node
    path = []
    curr = target_node
    while curr is not None:
        path.append(curr)
        curr = predecessors[curr]
    path.reverse()

    return round(distances[target_node], 2), path


def calculate_distances_from_candidates(
    graph: RoadGraph,
    candidate_locations: List[str],
    incident_location: str
) -> Dict[str, Tuple[float, List[str]]]:
    """
    Helper function to run Dijkstra from multiple candidate ambulance locations
    to a single incident location.
    Returns:
        Dict mapping location -> (distance_km, path_list)
    """
    results = {}
    for loc in candidate_locations:
        dist, path = dijkstra_shortest_path(graph, loc, incident_location)
        results[loc] = (dist, path)
    return results


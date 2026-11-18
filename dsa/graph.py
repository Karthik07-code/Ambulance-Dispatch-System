"""
Graph Data Structure Implementation (Adjacency List)
=====================================================
Academic Context:
A Graph G = (V, E) is used to model the predefined road network.
- Vertices (V): Predefined city hubs/locations (e.g., Gandhipuram, Peelamedu).
- Edges (E): Physical road connections between two hubs.
- Weights: The road distances in kilometres (km).

Representation:
We use an Adjacency List: a dictionary mapping each vertex to a list of
tuples `(neighbor, distance_km)`.
- Space Complexity: O(V + E)
- Edge lookup/traversal: O(degree(V))

This is more space-efficient than an Adjacency Matrix (O(V^2)) for sparse road networks.
"""

from typing import Dict, List, Tuple, Set


class RoadGraph:
    """
    Weighted, undirected Graph representing the road network using an Adjacency List.
    """

    def __init__(self):
        # adj_list maps vertex -> list of (neighbor_vertex, weight_km)
        self.adj_list: Dict[str, List[Tuple[str, float]]] = {}

    def add_vertex(self, vertex: str) -> None:
        """Add a location vertex if it does not already exist."""
        if vertex not in self.adj_list:
            self.adj_list[vertex] = []

    def add_edge(self, u: str, v: str, weight: float, bidirectional: bool = True) -> None:
        """
        Add a weighted edge (road) between u and v.
        Weight represents road distance in km (must be non-negative).
        """
        if weight < 0:
            raise ValueError("Road distances cannot be negative.")

        self.add_vertex(u)
        self.add_vertex(v)

        # Check if edge already exists to prevent duplicate parallel edges
        for neighbor, _ in self.adj_list[u]:
            if neighbor == v:
                return

        self.adj_list[u].append((v, float(weight)))
        if bidirectional:
            self.adj_list[v].append((u, float(weight)))

    def get_neighbors(self, vertex: str) -> List[Tuple[str, float]]:
        """Return list of (neighbor, distance) for a given vertex."""
        return self.adj_list.get(vertex, [])

    def get_all_locations(self) -> List[str]:
        """Return a sorted list of all unique location names in the network."""
        return sorted(list(self.adj_list.keys()))

    def get_all_edges(self) -> List[Dict[str, any]]:
        """Return all unique edges for UI presentation / visualization."""
        edges = []
        seen = set()
        for u in self.adj_list:
            for v, weight in self.adj_list[u]:
                edge_id = tuple(sorted([u, v]))
                if edge_id not in seen:
                    seen.add(edge_id)
                    edges.append({"from": u, "to": v, "distance_km": weight})
        return edges


def get_default_road_network() -> RoadGraph:
    """
    Predefined sample Coimbatore road network with realistic demo distances.
    Includes the mandatory hubs:
      - Gandhipuram
      - Peelamedu
      - RS Puram
      - Railway Station
      - Singanallur
    Plus well-connected hubs:
      - Ukkadam
      - Ganapathy
    """
    graph = RoadGraph()

    # Define connections with realistic road distances (in km)
    connections = [
        ("Gandhipuram", "Peelamedu", 6.5),
        ("Gandhipuram", "RS Puram", 4.2),
        ("Gandhipuram", "Railway Station", 3.0),
        ("Gandhipuram", "Ganapathy", 3.8),
        ("RS Puram", "Railway Station", 2.5),
        ("RS Puram", "Ukkadam", 3.5),
        ("Railway Station", "Ukkadam", 2.2),
        ("Railway Station", "Singanallur", 7.0),
        ("Peelamedu", "Singanallur", 4.0),
        ("Peelamedu", "Ganapathy", 5.5),
        ("Singanallur", "Ukkadam", 6.8),
    ]

    for u, v, dist in connections:
        graph.add_edge(u, v, dist, bidirectional=True)

    return graph


# Global default instance for reuse across modules
ROAD_NETWORK = get_default_road_network()
PREDEFINED_LOCATIONS = ROAD_NETWORK.get_all_locations()

# Realistic geographic coordinates for demo locations in Coimbatore
LOCATION_COORDINATES: Dict[str, Tuple[float, float]] = {
    "Gandhipuram": (11.0168, 76.9558),
    "Peelamedu": (11.0267, 77.0123),
    "RS Puram": (11.0089, 76.9463),
    "Railway Station": (10.9996, 76.9634),
    "Singanallur": (10.9972, 77.0253),
    "Ukkadam": (10.9880, 76.9610),
    "Ganapathy": (11.0420, 76.9740),
}


def get_nearest_location(lat: float, lng: float) -> str:
    """
    Finds the closest predefined road network node to a given (latitude, longitude)
    using Euclidean distance approximation for local city coordinates.
    """
    best_loc = "Gandhipuram"
    min_dist_sq = float('inf')
    for loc, coords in LOCATION_COORDINATES.items():
        dist_sq = (coords[0] - lat) ** 2 + (coords[1] - lng) ** 2
        if dist_sq < min_dist_sq:
            min_dist_sq = dist_sq
            best_loc = loc
    return best_loc



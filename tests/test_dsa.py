"""
Unit tests for DSA modules: RoadGraph, MinHeap, EmergencyPriorityQueue, and Dijkstra.
"""

import unittest
from dsa.graph import RoadGraph, get_default_road_network
from dsa.priority_queue import MinHeap, EmergencyPriorityQueue
from dsa.dijkstra import dijkstra_shortest_path


class TestDSA(unittest.TestCase):

    def test_min_heap(self):
        heap = MinHeap()
        heap.push(3, 1, "task3")
        heap.push(1, 2, "task1")
        heap.push(2, 3, "task2")

        # Smallest priority rank should come first
        self.assertEqual(heap.pop(), (1, 2, "task1"))
        self.assertEqual(heap.pop(), (2, 3, "task2"))
        self.assertEqual(heap.pop(), (3, 1, "task3"))
        self.assertTrue(heap.is_empty())

    def test_priority_queue_severity_and_fifo(self):
        pq = EmergencyPriorityQueue()
        # Add tasks:
        # req 1: Medium, id 10
        # req 2: Critical, id 11
        # req 3: High, id 12
        # req 4: Critical, id 13 (tied with req 2, but later id)
        pq.push({"request_id": 10, "patient_name": "P1", "severity": "Medium"})
        pq.push({"request_id": 11, "patient_name": "P2", "severity": "Critical"})
        pq.push({"request_id": 12, "patient_name": "P3", "severity": "High"})
        pq.push({"request_id": 13, "patient_name": "P4", "severity": "Critical"})

        # First out must be P2 (Critical, id 11)
        r1 = pq.pop()
        self.assertEqual(r1["patient_name"], "P2")
        self.assertEqual(r1["severity"], "Critical")

        # Second out must be P4 (Critical, id 13 - FIFO preserved for equal severity)
        r2 = pq.pop()
        self.assertEqual(r2["patient_name"], "P4")
        self.assertEqual(r2["severity"], "Critical")

        # Third out must be P3 (High, id 12)
        r3 = pq.pop()
        self.assertEqual(r3["patient_name"], "P3")
        self.assertEqual(r3["severity"], "High")

        # Fourth out must be P1 (Medium, id 10)
        r4 = pq.pop()
        self.assertEqual(r4["patient_name"], "P1")
        self.assertEqual(r4["severity"], "Medium")

    def test_graph_and_dijkstra(self):
        graph = get_default_road_network()
        # Shortest path between Gandhipuram and RS Puram is direct: 4.2 km
        dist, path = dijkstra_shortest_path(graph, "Gandhipuram", "RS Puram")
        self.assertEqual(dist, 4.2)
        self.assertEqual(path, ["Gandhipuram", "RS Puram"])

        # RS Puram to Singanallur:
        # Paths:
        # RS Puram -> Railway Station (2.5) -> Singanallur (7.0) = 9.5
        # RS Puram -> Ukkadam (3.5) -> Singanallur (6.8) = 10.3
        # RS Puram -> Gandhipuram (4.2) -> Peelamedu (6.5) -> Singanallur (4.0) = 14.7
        dist, path = dijkstra_shortest_path(graph, "RS Puram", "Singanallur")
        self.assertEqual(dist, 9.5)
        self.assertEqual(path, ["RS Puram", "Railway Station", "Singanallur"])

    def test_dijkstra_unreachable(self):
        graph = RoadGraph()
        graph.add_vertex("A")
        graph.add_vertex("B")
        dist, path = dijkstra_shortest_path(graph, "A", "B")
        self.assertEqual(dist, float('inf'))
        self.assertEqual(path, [])


if __name__ == "__main__":
    unittest.main()


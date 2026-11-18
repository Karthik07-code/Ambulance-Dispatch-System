"""
Priority Queue & Min-Heap Implementation
========================================
Academic Context:
A Priority Queue is an abstract data type where each element has an associated
priority. In emergency dispatch:
1. Higher severity requests must be serviced ahead of lower severity requests.
   Hierarchy:
     - Critical (Rank 1 - Highest Priority)
     - High     (Rank 2)
     - Medium   (Rank 3)
     - Low      (Rank 4 - Lowest Priority)
2. Ties in severity must strictly obey FIFO (First-In, First-Out) order.
   Tie-breaker: arrival timestamp or ascending request_id.

Binary Min-Heap Mechanics:
- Array-based complete binary tree where parent node <= child nodes.
- For a node at index i:
    Parent index:      (i - 1) // 2
    Left Child index:  2 * i + 1
    Right Child index: 2 * i + 2
- Insert (push): O(log N) using sift-up.
- Extract-Min (pop): O(log N) using sift-down.
- Peek: O(1).
"""

from typing import Any, List, Optional, Tuple


SEVERITY_MAPPING = {
    "Critical": 1,
    "High": 2,
    "Medium": 3,
    "Low": 4
}


class MinHeap:
    """
    A generic array-backed Binary Min-Heap implemented from scratch for educational demonstration.
    Elements are stored as tuples: (priority_key, tie_breaker, payload).
    """

    def __init__(self):
        self.heap: List[Tuple[int, int, Any]] = []

    def __len__(self) -> int:
        return len(self.heap)

    def is_empty(self) -> bool:
        return len(self.heap) == 0

    def peek(self) -> Optional[Tuple[int, int, Any]]:
        """Return the minimum element without removing it. O(1) time complexity."""
        if self.is_empty():
            return None
        return self.heap[0]

    def push(self, priority_key: int, tie_breaker: int, payload: Any) -> None:
        """
        Insert an item into the Min-Heap.
        Appends to the end and sifts up to restore heap invariant. O(log N).
        """
        item = (priority_key, tie_breaker, payload)
        self.heap.append(item)
        self._sift_up(len(self.heap) - 1)

    def pop(self) -> Optional[Tuple[int, int, Any]]:
        """
        Extract and return the root (minimum) element.
        Replaces root with the last element and sifts down. O(log N).
        """
        if self.is_empty():
            return None

        # If only 1 element, simply pop and return
        if len(self.heap) == 1:
            return self.heap.pop()

        root = self.heap[0]
        # Move the last element to root and restore heap property
        self.heap[0] = self.heap.pop()
        self._sift_down(0)
        return root

    def _sift_up(self, index: int) -> None:
        """Move element at index up until heap property parent <= child is restored."""
        parent_index = (index - 1) // 2
        while index > 0 and self.heap[index] < self.heap[parent_index]:
            # Swap with parent
            self.heap[index], self.heap[parent_index] = self.heap[parent_index], self.heap[index]
            index = parent_index
            parent_index = (index - 1) // 2

    def _sift_down(self, index: int) -> None:
        """Move element at index down until heap property parent <= children is restored."""
        size = len(self.heap)
        while True:
            left_child = 2 * index + 1
            right_child = 2 * index + 2
            smallest = index

            if left_child < size and self.heap[left_child] < self.heap[smallest]:
                smallest = left_child

            if right_child < size and self.heap[right_child] < self.heap[smallest]:
                smallest = right_child

            if smallest != index:
                # Swap with the smallest child
                self.heap[index], self.heap[smallest] = self.heap[smallest], self.heap[index]
                index = smallest
            else:
                break


class EmergencyPriorityQueue:
    """
    Priority Queue tailored for Emergency Requests.
    Encapsulates MinHeap and maps severity levels + arrival IDs.
    """

    def __init__(self):
        self.heap = MinHeap()
        self._counter = 0  # Fallback monotonic counter for FIFO if request_id is not passed

    def push(self, request: dict) -> None:
        """
        Push an emergency request dictionary into the priority queue.
        Expected keys in request: 'severity', 'request_id' (optional), plus payload data.
        """
        severity_str = request.get("severity", "Medium")
        priority_rank = SEVERITY_MAPPING.get(severity_str, 3)

        # Tie-breaker: prefer request_id if available, otherwise monotonically increasing counter
        tie_breaker = request.get("request_id")
        if tie_breaker is None:
            self._counter += 1
            tie_breaker = self._counter

        self.heap.push(priority_rank, tie_breaker, request)

    def pop(self) -> Optional[dict]:
        """
        Extract the highest priority (and earliest arrival if tied) emergency request.
        """
        item = self.heap.pop()
        if item is None:
            return None
        _, _, request = item
        return request

    def peek(self) -> Optional[dict]:
        """View the next emergency request to be dispatched without popping."""
        item = self.heap.peek()
        if item is None:
            return None
        _, _, request = item
        return request

    def is_empty(self) -> bool:
        return self.heap.is_empty()

    def size(self) -> int:
        return len(self.heap)

    def get_all_ordered(self) -> List[dict]:
        """
        Return a copy of all requests currently in queue in priority order.
        Does not mutate the queue.
        """
        # Clone heap elements and pop sequentially
        temp_heap = MinHeap()
        temp_heap.heap = list(self.heap.heap)
        ordered = []
        while not temp_heap.is_empty():
            _, _, req = temp_heap.pop()
            ordered.append(req)
        return ordered


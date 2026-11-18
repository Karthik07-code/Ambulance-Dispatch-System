# Emergency Ambulance Dispatch System

An educational, web-based **Emergency Ambulance Dispatch System** built with **Python (Flask)**, **SQLite**, **Tailwind CSS**, and **Bootstrap 5**, demonstrating **Data Structures and Algorithms (DSA)** in a real-world multi-role simulation.

> **Disclaimer:** This is an educational prototype for a college project demonstration. It does not connect to live emergency call centres or real ambulance operators. In a real life-threatening emergency, call **108 / 112 / 911**.

---

## 1. Multi-Role System Architecture

The application contains **three distinct panels** operating synchronously on a single unified database:

| Panel | Access & Security | Primary Purpose | Key Features |
| :--- | :--- | :--- | :--- |
| **Public User Panel** | Public (`/user`) &bull; **Zero Login** | Fast emergency ambulance booking & tracking | 3-way location picker (GPS, Places, Map Pin), unguessable token tracking (`/track/<token>`), road-based ETA, cancellation, and real-time WebSocket sync. |
| **Driver Panel** | Authenticated (`/driver`) &bull; Role: `Driver` | Mission navigation & patient handover | View assigned dispatches, tap-to-call patient, **Open in Google Maps**, status updates (`Accepted` &rarr; `En Route` &rarr; `Arrived` &rarr; `Picked Up` &rarr; `Completed`), nearby emergency hospital search, and background GPS broadcasting. |
| **Admin Panel** | Authenticated (`/dashboard`) &bull; Role: `Admin` | Fleet oversight & dispatch engine | Fleet metrics, live vehicle status, manual & automatic priority dispatch (Min-Heap + Dijkstra), fleet CRUD, and dispatch history. |

---

## 2. Pre-Configured Demo Credentials

For quick evaluation during college presentations and viva tests:

| Role | Username | Password | Linked Ambulance / Profile | Access URL |
| :--- | :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` | System Administrator | [http://127.0.0.1:5000/login](http://127.0.0.1:5000/login) |
| **Ambulance Driver 1** | `driver1` | `driver123` | Ravi Chandran (AMB-101) | [http://127.0.0.1:5000/login](http://127.0.0.1:5000/login) |
| **Ambulance Driver 2** | `driver2` | `driver123` | Senthil Kumar (AMB-102) | [http://127.0.0.1:5000/login](http://127.0.0.1:5000/login) |
| **Ambulance Driver 3** | `driver3` | `driver123` | Murugan P. (AMB-103) | [http://127.0.0.1:5000/login](http://127.0.0.1:5000/login) |
| **Ambulance Driver 4** | `driver4` | `driver123` | Karthik Selvam (AMB-104) | [http://127.0.0.1:5000/login](http://127.0.0.1:5000/login) |
| **Public Requester** | *None* | *None* | Zero-Login Public Patient | [http://127.0.0.1:5000/user](http://127.0.0.1:5000/user) |

---

## 3. Data Structures & Algorithms (DSA) Implementation

| Component | Module | Academic Role & Complexity |
| :--- | :--- | :--- |
| **Priority Queue (Min-Heap)** | `dsa/priority_queue.py` | Ranks pending requests: `Critical (Rank 1)` &gt; `High (Rank 2)` &gt; `Medium (Rank 3)` &gt; `Low (Rank 4)`. Preserves strict **FIFO order** on ties using request ID. **Time: O(log N)**. |
| **Graph (Adjacency List)** | `dsa/graph.py` | Models the Coimbatore road network. Vertices are hubs (*Gandhipuram, Peelamedu, RS Puram, Railway Station, Singanallur, Ukkadam, Ganapathy*); weighted edges represent road distances in km. **Space: O(V + E)**. |
| **Dijkstra's Algorithm** | `dsa/dijkstra.py` | Calculates the shortest road distance from candidate available ambulance bases to the emergency location. **Time: O((V + E) log V)**. |

---

## 4. End-to-End Workflow Demonstration

### Step 1: Patient Books an Ambulance (User Panel)
1. Navigate to `http://127.0.0.1:5000/user`.
2. Click **"Book an Ambulance Now"**.
3. Enter patient name (*"Anitha R."*), contact phone, and select severity (*Critical*).
4. Select location by clicking the map or selecting a hub (e.g. *Peelamedu*).
5. Click **"Confirm & Request Ambulance"**. You are instantly redirected to the private live tracking page (`/track/<token>`).

### Step 2: Driver Receives & Navigates Mission (Driver Panel)
1. Open a new window and sign in at `http://127.0.0.1:5000/login` as `driver1` (password: `driver123`).
2. Driver sees the active call with patient name, tap-to-call phone action, and **"Open in Google Maps"** navigation button.
3. Progress through the mission:
   - Click **"1. Accept Dispatch"** &rarr; status updates to `Accepted`.
   - Click **"2. Start Driving"** &rarr; status updates to `En Route`.
   - Click **"3. Arrived at Scene"** &rarr; status updates to `Arrived`.
4. Under **Nearby Emergency Hospitals**, click **"Select Hospital"** (e.g. *PSG Hospitals* or *KMCH*).
5. Click **"4. Patient Picked Up"** &rarr; vehicle routes to hospital.
6. Click **"5. Mark Trip Completed"** &rarr; mission closes and ambulance returns to `Available`.

### Step 3: Real-Time Synchronization (WebSocket)
- Throughout Step 2, watch the patient's User tracking screen update **live in real time via Socket.IO** without any page reload!

---

## 5. Getting Started & Installation

```bash
# 1. Activate the environment
source .venv/bin/activate

# 2. Run the application
python app.py
```

Open your browser:
- **Public User Portal:** [http://127.0.0.1:5000/user](http://127.0.0.1:5000/user)
- **Staff Sign In:** [http://127.0.0.1:5000/login](http://127.0.0.1:5000/login)
- **Admin Dashboard:** [http://127.0.0.1:5000/dashboard](http://127.0.0.1:5000/dashboard)
- **Driver Cockpit:** [http://127.0.0.1:5000/driver](http://127.0.0.1:5000/driver)

---

## 6. Running Automated Tests

Run all 23 unit, integration, and functional tests:
```bash
python -m unittest discover tests
```

Output:
```text
.......................
----------------------------------------------------------------------
Ran 23 tests in 2.242s

OK
```

# Emergency Ambulance Dispatch System

## 1. Project Overview

Build a basic, web-based **Emergency Ambulance Dispatch System** for a college mini-project. The system helps an administrator record emergency requests, manage a small fleet of ambulances, and assign the nearest available ambulance based on a predefined road network. The main academic objective is to demonstrate **Data Structures and Algorithms (DSA)** in a practical application.

> This is an educational simulation only, not a real emergency-response service. It does not connect to live GPS, emergency call centres, or real ambulance operators.

## 2. Technology Stack

- **Backend:** Python with Flask
- **Frontend:** HTML, CSS, Bootstrap 5, and minimal JavaScript
- **Database:** SQLite
- **DSA:** Queue, Priority Queue (min-heap), Graph, and Dijkstra's shortest-path algorithm

Keep the application beginner-friendly and suitable for a basic college demonstration. Avoid unnecessary third-party services and complex deployment requirements.

## 3. Main Modules and Features

### A. Admin Dashboard
- Display total ambulances, available ambulances, busy ambulances, pending emergencies, and assigned emergencies.
- Show recent emergency requests and recent dispatches.

### B. Ambulance Management
- Add, view, edit, and manage ambulance records.
- Store ambulance number, current predefined location, and availability status.
- Allow the administrator to update an ambulance's location when it is available.
- Suggested statuses: `Available`, `Busy`, and `Maintenance`.

### C. Emergency Request Management
- Register an emergency with patient name (or a demo patient label), predefined incident location, and severity.
- Suggested severity levels: `Critical`, `High`, `Medium`, and `Low`.
- View requests and their status: `Pending`, `Assigned`, `Completed`, or `Cancelled`.
- Validate required fields and prevent invalid locations or severity values.

### D. Automatic Ambulance Dispatch
- Process the highest-priority pending emergency first.
- For that request, consider only ambulances whose status is `Available`.
- Calculate the shortest road distance from each available ambulance's current location to the incident location.
- Assign the ambulance with the smallest reachable distance.
- Update the ambulance status to `Busy`, set the request status to `Assigned`, and create a dispatch-history record.
- If no ambulance is available or no route exists, leave the request pending and show a clear message.
- Prevent an ambulance from being assigned to more than one active request.

### E. Dispatch History
- Display request ID, ambulance number, incident location, calculated distance, assignment time, and dispatch status.
- Allow an assigned dispatch to be marked `Completed`; on completion, mark the ambulance `Available` again and the request `Completed`.

## 4. DSA Requirements

1. **Queue / FIFO:** Preserve arrival order when emergency requests have the same severity.
2. **Priority Queue (Heap):** Prioritise requests in this order: Critical, High, Medium, Low. Use arrival time or request ID as the tie-breaker so earlier requests are processed first.
3. **Graph:** Represent the predefined road network as an adjacency list. Locations are vertices; roads and their distances (in km) are weighted edges. Use an undirected graph unless a road is explicitly defined as one-way.
4. **Dijkstra's Algorithm:** Find the shortest distance and route between an ambulance's current location and the emergency location. Use non-negative road weights. If a location is unreachable, treat its distance as infinity and do not select that ambulance.

The dispatch decision must be based on **shortest road distance**, not straight-line distance. Keep the DSA implementation in separate, clearly named Python files so it can be demonstrated during evaluation.

## 5. Predefined Demo Locations and Road Network

Use a small fictional/sample Coimbatore-style network; no live maps or GPS are required. Include at least these locations:

- Gandhipuram
- Peelamedu
- RS Puram
- Railway Station
- Singanallur

Create a simple weighted road graph with realistic-looking positive demo distances (in kilometres). Store the graph in one dedicated module so it can be easily edited. Ensure the sample graph is connected for the main demonstration routes.

Seed the database with a few sample ambulances, for example:

- AMB-101 — Gandhipuram — Available
- AMB-102 — Peelamedu — Available
- AMB-103 — RS Puram — Available
- AMB-104 — Singanallur — Available

Clearly label all locations and distances as demonstration data.

## 6. Suggested Database Tables

### `ambulances`
- `ambulance_id` — primary key
- `ambulance_number` — unique, required
- `current_location` — required predefined location
- `status` — Available / Busy / Maintenance

### `emergency_requests`
- `request_id` — primary key
- `patient_name` — required
- `emergency_location` — required predefined location
- `severity` — Critical / High / Medium / Low
- `request_status` — Pending / Assigned / Completed / Cancelled
- `created_at` — timestamp

### `dispatch_history`
- `dispatch_id` — primary key
- `request_id` — foreign key
- `ambulance_id` — foreign key
- `distance_km` — calculated shortest road distance
- `route` — optional readable route/path
- `assigned_time` — timestamp
- `dispatch_status` — Assigned / Completed / Cancelled

Use parameterised SQL queries and enable SQLite foreign-key enforcement for each database connection.

## 7. Required Pages / UI

- **Dashboard:** Summary cards and recent activity.
- **Ambulance Management:** Ambulance list, add form, and edit form.
- **Emergency Requests:** Request list, create form, severity and status indicators.
- **Dispatch:** Button/action to run automatic dispatch and a clear result showing the selected ambulance, route, and distance.
- **Dispatch History:** Past assignments and a completion action.

Use a clean, responsive Bootstrap interface with a simple navigation bar/sidebar, readable tables, status badges, form validation, and success/error alerts. The interface should be easy to demonstrate in a college presentation.

## 8. Suggested Project Structure

```text
ambulance_dispatch/
├── app.py
├── database.py
├── requirements.txt
├── ambulance.db                 # created automatically at runtime
├── dsa/
│   ├── __init__.py
│   ├── priority_queue.py
│   ├── graph.py
│   └── dijkstra.py
├── modules/
│   ├── __init__.py
│   ├── ambulance.py
│   ├── emergency.py
│   └── dispatch.py
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── ambulances.html
│   ├── ambulance_form.html
│   ├── emergencies.html
│   ├── emergency_form.html
│   └── dispatch_history.html
└── static/
    ├── css/style.css
    └── js/
```

## 9. Core Dispatch Workflow

1. Administrator registers ambulances and their current locations.
2. Administrator records one or more emergency requests.
3. The system orders pending requests by severity using a priority queue; ties follow FIFO order.
4. For the highest-priority request, the system runs Dijkstra's algorithm from each available ambulance location to the incident location.
5. The system chooses the reachable ambulance with the lowest shortest-path distance.
6. The system records the assignment, marks the ambulance Busy, and changes the request to Assigned.
7. When the dispatch is marked Completed, the request becomes Completed and the ambulance becomes Available.

Use a database transaction during assignment so an ambulance cannot be allocated twice if two dispatch actions happen close together. For this single-user college demo, a simple transaction and status re-check are sufficient.

## 10. Basic Acceptance Criteria

- The application starts locally using Flask and creates its SQLite database automatically.
- Sample ambulances and predefined locations are available for demonstration.
- Admin can create, view, and edit ambulance records and emergency requests.
- Emergency requests are prioritised correctly, with FIFO order for equal severity.
- Dijkstra returns the shortest route and distance for connected locations.
- Automatic dispatch selects the nearest available ambulance by road distance.
- The system handles no-available-ambulance and unreachable-route cases without crashing.
- Ambulance and request statuses update correctly after assignment and completion.
- Dispatch history is saved and visible in the interface.
- The project has clear setup instructions in a README and is easy to run on a student's computer.

## 11. Implementation Guidance for Antigravity

Build the project in small, testable stages rather than generating everything as one large file:

1. Set up Flask, project structure, SQLite schema, and sample data.
2. Implement ambulance CRUD and emergency-request CRUD.
3. Implement and test the priority queue, graph, and Dijkstra modules independently.
4. Integrate automatic dispatch with database transactions and dispatch history.
5. Build the dashboard, tables, forms, validation, and status updates.
6. Test the complete workflow using the sample data and write a README with installation and run commands.

Keep business logic out of HTML templates. Use Flask routes for HTTP handling, separate modules for application operations, and separate files for DSA implementations. Add comments explaining the DSA logic because it is a key part of the college evaluation.

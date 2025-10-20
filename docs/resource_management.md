# Resource Management Guide

Managing resources effectively is key to project success. Our API helps you track and understand available resources for your construction projects.

## What is a Resource?

A resource can be anything required to complete a project task. This includes:

* **Crews:** Teams of workers (e.g., "Framing Crew 1", "Plumbing Team B").
* **Equipment:** Heavy machinery, tools, vehicles (e.g., "Crane 3", "Excavator 1").
* **Materials:** Specific building materials (though these are often managed as `cost-items` rather than `resources` in our system, depending on detail level).

## Listing Available Resources

To get a comprehensive list of all currently managed resources, make a `GET` request to the `/resources` endpoint.

This endpoint will return an array of resource objects, each containing:

* `resourceId`: Unique identifier for the resource.
* `resourceName`: Human-readable name (e.g., "Electrician Crew Alpha").
* `type`: The category of the resource (e.g., "Crew", "Equipment").
* `availability`: Current status (e.g., "Available", "Assigned to PROJ-XYZ").

**Example Response:**

```json
[
  {
    "resourceId": "RES-CRW-001",
    "resourceName": "Framing Crew 1",
    "type": "Crew",
    "availability": "Available"
  },
  {
    "resourceId": "RES-EQP-005",
    "resourceName": "Large Excavator",
    "type": "Equipment",
    "availability": "Assigned to PROJ-ABC"
  }
]
```

## Assigning Resources to Tasks

Resources are typically assigned when you create or update a schedule task using the `/projects/{projectId}/schedule-tasks` endpoint. The `assignedResource` field in the task payload should contain the `resourceName` or `resourceId`.

**Best Practice:** Before assigning a resource, check its availability using the `/resources` endpoint to avoid over-allocating.
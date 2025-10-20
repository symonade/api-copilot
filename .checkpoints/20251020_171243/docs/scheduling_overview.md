# Project Scheduling Overview

Effective project scheduling is crucial for on-time and on-budget delivery. Our API provides endpoints to manage tasks and allocate resources to a project timeline.

## Core Concepts

* **Tasks:** Discrete units of work with a defined `startDate` and `endDate`. Each task requires a `taskName` and can optionally be linked to an `assignedResource`.
* **Resources:** These are the entities that perform tasks, such as `Crews`, `Equipment`, or individual `Personnel`. Resources can be listed using the `/resources` endpoint.
* **Project ID:** All scheduling activities are linked to a specific `projectId`.

## How to Schedule a Task

To add a task to a project's schedule, use the `POST` method on the `/projects/{projectId}/schedule-tasks` endpoint.

**Required fields:**

* `taskName`: The name of the task (e.g., "Foundation Pour", "Steel Erection").
* `startDate`: The start date in `YYYY-MM-DD` format (e.g., "2024-07-20").
* `endDate`: The end date in `YYYY-MM-DD` format (e.g., "2024-07-25").

**Optional field:**

* `assignedResource`: The name or ID of the resource assigned to this task (e.g., "Crew A", "Crane 3").

**Example:**

```json
{
  "taskName": "HVAC Installation",
  "startDate": "2024-08-01",
  "endDate": "2024-08-15",
  "assignedResource": "HVAC Team Alpha"
}
```

## Listing Resources

Before assigning, you might want to see what resources are available. Use a `GET` request to the `/resources` endpoint to retrieve a list of all available construction resources.

## Common Schedule-Related Errors

* **404 Not Found:** If the `projectId` provided in the `/schedule-tasks` endpoint does not exist.
* **Date Format Errors:** Ensure dates are in `YYYY-MM-DD` format.
* **Resource Not Found:** While not enforced by the API, if `assignedResource` is provided, ensure it refers to a valid resource to avoid logical inconsistencies in your project plan.
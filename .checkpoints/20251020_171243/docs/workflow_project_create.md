# Workflow: Creating a Project and Adding Costs

This guide outlines the standard sequence for setting up a new project and associating initial costs.

## Step 1: Authenticate

Ensure you have a valid API Key and include it in the `X-API-Key` header for all subsequent requests (See auth.md).

## Step 2: Create the Project

Make a `POST` request to the `/projects` endpoint. Provide the `projectName` and `clientId` in the JSON body.

**Example Request Body:**
```json
{
  "projectName": "New Site Development",
  "clientId": "CUST-456"
}

The API will respond with a 201 Created status and return the new projectId. You will need this ID for the next step.

Example Response Body:
{
  "projectId": "PROJ-ABC123",
  "status": "Created"
}

Step 3: Add Cost Items
Using the projectId obtained from Step 2, make one or more POST requests to the /projects/{projectId}/cost-items endpoint. Replace {projectId} in the URL with the actual ID.

Provide the details of the cost item (material, labor, etc.) in the JSON body.

Example Request Body (for projectId PROJ-ABC123):

{
  "itemCode": "LAB-ELEC-01",
  "description": "Electrician Hourly Rate",
  "quantity": 40.0,
  "unitCost": 85.50
}

The API will respond with 201 Created for each successful cost item addition.

Common Issues
If you receive a 404 Not Found when adding cost items, double-check that the projectId in the URL is correct and matches the one returned in Step 2.

Ensure unitCost is provided as a number (e.g., 85.50), not a string ("85.50").
# Authentication Guide

All API requests must be authenticated using an API Key provided via the `X-API-Key` header.

## Obtaining a Key

API Keys can be generated from the Developer Portal under your account settings. Ensure you store your key securely.

## Making Authenticated Requests

Include the key in the header of every request:

```http
GET /projects HTTP/1.1
Host: api.example.com
X-API-Key: YOUR_SECRET_API_KEY

## Errors

- **401 Unauthorized:** Your API key is missing or invalid.
- **403 Forbidden:** Your API key is valid but does not have permission for the requested action (check scopes).
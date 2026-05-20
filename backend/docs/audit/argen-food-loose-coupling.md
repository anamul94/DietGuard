# Argen Food Loose Coupling Description

Argen Food separates the user-facing API layer, AI recommendation logic, notification flow, and persistence tier behind explicit service boundaries. The FastAPI backend exposes versioned REST contracts under `/v1` and treats downstream processing as independent services rather than shared in-process state.

The API backend communicates with the AI recommendation engine through an internal service boundary. If recommendation processing is slow or temporarily unavailable, the API layer can return a cached or static meal-plan response instead of failing the user-facing request. This keeps the customer API contract available while the recommendation tier recovers.

Push notifications are decoupled from the main request path through an asynchronous trigger. Notification delivery does not block the API response returned to the mobile app, so a notification delay or delivery failure does not cause the food upload or report workflow to fail.

The data tier is accessed through the database client abstraction and is intended to connect through RDS Proxy. Application components should not connect directly to the Aurora writer endpoint. RDS Proxy provides connection pooling and failover handling, reducing direct coupling between application instances and the database writer.

Infrastructure is independently deployable by tier using separate CloudFormation stacks and separate Auto Scaling Groups. The API compute tier, recommendation services, and database tier can be changed or scaled independently, which limits the blast radius of a change in one tier.


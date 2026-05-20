# Argen Food API Change Communication Process

Breaking API changes are flagged in the Git pull request description using a `BREAKING CHANGE` label or heading. The PR must describe the affected `/v1` endpoint, request or response contract changes, rollout plan, and any required mobile-app changes. Before merge, the consuming team, including the Argen Food mobile app engineers, is notified in the API change communication channel and given a minimum 5-day notice period before the breaking change is deployed to production. The change is not merged until affected service owners have reviewed and confirmed compatibility or migration readiness.


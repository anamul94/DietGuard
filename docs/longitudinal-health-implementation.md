# Longitudinal Health Implementation Tracker

This file captures the approved implementation direction for DietGuard's shift from single-event analysis to structured longitudinal health tracking.

## Phase 1 Focus

- [x] Save the approved implementation plan into the repository.
- [ ] Add structured report persistence and report versioning.
- [ ] Add meal draft and confirm flow before final nutrition persistence.
- [ ] Add vital ingestion for manual, CSV, and generic device sync.
- [ ] Add daily and weekly correlation summaries.
- [ ] Add analytics-oriented health profile endpoints.

## Approved Product Decisions

- V1 optimizes for core tracking before 7-day meal planning and mood/audio.
- Vitals support both manual entry and device sync, with CSV import for manual/upload cases.
- Food recognition must return a draft that the user can correct before nutrition is finalized.
- Audio belongs in a separate daily check-in flow, not inside the meal logging flow.
- Correlations must remain non-causal. Product language must say "may be associated with" and "possible contributing factors."

## Implementation Summary

1. Store raw medical report output and normalized structured fields together.
2. Persist confirmed meals as timeline events with item-level detail and macro totals.
3. Persist vitals as timestamped events from manual, CSV, or device-driven ingestion.
4. Generate daily and weekly summaries from a unified meal/vital/report timeline.
5. Introduce a LangGraph correlation workflow for evidence-based association summaries.

## Deferred

- Daily audio mood check-ins and transcription.
- 7-day meal plan generation and regeneration.
- Vendor-specific device integrations.
- Full dashboard frontend implementation.

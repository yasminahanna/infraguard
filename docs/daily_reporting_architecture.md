# Daily Reporting Architecture

## Goal

InfraGuard is intended to process city-scale CCTV traffic footage continuously and generate a daily road safety report.

The system is not primarily an on-demand recommendation tool.

The final product behavior is:

CCTV feeds  
→ sampled frame analysis  
→ event aggregation  
→ hotspot detection  
→ RAG-enhanced recommendation  
→ daily admin report  
→ dashboard map and summaries

## 24/7 CCTV Input

InfraGuard is designed for multiple CCTV cameras across city blocks.

The system should not process every video frame because that would be too expensive.

Instead, it should sample frames from each camera at fixed intervals.

Example sampling options:

- one frame every 5 seconds,
- one frame every 10 seconds,
- one short clip every minute,
- higher sampling during peak traffic hours.

## Detection Flow

For each sampled frame or short clip:

- Detection IEP decodes the frame.
- YOLO detects vehicles.
- CLIP classifies traffic-risk scene labels.
- The service outputs structured events.

Example events:

- unsafe proximity,
- high density,
- reckless driving,
- lane violation,
- phone usage possible,
- normal traffic.

## Event Storage

The production system should store structured outputs, not raw video by default.

Stored event data should include:

- camera ID,
- road segment ID,
- timestamp,
- location,
- event type,
- severity,
- confidence,
- model source,
- bounding box if available.

Raw images or video should only be stored if necessary for audit/debugging and should have a retention policy.

## Hotspot Aggregation

Every 24 hours, InfraGuard aggregates events by road segment.

The Hotspot IEP computes:

- total event count,
- event type distribution,
- average confidence,
- hotspot score,
- risk level,
- trend,
- cluster ID.

## Daily Recommendation Report

After hotspot aggregation, the Recommender IEP generates recommendations.

The recommender uses:

- detection summaries,
- hotspot scores,
- road metadata,
- retrieved web context if enabled,
- local project context if available.

The final output is a daily report for admins.

## Admin Dashboard Behavior

The dashboard should show the latest daily report.

Main dashboard views:

- city map,
- hotspot markers,
- road segment risk levels,
- selected hotspot details,
- recommendations,
- retrieved RAG context,
- system status.

The dashboard should not require admins to manually trigger every analysis.

A manual “Run sample analysis” button may exist only for demo/testing.

## Current Project Implementation

Current implementation includes:

- EEP Gateway,
- Detection IEP,
- Hotspot IEP,
- Recommender IEP,
- real YOLO + CLIP detection,
- `/v1/analyze` test endpoint,
- integration tests,
- observability stack.

The `/v1/analyze` endpoint is currently used to test the pipeline on one sample request.

## Planned Implementation

Next planned additions:

- daily report sample data,
- dashboard UI,
- map with hotspot markers,
- report display page,
- scheduled daily report generation,
- persistent storage for event summaries and reports.

## Privacy and Cost Notes

For city-scale 24/7 CCTV, InfraGuard should:

- sample frames instead of processing every frame,
- store structured events instead of raw video,
- avoid storing personally identifying information,
- blur or avoid faces/license plates where possible,
- limit raw media retention,
- monitor inference cost.
# Dataset Plan

## Purpose

InfraGuard requires real or public datasets for two major parts:

1. Computer vision and traffic behavior detection.
2. Classifier fallback or validation for hotspot and recommendation support.

Synthetic training labels will not be used for the final classifier fallback.

## Candidate Data Types

### Traffic Video or Vehicle Trajectory Data

Useful for:

- vehicle detection,
- unsafe proximity,
- lane behavior,
- trajectory analysis,
- speed proxy estimation.

Possible dataset types:

- drone vehicle trajectory datasets,
- roadside traffic camera datasets,
- vehicle detection datasets,
- traffic violation datasets.

### Crash or Incident Open Data

Useful for:

- hotspot modeling,
- severity classification,
- risk scoring validation.

Possible dataset types:

- public city crash records,
- national accident datasets,
- open road safety records.

### Intervention Labels

Real intervention labels are difficult to obtain publicly.

If direct intervention labels are unavailable, the fallback classifier will predict an intermediate label such as:

- risk class,
- violation type,
- hotspot severity,
- incident severity.

The LLM will then use that structured prediction with hotspot evidence to generate the final intervention recommendation.

## Dataset Selection Criteria

The chosen dataset should have:

- public access or clear academic use permission,
- enough examples for validation,
- documented fields,
- relevant traffic or road safety meaning,
- possible mapping to InfraGuard features.

## Planned Documentation

For every dataset used, document:

- source,
- license or usage terms,
- fields used,
- preprocessing steps,
- limitations,
- known biases,
- how it supports the project goal.

## Minimum Acceptable Dataset Plan

InfraGuard should include at least one dataset for model or evaluation work.

Possible acceptable dataset uses:

- traffic video for detection validation,
- vehicle trajectory data for unsafe proximity or speed proxy validation,
- crash records for hotspot validation,
- traffic incident records for risk classification.

## Important Limitation

The final project must be honest about dataset limitations.

If the dataset does not directly contain infrastructure intervention labels, the system must not claim that the classifier learned true intervention recommendations. Instead, it should claim that the classifier predicts an intermediate risk or incident class, which the LLM uses as supporting evidence.
# Fine-Tuning Plan

## Purpose

Fine-tuning is a future enhancement for the Recommender IEP.

The goal is not to teach the model new traffic laws or current local facts. Those should come from RAG.

The goal of fine-tuning is to teach the model InfraGuard's preferred recommendation behavior.

## What Fine-Tuning Should Improve

Fine-tuning may help with:

- consistent JSON output,
- better intervention ranking,
- clearer evidence-based explanations,
- better uncertainty wording,
- avoiding unsupported legal claims,
- consistent priority levels,
- consistent confidence scores.

## What Fine-Tuning Should Not Replace

Fine-tuning should not replace:

- web RAG,
- source retrieval,
- local laws or regulations,
- hotspot scoring,
- detection evidence,
- validation with Pydantic.

## Final Recommender Design

The intended final design is:

Detection evidence  
→ Hotspot evidence  
→ Web RAG context  
→ Fine-tuned or base LLM  
→ Pydantic validation  
→ Final recommendation

## Training Data Format

Each training example should contain:

Input:

- detection summary,
- hotspot summary,
- road metadata,
- retrieved context.

Output:

- primary intervention,
- priority,
- supporting actions,
- explanation,
- evidence used,
- confidence.

## Minimum Data Requirement

Fine-tuning should only be attempted after collecting enough high-quality examples.

Target:

- minimum: 30 examples,
- preferred: 50 or more examples.

The examples should be manually reviewed.

## Evaluation Before Fine-Tuning

Before fine-tuning, InfraGuard should have a golden evaluation set.

The evaluation set should test:

- valid JSON,
- allowed intervention values,
- correct use of evidence,
- no invented laws,
- reasonable priority,
- explanation quality,
- confidence range.

## Promotion Criteria

A fine-tuned model should only replace the base model if it improves:

- schema validity,
- recommendation consistency,
- evidence grounding,
- latency or cost if relevant,
- golden evaluation score.

## Rollback Criteria

Rollback if:

- JSON validation failures increase,
- unsupported claims increase,
- recommendations become less accurate,
- the model ignores retrieved context,
- latency or cost becomes unacceptable.
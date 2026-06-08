# Cost Estimate

## Cost Drivers

InfraGuard cost depends on:

- number of API requests,
- number of frames per request,
- computer vision inference cost,
- LLM recommendation calls,
- cloud container runtime,
- monitoring stack,
- storage for logs and metrics.

## Local Development Cost

Local Docker Compose development has no direct cloud cost.

## Cloud Runtime Cost

Expected services:

- EEP Gateway container,
- Detection IEP container,
- Hotspot IEP container,
- Recommender IEP container,
- Prometheus or managed metrics,
- Grafana or managed dashboard.

Small demo deployment estimate:

- low CPU containers,
- minimal memory,
- low traffic,
- expected cost depends on provider free tier and usage.

## LLM Cost

The LLM recommender is a variable cost.

Cost drivers:

- prompt length,
- response length,
- number of requests,
- model choice.

Cost reduction strategies:

- keep prompt compact,
- send structured summaries instead of raw frames,
- use caching for repeated scenarios,
- use classifier fallback for non-critical cases,
- use lower-cost model for demo.

## Computer Vision Cost

Current placeholder detection has minimal cost.

Future YOLO or OpenCV detection cost depends on:

- frame count,
- image resolution,
- CPU vs GPU inference,
- model size.

Cost reduction strategies:

- frame sampling,
- image resizing,
- lightweight detector,
- batch size limits.

## Monitoring Cost

Prometheus and Grafana can run locally or in containers.

Cloud cost depends on:

- retention period,
- scrape frequency,
- managed vs self-hosted monitoring.

## Estimated Demo Budget

For a short-lived demo deployment:

- expected low cloud cost if containers are small and traffic is limited,
- LLM cost should remain low because demo requests are few,
- monitoring can be local or low-retention.

Final exact numbers will be added after choosing the cloud provider.

## Cost Risks

Main cost risks:

- running large computer vision models continuously,
- using high-cost LLM models,
- storing raw video,
- high monitoring retention,
- leaving cloud services running after the demo.

## Cost Controls

Planned controls:

- frame limit per request,
- API key protection,
- low-cost model selection,
- no raw video retention by default,
- short monitoring retention for demo,
- shutdown script or manual shutdown checklist after presentation.

---

# Scaling Cost Estimate (Pilot → District → Full City)

This section turns the qualitative drivers above into **order-of-magnitude monthly
figures** for three deployment tiers, comparing **periodic sampling** against
**near-real-time** detection. These are planning estimates from Azure pay-as-you-go
list prices, not quotes — confirm against the Azure pricing calculator, and expect
**−30% to −60%** with 1-year reserved / spot capacity.

## Assumptions

- **Detection model:** YOLOv8n + CLIP zero-shot (the deployed stack).
- **Effective throughput:** ≈ **25 analyzed frames/sec per NVIDIA T4 GPU** (includes
  video decode + CLIP); ≈ **10 fps per 4-vCPU** on CPU-only.
- **Periodic mode:** 1 analyzed frame every 4 s per camera = **0.25 fps/camera**
  (matches the current stream-ingestor design — enough to catch `high_density` /
  `unsafe_proximity` events, which are the reliable single-frame triggers).
- **Near-real-time mode:** **5 fps/camera** (sufficient for traffic events; not full
  25–30 fps).
- **LLM (gpt-4o-mini):** 1 daily city report + 1 recommendation per road segment/day;
  ~1 segment per camera. ≈ $0.0006 per recommendation, ≈ $0.0014 per report.
- **Storage:** **event clips + sampled frames only — no raw 24/7 video.** ≈ 3 GB per
  camera per month at 30-day retention (Azure Blob hot ≈ $0.018/GB-mo). Inbound
  camera bandwidth to Azure is free; decode cost is folded into compute.
- **Reference prices:** T4 GPU VM (NC4as_T4_v3) ≈ **$385/mo**; general CPU VM
  (D4_v4, 4 vCPU/16 GB) ≈ **$140/mo**; 730 hrs/mo.

## Step 1 — Frame load and GPU fleet

| Tier | Cameras | Periodic load | Real-time load | GPUs (periodic) | GPUs (real-time) |
|------|---------|---------------|----------------|-----------------|------------------|
| Pilot | 25 | 6.25 fps | 125 fps | CPU (1 VM) or <1 GPU | 5× T4 |
| District | 250 | 62.5 fps | 1,250 fps | 3× T4 | 50× T4 |
| Full city | 2,500 | 625 fps | 12,500 fps | 25× T4 | 500× T4 |

> GPU count = ⌈load ÷ 25 fps⌉. Pilot-periodic fits on **CPU** (6.25 fps < ~10 fps on a
> D4), so no GPU is needed at the smallest tier.

## Step 2 — Detection compute cost (the dominant driver)

| Tier | Periodic compute | Real-time compute |
|------|------------------|-------------------|
| Pilot (25) | ~$140/mo (1 CPU VM) | ~$1,925/mo (5× T4) |
| District (250) | ~$1,155/mo (3× T4) | ~$19,250/mo (50× T4) |
| Full city (2,500) | ~$9,625/mo (25× T4) | ~$192,500/mo (500× T4) |

**Real-time costs ~5–17× more than periodic**, and full-city real-time (~$192k/mo ≈
$2.3M/yr) is the headline cost risk. Periodic sampling with **event-triggered bursts**
(temporarily raise fps only on a camera that just flagged an event) captures the safety
value at a fraction of the cost.

## Step 3 — Everything else (shared, per tier)

| Component | Pilot (25) | District (250) | Full city (2,500) |
|-----------|-----------|----------------|-------------------|
| Orchestration (EEP/Hotspot/Recommender) | ~$70 | ~$280 | ~$1,000 (AKS + nodes) |
| Blob storage (event clips, 30-day) | ~$1 | ~$14 | ~$140 |
| LLM reports + recommendations (daily) | ~$0.5 | ~$4.5 | ~$45 |
| Monitoring (Prometheus/Grafana) | ~$0 (co-located) | ~$140 | ~$400 |
| Auth + state DB (Supabase / managed PG) | ~$0–25 | ~$100 | ~$300 |
| **Subtotal (non-detection)** | **~$95–120** | **~$540** | **~$1,885** |
| RAG web search (Tavily, optional) | ~$3 | ~$30 | ~$300 |

> At scale the JSONL report/feedback store is replaced by **managed Postgres**, and the
> single VM by **AKS with a GPU node pool**; those shifts are captured in the
> orchestration/DB lines.

## Step 4 — Total monthly cost

| Tier | **Periodic (recommended)** | **Near-real-time** |
|------|----------------------------|--------------------|
| Pilot (25 cams) | **~$210/mo** | ~$2,000/mo |
| District (250 cams) | **~$1,700/mo** | ~$19,800/mo |
| Full city (2,500 cams) | **~$11,500/mo** | ~$193,000/mo |

**Per-camera unit cost (periodic):** Pilot ≈ $8.4 → District ≈ $6.8 → Full city ≈ $4.6
per camera/month — clear **economies of scale** as fixed platform cost amortizes.
(Add ~$0.12/cam for optional RAG.)

## Step 5 — Cost-reduction levers at scale

1. **Periodic + event-triggered bursts**, not blanket real-time — the single biggest lever.
2. **Reserved (1-yr) or spot GPUs** — −30% to −60% on the dominant compute line.
3. **YOLO-first, CLIP-on-demand** — run the cheap detector on every frame and the heavier
   CLIP classifier only on ambiguous/flagged frames (~10× fewer CLIP calls).
4. **Quantized / smaller CLIP** (ViT-B/32 INT8) and **batched inference** to lift fps/GPU.
5. **Blob lifecycle tiering** (hot → cool → archive) and short retention for non-event clips.
6. **Cache RAG results** and call Tavily only for new high-risk hotspots, not every segment.
7. **Keep daily-batch LLM reporting** (cheap) instead of per-event LLM calls.

## Bottom line

LLM and storage are **negligible** at every tier (< 1% of cost at full city); the estimate
is **entirely a detection-compute story**. Running **periodic sampling** keeps even a
2,500-camera citywide deployment around **~$11.5k/mo** (~$4.6/camera), whereas blanket
near-real-time inference is ~17× higher and is the main thing to engineer around.
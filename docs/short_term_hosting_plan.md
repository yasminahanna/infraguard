# Short-Term Hosting Plan

## Goal

InfraGuard must remain hosted and available during the grading and demonstration period.

If the project would be used outside the scope
of the course, then the users would have to pay
subscription only to keep it running 

## Hosting Requirement

The hosted system should include:

- EEP Gateway
- Detection IEP
- Hotspot IEP
- Recommender IEP
- Admin dashboard
- Public EEP URL
- Admin-only dashboard URL

## Preferred Hosting Option

Preferred option:

- Azure for Students

Reason:

- student credit can cover short-term deployment,
- no credit card required for eligible students,
- supports containers and static web hosting,
- suitable for a short-term hosted demo.

## Backup Hosting Option

Backup option:

- Google Cloud Run

Reason:

- supports containerized services,
- has free tier and new-user credits,
- can scale container services,
- suitable if Azure setup is blocked.

## Cost Control

Controls:

- keep replicas at 1,
- expose only EEP and admin dashboard publicly,
- use small CPU and memory where possible,
- keep Prometheus/Grafana local unless cloud resources allow,
- set billing alerts,
- shut down services immediately after grading,
- avoid storing raw video,
- limit requests during demo.

## Expected Hosted Architecture

Admin Dashboard  
→ EEP Gateway  
→ Detection IEP  
→ Hotspot IEP  
→ Recommender IEP

Only the dashboard and EEP should be public.

Internal services should be private or protected.

## Short-Term Availability Plan

Before grading:

- deploy all services,
- verify `/health`,
- run hosted E2E test,
- verify admin dashboard login,
- verify map and recommendation display.

During grading:

- keep services running,
- monitor logs and cost,
- avoid unnecessary heavy image requests.

After grading:

- export screenshots/logs,
- shut down compute services,
- keep repository and documentation available.

## Risk

The Detection IEP is the heaviest service because it uses YOLO and CLIP.

If the full detection service is too slow or expensive, use a smaller CPU/memory configuration only if it still passes the hosted E2E test.

Do not silently replace AI detection with fake logic in the final demo.
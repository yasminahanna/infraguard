# Azure VM Deployment Runbook (InfraGuard)

Target: **single Azure for Students Linux VM** running the full stack via
`docker-compose.prod.yml`. Only the **EEP (8000)** and the **dashboard (80)** are public;
all IEPs and Prometheus/Grafana stay internal on `infraguard-net`.

> Run the `az ...` commands from **your Windows terminal**; run the `sudo ...`/`docker ...`
> commands **on the VM over SSH**. Claude does not run git or cloud commands — execute these
> yourself.

---

## 0. Prerequisites
- Azure for Students account active (you have this).
- The repo reachable from the VM (`github.com/yasminahanna/infraguard`).
- Real values ready: `OPENAI_API_KEY`, Supabase URL + anon key + admin email.

---

## 1. Install Azure CLI (Windows)
```powershell
winget install --exact --id Microsoft.AzureCLI
# close & reopen the terminal, then:
az version
az login          # opens browser; pick your student account
az account show   # confirm the right subscription
```

## 2. Create resource group + VM
```powershell
# variables (edit region if you prefer)
$RG="infraguard-rg"
$LOC="francecentral"          # pick a region close to you
$VM="infraguard-vm"

az group create -n $RG -l $LOC

# Ubuntu 22.04, 4 vCPU / 16 GB (B4ms). YOLO+CLIP need headroom; B2ms (8 GB) is the
# bare minimum and may struggle building/running detection. 64 GB disk for image sizes.
az vm create `
  -g $RG -n $VM `
  --image Ubuntu2204 `
  --size Standard_B4ms `
  --os-disk-size-gb 64 `
  --admin-username azureuser `
  --generate-ssh-keys

# capture the public IP
$IP=$(az vm show -d -g $RG -n $VM --query publicIps -o tsv)
echo "VM public IP: $IP"
```

## 3. Open ONLY the required ports
```powershell
# Dashboard (HTTP 80) and EEP API (8000) — public
az vm open-port -g $RG -n $VM --port 80   --priority 1001
az vm open-port -g $RG -n $VM --port 8000 --priority 1002
```
- SSH (22) is opened by default. **Do NOT open 8001/8002/8003/9090/3000.**
- Recommended hardening: restrict SSH to your IP via the NSG rule (Azure Portal →
  VM → Networking → SSH rule → Source = My IP).

## 4. SSH in and install Docker
```powershell
ssh azureuser@$IP
```
On the VM:
```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker          # or log out/in so docker works without sudo
docker compose version
```

## 5. Clone, configure, and launch
On the VM:
```bash
git clone https://github.com/yasminahanna/infraguard.git
cd infraguard
git checkout deploy/azure-vm          # the deployment branch

cp .env.prod.example .env
nano .env
#   API_KEY            -> long random value (this is DEPLOYED_API_KEY)
#   PUBLIC_EEP_URL     -> http://<VM_PUBLIC_IP>:8000
#   FRONTEND_ORIGINS   -> http://<VM_PUBLIC_IP>
#   OPENAI_API_KEY     -> real key
#   SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_ADMIN_EMAILS -> real values

# Build + start. Detection (YOLO+CLIP) is the slow step — first build can take a while.
docker compose -f docker-compose.prod.yml --env-file .env up -d --build

# watch progress / health
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f eep-gateway
```
> If the VM runs out of memory during build, start without observability:
> `... up -d --build eep-gateway detection-iep hotspot-iep recommender-iep frontend`

## 6. Supabase: allow the public origin
In the Supabase dashboard → Authentication → URL Configuration, add the dashboard origin
`http://<VM_PUBLIC_IP>` to the allowed redirect/site URLs so admin login works from the cloud.

## 7. Smoke test (from your Windows terminal)
```powershell
curl.exe http://$IP:8000/health
# analyze (real orchestration through all 3 IEPs)
curl.exe -X POST "http://$IP:8000/v1/analyze" -H "X-API-Key: <API_KEY>" -H "Content-Type: application/json" --data "@samples\real_analyze_request.json"
```
Confirm the IEP ports are **not** reachable publicly (should hang/refuse):
```powershell
curl.exe --max-time 5 http://$IP:8001/health   # expect failure — good
```

## 8. Run the hosted E2E test (closes gate GT2) — from local repo
```powershell
$env:DEPLOYED_EEP_URL="http://$IP:8000"
$env:DEPLOYED_API_KEY="<API_KEY>"
pytest tests\e2e
```
Expect `test_deployed_eep_analyze_endpoint` to PASS (no longer skipped):
`status=completed`, `detection/hotspot/recommender` services all present.

## 9. Generate a real report + verify the dashboard
```powershell
# trigger a report on the (internal) recommender via the VM, then read through the public EEP:
ssh azureuser@$IP "curl -s -X POST http://localhost:8000/v1/reports/generate || curl -s -X POST http://recommender-iep:8003/v1/reports/generate"
curl.exe http://$IP:8000/v1/reports/latest
```
Open `http://<VM_PUBLIC_IP>` in a browser → log in (admin email) → map + hotspots + LLM report.

---

## Cost control & teardown
- **Deallocate when not demoing** (stops compute billing; keeps the VM/disk):
  ```powershell
  az vm deallocate -g infraguard-rg -n infraguard-vm
  az vm start      -g infraguard-rg -n infraguard-vm   # bring back up
  ```
- Set a billing alert in Cost Management.
- **After grading**, delete everything:
  ```powershell
  az group delete -n infraguard-rg --yes --no-wait
  ```

## Deliverable evidence to capture (for the report / rubric)
- Public EEP URL + a successful `/v1/analyze` response.
- Passing `pytest tests\e2e` output.
- Dashboard screenshot (map + generated report).
- Architecture note: only EEP + dashboard public; IEPs internal.
- Cost estimate + teardown command (above).

---

## Rollback (matches docs/deployment.md)
- Keep the previous working image; `git checkout <last-good>` + rebuild if a deploy breaks.
- `docker compose -f docker-compose.prod.yml down` then re-up the prior commit.
- Tag the last stable commit so it's identifiable.

## Notes / risks
- The VM is CPU-only, so detection builds torch the **standard** way and runs YOLO/CLIP on
  CPU (code already falls back to CPU). First build is the slow/heavy step — budget for it.
  The local CPU-only build shortcut stays **out of the repo** and is not used here.
- Optional speedup if VM builds are too slow: build images locally, push to Azure Container
  Registry / Docker Hub, and `pull` on the VM instead of `--build`.

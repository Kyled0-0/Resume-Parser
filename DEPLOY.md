# Deployment Guide

Manual GCP Console steps to wire up the full pipeline:
**push to GitHub `main`** → Cloud Build builds image → push to Artifact Registry → deploy to GKE.

Do these once, in order. After they're set up, every push to `main` triggers a deployment automatically.

---

## Prerequisites

- Google Cloud project with billing enabled (free tier works)
- GitHub account, with this repo pushed to GitHub
- A Gemini API key from [`aistudio.google.com`](https://aistudio.google.com/app/apikey)

Throughout this guide, replace:
- `PROJECT_ID` with your GCP project ID
- `REGION` with your chosen region (e.g. `australia-southeast1`)

---

## 1. Enable APIs

Console → **APIs & Services → Library**. Enable:
- Artifact Registry API
- Kubernetes Engine API
- Cloud Build API

---

## 2. Create the Artifact Registry repository

1. Console → **Artifact Registry → Repositories** → **Create Repository**
2. Name: `resume-parser-repo`
3. Format: **Docker**
4. Region: same as future GKE cluster
5. Click **Create**

📸 *Screenshot the repository list for submission evidence.*

---

## 3. Provision the GKE Autopilot cluster

1. Console → **Kubernetes Engine → Clusters** → **Create**
2. Choose **Autopilot**
3. Name: `resume-parser-cluster`
4. Region: same as Artifact Registry
5. Leave defaults, **Create**
6. Wait ~5–10 minutes for provisioning to turn green

📸 *Screenshot the cluster list once status is healthy.*

---

## 4. Create the API key Secret in the cluster

1. Console → **Kubernetes Engine → Configuration & Secrets** → **Create → Secret**
2. Name: `resume-parser-secrets`
3. Namespace: `default`
4. Type: `Opaque`
5. Add key-value pair:
   - Key: `GEMINI_API_KEY`
   - Value: `<your real Gemini key>`
6. **Create**

📸 *Screenshot the secret list (value is hidden after creation).*

---

## 5. Push this repo to GitHub

If you haven't already:

```bash
# In the repo root (not in a worktree)
gh repo create resume-parser --public --source=. --push
# Or use the GitHub UI to create the repo, then:
git remote add origin https://github.com/<you>/resume-parser.git
git push -u origin main
```

The `.gitignore` already excludes `CLAUDE.md`, `docs/`, `.env`, `.venv/`, `.worktrees/` — secrets and operational files won't go to GitHub.

---

## 6. Connect GitHub to Cloud Build

1. Console → **Cloud Build → Triggers** → **Connect Repository**
2. Source: **GitHub (Cloud Build GitHub App)**
3. Authenticate, select the `resume-parser` repo
4. Click **Connect**

---

## 7. Create the Cloud Build trigger

1. Console → **Cloud Build → Triggers** → **Create Trigger**
2. Name: `resume-parser-main`
3. Event: **Push to a branch**
4. Source: the GitHub repo you connected
5. Branch: `^main$`
6. Configuration: **Cloud Build configuration file**, location `/cloudbuild.yaml`
7. Substitution variables (click **Add Variable** for each):

| Variable | Value |
|---|---|
| `_REGION` | `australia-southeast1` (or your region) |
| `_REPO` | `resume-parser-repo` |
| `_CLUSTER` | `resume-parser-cluster` |
| `_IMAGE_NAME` | `resume-parser` |

8. Click **Create**

---

## 8. Grant IAM roles to the Cloud Build service account

Cloud Build runs as `<PROJECT_NUMBER>@cloudbuild.gserviceaccount.com`. It needs:

1. Console → **IAM & Admin → IAM**
2. Find the Cloud Build service account
3. **Edit** → add roles:
   - `Artifact Registry Writer` — to push images
   - `Kubernetes Engine Developer` — to deploy
   - `Cloud Build Service Account` (already present)

If your project's IAM is restricted (Deakin policies often block this), the build and push steps still work — only the `deploy` step in `cloudbuild.yaml` will fail. Capture the build log for submission evidence and proceed with manual deploy.

---

## 9. First deploy — manual (one time)

Before the first auto-deploy, do a manual deployment to bootstrap the cluster:

1. Trigger one Cloud Build run manually: **Cloud Build → Triggers → Run** on `resume-parser-main`. This pushes the first image to Artifact Registry.
2. Console → **Kubernetes Engine → Workloads → Deploy**
3. **Existing container image** → enter the full image path:
   `REGION-docker.pkg.dev/PROJECT_ID/resume-parser-repo/resume-parser:v1`
4. **Edit YAML** → paste the contents of `k8s/deployment.yaml`, replacing `PLACEHOLDER_IMAGE` with the path above
5. **Deploy**, wait 1–2 min for the rollout
6. From the Workloads list → click the deployment → **Actions → Expose**
7. Service type: `Load balancer`. Port: 80. Target port: 8000. **Expose**
8. Wait 1–2 min for an external IP to appear in **Services & Ingress**

📸 *Screenshot Workloads (healthy), Services & Ingress (external IP), and the Swagger UI loaded from that IP showing a successful parse — these three are your strongest deployment evidence.*

---

## 10. Verify

```bash
curl http://<EXTERNAL-IP>/health
# {"status": "ok"}
```

Open `http://<EXTERNAL-IP>/` in a browser — the resume parser UI loads. Open `http://<EXTERNAL-IP>/docs` for Swagger.

---

## How auto-deploy works after setup

```
git push origin main
   │
   ▼
GitHub webhook fires
   │
   ▼
Cloud Build trigger picks up the push
   │
   ▼
Runs cloudbuild.yaml:
   1. docker build → tags ${SHORT_SHA} and v1
   2. docker push  → Artifact Registry
   3. gke-deploy   → updates the Deployment to ${SHORT_SHA}
   │
   ▼
GKE rolls pods to the new SHA-tagged image
```

If step 3 fails on IAM (Deakin restrictions), the image still lands in Artifact Registry and you can update the Deployment manually via Console → Workloads → Edit → bump the image tag.

---

## Troubleshooting

| Symptom | Where to look | Fix |
|---|---|---|
| Build step 1 fails | Cloud Build logs | Run `docker build .` locally first |
| Push step fails with permission denied | IAM | Grant Cloud Build SA the `Artifact Registry Writer` role |
| Deploy step fails with permission denied | IAM | Grant Cloud Build SA the `Kubernetes Engine Developer` role |
| Pod stuck in `ImagePullBackOff` | Workloads → Events tab | Image path wrong, or registry creds missing |
| Pod stuck in `CreateContainerConfigError` | Workloads → Events tab | Secret `resume-parser-secrets` not applied; see step 4 |
| Pod CrashLoopBackOff | Workloads → Logs tab | Likely missing `GEMINI_API_KEY`; verify secret keys |
| `/parse` returns 502 with `ResourceExhausted` | Pod logs | Daily Gemini quota hit; change `GEMINI_MODEL` env var to a different model and roll the deployment |
| LoadBalancer IP `<pending>` | Services & Ingress | Region quota issue; switch to `NodePort` + `kubectl port-forward` for demo |

---

## Image tagging

The pipeline produces two tags per build:
- `${SHORT_SHA}` — unique per commit, what the deployment uses
- `v1` — stable pointer to the latest deployed version

Avoid `latest`. K8s treats unchanged tags as no-op rollouts.

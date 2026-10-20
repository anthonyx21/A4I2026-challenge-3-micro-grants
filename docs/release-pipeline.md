# Release deployment pipeline

Push to the GitHub branch **`release`** to deploy ReliefIQ. The workflow is [.github/workflows/release.yml](../.github/workflows/release.yml).

## What runs

1. Run backend/chat tests and all agent tests, then check UI JavaScript and deployment shell syntax.
2. Authenticate through GitHub OIDC and Google Workload Identity Federation, impersonating `reliefiq-release`. No service-account JSON key is stored in GitHub.
3. Build backend and agent Docker images from the release commit and push them to `us-central1-docker.pkg.dev/qwiklabs-gcp-04-029c15637557/reliefiq-release`.
4. Deploy tagged candidate revisions of `cascade-analyst` and `reliefiq-backend` without moving production traffic.
5. Check agent discovery/MCP readiness and backend PostgreSQL connectivity through candidate health endpoints.
6. Promote the agent revision, then the backend revision, to 100% traffic. GitHub Actions records logs and a deployment summary.

Releases run serially; an in-progress deployment is not cancelled by a later push. Manual runs are permitted only against the `release` branch. Failed tests, builds or candidate checks block traffic promotion. Promotion of two services is sequential, not atomic; if promotion partially fails, inspect the run and retry or restore the previous revisions.

The pipeline does not reload BigQuery or overwrite application records. Schema changes follow the backend's versioned schema logic; future migrations must remain compatible with the previous serving revision while candidate checks run. Database rollback is not automatic.

## Cloud identity

- Workload identity pool: `reliefiq-github`, global.
- OIDC provider: `github`, issuer `https://token.actions.githubusercontent.com`.
- Trust condition: GitHub repository ID `1427066686`, owner ID `7660271`, and ref `refs/heads/release`.
- Deployment service account: `reliefiq-release@qwiklabs-gcp-04-029c15637557.iam.gserviceaccount.com`.
- Access: Cloud Run Developer on the two submission services; Service Account User on their runtime identities; Artifact Registry Writer on the release image repository.
- GitHub repository variables: `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT`.

One-time administrator setup is preserved in [scripts/configure_release_identity.sh](../scripts/configure_release_identity.sh). Runtime database and reviewer secrets remain in Secret Manager; GitHub does not receive them.

## Publish and inspect

Merge the desired changes into `release` and push that branch. Inspect **GitHub → Actions → Deploy ReliefIQ release**. Serving URLs remain:

- https://reliefiq-backend-89073885580.us-central1.run.app
- https://cascade-analyst-89073885580.us-central1.run.app

Use [scripts/deploy_release.sh](../scripts/deploy_release.sh) for the implementation details. Release image tags and Cloud Run revision suffixes contain the Git commit SHA.

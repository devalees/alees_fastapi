# Deployment Strategy and CI/CD Pipeline (FastAPI Edition)

## 1. Overview

- **Purpose**: To define the strategy and automated processes for reliably building, testing, and deploying the FastAPI-based ERP backend application to various environments (e.g., Staging, Production).
- **Scope**: Covers Continuous Integration (CI) practices, Continuous Deployment/Delivery (CD) pipeline stages, target deployment infrastructure considerations, branching strategy, and rollback procedures.
- **Goals**: Automated testing, consistent builds via containerization, reliable and zero-downtime (or minimal downtime) deployments, reduced manual intervention, faster feedback cycles, and safe production releases.

## 2. Core Principles

- **Automate Everything Possible**: Automate testing, building, packaging, and deployment steps.
- **Infrastructure as Code (IaC):** Manage supporting infrastructure (servers, databases, load balancers, Kubernetes clusters, monitoring setup) using code (e.g., Terraform, AWS CloudFormation, Azure Resource Manager, Google Cloud Deployment Manager, Ansible).
- **Immutable Infrastructure (via Containers):** Deployments will primarily use Docker containers. New versions involve deploying new container images rather than updating existing servers in-place, reducing configuration drift.
- **Environment Parity**: Staging environment must mirror Production as closely as possible in terms of infrastructure, configuration structure, and data structure (though not necessarily data volume).
- **Monitoring & Feedback**: Integrate monitoring and alerting into the deployment process to quickly detect and respond to issues post-deployment.
- **Security Integrated (DevSecOps)**: Embed security checks (SAST, dependency scanning, container scanning) into the CI/CD pipeline.
- **Rollback Capability**: Have defined and tested procedures to quickly revert to a previous stable version in case of critical deployment failures.
- **Zero (or Minimal) Downtime Deployments**: Employ strategies like rolling updates, blue-green, or canary deployments for production releases.

## 3. Version Control & Branching Strategy

- **Version Control System:** **Git**. Hosted on a platform like GitHub, GitLab, or Bitbucket.
- **Branching Model (Gitflow Variation - Recommended):**
  - `main`: Represents the latest stable production code. Deployments to production are tagged releases from this branch (or a `release` branch). Merges only from `release/*` or `hotfix/*` branches.
  - `develop`: Represents the current state of development, integrating completed features. This is the target for feature branches and the source for release branches. CI runs comprehensively on this branch. Automatic deployments to a "Development" or "Integration" environment can occur from here.
  - `feature/<feature-name>` or `feat/<issue-id>-<short-description>`: Branched from `develop`. Developers work on features here. Pull/Merge Requests (PRs/MRs) are created from feature branches back into `develop`. CI runs on PRs/MRs.
  - `release/<version-number>` (e.g., `release/v1.2.0`): Branched from `develop` when preparing for a Staging/Production release. Only bug fixes and documentation updates allowed here. Used for final testing in Staging. Merged into `main` (and tagged) and back into `develop` upon successful release.
  - `hotfix/<issue-id>` or `fix/<version>-<short-description>`: Branched from `main` (or a production tag) to fix critical production bugs. Merged back into both `main` (tagged) and `develop` (and any active `release` branches).

## 4. Continuous Integration (CI) Pipeline

- **Trigger:** On every push to any branch, and especially on Pull/Merge Requests targeting `develop` or `main`/`release`.
- **Tool:** Chosen CI/CD platform (e.g., GitHub Actions, GitLab CI, Jenkins, CircleCI, Azure DevOps).
- **Key Stages:**
  1.  **Checkout Code:** Get the latest code from the relevant branch.
  2.  **Setup Environment:**
      - Set up the correct Python version (as defined in project, e.g., via `.python-version` or Dockerfile).
      - Install dependencies using `pip install -r requirements/dev.txt` (which includes `base.txt` and `test.txt`).
      - Set up necessary services if needed for tests not using mocks (e.g., PostgreSQL, Redis via Docker services within the CI runner).
  3.  **Linting & Code Formatting:**
      - Run linters (e.g., **Ruff** or Flake8 + plugins) and formatters (**Black**, isort via Ruff or standalone).
      - Fail build if checks fail.
  4.  **Static Analysis (SAST):**
      - Run **Bandit** to check for common Python security vulnerabilities.
      - Fail build on high-severity issues or based on configured policy.
  5.  **Type Checking (if using MyPy):**
      - Run `mypy .` to perform static type checking. Fail build on errors.
  6.  **Dependency Scanning:**
      - Run vulnerability scans on `requirements/*.txt` files (e.g., using **`pip-audit`**, Snyk, Trivy fs scan on requirements).
      - Fail build on critical/high vulnerabilities without approved exceptions.
  7.  **Run Tests (Pytest):**
      - Execute the full test suite: `pytest --cov=app --cov-report=xml --cov-report=term-missing` (or similar).
      - Requires access to a test database (PostgreSQL) and test Redis instance, typically provided as services in the CI environment.
      - Environment variables for test configuration will be set (e.g., `ENVIRONMENT=test`).
  8.  **Build Docker Image:**
      - Build the production Docker image using the project's `Dockerfile`.
      - The `Dockerfile` will install dependencies from `requirements/prod.txt` (which includes `base.txt`).
      - Tag the image with the Git commit SHA, branch name (for non-main/release branches), and potentially a version tag for releases.
  9.  **Scan Docker Image (Container Scanning):**
      - Scan the built Docker image for OS and library vulnerabilities (e.g., using Trivy image scan, Clair, or cloud provider's container scanning). Fail on critical/high vulnerabilities.
  10. **Push Docker Image:** Push the tagged and scanned image to a container registry (e.g., Docker Hub, AWS ECR, GCP Artifact Registry, GitLab Container Registry).
  11. **Code Coverage Report:** Upload code coverage reports (e.g., `coverage.xml`) to a monitoring service (e.g., Codecov, SonarQube, GitLab Coverage). Potentially fail build if coverage drops below a defined threshold.
  12. **Notifications:** Notify developers (e.g., via Slack, email, MS Teams) of CI build success or failure.

## 5. Continuous Deployment/Delivery (CD) Pipeline

- **Trigger:**
  - **Staging:** Automatically on successful merge to `develop` or `release/*` branches.
  - **Production:** Manually triggered after successful Staging deployment and verification, or automatically on merge to `main` (if using Continuous Delivery for `main`) or after tagging a release from a `release/*` branch.
- **Key Stages (Example for Staging/Production):**
  1.  **Approval (Production - Mandatory):** Manual approval step in the CD platform before deploying to Production.
  2.  **Fetch Artifacts:** Pull the specific Docker image (tagged from CI) from the container registry.
  3.  **Environment Configuration & Secret Injection:**
      - Retrieve environment-specific configuration values and secrets from the secrets management system (e.g., AWS Secrets Manager, Vault) and the configuration store (e.g., environment-specific config maps).
      - Inject these as environment variables into the application containers during deployment.
  4.  **Infrastructure Provisioning/Update (IaC - If Applicable):**
      - Run IaC tools (Terraform, CloudFormation, etc.) to apply any necessary infrastructure changes before application deployment.
  5.  **Database Backup (Production - CRITICAL):**
      - Trigger and verify a database backup immediately before applying database migrations (as defined in `migration_and_db_management_strategy.md (FastAPI Edition)`).
  6.  **Run Database Migrations (Alembic):**
      - Execute `alembic upgrade head` against the target environment's database. This command must be run from a container or environment that has the application code (for Alembic scripts) and database connectivity.
      - **Monitor migration execution closely.** Have a plan for failed migrations (usually involves restoring DB from backup and rolling back code).
  7.  **Deploy Application (Container Orchestrator - e.g., Kubernetes, ECS):**
      - Update the Kubernetes Deployment/StatefulSet, ECS Service, or equivalent with the new Docker image tag.
      - Utilize a safe deployment strategy:
        - **Rolling Update (Default):** Gradually replace old application instances with new ones. Configure readiness and liveness probes correctly.
        - **Blue-Green Deployment:** Deploy the new version alongside the old one, then switch traffic. Allows for easy rollback.
        - **Canary Deployment:** Release the new version to a small subset of users/traffic, monitor, then gradually roll out.
  8.  **Deploy Celery Workers & Beat:**
      - Update Celery worker deployments/services with the new Docker image.
      - Update Celery Beat deployment (usually a single instance) with the new image.
  9.  **Run Post-Deployment Health Checks/Smoke Tests:**
      - Execute a small suite of automated API tests (smoke tests) against the newly deployed version to verify critical functionality.
      - Check application health endpoints (`/healthz/live`, `/healthz/ready`).
  10. **Traffic Shifting (Completion for Blue-Green/Canary):** If using these strategies, complete the traffic shift to the new version after successful health checks and initial monitoring.
  11. **Notifications:** Notify relevant teams (Dev, QA, Ops) of deployment success or failure.
  12. **Cleanup (Blue-Green):** Decommission the old version's infrastructure after a successful blue-green deployment and monitoring period.

## 6. Deployment Infrastructure Considerations (FastAPI Focus)

- **Target Platform:** Cloud Provider (AWS, GCP, Azure), Kubernetes, Serverless (e.g., AWS Lambda with Mangum - for specific stateless workloads, not typically for full ERP), VMs. **Kubernetes or managed container services (ECS, Cloud Run) are highly recommended for scalability and management.**
- **Containerization:** Docker is used to package the FastAPI application, Uvicorn, and dependencies.
- **ASGI Server:** **Uvicorn** running with multiple worker processes (e.g., `uvicorn app.main:app --host 0.0.0.0 --port 80 --workers 4`).
  - Consider using **Gunicorn as a process manager for Uvicorn workers** in production (e.g., `gunicorn -k uvicorn.workers.UvicornWorker app.main:app`) for more robust worker management. Add `gunicorn` to `requirements/prod.txt`.
- **Reverse Proxy / Load Balancer:** Nginx, Traefik, HAProxy, or cloud provider load balancers (ALB, NLB, etc.) in front of Uvicorn instances for SSL termination, request routing, load balancing, and serving static files (if any are served by backend, though usually a CDN/S3 for frontend statics).
- **Database:** Managed PostgreSQL service (AWS RDS, Google Cloud SQL, Azure Database for PostgreSQL).
- **Redis:** Managed Redis service (AWS ElastiCache, Google Memorystore, Azure Cache for Redis).
- **Celery Workers/Beat:** Run as separate Docker containers, managed by the container orchestrator (e.g., Kubernetes Deployments for workers, a single-instance Deployment or CronJob for Beat if using Kubernetes-native scheduling, or a dedicated Beat container).
- **Elasticsearch:** Managed Elasticsearch/OpenSearch service or a self-hosted cluster (often on Kubernetes).

## 7. Rollback Strategy

- **Application Code/Containers:**
  - **Fast Rollback:** Re-deploy the previous stable Docker image tag. This is quick if using immutable infrastructure.
  - **Automated Rollback:** Configure CD pipeline to automatically trigger rollback if post-deployment health checks/smoke tests fail or if critical monitoring alerts fire immediately after deployment.
- **Database Migrations (Alembic):**
  - **Downgrading (`alembic downgrade -1`):** Possible if `down()` methods in migration scripts are meticulously written and tested. However, downgrading migrations with data changes can be risky and may lead to data loss. **Generally discouraged in production for complex changes.**
  - **Primary DB Rollback Strategy for Failed Migration:** **Restore the database from the verified backup** taken immediately before the migration run. This requires downtime and a code rollback to the version compatible with the restored DB schema.
  - **Roll-Forward Fix:** For minor schema issues post-migration, prefer creating a new Alembic migration to fix the problem and rolling forward.

## 8. Monitoring Integration

- Deployment events (start, success, failure, version deployed) will be sent to the monitoring/alerting system (e.g., as annotations in Grafana, events in Sentry/Loki).
- Monitor application health and key metrics closely immediately after deployment to detect issues rapidly.

# Secrets Management Strategy (FastAPI Edition)

## 1. Overview

- **Purpose**: To define the strategy for securely managing and accessing sensitive information (secrets) required by the FastAPI-based ERP application, ensuring they are protected throughout their lifecycle.
- **Scope**: Covers the definition of secrets, chosen storage solution (AWS Secrets Manager), access control, rotation policies, and integration with the application's configuration system (Pydantic Settings).
- **Chosen Technology**: **AWS Secrets Manager** as the primary secrets storage solution. Principles apply to alternatives like HashiCorp Vault or other cloud provider secret managers.

## 2. Core Principles

- **Centralized Secure Storage**: Store all application secrets in a dedicated, hardened secrets management system, not in version control, configuration files, or application code.
- **Least Privilege Access**: Grant applications, services, and users only the minimum necessary permissions to access specific secrets they require.
- **Encryption at Rest and in Transit**: Ensure secrets are encrypted both when stored within the secrets manager and when being transmitted to the application or authorized users. AWS Secrets Manager handles this by default (using AWS KMS).
- **Auditing**: Maintain comprehensive audit trails of all secret access, modifications, and management operations.
- **Rotation**: Implement automated or well-defined manual rotation policies for secrets to limit the window of exposure if a secret is compromised.
- **No Hardcoded Secrets**: Secrets must never be hardcoded.

## 3. Definition of Secrets

Secrets for the ERP application include, but are not limited to:

- **Database Credentials**: The full `DATABASE_URL` containing username and password for PostgreSQL.
- **`JWT_SECRET_KEY`**: The secret key used for signing and verifying JSON Web Tokens.
- **Redis Password**: If Redis instances are password-protected (`settings.REDIS_PASSWORD`).
- **Elasticsearch Credentials**: Username and password if Elasticsearch is secured (`settings.ELASTICSEARCH_USERNAME`, `settings.ELASTICSEARCH_PASSWORD`).
- **Cloud Provider Service Keys**:
  - `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` for accessing AWS services like S3 (if dedicated keys are used instead of solely relying on IAM roles for service access).
  - Equivalent credentials for other cloud services if applicable.
- **External Third-Party API Keys**: Keys for payment gateways, email services, mapping services, tax calculation services, etc.
- **Internal Service-to-Service Credentials**: If applicable.
- **Cryptographic Keys**: Any other application-level encryption or signing keys.
- **Sentry DSN**: While not a "secret" in the same vein as a password, the Sentry DSN is sensitive and should be managed as configuration injected from a secure source.

## 4. AWS Secrets Manager Integration & Workflow

### 4.1. Storing Secrets in AWS Secrets Manager

- **Creation**: Secrets will be created and managed within AWS Secrets Manager via the AWS Console, CLI, or Infrastructure as Code (e.g., Terraform, CloudFormation).
- **Secret Structure**: Secrets can be stored as:
  - **Plaintext**: For single values like `JWT_SECRET_KEY`.
  - **JSON Key-Value Pairs**: For grouped credentials, e.g., a single secret named `erp/production/database` could store a JSON object like `{"DATABASE_URL": "postgresql+asyncpg://user:verysecretpass@host/db"}`. This is often preferred as it allows fetching multiple related values with one `GetSecretValue` call.
- **Naming Convention**: A consistent naming convention will be used for secrets in AWS Secrets Manager to clearly identify their purpose and environment.
  - Format: `erp/{environment}/{service_or_component}/{secret_name}`
  - Examples:
    - `erp/production/postgresql/database_url`
    - `erp/staging/jwt/secret_key`
    - `erp/production/redis/password`
    - `erp/production/aws/s3_app_user_credentials` (containing access key ID and secret access key as JSON)
    - `erp/production/external_services/payment_gateway_api_key`

### 4.2. Application Access to Secrets & Integration with Pydantic Settings

- **Primary Method: Injection as Environment Variables at Deployment/Startup.**
  1.  **IAM Permissions:** The application's runtime environment (e.g., EC2 instance profile for VMs, ECS task role, EKS service account IAM role) will be granted fine-grained IAM permissions (e.g., `secretsmanager:GetSecretValue`) to read _only the specific secrets it requires_ from AWS Secrets Manager.
  2.  **Secret Retrieval Process:** During the application's deployment or container startup sequence (e.g., within a Docker `ENTRYPOINT` script, an init container in Kubernetes, or a deployment script):
      - A script (using AWS CLI or an SDK like `boto3` if the entrypoint is Python-based) will authenticate to AWS using the instance/task IAM role.
      - This script will fetch the required secret values from AWS Secrets Manager using their ARNs or friendly names.
      - If a secret from AWS Secrets Manager is a JSON string containing multiple key-value pairs, the script will parse the JSON.
      - The retrieved secret values (or parsed key-value pairs) will be **exported as environment variables** for the FastAPI application process (e.g., `export DATABASE_URL="retrieved_value"`, `export JWT_SECRET_KEY="retrieved_value"`).
  3.  **Consumption by Pydantic Settings:**
      - The FastAPI application's `pydantic-settings` configuration (defined in `app/core/config.py:Settings`) is designed to load configuration values from environment variables.
      - At application startup, the `Settings` class will automatically read these environment variables (which now contain the actual secret values) to populate its attributes (e.g., `settings.DATABASE_URL`, `settings.JWT_SECRET_KEY`).
      - This approach ensures that the application code itself does not directly interact with AWS Secrets Manager during its normal operation for configuration loading, simplifying the application logic and centralizing secret retrieval to the startup phase.

### 4.3. Example `Settings` Model Attributes for Secrets

```python
# app/core/config.py (relevant Pydantic Settings attributes)
class Settings(BaseSettings):
    # These are expected to be populated from environment variables,
    # which in turn are populated from AWS Secrets Manager in prod/staging.
    DATABASE_URL: PostgresDsn
    JWT_SECRET_KEY: str
    REDIS_PASSWORD: Optional[str] = None
    ELASTICSEARCH_PASSWORD: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None # If S3 user keys are used
    # ... other secret-dependent settings ...
```

## 5. Secret Rotation

- **Automated Rotation (AWS Secrets Manager Feature):**
  - For supported services like **AWS RDS database credentials**, AWS Secrets Manager's native rotation capabilities (using Lambda functions) will be configured and utilized.
  - Secrets Manager will automatically rotate these credentials with the database and update the secret value in Secrets Manager.
- **Custom Rotation Lambda Functions:**
  - For other secrets (e.g., application-specific `JWT_SECRET_KEY`, external API keys), custom AWS Lambda functions will be developed to handle automated rotation if the third-party service supports programmatic key rotation.
  - These Lambda functions will be scheduled and configured as custom rotation functions within AWS Secrets Manager.
- **Manual Rotation:**
  - For secrets where automated rotation is not feasible or overly complex, a documented manual rotation procedure will be established.
  - Rotation frequency will be defined based on risk assessment (e.g., every 90, 180, or 365 days).
- **Application Impact:**
  - Since secrets are injected as environment variables at application startup, applications typically need to be **restarted or redeployed** to pick up rotated secret values.
  - Deployment strategies (e.g., rolling updates) will facilitate this process with minimal downtime.

## 6. Local Development

- For local development, developers will use a local `.env` file to define values for secret-dependent settings (e.g., `DATABASE_URL` pointing to a local PostgreSQL, a development `JWT_SECRET_KEY`).
- **These local `.env` files must contain non-production, development-only values and must never be committed to version control.**
- Direct developer access to production or staging secrets in AWS Secrets Manager will be highly restricted and follow the principle of least privilege.

## 7. Security Best Practices & Auditing

- **IAM Least Privilege:** Ensure IAM roles/users for applications or deployment systems have only the necessary `secretsmanager:GetSecretValue` permissions on the specific secrets they need to access. Avoid wildcard permissions.
- **Encryption:** Utilize AWS KMS for encrypting secrets within Secrets Manager. Consider using customer-managed keys (CMKs) for enhanced control if required by specific compliance standards; otherwise, AWS-managed keys are typically sufficient.
- **Audit Logging:** AWS CloudTrail will be enabled and configured to log all API calls to AWS Secrets Manager. These logs will be monitored for unauthorized access attempts or suspicious activity, potentially by forwarding them to a SIEM.
- **VPC Endpoints for Secrets Manager:** In AWS environments, configure a VPC interface endpoint for AWS Secrets Manager. This allows applications within the VPC to access Secrets Manager without traffic traversing the public internet, enhancing security.
- **Regular Review:** Periodically review IAM permissions related to Secrets Manager access and the secrets themselves.

## 8. Tooling

- **Primary:** AWS Secrets Manager.
- **Supporting:** AWS IAM (for access control), AWS KMS (for encryption), AWS CloudTrail (for auditing), AWS CLI / SDKs (for scripted access and retrieval during deployment).

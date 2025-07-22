# Finks Naive - Pulumi Deployment

This directory contains the Pulumi infrastructure code for deploying the Finks Naive service as an AWS Lambda function across multiple environments.

## Prerequisites

1. Install Pulumi CLI
2. Configure AWS credentials
3. Install Python dependencies: `pip install -r requirements.txt`

## Multi-Environment Deployment

This project uses Pulumi stacks to manage three environments:
- **dev**: Development environment
- **staging**: Staging environment
- **prod**: Production environment

### Initial Setup

```bash
cd pulumi

# Initialize stacks (only needed once)
pulumi stack init dev       # Already exists
pulumi stack init staging   # Create new
pulumi stack init prod      # Create new
```

### Deploy to Specific Environment

```bash
# Deploy to dev
pulumi stack select dev
pulumi up

# Deploy to staging
pulumi stack select staging
pulumi up

# Deploy to prod
pulumi stack select prod
pulumi up

# Or deploy directly to a stack
pulumi up -s dev
pulumi up -s staging
pulumi up -s prod
```

### Environment Configuration

Each stack automatically:
- Loads from the appropriate `.env.{environment}` file
- Names resources with environment prefix (e.g., `dev-finks-screener-lambda`)
- Tags resources with the correct environment

Environment files:
- `.env.dev` - MongoDB: `dev-finks-db`
- `.env.staging` - MongoDB: `staging-finks-db`
- `.env.prod` - MongoDB: `prod-finks-db`

### View Deployment Outputs

After deployment, you can view the stack outputs to get URLs and resource information:

```bash
# Set passphrase (or export it)
export PULUMI_CONFIG_PASSPHRASE=finks

# View all outputs for current stack
uv run pulumi stack output

# Get specific output
uv run pulumi stack output function_url
uv run pulumi stack output function_url_endpoint

# View outputs for specific stack
uv run pulumi stack output -s dev
uv run pulumi stack output -s staging
uv run pulumi stack output -s prod

# Get specific output from specific stack
uv run pulumi stack output function_url -s staging
```

## Architecture

- **ECR Repository**: Stores the Docker image
- **Lambda Function**: Runs the FastAPI application with ARM64 architecture
- **Function URL**: Direct HTTP access (no API Gateway)
- **CloudWatch**: Logs and monitoring
- **IAM Role**: Lambda execution permissions

## Outputs

- `function_url`: Direct URL to access the API
- `function_url_endpoint`: URL to the API documentation (/docs)
- `lambda_function_name`: Name of the Lambda function
- `lambda_function_arn`: ARN of the Lambda function
- `ecr_repository_url`: ECR repository URL
- `cloudwatch_log_group`: CloudWatch log group name

## Cleanup

```bash
# Destroy specific stack
pulumi destroy -s dev
pulumi destroy -s staging
pulumi destroy -s prod

# Or select stack first then destroy
pulumi stack select dev
pulumi destroy
```
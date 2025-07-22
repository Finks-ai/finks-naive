import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
import os

# Get stack name and configuration
stack_name = pulumi.get_stack()
config = pulumi.Config()
aws_region = "ca-central-1"  # Always use ca-central-1

# Map stack names to environment names
env_map = {
    "dev": "dev",
    "staging": "staging",
    "prod": "prod"
}
environment = env_map.get(stack_name, "dev")

# Load environment variables from stack-specific .env file
def load_env_vars():
    """Load environment variables from stack-specific .env file"""
    env_vars = {}
    # Try stack-specific env file first, then fall back to .env
    env_files = [
        os.path.join(os.path.dirname(__file__), "..", f".env.{environment}"),
        os.path.join(os.path.dirname(__file__), "..", ".env")
    ]
    
    for env_file_path in env_files:
        if os.path.exists(env_file_path):
            with open(env_file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key] = value
            pulumi.log.info(f"Loaded environment variables from {env_file_path}")
            break
    
    return env_vars

env_vars = load_env_vars()

# Stack-specific naming
project_name = f"{environment}-finks-screener"

# Create ECR repository for container images
ecr_repo = aws.ecr.Repository(
    f"{project_name}-repo",
    name=project_name,
    force_delete=True,
    tags={
        "Project": "finks-naive",
        "Environment": environment
    }
)

# Build and push Docker image to ECR
image = awsx.ecr.Image(
    f"{project_name}-image",
    repository_url=ecr_repo.repository_url,
    context="../",  # Build context is the parent directory
    dockerfile="../dockerfile",
    platform="linux/arm64"  # ARM architecture as specified
)

# Create IAM role for Lambda function
lambda_role = aws.iam.Role(
    f"{project_name}-lambda-role",
    assume_role_policy=pulumi.Output.from_input({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"}
            }
        ]
    }).apply(lambda policy: pulumi.Output.json_dumps(policy))
)

# Attach basic Lambda execution policy
lambda_policy_attachment = aws.iam.RolePolicyAttachment(
    f"{project_name}-lambda-policy",
    role=lambda_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
)

# Create Lambda function
lambda_function = aws.lambda_.Function(
    f"{project_name}-lambda",
    package_type="Image",
    image_uri=image.image_uri,
    role=lambda_role.arn,
    architectures=["arm64"],  # ARM architecture
    timeout=600,  # 30 second timeout
    memory_size=512,  # 512MB memory
    environment={
        "variables": {
            "ENVIRONMENT": environment,
            "MONGODB_URL": env_vars.get("MONGODB_URL", ""),
            "MONGODB_DB_NAME": env_vars.get("MONGODB_DB_NAME", ""),
            "GEMINI_API_KEY": env_vars.get("GEMINI_API_KEY", ""),
            "OPENAI_API_KEY": env_vars.get("OPENAI_API_KEY", ""),
        }
    },
    tags={
        "Project": "finks-naive",
        "Environment": environment
    }
)

# Create Function URL for direct access (no API Gateway needed)
function_url = aws.lambda_.FunctionUrl(
    f"{project_name}-function-url",
    function_name=lambda_function.name,
    authorization_type="NONE",  # Public access - adjust as needed
    cors={
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_origins": ["*"],
        "allow_headers": ["*"],
        "expose_headers": ["date", "keep-alive"],
        "max_age": 86400,
    }
)

# Create CloudWatch Log Group for Lambda
log_group = aws.cloudwatch.LogGroup(
    f"{project_name}-log-group",
    name=pulumi.Output.concat("/aws/lambda/", lambda_function.name),
    retention_in_days=14,
    tags={
        "Project": "finks-naive",
        "Environment": environment
    }
)

# Export important outputs
pulumi.export("ecr_repository_url", ecr_repo.repository_url)
pulumi.export("lambda_function_name", lambda_function.name)
pulumi.export("lambda_function_arn", lambda_function.arn)
pulumi.export("function_url", function_url.function_url)
pulumi.export("function_url_endpoint", pulumi.Output.concat(function_url.function_url, "docs"))
pulumi.export("cloudwatch_log_group", log_group.name)

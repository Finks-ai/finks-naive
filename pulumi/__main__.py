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

# Stack-specific Lambda configuration
lambda_config = {
    "dev": {
        "memory_size": 256,  # Reduced based on logs showing only 128MB used
        "timeout": 60 * 5,  # Increased to handle init timeout
        "reserved_concurrent": 0,  # No reserved for dev
        "provisioned_concurrent": 0  # No provisioned for dev
    },
    "staging": {
        "memory_size": 512,
        "timeout": 60 * 5,
        # "reserved_concurrent": 2,
        # "provisioned_concurrent": 0
    },
    "prod": {
        "memory_size": 1024,  
        "timeout": 60 * 15,
        # "reserved_concurrent": 3,  
        # "provisioned_concurrent": 1  # Keep 2 warm instances
    }
}

current_config = lambda_config.get(environment, lambda_config["dev"])

# Create Lambda function with optimized settings
lambda_function = aws.lambda_.Function(
    f"{project_name}-lambda",
    package_type="Image",
    image_uri=image.image_uri,
    role=lambda_role.arn,
    architectures=["arm64"],  
    timeout=current_config["timeout"],
    memory_size=current_config["memory_size"],
    reserved_concurrent_executions=current_config["reserved_concurrent"] if current_config["reserved_concurrent"] > 0 else None,
    environment={
        "variables": {
            "ENVIRONMENT": environment,
            "MONGODB_URL": env_vars.get("MONGODB_URL", ""),
            "MONGODB_DB_NAME": env_vars.get("MONGODB_DB_NAME", ""),
            "GOOGLE_API_KEY": env_vars.get("GOOGLE_API_KEY", ""),
            "OPENAI_API_KEY": env_vars.get("OPENAI_API_KEY", ""),
            # MongoDB optimization settings
            "MONGODB_MAX_POOL_SIZE": "1",
            "MONGODB_MIN_POOL_SIZE": "0",
            "MONGODB_MAX_IDLE_TIME_MS": "45000",
            "MONGODB_SERVER_SELECTION_TIMEOUT_MS": "5000",
            # Cache settings
            "CACHE_TTL_SECONDS": "3600",
            "CACHE_MAX_MEMORY_ITEMS": "1000",
            # Performance settings
            "PARALLEL_EXECUTION_ENABLED": "true",
            "MAX_CONCURRENT_AGENTS": "5",
            # Lambda optimization flags
            "LAZY_LOAD_MODELS": "true",
            "PRELOAD_CACHE": "false" if environment == "dev" else "true"
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
log_retention = {
    "dev": 3,
    "staging": 7,
    "prod": 14
}

log_group = aws.cloudwatch.LogGroup(
    f"{project_name}-log-group",
    name=pulumi.Output.concat("/aws/lambda/", lambda_function.name),
    retention_in_days=log_retention.get(environment, 7),
    tags={
        "Project": "finks-naive",
        "Environment": environment
    }
)

# Add provisioned concurrency for production
if environment == "prod" and current_config["provisioned_concurrent"] > 0:
    provisioned_concurrency = aws.lambda_.ProvisionedConcurrencyConfig(
        f"{project_name}-provisioned-concurrency",
        function_name=lambda_function.name,
        provisioned_concurrent_executions=current_config["provisioned_concurrent"],
        qualifier=lambda_function.version
    )

# CloudWatch Alarms
# High error rate alarm
error_alarm = aws.cloudwatch.MetricAlarm(
    f"{project_name}-error-alarm",
    name=f"{project_name}-high-error-rate",
    comparison_operator="GreaterThanThreshold",
    evaluation_periods=2,
    metric_name="Errors",
    namespace="AWS/Lambda",
    period=300,
    statistic="Sum",
    threshold=10,
    alarm_description="Lambda function error rate is too high",
    dimensions={
        "FunctionName": lambda_function.name
    },
    tags={
        "Project": "finks-naive",
        "Environment": environment
    }
)

# Slow initialization alarm
init_alarm = aws.cloudwatch.MetricAlarm(
    f"{project_name}-init-alarm",
    name=f"{project_name}-slow-init",
    comparison_operator="GreaterThanThreshold",
    evaluation_periods=1,
    metric_name="InitDuration",
    namespace="AWS/Lambda",
    period=300,
    statistic="Maximum",
    threshold=5000,  # 5 seconds
    alarm_description="Lambda initialization is taking too long",
    dimensions={
        "FunctionName": lambda_function.name
    },
    tags={
        "Project": "finks-naive",
        "Environment": environment
    }
)

# Duration alarm for timeouts
duration_alarm = aws.cloudwatch.MetricAlarm(
    f"{project_name}-duration-alarm",
    name=f"{project_name}-slow-queries",
    comparison_operator="GreaterThanThreshold",
    evaluation_periods=3,
    metric_name="Duration",
    namespace="AWS/Lambda",
    period=300,
    statistic="Average",
    threshold=10000,  # 10 seconds
    alarm_description="Query processing is taking too long",
    dimensions={
        "FunctionName": lambda_function.name
    },
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
pulumi.export("lambda_memory_size", current_config["memory_size"])
pulumi.export("lambda_timeout", current_config["timeout"])
pulumi.export("environment", environment)

# Export alarm names
pulumi.export("error_alarm", error_alarm.name)
pulumi.export("init_alarm", init_alarm.name)
pulumi.export("duration_alarm", duration_alarm.name)

# Export configuration summary
pulumi.export("config_summary", {
    "memory_mb": current_config["memory_size"],
    "timeout_seconds": current_config["timeout"],
    "reserved_concurrent": current_config["reserved_concurrent"],
    "provisioned_concurrent": current_config["provisioned_concurrent"],
    "log_retention_days": log_retention.get(environment, 7)
})

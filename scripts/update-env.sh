#!/bin/bash

# Update Lambda Environment Variables Script
# This script updates the Lambda function environment variables

set -e

# Set Pulumi config passphrase
export PULUMI_CONFIG_PASSPHRASE="finks"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGION="ca-central-1"
STACK_NAME="dev"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get function name from Pulumi
get_function_name() {
    cd pulumi
    FUNCTION_NAME=$(pulumi stack output lambda_function_name --stack $STACK_NAME)
    cd ..

    if [ -z "$FUNCTION_NAME" ]; then
        log_error "Could not get Lambda function name from Pulumi stack"
        exit 1
    fi

    log_info "Function name: $FUNCTION_NAME"
}

# Update environment variables
update_env_vars() {
    log_info "Updating Lambda environment variables..."

    # Source the .env file to get values
    if [ -f .env ]; then
        export $(cat .env | xargs)
    else
        log_error ".env file not found. Please create it with your environment variables."
        exit 1
    fi

    # Update Lambda function environment variables using JSON file
    cat > /tmp/env.json << EOF
{
    "MONGODB_URL": "$MONGODB_URL",
    "MONGODB_DB_NAME": "$MONGODB_DB_NAME",
    "GEMINI_API_KEY": "$GEMINI_API_KEY",
    "OPENAI_API_KEY": "$OPENAI_API_KEY",
    "ENVIRONMENT": "development"
}
EOF

    aws lambda update-function-configuration \
        --function-name "$FUNCTION_NAME" \
        --environment Variables=file:///tmp/env.json \
        --region $REGION

    rm /tmp/env.json

    log_success "Environment variables updated successfully"
}

# Main function
main() {
    log_info "Updating Lambda environment variables..."
    get_function_name
    update_env_vars
    log_success "Environment variables update completed!"
}

# Run main function
main "$@"

#!/bin/bash

# Finks Naive Deployment Script
# This script handles the complete deployment process for the Finks Naive service

set -e  # Exit on any error

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

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if pulumi is installed
    if ! command -v pulumi &> /dev/null; then
        log_error "Pulumi CLI not found. Please install it first."
        exit 1
    fi

    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install it first."
        exit 1
    fi

    # Check if uv is installed
    if ! command -v uv &> /dev/null; then
        log_error "uv not found. Please install it first."
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Please run 'aws configure'."
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Deploy infrastructure
deploy_infrastructure() {
    log_info "Deploying infrastructure with Pulumi..."

    cd pulumi

    # Install Python dependencies
    log_info "Installing Pulumi dependencies..."
    pip install -r requirements.txt

    # Deploy stack
    log_info "Deploying stack: $STACK_NAME"
    pulumi up --yes --stack $STACK_NAME

    # Get outputs
    log_info "Getting deployment outputs..."
    export FUNCTION_NAME=$(pulumi stack output lambda_function_name --stack $STACK_NAME)
    export FUNCTION_URL=$(pulumi stack output function_url --stack $STACK_NAME)
    export FUNCTION_DOCS_URL=$(pulumi stack output function_url_endpoint --stack $STACK_NAME)

    cd ..

    log_success "Infrastructure deployed successfully"
}

# Check environment variables
check_environment_variables() {
    log_info "Checking environment variables..."

    # Check if .env file exists
    if [ -f .env ]; then
        log_success "Environment variables file (.env) found"
        log_info "Environment variables will be set automatically by Pulumi during deployment"
    else
        log_error ".env file not found. Please create it with your environment variables."
        exit 1
    fi
}

# Test deployment
test_deployment() {
    log_info "Testing deployment..."

    # Test root endpoint
    log_info "Testing root endpoint..."
    response=$(curl -s -o /dev/null -w "%{http_code}" "$FUNCTION_URL")

    if [ "$response" -eq 200 ]; then
        log_success "Root endpoint test passed"
    else
        log_error "Root endpoint test failed with status code: $response"
        exit 1
    fi

    # Test health endpoint
    log_info "Testing health endpoint..."
    response=$(curl -s -o /dev/null -w "%{http_code}" "$FUNCTION_URL/health")

    if [ "$response" -eq 200 ]; then
        log_success "Health endpoint test passed"
    else
        log_warning "Health endpoint test failed with status code: $response (might be database connection issue)"
    fi

    log_success "Deployment testing completed"
}

# Display deployment info
display_deployment_info() {
    log_info "Deployment Information:"
    echo ""
    echo "  Function Name: $FUNCTION_NAME"
    echo "  Function URL:  $FUNCTION_URL"
    echo "  API Docs:      $FUNCTION_DOCS_URL"
    echo ""
    log_info "You can now access your API at: $FUNCTION_URL"
    log_info "API Documentation: $FUNCTION_DOCS_URL"
}

# Main deployment process
main() {
    log_info "Starting Finks Naive deployment..."
    echo ""

    check_prerequisites
    check_environment_variables
    deploy_infrastructure
    test_deployment
    display_deployment_info

    log_success "Deployment completed successfully!"
}

# Run main function
main "$@"

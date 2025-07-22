#!/bin/bash

# Quick Deployment Script for Development
# This script handles quick redeployment of code changes

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

# Quick redeploy (only updates the Docker image)
quick_redeploy() {
    log_info "Quick redeployment - updating Docker image only..."
    
    cd pulumi
    
    # Update just the image
    pulumi up --yes --stack $STACK_NAME --target "awsx:ecr:Image\$docker-build:index:Image::*"
    
    # Get function URL
    export FUNCTION_URL=$(pulumi stack output function_url --stack $STACK_NAME)
    
    cd ..
    
    log_success "Quick redeployment completed!"
    log_info "Function URL: $FUNCTION_URL"
    log_info "API Docs: ${FUNCTION_URL}docs"
}

# Main function
main() {
    log_info "Starting quick deployment..."
    quick_redeploy
    log_success "Quick deployment completed successfully!"
}

# Run main function
main "$@"
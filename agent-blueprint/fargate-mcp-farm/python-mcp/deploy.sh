#!/bin/bash

# Python MCP Server Deployment Script
# Deploys Python MCP Server to AWS ECS Fargate using CDK

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CDK_DIR="${SCRIPT_DIR}/cdk"
DOCKER_DIR="${SCRIPT_DIR}/docker"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command_exists aws; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check CDK
    if ! command_exists cdk; then
        log_error "AWS CDK is not installed. Please install it first: npm install -g aws-cdk"
        exit 1
    fi
    
    # Check Python
    if ! command_exists python3; then
        log_error "Python 3 is not installed. Please install it first."
        exit 1
    fi
    
    # Check Docker
    if ! command_exists docker; then
        log_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    log_success "All prerequisites are satisfied"
}

# Function to setup Python virtual environment
setup_python_env() {
    log_info "Setting up Python virtual environment..."
    
    cd "${CDK_DIR}"
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Install/upgrade pip and requirements
    pip install --upgrade pip
    pip install -r requirements.txt
    
    log_success "Python environment setup complete"
}

# Function to validate AWS credentials and region
validate_aws_config() {
    log_info "Validating AWS configuration..."
    
    # Check AWS credentials
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        log_error "AWS credentials are not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    # Get account ID
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    CURRENT_REGION=$(aws configure get region)
    
    log_info "AWS Account ID: ${ACCOUNT_ID}"
    log_info "AWS Region: ${CURRENT_REGION}"
    
    # Verify region is us-west-2 (required for shared infrastructure)
    if [ "${CURRENT_REGION}" != "us-west-2" ]; then
        log_warning "Current region is ${CURRENT_REGION}, but shared infrastructure is in us-west-2"
        log_warning "Make sure your shared infrastructure (VPC, ALB) is in the same region"
    fi
    
    log_success "AWS configuration validated"
}

# Function to bootstrap CDK (if needed)
bootstrap_cdk() {
    log_info "Checking CDK bootstrap status..."
    
    cd "${CDK_DIR}"
    source venv/bin/activate
    
    # Check if CDK is already bootstrapped
    if aws cloudformation describe-stacks --stack-name CDKToolkit --region "${CURRENT_REGION}" >/dev/null 2>&1; then
        log_info "CDK is already bootstrapped"
    else
        log_info "Bootstrapping CDK..."
        cdk bootstrap "aws://${ACCOUNT_ID}/${CURRENT_REGION}"
        log_success "CDK bootstrap complete"
    fi
}

# Function to build and test Docker image locally
test_docker_build() {
    log_info "Testing Docker build locally..."
    
    cd "${SCRIPT_DIR}"
    
    # Build the Docker image with local source code
    docker build \
        --platform linux/arm64 \
        -f docker/Dockerfile \
        -t python-mcp-test:latest \
        .
    
    log_success "Docker build completed successfully"
    
    # Optional: Test the container locally
    log_info "Starting container for quick test..."
    CONTAINER_ID=$(docker run -d -p 3001:3001 python-mcp-test:latest)
    
    # Wait a moment for container to start
    sleep 15
    
    # Test health check
    if curl -f http://localhost:3001/mcp >/dev/null 2>&1; then
        log_success "Container health check passed"
    else
        log_warning "Container health check failed, but this may be expected for MCP protocol"
    fi
    
    # Stop test container
    docker stop "${CONTAINER_ID}" >/dev/null 2>&1
    docker rm "${CONTAINER_ID}" >/dev/null 2>&1
    
    log_info "Docker test completed"
}

# Function to deploy the stack
deploy_stack() {
    local STACK_NAME="python-mcp-fargate"
    
    log_info "Deploying stack: ${STACK_NAME}..."
    
    cd "${CDK_DIR}"
    source venv/bin/activate
    
    # Deploy the stack
    cdk deploy "${STACK_NAME}" \
        --require-approval never \
        --verbose
    
    log_success "Stack deployment completed: ${STACK_NAME}"
}

# Function to show deployment outputs
show_outputs() {
    local STACK_NAME="python-mcp-fargate"
    
    log_info "Deployment outputs for ${STACK_NAME}:"
    
    cd "${CDK_DIR}"
    source venv/bin/activate
    
    # Get stack outputs
    cdk outputs "${STACK_NAME}" 2>/dev/null || {
        log_warning "Could not retrieve stack outputs. Stack may still be deploying."
        return
    }
}

# Main deployment function
main() {
    log_info "Starting Python MCP Server deployment..."
    log_info "Stack name: python-mcp-fargate"
    
    # Run deployment steps
    check_prerequisites
    setup_python_env
    validate_aws_config
    bootstrap_cdk
    test_docker_build
    deploy_stack
    show_outputs
    
    log_success "Python MCP Server deployment completed successfully!"
    log_info "The service will be available at: http://<ALB-DNS>/python/mcp"
    log_info "Check the stack outputs above for the exact URL"
}

# Script usage
usage() {
    echo "Usage: $0"
    echo ""
    echo "Description:"
    echo "  Deploy Python MCP Server to AWS ECS Fargate"
    echo ""
    echo "Example:"
    echo "  $0           # Deploy Python MCP Server"
    echo ""
}

# Parse command line arguments
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    usage
    exit 0
fi

# Run main function
main
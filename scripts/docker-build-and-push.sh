#!/bin/bash

# Docker Build and Push Script for Charlotte Application
# This script builds and pushes both frontend and backend images to Azure Container Registry

set -e

# Configuration variables
ACR_NAME="charlotteacr"
RESOURCE_GROUP="rg-primary-unc-foit-charlotte-ai"
IMAGE_TAG="${IMAGE_TAG:-1.0.0}"
FRONTEND_API_URL="${NEXT_PUBLIC_API_BASE_URL:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    print_status "Docker is installed"
}

# Function to check if Azure CLI is installed
check_azure_cli() {
    if ! command -v az &> /dev/null; then
        print_error "Azure CLI is not installed. Please install it first."
        exit 1
    fi
    print_status "Azure CLI is installed"
}

# Function to login to Azure Container Registry using admin credentials
login_to_acr() {
    print_status "Logging in to Azure Container Registry (admin creds): $ACR_NAME"
    # Fetch admin credentials from ACR
    ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query username -o tsv)
    ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query passwords[0].value -o tsv)
    if [[ -z "$ACR_USERNAME" || -z "$ACR_PASSWORD" ]]; then
        print_error "Failed to retrieve ACR admin credentials. Ensure Admin user is enabled on the registry."
        exit 1
    fi
    # Get login server
    ACR_SERVER=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer --output tsv)
    echo "$ACR_PASSWORD" | docker login "$ACR_SERVER" --username "$ACR_USERNAME" --password-stdin
    print_status "Successfully logged in to ACR via docker login"
}

# Function to get ACR login server
get_acr_server() {
    ACR_SERVER=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer --output tsv)
    print_status "ACR server: $ACR_SERVER"
}

# Ensure buildx builder exists and is selected
ensure_buildx() {
    if ! docker buildx inspect charlotte-multi &> /dev/null; then
        print_status "Creating docker buildx builder (charlotte-multi)"
        docker buildx create --use --name charlotte-multi > /dev/null
    else
        docker buildx use charlotte-multi > /dev/null
    fi
    print_status "Using docker buildx builder: charlotte-multi"
}

# Function to build and push frontend image
build_and_push_frontend() {
    print_status "Building frontend Docker image..."

    # Build and push frontend image for linux/amd64
    docker buildx build \
        --platform linux/amd64 \
        -f Dockerfile \
        ${FRONTEND_API_URL:+--build-arg NEXT_PUBLIC_API_BASE_URL="$FRONTEND_API_URL"} \
        -t "$ACR_SERVER/charlotte-frontend:$IMAGE_TAG" \
        -t "$ACR_SERVER/charlotte-frontend:latest" \
        . \
        --push

    print_status "Frontend image pushed successfully"
}

# Function to build and push backend image
build_and_push_backend() {
    print_status "Building backend Docker image..."

    # Build and push backend image for linux/amd64
    docker buildx build \
        --platform linux/amd64 \
        -f backend/Dockerfile \
        -t "$ACR_SERVER/charlotte-backend:$IMAGE_TAG" \
        -t "$ACR_SERVER/charlotte-backend:latest" \
        backend \
        --push

    print_status "Backend image pushed successfully"
}

# Function to update web apps with new images
update_web_apps() {
    print_status "Updating web apps with new images..."
    
    # Update frontend web app
    print_status "Updating frontend web app..."
    az webapp config container set \
        --name "charlotte-frontend-app" \
        --resource-group "$RESOURCE_GROUP" \
        --docker-custom-image-name "$ACR_SERVER/charlotte-frontend:$IMAGE_TAG" \
        --docker-registry-server-url "https://$ACR_SERVER"
    
    # Update backend web app
    print_status "Updating backend web app..."
    az webapp config container set \
        --name "charlotte-backend-app" \
        --resource-group "$RESOURCE_GROUP" \
        --docker-custom-image-name "$ACR_SERVER/charlotte-backend:$IMAGE_TAG" \
        --docker-registry-server-url "https://$ACR_SERVER"
    
    print_status "Web apps updated successfully"
}

# Function to restart web apps
restart_web_apps() {
    print_status "Restarting web apps..."
    
    az webapp restart --resource-group "$RESOURCE_GROUP" --name "charlotte-frontend-app"
    az webapp restart --resource-group "$RESOURCE_GROUP" --name "charlotte-backend-app"
    
    print_status "Web apps restarted successfully"
}

# Function to display deployment information
display_deployment_info() {
    print_status "Docker build and push completed successfully!"
    echo
    echo "=== Deployment Information ==="
    echo "ACR Server: $ACR_SERVER"
    echo "Frontend Image: $ACR_SERVER/charlotte-frontend:$IMAGE_TAG"
    echo "Backend Image: $ACR_SERVER/charlotte-backend:$IMAGE_TAG"
    echo
    echo "=== Web App URLs ==="
    echo "Frontend: https://charlotte-frontend-app.azurewebsites.net"
    echo "Backend: https://charlotte-backend-app.azurewebsites.net"
    echo "Backend API Docs: https://charlotte-backend-app.azurewebsites.net/docs"
    echo
    echo "=== Testing Commands ==="
    echo "Test frontend: curl https://charlotte-frontend-app.azurewebsites.net"
    echo "Test backend: curl https://charlotte-backend-app.azurewebsites.net/docs"
    echo "Test API: curl -X POST https://charlotte-backend-app.azurewebsites.net/api/query -H 'Content-Type: application/json' -d '{\"query\": \"Hello\"}'"
}

# Function to show help
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --frontend-only    Build and push only frontend image"
    echo "  --backend-only     Build and push only backend image"
    echo "  --tag <tag>        Image tag to use (default: $IMAGE_TAG)"
    echo "  --api-url <url>    Frontend NEXT_PUBLIC_API_BASE_URL to bake at build time"
    echo "  --no-update        Skip updating web apps"
    echo "  --no-restart       Skip restarting web apps"
    echo "  --help             Show this help message"
    echo
    echo "Examples:"
    echo "  $0                                    # Build and push both images"
    echo "  $0 --frontend-only                   # Build and push only frontend"
    echo "  $0 --backend-only --no-restart       # Build and push backend without restarting"
}

# Parse command line arguments
FRONTEND_ONLY=false
BACKEND_ONLY=false
NO_UPDATE=false
NO_RESTART=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --frontend-only)
            FRONTEND_ONLY=true
            shift
            ;;
        --backend-only)
            BACKEND_ONLY=true
            shift
            ;;
        --api-url)
            FRONTEND_API_URL="$2"
            shift 2
            ;;
        --tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --no-update)
            NO_UPDATE=true
            shift
            ;;
        --no-restart)
            NO_RESTART=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
main() {
    print_status "Starting Docker build and push for Charlotte application"
    
    check_docker
    check_azure_cli
    login_to_acr
    get_acr_server
    ensure_buildx
    
    if [[ "$BACKEND_ONLY" == false ]]; then
        build_and_push_frontend
    fi
    
    if [[ "$FRONTEND_ONLY" == false ]]; then
        build_and_push_backend
    fi
    
    if [[ "$NO_UPDATE" == false ]]; then
        update_web_apps
    fi
    
    if [[ "$NO_RESTART" == false ]]; then
        restart_web_apps
    fi
    
    display_deployment_info
    
    print_status "Docker build and push script completed successfully!"
}

# Run main function
main "$@"

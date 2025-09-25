#!/bin/bash

# Docker Build and Push Script for Charlotte Application
# This script builds and pushes both frontend and backend images to Azure Container Registry

set -e

# Configuration variables
ACR_NAME="charlotteacr"
RESOURCE_GROUP="rg-primary-unc-foit-charlotte-ai"
IMAGE_TAG="${IMAGE_TAG:-1.0.0}"

# Frontend environment variables
NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-https://charlotte-backend-app.azurewebsites.net}"

# Backend environment variables
AZURE_SEARCH_ENDPOINT="${AZURE_SEARCH_ENDPOINT:-}"
AZURE_SEARCH_API_KEY="${AZURE_SEARCH_API_KEY:-}"
AZURE_SEARCH_INDEX_NAME="${AZURE_SEARCH_INDEX_NAME:-edi-transactions}"
AZURE_AI_PROJECT_ENDPOINT="${AZURE_AI_PROJECT_ENDPOINT:-}"
AZURE_AD_TENANT_ID="${AZURE_AD_TENANT_ID:-}"
AZURE_AD_CLIENT_ID="${AZURE_AD_CLIENT_ID:-}"
AZURE_AD_CLIENT_SECRET="${AZURE_AD_CLIENT_SECRET:-}"
AZURE_AGENT_ID="${AZURE_AGENT_ID:-}"
AZURE_OPENAI_KEY="${AZURE_OPENAI_KEY:-}"
SMALL_MODEL_NAME="${SMALL_MODEL_NAME:-gpt-4o-mini}"
AZURE_AI_RESOURCE_ENDPOINT="${AZURE_AI_RESOURCE_ENDPOINT:-}"
AZURE_AD_REDIRECT_URI="${AZURE_AD_REDIRECT_URI:-https://charlotte-backend-app.azurewebsites.net/auth/callback}"
AZURE_STORAGE_CONTAINER_NAME="${AZURE_STORAGE_CONTAINER_NAME:-edi-reports}"
EDI_JSON_OUTPUT_CONTAINER="${EDI_JSON_OUTPUT_CONTAINER:-edi-json-structured}"
AZURE_STORAGE_CONNECTION_STRING="${AZURE_STORAGE_CONNECTION_STRING:-}"
AZURE_STORAGE_ACCOUNT_NAME="${AZURE_STORAGE_ACCOUNT_NAME:-}"
AZURE_STORAGE_KEY="${AZURE_STORAGE_KEY:-}"

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

# Function to load environment variables from .env files
load_env_files() {
    print_status "Loading environment variables from .env files..."
    
    # Load frontend environment variables
    if [[ -f ".env.local" ]]; then
        print_status "Loading frontend variables from .env.local..."
        set -a  # automatically export all variables
        source .env.local
        set +a  # stop auto-exporting
    else
        print_warning ".env.local not found, skipping frontend env vars"
    fi
    
    # Load backend environment variables
    if [[ -f "backend/.env" ]]; then
        print_status "Loading backend variables from backend/.env..."
        set -a  # automatically export all variables
        source backend/.env
        set +a  # stop auto-exporting
    else
        print_warning "backend/.env not found, skipping backend env vars"
    fi
    
    print_status "Environment variables loaded from files"
}

# Function to validate environment variables
validate_env_vars() {
    print_status "Validating environment variables..."
    
    # Required for frontend
    if [[ -z "$NEXT_PUBLIC_API_BASE_URL" ]]; then
        print_warning "NEXT_PUBLIC_API_BASE_URL not set, using default: https://charlotte-backend-app.azurewebsites.net"
        NEXT_PUBLIC_API_BASE_URL="https://charlotte-backend-app.azurewebsites.net"
    fi
    
    # Check for required backend environment variables
    local missing_vars=()
    
    [[ -z "$AZURE_SEARCH_ENDPOINT" ]] && missing_vars+=("AZURE_SEARCH_ENDPOINT")
    [[ -z "$AZURE_SEARCH_API_KEY" ]] && missing_vars+=("AZURE_SEARCH_API_KEY")
    [[ -z "$AZURE_AI_PROJECT_ENDPOINT" ]] && missing_vars+=("AZURE_AI_PROJECT_ENDPOINT")
    [[ -z "$AZURE_AD_TENANT_ID" ]] && missing_vars+=("AZURE_AD_TENANT_ID")
    [[ -z "$AZURE_AD_CLIENT_ID" ]] && missing_vars+=("AZURE_AD_CLIENT_ID")
    [[ -z "$AZURE_AD_CLIENT_SECRET" ]] && missing_vars+=("AZURE_AD_CLIENT_SECRET")
    [[ -z "$AZURE_AGENT_ID" ]] && missing_vars+=("AZURE_AGENT_ID")
    [[ -z "$AZURE_OPENAI_KEY" ]] && missing_vars+=("AZURE_OPENAI_KEY")
    [[ -z "$AZURE_AI_RESOURCE_ENDPOINT" ]] && missing_vars+=("AZURE_AI_RESOURCE_ENDPOINT")
    [[ -z "$AZURE_STORAGE_CONNECTION_STRING" ]] && missing_vars+=("AZURE_STORAGE_CONNECTION_STRING")
    [[ -z "$AZURE_STORAGE_ACCOUNT_NAME" ]] && missing_vars+=("AZURE_STORAGE_ACCOUNT_NAME")
    [[ -z "$AZURE_STORAGE_KEY" ]] && missing_vars+=("AZURE_STORAGE_KEY")
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        print_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        echo
        print_error "Please set these environment variables before running the script."
        print_error "You can source them from your .env files or set them manually:"
        print_error "  source backend/.env && export \$(grep -v '^#' backend/.env | xargs)"
        exit 1
    fi
    
    print_status "Environment variables validated"
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
        --build-arg NEXT_PUBLIC_API_BASE_URL="$NEXT_PUBLIC_API_BASE_URL" \
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

# Function to update web apps with new images and environment variables
update_web_apps() {
    print_status "Updating web apps with new images and environment variables..."
    
    # Update frontend web app
    print_status "Updating frontend web app..."
    az webapp config container set \
        --name "charlotte-frontend" \
        --resource-group "$RESOURCE_GROUP" \
        --container-image-name "$ACR_SERVER/charlotte-frontend:$IMAGE_TAG" \
        --container-registry-url "https://$ACR_SERVER"
    
    # Set frontend environment variables
    print_status "Setting frontend environment variables..."
    az webapp config appsettings set \
        --name "charlotte-frontend" \
        --resource-group "$RESOURCE_GROUP" \
        --settings \
            "NEXT_PUBLIC_API_BASE_URL=https://charlotte-backend.azurewebsites.net" \
            "NODE_ENV=production"
    
    # Update backend web app
    print_status "Updating backend web app..."
    az webapp config container set \
        --name "charlotte-backend" \
        --resource-group "$RESOURCE_GROUP" \
        --container-image-name "$ACR_SERVER/charlotte-backend:$IMAGE_TAG" \
        --container-registry-url "https://$ACR_SERVER"
    
    # Set backend environment variables
    print_status "Setting backend environment variables..."
    az webapp config appsettings set \
        --name "charlotte-backend" \
        --resource-group "$RESOURCE_GROUP" \
        --settings \
            "AZURE_SEARCH_ENDPOINT=$AZURE_SEARCH_ENDPOINT" \
            "AZURE_SEARCH_API_KEY=$AZURE_SEARCH_API_KEY" \
            "AZURE_SEARCH_INDEX_NAME=$AZURE_SEARCH_INDEX_NAME" \
            "AZURE_AI_PROJECT_ENDPOINT=$AZURE_AI_PROJECT_ENDPOINT" \
            "AZURE_AD_TENANT_ID=$AZURE_AD_TENANT_ID" \
            "AZURE_AD_CLIENT_ID=$AZURE_AD_CLIENT_ID" \
            "AZURE_AD_CLIENT_SECRET=$AZURE_AD_CLIENT_SECRET" \
            "AZURE_AGENT_ID=$AZURE_AGENT_ID" \
            "AZURE_OPENAI_KEY=$AZURE_OPENAI_KEY" \
            "SMALL_MODEL_NAME=$SMALL_MODEL_NAME" \
            "AZURE_AI_RESOURCE_ENDPOINT=$AZURE_AI_RESOURCE_ENDPOINT" \
            "AZURE_AD_REDIRECT_URI=$AZURE_AD_REDIRECT_URI" \
            "AZURE_STORAGE_CONTAINER_NAME=$AZURE_STORAGE_CONTAINER_NAME" \
            "EDI_JSON_OUTPUT_CONTAINER=$EDI_JSON_OUTPUT_CONTAINER" \
            "AZURE_STORAGE_CONNECTION_STRING=$AZURE_STORAGE_CONNECTION_STRING" \
            "AZURE_STORAGE_ACCOUNT_NAME=$AZURE_STORAGE_ACCOUNT_NAME" \
            "AZURE_STORAGE_KEY=$AZURE_STORAGE_KEY" \
            "PYTHONDONTWRITEBYTECODE=1" \
            "PYTHONUNBUFFERED=1" \
            "NEXT_PUBLIC_API_BASE_URL=https://charlotte-backend.azurewebsites.net"
    
    print_status "Web apps updated successfully"
}

# Function to restart web apps
restart_web_apps() {
    print_status "Restarting web apps..."
    
    az webapp restart --resource-group "$RESOURCE_GROUP" --name "charlotte-frontend"
    az webapp restart --resource-group "$RESOURCE_GROUP" --name "charlotte-backend"
    
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
    echo "Frontend: https://charlotte-frontend.azurewebsites.net"
    echo "Backend: https://charlotte-backend.azurewebsites.net"
    echo "Backend API Docs: https://charlotte-backend.azurewebsites.net/docs"
    echo
    echo "=== Testing Commands ==="
    echo "Test frontend: curl https://charlotte-frontend.azurewebsites.net"
    echo "Test backend: curl https://charlotte-backend.azurewebsites.net/docs"
    echo "Test API: curl -X POST https://charlotte-backend.azurewebsites.net/api/query -H 'Content-Type: application/json' -d '{\"query\": \"Hello\"}'"
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
    echo "  --load-env         Automatically load environment variables from .env files"
    echo "  --function <name>  Run only a specific function (validate_env_vars, update_web_apps, restart_web_apps, etc.)"
    echo "  --help             Show this help message"
    echo
    echo "Environment Variables:"
    echo "  Frontend (build-time):"
    echo "    NEXT_PUBLIC_API_BASE_URL  Backend API URL (default: https://charlotte-backend.azurewebsites.net)"
    echo
    echo "  Backend (required for Azure Web App configuration):"
    echo "    AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_API_KEY, AZURE_SEARCH_INDEX_NAME"
    echo "    AZURE_AI_PROJECT_ENDPOINT, AZURE_AD_TENANT_ID, AZURE_AD_CLIENT_ID"
    echo "    AZURE_AD_CLIENT_SECRET, AZURE_AGENT_ID, AZURE_OPENAI_KEY"
    echo "    AZURE_AI_RESOURCE_ENDPOINT, AZURE_AD_REDIRECT_URI"
    echo "    AZURE_STORAGE_CONNECTION_STRING, AZURE_STORAGE_ACCOUNT_NAME, AZURE_STORAGE_KEY"
    echo
    echo "  To load environment variables from .env files:"
    echo "    source backend/.env && export \$(grep -v '^#' backend/.env | xargs)"
    echo
    echo "Examples:"
    echo "  $0 --load-env                        # Load env vars from .env files and build both images"
    echo "  $0 --frontend-only                   # Build and push only frontend"
    echo "  $0 --backend-only --no-restart       # Build and push backend without restarting"
    echo "  $0 --load-env --frontend-only        # Load env vars and build only frontend"
    echo "  $0 --load-env --function update_web_apps    # Run only the update_web_apps function"
    echo "  $0 --function validate_env_vars      # Run only environment validation"
    echo "  NEXT_PUBLIC_API_BASE_URL=https://my-api.com $0 --frontend-only"
}

# Parse command line arguments
FRONTEND_ONLY=false
BACKEND_ONLY=false
NO_UPDATE=false
NO_RESTART=false
LOAD_ENV=false
RUN_FUNCTION=""

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
            NEXT_PUBLIC_API_BASE_URL="$2"
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
        --load-env)
            LOAD_ENV=true
            shift
            ;;
        --function)
            RUN_FUNCTION="$2"
            shift 2
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

# Function to run a specific function
run_specific_function() {
    local func_name="$1"
    
    # Load environment variables if requested
    if [[ "$LOAD_ENV" == true ]]; then
        load_env_files
    fi
    
    # Basic setup for most functions
    if [[ "$func_name" != "validate_env_vars" && "$func_name" != "load_env_files" ]]; then
        validate_env_vars
    fi
    
    if [[ "$func_name" == "update_web_apps" || "$func_name" == "restart_web_apps" ]]; then
        check_azure_cli
        login_to_acr
        get_acr_server
    fi
    
    # Call the specific function
    case "$func_name" in
        validate_env_vars|load_env_files|check_docker|check_azure_cli|login_to_acr|get_acr_server|ensure_buildx|build_and_push_frontend|build_and_push_backend|update_web_apps|restart_web_apps|display_deployment_info)
            print_status "Running function: $func_name"
            $func_name
            print_status "Function $func_name completed successfully!"
            ;;
        *)
            print_error "Unknown function: $func_name"
            print_error "Available functions: validate_env_vars, load_env_files, check_docker, check_azure_cli, login_to_acr, get_acr_server, ensure_buildx, build_and_push_frontend, build_and_push_backend, update_web_apps, restart_web_apps, display_deployment_info"
            exit 1
            ;;
    esac
}

# Main execution
main() {
    # If a specific function was requested, run only that
    if [[ -n "$RUN_FUNCTION" ]]; then
        run_specific_function "$RUN_FUNCTION"
        return
    fi
    
    print_status "Starting Docker build and push for Charlotte application"
    
    # Load environment variables if requested
    if [[ "$LOAD_ENV" == true ]]; then
        load_env_files
    fi
    
    check_docker
    check_azure_cli
    validate_env_vars
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

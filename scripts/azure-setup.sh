#!/bin/bash

# Azure Deployment Script for Charlotte Application
# This script automates the Azure resource provisioning

set -e

# Configuration variables
RESOURCE_GROUP="charlotte-rg"
LOCATION="eastus"
ACR_NAME="charlotteacr"
APP_PLAN_NAME="charlotte-plan"
FRONTEND_APP_NAME="charlotte-frontend-app"
BACKEND_APP_NAME="charlotte-backend-app"
INSIGHTS_NAME="charlotte-insights"
STORAGE_ACCOUNT_NAME="edireportstorage"
SEARCH_SERVICE_NAME="edi-search-service"
AI_ACCOUNT_NAME="charlotte-resource"

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

# Function to check if Azure CLI is installed
check_azure_cli() {
    if ! command -v az &> /dev/null; then
        print_error "Azure CLI is not installed. Please install it first."
        exit 1
    fi
    print_status "Azure CLI is installed"
}

# Function to check if user is logged in
check_azure_login() {
    if ! az account show &> /dev/null; then
        print_error "Not logged in to Azure. Please run 'az login' first."
        exit 1
    fi
    print_status "Logged in to Azure"
}

# Function to set subscription
set_subscription() {
    print_status "Setting Azure subscription..."
    read -p "Enter your Azure subscription ID: " SUBSCRIPTION_ID
    az account set --subscription "$SUBSCRIPTION_ID"
    print_status "Subscription set to: $SUBSCRIPTION_ID"
}

# Function to create resource group
create_resource_group() {
    print_status "Creating resource group: $RESOURCE_GROUP"
    az group create \
        --name "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --output table
    print_status "Resource group created successfully"
}

# Function to create Azure Container Registry
create_acr() {
    print_status "Creating Azure Container Registry: $ACR_NAME"
    az acr create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$ACR_NAME" \
        --sku "Basic" \
        --admin-enabled false \
        --output table
    print_status "ACR created successfully"
    
    # Get ACR login server
    ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer --output tsv)
    print_status "ACR login server: $ACR_LOGIN_SERVER"
}

# Function to create App Service Plan
create_app_service_plan() {
    print_status "Creating App Service Plan: $APP_PLAN_NAME"
    az appservice plan create \
        --name "$APP_PLAN_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --sku "B1" \
        --is-linux \
        --output table
    print_status "App Service Plan created successfully"
}

# Function to create Application Insights
create_application_insights() {
    print_status "Creating Application Insights: $INSIGHTS_NAME"
    az monitor app-insights component create \
        --app "$INSIGHTS_NAME" \
        --location "$LOCATION" \
        --resource-group "$RESOURCE_GROUP" \
        --output table
    print_status "Application Insights created successfully"
}

# Function to create frontend web app
create_frontend_app() {
    print_status "Creating frontend web app: $FRONTEND_APP_NAME"
    az webapp create \
        --resource-group "$RESOURCE_GROUP" \
        --plan "$APP_PLAN_NAME" \
        --name "$FRONTEND_APP_NAME" \
        --deployment-container-image-name "nginx:latest" \
        --output table
    az webapp identity assign -g "$RESOURCE_GROUP" -n "$FRONTEND_APP_NAME" >/dev/null
    print_status "Frontend web app created successfully"
}

# Function to create backend web app
create_backend_app() {
    print_status "Creating backend web app: $BACKEND_APP_NAME"
    az webapp create \
        --resource-group "$RESOURCE_GROUP" \
        --plan "$APP_PLAN_NAME" \
        --name "$BACKEND_APP_NAME" \
        --deployment-container-image-name "nginx:latest" \
        --output table
    az webapp identity assign -g "$RESOURCE_GROUP" -n "$BACKEND_APP_NAME" >/dev/null
    print_status "Backend web app created successfully"
}

# Function to configure ACR integration
configure_acr_integration() {
    print_status "Configuring ACR integration and granting AcrPull via managed identity..."

    # Assign AcrPull to both web apps' identities
    ACR_ID=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query id -o tsv)
    FRONTEND_PRINCIPAL_ID=$(az webapp identity show -g "$RESOURCE_GROUP" -n "$FRONTEND_APP_NAME" --query principalId -o tsv)
    BACKEND_PRINCIPAL_ID=$(az webapp identity show -g "$RESOURCE_GROUP" -n "$BACKEND_APP_NAME" --query principalId -o tsv)

    az role assignment create --assignee-object-id "$FRONTEND_PRINCIPAL_ID" --assignee-principal-type ServicePrincipal --role AcrPull --scope "$ACR_ID" >/dev/null || true
    az role assignment create --assignee-object-id "$BACKEND_PRINCIPAL_ID"  --assignee-principal-type ServicePrincipal --role AcrPull --scope "$ACR_ID" >/dev/null || true

    # Configure container settings without credentials (managed identity)
    az webapp config container set \
        --name "$FRONTEND_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --docker-custom-image-name "$ACR_NAME.azurecr.io/charlotte-frontend:latest" \
        --docker-registry-server-url "https://$ACR_NAME.azurecr.io"

    az webapp config container set \
        --name "$BACKEND_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --docker-custom-image-name "$ACR_NAME.azurecr.io/charlotte-backend:latest" \
        --docker-registry-server-url "https://$ACR_NAME.azurecr.io"

    print_status "ACR integration configured successfully (managed identity)"
}

# Function to configure environment variables
configure_environment_variables() {
    print_status "Configuring environment variables..."
    
    # Get backend URL
    BACKEND_URL="https://$BACKEND_APP_NAME.azurewebsites.net"
    
    # Configure frontend environment variables
    az webapp config appsettings set \
        --resource-group "$RESOURCE_GROUP" \
        --name "$FRONTEND_APP_NAME" \
        --settings \
            NODE_ENV=production \
            NEXT_PUBLIC_API_URL="$BACKEND_URL"
    
    # Configure backend environment variables
    print_warning "Please configure the following environment variables for the backend:"
    echo "AZURE_AI_ENDPOINT"
    echo "AZURE_AGENT_ID"
    
    read -p "Do you want to configure these now? (y/n): " configure_now
    
    if [[ $configure_now == "y" || $configure_now == "Y" ]]; then
        read -p "Enter AZURE_AI_ENDPOINT: " AI_ENDPOINT
        read -p "Enter AZURE_AGENT_ID: " AGENT_ID
        
        az webapp config appsettings set \
            --resource-group "$RESOURCE_GROUP" \
            --name "$BACKEND_APP_NAME" \
            --settings \
                AZURE_AI_ENDPOINT="$AI_ENDPOINT" \
                AZURE_AGENT_ID="$AGENT_ID"
        
        print_status "Backend environment variables configured"
    else
        print_warning "Skipping backend environment variable configuration"
    fi
}

# Function to create supporting services (Storage, Search, Azure AI)
create_supporting_services() {
    print_status "Creating Storage Account: $STORAGE_ACCOUNT_NAME"
    az storage account create \
        --name "$STORAGE_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --sku Standard_LRS \
        --kind StorageV2 \
        --output table

    print_status "Creating blob containers"
    az storage container create --account-name "$STORAGE_ACCOUNT_NAME" --name "edi-reports" --auth-mode login >/dev/null
    az storage container create --account-name "$STORAGE_ACCOUNT_NAME" --name "edi-json-structured" --auth-mode login >/dev/null

    print_status "Creating Azure AI Search service (Free): $SEARCH_SERVICE_NAME"
    az search service create \
        --name "$SEARCH_SERVICE_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --sku free \
        --location "eastus2" \
        --output table

    print_status "Creating Azure AI (AIServices S0): $AI_ACCOUNT_NAME"
    az cognitiveservices account create \
        --name "$AI_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "eastus2" \
        --kind AIServices \
        --sku S0 \
        --yes \
        --output table
}

# Function to enable HTTPS
enable_https() {
    print_status "Enabling HTTPS for web apps..."
    
    az webapp update \
        --resource-group "$RESOURCE_GROUP" \
        --name "$FRONTEND_APP_NAME" \
        --https-only true
    
    az webapp update \
        --resource-group "$RESOURCE_GROUP" \
        --name "$BACKEND_APP_NAME" \
        --https-only true
    
    print_status "HTTPS enabled for both web apps"
}

# Function to display deployment information
display_deployment_info() {
    print_status "Deployment completed successfully!"
    echo
    echo "=== Deployment Information ==="
    echo "Resource Group: $RESOURCE_GROUP"
    echo "Location: $LOCATION"
    echo "ACR Name: $ACR_NAME"
    echo "Frontend URL: https://$FRONTEND_APP_NAME.azurewebsites.net"
    echo "Backend URL: https://$BACKEND_APP_NAME.azurewebsites.net"
    echo
    echo "=== Next Steps ==="
    echo "1. Build and push Docker images to ACR"
    echo "2. Configure CORS settings in backend"
    echo "3. Test the deployment"
    echo "4. Set up monitoring and alerts"
    echo
    echo "=== Docker Commands ==="
    echo "Login to ACR: az acr login --name $ACR_NAME"
    echo "Build frontend: docker build -t $ACR_NAME.azurecr.io/charlotte-frontend:latest ."
    echo "Push frontend: docker push $ACR_NAME.azurecr.io/charlotte-frontend:latest"
    echo "Build backend: cd backend && docker build -t $ACR_NAME.azurecr.io/charlotte-backend:latest ."
    echo "Push backend: docker push $ACR_NAME.azurecr.io/charlotte-backend:latest"
}

# Main execution
main() {
    print_status "Starting Azure deployment for Charlotte application"
    
    check_azure_cli
    check_azure_login
    set_subscription
    create_resource_group
    create_acr
    create_app_service_plan
    create_supporting_services
    create_application_insights
    create_frontend_app
    create_backend_app
    configure_acr_integration
    configure_environment_variables
    enable_https
    display_deployment_info
    
    print_status "Azure deployment script completed successfully!"
}

# Run main function
main "$@"

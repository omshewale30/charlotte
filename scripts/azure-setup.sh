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
        --admin-enabled true \
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
    print_status "Backend web app created successfully"
}

# Function to configure ACR integration
configure_acr_integration() {
    print_status "Configuring ACR integration..."
    
    # Get ACR credentials
    ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query username --output tsv)
    ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query passwords[0].value --output tsv)
    
    # Configure frontend ACR integration
    az webapp config container set \
        --name "$FRONTEND_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --docker-custom-image-name "$ACR_NAME.azurecr.io/charlotte-frontend:latest" \
        --docker-registry-server-url "https://$ACR_NAME.azurecr.io" \
        --docker-registry-server-user "$ACR_USERNAME" \
        --docker-registry-server-password "$ACR_PASSWORD"
    
    # Configure backend ACR integration
    az webapp config container set \
        --name "$BACKEND_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --docker-custom-image-name "$ACR_NAME.azurecr.io/charlotte-backend:latest" \
        --docker-registry-server-url "https://$ACR_NAME.azurecr.io" \
        --docker-registry-server-user "$ACR_USERNAME" \
        --docker-registry-server-password "$ACR_PASSWORD"
    
    print_status "ACR integration configured successfully"
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
    echo "AZURE_TENANT_ID"
    echo "AZURE_CLIENT_ID"
    echo "AZURE_CLIENT_SECRET"
    echo "AZURE_AGENT_ID"
    
    read -p "Do you want to configure these now? (y/n): " configure_now
    
    if [[ $configure_now == "y" || $configure_now == "Y" ]]; then
        read -p "Enter AZURE_AI_ENDPOINT: " AI_ENDPOINT
        read -p "Enter AZURE_TENANT_ID: " TENANT_ID
        read -p "Enter AZURE_CLIENT_ID: " CLIENT_ID
        read -s -p "Enter AZURE_CLIENT_SECRET: " CLIENT_SECRET
        echo
        read -p "Enter AZURE_AGENT_ID: " AGENT_ID
        
        az webapp config appsettings set \
            --resource-group "$RESOURCE_GROUP" \
            --name "$BACKEND_APP_NAME" \
            --settings \
                AZURE_AI_ENDPOINT="$AI_ENDPOINT" \
                AZURE_TENANT_ID="$TENANT_ID" \
                AZURE_CLIENT_ID="$CLIENT_ID" \
                AZURE_CLIENT_SECRET="$CLIENT_SECRET" \
                AZURE_AGENT_ID="$AGENT_ID"
        
        print_status "Backend environment variables configured"
    else
        print_warning "Skipping backend environment variable configuration"
    fi
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

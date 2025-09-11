# Azure Deployment Roadmap for Charlotte Application

## Overview
This roadmap provides step-by-step instructions for deploying the Charlotte Next.js frontend and FastAPI backend to Azure using Azure Container Registry (ACR) and Azure Web Apps. It uses system-assigned managed identities (no user-assigned identities) and cost-conscious SKUs to keep monthly spend under $100.

## Prerequisites
- Azure CLI installed and configured
- Docker installed locally
- Azure subscription with appropriate permissions
- Environment variables for Azure AI services configured

## Architecture
- **Frontend**: Next.js application deployed on Azure Web App for Containers
- **Backend**: FastAPI application deployed on Azure Web App for Containers
- **Container Registry**: Azure Container Registry (ACR) for storing Docker images
- **Resource Group**: New resource group for all resources
- **Networking**: VNet integration for secure communication
- **Storage**: Azure Storage Account for documents and processed data (Standard LRS)
- **Search**: Azure AI Search service (Free tier)
- **Azure AI**: Azure AI (Cognitive Services) account for model deployments (S0, pay-as-you-go)

## Step-by-Step Deployment Guide

### Phase 1: Azure Setup and Resource Group Creation

#### 1.1 Login to Azure and Set Subscription
```bash
# Login to Azure
az login

# List available subscriptions
az account list --output table

# Set the target subscription (replace with your subscription ID)
az account set --subscription "your-subscription-id"

# If subscription not found error occurs, use subscription ID directly:
az account set --subscription "b4c2bcf7-cfaa-4c3e-b0c9-da3414f6ac0b"

# Verify current subscription
az account show
```

#### 1.2 Create Resource Group
```bash
# Create resource group in East US region
az group create \
  --name "charlotte-rg" \
  --location "eastus"

# Verify resource group creation
az group show --name "charlotte-rg"
```

### Phase 2: Azure Container Registry Setup

#### 2.1 Create Azure Container Registry
```bash
# Create ACR (replace with unique name)
az acr create \
  --resource-group "charlotte-rg" \
  --name "charlotteacr" \
  --sku "Basic" \
  --admin-enabled true

# Get ACR login server
az acr show --name "charlotteacr" --query loginServer --output tsv
```

#### 2.2 Login to ACR
```bash
# Login to ACR
az acr login --name "charlotteacr"

# Get ACR credentials
az acr credential show --name "charlotteacr"
```

### Phase 3: Build and Push Docker Images

#### 3.1 Build and Push Frontend Image
```bash
# Navigate to project root
cd /path/to/charlotte

# Build frontend image
docker build -t charlotte-frontend .

# Tag for ACR
docker tag charlotte-frontend charlotteacr.azurecr.io/charlotte-frontend:latest

# Push to ACR
docker push charlotteacr.azurecr.io/charlotte-frontend:latest
```

#### 3.2 Build and Push Backend Image
```bash
# Navigate to backend directory
cd backend

# Build backend image
docker build -t charlotte-backend .

# Tag for ACR
docker tag charlotte-backend charlotteacr.azurecr.io/charlotte-backend:latest

# Push to ACR
docker push charlotteacr.azurecr.io/charlotte-backend:latest
```

### Phase 4: Azure Web Apps Creation (System-Assigned Identity)

#### 4.1 Create App Service Plan
```bash
# Create App Service Plan (B1 tier; both apps share the same plan)
az appservice plan create \
  --name "charlotte-plan" \
  --resource-group "charlotte-rg" \
  --sku "B1" \
  --is-linux \
  --location "eastus2"
```

#### 4.2 Create Frontend Web App
```bash
# Create frontend web app with admin credentials (workaround for permissions)
az webapp create \
    --resource-group "rg-primary-unc-foit-charlotte-ai" \
    --plan "charlotte-plan" \
    --name "charlotte-frontend" \
    --deployment-container-image-name "charlotteacr.azurecr.io/charlotte-frontend:latest" \
    --https-only true

# Get ACR admin credentials
az acr credential show --name charlotteacr

# Configure container with admin credentials
az webapp config container set \
    --resource-group "rg-primary-unc-foit-charlotte-ai" \
    --name "charlotte-frontend" \
    --container-image-name "charlotteacr.azurecr.io/charlotte-frontend:latest" \
    --container-registry-url "https://charlotteacr.azurecr.io" \
    --container-registry-user <username_from_above> \
    --container-registry-password <password_from_above>
```

#### 4.3 Create Backend Web App
```bash
# Create backend web app with admin credentials (workaround for permissions)
az webapp create \
    --resource-group "rg-primary-unc-foit-charlotte-ai" \
    --plan "charlotte-plan" \
    --name "charlotte-backend" \
    --deployment-container-image-name "charlotteacr.azurecr.io/charlotte-backend:latest" \
    --https-only true

# Configure container with admin credentials (use same credentials from above)
az webapp config container set \
    --resource-group "rg-primary-unc-foit-charlotte-ai" \
    --name "charlotte-backend" \
    --container-image-name "charlotteacr.azurecr.io/charlotte-backend:latest" \
    --container-registry-url "https://charlotteacr.azurecr.io" \
    --container-registry-user <username_from_above> \
    --container-registry-password <password_from_above>
```

### Phase 4.4: Authentication Method Used
**Note**: Using ACR admin credentials instead of managed identity due to permission limitations.

**Alternative: Managed Identity (requires admin permissions)**
```bash
# If you have admin permissions, you can use managed identity instead:
# Get ACR resource ID
ACR_ID=$(az acr show --name "charlotteacr" --resource-group "charlotte-rg" --query id -o tsv)

# Get principal IDs of web apps' managed identities
FRONTEND_PRINCIPAL_ID=$(az webapp identity show -g "charlotte-rg" -n "charlotte-frontend-app" --query principalId -o tsv)
BACKEND_PRINCIPAL_ID=$(az webapp identity show -g "charlotte-rg" -n "charlotte-backend-app" --query principalId -o tsv)

# Assign AcrPull at ACR scope
az role assignment create --assignee-object-id "$FRONTEND_PRINCIPAL_ID" --assignee-principal-type ServicePrincipal --role AcrPull --scope "$ACR_ID"
az role assignment create --assignee-object-id "$BACKEND_PRINCIPAL_ID"  --assignee-principal-type ServicePrincipal --role AcrPull --scope "$ACR_ID"
```

### Phase 5: Configure Web Apps

#### 5.1 Configure ACR Integration
```bash
# Configure ACR integration for frontend using managed identity (no username/password)
az webapp config container set \
  --name "charlotte-frontend-app" \
  --resource-group "charlotte-rg" \
  --docker-custom-image-name "charlotteacr.azurecr.io/charlotte-frontend:latest" \
  --docker-registry-server-url "https://charlotteacr.azurecr.io"

# Configure ACR integration for backend using managed identity (no username/password)
az webapp config container set \
  --name "charlotte-backend-app" \
  --resource-group "charlotte-rg" \
  --docker-custom-image-name "charlotteacr.azurecr.io/charlotte-backend:latest" \
  --docker-registry-server-url "https://charlotteacr.azurecr.io"

```

#### 5.2 Create Storage, Search, and Azure AI resources
```bash
# Storage Account (Standard LRS)
az storage account create \
  --name "edireportstorage" \
  --resource-group "rg-primary-unc-foit-charlotte-ai" \
  --location "eastus" \
  --sku Standard_LRS \
  --kind StorageV2

# Create blob containers
az storage container create --account-name "edireportstorage" --name "edi-reports" --auth-mode login
az storage container create --account-name "edireportstorage" --name "edi-json-structured" --auth-mode login

# Azure AI Search (Free tier)
az search service create \
  --name "edi-search-service" \
  --resource-group "rg-primary-unc-foit-charlotte-ai" \
  --sku free \
  --location "eastus2"

# Azure AI (Cognitive Services) account (AIServices, S0)
az cognitiveservices account create \
  --name "charlotte-resource" \
  --resource-group "rg-primary-unc-foit-charlotte-ai" \
  --location "eastus2" \
  --kind AIServices \
  --sku S0 \
  --yes
```

#### 5.2 Configure Environment Variables

**Frontend Environment Variables:**
```bash
# Set frontend environment variables
az webapp config appsettings set \
  --resource-group "charlotte-rg" \
  --name "charlotte-frontend-app" \
  --settings \
    NODE_ENV=production \
    NEXT_PUBLIC_API_URL=https://charlotte-backend-app.azurewebsites.net
```

**Backend Environment Variables:**
```bash
# Set backend environment variables
az webapp config appsettings set \
  --resource-group "charlotte-rg" \
  --name "charlotte-backend-app" \
  --settings \
    AZURE_AI_ENDPOINT="your-azure-ai-endpoint" \
    AZURE_AGENT_ID="your-agent-id"
# Note: Using system-assigned identity for auth; no client secret needed.
```

### Phase 6: Configure CORS and Networking

#### 6.1 Update Backend CORS Settings
```bash
# Update CORS to allow frontend domain
az webapp config appsettings set \
  --resource-group "charlotte-rg" \
  --name "charlotte-backend-app" \
  --settings \
    CORS_ORIGINS="https://charlotte-frontend-app.azurewebsites.net"
```

#### 6.2 Configure Custom Domains (Optional)
```bash
# Add custom domain for frontend
az webapp config hostname add \
  --webapp-name "charlotte-frontend-app" \
  --resource-group "charlotte-rg" \
  --hostname "your-domain.com"

# Add custom domain for backend
az webapp config hostname add \
  --webapp-name "charlotte-backend-app" \
  --resource-group "charlotte-rg" \
  --hostname "api.your-domain.com"
```

### Phase 7: SSL Certificate and Security



#### 7.2 Configure Authentication (Optional)
```bash
# Enable Azure AD authentication for frontend
az webapp auth update \
  --resource-group "charlotte-rg" \
  --name "charlotte-frontend-app" \
  --enabled true \
  --action LoginWithAzureActiveDirectory \
  --aad-client-id "your-app-registration-client-id"
```

### Phase 8: Monitoring and Logging

#### 8.1 Create Application Insights
```bash
# Create Application Insights
az monitor app-insights component create \
  --app "charlotte-insights" \
  --location "eastus" \
  --resource-group "charlotte-rg"

# Get instrumentation key
az monitor app-insights component show \
  --app "charlotte-insights" \
  --resource-group "charlotte-rg" \
  --query instrumentationKey --output tsv
```

#### 8.2 Configure Logging
```bash
# Enable application logging for frontend
az webapp log config \
  --resource-group "charlotte-rg" \
  --name "charlotte-frontend-app" \
  --application-logging true \
  --level information

# Enable application logging for backend
az webapp log config \
  --resource-group "charlotte-rg" \
  --name "charlotte-backend-app" \
  --application-logging true \
  --level information
```

### Phase 9: Deployment and Testing

#### 9.1 Deploy Applications
```bash
# Restart web apps to ensure latest configuration
az webapp restart --resource-group "charlotte-rg" --name "charlotte-frontend-app"
az webapp restart --resource-group "charlotte-rg" --name "charlotte-backend-app"
```

#### 9.2 Test Deployment
```bash
# Get frontend URL
az webapp show --resource-group "charlotte-rg" --name "charlotte-frontend-app" --query defaultHostName --output tsv

# Get backend URL
az webapp show --resource-group "charlotte-rg" --name "charlotte-backend-app" --query defaultHostName --output tsv

# Test backend health
curl https://charlotte-backend-app.azurewebsites.net/docs

# Test frontend
curl https://charlotte-frontend-app.azurewebsites.net
```

### Phase 10: CI/CD Pipeline (Optional)

#### 10.1 Create GitHub Actions Workflow
Create `.github/workflows/deploy.yml`:
```yaml
name: Deploy to Azure

on:
  push:
    branches: [ main ]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Login to Azure
      uses: azure/login@v1
      with:
        creds: ${{ secrets.AZURE_CREDENTIALS }}
    
    - name: Build and push frontend
      run: |
        docker build -t charlotteacr.azurecr.io/charlotte-frontend:${{ github.sha }} .
        docker push charlotteacr.azurecr.io/charlotte-frontend:${{ github.sha }}
    
    - name: Build and push backend
      run: |
        cd backend
        docker build -t charlotteacr.azurecr.io/charlotte-backend:${{ github.sha }} .
        docker push charlotteacr.azurecr.io/charlotte-backend:${{ github.sha }}
    
    - name: Deploy to Azure Web Apps
      run: |
        az webapp config container set --name charlotte-frontend-app --resource-group charlotte-rg --docker-custom-image-name charlotteacr.azurecr.io/charlotte-frontend:${{ github.sha }}
        az webapp config container set --name charlotte-backend-app --resource-group charlotte-rg --docker-custom-image-name charlotteacr.azurecr.io/charlotte-backend:${{ github.sha }}
```

## Cost Estimation (Monthly for 10-15 users)

| Resource | Tier | Estimated Cost |
|----------|------|----------------|
| App Service Plan (B1, shared) | Basic | $13–15 |
| Azure Container Registry | Basic | $5 |
| Azure Storage (Standard LRS, light usage) | Hot | $2–5 |
| Azure AI Search | Free | $0 |
| Azure AI (AIServices) | S0 (pay-go) | $0–20+ (usage-based) |
| Application Insights | Basic/Free | $0–5 (ingestion) |
| **Total (typical dev/test)** | | **~$20–50/month** |

Notes:
- Keep ingestion low in Application Insights to stay in free/low tiers.
- Azure AI charges are usage-based; with light usage you can stay well under $100.

## Security Considerations

1. **Environment Variables**: Store sensitive data in Azure Key Vault
2. **Network Security**: Configure VNet integration for internal communication
3. **Authentication**: Implement Azure AD authentication
4. **HTTPS**: Enable HTTPS-only communication
5. **Monitoring**: Set up alerts for security events

## Troubleshooting

### Common Issues:
1. **CORS Errors**: Update CORS settings in backend
2. **Image Pull Errors**: Verify ACR credentials
3. **Environment Variables**: Check app settings configuration
4. **SSL Issues**: Verify certificate configuration

### Useful Commands:
```bash
# View web app logs
az webapp log tail --resource-group "charlotte-rg" --name "charlotte-frontend-app"

# Check web app status
az webapp show --resource-group "charlotte-rg" --name "charlotte-frontend-app" --query state

# Restart web app
az webapp restart --resource-group "charlotte-rg" --name "charlotte-frontend-app"
```

## Next Steps

1. Set up monitoring and alerting
2. Configure backup and disaster recovery
3. Implement automated scaling
4. Set up staging environment
5. Configure custom domains and SSL certificates

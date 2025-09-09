#!/bin/bash

# Azure Cleanup Script for Charlotte Application
# This script removes all Azure resources created for the Charlotte application

set -e

# Configuration variables
RESOURCE_GROUP="charlotte-rg"

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

# Function to confirm deletion
confirm_deletion() {
    print_warning "This will delete ALL resources in the resource group: $RESOURCE_GROUP"
    print_warning "This action cannot be undone!"
    echo
    read -p "Are you sure you want to continue? (yes/no): " confirm
    
    if [[ $confirm != "yes" ]]; then
        print_status "Deletion cancelled"
        exit 0
    fi
}

# Function to delete resource group
delete_resource_group() {
    print_status "Deleting resource group: $RESOURCE_GROUP"
    
    if az group show --name "$RESOURCE_GROUP" &> /dev/null; then
        az group delete \
            --name "$RESOURCE_GROUP" \
            --yes \
            --no-wait
        print_status "Resource group deletion initiated"
    else
        print_warning "Resource group $RESOURCE_GROUP does not exist"
    fi
}

# Function to show remaining resources
show_remaining_resources() {
    print_status "Checking for remaining resources..."
    
    # Check for any remaining resources
    remaining_resources=$(az resource list --resource-group "$RESOURCE_GROUP" --query "[].{Name:name, Type:type}" --output table 2>/dev/null || echo "")
    
    if [[ -n "$remaining_resources" && "$remaining_resources" != "Name    Type" ]]; then
        print_warning "Some resources may still exist:"
        echo "$remaining_resources"
    else
        print_status "No remaining resources found"
    fi
}

# Function to show help
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --force           Skip confirmation prompt"
    echo "  --help            Show this help message"
    echo
    echo "Examples:"
    echo "  $0                # Delete with confirmation"
    echo "  $0 --force        # Delete without confirmation"
}

# Parse command line arguments
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE=true
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
    print_status "Starting Azure cleanup for Charlotte application"
    
    check_azure_cli
    check_azure_login
    
    if [[ "$FORCE" == false ]]; then
        confirm_deletion
    fi
    
    delete_resource_group
    show_remaining_resources
    
    print_status "Azure cleanup completed"
    print_warning "Note: Resource group deletion may take a few minutes to complete"
}

# Run main function
main "$@"

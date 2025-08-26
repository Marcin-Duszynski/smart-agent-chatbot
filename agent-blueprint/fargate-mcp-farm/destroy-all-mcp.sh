#!/bin/bash

# MCP Farm Destroy Script
# Destroys all MCP-related stacks in the correct dependency order

set -e  # Exit on any error

echo "🔥 Starting MCP Farm destruction..."
echo "This will destroy the following stacks in order:"
echo "1. Python MCP Fargate Stack"
echo "2. Playwright MCP Fargate Stack" 
echo "3. MCP Farm ALB Stack"
echo ""

# Confirmation
read -p "Are you sure you want to destroy all MCP stacks? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Destruction cancelled."
    exit 1
fi

# Function to check if script exists and run it
run_destroy_script() {
    local script_path=$1
    local description=$2
    
    if [ -f "$script_path" ]; then
        echo "🔥 $description using destroy script..."
        cd "$(dirname "$script_path")"
        chmod +x "$(basename "$script_path")"
        ./$(basename "$script_path")
        cd - > /dev/null
    else
        echo "⚠️  Destroy script not found: $script_path"
        return 1
    fi
}

# Function to run CDK destroy directly
run_cdk_destroy() {
    local cdk_dir=$1
    local stack_name=$2
    local description=$3
    
    if [ -d "$cdk_dir" ]; then
        echo "🔥 $description using CDK destroy..."
        cd "$cdk_dir"
        
        # Activate virtual environment if it exists
        if [ -d "venv" ]; then
            source venv/bin/activate
        fi
        
        cdk destroy "$stack_name" --force
        
        # Deactivate virtual environment if it was activated
        if [ -d "venv" ]; then
            deactivate 2>/dev/null || true
        fi
        
        cd - > /dev/null
    else
        echo "⚠️  CDK directory not found: $cdk_dir"
        return 1
    fi
}

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "🔥 Step 1: Destroying Python MCP Fargate Stack..."
if ! run_destroy_script "$SCRIPT_DIR/python-mcp/destroy.sh" "Python MCP Stack"; then
    echo "⚠️  Trying CDK destroy directly..."
    run_cdk_destroy "$SCRIPT_DIR/python-mcp/cdk" "python-mcp-fargate" "Python MCP Stack"
fi

echo ""
echo "🔥 Step 2: Destroying Playwright MCP Fargate Stack..."
if ! run_destroy_script "$SCRIPT_DIR/playwright-mcp/destroy.sh" "Playwright MCP Stack"; then
    echo "⚠️  Trying CDK destroy directly..."
    run_cdk_destroy "$SCRIPT_DIR/playwright-mcp/cdk" "playwright-mcp-fargate" "Playwright MCP Stack"
fi

echo ""
echo "🔥 Step 3: Destroying MCP Farm ALB Stack..."
if ! run_cdk_destroy "$SCRIPT_DIR/shared-infrastructure/cdk" "McpFarmAlbStack" "MCP Farm ALB Stack"; then
    echo "❌ Failed to destroy MCP Farm ALB Stack"
    exit 1
fi

echo ""
echo "✅ All MCP stacks destroyed successfully!"
echo ""
echo "📝 Note: You can now safely destroy the ChatbotStack:"
echo "   cd ../chatbot-deployment/infrastructure"
echo "   cdk destroy ChatbotStack"
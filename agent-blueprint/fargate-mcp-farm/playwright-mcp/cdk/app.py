#!/usr/bin/env python3
"""
Playwright MCP Server Fargate Deployment
CDK App Entry Point
"""

import os
import aws_cdk as cdk
from stacks.playwright_fargate_stack import PlaywrightFargateStack

app = cdk.App()

# Get configuration from context or environment
region = app.node.try_get_context("region") or "us-west-2"
stack_name = f"playwright-mcp-fargate"

# Create the Playwright Fargate stack
PlaywrightFargateStack(
    app, 
    stack_name,
    env=cdk.Environment(
        account=os.environ.get('CDK_DEFAULT_ACCOUNT'),
        region=region
    ),
    description="Playwright MCP Server running on AWS Fargate with Application Load Balancer"
)

app.synth()

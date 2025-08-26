#!/usr/bin/env python3
"""
MCP Farm Shared Infrastructure CDK App
"""

import aws_cdk as cdk
from stacks.mcp_farm_alb_stack import McpFarmAlbStack

app = cdk.App()

# Create MCP Farm Shared ALB Stack
McpFarmAlbStack(
    app, "McpFarmAlbStack",
    description="MCP Farm Shared Application Load Balancer and VPC Infrastructure",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-west-2"
    )
)

app.synth()

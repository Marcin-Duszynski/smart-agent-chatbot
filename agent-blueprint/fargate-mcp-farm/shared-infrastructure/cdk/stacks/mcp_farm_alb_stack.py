"""
MCP Farm Shared ALB Stack
AWS CDK Stack for creating a shared Application Load Balancer for all MCP servers
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    Fn,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_logs as logs,
    CfnOutput
)
from constructs import Construct


class McpFarmAlbStack(Stack):
    """
    CDK Stack for MCP Farm Shared Application Load Balancer
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get stack name for resource naming
        stack_name = self.stack_name.lower()

        # Import shared VPC from Chatbot deployment
        vpc = ec2.Vpc.from_vpc_attributes(
            self, "SharedChatbotVpc",
            vpc_id=Fn.import_value(f"ChatbotStack-vpc-id"),
            availability_zones=["us-west-2a", "us-west-2b"],  # Must match Chatbot VPC AZs
            public_subnet_ids=[
                Fn.select(0, Fn.split(",", Fn.import_value(f"ChatbotStack-public-subnets"))),
                Fn.select(1, Fn.split(",", Fn.import_value(f"ChatbotStack-public-subnets")))
            ],
            private_subnet_ids=[
                Fn.select(0, Fn.split(",", Fn.import_value(f"ChatbotStack-private-subnets"))),
                Fn.select(1, Fn.split(",", Fn.import_value(f"ChatbotStack-private-subnets")))
            ]
        )

        # Create security group for the ALB
        alb_security_group = ec2.SecurityGroup(
            self, "McpFarmAlbSecurityGroup",
            vpc=vpc,
            description="Security group for MCP Farm Application Load Balancer",
            allow_all_outbound=True
        )

        # Allow inbound HTTP traffic
        alb_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP traffic from anywhere"
        )

        # Allow inbound HTTPS traffic (for future use)
        alb_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS traffic from anywhere"
        )

        # Create Application Load Balancer
        alb = elbv2.ApplicationLoadBalancer(
            self, "McpFarmAlb",
            vpc=vpc,
            internet_facing=True,
            load_balancer_name=f"{stack_name}-mcp-farm-alb",
            security_group=alb_security_group,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC
            ),
            idle_timeout=Duration.seconds(3600)
        )

        # Create default listener (HTTP)
        default_listener = alb.add_listener(
            "McpFarmDefaultListener",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            default_action=elbv2.ListenerAction.fixed_response(
                status_code=200,
                content_type="application/json",
                message_body='{"message": "MCP Farm ALB - Ready for MCP servers", "status": "healthy"}'
            )
        )


        # Create CloudWatch log group for ALB access logs
        alb_log_group = logs.LogGroup(
            self, "McpFarmAlbLogGroup",
            log_group_name=f"/aws/alb/{stack_name}-mcp-farm",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Enable ALB access logging (optional, can be enabled later)
        # alb.log_access_logs(
        #     bucket=s3_bucket,  # Would need to create S3 bucket
        #     prefix="alb-access-logs"
        # )

        # Outputs
        CfnOutput(
            self, "McpFarmAlbArn",
            value=alb.load_balancer_arn,
            description="MCP Farm ALB ARN for cross-stack references",
            export_name=f"{stack_name}-mcp-farm-alb-arn"
        )

        CfnOutput(
            self, "McpFarmAlbDnsName",
            value=alb.load_balancer_dns_name,
            description="MCP Farm ALB DNS Name",
            export_name=f"{stack_name}-mcp-farm-alb-dns"
        )

        CfnOutput(
            self, "McpFarmAlbUrl",
            value=f"http://{alb.load_balancer_dns_name}",
            description="MCP Farm ALB Base URL"
        )

        CfnOutput(
            self, "McpFarmVpcId",
            value=vpc.vpc_id,
            description="MCP Farm VPC ID (using Chatbot VPC)",
            export_name=f"{stack_name}-mcp-farm-vpc-id"
        )

        CfnOutput(
            self, "McpFarmPrivateSubnetIds",
            value=Fn.import_value(f"ChatbotStack-private-subnets"),
            description="MCP Farm Private Subnet IDs (using Chatbot private subnets)",
            export_name=f"{stack_name}-mcp-farm-private-subnets"
        )

        CfnOutput(
            self, "McpFarmDefaultListenerArn",
            value=default_listener.listener_arn,
            description="MCP Farm ALB Default Listener ARN for adding rules",
            export_name=f"{stack_name}-mcp-farm-listener-arn"
        )

        CfnOutput(
            self, "McpFarmAlbSecurityGroupId",
            value=alb_security_group.security_group_id,
            description="MCP Farm ALB Security Group ID for cross-stack references",
            export_name=f"{stack_name}-mcp-farm-alb-sg-id"
        )

        # Store important values as instance variables for potential use
        self.vpc = vpc
        self.alb = alb
        self.default_listener = default_listener
        self.alb_security_group = alb_security_group
        self.alb_log_group = alb_log_group

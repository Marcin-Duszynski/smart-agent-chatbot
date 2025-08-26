"""
Playwright MCP Server Fargate Stack
AWS CDK Stack for deploying Playwright MCP Server on ECS Fargate
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    Fn,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ecr as ecr,
    aws_logs as logs,
    aws_iam as iam,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ssm as ssm,
    CfnOutput
)
from constructs import Construct


class PlaywrightFargateStack(Stack):
    """
    CDK Stack for Playwright MCP Server on Fargate
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

        # Create ECR repository for the Docker image
        ecr_repository = ecr.Repository(
            self, "PlaywrightMcpRepository",
            repository_name=f"{stack_name}-playwright-mcp",
            removal_policy=RemovalPolicy.DESTROY,  # For demo purposes
            image_scan_on_push=True,
            lifecycle_rules=[
                ecr.LifecycleRule(
                    description="Keep only 10 most recent images",
                    max_image_count=10
                )
            ]
        )

        # Create ECS cluster
        cluster = ecs.Cluster(
            self, "PlaywrightMcpCluster",
            cluster_name=f"{stack_name}-cluster",
            vpc=vpc
            # container_insights=True  # Commented out to avoid deprecation warning
        )

        # Create CloudWatch log group
        log_group = logs.LogGroup(
            self, "PlaywrightMcpLogGroup",
            log_group_name=f"/ecs/{stack_name}-playwright-mcp",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Create task execution role
        execution_role = iam.Role(
            self, "PlaywrightMcpExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ]
        )

        # Grant ECR permissions to execution role
        ecr_repository.grant_pull(execution_role)

        # Create task role (for the container itself)
        task_role_statements = [
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=[log_group.log_group_arn]
            )
        ]
        
        
        task_role = iam.Role(
            self, "PlaywrightMcpTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            inline_policies={
                "PlaywrightMcpPolicy": iam.PolicyDocument(
                    statements=task_role_statements
                )
            }
        )

        # Create Fargate task definition
        task_definition = ecs.FargateTaskDefinition(
            self, "PlaywrightMcpTaskDefinition",
            family=f"{stack_name}-playwright-mcp",
            cpu=1024,  # 1 vCPU
            memory_limit_mib=2048,  # 2 GB RAM
            execution_role=execution_role,
            task_role=task_role,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.ARM64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX
            )
        )

        # Add container to task definition
        task_definition.add_container(
            "PlaywrightMcpContainer",
            image=ecs.ContainerImage.from_asset(
                directory="../docker"
            ),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="playwright-mcp",
                log_group=log_group
            ),
            environment=self._build_environment_variables(),
            port_mappings=[
                ecs.PortMapping(
                    container_port=8931,
                    protocol=ecs.Protocol.TCP
                )
            ]
        )

        # Create security group for the service
        service_security_group = ec2.SecurityGroup(
            self, "PlaywrightMcpServiceSecurityGroup",
            vpc=vpc,
            description="Security group for Playwright MCP Fargate service",
            allow_all_outbound=True
        )

        # Allow inbound traffic on port 8931 from ALB security group
        # Import VPC CIDR for security group rules
        vpc_cidr = Fn.import_value(f"ChatbotStack-vpc-cidr")
        service_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc_cidr),
            connection=ec2.Port.tcp(8931),
            description="Allow inbound traffic from ALB"
        )

        # Import shared ALB from the MCP Farm infrastructure
        shared_alb = elbv2.ApplicationLoadBalancer.from_application_load_balancer_attributes(
            self, "SharedMcpFarmAlb",
            load_balancer_arn=Fn.import_value(f"mcpfarmalbstack-mcp-farm-alb-arn"),
            load_balancer_dns_name=Fn.import_value(f"mcpfarmalbstack-mcp-farm-alb-dns"),
            vpc=vpc,
            security_group_id=Fn.import_value(f"mcpfarmalbstack-mcp-farm-alb-sg-id")
        )
        
        # Import shared listener using from_application_listener_attributes
        shared_listener = elbv2.ApplicationListener.from_application_listener_attributes(
            self, "SharedMcpFarmListener",
            listener_arn=Fn.import_value(f"mcpfarmalbstack-mcp-farm-listener-arn"),
            security_group=shared_alb.connections.security_groups[0]
        )

        # Create Fargate service without ALB (we'll add target group manually)
        fargate_service = ecs.FargateService(
            self, "PlaywrightMcpService",
            cluster=cluster,
            task_definition=task_definition,
            service_name=f"{stack_name}-playwright-mcp-service",
            desired_count=1,
            platform_version=ecs.FargatePlatformVersion.LATEST,
            assign_public_ip=False,  # Running in private subnet
            security_groups=[service_security_group],
            vpc_subnets=ec2.SubnetSelection(
                subnets=vpc.private_subnets
            )
        )

        # Create target group for the Fargate service
        target_group = elbv2.ApplicationTargetGroup(
            self, "PlaywrightMcpTargetGroup",
            vpc=vpc,
            port=8931,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            deregistration_delay=Duration.seconds(30),
            health_check=elbv2.HealthCheck(
                protocol=elbv2.Protocol.HTTP,
                path="/mcp",
                port="8931",
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
                timeout=Duration.seconds(5),
                interval=Duration.seconds(30),
                healthy_http_codes="200,400"  # Accept 400 as healthy since MCP server responds with 400 to GET
            )
        )


        # Add listener rule for /playwright/* path
        elbv2.ApplicationListenerRule(
            self, "PlaywrightMcpListenerRule",
            listener=shared_listener,
            priority=100,
            conditions=[
                elbv2.ListenerCondition.path_patterns(["/playwright/*"])
            ],
            action=elbv2.ListenerAction.forward([target_group])
        )

        # Attach Fargate service to target group
        fargate_service.attach_to_application_target_group(target_group)

        # Configure deployment settings to speed up deployments
        cfn_service = fargate_service.node.default_child
        cfn_service.add_property_override("DeploymentConfiguration", {
            "MinimumHealthyPercent": 0,
            "MaximumPercent": 200,
            "DeploymentCircuitBreaker": {
                "Enable": False,
                "Rollback": False
            }
        })

        # Store ALB reference for other services to use
        self.shared_alb = shared_alb
        self.shared_listener = shared_listener

        # Configure auto scaling
        scalable_target = fargate_service.auto_scale_task_count(
            min_capacity=1,
            max_capacity=5
        )

        # Scale based on CPU utilization
        scalable_target.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.minutes(5),
            scale_out_cooldown=Duration.minutes(2)
        )

        # Scale based on memory utilization
        scalable_target.scale_on_memory_utilization(
            "MemoryScaling",
            target_utilization_percent=80,
            scale_in_cooldown=Duration.minutes(5),
            scale_out_cooldown=Duration.minutes(2)
        )

        # Outputs
        CfnOutput(
            self, "LoadBalancerUrl",
            value=f"http://{shared_alb.load_balancer_dns_name}",
            description="MCP Farm Application Load Balancer URL"
        )

        CfnOutput(
            self, "McpEndpoint",
            value=f"http://{shared_alb.load_balancer_dns_name}/playwright/mcp",
            description="Playwright MCP Server Endpoint URL"
        )

        CfnOutput(
            self, "McpFarmAlbDnsName",
            value=shared_alb.load_balancer_dns_name,
            description="MCP Farm ALB DNS Name for adding additional MCP servers"
        )

        CfnOutput(
            self, "EcrRepositoryUri",
            value=ecr_repository.repository_uri,
            description="ECR Repository URI for Docker images"
        )

        CfnOutput(
            self, "ClusterName",
            value=cluster.cluster_name,
            description="ECS Cluster Name"
        )

        CfnOutput(
            self, "ServiceName",
            value=fargate_service.service_name,
            description="ECS Service Name"
        )

        # Parameter Store entry for MCP endpoint
        ssm.StringParameter(
            self, "McpEndpointParameter",
            parameter_name="/mcp/endpoints/stateful/playwright-mcp",
            string_value=f"http://{shared_alb.load_balancer_dns_name}/playwright/mcp",
            description="Playwright MCP Server endpoint URL"
        )
        

        # Store important values as instance variables for potential use
        self.vpc = vpc
        self.cluster = cluster
        self.ecr_repository = ecr_repository
        self.fargate_service = fargate_service
        self.target_group = target_group
        self.log_group = log_group
    
    def _build_environment_variables(self) -> dict:
        """Build environment variables for the container"""
        env_vars = {
            "NODE_ENV": "production",
            "PORT": "8931",
            "LOG_LEVEL": "info",
            # Deployment mode for environment detection
            "DEPLOYMENT_MODE": "cloud",
            # AWS region
            "AWS_DEFAULT_REGION": self.region
        }
        
        return env_vars

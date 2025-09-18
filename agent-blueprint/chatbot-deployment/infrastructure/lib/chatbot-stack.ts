import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

// Region-specific configuration
const REGION_CONFIG: { [key: string]: { azs: string[] } } = {
  'us-west-2': { azs: ['us-west-2a', 'us-west-2b'] },
  'us-east-1': { azs: ['us-east-1a', 'us-east-1b'] },
  'ap-northeast-2': { azs: ['ap-northeast-2a', 'ap-northeast-2b'] },
  'eu-west-1': { azs: ['eu-west-1a', 'eu-west-1b'] }
};

export class ChatbotStack extends cdk.Stack {

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);


    // Create new VPC for chatbot and MCP farm
    const vpc = new ec2.Vpc(this, 'ChatbotMcpVpc', {
      maxAzs: 2,  // Use 2 AZs for high availability
      natGateways: 1,  // Cost optimization - use 1 NAT gateway
      subnetConfiguration: [
        {
          name: 'PublicSubnet',
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24
        },
        {
          name: 'PrivateSubnet',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          cidrMask: 24
        }
      ]
    });

    // ECR Repositories - Import existing repositories
    const backendRepository = ecr.Repository.fromRepositoryName(this, 'ChatbotBackendRepository', 'chatbot-backend');
    const frontendRepository = ecr.Repository.fromRepositoryName(this, 'ChatbotFrontendRepository', 'chatbot-frontend');


    // ECS Cluster
    const cluster = new ecs.Cluster(this, 'ChatbotCluster', {
      vpc,
      clusterName: 'chatbot-cluster',
    });

    // Backend Task Definition
    const backendTaskDefinition = new ecs.FargateTaskDefinition(this, 'ChatbotBackendTaskDef', {
      memoryLimitMiB: 512,
      cpu: 256,
    });

    // Add Bedrock permissions to backend task role
    backendTaskDefinition.taskRole.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonBedrockFullAccess')
    );
    backendTaskDefinition.taskRole.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName('BedrockAgentCoreFullAccess')
    );

    // Add API Gateway invoke permissions for MCP servers
    backendTaskDefinition.addToTaskRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'execute-api:Invoke'
        ],
        resources: [
          `arn:aws:execute-api:${this.region}:${this.account}:*/*/POST/mcp`,
          `arn:aws:execute-api:${this.region}:${this.account}:mcp-*/*/*/*`
        ]
      })
    );

    // Add Parameter Store permissions for dynamic MCP endpoint configuration
    backendTaskDefinition.addToTaskRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'ssm:GetParameter',
          'ssm:GetParameters',
          'ssm:GetParametersByPath'
        ],
        resources: [
          `arn:aws:ssm:${this.region}:${this.account}:parameter/mcp/endpoints/*`
        ]
      })
    );

    // Add CloudWatch permissions for AgentCore Observability
    backendTaskDefinition.addToTaskRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'logs:CreateLogStream',
          'logs:PutLogEvents',
          'cloudwatch:PutMetricData'
        ],
        resources: [
          `arn:aws:logs:${this.region}:${this.account}:log-group:agents/strands-agent-logs`,
          `arn:aws:logs:${this.region}:${this.account}:log-group:agents/strands-agent-logs:*`
        ]
      })
    );

    // Add X-Ray permissions for trace export
    backendTaskDefinition.addToTaskRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'xray:PutTraceSegments',
          'xray:PutTelemetryRecords'
        ],
        resources: ['*']
      })
    );

    // Create or reuse AgentCore Observability Log Group (idempotent)
    const agentObservabilityLogGroup = new logs.LogGroup(this, 'AgentObservabilityLogGroup', {
      logGroupName: 'agents/strands-agent-logs',
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.RETAIN
    });

    // Generate unique log stream name
    const logStreamName = `otel-auto-${Math.random().toString(36).substring(2, 11)}`;
    
    // Create OTEL log stream
    new logs.LogStream(this, 'OtelLogStream', {
      logGroup: agentObservabilityLogGroup,
      logStreamName: logStreamName,
      removalPolicy: cdk.RemovalPolicy.RETAIN
    });



    // Backend Container
    const backendContainer = backendTaskDefinition.addContainer('ChatbotBackendContainer', {
      image: ecs.ContainerImage.fromEcrRepository(backendRepository, 'latest'),
      environment: {
        DEPLOYMENT_ENV: 'production',
        STORAGE_TYPE: 'local',
        HOST: '0.0.0.0',
        PORT: '8000',
        CORS_ORIGINS: '*',
        FORCE_UPDATE: new Date().toISOString(),
        AWS_DEFAULT_REGION: this.region,
        // AgentCore Observability - OTEL Configuration
        OTEL_PYTHON_DISTRO: 'aws_distro',
        OTEL_PYTHON_CONFIGURATOR: 'aws_configurator',
        OTEL_EXPORTER_OTLP_PROTOCOL: 'http/protobuf',
        OTEL_EXPORTER_OTLP_LOGS_PROTOCOL: 'http/protobuf',
        OTEL_LOGS_EXPORTER: 'otlp',
        OTEL_TRACES_EXPORTER: 'otlp',
        OTEL_EXPORTER_OTLP_LOGS_HEADERS: `x-aws-log-group=agents/strands-agent-logs,x-aws-log-stream=${logStreamName},x-aws-metric-namespace=agentsd`,
        OTEL_RESOURCE_ATTRIBUTES: 'service.name=strands-chatbot',
        AGENT_OBSERVABILITY_ENABLED: 'true',
        AWS_REGION: this.region,
        OTEL_LOG_LEVEL: 'DEBUG',
        // OTEL batch processing settings for real-time traces
        OTEL_BSP_SCHEDULE_DELAY: '100',
        OTEL_BSP_MAX_EXPORT_BATCH_SIZE: '1',
        OTEL_BSP_EXPORT_TIMEOUT: '5000',
      },
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'chatbot-backend',
      }),
    });

    backendContainer.addPortMappings({
      containerPort: 8000,
      protocol: ecs.Protocol.TCP,
    });

    // Backend ECS Service
    const backendService = new ecs.FargateService(this, 'ChatbotBackendService', {
      cluster,
      taskDefinition: backendTaskDefinition,
      desiredCount: 1,
      assignPublicIp: true,
      minHealthyPercent: 0,  // Allow stopping all tasks during deployment
      maxHealthyPercent: 200,
    });


    // Create security group for ALB
    const albSecurityGroup = new ec2.SecurityGroup(this, 'ChatbotAlbSecurityGroup', {
      vpc,
      description: 'Security group for Chatbot Application Load Balancer',
      allowAllOutbound: true
    });

    // Allow inbound HTTP traffic
    albSecurityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(80),
      'Allow HTTP traffic from anywhere'
    );

    // Application Load Balancer
    const alb = new elbv2.ApplicationLoadBalancer(this, 'ChatbotALB', {
      vpc,
      internetFacing: true,
      securityGroup: albSecurityGroup,
      idleTimeout: cdk.Duration.seconds(3600),
    });

    const listener = alb.addListener('ChatbotListener', {
      port: 80,
      open: true,
    });

    // Frontend Task Definition (before ALB targets)
    const frontendTaskDefinition = new ecs.FargateTaskDefinition(this, 'ChatbotFrontendTaskDef', {
      memoryLimitMiB: 512,
      cpu: 256,
    });


    // Frontend Container
    const frontendContainer = frontendTaskDefinition.addContainer('ChatbotFrontendContainer', {
      image: ecs.ContainerImage.fromEcrRepository(frontendRepository, 'latest'),
      environment: {
        NODE_ENV: 'production',
        FORCE_UPDATE: new Date().toISOString(),
        BACKEND_URL: `http://${alb.loadBalancerDnsName}`,
        // NEXT_PUBLIC_API_URL removed - using auto-detection based on hostname
        NEXT_PUBLIC_AWS_REGION: this.region,
        AWS_DEFAULT_REGION: this.region,
      },
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'chatbot-frontend',
      }),
    });

    frontendContainer.addPortMappings({
      containerPort: 3000,
      protocol: ecs.Protocol.TCP,
    });

    // Frontend ECS Service
    const frontendService = new ecs.FargateService(this, 'ChatbotFrontendService', {
      cluster,
      taskDefinition: frontendTaskDefinition,
      desiredCount: 1,
      assignPublicIp: true,
      minHealthyPercent: 0,  // Allow stopping all tasks during deployment
      maxHealthyPercent: 200,
    });

    // Default Target Group (Frontend) - No priority, no conditions
    const frontendTargetGroup = listener.addTargets('DefaultFrontendTarget', {
      port: 3000,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [frontendService],
      healthCheck: {
        path: '/health',
        interval: cdk.Duration.seconds(30),
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 3,
        timeout: cdk.Duration.seconds(10),
      },
      deregistrationDelay: cdk.Duration.seconds(30),
    });

    frontendTargetGroup.setAttribute('load_balancing.cross_zone.enabled', 'true');

    // Backend Target Group - Unified routing for all API requests
    const backendTargetGroup = listener.addTargets('BackendApiTarget', {
      port: 8000,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [backendService],
      priority: 100,
      conditions: [
        elbv2.ListenerCondition.pathPatterns([
          '/api/*',           // All API requests
          '/docs*',           // Swagger documentation
          '/health',          // Health check endpoint
          '/uploads/*',       // Direct uploads endpoints
          '/output/*',        // Direct output endpoints
        ]),
      ],
      healthCheck: {
        path: '/health',
        interval: cdk.Duration.seconds(60),
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 3,
        timeout: cdk.Duration.seconds(10),
      },
      stickinessCookieDuration: cdk.Duration.hours(1),
      deregistrationDelay: cdk.Duration.seconds(30),
    });

    backendTargetGroup.setAttribute('load_balancing.cross_zone.enabled', 'true');


    // Outputs
    new cdk.CfnOutput(this, 'ApplicationUrl', {
      value: `http://${alb.loadBalancerDnsName}`,
      description: 'Application URL (Frontend + Backend)',
    });

    new cdk.CfnOutput(this, 'BackendApiUrl', {
      value: `http://${alb.loadBalancerDnsName}/api`,
      description: 'Backend API URL',
    });

    new cdk.CfnOutput(this, 'SwaggerDocsUrl', {
      value: `http://${alb.loadBalancerDnsName}/docs`,
      description: 'API Documentation (Swagger)',
    });


    new cdk.CfnOutput(this, 'BackendECRRepositoryUri', {
      value: backendRepository.repositoryUri,
      description: 'Backend ECR Repository URI',
    });

    new cdk.CfnOutput(this, 'FrontendECRRepositoryUri', {
      value: frontendRepository.repositoryUri,
      description: 'Frontend ECR Repository URI',
    });

    // Export VPC information for MCP farm to reuse
    new cdk.CfnOutput(this, 'VpcId', {
      value: vpc.vpcId,
      description: 'VPC ID for MCP farm reuse',
      exportName: `${this.stackName}-vpc-id`
    });

    new cdk.CfnOutput(this, 'PrivateSubnetIds', {
      value: vpc.privateSubnets.map(subnet => subnet.subnetId).join(','),
      description: 'Private Subnet IDs for MCP farm reuse',
      exportName: `${this.stackName}-private-subnets`
    });

    new cdk.CfnOutput(this, 'PublicSubnetIds', {
      value: vpc.publicSubnets.map(subnet => subnet.subnetId).join(','),
      description: 'Public Subnet IDs for MCP farm reuse',
      exportName: `${this.stackName}-public-subnets`
    });

    new cdk.CfnOutput(this, 'VpcCidrBlock', {
      value: vpc.vpcCidrBlock,
      description: 'VPC CIDR Block for MCP farm reuse',
      exportName: `${this.stackName}-vpc-cidr`
    });

    // AgentCore Observability Outputs
    new cdk.CfnOutput(this, 'ObservabilityLogGroupName', {
      value: 'agents/strands-agent-logs',
      description: 'CloudWatch Log Group for AgentCore Observability'
    });

    new cdk.CfnOutput(this, 'ObservabilitySetupNote', {
      value: 'Remember to enable CloudWatch Transaction Search for full observability',
      description: 'AgentCore Observability Setup Reminder'
    });

  }

}

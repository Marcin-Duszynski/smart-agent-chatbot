#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { ChatbotStack } from '../lib/chatbot-stack';
import { readFileSync } from 'fs';
import { join } from 'path';

// Load config.json
const configPath = join(__dirname, '..', 'config.json');
const config = JSON.parse(readFileSync(configPath, 'utf8'));

const app = new cdk.App();

// Get deployment region from environment variable or use default
const deploymentRegion = process.env.AWS_REGION || config.defaultRegion;

// Validate region is supported
if (!config.supportedRegions.includes(deploymentRegion)) {
  console.error(`❌ Unsupported region: ${deploymentRegion}`);
  console.error(`✅ Supported regions: ${config.supportedRegions.join(', ')}`);
  process.exit(1);
}

console.log(`🚀 Deploying to region: ${deploymentRegion}`);

new ChatbotStack(app, 'ChatbotStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: deploymentRegion,
  },
});

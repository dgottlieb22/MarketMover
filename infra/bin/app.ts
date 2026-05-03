#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { MmdStack } from '../lib/mmd-stack';

const app = new cdk.App();
new MmdStack(app, 'MmdStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION ?? 'us-east-1',
  },
});

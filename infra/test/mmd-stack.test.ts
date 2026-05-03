import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { MmdStack } from '../lib/mmd-stack';

describe('MmdStack', () => {
  let template: Template;

  beforeAll(() => {
    const app = new cdk.App();
    const stack = new MmdStack(app, 'TestStack', { alertEmail: 'test@example.com' });
    template = Template.fromStack(stack);
  });

  test('creates a VPC', () => {
    template.resourceCountIs('AWS::EC2::VPC', 1);
  });

  test('creates an RDS Postgres instance', () => {
    template.hasResourceProperties('AWS::RDS::DBInstance', {
      Engine: 'postgres',
      DBName: 'market_data',
    });
  });

  test('creates an SNS topic', () => {
    template.hasResourceProperties('AWS::SNS::Topic', {
      DisplayName: 'MMD High-Severity Alerts',
    });
  });

  test('creates an email subscription when alertEmail is provided', () => {
    template.hasResourceProperties('AWS::SNS::Subscription', {
      Protocol: 'email',
      Endpoint: 'test@example.com',
    });
  });

  test('creates an S3 bucket with 90-day lifecycle', () => {
    template.hasResourceProperties('AWS::S3::Bucket', {
      LifecycleConfiguration: {
        Rules: Match.arrayWith([
          Match.objectLike({ ExpirationInDays: 90, Status: 'Enabled' }),
        ]),
      },
    });
  });

  test('creates a Lambda function with correct environment', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      Runtime: 'python3.12',
      Handler: 'handler.main',
      Timeout: 300,
      MemorySize: 512,
    });
  });

  test('creates an EventBridge rule for weekday scheduling', () => {
    template.hasResourceProperties('AWS::Events::Rule', {
      ScheduleExpression: 'cron(30 21 ? * MON-FRI *)',
    });
  });

  test('creates an ECS Fargate service', () => {
    template.hasResourceProperties('AWS::ECS::Service', {
      LaunchType: 'FARGATE',
    });
  });

  test('creates a load balancer', () => {
    template.resourceCountIs('AWS::ElasticLoadBalancingV2::LoadBalancer', 1);
  });

  test('outputs API URL, topic ARN, and bucket name', () => {
    template.hasOutput('ApiUrl', {});
    template.hasOutput('AlertTopicArn', {});
    template.hasOutput('BacktestBucketName', {});
  });

  test('Lambda has permissions to read DB secret', () => {
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Action: Match.arrayWith(['secretsmanager:GetSecretValue']),
            Effect: 'Allow',
          }),
        ]),
      },
    });
  });

  test('Lambda has permissions to publish to SNS', () => {
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Action: 'sns:Publish',
            Effect: 'Allow',
          }),
        ]),
      },
    });
  });
});

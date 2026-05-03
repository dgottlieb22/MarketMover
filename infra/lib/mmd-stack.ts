import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecs_patterns from 'aws-cdk-lib/aws-ecs-patterns';
import * as events from 'aws-cdk-lib/aws-events';
import * as events_targets from 'aws-cdk-lib/aws-events-targets';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as sns_subs from 'aws-cdk-lib/aws-sns-subscriptions';
import { Construct } from 'constructs';

export interface MmdStackProps extends cdk.StackProps {
  /** Email to receive high-severity alert notifications. */
  alertEmail?: string;
}

/**
 * Market Movement Detector — AWS deployment architecture.
 *
 * Architecture:
 *   EventBridge (cron) -> Lambda (pipeline) -> RDS Postgres
 *                                           -> SNS (alerts)
 *   ECS Fargate (FastAPI) -> RDS Postgres
 *   S3 (backtest exports)
 */
export class MmdStack extends cdk.Stack {
  public readonly vpc: ec2.IVpc;
  public readonly database: rds.DatabaseInstance;
  public readonly alertTopic: sns.Topic;
  public readonly backtestBucket: s3.Bucket;
  public readonly pipelineFn: lambda.Function;
  public readonly apiService: ecs_patterns.ApplicationLoadBalancedFargateService;

  constructor(scope: Construct, id: string, props?: MmdStackProps) {
    super(scope, id, props);

    // --- Networking ---
    this.vpc = new ec2.Vpc(this, 'Vpc', { maxAzs: 2 });

    // --- Database ---
    this.database = new rds.DatabaseInstance(this, 'Database', {
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_16_4,
      }),
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T4G, ec2.InstanceSize.MICRO),
      vpc: this.vpc,
      databaseName: 'market_data',
      credentials: rds.Credentials.fromGeneratedSecret('mmd_admin'),
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      deletionProtection: false,
    });

    // --- SNS topic for alert notifications ---
    this.alertTopic = new sns.Topic(this, 'AlertTopic', {
      displayName: 'MMD High-Severity Alerts',
    });

    if (props?.alertEmail) {
      this.alertTopic.addSubscription(
        new sns_subs.EmailSubscription(props.alertEmail),
      );
    }

    // --- S3 bucket for backtest exports ---
    this.backtestBucket = new s3.Bucket(this, 'BacktestBucket', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [{ expiration: cdk.Duration.days(90) }],
    });

    // --- Lambda: scheduled pipeline (ingest -> features -> detect) ---
    this.pipelineFn = new lambda.Function(this, 'PipelineFn', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.main',
      code: lambda.Code.fromInline('# Placeholder — real deployment bundles ../backend with dependencies'),
      timeout: cdk.Duration.minutes(5),
      memorySize: 512,
      environment: {
        DB_SECRET_ARN: this.database.secret?.secretArn ?? '',
        ALERT_TOPIC_ARN: this.alertTopic.topicArn,
        BACKTEST_BUCKET: this.backtestBucket.bucketName,
      },
      vpc: this.vpc,
    });

    this.database.secret?.grantRead(this.pipelineFn);
    this.database.connections.allowDefaultPortFrom(this.pipelineFn);
    this.alertTopic.grantPublish(this.pipelineFn);
    this.backtestBucket.grantWrite(this.pipelineFn);

    // --- EventBridge: run pipeline at market close (weekdays 4:30 PM ET) ---
    new events.Rule(this, 'PipelineSchedule', {
      schedule: events.Schedule.cron({
        minute: '30',
        hour: '21',  // 4:30 PM ET = 21:30 UTC
        weekDay: 'MON-FRI',
      }),
      targets: [new events_targets.LambdaFunction(this.pipelineFn)],
    });

    // --- ECS Fargate: FastAPI service ---
    const cluster = new ecs.Cluster(this, 'Cluster', { vpc: this.vpc });

    this.apiService = new ecs_patterns.ApplicationLoadBalancedFargateService(
      this, 'ApiService', {
        cluster,
        cpu: 256,
        memoryLimitMiB: 512,
        desiredCount: 1,
        taskImageOptions: {
          image: ecs.ContainerImage.fromRegistry('python:3.12-slim'),  // Placeholder — real deployment builds ../backend
          containerPort: 8000,
          environment: {
            DB_SECRET_ARN: this.database.secret?.secretArn ?? '',
          },
        },
        publicLoadBalancer: true,
      },
    );

    this.database.connections.allowDefaultPortFrom(this.apiService.service);

    // --- Outputs ---
    new cdk.CfnOutput(this, 'ApiUrl', {
      value: this.apiService.loadBalancer.loadBalancerDnsName,
      description: 'API load balancer URL',
    });

    new cdk.CfnOutput(this, 'AlertTopicArn', {
      value: this.alertTopic.topicArn,
      description: 'SNS topic for alert notifications',
    });

    new cdk.CfnOutput(this, 'BacktestBucketName', {
      value: this.backtestBucket.bucketName,
      description: 'S3 bucket for backtest exports',
    });
  }
}

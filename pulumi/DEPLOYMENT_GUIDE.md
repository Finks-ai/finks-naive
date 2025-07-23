# Finks Naive Pulumi Deployment Guide

## Overview

This Pulumi configuration deploys the Finks Naive API to AWS Lambda with optimized settings for each environment.

## Key Improvements Based on Performance Analysis

### 1. **Fixed Init Timeout Issues**
- Increased timeout from 30s to 60s for dev/staging
- Production keeps 30s with provisioned concurrency

### 2. **Right-sized Memory Allocation**
- Dev: 256MB (logs showed only 128MB used)
- Staging: 512MB
- Production: 1024MB (for best performance)

### 3. **Environment-Specific Optimizations**
| Environment | Memory | Timeout | Reserved | Provisioned | Log Retention |
|-------------|--------|---------|----------|-------------|---------------|
| Dev         | 256MB  | 60s     | 0        | 0           | 3 days        |
| Staging     | 512MB  | 60s     | 2        | 0           | 7 days        |
| Production  | 1024MB | 30s     | 10       | 2           | 14 days       |

### 4. **New Environment Variables**
- MongoDB connection pooling settings
- Cache configuration
- Performance flags (lazy loading, preload cache)

### 5. **CloudWatch Alarms**
- **High Error Rate**: Triggers if >10 errors in 5 minutes
- **Slow Init**: Triggers if initialization >5 seconds
- **Slow Queries**: Triggers if average duration >10 seconds

## Deployment Commands

### Deploy to Development
```bash
cd pulumi
pulumi stack select dev
pulumi up
```

### Deploy to Staging
```bash
cd pulumi
pulumi stack select staging
pulumi up
```

### Deploy to Production
```bash
cd pulumi
pulumi stack select prod
pulumi up
```

## Cost Optimization

### Dev Environment
- Minimal resources (256MB)
- No reserved/provisioned capacity
- Short log retention (3 days)
- **Estimated cost**: ~$5-10/month

### Production Environment
- Provisioned concurrency (2 instances) eliminates cold starts
- Reserved concurrency (10) prevents runaway scaling
- **Estimated cost**: ~$100-150/month

## Monitoring

### View Lambda Logs
```bash
# Dev environment
aws logs tail "/aws/lambda/dev-finks-screener-lambda" --follow --region ca-central-1

# Production
aws logs tail "/aws/lambda/prod-finks-screener-lambda" --follow --region ca-central-1
```

### Check Alarms
```bash
# List all alarms for the project
aws cloudwatch describe-alarms --alarm-name-prefix "dev-finks-screener" --region ca-central-1
```

### View Metrics
```bash
# Get recent invocation count
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=dev-finks-screener-lambda \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Sum \
  --region ca-central-1
```

## Troubleshooting

### Init Timeout Issues
If you still see init timeouts:
1. Check if all dependencies are in requirements.txt
2. Consider creating a Lambda Layer for dependencies
3. Enable `LAZY_LOAD_MODELS=true` environment variable

### High Memory Usage
If memory usage increases:
1. Check the CloudWatch logs for memory patterns
2. Adjust memory in the stack-specific configuration
3. Consider implementing more aggressive garbage collection

### Cold Start Issues
For production:
1. Provisioned concurrency is set to 2
2. Monitor the `InitDuration` metric
3. Consider increasing provisioned concurrency if needed

## Performance Baseline

Based on current logs:
- **Cold start**: ~15 seconds (being addressed with provisioned concurrency)
- **Warm start**: ~50ms
- **Query processing**: ~8 seconds (acceptable for AI agents)
- **Memory usage**: ~128MB (plenty of headroom)

## Next Steps

1. **Lambda Layers**: Create a layer for dependencies to speed up deployments
2. **Step Functions**: Consider for complex workflows exceeding 15 minutes
3. **API Gateway**: Add if you need request throttling and API key management
4. **X-Ray**: Enable for detailed tracing of agent execution

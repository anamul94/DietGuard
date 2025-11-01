# AWS Systems Manager Parameters Setup

Create these parameters in AWS Systems Manager Parameter Store before deployment:

## Required Parameters

```bash
# AWS Credentials
aws ssm put-parameter --name "/dietguard/aws/access-key-id" --value "YOUR_ACCESS_KEY" --type "SecureString"
aws ssm put-parameter --name "/dietguard/aws/secret-access-key" --value "YOUR_SECRET_KEY" --type "SecureString"
aws ssm put-parameter --name "/dietguard/aws/region" --value "ap-south-1" --type "String"

# PostgreSQL Configuration
aws ssm put-parameter --name "/dietguard/postgres/host" --value "your-postgres-host" --type "String"
aws ssm put-parameter --name "/dietguard/postgres/port" --value "5432" --type "String"
aws ssm put-parameter --name "/dietguard/postgres/user" --value "dietguard" --type "String"
aws ssm put-parameter --name "/dietguard/postgres/password" --value "your-postgres-password" --type "SecureString"
aws ssm put-parameter --name "/dietguard/postgres/db" --value "dietguard" --type "String"

# Langfuse Configuration
aws ssm put-parameter --name "/dietguard/langfuse/public-key" --value "your-langfuse-public-key" --type "String"
aws ssm put-parameter --name "/dietguard/langfuse/secret-key" --value "your-langfuse-secret-key" --type "SecureString"
aws ssm put-parameter --name "/dietguard/langfuse/host" --value "your-langfuse-host" --type "String"
```

## Environment Variables for CodeBuild

Set these in your CodeBuild project:

- `AWS_DEFAULT_REGION`: ap-south-1

## IAM Permissions

Ensure your CodeBuild service role has:
- S3 permissions (for artifacts)
- SSM Parameter Store read access
- CodeDeploy permissions

Ensure your EC2 instance role has:
- SSM Parameter Store read access
- CloudWatch Logs permissions
- CodeDeploy agent permissions
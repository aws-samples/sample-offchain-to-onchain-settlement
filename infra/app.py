#!/usr/bin/env python3
import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks, NagSuppressions

from settlement_stack import SettlementStack

app = cdk.App()
stack = SettlementStack(
    app,
    "SettlementStack",
    env=cdk.Environment(region="us-east-1"),
)

NagSuppressions.add_stack_suppressions(stack, [
    {"id": "AwsSolutions-S1", "reason": "Access logging not required for demo"},
    {"id": "AwsSolutions-DDB3", "reason": "PITR not required for demo"},
    {"id": "AwsSolutions-IAM4", "reason": "AWS managed policies acceptable for Lambda and API GW roles"},
    {"id": "AwsSolutions-IAM5", "reason": "Wildcard permissions are CDK-generated, scoped to specific resources"},
    {"id": "AwsSolutions-L1", "reason": "Python 3.11 is sufficient for this workload"},
    {"id": "AwsSolutions-APIG1", "reason": "API access logging not required for demo"},
    {"id": "AwsSolutions-APIG2", "reason": "Request validation handled in Lambda"},
    {"id": "AwsSolutions-APIG3", "reason": "WAF not required for demo"},
    {"id": "AwsSolutions-APIG4", "reason": "API key auth sufficient for machine-to-machine access"},
    {"id": "AwsSolutions-APIG6", "reason": "CloudWatch method logging not required for demo"},
    {"id": "AwsSolutions-COG4", "reason": "Cognito not required — API is machine-to-machine with API key auth"},
])

cdk.Aspects.of(app).add(AwsSolutionsChecks())
app.synth()

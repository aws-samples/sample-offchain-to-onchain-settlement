from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_apigateway as apigw,
    aws_dynamodb as ddb,
    aws_kms as kms,
    aws_lambda as lambda_,
    aws_s3 as s3,
)
from constructs import Construct


class SettlementStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        verifying_contract = self.node.try_get_context("verifyingContract") or "0x0000000000000000000000000000000000000000"
        allowed_chain_id = self.node.try_get_context("chainId") or "11155111"

        signer_key = kms.Key(
            self,
            "SignerKey",
            key_spec=kms.KeySpec.ECC_SECG_P256K1,
            key_usage=kms.KeyUsage.SIGN_VERIFY,
            removal_policy=RemovalPolicy.DESTROY,
        )

        raw_bucket = s3.Bucket(
            self,
            "RawMessageBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        instructions_table = ddb.Table(
            self,
            "InstructionsTable",
            partition_key=ddb.Attribute(name="instructionId", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        instructions_table.add_global_secondary_index(
            index_name="status-index",
            partition_key=ddb.Attribute(name="status", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="createdAt", type=ddb.AttributeType.NUMBER),
            projection_type=ddb.ProjectionType.ALL,
        )

        idempotency_table = ddb.Table(
            self,
            "IdempotencyTable",
            partition_key=ddb.Attribute(name="idempotencyKey", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        audit_table = ddb.Table(
            self,
            "AuditTable",
            partition_key=ddb.Attribute(name="instructionId", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="ts", type=ddb.AttributeType.NUMBER),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        lambda_fn = lambda_.Function(
            self,
            "IngestionHandler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="app.handler",
            code=lambda_.Code.from_asset(
                "../aws",
                exclude=[
                    "**/__pycache__",
                    "*.pyc",
                ],
            ),
            timeout=Duration.seconds(30),
            environment={
                "INSTRUCTIONS_TABLE": instructions_table.table_name,
                "IDEMPOTENCY_TABLE": idempotency_table.table_name,
                "AUDIT_TABLE": audit_table.table_name,
                "RAW_BUCKET": raw_bucket.bucket_name,
                "KMS_KEY_ID": signer_key.key_id,
                "VERIFYING_CONTRACT": verifying_contract,
                "STATUS_INDEX": "status-index",
                "ALLOWED_CHAIN_ID": str(allowed_chain_id),
            },
        )

        instructions_table.grant_read_write_data(lambda_fn)
        idempotency_table.grant_read_write_data(lambda_fn)
        audit_table.grant_read_write_data(lambda_fn)
        raw_bucket.grant_read_write(lambda_fn)
        signer_key.grant(lambda_fn, "kms:Sign", "kms:GetPublicKey")

        api = apigw.RestApi(
            self,
            "SettlementApi",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=["GET", "POST", "OPTIONS"],
            ),
        )

        # Create API key for authenticated access
        api_key = api.add_api_key(
            "SettlementApiKey",
            api_key_name="settlement-api-key",
        )

        # Create usage plan and associate API key
        usage_plan = api.add_usage_plan(
            "SettlementUsagePlan",
            name="settlement-usage-plan",
            throttle=apigw.ThrottleSettings(
                rate_limit=100,
                burst_limit=200,
            ),
        )
        usage_plan.add_api_key(api_key)
        usage_plan.add_api_stage(stage=api.deployment_stage)

        messages = api.root.add_resource("messages")
        # Require API key for creating messages
        messages.add_method(
            "POST",
            apigw.LambdaIntegration(lambda_fn),
            api_key_required=True,
        )

        instructions = api.root.add_resource("instructions")
        # GET /instructions - fetch all instructions
        instructions.add_method(
            "GET",
            apigw.LambdaIntegration(lambda_fn),
            api_key_required=True,
        )
        pending = instructions.add_resource("pending")
        # Require API key for fetching pending instructions
        pending.add_method(
            "GET",
            apigw.LambdaIntegration(lambda_fn),
            api_key_required=True,
        )

        instruction_id = instructions.add_resource("{instructionId}")
        status = instruction_id.add_resource("status")
        # Status updates from CRE also need API key
        status.add_method(
            "POST",
            apigw.LambdaIntegration(lambda_fn),
            api_key_required=True,
        )

        CfnOutput(self, "ApiBaseUrl", value=api.url)
        CfnOutput(self, "ApiKeyId", value=api_key.key_id)
        CfnOutput(self, "KmsKeyId", value=signer_key.key_id)
        CfnOutput(self, "RawBucketName", value=raw_bucket.bucket_name)
        CfnOutput(self, "InstructionsTableName", value=instructions_table.table_name)
        CfnOutput(self, "IdempotencyTableName", value=idempotency_table.table_name)
        CfnOutput(self, "AuditTableName", value=audit_table.table_name)

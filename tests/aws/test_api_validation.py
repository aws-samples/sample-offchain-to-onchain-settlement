import importlib
import json
import os
import unittest


def _load_app(allowed_chain_id: str = "11155111"):
    os.environ["INSTRUCTIONS_TABLE"] = "instructions"
    os.environ["IDEMPOTENCY_TABLE"] = "idempotency"
    os.environ["AUDIT_TABLE"] = "audit"
    os.environ["RAW_BUCKET"] = "raw-bucket"
    os.environ["KMS_KEY_ID"] = "kms-key-id"
    os.environ["ALLOWED_CHAIN_ID"] = allowed_chain_id
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    app_module = importlib.import_module("app")
    return importlib.reload(app_module)


class TestApiValidation(unittest.TestCase):
    def test_messages_rejects_bad_asset(self):
        app = _load_app()
        event = {
            "httpMethod": "POST",
            "path": "/messages",
            "body": json.dumps(
                {
                    "rawMessage": "hello",
                    "asset": "not-an-address",
                    "amount": "1",
                    "fromParty": "0x0000000000000000000000000000000000000000",
                    "toParty": "0x1111111111111111111111111111111111111111",
                    "valueTime": 1700000000,
                    "intent": "MINT_ONLY",
                    "chainId": 11155111,
                }
            ),
        }
        response = app.handler(event, None)
        self.assertEqual(response["statusCode"], 400)
        self.assertIn("asset must be 20-byte hex address", response["body"])

    def test_messages_rejects_disallowed_chain(self):
        app = _load_app(allowed_chain_id="1")
        event = {
            "httpMethod": "POST",
            "path": "/messages",
            "body": json.dumps(
                {
                    "rawMessage": "hello",
                    "asset": "0x1111111111111111111111111111111111111111",
                    "amount": "1",
                    "fromParty": "0x0000000000000000000000000000000000000000",
                    "toParty": "0x1111111111111111111111111111111111111111",
                    "valueTime": 1700000000,
                    "intent": "MINT_ONLY",
                    "chainId": 11155111,
                }
            ),
        }
        response = app.handler(event, None)
        self.assertEqual(response["statusCode"], 400)
        self.assertIn("chainId not allowed", response["body"])

    def test_status_rejects_invalid_status_value(self):
        app = _load_app()
        event = {
            "httpMethod": "POST",
            "path": "/instructions/0x" + "12" * 32 + "/status",
            "body": json.dumps({"status": "INVALID"}),
        }
        response = app.handler(event, None)
        self.assertEqual(response["statusCode"], 400)
        self.assertIn("status must be SUBMITTED, CONFIRMED, or FAILED", response["body"])


if __name__ == "__main__":
    unittest.main()

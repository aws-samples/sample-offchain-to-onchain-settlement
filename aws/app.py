import base64
import json
import os
import re
import time
from typing import Any, Dict, Tuple

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError

from crypto import keccak256
from csi import (
    build_csi,
    derive_instruction_id,
    hash_typed_data,
    idempotency_key,
    typed_data_payload,
    validate_intent,
)
from kms_signer import KmsSigner

ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
BYTES32_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")

INSTRUCTIONS_TABLE = os.environ.get("INSTRUCTIONS_TABLE")
IDEMPOTENCY_TABLE = os.environ.get("IDEMPOTENCY_TABLE")
AUDIT_TABLE = os.environ.get("AUDIT_TABLE")
RAW_BUCKET = os.environ.get("RAW_BUCKET")
KMS_KEY_ID = os.environ.get("KMS_KEY_ID")
VERIFYING_CONTRACT = os.environ.get("VERIFYING_CONTRACT", "0x0000000000000000000000000000000000000000")
STATUS_INDEX = os.environ.get("STATUS_INDEX", "status-index")
ALLOWED_CHAIN_ID = os.environ.get("ALLOWED_CHAIN_ID")

if not (INSTRUCTIONS_TABLE and IDEMPOTENCY_TABLE and AUDIT_TABLE and RAW_BUCKET and KMS_KEY_ID):
    raise RuntimeError("Missing required environment variables for AWS integration")

_dynamodb = boto3.resource("dynamodb")
_ddb_client = boto3.client("dynamodb")
_s3 = boto3.client("s3")
_serializer = TypeSerializer()
_deserializer = TypeDeserializer()

_instructions_table = _dynamodb.Table(INSTRUCTIONS_TABLE)
_idempotency_table = _dynamodb.Table(IDEMPOTENCY_TABLE)
_audit_table = _dynamodb.Table(AUDIT_TABLE)
_signer = KmsSigner(KMS_KEY_ID)


def _marshal(item: Dict[str, Any]) -> Dict[str, Any]:
    return {k: _serializer.serialize(v) for k, v in item.items()}


def _unmarshal(item: Dict[str, Any]) -> Dict[str, Any]:
    return {k: _deserializer.deserialize(v) for k, v in item.items()}


def _decimal_default(obj):
    from decimal import Decimal
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _json_response(status: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    body = json.dumps(payload, default=_decimal_default)
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": body,
    }


def _error(status: int, message: str) -> Dict[str, Any]:
    return _json_response(status, {"error": message})


def _parse_event(event: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
    path = event.get("path") or event.get("rawPath") or event.get("requestContext", {}).get("http", {}).get("path")
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    payload = json.loads(body) if body else {}
    return method, path, payload


def _require_address(value: str, field: str) -> str:
    if not isinstance(value, str) or not ADDRESS_RE.match(value):
        raise ValueError(f"{field} must be 20-byte hex address")
    return value.lower()


def _require_bytes32(value: str, field: str) -> str:
    if not isinstance(value, str) or not BYTES32_RE.match(value):
        raise ValueError(f"{field} must be bytes32 hex")
    return value.lower()


def _require_uint(value, field: str) -> int:
    if isinstance(value, str):
        if not value.isdigit():
            raise ValueError(f"{field} must be a number")
        value = int(value)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _normalize_raw_message(raw_message: str) -> bytes:
    if not isinstance(raw_message, str) or not raw_message:
        raise ValueError("rawMessage must be a non-empty string")
    return raw_message.encode("utf-8")


def _nonce_from_reference(reference: str) -> bytes:
    if not reference:
        return b"\x00" * 32
    return keccak256(reference.encode("utf-8"))


def _put_audit(instruction_id: str, action: str, detail: Dict[str, Any]) -> None:
    now = int(time.time())
    _audit_table.put_item(
        Item={
            "instructionId": instruction_id,
            "ts": now,
            "action": action,
            "detail": detail,
        }
    )


def _fetch_existing_by_idempotency(idempotency_hex: str) -> Dict[str, Any] | None:
    existing = _idempotency_table.get_item(Key={"idempotencyKey": idempotency_hex}).get("Item")
    if not existing:
        return None
    instruction_id = existing["instructionId"]
    record = _instructions_table.get_item(Key={"instructionId": instruction_id}).get("Item")
    return record


def _record_to_response(record: Dict[str, Any]) -> Dict[str, Any]:
    typed = record.get("typedData")
    if isinstance(typed, str):
        typed = json.loads(typed)
    last_status = record.get("lastStatus", {})
    return {
        "instruction": record["instruction"],
        "signature": record["signature"],
        "status": record["status"],
        "typedData": typed,
        "messageDigest": record["messageDigest"],
        "signer": record.get("signer"),
        "txHash": last_status.get("txHash") if isinstance(last_status, dict) else None,
    }


def _post_messages(payload: Dict[str, Any]) -> Dict[str, Any]:
    raw_message = payload.get("rawMessage")
    raw_bytes = _normalize_raw_message(raw_message)
    message_digest = keccak256(raw_bytes)

    asset = _require_address(payload.get("asset", ""), "asset")
    amount = _require_uint(payload.get("amount"), "amount")
    from_party = _require_address(payload.get("fromParty", ""), "fromParty")
    to_party = _require_address(payload.get("toParty", ""), "toParty")
    value_time = _require_uint(payload.get("valueTime"), "valueTime")
    intent = validate_intent(payload.get("intent"))
    chain_id = _require_uint(payload.get("chainId"), "chainId")
    if ALLOWED_CHAIN_ID and chain_id != int(ALLOWED_CHAIN_ID):
        raise ValueError("chainId not allowed")

    reference = payload.get("reference", "")
    nonce = _nonce_from_reference(reference)

    created_at = payload.get("createdAt")
    expiry = payload.get("expiry")
    expiry_seconds = payload.get("expirySeconds", 3600)

    now = int(time.time())
    created_at = _require_uint(created_at if created_at is not None else now, "createdAt")
    if expiry is None:
        expiry = created_at + _require_uint(expiry_seconds, "expirySeconds")
    expiry = _require_uint(expiry, "expiry")
    if expiry <= created_at:
        raise ValueError("expiry must be greater than createdAt")

    idempotency = idempotency_key(
        message_digest,
        asset,
        amount,
        from_party,
        to_party,
        value_time,
        intent,
        chain_id,
        reference or "",
    )
    idempotency_hex = "0x" + idempotency.hex()

    existing = _fetch_existing_by_idempotency(idempotency_hex)
    if existing:
        return _record_to_response(existing)

    instruction_id = derive_instruction_id(
        message_digest,
        asset,
        amount,
        from_party,
        to_party,
        value_time,
        intent,
        chain_id,
        created_at,
        expiry,
        nonce,
    )

    csi = build_csi(
        instruction_id,
        message_digest,
        asset,
        amount,
        from_party,
        to_party,
        value_time,
        created_at,
        expiry,
        intent,
        chain_id,
        nonce,
    )

    typed_data = typed_data_payload(csi, VERIFYING_CONTRACT)
    digest = hash_typed_data(csi, chain_id, VERIFYING_CONTRACT)
    signature = _signer.sign_digest(digest)

    message_digest_hex = "0x" + message_digest.hex()
    raw_key = f"raw/{message_digest_hex}.txt"
    _s3.put_object(Bucket=RAW_BUCKET, Key=raw_key, Body=raw_bytes)

    instruction_id_hex = "0x" + instruction_id.hex()
    now = int(time.time())
    instruction_map = csi.to_dict()

    record = {
        "instructionId": instruction_id_hex,
        "status": "PENDING",
        "createdAt": now,
        "updatedAt": now,
        "instruction": instruction_map,
        "messageDigest": message_digest_hex,
        "signature": signature["signature"],
        "signer": signature["signer"],
        "typedData": typed_data,
        "rawMessageKey": raw_key,
    }
    idempotency_item = {
        "idempotencyKey": idempotency_hex,
        "instructionId": instruction_id_hex,
        "createdAt": now,
    }
    audit_item = {
        "instructionId": instruction_id_hex,
        "ts": now,
        "action": "CREATED",
        "detail": {"status": "PENDING"},
    }

    try:
        _ddb_client.transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": IDEMPOTENCY_TABLE,
                        "Item": _marshal(idempotency_item),
                        "ConditionExpression": "attribute_not_exists(idempotencyKey)",
                    }
                },
                {
                    "Put": {
                        "TableName": INSTRUCTIONS_TABLE,
                        "Item": _marshal(record),
                        "ConditionExpression": "attribute_not_exists(instructionId)",
                    }
                },
                {
                    "Put": {
                        "TableName": AUDIT_TABLE,
                        "Item": _marshal(audit_item),
                        "ConditionExpression": "attribute_not_exists(instructionId) AND attribute_not_exists(ts)",
                    }
                },
            ]
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "TransactionCanceledException":
            existing = _fetch_existing_by_idempotency(idempotency_hex)
            if existing:
                return _record_to_response(existing)
        raise

    return _record_to_response(record)


def _get_pending() -> Dict[str, Any]:
    response = _instructions_table.query(
        IndexName=STATUS_INDEX,
        KeyConditionExpression=Key("status").eq("PENDING"),
    )
    items = response.get("Items", [])
    return {"pending": [_record_to_response(item) for item in items]}


def _get_all_instructions() -> Dict[str, Any]:
    response = _instructions_table.scan()
    items = response.get("Items", [])
    return {"instructions": [_record_to_response(item) for item in items]}


def _post_status(instruction_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    instruction_id = _require_bytes32(instruction_id, "instructionId")
    status = payload.get("status")
    if status not in {"SUBMITTED", "CONFIRMED", "FAILED"}:
        raise ValueError("status must be SUBMITTED, CONFIRMED, or FAILED")

    detail = {
        "status": status,
        "txHash": payload.get("txHash"),
        "workflowRunId": payload.get("workflowRunId"),
        "chainId": payload.get("chainId"),
        "reason": payload.get("reason"),
    }

    now = int(time.time())
    response = _instructions_table.update_item(
        Key={"instructionId": instruction_id},
        UpdateExpression="SET #s = :s, updatedAt = :u, lastStatus = :d",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": status, ":u": now, ":d": detail},
        ReturnValues="ALL_NEW",
    )
    _put_audit(instruction_id, "STATUS", detail)
    record = response.get("Attributes")
    if not record:
        raise KeyError("instruction not found")
    return _record_to_response(record)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    try:
        method, path, payload = _parse_event(event)
        if method == "POST" and path == "/messages":
            return _json_response(201, _post_messages(payload))
        if method == "GET" and path == "/instructions/pending":
            return _json_response(200, _get_pending())
        if method == "GET" and path == "/instructions":
            return _json_response(200, _get_all_instructions())
        if method == "POST" and path.startswith("/instructions/") and path.endswith("/status"):
            parts = path.strip("/").split("/")
            if len(parts) != 3:
                return _error(404, "not_found")
            instruction_id = parts[1]
            return _json_response(200, _post_status(instruction_id, payload))
        return _error(404, "not_found")
    except ValueError as exc:
        return _error(400, str(exc))
    except KeyError:
        return _error(404, "not_found")
    except Exception:
        return _error(500, "internal_error")

import unittest

from csi import idempotency_key, validate_intent


class TestCsiIdempotency(unittest.TestCase):
    def setUp(self):
        self.message_digest = bytes.fromhex("11" * 32)
        self.asset = "0x" + "22" * 20
        self.from_party = "0x" + "33" * 20
        self.to_party = "0x" + "44" * 20

    def test_idempotency_same_payload_same_key(self):
        key1 = idempotency_key(
            self.message_digest,
            self.asset,
            100,
            self.from_party,
            self.to_party,
            1_700_000_000,
            0,
            11155111,
            "REF-001",
        )
        key2 = idempotency_key(
            self.message_digest,
            self.asset,
            100,
            self.from_party,
            self.to_party,
            1_700_000_000,
            0,
            11155111,
            "REF-001",
        )
        self.assertEqual(key1, key2)

    def test_idempotency_reference_changes_key(self):
        key1 = idempotency_key(
            self.message_digest,
            self.asset,
            100,
            self.from_party,
            self.to_party,
            1_700_000_000,
            0,
            11155111,
            "REF-001",
        )
        key2 = idempotency_key(
            self.message_digest,
            self.asset,
            100,
            self.from_party,
            self.to_party,
            1_700_000_000,
            0,
            11155111,
            "REF-002",
        )
        self.assertNotEqual(key1, key2)

    def test_validate_intent_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            validate_intent("NOT_A_REAL_INTENT")


if __name__ == "__main__":
    unittest.main()

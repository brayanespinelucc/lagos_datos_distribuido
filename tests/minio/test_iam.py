"""Regresión del criterio IAM. El laboratorio Compose cubre la integración con MinIO."""
import json
import subprocess
import unittest
from unittest.mock import Mock

from lab import Lab


class IngestPermissionTests(unittest.TestCase):
    def lab(self, put_code="AccessDenied", read_status=404, read_code="NoSuchKey", rc=1, alias="ingesta-lab"):
        lab = Mock(spec=Lab)

        def mc(*args, **kwargs):
            if args[:2] == ("alias", "list"):
                body = {"accessKey": alias, "URL": "http://lb-minio:9000"}
            elif args[:3] == ("admin", "user", "info"):
                body = {"accessKey": "ingesta-lab", "policyName": "ingesta-bronze", "userStatus": "enabled"}
            else:
                return subprocess.CompletedProcess(args, rc, b"", b"Texto del cliente en otro idioma.")
            return subprocess.CompletedProcess(args, 0, json.dumps(body).encode(), b"")

        lab.mc.side_effect = mc
        lab.signed_request.side_effect = lambda method, key, identity, payload=None: (
            {"http": 403, "codigo_s3": put_code} if method == "PUT" else
            {"http": read_status, "codigo_s3": read_code})
        return lab

    def test_denial_does_not_depend_on_client_language(self):
        events = []
        Lab.check_permissions(self.lab(), lambda step, **data: events.append(data))
        self.assertEqual([e["bucket"] for e in events if "bucket" in e], ["gold", "silver"])

    def test_wrong_signature_and_invalid_key_are_not_policy_denials(self):
        for code in ("SignatureDoesNotMatch", "InvalidAccessKeyId"):
            with self.subTest(code=code), self.assertRaises(RuntimeError):
                Lab.check_permissions(self.lab(put_code=code), Mock())

    def test_admin_must_observe_absence_of_the_object_in_an_existing_bucket(self):
        for status, code in ((200, None), (403, "AccessDenied"), (404, "NoSuchBucket")):
            with self.subTest(status=status), self.assertRaises(RuntimeError):
                Lab.check_permissions(self.lab(read_status=status, read_code=code), Mock())

    def test_successful_cli_write_or_wrong_identity_fails(self):
        for lab in (self.lab(rc=0), self.lab(alias="otra-identidad")):
            with self.assertRaises(RuntimeError):
                Lab.check_permissions(lab, Mock())


if __name__ == "__main__":
    unittest.main()

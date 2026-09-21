# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Adapter base class contract.

Covers:

* PROVIDER_CODE / API_VERSION class attribute requirement.
* Profile-version mismatch raises with a clear message.
* Mock mode loads a fixture and writes a message log row.
* The dispatch chain serialise to call to log creation works for the
  happy path.

The tests register a TestAdapter into the registry; the
EhLogIntegrationTestCase common harness restores the registry between
tests so no leak.
"""
import json
import os
import tempfile
from pathlib import Path

from .common import EhLogIntegrationTestCase
from .. import adapter_registry
from ..adapters.base import BaseAdapter
from ..exceptions import ConfigurationMissingError


class TestAdapterRequiresClassAttributes(EhLogIntegrationTestCase):

    def test_missing_provider_code_raises(self):
        class BadAdapter(BaseAdapter):
            API_VERSION = "1.0"

        with self.assertRaises(ConfigurationMissingError) as ctx:
            BadAdapter(self.profile_test)
        self.assertIn("PROVIDER_CODE", str(ctx.exception))

    def test_missing_api_version_raises(self):
        class BadAdapter(BaseAdapter):
            PROVIDER_CODE = "test_provider"

        with self.assertRaises(ConfigurationMissingError) as ctx:
            BadAdapter(self.profile_test)
        self.assertIn("API_VERSION", str(ctx.exception))

    def test_provider_code_mismatch_raises(self):
        class WrongCodeAdapter(BaseAdapter):
            PROVIDER_CODE = "different_provider"
            API_VERSION = "1.0"

        with self.assertRaises(ConfigurationMissingError) as ctx:
            WrongCodeAdapter(self.profile_test)
        message = str(ctx.exception)
        self.assertIn("different_provider", message)
        self.assertIn("test_provider", message)

    def test_api_version_mismatch_raises(self):
        class WrongVersionAdapter(BaseAdapter):
            PROVIDER_CODE = "test_provider"
            API_VERSION = "2.0"

        with self.assertRaises(ConfigurationMissingError) as ctx:
            WrongVersionAdapter(self.profile_test)
        message = str(ctx.exception)
        self.assertIn("2.0", message)
        self.assertIn("1.0", message)


class TestAdapterMockMode(EhLogIntegrationTestCase):
    """Verify mock-mode dispatch round-trips through the message log.

    The TestAdapter writes its fixture file to a temp directory, then
    monkey-patches its own __module__ so the BaseAdapter's fixture
    lookup resolves to the temp directory.
    """

    def test_mock_call_loads_fixture_and_logs_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            module_dir = tmp_path / "fake_module"
            (module_dir / "tests" / "fixtures" / "test_provider").mkdir(
                parents=True, exist_ok=True,
            )
            fixture_path = (
                module_dir / "tests" / "fixtures" / "test_provider"
                / "ping.success.json"
            )
            fixture_path.write_text(
                json.dumps({"status": "ok", "echo": "hello"}),
                encoding="utf-8",
            )
            # Real adapters live in <module>/adapters/<provider>.py, so
            # the fixture lookup resolves the module root as the adapter
            # file's grandparent. Mirror that layout here.
            adapters_dir = module_dir / "adapters"
            adapters_dir.mkdir(parents=True, exist_ok=True)
            adapter_module_file = adapters_dir / "fake_adapter.py"
            adapter_module_file.write_text("# placeholder\n")

            class TestAdapter(BaseAdapter):
                PROVIDER_CODE = "test_provider"
                API_VERSION = "1.0"

                def serialize(self, message_type, payload):
                    return json.dumps(payload).encode("utf-8")

                def parse(self, message_type, raw):
                    return json.loads(raw)

            # Inject a synthetic module so BaseAdapter._call_mock resolves
            # the fixture root next to it.
            import sys
            import types
            fake_module = types.ModuleType("eh_log_base_test_fake_module")
            fake_module.__file__ = str(adapter_module_file)
            sys.modules[fake_module.__name__] = fake_module
            TestAdapter.__module__ = fake_module.__name__

            try:
                adapter_registry.register("test_provider", TestAdapter)
                adapter = TestAdapter(self.profile_test)
                result = adapter.call("ping", {"echo": "hello"})

                self.assertEqual(result.status, "success")
                self.assertEqual(result.parsed["echo"], "hello")
                self.assertTrue(result.message_id)

                message = self.env["eh.log.adapter.message"].browse(
                    result.message_id,
                )
                self.assertEqual(message.profile_id, self.profile_test)
                self.assertEqual(message.message_type, "ping")
                self.assertEqual(message.status, "success")
                self.assertEqual(message.direction, "outbound")
                self.assertIn("ok", message.response_payload)
            finally:
                sys.modules.pop(fake_module.__name__, None)


class TestAdapterRegistry(EhLogIntegrationTestCase):

    def test_register_and_get(self):
        class A(BaseAdapter):
            PROVIDER_CODE = "test_a"
            API_VERSION = "1.0"

        adapter_registry.register("test_a", A)
        self.assertIs(adapter_registry.get("test_a"), A)

    def test_get_missing_returns_none(self):
        self.assertIsNone(adapter_registry.get("never_registered"))

    def test_register_overwrites(self):
        class A(BaseAdapter):
            PROVIDER_CODE = "test_overwrite"
            API_VERSION = "1.0"

        class B(BaseAdapter):
            PROVIDER_CODE = "test_overwrite"
            API_VERSION = "2.0"

        adapter_registry.register("test_overwrite", A)
        adapter_registry.register("test_overwrite", B)
        self.assertIs(adapter_registry.get("test_overwrite"), B)

    def test_keys_lists_registered(self):
        class A(BaseAdapter):
            PROVIDER_CODE = "test_keys_listing"
            API_VERSION = "1.0"

        adapter_registry.register("test_keys_listing", A)
        self.assertIn("test_keys_listing", adapter_registry.keys())

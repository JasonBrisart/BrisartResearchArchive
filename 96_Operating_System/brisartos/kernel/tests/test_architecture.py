r"""
File: brisartos/kernel/tests/test_architecture.py

Purpose
-------
Exercise composition, persistent state, compatibility, manifests, lifecycle
failure cleanup and structured events across runtime boundaries.

Verifies: brisartos/events/events.py, brisartos/extensions/api.py,
brisartos/extensions/contracts.py, brisartos/host/serialization.py,
brisartos/kernel/composition.py, brisartos/kernel/kernel.py,
brisartos/services/registry.py, brisartos/services/settings.py,
brisartos/storage/schema.py, brisartos/storage/storage.py.

Contains 24 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.events.events (brisartos/events/events.py)
- brisartos.extensions.api (brisartos/extensions/api.py)
- brisartos.extensions.contracts (brisartos/extensions/contracts.py)
- brisartos.host.serialization (brisartos/host/serialization.py)
- brisartos.kernel.composition (brisartos/kernel/composition.py)
- brisartos.kernel.kernel (brisartos/kernel/kernel.py)
- brisartos.services.registry (brisartos/services/registry.py)
- brisartos.services.settings (brisartos/services/settings.py)
- brisartos.storage.schema (brisartos/storage/schema.py)
- brisartos.storage.storage (brisartos/storage/storage.py)
Standard library: pathlib, tempfile, unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/kernel/tests); nothing imports it.

Settings / parameters
---------------------
Each scenario constructs isolated runtime objects or temporary disk roots.

Edge cases
----------
Failed writes, corrupt state, incompatible manifests and failed cleanup hooks
are deliberately injected.

ArchitectureTests:
- Explicit composition.
- All service state survives new disk kernel.
- Memory kernel does not share state.
- Unknown schema is refused.
- Legacy files are preserved.
- Corrupt settings unwinds startup.
- Settings failed write does not publish.
- Persistent settings are detached.
- Serialization rejects unsupported values.
- State envelope rejects wrong kind.
- Service order and reverse cleanup.
- Service start failure cleans attempted service.
- Cleanup failure does not skip services.
- Stopping blocks module and shell work.
- Module cleanup continues after failure.
- Cancel closes started generator.
- Event append failure leaves no recent event.
- Structured details are detached.
- Task outcomes are structured.
- Facades hide lifecycle.
- Api compatibility.
- Manifest rejects before executing.
- Manifest is authoritative.
- Shutdown log failure still stops.

Known limitations
-----------------
- No power-loss, hostile-code isolation or hardware-boot validation is
  performed.
- Passing proves only the 24 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/kernel/tests -p test_architecture.py
"""

import tempfile
import unittest
from pathlib import Path
from brisartos.kernel.kernel import Kernel
from brisartos.kernel.composition import build_runtime
from brisartos.services.registry import ServiceRegistry
from brisartos.services.settings import Settings
from brisartos.storage.storage import Storage
from brisartos.storage.schema import FORMAT_PATH, SETTINGS_PATH, DATA_FORMAT, envelope, payload
from brisartos.host.serialization import encode_mapping, decode_mapping
from brisartos.extensions.api import ModuleAPI
from brisartos.extensions.contracts import check_compatibility
from brisartos.events.events import EventLog

class ArchitectureTests(unittest.TestCase):
    def test_explicit_composition(self):
        components = build_runtime()
        kernel = Kernel(components=components)
        self.assertIs(kernel.storage, components.storage)
        self.assertFalse(kernel.modules.context.accepting)
        kernel.start()
        self.assertTrue(kernel.modules.context.accepting)
        self.assertEqual(kernel.stop(), [])
    def test_all_service_state_survives_new_disk_kernel(self):
        with tempfile.TemporaryDirectory() as folder:
            first = Kernel(data_root=folder)
            first.start()
            first.storage.write('/work.txt', 'saved')
            first.services.get('settings').set('nested', {'a': [1, True]})
            first.services.get('archive').save('checkpoint')
            first.services.get('updates').stage('patch', 'print(1)')
            first.storage.write('/work.txt', 'changed')
            first.stop()
            second = Kernel(data_root=folder)
            second.start()
            self.assertEqual(second.services.get('settings').get('nested'), {'a': [1, True]})
            self.assertEqual(second.services.get('updates').inspect('patch')['source'], 'print(1)')
            second.services.get('archive').restore('checkpoint')
            self.assertEqual(second.storage.read('/work.txt'), 'saved')
            self.assertTrue(second.storage.exists(SETTINGS_PATH))
            self.assertEqual(second.stop(), [])
    def test_memory_kernel_does_not_share_state(self):
        a, b = Kernel(), Kernel()
        a.start(); b.start()
        a.services.get('settings').set('a', 1)
        self.assertIsNone(b.services.get('settings').get('a'))
        a.stop(); b.stop()
    def test_unknown_schema_is_refused(self):
        c = build_runtime()
        c.storage.write(FORMAT_PATH, 'future')
        k = Kernel(components=c)
        with self.assertRaises(ValueError): k.start()
        self.assertEqual(k.state, 'stopped')
        self.assertEqual(c.storage.read(FORMAT_PATH), 'future')
    def test_legacy_files_are_preserved(self):
        c = build_runtime()
        c.storage.write('/old.txt', 'keep')
        k = Kernel(components=c); k.start()
        self.assertEqual(k.storage.read('/old.txt'), 'keep')
        self.assertEqual(k.storage.read(FORMAT_PATH).strip(), DATA_FORMAT)
        k.stop()
    def test_corrupt_settings_unwinds_startup(self):
        c = build_runtime(); c.storage.write(SETTINGS_PATH, '{broken')
        k = Kernel(components=c)
        with self.assertRaises(ValueError): k.start()
        self.assertEqual(k.state, 'stopped')
        self.assertFalse(k.modules.context.accepting)
    def test_settings_failed_write_does_not_publish(self):
        class Broken(Storage):
            def write(self, path, text): raise OSError('full')
        s = Settings(Broken(), encode_mapping, decode_mapping)
        with self.assertRaises(OSError): s.set('a', 1)
        self.assertIsNone(s.get('a'))
    def test_persistent_settings_are_detached(self):
        s = Settings(Storage(), encode_mapping, decode_mapping)
        value = {'a': [1]}; s.set('x', value); value['a'].append(2)
        result = s.get('x'); result['a'].append(3)
        self.assertEqual(s.get('x'), {'a': [1]})
    def test_serialization_rejects_unsupported_values(self):
        for value in ({'a': object()}, {1: 'bad'}, {'a': (1,)}, {'a': float('nan')}):
            with self.assertRaises((TypeError, ValueError)): encode_mapping(value)
        with self.assertRaises(ValueError): decode_mapping('{"a":NaN}')
        with self.assertRaises(ValueError): decode_mapping('[]')
    def test_state_envelope_rejects_wrong_kind(self):
        with self.assertRaises(ValueError): payload(envelope('archive', {}), 'settings')
    def test_service_order_and_reverse_cleanup(self):
        order = []
        class Service:
            def __init__(self, name): self.name = name
            def start(self): order.append('start:' + self.name)
            def stop(self): order.append('stop:' + self.name)
        r = ServiceRegistry()
        r.register('a', Service('a')); r.register('b', Service('b'))
        r.start_all(); self.assertEqual(r.stop_all(), [])
        self.assertEqual(order, ['start:a', 'start:b', 'stop:b', 'stop:a'])
    def test_service_start_failure_cleans_attempted_service(self):
        order = []
        class Good:
            def start(self): order.append('start')
            def stop(self): order.append('stop')
        class Bad:
            def start(self): raise RuntimeError('start failure')
            def stop(self): order.append('bad stop')
        r = ServiceRegistry(); r.register('a', Good()); r.register('b', Bad())
        with self.assertRaisesRegex(RuntimeError, 'start failure'): r.start_all()
        self.assertEqual(order, ['start', 'bad stop', 'stop'])
    def test_cleanup_failure_does_not_skip_services(self):
        k = Kernel(); k.start(); order = []
        class Bad:
            def stop(self): order.append('bad'); raise RuntimeError('stop failure')
        class Good:
            def stop(self): order.append('good')
        k.services.register('good', Good()); k.services.register('bad', Bad())
        # Late registration is started explicitly here as a lifecycle test fixture.
        k.services._started.extend(['good', 'bad'])
        errors = k.stop()
        self.assertEqual(order, ['bad', 'good'])
        self.assertTrue(any('stop failure' in item['error'] for item in errors))
        self.assertEqual(k.state, 'stopped')
    def test_stopping_blocks_module_and_shell_work(self):
        k = Kernel(); k.start(); observations = []
        def hook():
            observations.append(k.state)
            with self.assertRaises(RuntimeError): k.modules.run('demo')
            with self.assertRaises(RuntimeError): k.run_file('/x')
        k.modules.register('demo', lambda api: None, shutdown=hook)
        k.stop(); self.assertEqual(observations, ['stopping'])
    def test_module_cleanup_continues_after_failure(self):
        k = Kernel(); k.start(); order = []
        def bad(): order.append('bad'); raise RuntimeError('module cleanup')
        k.modules.register('first', lambda api: None, shutdown=lambda: order.append('first'))
        k.modules.register('bad', lambda api: None, shutdown=bad)
        self.assertTrue(k.stop()); self.assertEqual(order, ['bad', 'first'])
    def test_cancel_closes_started_generator(self):
        k = Kernel(); k.start(); closed = []
        def task():
            try: yield 1
            finally: closed.append(True)
        k.scheduler.spawn('demo', task()); k.scheduler.step(); k.stop()
        self.assertEqual(closed, [True])
    def test_event_append_failure_leaves_no_recent_event(self):
        class Broken:
            def append(self, path, text): raise OSError('full')
        e = EventLog(Broken(), lambda: 'T')
        with self.assertRaises(OSError): e.record('demo', 'message')
        self.assertEqual(e.total, 0); self.assertEqual(e.recent(), [])
    def test_structured_details_are_detached(self):
        e = EventLog(Storage(), lambda: 'T'); details = {'a': [1]}
        e.record('demo', 'ready', kind='module.loaded', details=details)
        details['a'].append(2); result = e.recent(); result[0]['details']['a'].append(3)
        self.assertEqual(e.recent()[0]['details'], {'a': [1]})
    def test_task_outcomes_are_structured(self):
        k = Kernel(); k.start(); k.scheduler.spawn('demo', iter([1])); k.scheduler.run()
        kinds = [e['kind'] for e in k.events.recent()]
        self.assertIn('task.spawned', kinds); self.assertIn('task.finished', kinds)
        k.stop()
    def test_facades_hide_lifecycle(self):
        k = Kernel(); k.start()
        api = ModuleAPI(k.modules.context, 'demo', ('service:settings', 'service:archive', 'service:updates'))
        for name in ('settings', 'archive', 'updates'):
            facade = api.get_service(name)
            self.assertIsNot(facade, k.services.get(name))
            self.assertFalse(hasattr(facade, 'start')); self.assertFalse(hasattr(facade, 'stop'))
        k.stop()
    def test_api_compatibility(self):
        self.assertEqual(check_compatibility(('brisartos.module', 1, 0)), ('brisartos.module', 1, 0))
        for api in (('other', 1, 0), ('brisartos.module', 2, 0), ('brisartos.module', 1, 1), ('brisartos.module', True, 0), ('brisartos.module', 1, -1)):
            with self.assertRaises(ValueError): check_compatibility(api)
    def test_manifest_rejects_before_executing(self):
        with tempfile.TemporaryDirectory() as folder:
            d = Path(folder) / 'demo'; d.mkdir()
            marker = Path(folder) / 'executed'
            (d / 'module.py').write_text('from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n')
            manifest = 'name=demo\ndisplay_name=Demo\nversion=runtime\nauthor=Test\ndescription=Test\napi=brisartos.module\napi_major=2\napi_minor=0\npermissions=\nentry=run\n'
            (d / 'manifest.txt').write_text(manifest)
            k = Kernel(modules_path=folder); k.start()
            self.assertIn('demo', k.modules.failures); self.assertFalse(marker.exists())
            k.stop()
    def test_manifest_is_authoritative(self):
        with tempfile.TemporaryDirectory() as folder:
            d = Path(folder) / 'demo'; d.mkdir()
            (d / 'module.py').write_text('def run(api): return "ok"\n')
            (d / 'manifest.txt').write_text('name=demo\ndisplay_name=Demo\nversion=runtime\nauthor=Test\ndescription=Test\napi=brisartos.module\napi_major=1\napi_minor=0\npermissions=\nentry=run\n')
            k = Kernel(modules_path=folder); k.start()
            self.assertEqual(k.modules.run('demo'), 'ok')
            self.assertEqual(k.modules.describe('demo')['api'], ('brisartos.module', 1, 0))
            k.stop()
    def test_shutdown_log_failure_still_stops(self):
        k = Kernel(); k.start()
        def broken(*args, **kwargs): raise OSError('logging failed')
        k.events.record = broken
        self.assertTrue(k.stop()); self.assertEqual(k.state, 'stopped')

if __name__ == '__main__':
    unittest.main()

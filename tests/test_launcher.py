import unittest,tempfile
from pathlib import Path
from unittest.mock import patch,Mock
import test_financials as fixture
import launcher
class LauncherTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        p=patch.object(launcher,'ROOT',Path(tmp.name));p.start();self.addCleanup(p.stop)
    def test_reuses_healthy_instance_without_starting_process(self):
        with patch.object(launcher,'healthy',return_value=True),patch.object(launcher.subprocess,'Popen') as start:
            self.assertIn('already running',launcher.launch());start.assert_not_called()
    def test_occupied_port_never_starts_or_kills(self):
        with patch.object(launcher,'healthy',return_value=False),patch.object(launcher,'occupied',return_value=True),patch.object(launcher.subprocess,'Popen') as start:
            with self.assertRaisesRegex(RuntimeError,'No process was stopped'):launcher.launch()
            start.assert_not_called()
    def test_missing_dependencies_no_start(self):
        with patch.object(launcher,'healthy',return_value=False),patch.object(launcher,'occupied',return_value=False),patch.object(launcher.subprocess,'run',return_value=Mock(returncode=1,stderr='missing')),patch.object(launcher.subprocess,'Popen') as start:
            with self.assertRaisesRegex(RuntimeError,'missing Flask or ReportLab'):launcher.launch()
            start.assert_not_called()
    def test_start_waits_for_matching_health(self):
        with patch.object(launcher,'healthy',side_effect=[False,True]),patch.object(launcher,'occupied',return_value=False),patch.object(launcher.subprocess,'run',return_value=Mock(returncode=0)),patch.object(launcher.subprocess,'Popen',return_value=Mock(pid=123)) as start:
            self.assertEqual(launcher.launch(),'PFMS is ready.')
            self.assertTrue(start.call_args.kwargs['start_new_session'])
            self.assertEqual((launcher.ROOT/'.runtime/server.pid').read_text(),'123')
    def test_failure_does_not_open_browser(self):
        with patch.object(launcher,'launch',side_effect=RuntimeError('failed')),patch.object(launcher.subprocess,'run') as run:
            self.assertEqual(launcher.main(),1);run.assert_not_called()

"""The local launcher must release its ports even during repeated Ctrl+C."""
import importlib.util
from pathlib import Path
import signal
import socket


def launcher():
    spec = importlib.util.spec_from_file_location("project_launcher", Path(__file__).resolve().parents[2] / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shutdown_closes_port_and_backend(monkeypatch):
    module = launcher()
    httpd = module.serve_frontend(0)
    port = httpd.server_address[1]
    stopped = []
    backend = object()
    previous = signal.getsignal(signal.SIGINT)
    def stop(process):
        assert signal.getsignal(signal.SIGINT) == signal.SIG_IGN
        stopped.append(process)
    monkeypatch.setattr(module, "stop_tree", stop)
    module.stop_services(httpd, backend)
    assert stopped == [backend]
    assert signal.getsignal(signal.SIGINT) == previous
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))

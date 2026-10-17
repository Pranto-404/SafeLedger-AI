"""Actual child-listener teardown regression;test harness must not leak npm-like children."""
import os
import socket
import subprocess
import sys
import pytest
from scripts.m4_browser_demo import stop_process,verify_ports_closed


@pytest.mark.skipif(os.name!='posix',reason='POSIX process-group cleanup;Windows requires separate qualification')
def test_process_group_cleanup_closes_child_listener(tmp_path):
    ready=tmp_path/'ready'
    child="import socket,time;import pytest;s=socket.socket();s.bind(('127.0.0.1',0));s.listen();Path(%r).write_text(str(s.getsockname()[1]));time.sleep(60)"%str(ready)
    parent="import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',%r]);time.sleep(60)"%child
    process=subprocess.Popen([sys.executable,'-c',parent],start_new_session=True)
    try:
        import time
        for _ in range(100):
            if ready.exists():break
            time.sleep(.02)
        assert ready.exists()
        number=int(ready.read_text())
        with socket.create_connection(('127.0.0.1',number),timeout=1):pass
        stop_process(process)
        verify_ports_closed([number])
    finally:
        if process.poll() is None:stop_process(process)

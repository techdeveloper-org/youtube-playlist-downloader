import pytest
import os
import threading
from extractor import extract_playlist_info
from downloaders import IDMDownloader
from unittest.mock import patch, MagicMock

import downloaders

def test_idm_downloader_flags():
    downloader = IDMDownloader()
    with patch('subprocess.Popen') as mock_popen:
        with patch('downloaders.find_idm', return_value='/mock/idm.exe'):
            with patch('os.path.exists', return_value=True):
                downloader._add_to_idm("http://url", "/out", "file.mp4")
                
                # Verify the exact flags are used: /n and /a
                calls = mock_popen.call_args_list
                assert len(calls) > 0
                cmd = calls[0][0][0]
                assert "/n" in cmd
                assert "/a" in cmd
                assert "/d" in cmd
                assert "http://url" in cmd
                assert "/p" in cmd
                assert "/out" in cmd
                assert "/f" in cmd
                assert "file.mp4" in cmd

def test_extract_playlist_info_cancellation():
    cancel_event = threading.Event()
    cancel_event.set()
    # Popen should immediately return "Canceled" due to the mock loop polling the event
    with patch('subprocess.Popen') as mock_popen:
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.returncode = -1
        mock_popen.return_value = mock_proc
        
        try:
            extract_playlist_info("http://url", cancel_event)
        except RuntimeError as e:
            assert "Canceled" in str(e)
            assert mock_proc.terminate.called


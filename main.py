#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Main entrypoint for youtube_playlist_downloader package"""

import sys
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

import customtkinter as ctk
from gui import DownloaderView
from controller import DownloaderController

def main():
    root = ctk.CTk()
    # To resolve chicken-and-egg dependency, we pass None first
    view = DownloaderView(root, None)
    controller = DownloaderController(view)
    view.controller = controller
    
    root.mainloop()

if __name__ == "__main__":
    main()

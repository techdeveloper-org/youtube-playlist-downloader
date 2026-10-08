#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Filesystem helpers"""

from typing import List


def remove_url_from_file(urls_file: str, url: str):
    try:
        with open(urls_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        with open(urls_file, "w", encoding="utf-8") as f:
            for line in lines:
                if url not in line:
                    f.write(line)
    except Exception:
        pass


def save_urls_to_file(urls: List[str], filepath: str):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(urls))


def load_urls_from_file(filepath: str) -> List[str]:
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

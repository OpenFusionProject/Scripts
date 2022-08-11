#!/usr/bin/env python
# coding: utf-8

import os
import sys
from swapper import process

def process_file(filename, suffix):
    dot = filename.rfind(".")
    if dot > -1:
        outfile_name = filename[:dot] + suffix + filename[dot:]
    else:
        outfile_name = filename + suffix
    return process(filename, outfile_name)

def process_batch(path, suffix="_hlsl"):
    files = os.listdir(path)
    for f in files:
        if os.path.isdir(f):
            process_batch(f"{path}/{f}")
        else:
            try:
                if process_file(f"{path}/{f}", suffix):
                    print(f"Processed {f}")
                else:
                    print(f"Skipping {f}")
            except ValueError as err:
                print(f"Failed to process {f}: {err}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: main.py <folder> [outfile-suffix]")
    elif len(sys.argv) == 2:
        process_batch(sys.argv[1])
    else:
        process_batch(*sys.argv[1:3])


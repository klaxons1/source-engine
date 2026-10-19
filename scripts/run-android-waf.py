#!/usr/bin/env python3
"""Stream a build command and expose its failure tail as a GitHub annotation."""
import argparse
from collections import deque
import os
from pathlib import Path
import re
import subprocess
import sys


def annotate(text):
    if os.environ.get("GITHUB_ACTIONS") == "true":
        text = re.sub(r"\x1b\[[0-9;]*m", "", text)
        # Workflow command data escaping, including literal percent signs.
        # GitHub truncates an annotation at 4096 decoded characters. Keep
        # the ACTUAL failure tail, not the first 4K of a much longer build log.
        text = text[-3800:].replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print("::error title=Android Waf failure::" + text, flush=True)


def run(command, config_log=None):
    tail = deque(maxlen=70)
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace", bufsize=1)
    except OSError as error:
        print(str(error), file=sys.stderr)
        annotate(str(error))
        return 127
    for line in process.stdout:
        print(line, end="", flush=True)
        tail.append(line)
    process.stdout.close()
    code = process.wait()
    if code:
        details = "".join(tail)
        if config_log and config_log.is_file():
            lines = config_log.read_text(encoding="utf-8", errors="replace").splitlines()
            details += "\n--- config.log tail ---\n" + "\n".join(lines[-70:])
        annotate(details or "Build command exited with code " + str(code))
    return code if code >= 0 else 128 - code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-log", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error("a build command is required")
    sys.exit(run(args.command, args.config_log))

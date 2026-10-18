#!/usr/bin/env python3
"""Compile and run the actual Android-independent Java launch policy tests."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def run():
    java = os.environ.get("JAVA", shutil.which("java"))
    compiler_jar = os.environ.get("JAVA_COMPILER_JAR")
    javac = os.environ.get("JAVAC", shutil.which("javac"))
    if not java or (not compiler_jar and not javac):
        raise RuntimeError("A Java runtime/compiler is required for the launcher contract tests")
    compiler = [java, "-jar", compiler_jar] if compiler_jar else [javac]
    with tempfile.TemporaryDirectory(prefix="underhell-java-tests-") as tmp:
        subprocess.run(compiler + ["-source", "8", "-target", "8", "-d", tmp,
            str(ROOT / "assets/android/java/me/nillerusr/UnderhellLaunchContract.java"),
            str(ROOT / "scripts/tests/UnderhellLaunchContractTest.java")], check=True)
        subprocess.run([java, "-cp", tmp, "UnderhellLaunchContractTest"], check=True)


if __name__ == "__main__":
    run()

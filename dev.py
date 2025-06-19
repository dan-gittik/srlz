import contextlib
import functools
import http.server
import pathlib
import shutil
import subprocess
import tomllib
from typing import Any

import click

ROOT = pathlib.Path(__file__).parent
PACKAGE: str = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["name"]
LINE_LENGTH = 120
COVERAGE_PORT = 8888
ARTEFACTS = [
    ".pytest_cache",
    ".coverage",
    "htmlcov",
    ".mypy_cache",
]


@click.group()
def main() -> None:
    pass


@main.command()
def clean() -> None:
    for path in ROOT.rglob("*"):
        if path.name not in ARTEFACTS:
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


@main.command()
@click.argument("args", nargs=-1)
def test(args: list[str]) -> None:
    tests = []
    for arg in args:
        tests.extend(["-k", arg])
    _execute("pytest", "tests", "-x", "-vv", "--ff", *tests)


@main.command()
def cov() -> None:
    _execute("pytest", f"--cov={PACKAGE}", "--cov-report=html", "tests")
    _serve(ROOT / "htmlcov", COVERAGE_PORT)


@main.command()
@click.argument("args", nargs=-1)
def lint(args: list[str]) -> None:
    paths = []
    for arg in args:
        path = ROOT / PACKAGE / arg.replace(".", "/")
        if not path.exists():
            path = path.with_suffix(".py")
        if not path.exists():
            raise FileNotFoundError(f"{path} does not exist")
        paths.append(path)
    if not paths:
        paths.extend([ROOT / PACKAGE, ROOT / "tests"])
    for path in paths:
        _execute("black", f"--line-length={LINE_LENGTH}", path)
        _execute("isort", "--profile=black", path)
        _execute("flake8", f"--max-line-length={LINE_LENGTH}", "--extend-ignore=E203", path)


@main.command()
@click.argument("args", nargs=-1)
def type(args: list[str]) -> None:
    packages = []
    for arg in args:
        packages.extend(["-p", f"{PACKAGE}.{arg}"])
    if not packages:
        packages.extend(["-p", PACKAGE])
    _execute("mypy", *packages)


def _execute(*args: Any) -> None:
    subprocess.run([str(arg) for arg in args])


def _serve(directory: pathlib.Path, port: int) -> None:
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(directory),
    )
    server = http.server.HTTPServer(("localhost", port), handler)
    print(f"http://localhost:{port}")
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()


if __name__ == "__main__":
    main()

"""Validate release packages and create the source ZIP used by Discord hosts."""

import argparse
import logging
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

import tomllib

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]


def require_members(label: str, actual: set[str], expected: set[str]) -> None:
    missing, extra = expected - actual, actual - expected
    if missing or extra:
        raise ValueError(f"{label}: missing={sorted(missing)}, unexpected={sorted(extra)}")


def package_runtime(dist: Path) -> Path:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    name, version = project["name"].replace("-", "_"), project["version"]
    python_files = {"bot.py", "main.py", "database.py", "utils.py"}
    python_files.update(path.relative_to(ROOT).as_posix() for path in (ROOT / "cogs").glob("*.py"))
    licenses = {
        path.name for pattern in ("LICENSE", "LICENSE.*", "COPYING") for path in ROOT.glob(pattern) if path.is_file()
    }
    runtime_files = python_files | licenses | {"requirements.txt", ".env.example", "readme.md", "commands.md"}
    wheel = dist / f"{name}-{version}-py3-none-any.whl"
    sdist = dist / f"{name}-{version}.tar.gz"
    runtime = dist / f"{name}-{version}-runtime.zip"
    unexpected = {path.name for path in dist.iterdir()} - {wheel.name, sdist.name, runtime.name}
    if unexpected:
        raise ValueError(f"Unexpected release output files: {sorted(unexpected)}")

    with zipfile.ZipFile(wheel) as archive:
        members = {entry.filename for entry in archive.infolist() if not entry.is_dir()}
        metadata_prefix = f"{name}-{version}.dist-info/"
        metadata = {metadata_prefix + item for item in ("METADATA", "WHEEL", "top_level.txt", "RECORD")}
        metadata.update(metadata_prefix + "licenses/" + item for item in licenses)
        require_members("wheel", members, python_files | metadata)
        if len(members) != len([entry for entry in archive.infolist() if not entry.is_dir()]):
            raise ValueError("Duplicate wheel members")

    with tarfile.open(sdist, "r:gz") as archive:
        members = set()
        prefix = f"{name}-{version}"
        for entry in archive.getmembers():
            path = PurePosixPath(entry.name)
            if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != prefix:
                raise ValueError(f"Unsafe source distribution member: {entry.name}")
            if entry.isdir():
                continue
            if not entry.isfile():
                raise ValueError(f"Non-file source distribution member: {entry.name}")
            relative = path.relative_to(prefix).as_posix()
            if relative in members:
                raise ValueError(f"Duplicate source distribution member: {entry.name}")
            members.add(relative)
        build_files = {"pyproject.toml", "MANIFEST.in", "PKG-INFO", "setup.cfg"}
        egg_info = {
            f"{name}.egg-info/{item}"
            for item in ("PKG-INFO", "SOURCES.txt", "dependency_links.txt", "requires.txt", "top_level.txt")
        }
        # Setuptools may omit source-tree egg metadata after the manifest excludes it.
        require_members("sdist", members - egg_info, runtime_files | build_files)

    with zipfile.ZipFile(runtime, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in sorted(runtime_files):
            source = ROOT / relative
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"Runtime member is not a regular file: {relative}")
            archive.write(source, relative)
    with zipfile.ZipFile(runtime) as archive:
        require_members("runtime ZIP", set(archive.namelist()), runtime_files)
        invalid = archive.testzip()
        if invalid is not None:
            raise ValueError(f"Corrupt runtime ZIP member: {invalid}")
    logger.info("Validated wheel and sdist; created %s with %s runtime files", runtime, len(runtime_files))
    return runtime


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    package_runtime(parser.parse_args().dist)

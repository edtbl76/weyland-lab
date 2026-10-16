"""scripts/lib/dockerfile_installs.py — count packages a Dockerfile installs outside a requirements file (2026-10-16).

Why: 14 Dockerfiles installed 103 Python packages straight from `pip install` lines (23 pinned, 80 unpinned). No source
scanner reads them (tool-server's mcp 1.28.1 hid in one through GHSA-84m7-p3x7-pcfv), and an unpinned one drifts on any
rebuild (the class that took Dagster down on 2026-10-01). The guard holds a per-Dockerfile ceiling that may only fall:
move installs into a pinned requirements file, lower the baseline. Every stage counts, builder stages included.
"""
import dockerfile_installs as d


def test_a_direct_install_counts_each_package_pinned_or_not():
    text = "FROM python:3.12-slim\nRUN pip install --no-cache-dir 'fastapi==0.139.2' uvicorn httpx\n"
    assert d.packages(text) == ["fastapi==0.139.2", "uvicorn", "httpx"]


def test_a_requirements_file_install_is_not_counted():
    text = "RUN pip install --no-cache-dir -r requirements.txt\nRUN pip install -r /tmp/r.txt --no-deps\n"
    assert d.packages(text) == []


def test_continuation_lines_and_chained_commands_are_read():
    text = ("RUN apt-get update && pip install --no-cache-dir \\\n    psycopg2-binary \\\n    'qdrant-client' \\\n"
            "    && rm -rf /var/lib/apt/lists/*\n")
    assert d.packages(text) == ["psycopg2-binary", "qdrant-client"]


def test_comments_never_count():
    # the first inventory pass counted words in comments as packages ("this", "used", "to")
    text = "# this used to pip install fastmcp unpinned\nRUN pip install -r requirements.txt\n"
    assert d.packages(text) == []


def test_option_values_and_local_paths_are_not_packages():
    text = ("RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu\n"
            "RUN pip install --target /opt/x ./dist/pkg.whl . /src\n")
    assert d.packages(text) == ["torch"]


def test_uv_pip_and_pip3_count_too():
    assert d.packages("RUN uv pip install --system polars\nRUN pip3 install duckdb\n") == ["polars", "duckdb"]


def test_a_count_above_the_baseline_fails_and_names_the_file():
    bad, lower = d.compare({"a/Dockerfile": 5, "b/Dockerfile": 2}, {"a/Dockerfile": 3, "b/Dockerfile": 2})
    assert bad == ["a/Dockerfile: 5 direct pip install(s), baseline 3"]
    assert lower == []


def test_a_new_dockerfile_with_direct_installs_fails():
    bad, _ = d.compare({"new/Dockerfile": 1}, {})
    assert bad == ["new/Dockerfile: 1 direct pip install(s), baseline 0 (not in the baseline)"]


def test_a_count_below_the_baseline_asks_for_the_baseline_to_be_lowered():
    bad, lower = d.compare({"a/Dockerfile": 1}, {"a/Dockerfile": 3, "gone/Dockerfile": 2})
    assert bad == []
    assert lower == ["a/Dockerfile: 1 < baseline 3", "gone/Dockerfile: 0 < baseline 2"]


def test_the_baseline_file_round_trips(tmp_path):
    p = tmp_path / "baseline"
    d.write_baseline(str(p), {"b/Dockerfile": 2, "a/Dockerfile": 3, "z/Dockerfile": 0})
    assert d.read_baseline(str(p)) == {"a/Dockerfile": 3, "b/Dockerfile": 2}     # zeros are not stored


def test_a_pep508_url_reference_is_one_package():
    # tool-server installs grkit as 'grkit @ https://github.com/.../archive/<sha>.tar.gz#subdirectory=python'
    text = "RUN pip install 'grkit @ https://github.com/edtbl76/grkit/archive/0d07977.tar.gz#subdirectory=python' httpx\n"
    assert d.packages(text) == ["grkit @ https://github.com/edtbl76/grkit/archive/0d07977.tar.gz#subdirectory=python",
                                "httpx"]
    assert d.packages("RUN pip install grkit @ https://x/y.tar.gz\n") == ["grkit @ https://x/y.tar.gz"]

"""builtin tools tests — push coverage over 70%"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import tempfile


def test_echo():
    from bot001.tools.builtin import echo

    assert echo("hello") == "hello"
    assert echo("") == ""
    assert echo("中文") == "中文"
    print("✅ echo")


def test_grep_file_not_found():
    from bot001.tools.builtin import grep

    r = grep("hello", "/nonexistent/path/123")
    assert "not found" in r.lower() or "error" in r.lower()
    print("✅ grep_file_not_found")


def test_grep_on_file(tmp_path):
    from bot001.tools.builtin import grep

    f = tmp_path / "test.txt"
    f.write_text("line1 hello world\nline2 foo bar\nline3 hello again")
    r = grep("hello", str(f))
    assert "2 matches" in r  # hello appears twice
    print("✅ grep_on_file")


def test_grep_on_dir(tmp_path):
    from bot001.tools.builtin import grep

    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("target content")
    f2.write_text("other content")

    r = grep("target", str(tmp_path))
    assert "1 files" in r or "a.txt" in r
    print("✅ grep_on_dir")


def test_shell_whitelist():
    from bot001.tools.builtin import shell

    # whitelisted commands
    r = shell("echo hello")
    assert "hello" in r
    # non-whitelisted
    r2 = shell("rm -rf /")
    assert "not in whitelist" in r2
    print("✅ shell_whitelist")


def test_shell_stderr(tmp_path):
    from bot001.tools.builtin import shell

    # stderr should be captured
    r = shell("ls /nonexistent_dir_xyz 2>&1 || true")
    # should not raise, should return something
    assert isinstance(r, str)
    print("✅ shell_stderr")


def test_shell_work_dir(tmp_path):
    from bot001.tools.builtin import shell

    f = tmp_path / "marker.txt"
    f.write_text("x")
    r = shell("cat marker.txt", work_dir=str(tmp_path))
    assert "x" in r
    print("✅ shell_work_dir")


def test_file_read_not_found():
    from bot001.tools.builtin import file_read

    r = file_read("/nonexistent/file_12345.txt")
    assert "not found" in r.lower() or "error" in r.lower()
    print("✅ file_read_not_found")


def test_file_read_ok(tmp_path):
    from bot001.tools.builtin import file_read

    f = tmp_path / "readme.txt"
    f.write_text("hello world")
    r = file_read(str(f))
    assert "hello world" in r
    print("✅ file_read_ok")


def test_file_read_truncate(tmp_path):
    from bot001.tools.builtin import file_read

    f = tmp_path / "large.txt"
    f.write_text("x" * 5000)
    r = file_read(str(f))
    assert len(r) <= 4000  # truncated
    print("✅ file_read_truncate")


def test_file_write(tmp_path):
    from bot001.tools.builtin import file_write

    f = tmp_path / "written.txt"
    r = file_write(str(f), "content here")
    assert "written" in r.lower()
    assert f.read_text() == "content here"
    print("✅ file_write")


def test_file_write_nested(tmp_path):
    from bot001.tools.builtin import file_write

    nested = tmp_path / "a" / "b" / "c.txt"
    r = file_write(str(nested), "nested content")
    assert "written" in r.lower()
    assert nested.read_text() == "nested content"
    print("✅ file_write_nested")


def test_register_builtin_tools():
    from bot001.tools.registry import ToolRegistry
    from bot001.tools.builtin import register_builtin_tools

    reg = ToolRegistry()
    register_builtin_tools(reg)
    tools = reg.list_tools()
    names = [t.name for t in tools]
    assert "echo" in names
    assert "grep" in names
    assert "shell" in names
    assert "file_read" in names
    assert "file_write" in names
    print("✅ register_builtin_tools")


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_echo()
        test_grep_file_not_found()
        test_grep_on_file(Path(td) / "f")
        test_grep_on_dir(Path(td) / "d")
        test_shell_whitelist()
        test_shell_stderr()
        test_shell_timeout()
        test_shell_work_dir(Path(td))
        test_file_read_not_found()
        test_file_read_ok(Path(td))
        test_file_read_truncate(Path(td))
        test_file_write(Path(td))
        test_file_write_nested(Path(td))
        test_register_builtin_tools()
    print("\n🎉 All builtin tests passed!")

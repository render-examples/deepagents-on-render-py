"""Tests for agents/tools/code_analysis.py — static analysis tools."""

from agents.tools.code_analysis import (
    detect_language,
    extract_functions,
    find_patterns,
    check_imports,
)


class TestDetectLanguage:
    def test_python(self):
        assert detect_language.invoke({"file_path": "src/main.py"}) == "python"

    def test_typescript(self):
        assert detect_language.invoke({"file_path": "app/index.ts"}) == "typescript"

    def test_tsx(self):
        assert detect_language.invoke({"file_path": "Component.tsx"}) == "typescript"

    def test_javascript(self):
        assert detect_language.invoke({"file_path": "utils.js"}) == "javascript"

    def test_go(self):
        assert detect_language.invoke({"file_path": "cmd/server/main.go"}) == "go"

    def test_rust(self):
        assert detect_language.invoke({"file_path": "src/lib.rs"}) == "rust"

    def test_java(self):
        assert detect_language.invoke({"file_path": "App.java"}) == "java"

    def test_yaml(self):
        assert detect_language.invoke({"file_path": "config.yml"}) == "yaml"
        assert detect_language.invoke({"file_path": "config.yaml"}) == "yaml"

    def test_unknown(self):
        assert detect_language.invoke({"file_path": "Makefile"}) == "unknown"
        assert detect_language.invoke({"file_path": "data.xyz"}) == "unknown"

    def test_case_insensitive_path(self):
        assert detect_language.invoke({"file_path": "Main.PY"}) == "python"

    def test_nested_path(self):
        assert detect_language.invoke({"file_path": "a/b/c/d/e.go"}) == "go"


class TestExtractFunctions:
    def test_python_functions(self, python_code):
        result = extract_functions.invoke({"code": python_code, "language": "python"})
        names = [f["name"] for f in result]
        assert "__init__" in names
        assert "greet" in names
        assert "fetch_data" in names
        assert "top_level_function" in names
        assert "async_top_level" in names

    def test_python_function_lines(self, python_code):
        result = extract_functions.invoke({"code": python_code, "language": "python"})
        by_name = {f["name"]: f["line"] for f in result}
        assert by_name["__init__"] < by_name["greet"] < by_name["top_level_function"]

    def test_go_functions(self, go_code):
        result = extract_functions.invoke({"code": go_code, "language": "go"})
        names = [f["name"] for f in result]
        assert "main" in names
        assert "HandleRequest" in names
        assert "helper" in names

    def test_javascript_functions(self, js_code):
        result = extract_functions.invoke({"code": js_code, "language": "javascript"})
        names = [f["name"] for f in result]
        assert "handleRequest" in names
        assert "processData" in names
        assert "fetchUser" in names

    def test_unsupported_language_returns_empty(self):
        result = extract_functions.invoke({"code": "some code", "language": "cobol"})
        assert result == []

    def test_empty_code(self):
        result = extract_functions.invoke({"code": "", "language": "python"})
        assert result == []


class TestFindPatterns:
    def test_python_dangerous_patterns(self, dangerous_python):
        result = find_patterns.invoke({
            "code": dangerous_python,
            "file_path": "script.py",
        })
        concerns = [f["concern"] for f in result]
        assert any("eval()" in c for c in concerns)
        assert any("os.system()" in c for c in concerns)
        assert any("pickle" in c for c in concerns)

    def test_python_hardcoded_secrets(self, dangerous_python):
        result = find_patterns.invoke({
            "code": dangerous_python,
            "file_path": "script.py",
        })
        concerns = [f["concern"] for f in result]
        assert any("password" in c for c in concerns)
        assert any("API key" in c for c in concerns)

    def test_javascript_dangerous_patterns(self, dangerous_js):
        result = find_patterns.invoke({
            "code": dangerous_js,
            "file_path": "app.js",
        })
        concerns = [f["concern"] for f in result]
        assert any("eval()" in c for c in concerns)
        assert any("innerHTML" in c for c in concerns)
        assert any("document.write()" in c for c in concerns)
        assert any("new Function()" in c for c in concerns)

    def test_common_patterns_apply_to_all_languages(self, dangerous_js):
        result = find_patterns.invoke({
            "code": dangerous_js,
            "file_path": "app.js",
        })
        concerns = [f["concern"] for f in result]
        assert any("secret" in c for c in concerns)

    def test_clean_code_no_findings(self):
        clean = "def add(a, b):\n    return a + b\n"
        result = find_patterns.invoke({"code": clean, "file_path": "math.py"})
        assert result == []

    def test_findings_have_line_numbers(self, dangerous_python):
        result = find_patterns.invoke({
            "code": dangerous_python,
            "file_path": "script.py",
        })
        for finding in result:
            assert "line_number" in finding
            assert isinstance(finding["line_number"], int)
            assert finding["line_number"] >= 1

    def test_findings_include_matched_line(self, dangerous_python):
        result = find_patterns.invoke({
            "code": dangerous_python,
            "file_path": "script.py",
        })
        for finding in result:
            assert "line" in finding
            assert len(finding["line"]) > 0

    def test_unknown_language_still_checks_common(self):
        code = 'token = "abc123"\n'
        result = find_patterns.invoke({"code": code, "file_path": "config.xyz"})
        assert len(result) >= 1
        assert any("token" in f["concern"] for f in result)


class TestCheckImports:
    def test_python_import(self):
        code = "import os\nimport sys\n"
        result = check_imports.invoke({"code": code, "language": "python"})
        modules = [r["module"] for r in result]
        assert "os" in modules
        assert "sys" in modules

    def test_python_from_import(self):
        code = "from pathlib import Path\nfrom os.path import join\n"
        result = check_imports.invoke({"code": code, "language": "python"})
        modules = [r["module"] for r in result]
        assert "pathlib" in modules
        assert "os.path" in modules

    def test_python_multi_import(self):
        code = "import os, sys, json\n"
        result = check_imports.invoke({"code": code, "language": "python"})
        modules = [r["module"] for r in result]
        assert "os" in modules
        assert "sys" in modules
        assert "json" in modules

    def test_python_line_numbers(self, python_code):
        result = check_imports.invoke({"code": python_code, "language": "python"})
        assert len(result) >= 2
        assert result[0]["line"] == 1
        assert result[1]["line"] == 2

    def test_javascript_import(self, js_code):
        result = check_imports.invoke({"code": js_code, "language": "javascript"})
        modules = [r["module"] for r in result]
        assert "express" in modules

    def test_javascript_require(self, js_code):
        result = check_imports.invoke({"code": js_code, "language": "javascript"})
        modules = [r["module"] for r in result]
        assert "axios" in modules

    def test_typescript_uses_same_as_javascript(self):
        code = "import { Router } from 'express';\n"
        result = check_imports.invoke({"code": code, "language": "typescript"})
        assert len(result) == 1
        assert result[0]["module"] == "express"

    def test_unsupported_language_returns_empty(self):
        result = check_imports.invoke({"code": "use std::io;", "language": "rust"})
        assert result == []

    def test_no_imports_returns_empty(self):
        result = check_imports.invoke({
            "code": "x = 1\nprint(x)\n",
            "language": "python",
        })
        assert result == []

"""Shared fixtures for the test suite."""

import pytest


SIMPLE_DIFF = """\
diff --git a/src/utils.py b/src/utils.py
--- a/src/utils.py
+++ b/src/utils.py
@@ -10,6 +10,8 @@ def helper():
     return True
 
 def process(data):
-    return data
+    if data is None:
+        raise ValueError("data cannot be None")
+    return data.strip()
"""

MULTI_FILE_DIFF = """\
diff --git a/src/utils.py b/src/utils.py
--- a/src/utils.py
+++ b/src/utils.py
@@ -1,4 +1,5 @@
 import os
+import json
 
 def helper():
     return True
diff --git a/src/auth.py b/src/auth.py
--- a/src/auth.py
+++ b/src/auth.py
@@ -5,3 +5,7 @@ def login(user, password):
     if check(user, password):
         return create_token(user)
     return None
+
+def logout(token):
+    revoke_token(token)
+    return True
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,2 +1,3 @@
 # My Project
 A cool project.
+Updated docs.
"""

NEW_FILE_DIFF = """\
diff --git a//dev/null b/src/new_module.py
--- /dev/null
+++ b/src/new_module.py
@@ -0,0 +1,5 @@
+\"\"\"A brand new module.\"\"\"
+
+
+def greet(name: str) -> str:
+    return f"Hello, {name}"
"""

DELETED_FILE_DIFF = """\
diff --git a/src/old_module.py b//dev/null
--- a/src/old_module.py
+++ /dev/null
@@ -1,3 +0,0 @@
-def deprecated():
-    pass
-
"""

RENAMED_FILE_DIFF = """\
diff --git a/src/old_name.py b/src/new_name.py
--- a/src/old_name.py
+++ b/src/new_name.py
@@ -1,3 +1,3 @@
 def example():
-    return "old"
+    return "new"
"""

DANGEROUS_PYTHON = """\
import os
import pickle

password = "supersecret123"
api_key = "sk-abc123"

def run_command(cmd):
    os.system(cmd)

def load_data(raw):
    return pickle.loads(raw)

def execute(code):
    eval(code)
"""

DANGEROUS_JS = """\
const secret = "my-secret-token";

function renderHTML(input) {
    document.getElementById("app").innerHTML = input;
    document.write(input);
}

function run(code) {
    eval(code);
    const fn = new Function(code);
}
"""

PYTHON_CODE = """\
import os
from pathlib import Path

class MyClass:
    def __init__(self, name):
        self.name = name

    def greet(self):
        return f"Hello, {self.name}"

    async def fetch_data(self):
        return await self._do_fetch()

def top_level_function(x, y):
    return x + y

async def async_top_level():
    pass
"""

GO_CODE = """\
package main

import "fmt"

func main() {
    fmt.Println("hello")
}

func (s *Server) HandleRequest(w http.ResponseWriter, r *http.Request) {
    // ...
}

func helper() int {
    return 42
}
"""

JS_CODE = """\
import express from 'express';
const axios = require('axios');

function handleRequest(req, res) {
    res.send("ok");
}

const processData = async (data) => {
    return data;
};

async function fetchUser(id) {
    return await db.find(id);
}
"""


@pytest.fixture
def simple_diff():
    return SIMPLE_DIFF


@pytest.fixture
def multi_file_diff():
    return MULTI_FILE_DIFF


@pytest.fixture
def new_file_diff():
    return NEW_FILE_DIFF


@pytest.fixture
def deleted_file_diff():
    return DELETED_FILE_DIFF


@pytest.fixture
def renamed_file_diff():
    return RENAMED_FILE_DIFF


@pytest.fixture
def dangerous_python():
    return DANGEROUS_PYTHON


@pytest.fixture
def dangerous_js():
    return DANGEROUS_JS


@pytest.fixture
def python_code():
    return PYTHON_CODE


@pytest.fixture
def go_code():
    return GO_CODE


@pytest.fixture
def js_code():
    return JS_CODE

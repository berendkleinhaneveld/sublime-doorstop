import json
from pathlib import Path
import subprocess

import sublime
import sublime_plugin

from .doorstop_plugin_api import Setting
from .doorstop_plugin_api import Settings


DOORSTOP_KEY = "doorstop"
settings = None


def trace():
    import pdb
    import sys

    pdb.Pdb(stdout=sys.__stdout__).set_trace()


def plugin_loaded():
    print("==LOADED==")
    global settings
    settings = Settings()


def plugin_unloaded():
    print("==UNLOADED==")
    global settings
    settings.remove_callbacks()

    for key in list(globals().keys()):
        if "doorstop" in key.lower():
            del globals()[key]


class DoorstopSetDoorstopPythonInterpreterCommand(sublime_plugin.ApplicationCommand):
    def run(self, interpreter):
        global settings
        settings.set(Setting().INTERPRETER, interpreter)
        # FIXME: this might not work... Only seems to update the settings for
        # the current view :'( There does not seem to be a way to update the setting
        # for the user...
        settings.save()

    def input(self, args):
        return DoorstopPythonInterpreterInputHandler()


class DoorstopPythonInterpreterInputHandler(sublime_plugin.TextInputHandler):
    def name(self):
        return "interpreter"

    def preview(self, text):
        return "Please select a valid python interpreter with doorstop available"

    def validate(self, text):
        import subprocess

        return subprocess.call([text, "-c", "import doorstop"]) == 0


class DoorstopDebugCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        global settings
        print(settings.get(Setting().INTERPRETER))


def _reference(view: sublime.View):
    # Check the selection
    keyword = None
    selection = view.sel()
    if len(selection) == 1:
        # Only take the first line of the selection, if the
        # selection is multiline
        selected_text = view.substr(selection[0]).split("\n")[0]
        if len(selected_text) > 0:
            keyword = selected_text

    # Create paths
    # FIXME: window can have multiple folders open...
    # Maybe try to find the best 'relative' folder for the current_file?
    project_dir = Path(view.window().folders()[0])
    current_file = view.window().extract_variables().get("file")
    if not current_file:
        return None

    relative = Path(current_file).relative_to(project_dir)
    result = {
        "path": str(relative),
        "type": "file",
    }
    if keyword:
        result["keyword"] = keyword
    return result


def run_doorstop_command(args):
    global settings
    interpreter = settings.get(Setting().INTERPRETER)
    script = Path(__file__).parent / "doorstop_cli" / "doorstop_cli.py"
    assert script.is_file()

    try:
        result = subprocess.check_output([interpreter, str(script)] + args)
    except subprocess.CalledProcessError as e:
        print("error: {}".format(e))
        return None
    return result


class DoorstopAddItemCommand(sublime_plugin.WindowCommand):
    def run(self, document):
        result = run_doorstop_command(
            ["--root", self.window.folders()[0], "add_item", "--prefix", document]
        )
        new_item = json.loads(result.decode("utf-8"))
        path = list(new_item.values())[0]
        self.window.open_file(path)

    def input(self, args):
        # FIXME: what if no folder is open?
        project_dir = self.window.folders()[0]
        return DoorstopFindDocumentInputHandler(project_dir)


class DoorstopCopyReferenceCommand(sublime_plugin.TextCommand):
    """
    Creates content for the paste buffer to be able to paste the
    reference in a doorstop item.

    Example output of self.view.window().extract_variables:
    {
        'file': '~/Library/AppSupport/Sublime/Packages/doorstop/doorstop.py',
        'file_base_name': 'doorstop',
        'packages': '~/Library/AppSupport/Sublime/Packages',
        'file_extension': 'py',
        'file_name': 'doorstop.py',
        'platform': 'OSX',
        'folder': '~/Library/AppSupport/Sublime/Packages/doorstop',
        'file_path': '~/Library/AppSupport/Sublime/Packages/doorstop'
    }
    """

    def run(self, edit):
        reference = _reference(self.view)

        # Create lines for the clipboard
        lines = [
            "- path: '{}'".format(reference["path"]),
            "  type: {}".format(reference["type"]),
        ]
        if "keyword" in reference:
            lines.append("  keyword: '{}'".format(reference["keyword"]))

        sublime.set_clipboard("\n".join(lines))

    def is_enabled(self, *args):
        return self.view.file_name is not None


class DoorstopCreateReferenceCommand(sublime_plugin.TextCommand):
    def run(self, edit, document, item):
        reference = _reference(self.view)
        run_doorstop_command(
            [
                "--root",
                self.view.window().folders()[0],
                "add_reference",
                "--item",
                item,
                json.dumps(reference),
            ]
        )

    def is_enabled(self, *args):
        return self.view.file_name is not None

    def input(self, args):
        # TODO: make this configurable in settings
        # if not empty, use setting, otherwise try first open folder
        project_dir = self.view.window().folders()[0]
        return DoorstopFindDocumentInputHandler(
            project_dir, DoorstopFindItemInputHandler
        )


class DoorstopFindDocumentInputHandler(sublime_plugin.ListInputHandler):
    def __init__(self, root, next_input_type=None):
        self.root = root
        self.next_input_type = next_input_type

    def name(self):
        return "document"

    def list_items(self):
        result = run_doorstop_command(["--root", self.root, "documents"])
        if not result:
            return []

        json_result = result.decode("utf-8")
        items = json.loads(json_result)
        return [item["prefix"] for item in items]

    def next_input(self, args):
        # print("--> args: {}".format(args))
        if self.next_input_type:
            return self.next_input_type(self.root, args["document"])
        return None


class DoorstopFindItemInputHandler(sublime_plugin.ListInputHandler):
    def __init__(self, root, document):
        self.root = root
        self.document = document

    def name(self):
        return "item"

    def list_items(self):
        result = run_doorstop_command(
            [
                "--root",
                self.root,
                "items",
                "--prefix",
                self.document,
            ]
        )
        if not result:
            return []

        json_result = result.decode("utf-8")
        items = json.loads(json_result)
        return ["{}: {}".format(item["uid"], item["text"]) for item in items]

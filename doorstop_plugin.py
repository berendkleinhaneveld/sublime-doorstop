import json
from pathlib import Path
import subprocess

import sublime
import sublime_plugin

from .doorstop_plugin_api import Setting
from .doorstop_plugin_api import Settings


DOORSTOP_KEY = "doorstop"
settings = None


def plugin_loaded():
    print("==LOADED==")
    global settings
    settings = Settings()


def plugin_unloaded():
    print("==UNLOADED==")
    global settings
    settings.remove_callbacks()

    doorstop_plugin_classes = [
        "DoorstopDebugCommand",
        "DoorstopCopyReferenceCommand",
        "DoorstopCreateReferenceCommand",
        "DoorstopFindDocumentInputHandler",
        "DoorstopFindItemInputHandler",
        "DoorstopSetDoorstopPythonInterpreterCommand",
        "DoorstopPythonInterpreterInputHandler",
    ]
    for class_name in doorstop_plugin_classes:
        try:
            del globals()[class_name]
        except Exception as e:
            print(e)


class DoorstopSetDoorstopPythonInterpreterCommand(sublime_plugin.ApplicationCommand):
    def run(self, interpreter):
        global settings
        settings.set(Setting().INTERPRETER, interpreter)
        # FIXME: this might not work... Only seems to update the settings for
        # the current view :'( There does not seem to be a way to update the setting
        # for the user...
        sublime.save_settings("Doorstop.sublime-settings")

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

        # import pdb
        # import sys

        # pdb.Pdb(stdout=sys.__stdout__).set_trace()


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

        print(reference)
        print("doc: {}".format(document))
        print("item type: {}".format(type(item)))
        print("item: {}".format(item))

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
        print("args: {}".format(args))
        # TODO: make this configurable in settings
        # if not empty, use setting, otherwise try first open folder
        project_dir = self.view.window().folders()[0]
        return DoorstopFindDocumentInputHandler(project_dir)


class DoorstopFindDocumentInputHandler(sublime_plugin.ListInputHandler):
    def __init__(self, root):
        self.root = root

    def name(self):
        return "document"

    def list_items(self):
        result = run_doorstop_command(["--root", self.root, "documents"])
        if not result:
            return []

        json_result = result.decode("utf-8")
        values = list(json.loads(json_result).keys())
        values.sort()
        return values

    def next_input(self, args):
        return DoorstopFindItemInputHandler(self.root, args["document"])


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
        values = list(json.loads(json_result).keys())
        values.sort()
        return values

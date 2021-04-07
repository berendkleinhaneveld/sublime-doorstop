import json
from pathlib import Path
import subprocess
import yaml

import sublime
import sublime_plugin

from .doorstop_plugin_api import Setting
from .doorstop_plugin_api import Settings


DOORSTOP_KEY = "doorstop"
settings = None


def trace():
    # NOTE to future me:
    # Start Sublime with:
    # ▶ /Applications/Sublime\ Text.app/Contents/MacOS/Sublime\ Text
    # then call this function to start debugger
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


class DoorstopReference:
    def __init__(self, region, path=None, file=None, keyword=None, point=None):
        self.region = region
        self.path = path
        self.file = file
        self.keyword = keyword
        self.point = point

    def is_valid(self):
        if not self.path:
            return False
        if self.keyword and not self.point:
            return False
        return True


class DoorstopReferencesListener(sublime_plugin.ViewEventListener):
    @classmethod
    def is_applicable(cls, settings):
        return "yaml" in settings.get("syntax").lower()

    def update_regions(self):
        # Find references key
        references_regions = self.view.find_all(r"^references:$")
        if len(references_regions) != 1:
            return

        references_region = references_regions[0]

        lines_that_start_with_word = self.view.find_all(r"^\w+")

        attribute_after_references = None
        for x in lines_that_start_with_word:
            if x.begin() > references_region.begin():
                attribute_after_references = x

        regions = []
        items = self.view.find_all(r"(?s)*(^- .*?)(?:(?!^[-|\w]).)*")
        for item in items:
            if item.begin() < references_region.begin():
                continue
            if item.begin() > attribute_after_references.begin():
                continue
            regions.append(sublime.Region(item.begin(), item.end()))

        self.references = [self.region_to_reference(region) for region in regions]

        self.view.add_regions(
            "doorstop:valid",
            [ref.region for ref in self.references if ref.is_valid()],
            "string",  # scope
            "bookmark",
            sublime.DRAW_NO_FILL,
        )
        self.view.add_regions(
            "doorstop:invalid",
            [ref.region for ref in self.references if not ref.is_valid()],
            "invalid",  # scope
            "bookmark",
            # sublime.DRAW_STIPPLED_UNDERLINE
            # | sublime.DRAW_NO_OUTLINE
            # |
            sublime.DRAW_NO_FILL,
        )

    def on_activated_async(self):
        """
        Called when a view gains input focus.
        """
        self.update_regions()

    def parse_reference_region(self, region):
        text = self.view.substr(region)
        try:
            content = yaml.load(text, Loader=yaml.SafeLoader)
            return content[0]
        except Exception:
            print("Could not parse region: {}".format(text))
        return None

    def region_to_reference(self, region):
        parsed = self.parse_reference_region(region)
        path = parsed.get("path")
        keyword = parsed.get("keyword")

        reference = DoorstopReference(region, path=path, keyword=keyword)

        if not path:
            return reference

        root = Path(self.view.window().folders()[0])
        file = root / path
        if not file.is_file():
            return reference

        reference.file = str(file)

        with open(str(file), mode="r", encoding="utf-8") as fh:
            point = 0
            line = fh.readline()
            while line:
                if keyword in line:
                    reference.point = point
                    break
                point += len(line)
                line = fh.readline()

        return reference

    def on_hover(self, point, hover_zone):
        if not hasattr(self, "references"):
            return

        hovered_references = [
            ref for ref in self.references if ref.region.contains(point)
        ]
        if len(hovered_references) > 0:
            hovered_reference = hovered_references[0]
            href = hovered_reference.path
            if hovered_reference.point:
                href += ":" + str(hovered_reference.point)

            if href:
                self.view.show_popup(
                    "<a href='{}'>{}</a>".format(href, hovered_reference.path),
                    sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                    point,
                    500,
                    500,
                    self.link_clicked,
                )

    def link_clicked(self, href):
        root = Path(self.view.window().folders()[0])
        try:
            idx = href.index(":")
        except ValueError:
            self.view.window().open_file(str(root / href))
            return

        file = href[:idx]
        point = href[idx + 1 :]

        file_view = self.view.window().open_file(str(root / file))
        file_view.show_at_center(int(point))
        file_view.sel().clear()
        file_view.sel().add(sublime.Region(int(point), int(point)))

    def on_deactivated(self):
        """
        Called when a view loses input focus.
        """
        self.view.erase_regions("doorstop:invalid")
        self.view.erase_regions("doorstop:valid")

    def on_modified_async(self):
        """
        Called after changes have been made to a view. Runs in a separate thread, and
        does not block the application.
        """
        self.update_regions()


class DoorstopSetDoorstopPythonInterpreterCommand(sublime_plugin.ApplicationCommand):
    def run(self, interpreter):
        global settings
        settings.set(Setting().INTERPRETER, interpreter)
        settings.save()

        # TODO: maybe use set_project_data(data) of WindowCommand instead?

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
        for setting in Setting():
            print("{}: {}".format(setting, settings.get(setting)))


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

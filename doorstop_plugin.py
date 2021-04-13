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
    global settings
    settings = Settings()


def plugin_unloaded():
    global settings
    settings.remove_callbacks()

    for key in list(globals().keys()):
        if "doorstop" in key.lower():
            del globals()[key]


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


def _is_doorstop_configured(view=None, window=None):
    global settings
    if settings.get(Setting().INTERPRETER) is None:
        return False
    if _doorstop_root(view=view, window=window) is None:
        return False
    return True


def _doorstop_root(view: sublime.View = None, window: sublime.Window = None) -> str:
    global settings
    root = settings.get(Setting().ROOT)
    if root:
        return root
    if view:
        if view.file_name():
            path = Path(view.file_name())
            # best_match = folder with .git as subfolder
            # and a folder that is in close proximity to current opened file?
            folders = view.window().folders()
            rel_paths = [path.relative_to(Path(folder)) for folder in folders]
            shortest_rel_path = None
            result = None
            for rel_path, path in zip(rel_paths, folders):
                if not shortest_rel_path or len(str(rel_path)) < len(
                    str(shortest_rel_path)
                ):
                    shortest_rel_path = rel_path
                    result = path

            return result
    if window:
        if window.folders():
            return window.folders()[0]


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
    project_dir = _doorstop_root(view=view)
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


def _run_doorstop_command(args):
    global settings
    interpreter = settings.get(Setting().INTERPRETER)
    # TODO: maybe I could use the 'find_resources' method here from sublime
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
        root = _doorstop_root(window=self.window)
        result = _run_doorstop_command(
            ["--root", root, "add_item", "--prefix", document]
        )
        new_item = json.loads(result.decode("utf-8"))
        path = list(new_item.values())[0]
        self.window.open_file(path)

    def input(self, args):
        project_dir = _doorstop_root(window=self.window)
        return DoorstopFindDocumentInputHandler(project_dir)

    def is_enabled(self, *args):
        return _is_doorstop_configured(
            view=self.window.active_view(), window=self.window
        )


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
        return self.view.file_name() is not None


class DoorstopCreateReferenceCommand(sublime_plugin.TextCommand):
    def run(self, edit, document, item):

        reference = _reference(self.view)
        root = _doorstop_root(view=self.view)
        _run_doorstop_command(
            [
                "--root",
                root,
                "add_reference",
                "--item",
                item,
                json.dumps(reference),
            ]
        )

    def is_enabled(self, *args):
        return self.view.file_name() is not None

    def input(self, args):
        # TODO: make this configurable in settings
        # if not empty, use setting, otherwise try first open folder
        root = _doorstop_root(view=self.view)
        return DoorstopFindDocumentInputHandler(root, DoorstopFindItemInputHandler)


class DoorstopFindDocumentInputHandler(sublime_plugin.ListInputHandler):
    def __init__(self, root, next_input_type=None):
        self.root = root
        self.next_input_type = next_input_type

    def name(self):
        return "document"

    def list_items(self):
        result = _run_doorstop_command(["--root", self.root, "documents"])
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
        result = _run_doorstop_command(
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
        return [
            ("{}: {}".format(item["uid"], item["text"]), item["uid"]) for item in items
        ]


class DoorstopReference:
    def __init__(self, region, path=None, file=None, keyword=None, point=None):
        self.region = region
        self.path = path
        self.file = file
        self.keyword = keyword
        self.point = point
        self.row = None
        self.column = None

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

        self.references = [
            _region_to_reference(self.view, region) for region in regions
        ]

        self.view.add_regions(
            "doorstop:valid",
            [ref.region for ref in self.references if ref.is_valid()],
            "string",
            "bookmark",
            sublime.DRAW_NO_FILL,
        )
        self.view.add_regions(
            "doorstop:invalid",
            [ref.region for ref in self.references if not ref.is_valid()],
            "invalid",
            "bookmark",
            sublime.DRAW_NO_FILL,
        )

    def on_load_async(self):
        """
        Called when the file is finished loading. Runs in a separate thread,
        and does not block the application.
        """
        self.update_regions()

    def on_activated_async(self):
        """
        Called when a view gains input focus.
        """
        self.update_regions()

    def on_hover(self, point, hover_zone):
        if not hasattr(self, "references"):
            return

        hovered_references = [
            ref for ref in self.references if ref.region.contains(point)
        ]
        if len(hovered_references) > 0:
            hovered_reference = hovered_references[0]
            href = hovered_reference.path
            if hovered_reference.row:
                href += (
                    ":"
                    + str(hovered_reference.row)
                    + ":"
                    + str(hovered_reference.column)
                )

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
        root = Path(_doorstop_root(view=self.view))
        try:
            href.index(":")
        except ValueError:
            self.view.window().open_file(str(root / href))
            return

        self.view.window().open_file(
            str(root / href), sublime.ENCODED_POSITION | sublime.TRANSIENT
        )

    def on_close(self):
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


class DoorstopGotoReferenceCommand(sublime_plugin.TextCommand):
    def goto_reference(self, idx):
        if idx < 0:
            return

        root = Path(_doorstop_root(view=self.view))
        reference = self.references[idx]
        if not reference.row:
            self.view.window().open_file(str(root / reference.file), sublime.TRANSIENT)
        else:
            link = "{}:{}:{}".format(
                str(root / reference.file), reference.row, reference.column
            )
            self.view.window().open_file(
                link, sublime.ENCODED_POSITION | sublime.TRANSIENT
            )

    def run(self, edit):
        regions = self.view.get_regions("doorstop:valid")
        self.references = [
            _region_to_reference(self.view, region) for region in regions
        ]
        if len(self.references) == 1:
            self.goto_reference(0)
        else:
            items = [
                ref.path if not ref.keyword else "{}: {}".format(ref.path, ref.keyword)
                for idx, ref in enumerate(self.references)
            ]
            self.view.window().show_quick_panel(
                items,
                self.goto_reference,
            )

    def is_enabled(self, *args):
        return len(self.view.get_regions("doorstop:valid")) >= 1


class DoorstopGotoParentCommand(sublime_plugin.TextCommand):
    def goto_parent(self, idx):
        if idx < 0:
            return

        parent = self.parents[idx]
        self.view.window().open_file(parent["path"], sublime.TRANSIENT)

    def run(self, edit):
        file_name = Path(self.view.file_name())
        root = _doorstop_root(view=self.view)
        result = _run_doorstop_command(
            ["--root", root, "parents", "--item", file_name.stem]
        )
        self.parents = json.loads(result.decode("utf-8"))
        items = [
            "{}: {}".format(parent["uid"], parent["text"])
            for idx, parent in enumerate(self.parents)
        ]
        self.view.window().show_quick_panel(
            items,
            self.goto_parent,
        )
        # TODO: maybe show that no parent can be found?

    def is_enabled(self, *args):
        if not self.view.file_name():
            return False
        file_name = Path(self.view.file_name())
        if file_name.suffix != ".yml":
            return False
        if not (file_name.parent / ".doorstop.yml").exists():
            return False
        if file_name.name == ".doorstop.yml":
            return False
        return True


class DoorstopChooseReferenceInputHandler(sublime_plugin.ListInputHandler):
    def __init__(self, references):
        self.references = references

    def name(self):
        return "ref_idx"

    def list_items(self):
        return [
            (ref.path, idx)
            if not ref.keyword
            else ("{}: {}".format(ref.path, ref.keyword), idx)
            for idx, ref in enumerate(self.references)
        ]


def _parse_reference_region(view, region):
    text = view.substr(region)
    try:
        content = yaml.load(text, Loader=yaml.SafeLoader)
        return content[0]
    except Exception:
        print("Could not parse region: {}".format(text))
    return None


def _region_to_reference(view, region):
    parsed = _parse_reference_region(view, region)
    path = parsed.get("path")
    keyword = parsed.get("keyword")

    reference = DoorstopReference(region, path=path, keyword=keyword)

    if not path:
        return reference

    root = Path(_doorstop_root(view=view))
    file = root / path
    if not file.is_file():
        return reference

    reference.file = str(file)

    with open(str(file), mode="r", encoding="utf-8") as fh:
        point = 0
        row = 1
        line = fh.readline()
        while line:
            if keyword in line:
                reference.point = point
                reference.row = row
                reference.column = line.index(keyword) + 1
                break
            point += len(line)
            row += 1
            line = fh.readline()

    return reference

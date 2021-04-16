import json
from pathlib import Path

import sublime
import sublime_plugin

from .doorstop_plugin_api import Setting
from .doorstop_plugin_api import Settings

from . import doorstop_util


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
    doorstop_util.settings = settings


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
    """
    Debug command that prints settings
    """

    def run(self, edit):
        global settings
        for setting in Setting():
            print("{}: {}".format(setting, settings.get(setting)))


class DoorstopAddItemCommand(sublime_plugin.WindowCommand):
    """
    Adds an item to the specified doorstop document
    """

    def _add_item(self, text):
        args = ["--prefix", self.document]
        if len(text) > 1:
            args += ["--text", text]
        new_item = doorstop_util.doorstop(self, "add_item", *args)
        path = list(new_item.values())[0]
        self.window.open_file(path)

    def run(self, document):
        self.document = document
        self.window.show_input_panel(
            "Specify (optional) text for new {} item".format(document),
            "",
            self._add_item,
            None,
            None,
        )

    def input(self, args):
        project_dir = doorstop_util.doorstop_root(window=self.window)
        return DoorstopFindDocumentInputHandler(project_dir)

    def is_enabled(self, *args):
        return doorstop_util.is_doorstop_configured(
            view=self.window.active_view(), window=self.window
        )


class DoorstopCopyReferenceCommand(sublime_plugin.TextCommand):
    """
    Creates content for the paste buffer to be able to paste the
    reference in a doorstop item.
    """

    def run(self, edit):
        reference = doorstop_util.reference(self.view)

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
    """
    Add a new reference to an existing doorstop item.
    """

    def run(self, edit, document, item):
        reference = doorstop_util.reference(self.view)
        doorstop_util.doorstop(
            self, "add_reference", "--item", item, json.dumps(reference)
        )

    def is_enabled(self, *args):
        return self.view.file_name() is not None

    def input(self, args):
        root = doorstop_util.doorstop_root(view=self.view)
        return DoorstopFindDocumentInputHandler(root, DoorstopFindItemInputHandler)


class DoorstopAddLinkCommand(sublime_plugin.TextCommand):
    """
    Links an item to the current doorstop item.
    """

    def run(self, edit, document, item):
        file_name = Path(self.view.file_name())
        result = doorstop_util.doorstop(self, "link", file_name.stem, item)
        self.view.window().open_file(result["path"])

    def input(self, args):
        root = doorstop_util.doorstop_root(view=self.view)
        return DoorstopFindDocumentInputHandler(root, DoorstopFindItemInputHandler)

    def is_enabled(self, *args):
        if not self.view.file_name():
            return False
        file_name = Path(self.view.file_name())
        if file_name.suffix != ".yml":
            return False
        if not (file_name.parent / ".doorstop.yml").exists():
            return False
        if file_name.name.startswith("."):
            return False
        if file_name.name == ".doorstop.yml":
            return False
        return True


class DoorstopFindDocumentInputHandler(sublime_plugin.ListInputHandler):
    def __init__(self, root, next_input_type=None):
        self.root = root
        self.next_input_type = next_input_type

    def name(self):
        return "document"

    def list_items(self):
        items = doorstop_util.doorstop(self.root, "documents")
        if not items:
            return []

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
        items = doorstop_util.doorstop(
            self.root,
            "items",
            "--prefix",
            self.document,
        )
        if not items:
            return []

        return [
            ("{}: {}".format(item["uid"], item["text"]), item["uid"]) for item in items
        ]


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
            doorstop_util.region_to_reference(self.view, region) for region in regions
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
        root = Path(doorstop_util.doorstop_root(view=self.view))
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

        root = Path(doorstop_util.doorstop_root(view=self.view))
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
            doorstop_util.region_to_reference(self.view, region) for region in regions
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
        self.parents = doorstop_util.doorstop(self, "parents", "--item", file_name.stem)
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
        if file_name.name.startswith("."):
            return False
        if file_name.name == ".doorstop.yml":
            return False
        return True


class DoorstopGotoChildCommand(sublime_plugin.TextCommand):
    def goto_child(self, idx):
        if idx < 0:
            return

        child = self.children[idx]
        self.view.window().open_file(child["path"], sublime.TRANSIENT)

    def run(self, edit):
        file_name = Path(self.view.file_name())
        self.children = doorstop_util.doorstop(
            self, "children", "--item", file_name.stem
        )
        items = [
            "{}: {}".format(child["uid"], child["text"])
            for idx, child in enumerate(self.children)
        ]
        self.view.window().show_quick_panel(
            items,
            self.goto_child,
        )
        # TODO: maybe show that no child can be found?

    def is_enabled(self, *args):
        if not self.view.file_name():
            return False
        file_name = Path(self.view.file_name())
        if file_name.suffix != ".yml":
            return False
        if not (file_name.parent / ".doorstop.yml").exists():
            return False
        if file_name.name.startswith("."):
            return False
        if file_name.name == ".doorstop.yml":
            return False
        return True


class DoorstopGotoLinkCommand(sublime_plugin.TextCommand):
    def goto_link(self, idx):
        if idx < 0:
            return

        link = self.links[idx]
        self.view.window().open_file(link["path"], sublime.TRANSIENT)

    def run(self, edit):
        file_name = Path(self.view.file_name())
        self.links = doorstop_util.doorstop(self, "linked", "--item", file_name.stem)
        items = [
            "{}: {}".format(link["uid"], link["text"])
            for idx, link in enumerate(self.links)
        ]
        self.view.window().show_quick_panel(
            items,
            self.goto_link,
        )
        # TODO: maybe show that no child can be found?

    def is_enabled(self, *args):
        if not self.view.file_name():
            return False
        file_name = Path(self.view.file_name())
        if file_name.suffix != ".yml":
            return False
        if not (file_name.parent / ".doorstop.yml").exists():
            return False
        if file_name.name.startswith("."):
            return False
        if file_name.name == ".doorstop.yml":
            return False
        return True


class DoorstopGotoAnyLinkCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        file_name = Path(self.view.file_name())
        self.parents = doorstop_util.doorstop(self, "parents", "--item", file_name.stem)
        self.children = doorstop_util.doorstop(
            self, "children", "--item", file_name.stem
        )
        self.links = doorstop_util.doorstop(self, "linked", "--item", file_name.stem)

        all_items = []
        for name, items in zip(
            ["Parent", "Child", "Other"], [self.parents, self.children, self.links]
        ):
            all_items.extend(
                [
                    "{}: {}: {}".format(name, link["uid"], link["text"])
                    for idx, link in enumerate(items)
                ]
            )
        self.view.window().show_quick_panel(
            all_items,
            self.goto_item,
        )
        # TODO: maybe show that no child can be found?

    def is_enabled(self, *args):
        if not self.view.file_name():
            return False
        file_name = Path(self.view.file_name())
        if file_name.suffix != ".yml":
            return False
        if not (file_name.parent / ".doorstop.yml").exists():
            return False
        if file_name.name.startswith("."):
            return False
        if file_name.name == ".doorstop.yml":
            return False
        return True

    def goto_item(self, idx):
        if idx < 0:
            return

        items = self.parents + self.children + self.links
        item = items[idx]
        self.view.window().open_file(item["path"], sublime.TRANSIENT)


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


class DoorstopLinksListener(sublime_plugin.ViewEventListener):
    @classmethod
    def is_applicable(cls, settings):
        return "yaml" in settings.get("syntax").lower()

    def update_regions(self):
        # Make sure we don't update those regions too often
        if hasattr(self, "dirty") and not self.dirty:
            return

        links_regions = self.view.find_all(r"^links")
        if len(links_regions) != 1:
            return

        if not self.view.file_name():
            return

        is_normative = True
        normative_region = self.view.find_all(r"^normative:.*$")
        if len(normative_region) == 1 and "true" not in self.view.substr(
            normative_region[0]
        ):
            is_normative = False

        file_name = Path(self.view.file_name())
        item = file_name.stem

        self.parents = doorstop_util.doorstop(self, "parents", "--item", item)
        self.children = doorstop_util.doorstop(self, "children", "--item", item)
        self.other = doorstop_util.doorstop(self, "linked", "--item", item)

        links_region = links_regions[0]
        self.view.add_regions(
            "doorstop:links",
            [links_region],
            "string"
            if self.parents or self.children or self.other or not is_normative
            else "invalid",
            "bookmark",
            sublime.DRAW_NO_FILL
            | sublime.DRAW_NO_OUTLINE
            | sublime.DRAW_STIPPLED_UNDERLINE,
        )

        self.dirty = False

    def on_load_async(self):
        """
        Called when the file is finished loading. Runs in a separate thread,
        and does not block the application.
        """
        self.dirty = True
        self.update_regions()

    def on_modified_async(self):
        """
        Called after changes have been made to a view. Runs in a separate thread,
        and does not block the application.
        """
        self.dirty = True

    def on_activated_async(self):
        """
        Called when a view gains input focus.
        """
        self.update_regions()

    def on_post_save_async(self):
        """
        Called after changes have been made to a view. Runs in a separate thread, and
        does not block the application.
        """
        self.update_regions()

    def on_close(self):
        """
        Called when a view loses input focus.
        """
        self.view.erase_regions("doorstop:links")

    def on_hover(self, point, hover_zone):
        regions = self.view.get_regions("doorstop:links")
        if not regions:
            return

        if not regions[0].contains(point):
            return

        if (
            not hasattr(self, "parents")
            or not hasattr(self, "children")
            or not hasattr(self, "other")
        ):
            return

        def item_to_link(item):
            return "<a href='{}'>{}</a>".format(
                item["path"],
                "{}: {}".format(item["uid"], item["text"]),
            )

        sections = []
        if self.parents:
            sections.append("Parent(s):")
            for parent in self.parents:
                sections.append(item_to_link(parent))
        if self.children:
            sections.append("Child(ren):")
            for child in self.children:
                sections.append(item_to_link(child))
        if self.other:
            sections.append("Other:")
            for item in self.other:
                sections.append(item_to_link(item))

        if not sections:
            self.view.show_popup(
                "No links found",
                sublime.HIDE_ON_MOUSE_MOVE,
                point,
                1000,
                2000,
                None,
            )
        else:
            self.view.show_popup(
                "<br>".join(sections),
                sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                point,
                1000,
                2000,
                self.link_clicked,
            )

    def link_clicked(self, href):
        self.view.window().open_file(href, sublime.TRANSIENT)

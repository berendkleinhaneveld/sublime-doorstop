import json
from pathlib import Path
import re

import sublime
import sublime_plugin

from .doorstop_util import Setting
from .doorstop_util import Settings

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
    """
    Hook that is called by Sublime when plugin is loaded.
    """
    global settings
    settings = Settings()
    doorstop_util.settings = settings


def plugin_unloaded():
    """
    Hook that is called by Sublime when plugin is unloaded.
    """
    global settings
    settings.remove_callbacks()

    for key in list(globals().keys()):
        if "doorstop" in key.lower():
            del globals()[key]


class DoorstopSetDoorstopPythonInterpreterCommand(sublime_plugin.ApplicationCommand):
    """
    Command to set the python interpreter in settings that will be
    used to run the script `doorstop_cli/doorstop_cli.py`
    """

    def run(self, interpreter):
        global settings
        settings.set(Setting().INTERPRETER, interpreter)
        settings.save()

        # TODO: maybe use set_project_data(data) of WindowCommand instead?

    def input(self, args):
        return DoorstopPythonInterpreterInputHandler()


class DoorstopPythonInterpreterInputHandler(sublime_plugin.TextInputHandler):
    """
    TextInputHandler that will ask the user to specify a valid python interpreter.
    It only accepts input when it can run the python interpreter to import the
    doorstop package.
    """

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


class DoorstopGotoAnyItemCommand(sublime_plugin.WindowCommand):
    """
    GoTo any doorstop item.
    """

    def run(self, document, item):
        self.window.open_file(item)

    def input(self, args):
        project_dir = doorstop_util.doorstop_root(window=self.window)
        return DoorstopFindDocumentInputHandler(
            project_dir, DoorstopFindItemPathInputHandler
        )

    def is_enabled(self, *args):
        return doorstop_util.is_doorstop_configured(
            view=self.window.active_view(), window=self.window
        )


class DoorstopCreateReferenceCommand(sublime_plugin.TextCommand):
    """
    Add a new reference to an existing doorstop item.
    """

    def run(self, edit, document, item):
        reference = doorstop_util.reference(self.view)
        result = doorstop_util.doorstop(
            self, "add_reference", "--item", item, json.dumps(reference)
        )
        self.view.window().open_file(result["path"])

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
        return doorstop_util.is_doorstop_item_file(self.view.file_name())


class DoorstopFindDocumentInputHandler(sublime_plugin.ListInputHandler):
    """
    List input handler that will show a list of doorstop documents
    for the user to choose from.
    """

    def __init__(self, root, next_input_type=None):
        """
        root: str
            Root path of doorstop
        next_input_type: InputHandler
            Handler to show when user has picked document
        """
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
    """
    List input handler that will show a list of doorstop items
    for the given document name for the user to choose from.
    """

    def __init__(self, root, document, result_as_path=False):
        """
        root: str
            Root path of doorstop
        document: str
            Document prefix/name
        """
        self.root = root
        self.document = document
        self.result_as_path = result_as_path

    def name(self):
        return "item"

    def list_items(self):
        items = doorstop_util.doorstop(self.root, "items", "--prefix", self.document)
        if not items:
            return []

        return [
            (
                "{}: {}".format(item["uid"], item["text"]),
                item["path"] if self.result_as_path else item["uid"],
            )
            for item in items
        ]


class DoorstopFindItemPathInputHandler(DoorstopFindItemInputHandler):
    def __init__(self, root, document):
        super().__init__(root, document, result_as_path=True)


class DoorstopReferencedLocationsListener(sublime_plugin.ViewEventListener):
    @classmethod
    def is_applicable(cls, settings):
        # TODO: check for existance of doorstop stuff in project root?
        # return "yaml" in settings.get("syntax").lower()
        return True

    def on_load_async(self):
        """
        Called when the file is finished loading. Runs in a separate thread,
        and does not block the application.
        """
        self.update_referenced_locations()

    def on_activated_async(self):
        """
        Called when a view gains input focus.
        """
        self.update_referenced_locations()

    def on_close(self):
        """
        Called when a view loses input focus.
        """
        self.erase_regions()

    def erase_regions(self):
        self.view.erase_regions("doorstop:referenced")

    # def on_modified_async(self):
    #     """
    #     Called after changes have been made to a view. Runs in a separate thread, and
    #     does not block the application.
    #     """
    #     self.update_referenced_locations()

    def update_referenced_locations(self):
        path = self.view.file_name()
        root = doorstop_util.doorstop_root(view=self.view)
        if not path or not root:
            return

        file = Path(path).relative_to(Path(root))

        items = doorstop_util.doorstop(
            self,
            "find_references",
            str(file),
        )
        for item in items:
            keyword = item.get("keyword")

            if not keyword:
                continue

            # region = self.view.find(re.escape(keyword), 0)
            region = self.view.find(keyword, 0)
            if region.begin() == -1:
                print("Could not find keyword: '{}'".format(keyword))
                continue
            item["region"] = region

        self.referenced = items
        self.view.add_regions(
            "doorstop:referenced",
            [item["region"] for item in self.referenced if "region" in item],
            "string",
            "bookmark",
            sublime.DRAW_NO_FILL,
        )

    def on_hover(self, point, hover_zone):
        """
        Called when the user's mouse hovers over a view for a short period.
        """
        if not hasattr(self, "referenced"):
            return

        hovered_referenced = [
            ref for ref in self.referenced if ref["region"].contains(point)
        ]
        if not hovered_referenced:
            return

        hovered_reference = hovered_referenced[0]
        self.view.show_popup(
            "<a href='{}'>{}</a>".format(
                hovered_reference["path"],
                "{}: {}".format(hovered_reference["uid"], hovered_reference["text"]),
            ),
            sublime.HIDE_ON_MOUSE_MOVE_AWAY,
            point,
            500,
            500,
            self.referenced_href_clicked,
        )

    def referenced_href_clicked(self, href):
        self.view.window().open_file(href)


class DoorstopReferencesListener(sublime_plugin.ViewEventListener):
    """
    ViewEventListener that will try to find and highlight references
    in yaml/doorstop files.
    """

    @classmethod
    def is_applicable(cls, settings):
        return "yaml" in settings.get("syntax").lower()

    def on_load_async(self):
        """
        Called when the file is finished loading. Runs in a separate thread,
        and does not block the application.
        """
        self.update_references_regions()

    def on_activated_async(self):
        """
        Called when a view gains input focus.
        """
        self.update_references_regions()

    def on_hover(self, point, hover_zone):
        """
        Called when the user's mouse hovers over a view for a short period.
        """
        if not hasattr(self, "references"):
            return

        hovered_references = [
            ref for ref in self.references if ref.region.contains(point)
        ]
        if len(hovered_references) > 0:
            hovered_reference = hovered_references[0]
            href = hovered_reference.file
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
                    self.reference_href_clicked,
                )

    def on_close(self):
        """
        Called when a view loses input focus.
        """
        self.erase_regions()

    def on_modified_async(self):
        """
        Called after changes have been made to a view. Runs in a separate thread, and
        does not block the application.
        """
        self.update_references_regions()

    def erase_regions(self):
        self.view.erase_regions("doorstop:references:invalid")
        self.view.erase_regions("doorstop:references:valid")

    def update_references_regions(self):
        # TODO: don't run this too often...
        regions = regions_for_items_in_yaml_list(self.view, "references")
        if regions is None:
            self.erase_regions()
            return

        self.references = [
            doorstop_util.region_to_reference(self.view, region) for region in regions
        ]

        self.view.add_regions(
            "doorstop:references:valid",
            [ref.region for ref in self.references if ref.is_valid()],
            "string",
            "bookmark",
            sublime.DRAW_NO_FILL,
        )
        self.view.add_regions(
            "doorstop:references:invalid",
            [ref.region for ref in self.references if not ref.is_valid()],
            "invalid",
            "bookmark",
            sublime.DRAW_NO_FILL,
        )

    def reference_href_clicked(self, href):
        root = Path(doorstop_util.doorstop_root(view=self.view))
        try:
            href.index(":")
        except ValueError:
            self.view.window().open_file(str(root / href))
            return

        self.view.window().open_file(
            str(root / href), sublime.ENCODED_POSITION | sublime.TRANSIENT
        )


class DoorstopGotoReferenceCommand(sublime_plugin.TextCommand):
    """
    Text command that shows a list of all the references. Picking
    a reference will open the file. When a keyword is specified,
    it will try to look that up.
    """

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
        regions = self.view.get_regions("doorstop:references:valid")
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
        return len(self.view.get_regions("doorstop:references:valid")) >= 1


class DoorstopGotoAnyLinkCommand(sublime_plugin.TextCommand):
    """
    Text command that shows a list of all the links from and to this doorstop item
    """

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
        return doorstop_util.is_doorstop_item_file(self.view.file_name())

    def goto_item(self, idx):
        if idx < 0:
            return

        items = self.parents + self.children + self.links
        item = items[idx]
        self.view.window().open_file(item["path"], sublime.TRANSIENT)


class DoorstopLinksListener(sublime_plugin.ViewEventListener):
    """
    ViewEventListener that will try to find link from and to
    the currently opened doorstop item.
    """

    @classmethod
    def is_applicable(cls, settings):
        return "yaml" in settings.get("syntax").lower()

    def on_load_async(self):
        """
        Called when the file is finished loading. Runs in a separate thread,
        and does not block the application.
        """
        self.dirty = True
        self.update_links_regions()

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
        self.update_links_regions()

    def on_post_save_async(self):
        """
        Called after changes have been made to a view. Runs in a separate thread, and
        does not block the application.
        """
        self.update_links_regions()

    def on_close(self):
        """
        Called when a view is closed (note, there may still be other views into
        the same buffer).
        """
        self.view.erase_regions("doorstop:links")

    def on_hover(self, point, hover_zone):
        """
        Called when the user's mouse hovers over a view for a short period.
        """
        regions = self.view.get_regions("doorstop:links:direct")
        hovered_regions = [region for region in regions if region.contains(point)]
        if hovered_regions:
            # TODO: figure this out in update_links_region
            # TODO: lint the direct links
            item_uid = self.view.substr(hovered_regions[0])
            item = doorstop_util.doorstop(self, "item", item_uid)
            if item:
                self.view.show_popup(
                    "<a href='{}'>{}: {}</a>".format(
                        item["path"], item["uid"], item["text"]
                    ),
                    sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                    point,
                    1000,
                    2000,
                    self.link_href_clicked,
                )
            return

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
                self.link_href_clicked,
            )

    def update_links_regions(self):
        # Make sure we don't update those regions too often
        if hasattr(self, "dirty") and not self.dirty:
            return

        links_regions = self.view.find_all(r"^links")
        if len(links_regions) != 1:
            self.view.erase_regions("doorstop:links")
            return

        link_regions = regions_for_items_in_yaml_list(self.view, "links")
        if link_regions is None:
            self.view.erase_regions("doorstop:links:direct")
            link_regions = []

        uid_link_regions = []
        for region in link_regions:
            content = self.view.substr(region)
            try:
                index = content.rindex(": ")
                uid_link_regions.append(
                    sublime.Region(region.begin() + 2, region.begin() + index)
                )
            except ValueError:
                uid_link_regions.append(
                    sublime.Region(region.begin() + 2, region.end())
                )

        self.view.add_regions(
            "doorstop:links:direct",
            uid_link_regions,
            "string",  # keyword seems to be orange
            "",
            sublime.DRAW_NO_FILL
            | sublime.DRAW_NO_OUTLINE
            | sublime.DRAW_SOLID_UNDERLINE,
        )

        file_name = Path(self.view.file_name())
        item = file_name.stem

        self.parents = doorstop_util.doorstop(self, "parents", "--item", item)
        self.children = doorstop_util.doorstop(self, "children", "--item", item)
        self.other = doorstop_util.doorstop(self, "linked", "--item", item)

        is_normative = True
        normative_region = self.view.find_all(r"^normative:.*$")
        if len(normative_region) == 1 and "true" not in self.view.substr(
            normative_region[0]
        ):
            is_normative = False

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
            | sublime.DRAW_SOLID_UNDERLINE,
        )

        self.dirty = False

    def link_href_clicked(self, href):
        self.view.window().open_file(href, sublime.TRANSIENT)


def regions_for_items_in_yaml_list(view, keyword):
    keyword_regions = view.find_all("^{}:$".format(keyword))
    if len(keyword_regions) != 1:
        return None

    keyword_region = keyword_regions[0]

    lines_that_start_with_word = view.find_all(r"^\w+")

    attribute_after_references = None
    for x in lines_that_start_with_word:
        if x.begin() > keyword_region.begin():
            attribute_after_references = x
            break

    regions = []
    items = view.find_all(r"(?s)*(^- .*?)(?:(?!^[-|\w]).)*")
    for item in items:
        if item.begin() < keyword_region.begin():
            continue
        if item.begin() > attribute_after_references.begin():
            continue
        regions.append(sublime.Region(item.begin(), item.end()))

    return regions

from pathlib import Path

import sublime
import sublime_plugin

from . import doorstop_util


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

        file_name = Path(self.view.file_name())
        item = file_name.stem

        self.parents = doorstop_util._doorstop(self, "parents", "--item", item)
        self.children = doorstop_util._doorstop(self, "children", "--item", item)
        self.other = doorstop_util._doorstop(self, "linked", "--item", item)

        links_region = links_regions[0]
        self.view.add_regions(
            "doorstop:links",
            [links_region],
            "string" if self.parents or self.children or self.other else "invalid",
            "bookmark",
            sublime.DRAW_NO_FILL,
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
            sections.append("Parent(s):<br>")
            for parent in self.parents:
                sections.append(item_to_link(parent))
        if self.children:
            sections.append("Child(ren)<br>")
            for child in self.children:
                sections.append(item_to_link(child))
        if self.other:
            sections.append("Other<br>")
            for item in self.other:
                sections.append(item_to_link(item))

        if not sections:
            self.view.show_popup(
                "No links found",
                sublime.HIDE_ON_MOUSE_MOVE,
                point,
                500,
                500,
                None,
            )
        else:
            self.view.show_popup(
                # "<a href='{}'>{}</a>".format(href, hovered_reference.path),
                "".join(sections),
                sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                point,
                500,
                500,
                self.link_clicked,
            )

    def link_clicked(self, href):
        self.view.window().open_file(href, sublime.TRANSIENT)

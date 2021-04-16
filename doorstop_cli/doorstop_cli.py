#!/usr/bin/env python
import json
import logging
import argparse

import doorstop


doorstop.settings.ADDREMOVE_FILES = False


logger = logging.getLogger("DoorstopPlugin")


def item_to_dict(item):
    return {
        "uid": item.uid.value,
        "path": item.path,
        "text": item.header if item.header else item.text.split("\n")[0],
    }


def document(args):
    tree = doorstop.build(root=args.root)
    prefixes = [{"prefix": doc.prefix, "path": doc.path} for doc in tree.documents]
    print(json.dumps(prefixes))


def items(args):
    tree = doorstop.build(root=args.root)
    document = tree.find_document(args.prefix)
    items = [item_to_dict(item) for item in document.items]
    print(json.dumps(items))


def parents(args):
    tree = doorstop.build(root=args.root)
    item = tree.find_item(args.item)
    parents = [item_to_dict(item) for item in item.parent_items]
    print(json.dumps(parents))


def children(args):
    tree = doorstop.build(root=args.root)
    item = tree.find_item(args.item)
    children = [item_to_dict(item) for item in item.child_items]
    print(json.dumps(children))


def linked(args):
    tree = doorstop.build(root=args.root)
    target = tree.find_item(args.item)

    # Find all items that link to the given item
    linked = []
    for document in tree.documents:
        for item in document.items:
            if target.uid in item.links and item.uid not in target.child_links:
                linked.append(item)

    result = [item_to_dict(item) for item in linked]
    print(json.dumps(result))


def link(args):
    tree = doorstop.build(root=args.root)
    child = tree.find_item(args.child)
    parent = tree.find_item(args.parent)
    doc = parent.document
    parents = []
    while doc:
        parents.append(doc)
        try:
            doc = tree.find_document(doc.parent)
        except Exception:
            break

    # child is actually a parent of the
    # parent, so reverse the order
    if child.document in parents:
        parent.link(child)
        print(item_to_dict(parent))
    else:
        child.link(parent)
        print(item_to_dict(child))


def add_reference_to_item(args):
    tree = doorstop.build(root=args.root)
    reference = json.loads(args.reference)
    item = tree.find_item(args.item)
    if not item.references:
        item.references = []

    if reference not in item.references:
        item.references.append(reference)
        item.save()


def add_item(args):
    tree = doorstop.build(root=args.root)
    document = tree.find_document(args.prefix)
    item = document.add_item()
    if hasattr(args, "text"):
        item.text = args.text
    print(json.dumps({str(item.uid): item.path}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get information from doorstop")
    parser.add_argument(
        "--root",
        action="store",
        default=".",
        type=str,
        help="root from which to load doorstop",
    )

    commands = parser.add_subparsers(help="commands")

    document_command = commands.add_parser(
        "documents", help="Get list of document prefixes (JSON format)"
    )
    document_command.set_defaults(func=document)

    items_command = commands.add_parser(
        "items", help="Get list of items for specific document prefix (JSON format)"
    )
    items_command.set_defaults(func=items)
    items_command.add_argument(
        "--prefix",
        action="store",
        required=True,
        type=str,
        help="Prefix of doorstop document",
    )

    add_reference_command = commands.add_parser(
        "add_reference", help="Add reference to specific item"
    )
    add_reference_command.set_defaults(func=add_reference_to_item)
    add_reference_command.add_argument(
        "--item",
        action="store",
        required=True,
        type=str,
        help="UID of item to add reference to",
    )
    add_reference_command.add_argument(
        "reference",
        action="store",
        type=str,
        help="JSON representation of reference to add",
    )

    add_item_command = commands.add_parser("add_item", help="Add item to document")
    add_item_command.set_defaults(func=add_item)
    add_item_command.add_argument(
        "--prefix",
        action="store",
        required=True,
        type=str,
        help="Prefix of doorstop document",
    )
    add_item_command.add_argument(
        "--text", action="store", type=str, help="Initial text for new doorstop item"
    )

    parents_command = commands.add_parser("parents", help="Get parents for item")
    parents_command.set_defaults(func=parents)
    parents_command.add_argument(
        "--item", action="store", required=True, type=str, help="Doorstop item name"
    )

    children_command = commands.add_parser("children", help="Get children for item")
    children_command.set_defaults(func=children)
    children_command.add_argument(
        "--item", action="store", required=True, type=str, help="Doorstop item name"
    )

    linked_command = commands.add_parser("linked", help="Get linked items for item")
    linked_command.set_defaults(func=linked)
    linked_command.add_argument(
        "--item", action="store", required=True, type=str, help="Doorstop item name"
    )

    link_items_command = commands.add_parser("link", help="Link a child to a parent")
    link_items_command.set_defaults(func=link)
    link_items_command.add_argument(
        "child", action="store", type=str, help="child item"
    )
    link_items_command.add_argument(
        "parent", action="store", type=str, help="parent item"
    )

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)

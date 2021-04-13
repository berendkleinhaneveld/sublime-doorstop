#!/usr/bin/env python
import json
import logging
import argparse

import doorstop


doorstop.settings.ADDREMOVE_FILES = False


logger = logging.getLogger("DoorstopPlugin")


def document(args):
    tree = doorstop.build(root=args.root)
    # prefixes = {doc.prefix: doc.path for doc in tree.documents}
    prefixes = [{"prefix": doc.prefix, "path": doc.path} for doc in tree.documents]
    print(json.dumps(prefixes))


def items(args):
    tree = doorstop.build(root=args.root)
    document = tree.find_document(args.prefix)
    items = [
        {
            "uid": str(item.uid),
            "path": item.path,
            "text": item.header if item.header else item.text.split("\n")[0],
        }
        for item in document.items
    ]
    # items = {str(item.uid): item.path for item in document.items}
    print(json.dumps(items))


def parents(args):
    tree = doorstop.build(root=args.root)
    item = tree.find_item(args.item)
    parents = [
        {
            "uid": str(item.uid),
            "path": item.path,
            "text": item.header if item.header else item.text.split("\n")[0],
        }
        for item in item.parent_items
    ]
    print(json.dumps(parents))


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

    parents_command = commands.add_parser("parents", help="Get parents for item")
    parents_command.set_defaults(func=parents)
    parents_command.add_argument(
        "--item", action="store", required=True, type=str, help="Doorstop item name"
    )

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)

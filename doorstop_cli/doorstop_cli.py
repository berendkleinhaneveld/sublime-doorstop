#!/usr/bin/env python
import json
import logging
import argparse

import doorstop


doorstop.settings.ADDREMOVE_FILES = False


logger = logging.getLogger("DoorstopPlugin")


def document(args):
    tree = doorstop.build(root=args.root)
    print(json.dumps(get_document_prefixes(tree)))


def items(args):
    tree = doorstop.build(root=args.root)
    print(json.dumps(get_items_for_document_prefix(tree, args.prefix)))


def add_reference_to_item(args):
    tree = doorstop.build(root=args.root)
    reference = json.loads(args.reference)
    add_reference(tree, args.item, reference)


def get_document_prefixes(tree):
    return {doc.prefix: doc.path for doc in tree.documents}


def get_items_for_document_prefix(tree, prefix):
    document = tree.find_document(prefix)
    return {str(item.uid): str(item.path) for item in document.items}


def add_reference(tree, item, reference):
    item = tree.find_item(item)
    if not item.references:
        item.references = []

    if reference not in item.references:
        item.references.append(reference)
        item.save()


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

    args = parser.parse_args()
    args.func(args)

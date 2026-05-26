#!/usr/bin/env python3
import sys
import json
import argparse


def load_tree(path):
    with open(path) as f:
        return json.load(f)


def walk_subtree(nodes, root):
    """Yield (path, node) for every entry in the subtree rooted at `root`."""
    node = nodes.get(root)
    if node is None:
        return
    yield root, node
    if node["type"] == "dir":
        for child in node.get("children", []):
            yield from walk_subtree(nodes, child)


def diff_trees(a_tree, b_tree, include_dirs=False):
    """Walk both trees top-down, pruning subtrees whose hashes match."""
    a = a_tree["nodes"]
    b = b_tree["nodes"]
    added, removed, modified = [], [], []

    def add_subtree(nodes, path, bucket):
        for p, node in walk_subtree(nodes, path):
            if node["type"] == "file" or include_dirs:
                bucket.append(p)

    def recurse(path):
        na = a.get(path)
        nb = b.get(path)

        if na is None and nb is None:
            return
        if na is None:
            add_subtree(b, path, added)
            return
        if nb is None:
            add_subtree(a, path, removed)
            return

        if na["hash"]["full"] == nb["hash"]["full"]:
            return  # merkle prune: subtrees identical

        if na["type"] != nb["type"]:
            add_subtree(a, path, removed)
            add_subtree(b, path, added)
            return

        if na["type"] == "file":
            modified.append({
                "path": path,
                "before": na["hash"]["full"],
                "after": nb["hash"]["full"],
            })
            return

        if include_dirs:
            modified.append({
                "path": path,
                "before": na["hash"]["full"],
                "after": nb["hash"]["full"],
            })
        children = set(na.get("children", [])) | set(nb.get("children", []))
        for child in sorted(children):
            recurse(child)

    root = a_tree.get("root", b_tree.get("root", "."))
    recurse(root)
    return {
        "added": sorted(added),
        "removed": sorted(removed),
        "modified": sorted(modified, key=lambda m: m["path"]),
    }


def format_human(diff):
    lines = []
    for p in diff["removed"]:
        lines.append(f"- {p}")
    for p in diff["added"]:
        lines.append(f"+ {p}")
    for m in diff["modified"]:
        lines.append(f"~ {m['path']}  {m['before']} -> {m['after']}")
    return "\n".join(lines) if lines else "(no differences)"


def main():
    parser = argparse.ArgumentParser(
        description="Diff two Merkle trees produced by merkel-tree_v0-0-3.py."
    )
    parser.add_argument("before", help="Path to the 'before' tree JSON.")
    parser.add_argument("after", help="Path to the 'after' tree JSON.")
    parser.add_argument(
        "--include-dirs",
        action="store_true",
        help="Also report changed/added/removed directories, not just files."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable text."
    )
    args = parser.parse_args()

    a = load_tree(args.before)
    b = load_tree(args.after)

    if a.get("algorithm") and b.get("algorithm") and a["algorithm"] != b["algorithm"]:
        print(
            f"warning: algorithms differ ({a['algorithm']} vs {b['algorithm']})",
            file=sys.stderr,
        )

    diff = diff_trees(a, b, include_dirs=args.include_dirs)

    if args.json:
        print(json.dumps(diff, indent=2))
    else:
        print(format_human(diff))

    # Exit non-zero if anything differs, like classic `diff`.
    if diff["added"] or diff["removed"] or diff["modified"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

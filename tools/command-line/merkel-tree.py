#!/usr/bin/env python3
import os
import json
import argparse
import subprocess
from multiprocessing import Pool


def hash_file(filepath, algorithm):
    """Compute hash of a file using the specified algorithm."""
    result = subprocess.run([algorithm, filepath], capture_output=True, text=True)
    return result.stdout.split()[0]


def hash_string(data, algorithm):
    """Compute hash of a string using the specified algorithm."""
    result = subprocess.run([algorithm], input=data, capture_output=True, text=True)
    return result.stdout.split()[0]


def format_hash(raw_hash, algorithm):
    prefix = algorithm.split('sum')[0]
    return {
        "full": f"{prefix}-{raw_hash}",
        "short": f"{prefix}-{raw_hash[:7]}",
    }


def collect_files(dir_path):
    """Collect all regular file paths under dir_path."""
    files = []
    for root, _, filenames in os.walk(dir_path):
        for filename in filenames:
            files.append(os.path.join(root, filename))
    return files


def build_merkle_tree(root_dir, algorithm):
    """Build a flat path -> node map. Each node carries its hash, parent, and (for dirs) children."""
    root_dir = os.path.abspath(root_dir)

    files = collect_files(root_dir)
    with Pool() as pool:
        file_hashes = pool.starmap(hash_file, [(f, algorithm) for f in files])

    def rel(p):
        r = os.path.relpath(p, root_dir)
        return "." if r == "." else r

    nodes = {}

    for path, raw in zip(files, file_hashes):
        nodes[rel(path)] = {
            "type": "file",
            "hash": format_hash(raw, algorithm),
            "parent": rel(os.path.dirname(path)),
        }

    # Bottom-up so children are populated before their parent is hashed.
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        children = sorted(filenames + dirnames)
        child_lines = [
            f"{name}:{nodes[rel(os.path.join(dirpath, name))]['hash']['full']}"
            for name in children
        ]
        dir_hash = hash_string("\n".join(child_lines), algorithm)

        entry = {
            "type": "dir",
            "hash": format_hash(dir_hash, algorithm),
            "children": [rel(os.path.join(dirpath, name)) for name in children],
        }
        if dirpath != root_dir:
            entry["parent"] = rel(os.path.dirname(dirpath))
        nodes[rel(dirpath)] = entry

    return {
        "root": ".",
        "algorithm": algorithm,
        "nodes": nodes,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Build a flat Merkle tree map for a dataset using md5, sha1, or sha256."
    )
    parser.add_argument("dir_path", help="Path to the dataset directory.")
    parser.add_argument(
        "-o", "--output",
        help="Path to the output JSON file. If omitted, prints to stdout."
    )
    parser.add_argument(
        "-a", "--algorithm",
        choices=["md5sum", "sha1sum", "sha256sum"],
        default="md5sum",
        help="Hashing algorithm: md5sum, sha1sum, or sha256sum (default: md5sum)."
    )
    parser.add_argument(
        "-t", "--top-only",
        action="store_true",
        help="Print only the top-level hash of the root directory and exit."
    )
    args = parser.parse_args()

    tree = build_merkle_tree(args.dir_path, args.algorithm)

    if args.top_only:
        print(tree["nodes"]["."]["hash"]["full"])
        return

    if args.output:
        with open(args.output, "w") as f:
            json.dump(tree, f, indent=2)
        print(f"Merkle tree saved to {args.output}")
    else:
        print(json.dumps(tree, indent=2))


if __name__ == "__main__":
    main()

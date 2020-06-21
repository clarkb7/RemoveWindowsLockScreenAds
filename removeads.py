import os
import sys
import argparse
import json

import logging
logger = logging.getLogger("RemoveWindowsLockScreenAds")

def remove_ads(path):
    if not os.path.exists(path):
        raise ValueError("Path does not exist: {}".format(path))
    with open(path, 'r') as f:
        jso = json.load(f)

    keep_items = []
    for item in jso['items']:
        prop = item['properties']
        if "basicHotspot" == prop['template']['text']:
            # Annoying ad
            pass
        if "infoHotspot" == prop['template']['text']:
            # Image info/credits
            keep_items.append(item)
    jso['items'] = keep_items

    with open(path, 'w') as f:
        json.dump(jso, f)

def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    subp = parser.add_subparsers(dest='subparser_name')

    pwatch = subp.add_parser("watch", help="Watch for new ads and remove them")
    pwatch.add_argument("path", nargs="?", const=None, help="Directory path to watch")

    pfile = subp.add_parser("file", help="Remove ads from specific file")
    pfile.add_argument("path", help="Path to file to remove lock screen ads from")

    args = parser.parse_args(argv[1:])

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    sub = args.subparser_name
    if sub == "watch":
        raise NotImplementedError()
    elif sub == "file":
        remove_ads(args.path)

if __name__ == "__main__":
    main(sys.argv)

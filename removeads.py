import os
import sys
import argparse
import json
import functools

import logging
logger = logging.getLogger("RemoveWindowsLockScreenAds")

def catch_exception(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(e)
            return None
    return wrapper

class AdRemover():
    def __init__(self, dry_run=False):
        self.dry_run = dry_run

    @catch_exception
    def remove_ads_file(self, path):
        if not os.path.exists(path):
            raise ValueError("Path does not exist: {}".format(path))

        logger.debug("Processing ContentDeliveryManager file: {}".format(os.path.basename(path)))

        with open(path, 'r') as f:
            jso = json.load(f)

        # Iterate list of items and pick the ones we want to keep
        keep_items = []
        for item in jso['items']:
            try:
                prop = item['properties']
                if "basicHotspot" == prop['template']['text']:
                    # Annoying ad
                    logger.debug("Removing ad: '{}'".format(prop['title']['text']))
                elif "infoHotspot" == prop['template']['text']:
                    # Image info/credits
                    keep_items.append(item)
                else:
                    logger.debug("Skipping unknown template type: {}".format(prop['template']['text']))
            except KeyError as e:
                logger.exception("")
                logger.debug("Unexpected item format: {}".format(json.dumps(item)))
        jso['items'] = keep_items

        if not self.dry_run:
            with open(path, 'w') as f:
                json.dump(jso, f)

    def remove_ads_dir(self, path):
        for fpath in os.listdir(path):
            self.remove_ads_file(os.path.join(path,fpath))

    def remove_ads_path(self, path):
        if os.path.isdir(path):
            self.remove_ads_dir(path)
        elif os.path.isfile(path):
            self.remove_ads_file(path)

def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--dry-run", action="store_true",
        help="Process and log but do not modify files")
    subp = parser.add_subparsers(dest='subparser_name')

    pwatch = subp.add_parser("watch", help="Watch for new ads and remove them")
    pwatch.add_argument("path", nargs="?", const=None, help="Directory path to watch")

    pfile = subp.add_parser("file", help="Remove ads from specific file")
    pfile.add_argument("path", help="Path to file or directory to remove lock screen ads from")

    args = parser.parse_args(argv[1:])

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    adrem = AdRemover(dry_run=args.dry_run)

    sub = args.subparser_name
    if sub == "watch":
        raise NotImplementedError()
    elif sub == "file":
        adrem.remove_ads_path(args.path)

if __name__ == "__main__":
    main(sys.argv)

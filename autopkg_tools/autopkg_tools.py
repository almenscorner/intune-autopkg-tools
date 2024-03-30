#!/usr/bin/env python3

# BSD-3-Clause
# Copyright (c) Facebook, Inc. and its affiliates.
# Copyright (c) tig <https://6fx.eu/>.
# Copyright (c) Gusto, Inc.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import sys
import json
import plistlib
import subprocess

from pathlib import Path
from argparse import ArgumentParser
from teams_alert import notify_teams
from logger import logger

DEBUG = os.environ.get("DEBUG", False)
OVERRIDES_DIR = os.environ.get("OVERRIDES_DIR")
RECIPE_TO_RUN = os.environ.get("RECIPE", None)
TEAMS_WEBHOOK = os.environ.get("TEAMS_WEBHOOK")
logger = logger("/tmp/autopkg_tools.log")


class Recipe(object):
    def __init__(self, path):
        self.path = os.path.join(OVERRIDES_DIR, path)
        self.error = False
        self.results = {}
        self.updated = False
        self.removed = False
        self.promoted = False
        self.verified = None

        self._keys = None
        self._has_run = False

    @property
    def plist(self):
        if self._keys is None:
            with open(self.path, "rb") as f:
                self._keys = plistlib.load(f)

        return self._keys

    @property
    def updated_version(self):
        if not self.results or not self.results["imported"]:
            return None

        return self.results["imported"][0]["version"].strip().replace(" ", "")

    @property
    def name(self):
        if "NAME" in self.plist["Input"]:
            return self.plist["Input"]["NAME"]
        else:
            return "Recipe"

    @property
    def identifier(self):
        if "Identifier" in self.plist:
            return self.plist["Identifier"]
        else:
            return ""

    def verify_trust_info(self):
        cmd = [
            "/usr/local/bin/autopkg",
            "verify-trust-info",
            f'"{self.identifier}"',
            "-vvv",
        ]
        cmd = " ".join(cmd)

        if DEBUG:
            logger.debug(f"Running {cmd}")

        p = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )
        (output, err) = p.communicate()
        p_status = p.wait()
        if p_status == 0:
            self.verified = True
        else:
            err = err.decode()
            self.results["message"] = err
            self.verified = False
        return self.verified

    def update_trust_info(self):
        cmd = ["/usr/local/bin/autopkg", "update-trust-info", f'"{self.identifier}"']
        cmd = " ".join(cmd)

        if DEBUG:
            logger.debug(f"Running {cmd}")

        # Fail loudly if this exits 0
        try:
            subprocess.check_call(cmd, shell=True)
        except subprocess.CalledProcessError as e:
            logger.error(e.stderr)
            raise e

    def _parse_report(self, report):
        with open(report, "rb") as f:
            report_data = plistlib.load(f)

        failed_items = report_data.get("failures", [])
        imported_items = []
        removed_items = []
        promoted_items = []
        if report_data.get("summary_results"):
            # This means something happened
            intune_results = report_data["summary_results"].get(
                "intuneappuploader_summary_result", {}
            )
            removed_results = report_data["summary_results"].get(
                "intuneappcleaner_summary_result", {}
            )
            promoted_results = report_data["summary_results"].get(
                "intuneapppromoter_summary_result", {}
            )
            imported_items.extend(intune_results.get("data_rows", []))
            removed_items.extend(removed_results.get("data_rows", []))
            promoted_items.extend(promoted_results.get("data_rows", []))

        return {
            "imported": imported_items,
            "failed": failed_items,
            "removed": removed_items,
            "promoted": promoted_items,
        }

    def _parse_list(self, list):
        with open(list, "rb") as f:
            data = json.load(f)
        return data

    def run(self, opts):
        verbosity_level = "-vvv" if DEBUG else "-v"
        if self.verified == False:
            self.error = True
            self.results["failed"] = True
        else:
            report = "/tmp/autopkg.plist"
            if not os.path.isfile(report):
                # Letting autopkg create them has led to errors on github runners
                Path(report).touch()

            try:
                cmd = [
                    "/usr/local/bin/autopkg",
                    "run",
                    f'"{self.identifier}"',
                    verbosity_level,
                    "--report-plist",
                    report,
                ]

                if opts.cleanup_list:
                    cleanup_list = self._parse_list(opts.cleanup_list)
                    cleanup_item = [
                        item for item in cleanup_list if item["name"] == self.name
                    ]
                    if cleanup_item:
                        cmd.extend(
                            [
                                "--post",
                                "com.github.almenscorner.intune-upload.processors/IntuneAppCleaner",
                            ]
                        )
                        # check if keep_count is set
                        if cleanup_item[0].get("keep_count"):
                            cmd.extend(
                                [
                                    "-k",
                                    f"keep_version_count={cleanup_item[0]['keep_count']}",
                                ]
                            )
                    else:
                        logger.log(
                            f"Skipping cleanup for {self.name}, not in cleanup list"
                        )

                if opts.promote_list:
                    app_names = self._parse_list(opts.promote_list)
                    if self.name in app_names:
                        cmd.extend(
                            [
                                "--post",
                                "com.github.almenscorner.intune-upload.processors/IntuneAppPromoter",
                            ]
                        )
                    else:
                        logger.log(
                            f"Skipping promotion for {self.name}, not in promote list"
                        )

                if DEBUG:
                    logger.debug(f"Running {cmd}")

                cmd = " ".join(cmd)

                p = subprocess.Popen(
                    cmd,
                    shell=True,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                )

                while True:
                    output = p.stdout.read(1024)  # Read in chunks
                    if not output and p.poll() is not None:
                        break
                    if output:
                        logger.logger.handlers[0].stream.write(output.decode("utf-8"))
                        logger.logger.handlers[0].stream.flush()

            except subprocess.CalledProcessError as e:
                self.error = True

            self._has_run = True
            self.results = self._parse_report(report)
            if not self.results["failed"] and not self.error and self.updated_version:
                self.updated = True
            if (
                self.results["removed"]
                and int(self.results["removed"][0].get("removed count")) > 0
            ):
                self.removed = True
            if self.results["promoted"] and self.results["promoted"][0].get(
                "promotions"
            ):
                self.promoted = True

        return self.results


### Recipe handling
def handle_recipe(recipe, opts):
    if not opts.disable_verification:
        recipe.verify_trust_info()
        if recipe.verified is False:
            recipe.update_trust_info()
    if recipe.verified in (True, None):
        recipe.run(opts)

    return recipe


def parse_recipes(recipes):
    recipe_list = []
    ## Added this section so that we can run individual recipes
    if RECIPE_TO_RUN:
        for recipe in recipes:
            ext = os.path.splitext(recipe)[1]
            if ext != ".recipe":
                recipe_list.append(recipe + ".recipe")
            else:
                recipe_list.append(recipe)
    else:
        ext = os.path.splitext(recipes)[1]
        if ext == ".json":
            parser = json.load
        elif ext == ".plist":
            parser = plistlib.load
        else:
            logger.error(f'Invalid run list extension "{ext}" (expected plist or json)')
            sys.exit(1)

        with open(recipes, "rb") as f:
            recipe_list = parser(f)

    return map(Recipe, recipe_list)


def main():
    parser = ArgumentParser(description="Wrap AutoPkg with git support.")
    parser.add_argument(
        "-l", "--list", help="Path to a plist or JSON list of recipe names."
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Disables sending Slack alerts and adds more verbosity to output.",
    )
    parser.add_argument(
        "-v",
        "--disable_verification",
        action="store_true",
        help="Disables recipe verification.",
    )
    parser.add_argument(
        "-c",
        "--cleanup-list",
        help="List of apps to run cleanup for, separated by commas",
    )
    parser.add_argument(
        "--promote-list",
        help="List of apps to run promotion for, separated by commas",
    )

    opts = parser.parse_args()

    global DEBUG
    DEBUG = bool(DEBUG or opts.debug)
    if DEBUG:
        logger.logger.setLevel(10)

    failures = []

    recipes = (
        RECIPE_TO_RUN.split(", ") if RECIPE_TO_RUN else opts.list if opts.list else None
    )
    if recipes is None:
        logger.error("Recipe --list or RECIPE_TO_RUN not provided!")
        sys.exit(1)
    recipes = parse_recipes(recipes)
    for recipe in recipes:
        handle_recipe(recipe, opts)
        if DEBUG:
            logger.debug("Skipping Teams notification - debug is enabled!")
        if TEAMS_WEBHOOK is None:
            logger.log("Skipping Teams notification - webhook url is missing!")
        if not DEBUG and TEAMS_WEBHOOK is not None:
            notify_teams(recipe, opts)
        if not opts.disable_verification:
            if not recipe.verified:
                failures.append(recipe)


if __name__ == "__main__":
    main()

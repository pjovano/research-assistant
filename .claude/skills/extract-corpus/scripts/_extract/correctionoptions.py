from __future__ import annotations

_PDF_HELP = "a library filename, or a path"
_BODY_HELP = "the reviewed work's corpus file body instead of its trial"


class CorrectionOptions:
    def add(self, subparsers) -> None:
        self._add_correct(subparsers)
        self._add_listing(subparsers)

    @staticmethod
    def _add_correct(subparsers) -> None:
        correct = subparsers.add_parser("correct",
                                        help="read-only: apply a corrections file to the trial and print each "
                                             "correction's outcome; with --apply, write the corrected trial")
        correct.add_argument("pdf", help=_PDF_HELP)
        correct.add_argument("--corrections", required=True, metavar="FILE",
                             help="JSON list of corrections the layout corrector wrote")
        correct.add_argument("--apply", action="store_true",
                             help="write the corrected text and record the applied corrections")
        correct.add_argument("--body", action="store_true", help=_BODY_HELP)
        correct.add_argument("--replace", action="store_true",
                             help="with --body --apply, rewrite the corpus file's body")

    @staticmethod
    def _add_listing(subparsers) -> None:
        listing = subparsers.add_parser("correction-listing",
                                        help="read-only: list the pages of the trial the cleanup reads, each with "
                                             "the reasons the script doubts it and its text")
        listing.add_argument("pdf", help=_PDF_HELP)
        listing.add_argument("--body", action="store_true", help=_BODY_HELP)

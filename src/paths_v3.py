"""v3 path roots, so every script runs unchanged locally and on Kaggle (Linux).

--data-root  raw inputs (default <repo>/data/raw; config paths such as "figshare/..." resolve under it)
--out-root   every output (default <repo>; config paths such as "results/v3/..." resolve under it)
--prev-root  outputs of earlier steps that this step reads (default: the out-root)
"""
from dataclasses import dataclass
from pathlib import Path

from provenance_v3 import ROOT


@dataclass(frozen=True)
class Roots:
    data: Path
    out: Path
    prev: Path

    def data_path(self, rel):
        return self.data / Path(rel)

    def out_path(self, rel):
        return self.out / Path(rel)

    def prev_path(self, rel):
        return self.prev / Path(rel)

    def as_dict(self):
        return {"data_root": self.data.as_posix(), "out_root": self.out.as_posix(), "prev_root": self.prev.as_posix()}


def add_root_args(parser):
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "raw", help="raw inputs (contains figshare/)")
    parser.add_argument("--out-root", type=Path, default=ROOT, help="root for all outputs")
    parser.add_argument("--prev-root", type=Path, default=None, help="root of earlier-step outputs (default: out-root)")
    return parser


def roots_from_args(args):
    out = Path(args.out_root).resolve()
    prev = Path(args.prev_root).resolve() if args.prev_root else out
    return Roots(data=Path(args.data_root).resolve(), out=out, prev=prev)

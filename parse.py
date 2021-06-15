import sys
from glob import glob
import os.path
import re

req_re = re.compile(
    r"^\|\s*\*\*([0-9.]+)\*\* \|\s*(\[[^\]]*\])?\s*(.*)\s*\|\s*(.*)\s*\|\s*(.*)\s*\|\s*(.*)\s*\|"
)


def enumerate1(seq):
    return ((i + 1, item) for i, item in enumerate(seq))


def level(l1, l2, l3):
    if l1:
        return 1
    if l2:
        return 2
    if l3:
        return 3
    return None


def parse_file(fname):
    with open(fname) as fp:
        for lineno, line in enumerate1(fp):
            m = req_re.match(line)
            if m:
                id, tag, req, l1, l2, l3 = m.groups()
                l = level(l1, l2, l3)
                print(id, l)


if __name__ == "__main__":
    asvs_dir = sys.argv[1]
    req_files = glob(os.path.join(asvs_dir, "0x??-V*"))
    for req_file in req_files:
        print(parse_file(req_file))

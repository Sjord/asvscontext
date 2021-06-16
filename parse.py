import sys
from glob import glob
import os.path
import re
import git

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
    reqs = []
    with open(fname) as fp:
        for lineno, line in enumerate1(fp):
            m = req_re.match(line)
            if m:
                id, tag, req, l1, l2, l3 = m.groups()
                l = level(l1, l2, l3)
                reqs.append((id, tag, req, l, (fname, lineno)))
    return reqs


class AsvsRepo:
    def __init__(self, path):
        self.path = path
        self.repo = git.Repo(path)

    @property
    def requirement_file_paths(self):
        return glob(os.path.join(self.path, "4.0/en/0x??-V*"))

    def blame(self, req_file):
        blame = self.repo.blame("HEAD", req_file)
        line_no = 1
        line_to_commit = {}
        for commit, lines in blame:
            new_line_no = line_no + len(lines)
            while line_no < new_line_no:
                line_to_commit[line_no] = commit
                line_no += 1
        return line_to_commit


if __name__ == "__main__":
    asvs_dir = sys.argv[1]
    repo = AsvsRepo(asvs_dir)

    req_files = repo.requirement_file_paths
    for req_file in req_files:
        print(req_file)
        blame = repo.blame(req_file)
        print(parse_file(req_file))

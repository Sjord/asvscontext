import sys
from glob import glob
import os.path
import re
import git
from github import Github
import os
from collections import defaultdict
from get_merge import get_ancestry_path_first_parent_match


req_re = re.compile(
    r"^\|\s*\*\*([0-9.]+)\*\* \|\s*(\[[^\]]*\])?\s*([^|]*)\s*\|\s*([^|]*)\s*\|\s*([^|]*)\s*\|\s*([^|]*)\s*\|"
    #            ID                   Tag           Desc          L1              L2              L3 
)

ref_re = re.compile("([1-9]\d*\.[1-9]\d*\.[1-9]\d*)")

issue_re = re.compile("((/issues/|issue-|#)(\d+))")


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


def escape(s):
    return s.replace("'", "&apos;");


class Requirement:
    def __init__(self, id, tag, description, level, position, commit, issues):
        self.id = id
        self.tag = tag
        self.description = description
        self.level = level or ""
        self.position = position
        self.commit = commit
        self.issues = issues

    @property
    def emoji(self):
        tag = self.tag
        if tag is None:
            return "⚪️"
        if "ADDED" in tag:
            return "➕";
        if "MOVED" in tag:
            return "🔀";
        if "SPLIT" in tag:
            return "✂️";
        if "REMOVED" in tag or "DELETED" in tag:
            return "❌";
        if "LEVEL" in tag:
            return "🎚"
        return "🖊️";
    
    @property
    def title(self):
        return self.tag or ""

    @property
    def formatted_issues(self):
        texts = []
        for i in self.issues:
            texts.append(f"<a href='{i.html_url}'>#{i.number}</a>")
        return " ".join(texts)


class AsvsRepo:
    def __init__(self, path):
        self.path = path
        self.repo = git.Repo(path)
        self.github = Github(os.environ["github_access_token"]).get_repo("OWASP/ASVS")

    @property
    def requirement_file_paths(self):
        files = glob(os.path.join(self.path, "4.0/en/0x??-V*"))
        return sorted(files)

    def commit_msg_issues(self, commit):
        matches = issue_re.findall(commit.message)

        merge_commit = get_ancestry_path_first_parent_match(self.repo, commit.hexsha, "master")
        if merge_commit:
            merge_commit = self.repo.commit(merge_commit)
            matches += issue_re.findall(merge_commit.message)

        numbers = set([number for (_, _, number) in matches])
        return [self.github.get_issue(int(n)) for n in numbers]

    def parse_file(self, fname):
        reqs = []
        blames = self.blame(fname)
        issues = self.get_issues()
        with open(fname) as fp:
            for lineno, line in enumerate1(fp):
                m = req_re.match(line)
                if m:
                    id, tag, req, l1, l2, l3 = m.groups()
                    if "([C" in req:
                        req = req[:req.index("([C")]
                    l = level(l1, l2, l3)
                    commit = blames[lineno]
                    req = Requirement(id, tag, req.strip(), l, (fname, lineno), commit, self.commit_msg_issues(commit) + issues.get(id, []))
                    reqs.append(req)
        return reqs

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
    
    def get_issues(self):
        issue_dict = defaultdict(list)
        g = Github(os.environ["github_access_token"])
        repo = g.get_repo("OWASP/ASVS")
        issues = repo.get_issues() #filter="all", state="all")
        for issue in issues:
            m = ref_re.findall(issue.title)
            if m:
                for req_id in m:
                    issue_dict[req_id].append(issue)
        return issue_dict


if __name__ == "__main__":
    asvs_dir = sys.argv[1]
    repo = AsvsRepo(asvs_dir)

    print("|ID|L|I|M|Desc|")
    print("--|--|--|--|--")

    req_files = repo.requirement_file_paths
    for req_file in req_files:
        reqs = repo.parse_file(req_file)
        for r in reqs:
            print(f"|{r.id}|{r.level}|{r.formatted_issues}|<span title='{r.title}'>{r.emoji}</span>|{r.description}|")

import sys
from glob import glob
import os.path
import re
import git
from github import Github
import os
from collections import defaultdict
from get_merge import get_ancestry_path_first_parent_match, get_first_merge_into


req_re = re.compile(
    r"^\|\s*\*\*([0-9.]+)\*\* \|\s*(\[[^\]]*\])?\s*([^|]*)\s*\|\s*([^|]*)\s*\|\s*([^|]*)\s*\|\s*([^|]*)\s*\|"
    #            ID                   Tag           Desc          L1              L2              L3 
)

ref_re = re.compile("([1-9]\d*\.[1-9]\d*\.[1-9]\d*)")

issue_re = re.compile("((/issues/|issue-|issue |issue|pr|#)(\d\d+))")


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
    return (s.replace("'", "&apos;")
        .replace("|", "&#x7C;"))


class Requirement:
    def __init__(self, id, tag, description, level, position, commits, issues):
        self.id = id
        self.tag = tag
        self.description = description
        self.level = level or ""
        self.position = position
        self.commits = commits
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
        meh_issues = [1119]
        issues = [i for i in self.issues if i.number not in meh_issues]

        texts = []
        for i in sorted(issues, key=lambda i: -i.number):
            texts.append(f"<a href='{escape(i.html_url)}' title='{escape(i.title)}'>#{i.number}</a>")
        return " ".join(texts)


class AsvsRepo:
    def __init__(self, path):
        self.path = path
        self.repo = git.Repo(path)
        self.github = Github(os.environ["github_access_token"]).get_repo("OWASP/ASVS")
        self._issue_dict = None

    @property
    def requirement_file_paths(self):
        files = glob(os.path.join(self.path, "5.0/en/0x??-V*"))
        return sorted(files)

    def commit_msg_issues(self, commits):
        matches = []
        for commit in commits:
            matches += issue_re.findall(commit.message)

        numbers = set([number for (_, _, number) in matches])
        return [self.github.get_issue(int(n)) for n in numbers]

    def parse_file(self, fname):
        reqs = []
        with open(fname) as fp:
            for lineno, line in enumerate1(fp):
                m = req_re.match(line)
                if m:
                    id, tag, req, l1, l2, l3 = m.groups()
                    if "([C" in req:
                        req = req[:req.index("([C")]
                    l = level(l1, l2, l3)
                    commits = self.relevant_commits(fname, id)
                    req = Requirement(id, tag, req.strip(), l, (fname, lineno), commits, self.commit_msg_issues(commits) + self.issues.get(id, []))
                    reqs.append(req)
        return reqs

    def get_merge_commit(self, sha):
        a = get_ancestry_path_first_parent_match(self.repo, sha, "master")
        b = get_first_merge_into(self.repo, sha, "master")
        if a == b:
            return a
        return None

    def relevant_commits(self, fname, id):
        log = self.repo.git.log("-G", re.escape(f"**{id}**"), "v4.0.1..HEAD", "--pretty=format:%H", "--", fname)
        shas = [sha for sha in log.split("\n") if sha]
        merges = [self.get_merge_commit(sha) for sha in shas]
        merges = [m for m in merges if m]
        return [self.repo.commit(c) for c in shas + merges]
    
    @property
    def issues(self):
        if self._issue_dict:
            return self._issue_dict

        issue_dict = defaultdict(list)
        g = Github(os.environ["github_access_token"])
        repo = g.get_repo("OWASP/ASVS")
        issues = repo.get_issues(state="all")
        for issue in issues:
            m = ref_re.findall(issue.title)
            if m:
                for req_id in m:
                    issue_dict[req_id].append(issue)

        self._issue_dict = issue_dict
        return issue_dict

def find_req(reqs, id):
    matches = [r for r in reqs if r.id == id]
    (single,) = matches
    return single

def merge_issues(a, b):
    issues = {}
    for ib in b:
        issues[ib.id] = ib
    for ia in a:
        issues[ia.id] = ia
    return sorted(issues.values(), key=lambda i: -i.number)

def merge_reqs(a, b):
    result = []
    for reqa in a:
        try:
            reqb = find_req(b, reqa.id)
            result.append(Requirement(
                reqa.id, reqa.tag or reqb.tag, reqa.description or reqb.description, reqa.level or reqb.level, reqa.position or reqb.position, reqa.commits + reqb.commits, merge_issues(reqa.issues, reqb.issues)))
        except ValueError:
            result.append(reqa)

    return result

if __name__ == "__main__":
    asvs_dir = sys.argv[1]
    repo = AsvsRepo(asvs_dir)

    print("|ID|L|I|M|Desc|")
    print("--|--|--|--|--")

    req_files = repo.requirement_file_paths
    for req_file in req_files:
        print(req_file, file=sys.stderr)

        reqs5 = repo.parse_file(req_file)
        req4_file = req_file.replace("/5.0/", "/4.0/")
        reqs4 = repo.parse_file(req4_file)
        reqs = merge_reqs(reqs5, reqs4)

        for r in reqs:
            print(f"|{r.id}|{r.level}|{r.formatted_issues}|<span title='{r.title}'>{r.emoji}</span>|{r.description}|")

    print()
    print("Generated by [asvscontext](https://github.com/Sjord/asvscontext)")

# git-filter-repo 回调：将 cursoragent/Cursor Agent 的提交改为 llee92063
def callback(commit, metadata):
    def is_cursor(e, n):
        if e and (b'cursoragent' in e.lower() or b'cursor-agent' in e.lower()):
            return True
        if n and (n == b'Cursor Agent' or n == b'cursoragent' or n == b'CursorAgent'):
            return True
        return False
    if is_cursor(commit.author_email, commit.author_name) or is_cursor(commit.committer_email, commit.committer_name):
        commit.author_name = b'llee92063'
        commit.author_email = b'llee92063@gmail.com'
        commit.committer_name = b'llee92063'
        commit.committer_email = b'llee92063@gmail.com'

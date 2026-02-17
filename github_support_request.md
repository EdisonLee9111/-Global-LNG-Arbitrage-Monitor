# GitHub Support 工单内容（中英文版本）

## 英文版本（推荐使用）

**Subject:** Request to Clear Contributors Cache for Repository

**Message:**

Hello GitHub Support Team,

I am writing to request assistance with clearing the contributors cache for my repository:

**Repository:** https://github.com/EdisonLee9111/-Global-LNG-Arbitrage-Monitor

**Issue:**
The contributors list currently shows "cursoragent Cursor Agent" as a contributor, even though I have successfully rewritten the entire git history to remove all commits containing "Co-authored-by: Cursor <cursoragent@cursor.com>".

**What I've done:**
1. Initially attempted `git filter-repo` (which parsed 1 commit locally)
2. Discovered the old commits with `Co-authored-by: Cursor <cursoragent@cursor.com>` existed on GitHub's server
3. Created a **completely new orphan branch** using `git checkout --orphan` to start fresh history from scratch
4. Committed all current files as a single clean commit (author and committer: llee92063@gmail.com)
5. Deleted the old `main` branch and renamed the orphan branch to `main`
6. Force-pushed to GitHub: `git push origin main --force`, which **replaced the entire commit history**
7. Verified via API that the current commit (4521dfebf07e67e1e676b0aba6949e1892ce925c) contains no reference to cursoragent
8. Confirmed via `git ls-remote origin` that only one ref exists: `refs/heads/main` pointing to the clean commit

**Note on git-filter-repo output:**
Since I used the orphan branch approach (complete history replacement) rather than traditional rewriting, there is no "First Changed Commit" in the git-filter-repo sense. The old root commit was entirely discarded and replaced with a new root commit `4521dfebf07e67e1e676b0aba6949e1892ce925c`.

**Current status:**
- API endpoint `/repos/EdisonLee9111/-Global-LNG-Arbitrage-Monitor/contributors` correctly shows only one contributor (vanille940)
- However, the web UI at `/graphs/contributors` still displays "cursoragent Cursor Agent"
- This appears to be caused by GitHub's contributors cache retaining old/deleted commits

**Request:**
Could you please manually refresh/clear the contributors cache for this repository? I want the contributors list to reflect only the current commit history.

**Repository details:**
- Repository: EdisonLee9111/-Global-LNG-Arbitrage-Monitor
- Current HEAD commit: 4521dfebf07e67e1e676b0aba6949e1892ce925c (new root commit, orphan branch)
- Identity to remove: cursoragent Cursor Agent (cursoragent@cursor.com)
- Expected contributors: Only vanille940 (llee92063@gmail.com)
- Number of affected pull requests: 0
- git-filter-repo "First Changed Commit": N/A (used orphan branch to replace entire history instead of rewriting)

**Confirmation:**
- ✓ No forks of this repository exist
- ✓ No pull request refs exist (refs/pull/*)
- ✓ No branches other than main exist
- ✓ I have successfully rewritten history and force-pushed
- ✓ No remaining refs on the repository contain the offending author

Thank you for your assistance!

Best regards

---

## 中文版本（如果需要翻译）

**主题：** 请求清除仓库的 Contributors 缓存

**消息：**

你好 GitHub Support 团队，

我想请求帮助清除我仓库的贡献者缓存：

**仓库地址：** https://github.com/EdisonLee9111/-Global-LNG-Arbitrage-Monitor

**问题描述：**
贡献者列表中显示了 "cursoragent Cursor Agent"，尽管我已经成功重写了整个 git 历史，删除了所有包含 "Co-authored-by: Cursor <cursoragent@cursor.com>" 的提交。

**我已完成的操作：**
1. 初步尝试了 `git filter-repo`（本地仅解析 1 个提交）
2. 发现包含 `Co-authored-by: Cursor <cursoragent@cursor.com>` 的旧提交存在于 GitHub 服务器上
3. 使用 `git checkout --orphan` 创建了**全新的孤儿分支**，从零开始建立历史
4. 将所有当前文件作为单个干净提交（作者和提交者：llee92063@gmail.com）
5. 删除了旧的 `main` 分支，将孤儿分支重命名为 `main`
6. 强制推送到 GitHub：`git push origin main --force`，**完全替换了整个提交历史**
7. 通过 API 验证当前提交 (4521dfebf07e67e1e676b0aba6949e1892ce925c) 中不包含 cursoragent 引用
8. 通过 `git ls-remote origin` 确认仅存在一个引用：`refs/heads/main` 指向干净提交

**关于 git-filter-repo 输出的说明：**
由于我使用了孤儿分支方法（完全替换历史）而非传统的重写，因此没有 git-filter-repo 意义上的 "First Changed Commit"。旧的根提交已被完全丢弃并替换为新的根提交 `4521dfebf07e67e1e676b0aba6949e1892ce925c`。

**当前状态：**
- API 端点 `/repos/EdisonLee9111/-Global-LNG-Arbitrage-Monitor/contributors` 正确显示只有一个贡献者 (vanille940)
- 但网页界面 `/graphs/contributors` 仍然显示 "cursoragent Cursor Agent"
- 这似乎是 GitHub 的贡献者缓存保留了旧的/已删除的提交导致的

**请求：**
能否请你们手动刷新/清除此仓库的贡献者缓存？我希望贡献者列表只反映当前的提交历史。

**仓库详情：**
- 仓库：EdisonLee9111/-Global-LNG-Arbitrage-Monitor
- 当前 HEAD 提交：4521dfebf07e67e1e676b0aba6949e1892ce925c（新的根提交，孤儿分支）
- 要移除的身份：cursoragent Cursor Agent (cursoragent@cursor.com)
- 期望的贡献者：仅 vanille940 (llee92063@gmail.com)
- 受影响的 PR 数量：0
- git-filter-repo "First Changed Commit"：N/A（使用孤儿分支完全替换历史，而非重写）

感谢你们的帮助！

---

## 提交步骤

1. 访问：https://support.github.com/contact
2. 选择问题类型（通常选择 "Repositories" 或 "Other"）
3. 填写表单：
   - Subject: Request to Clear Contributors Cache for Repository
   - Message: 复制上面的英文版本
4. 提交工单
5. 等待 GitHub 回复（通常 1-3 个工作日）

---

## 备注

- 使用英文版本可能获得更快的响应
- 附上仓库链接和当前 commit SHA 可以帮助支持团队快速定位问题
- 如果支持团队无法手动清除，可能需要采用"删除仓库重建"的方案

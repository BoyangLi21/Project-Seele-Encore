# 交接附属证据

主文档是 ../HANDOFF_CODEX_20261106.zh.md。

- saved-work-manifest.json：407份历史源码/文档的原路径、base commit、原状态、大小、快照路径；另2项仅保留原位。
- snapshots/：完整原始字节，后缀.snapshot.txt；不执行，不批量覆盖当前源码。要合并时以manifest的base commit与当前main做三方比较，明确选择每项改动。
- main-uncommitted-inventory.tsv：F:/eva的522个未提交文件，只读分类，没有改动原件。
- git-inventory-before.json：交接前分支、worktree、提交祖先关系；不是交接后最新HEAD。
- environment-inventory.json：工具/自动化/SSH名称与artifact顶层目录，不含密钥内容。
- map-status-at-handoff.json、map-draft-inventory.json：81批状态和未安装候选。F盘原件均未改。
- operational-sources/：本对话用过的发布脚手架原始文本与来源；有旧路径和覆盖日志风险，不能直接重放旧批次。
- validation-summary.json：本次离线构建、6个草稿契约测试和语法/保存检查。
- final-receipt.json（生成后）：保存提交、首次普通推送、停止与最终盘点结果。

没有将官方素材、私有模型、世界或大体积生成物保存到这里。保存不是功能完成或人工验收。

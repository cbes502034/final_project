# 這個目錄是複製過來的，不要直接改

原始碼在 `working_space/`。這裡是為了讓靜態站台能直接發布而提交的副本
（Render 上的服務是手動建立的，`render.yaml` 的建置指令不會生效）。

改完 `working_space/` 之後，用這行同步：

```bash
rm -rf site/proto && cp -r working_space site/proto
```

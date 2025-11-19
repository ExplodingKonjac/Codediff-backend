# Codediff-backend

Codediff 项目的后端。使用 Flask 编写，使用 uv 进行包管理。

## 如何部署

目前大概只支持 Linux。进入项目目录，将包同步（需要 uv）：

```
uv sync
```

安装依赖：

```
./init.sh
```

然后就可以按照标准的 Flask 应用部署步骤来部署了。可以在 .env 中修改配置。

尽量在项目根目录运行，这样不用重新设置 testlib.h, rlimit_wrapper 的路径。

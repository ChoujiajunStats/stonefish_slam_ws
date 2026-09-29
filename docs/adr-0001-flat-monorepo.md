---
status: accepted
date: 2026-09-21
---

# ADR-0001：根目录并列的功能包

采用一个仓库、功能包并列、固定上游 underlay、项目 overlay。
显式 colcon 路径为 `app robot simulations ui benchmark`。
不建立根 `package.xml`，不复制第三方源码入仓库，不预建后续空算法包。
接口目录暂为文档，首次需要自定义消息时再建立 `uw_interfaces`。

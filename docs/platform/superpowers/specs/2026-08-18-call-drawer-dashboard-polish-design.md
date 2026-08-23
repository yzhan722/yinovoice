# 通话侧栏详情 + 工作台正式化

日期：2026-08-18  
状态：已部署 Stage1（待网页验收）  
范围：Control Plane Web（租户；共用列表组件则 operator 受益）  
不上生产（另授 Stage1）

## 目标

1. 通话记录：列表点击打开右侧抽屉，气泡转写更直观（对齐 Vapi 拉篮，浅色系）  
2. 工作台：去掉 Streak/庆祝游戏化；保留进度；强化运营 KPI/待办/快捷入口  

## 通话抽屉

- 组件：扩展 `CallRecordListView` + 新 `CallRecordDetailDrawer`  
- 内容：元信息、录音播放（若有）、转写气泡  
- 保留详情路由深链  

## 工作台

- 删 Streak / 火焰 / 进 celebration  
- 保留进度圆环  
- 文案正式化；右侧可放待办摘要  

## 非目标

endedReason 搜索后端、双色波形、Logs/Cost Tab、深色主题  

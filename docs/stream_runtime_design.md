# 流式 LLM 调度执行框架设计文档

## 澄清结论
- Python 3.11
- OpenAI SDK 适配封装可接受
- 默认 fail_fast=False
- 使用统一 TaskOutcome
- 示例采用真实 OpenAI 接口
- README 需要扩展指南

## WHAT
构建 `stream_runtime` 包，分离抽象层和实现层，实现：
- 流式 chunk source
- JSONL 增量 parser
- 动态 add_task scheduler
- orchestrator 生命周期编排
- 可注入 executor/aggregator

## WHY
- 解耦上游 SDK 与业务
- 支持复用与扩展
- 任务列表动态生成场景下可并发处理

## HOW
- 抽象协议定义于 `abstractions/`
- 默认实现定义于 `implementations/`
- 通过 `DefaultStreamOrchestrator` 串联 source->parser->scheduler->aggregate
- 统一错误边界：source/parse/task/aggregate

# stream_runtime：流式 LLM 动态任务调度执行框架

`stream_runtime` 是一个可复用的 Python 3.11 框架，用于把「LLM 流式输出」转化为「动态并发任务执行」：

- 上游流式产出 chunk
- 增量解析对象（当前实现：JSONL）
- 对每个完整对象立即启动异步任务
- 流结束后统一等待所有任务收敛
- 最后统一汇总结果

该框架专门解决“任务列表不是预先已知、而是由流式输出动态生成”的问题。

---

## 1. 解决什么问题

传统并发模式：

1. 先得到完整列表
2. 遍历列表创建任务
3. `await gather(...)`

流式场景下的问题：

- 列表是边生成边到达，无法提前知道总量
- 如果等流结束再执行，下游处理会被整体延迟

`stream_runtime` 的目标是：

- 每解析出一个对象就立刻调度执行
- 同时继续接收后续流
- 最后一次性收敛并汇总

---

## 2. 生命周期（核心执行链路）

1. `StreamChunkSource.stream()` 持续产出 chunk
2. `IncrementalObjectParser.feed(chunk)` 增量解析对象
3. `DynamicTaskScheduler.add_task(...)` 动态添加任务
4. 流结束后 `parser.flush()` 处理尾部数据
5. `scheduler.close_and_wait()` 等待所有动态任务完成
6. `ResultAggregator` 汇总 `TaskOutcome[]`

---

## 3. 为什么分抽象层与实现层

### 抽象层（`stream_runtime/abstractions`）

定义协议和数据模型，不依赖 OpenAI SDK 或具体业务：

- `StreamChunkSource`
- `IncrementalObjectParser`
- `DynamicTaskScheduler`
- `ObjectExecutor`
- `ResultAggregator`
- `StreamOrchestrator`
- `TaskOutcome` / `OrchestrationReport`

### 实现层（`stream_runtime/implementations`）

提供默认可运行实现：

- `OpenAIStreamChunkSource`（OpenAI 兼容流）
- `JsonlIncrementalParser`（JSONL 增量解析）
- `AsyncioDynamicTaskScheduler`（动态任务调度）
- `DefaultStreamOrchestrator`（总编排）

好处：

- 业务逻辑可注入，不写死
- 未来可替换源、解析模式、调度策略
- 单元测试边界清晰

---

## 4. 快速使用

```python
source = OpenAIStreamChunkSource(...)
parser = JsonlIncrementalParser()
scheduler = AsyncioDynamicTaskScheduler(max_concurrency=8)

orchestrator = DefaultStreamOrchestrator(
    source=source,
    parser=parser,
    scheduler=scheduler,
    executor=execute_one_object,
    aggregator=aggregate_results,
)

final_result, report = await orchestrator.run()
```

其中：

- `executor(obj)`：调用方注入的异步函数
- `aggregator(outcomes)`：调用方注入的汇总函数（可同步或异步）

---

## 5. 动态任务 vs 预先已知任务

### 预先已知列表

```python
tasks = [asyncio.create_task(execute(x)) for x in known_items]
results = await asyncio.gather(*tasks)
```

### 动态流式列表（本框架）

```python
async for chunk in source.stream():
    objs = parser.feed(chunk)
    for obj in objs:
        await scheduler.add_task(executor(obj), input_object=obj)

for obj in parser.flush():
    await scheduler.add_task(executor(obj), input_object=obj)

outcomes = await scheduler.close_and_wait()
```

关键区别是：任务在接收流的过程中持续新增，并最终统一收敛。

---

## 6. 异常处理边界

- 上游流错误：记录为 `source_error`
- 解析错误：记录在 `parse_issues`，默认不中断流程
- 单任务执行错误：进入 `TaskOutcome(success=False, error=...)`
- 汇总错误：抛出 `AggregationError`

默认策略不是 fail-fast（`fail_fast=False`），适用于“尽可能多处理成功任务”的场景。

---

## 7. 最小示例

见：`stream_runtime/examples/demo_jsonl_pipeline.py`

运行前需设置：

```bash
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-4o-mini  # 可选
python -m stream_runtime.examples.demo_jsonl_pipeline
```

---

## 8. 扩展指南

### 8.1 支持非 JSONL 解析

实现 `IncrementalObjectParser` 新类（如单 JSON、数组元素流式解析），替换注入即可。

### 8.2 根据对象类型路由执行器

在外部实现 Router Executor：

- 输入对象后按 `obj["type"]` 分发到不同异步函数
- 仍通过统一 `executor` 注入 orchestrator

### 8.3 任务依赖关系

可扩展 scheduler：

- 在 `add_task` 增加依赖参数
- 内部实现 DAG 拓扑调度

### 8.4 更复杂状态管理

可在 orchestrator 增加事件钩子：

- `on_chunk`
- `on_object_parsed`
- `on_task_done`

用于指标监控、日志审计、断点恢复。

---

## 9. 目录结构

```text
stream_runtime/
  abstractions/
    __init__.py
    models.py
    errors.py
    source.py
    parser.py
    scheduler.py
    executor.py
    aggregator.py
    orchestrator.py
  implementations/
    __init__.py
    openai_source.py
    jsonl_parser.py
    asyncio_scheduler.py
    default_orchestrator.py
  examples/
    demo_jsonl_pipeline.py
  __init__.py
```

# 项目架构文档

> AI Idea Generator - 飞书文档 AI 处理后端服务
> 
> 最后更新：2025-12-31

欢迎来到 AI Idea Generator 项目架构文档！本目录包含了项目的详细架构设计、模块说明和快速参考手册。

---

## 📚 文档导航

### 🏗️ [架构概览](architecture_overview.md)
**推荐首先阅读**

全面了解项目的整体架构、设计思路和核心特性。

**包含内容**：
- 项目简介和目标
- 整体架构图
- 目录结构说明
- 核心模块概览
- 数据流转示意
- 配置文件说明
- 设计模式与优势
- 关键特性介绍
- 性能优化策略
- 未来扩展方向

**适合人群**：
- ✅ 新加入项目的开发者
- ✅ 需要了解系统全貌的技术 Leader
- ✅ 进行架构设计参考的工程师

---

### 🔍 [模块详细说明](module_details.md)
**深入了解各模块实现**

详细说明各核心模块的实现细节、接口定义和使用方式。

**包含内容**：
- LLM 客户端详解
- 流程编排器实现
- 处理器层设计
- 输出层设计
- 飞书客户端封装
- 工具层实现
- 任务存储机制

**适合人群**：
- ✅ 需要修改现有功能的开发者
- ✅ 新增 Processor 或 OutputHandler 的工程师
- ✅ 进行代码 Review 的技术专家

---

### ⚡ [快速参考手册](quick_reference.md)
**日常开发必备**

快速查找常用命令、配置和代码片段。

**包含内容**：
- 启动和部署命令
- 配置文件示例
- API 接口文档
- 测试命令大全
- 常用代码片段
- 故障排查指南
- 性能监控方法

**适合人群**：
- ✅ 日常开发和调试的工程师
- ✅ 运维和部署人员
- ✅ 问题排查和性能优化工程师

---

## 🎯 快速开始

### 对于新开发者

1. **第一步**：阅读 [架构概览](architecture_overview.md)，了解项目整体设计
2. **第二步**：浏览 [模块详细说明](module_details.md)，熟悉核心模块
3. **第三步**：参考 [快速参考手册](quick_reference.md)，开始编码

### 对于运维人员

1. **直接查看** [快速参考手册](quick_reference.md) 的以下章节：
   - 启动和部署
   - 配置文件
   - 故障排查
   - 性能监控

### 对于技术 Leader

1. **重点阅读** [架构概览](architecture_overview.md) 的以下章节：
   - 整体架构
   - 设计模式与架构优势
   - 关键特性
   - 未来扩展方向

---

## 📖 其他文档

本目录是**架构文档**，项目还包含以下文档：

### 产品和需求
- [`product_requirements.md`](../product_requirements.md) - 产品需求文档
- [`backend_fastapi_design.md`](../backend_fastapi_design.md) - 后端 API 设计
- [`backend_detailed_design.md`](../backend_detailed_design.md) - 后端详细设计
- [`implementation_plan.md`](../implementation_plan.md) - 实施计划

### SDK 文档
- [`sdk/README.md`](../../sdk/README.md) - TypeScript SDK 使用文档

---

## 🔄 文档更新记录

### 2025-12-31
- ✅ 创建架构文档目录结构
- ✅ 完成架构概览文档（750+ 行）
- ✅ 完成模块详细说明（1000+ 行）
- ✅ 完成快速参考手册（770+ 行）
- ✅ 新增智能标题生成器文档

### 未来计划
- 📝 添加 API 交互流程图
- 📝 添加性能测试报告
- 📝 添加最佳实践文档

---

## 💡 使用建议

### 如何查找信息

**场景 1：我想了解某个模块的具体实现**
- 📖 查看 [模块详细说明](module_details.md)
- 🔍 使用 Ctrl+F 搜索模块名

**场景 2：我需要配置 LLM Provider**
- ⚡ 查看 [快速参考手册](quick_reference.md) → 配置文件 → llm_config.yml

**场景 3：我要新增一个处理模式**
- 📖 查看 [模块详细说明](module_details.md) → 3.4 扩展新 Processor
- ⚡ 参考 [快速参考手册](quick_reference.md) → 常用代码片段 → 新增 Processor

**场景 4：服务启动报错，如何排查**
- ⚡ 查看 [快速参考手册](quick_reference.md) → 故障排查

**场景 5：我想了解整体架构设计思路**
- 🏗️ 查看 [架构概览](architecture_overview.md) → 整体架构 / 设计模式与架构优势

---

## 🤝 贡献指南

### 文档更新原则

1. **及时性**：代码变更时同步更新文档
2. **准确性**：确保文档与实际代码一致
3. **完整性**：涵盖所有关键功能和接口
4. **易读性**：使用清晰的结构和示例

### 如何贡献

1. 发现文档错误或过时信息 → 提交 Issue
2. 有改进建议 → 提交 Pull Request
3. 新增功能 → 同步更新相关文档

---

## 📞 联系方式

如有问题或建议，请：
- 📧 提交 Issue
- 💬 联系项目维护者

---

## 🎓 学习路径

### 初级开发者

**Week 1**：了解架构
- Day 1-2: 阅读 [架构概览](architecture_overview.md)
- Day 3-4: 尝试启动服务，运行测试
- Day 5-7: 阅读 [模块详细说明](module_details.md)，理解核心模块

**Week 2**：动手实践
- 尝试修改 Prompt（在 Processor 中）
- 配置新的 LLM Provider
- 添加日志输出

**Week 3**：功能开发
- 新增一个简单的 Processor
- 测试和调试

### 高级开发者

**Day 1**：快速上手
- 浏览 [架构概览](architecture_overview.md)
- 阅读关键模块源码

**Day 2-3**：深度定制
- 实现复杂的 Processor（如多阶段处理）
- 新增 OutputHandler（如邮件通知）
- 优化性能

---

## 🔖 快速链接

### 核心概念
- [处理器（Processor）](module_details.md#3-处理器层-processors)
- [输出器（OutputHandler）](module_details.md#4-输出层-outputhandlers)
- [LLM 客户端](module_details.md#1-llm-客户端-llmclient)
- [智能标题生成器](module_details.md#61-titlegenerator智能标题生成器)

### 配置
- [环境变量配置](quick_reference.md#env环境变量)
- [LLM 配置](quick_reference.md#llm_configymllm-配置)
- [工作流配置](quick_reference.md#workflow_configyml工作流配置)

### API
- [触发文档处理](quick_reference.md#2-触发文档处理)
- [查询任务状态](quick_reference.md#3-查询任务状态)
- [飞书事件回调](quick_reference.md#4-飞书事件回调)

### 开发
- [新增 Processor](quick_reference.md#新增-processor)
- [新增 OutputHandler](quick_reference.md#新增-outputhandler)
- [调用飞书 API](quick_reference.md#调用飞书-api)
- [调用 LLM](quick_reference.md#调用-llm)

---

## 📊 文档统计

- **总文档数**：3 个主要文档 + 1 个索引
- **总行数**：2500+ 行
- **覆盖模块**：7 个核心模块
- **代码示例**：30+ 个
- **配置示例**：10+ 个
- **故障排查案例**：6 个

---

> 📝 **维护说明**：
> - 本目录由项目维护者定期更新
> - 建议每次发版前 Review 并更新文档
> - 欢迎贡献改进建议

---

**Happy Coding! 🚀**

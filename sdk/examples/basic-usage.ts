/**
 * SDK 基础使用示例
 * 
 * 注意：这些示例需要后端服务运行在 http://127.0.0.1:8001
 */

import { FeishuAIDocSDK } from "../src/index.js";

// ============================================
// 示例 1：云盘文档 - 思路扩展（idea_expand）
// ============================================
async function example1_IdeaExpand() {
  console.log("\n========== 示例 1：云盘文档 - 思路扩展 ==========\n");

  const sdk = new FeishuAIDocSDK({
    baseUrl: "http://175.24.200.253:8001",
  });

  try {
    const result = await sdk.generate({
      // 云盘文档使用 docToken
      docToken: "doxcnxxxx",  // 替换为实际的文档 token
      userId: "ou_xxx",        // 替换为实际的用户 ID
      mode: "idea_expand",
      triggerSource: "manual_test",
      
      // 进度回调
      onProgress: (p) => {
        console.log(
          `[${p.status}] ${p.percent ?? 0}% - ${p.stage ?? ""} ${p.message ?? ""}`
        );
      },
    });

    console.log("\n✅ 生成完成！");
    console.log("子文档链接:", result.childDocUrl);
    console.log("子文档 Token:", result.childDocToken);
    console.log("任务状态:", result.task.status);
  } catch (error) {
    console.error("❌ 生成失败:", error);
  }
}

// ============================================
// 示例 2：知识库文档 - 深度调研（research）
// ============================================
async function example2_DeepResearch() {
  console.log("\n========== 示例 2：知识库文档 - 深度调研 ==========\n");

  const sdk = new FeishuAIDocSDK({
    baseUrl: "http://127.0.0.1:8001",
  });

  try {
    const result = await sdk.generate({
      // 知识库使用 token（wikcn 开头）
      token: "wikcnxxxx",      // 替换为实际的知识库 node_token
      userId: "ou_xxx",         // 替换为实际的用户 ID
      mode: "research",
      wikiSpaceId: "7xxxxx",    // 替换为实际的 space_id
      
      // 深度调研耗时较长，增加超时时间
      timeoutMs: 300_000,       // 5 分钟
      pollIntervalMs: 3000,     // 每 3 秒轮询一次
      
      onProgress: (p) => {
        const percent = p.percent ?? 0;
        const stage = p.stage ?? "";
        const message = p.message ?? "";
        console.log(`[${p.status}] ${percent}% - ${stage} ${message}`);
      },
    });

    console.log("\n✅ 调研完成！");
    console.log("子文档链接:", result.childDocUrl);
    console.log("子文档 Token:", result.childDocToken);
  } catch (error) {
    console.error("❌ 调研失败:", error);
  }
}

// ============================================
// 示例 3：分步调用（手动控制）
// ============================================
async function example3_ManualControl() {
  console.log("\n========== 示例 3：分步调用 ==========\n");

  const sdk = new FeishuAIDocSDK({
    baseUrl: "http://127.0.0.1:8001",
  });

  try {
    // 步骤 1：触发任务
    console.log("1. 触发任务...");
    const accepted = await sdk.trigger({
      docToken: "doxcnxxxx",
      userId: "ou_xxx",
      mode: "idea_expand",
    });
    console.log(`✅ 任务已接受，task_id: ${accepted.task_id}`);

    // 步骤 2：查询任务状态
    console.log("\n2. 查询任务状态...");
    let task = await sdk.getTask(accepted.task_id);
    console.log(`当前状态: ${task.status}`);

    // 步骤 3：等待任务完成
    console.log("\n3. 等待任务完成...");
    task = await sdk.waitTask(accepted.task_id, {
      pollIntervalMs: 2000,
      timeoutMs: 180_000,
    });

    console.log(`\n✅ 任务完成: ${task.status}`);
    if (task.result) {
      console.log("结果:", task.result);
    }
  } catch (error) {
    console.error("❌ 执行失败:", error);
  }
}

// ============================================
// 示例 4：错误处理
// ============================================
async function example4_ErrorHandling() {
  console.log("\n========== 示例 4：错误处理 ==========\n");

  const sdk = new FeishuAIDocSDK({
    baseUrl: "http://127.0.0.1:8001",
  });

  try {
    const result = await sdk.generate({
      docToken: "invalid_token",  // 故意使用无效 token
      userId: "ou_xxx",
      mode: "idea_expand",
      timeoutMs: 30_000,  // 30 秒超时
    });
    console.log(result);
  } catch (error) {
    // 错误类型判断
    if (error instanceof Error) {
      console.log("错误类型:", error.name);
      console.log("错误信息:", error.message);
      
      // HTTPError 类型
      if ("status" in error) {
        console.log("HTTP 状态码:", (error as any).status);
        console.log("响应内容:", (error as any).bodyText);
      }
      
      // TimeoutError 类型
      if (error.name === "TimeoutError") {
        console.log("任务超时，请稍后重试");
      }
    }
  }
}

// ============================================
// 运行示例（取消注释你想运行的示例）
// ============================================
async function main() {
  // await example1_IdeaExpand();
  // await example2_DeepResearch();
  // await example3_ManualControl();
  // await example4_ErrorHandling();
  
  console.log("\n请取消注释上面的示例代码来运行！\n");
}

main().catch(console.error);

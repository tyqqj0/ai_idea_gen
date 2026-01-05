/**
 * SDK 最小化测试脚本（Node.js）
 * 不需要编译 TypeScript，直接测试 HTTP 调用逻辑
 */

// 模拟 SDK 的核心逻辑
class TestSDK {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
  }

  async trigger(options) {
    const payload = {
      token: options.token || null,
      doc_token: options.docToken || options.token || null,  // 修复：使用 null 而不是空字符串
      user_id: options.userId,
      mode: options.mode || "idea_expand",
      trigger_source: options.triggerSource || "docs_addon",
      wiki_node_token: options.wikiNodeToken || null,
      wiki_space_id: options.wikiSpaceId || null,
    };

    console.log("📤 发送请求:");
    console.log("URL:", `${this.baseUrl}/api/addon/process`);
    console.log("Payload:", JSON.stringify(payload, null, 2));

    const response = await fetch(`${this.baseUrl}/api/addon/process`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const text = await response.text();
    console.log("\n📥 响应:");
    console.log("Status:", response.status, response.statusText);
    console.log("Body:", text);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${text}`);
    }

    return JSON.parse(text);
  }

  async getTask(taskId) {
    const url = `${this.baseUrl}/api/addon/tasks/${taskId}`;
    console.log("\n📤 查询任务:", url);

    const response = await fetch(url);
    const text = await response.text();

    console.log("📥 响应:");
    console.log("Status:", response.status, response.statusText);
    console.log("Body:", text);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${text}`);
    }

    return JSON.parse(text);
  }
}

// 测试用例
async function main() {
  // 后端地址（根据实际情况修改）
  const baseUrl = process.env.BASE_URL || "http://127.0.0.1:8001";
  
  // 测试 token（需要替换为真实的文档 token）
  const testToken = process.env.DOC_TOKEN || "doccnXXXXXXXXXXXXXX";
  const testUserId = process.env.USER_ID || "test_user_001";

  const sdk = new TestSDK(baseUrl);

  console.log("🧪 测试场景 1: 正常调用（使用 token 参数）");
  console.log("=" .repeat(60));
  try {
    const result = await sdk.trigger({
      token: testToken,
      userId: testUserId,
      mode: "idea_expand",
    });
    console.log("\n✅ 触发成功:", result);

    // 等待一下再查询
    await new Promise(r => setTimeout(r, 1000));

    const task = await sdk.getTask(result.task_id);
    console.log("\n✅ 任务查询成功:", task);
  } catch (error) {
    console.error("\n❌ 测试失败:", error.message);
  }

  console.log("\n" + "=".repeat(60));
  console.log("🧪 测试场景 2: 使用 docToken 参数");
  console.log("=" .repeat(60));
  try {
    const result = await sdk.trigger({
      docToken: testToken,
      userId: testUserId,
      mode: "idea_expand",
    });
    console.log("\n✅ 触发成功:", result);
  } catch (error) {
    console.error("\n❌ 测试失败:", error.message);
  }

  console.log("\n" + "=".repeat(60));
  console.log("🧪 测试场景 3: 缺少 token（预期失败）");
  console.log("=" .repeat(60));
  try {
    const result = await sdk.trigger({
      userId: testUserId,
      mode: "idea_expand",
    });
    console.log("\n❌ 不应该成功:", result);
  } catch (error) {
    console.log("\n✅ 预期的错误:", error.message);
  }

  console.log("\n" + "=".repeat(60));
  console.log("🧪 测试场景 4: ping 接口");
  console.log("=" .repeat(60));
  try {
    const response = await fetch(`${baseUrl}/api/ping`);
    const data = await response.json();
    console.log("✅ Ping 成功:", data);
  } catch (error) {
    console.error("❌ Ping 失败:", error.message);
  }
}

main().catch(console.error);

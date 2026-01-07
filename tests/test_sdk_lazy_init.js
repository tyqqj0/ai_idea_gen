/**
 * SDK 懒加载自动初始化测试脚本
 * 
 * 测试新功能：
 * 1. 懒加载自动初始化（模拟飞书环境）
 * 2. 快捷方法（ideaExpand, research, save）
 * 3. 通用方法（process）
 * 4. content 参数传递
 * 
 * 运行方式：
 *   node tests/test_sdk_lazy_init.js
 */

// 模拟飞书环境
globalThis.DocMiniApp = {
  getCurrentDocToken: () => {
    console.log("🔧 [Mock] DocMiniApp.getCurrentDocToken() called");
    return process.env.DOC_TOKEN || "doccnMockTokenForTest";
  },
  
  getWikiInfo: () => {
    console.log("🔧 [Mock] DocMiniApp.getWikiInfo() called");
    return null;  // 非知识库场景
  },
  
  Service: {
    User: {
      login: async () => {
        console.log("🔧 [Mock] DocMiniApp.Service.User.login() called");
        return "mock_user_code_12345";
      }
    }
  }
};

// 模拟 SDK（简化版，只测试核心逻辑）
class MockSDK {
  constructor(config) {
    this.config = config;
    this._docToken = null;
    this._openId = null;
    this._wikiNodeToken = null;
    this._wikiSpaceId = null;
  }

  // 懒加载：获取 docToken
  async ensureDocToken() {
    if (!this._docToken) {
      console.log("\n🔄 [Lazy Init] 第一次调用，获取 docToken...");
      if (this.config.docTokenProvider) {
        this._docToken = await this.config.docTokenProvider();
      } else if (typeof globalThis.DocMiniApp !== "undefined") {
        this._docToken = globalThis.DocMiniApp.getCurrentDocToken();
        
        const wikiInfo = globalThis.DocMiniApp.getWikiInfo?.();
        if (wikiInfo) {
          this._wikiNodeToken = wikiInfo.nodeToken ?? null;
          this._wikiSpaceId = wikiInfo.spaceId ?? null;
        }
      } else {
        throw new Error("无法获取 docToken");
      }
      console.log(`✅ docToken 已缓存: ${this._docToken}`);
    } else {
      console.log(`♻️  [Cache Hit] 复用缓存的 docToken: ${this._docToken}`);
    }
    return this._docToken;
  }

  // 懒加载：获取 openId
  async ensureOpenId() {
    if (!this._openId) {
      console.log("\n🔄 [Lazy Init] 第一次调用，换取 openId...");
      let code;
      if (this.config.codeProvider) {
        code = await this.config.codeProvider();
      } else if (typeof globalThis.DocMiniApp !== "undefined") {
        code = await globalThis.DocMiniApp.Service.User.login();
      } else {
        throw new Error("无法获取 code");
      }
      console.log(`  获取到 code: ${code}`);
      
      // 调用后端 /auth 接口（模拟）
      console.log(`  调用 ${this.config.baseUrl}/api/addon/auth`);
      const authResp = await this._mockAuthAPI(code);
      this._openId = authResp.open_id;
      console.log(`✅ openId 已缓存: ${this._openId}`);
    } else {
      console.log(`♻️  [Cache Hit] 复用缓存的 openId: ${this._openId}`);
    }
    return this._openId;
  }

  // 模拟后端 /auth 接口
  async _mockAuthAPI(code) {
    // 实际环境需要真实调用后端
    return { open_id: `ou_from_code_${code.slice(0, 8)}` };
  }

  // 快捷方法：思路扩展
  async ideaExpand(opts = {}) {
    console.log("\n📝 [API] ideaExpand() called");
    console.log(`   content: ${opts.content || "(未传入)"}`);
    return this.process({ mode: "idea_expand", content: opts.content });
  }

  // 快捷方法：深度调研
  async research(opts = {}) {
    console.log("\n📝 [API] research() called");
    console.log(`   content: ${opts.content || "(未传入)"}`);
    return this.process({ mode: "research", content: opts.content });
  }

  // 快捷方法：通用保存
  async save(opts) {
    console.log("\n📝 [API] save() called");
    console.log(`   content: ${opts.content.slice(0, 50)}...`);
    console.log(`   title: ${opts.title || "(自动生成)"}`);
    
    const [docToken, openId] = await Promise.all([
      this.ensureDocToken(),
      this.ensureOpenId(),
    ]);

    console.log("\n📤 [HTTP] POST /api/addon/save");
    console.log(`   Payload: { content, title, token: ${docToken}, user_id: ${openId}, ... }`);
    
    // 模拟响应
    return {
      taskId: "task_save_mock",
      status: "succeeded",
      childDocUrl: "https://feishu.cn/docx/SavedDoc123",
      childDocToken: "SavedDoc123",
    };
  }

  // 通用方法：支持任意 mode
  async process(opts) {
    console.log("\n📝 [API] process() called");
    console.log(`   mode: ${opts.mode}`);
    console.log(`   content: ${opts.content || "(未传入)"}`);

    const [docToken, openId] = await Promise.all([
      this.ensureDocToken(),
      this.ensureOpenId(),
    ]);

    console.log("\n📤 [HTTP] POST /api/addon/process");
    console.log(`   Payload: { token: ${docToken}, user_id: ${openId}, mode: ${opts.mode}, content: ${opts.content || "null"}, ... }`);
    
    // 模拟响应
    return {
      task: { task_id: "task_mock_123", status: "succeeded" },
      childDocUrl: `https://feishu.cn/docx/${opts.mode}_Result`,
      childDocToken: `${opts.mode}_Result`,
    };
  }

  // 手动设置上下文
  setContext(ctx) {
    console.log("\n🔧 [API] setContext() called");
    if (ctx.docToken) {
      console.log(`   设置 docToken: ${ctx.docToken}`);
      this._docToken = ctx.docToken;
    }
    if (ctx.wikiNodeToken) {
      console.log(`   设置 wikiNodeToken: ${ctx.wikiNodeToken}`);
      this._wikiNodeToken = ctx.wikiNodeToken;
    }
    if (ctx.wikiSpaceId) {
      console.log(`   设置 wikiSpaceId: ${ctx.wikiSpaceId}`);
      this._wikiSpaceId = ctx.wikiSpaceId;
    }
    return this;
  }

  // 清除上下文
  clearContext() {
    console.log("\n🔧 [API] clearContext() called");
    console.log("   清除 docToken, wikiNodeToken, wikiSpaceId");
    console.log("   保留 openId（用户身份不变）");
    this._docToken = null;
    this._wikiNodeToken = null;
    this._wikiSpaceId = null;
    return this;
  }
}

// ========================================
// 测试场景
// ========================================

async function testLazyInit() {
  console.log("\n" + "=".repeat(80));
  console.log("🧪 测试 1: 懒加载自动初始化");
  console.log("=".repeat(80));

  const sdk = new MockSDK({
    baseUrl: "http://127.0.0.1:8001",
  });

  console.log("\n▶️  第一次调用 ideaExpand()");
  const result1 = await sdk.ideaExpand({ content: "用户划词的文本1" });
  console.log(`\n✅ 结果: ${result1.childDocUrl}`);

  console.log("\n▶️  第二次调用 research()");
  const result2 = await sdk.research({ content: "用户划词的文本2" });
  console.log(`\n✅ 结果: ${result2.childDocUrl}`);

  console.log("\n▶️  第三次调用 save()");
  const result3 = await sdk.save({ content: "要保存的笔记内容", title: "我的笔记" });
  console.log(`\n✅ 结果: ${result3.childDocUrl}`);
}

async function testProcessMethod() {
  console.log("\n" + "=".repeat(80));
  console.log("🧪 测试 2: 通用 process() 方法（动态 mode）");
  console.log("=".repeat(80));

  const sdk = new MockSDK({
    baseUrl: "http://127.0.0.1:8001",
  });

  const tools = [
    { id: "idea_expand", name: "扩展思路" },
    { id: "research", name: "深度调研" },
    { id: "summarize", name: "总结摘要" },
  ];

  for (const tool of tools) {
    console.log(`\n▶️  用户点击 "${tool.name}"`);
    const result = await sdk.process({
      mode: tool.id,
      content: `测试内容 for ${tool.name}`,
    });
    console.log(`\n✅ 结果: ${result.childDocUrl}`);
  }
}

async function testContextManagement() {
  console.log("\n" + "=".repeat(80));
  console.log("🧪 测试 3: 上下文管理（setContext / clearContext）");
  console.log("=".repeat(80));

  const sdk = new MockSDK({
    baseUrl: "http://127.0.0.1:8001",
  });

  console.log("\n▶️  手动设置上下文");
  sdk.setContext({
    docToken: "doccnManualSet123",
    wikiNodeToken: "wikcnManualSet456",
  });

  console.log("\n▶️  调用 ideaExpand()（使用手动设置的 docToken）");
  await sdk.ideaExpand({ content: "测试内容" });

  console.log("\n▶️  清除上下文");
  sdk.clearContext();

  console.log("\n▶️  再次调用 ideaExpand()（重新获取 docToken）");
  await sdk.ideaExpand({ content: "测试内容" });
}

async function testCustomProvider() {
  console.log("\n" + "=".repeat(80));
  console.log("🧪 测试 4: 自定义 Provider（测试场景）");
  console.log("=".repeat(80));

  const sdk = new MockSDK({
    baseUrl: "http://127.0.0.1:8001",
    docTokenProvider: () => {
      console.log("🔧 [Custom] docTokenProvider() called");
      return "CustomDocToken999";
    },
    codeProvider: async () => {
      console.log("🔧 [Custom] codeProvider() called");
      return "CustomCode888";
    },
  });

  console.log("\n▶️  调用 ideaExpand()");
  await sdk.ideaExpand({ content: "测试内容" });
}

// ========================================
// 运行测试
// ========================================

async function main() {
  console.log("\n");
  console.log("╔═══════════════════════════════════════════════════════════════════════════╗");
  console.log("║               SDK 懒加载自动初始化功能测试                                 ║");
  console.log("╚═══════════════════════════════════════════════════════════════════════════╝");

  try {
    await testLazyInit();
    await testProcessMethod();
    await testContextManagement();
    await testCustomProvider();

    console.log("\n" + "=".repeat(80));
    console.log("🎉 所有测试完成！");
    console.log("=".repeat(80));
  } catch (error) {
    console.error("\n❌ 测试失败:", error);
    process.exit(1);
  }
}

main().catch(console.error);

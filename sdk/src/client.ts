import { TimeoutError } from "./errors.js";
import { HttpClient } from "./http.js";
import type {
  AddonProcessAccepted,
  AddonProcessRequest,
  AuthRequest,
  AuthResponse,
  GenerateOptions,
  GenerateResult,
  IdeaExpandOptions,
  ProcessOptions,
  ResearchOptions,
  SaveOptions,
  SaveResult,
  SDKConfig,
  TaskStatusResponse,
  TriggerOptions,
} from "./types.js";

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

export class FeishuAIDocSDK {
  private readonly http: HttpClient;
  private readonly config: SDKConfig;

  // 环境信息缓存（懒加载）
  private _docToken: string | null = null;
  private _openId: string | null = null;
  private _wikiNodeToken: string | null = null;
  private _wikiSpaceId: string | null = null;

  constructor(cfg: SDKConfig) {
    this.config = cfg;
    this.http = new HttpClient(cfg);
  }

  // ====== 懒加载环境信息 ======

  /**
   * 确保获取到文档 token（懒加载）
   */
  private async ensureDocToken(): Promise<string> {
    if (!this._docToken) {
      if (this.config.docTokenProvider) {
        this._docToken = await this.config.docTokenProvider();
      } else if (typeof globalThis !== "undefined" && (globalThis as any).DocMiniApp) {
        const DocMiniApp = (globalThis as any).DocMiniApp;
        
        // 使用官方 API：getActiveDocumentRef() 是异步方法，返回 { docToken: "xxx" }
        const docRef = await DocMiniApp.getActiveDocumentRef();
        this._docToken = docRef?.docToken ?? null;

        // 顺便获取知识库信息
        if (this.config.wikiInfoProvider) {
          const wikiInfo = await this.config.wikiInfoProvider();
          this._wikiNodeToken = wikiInfo.nodeToken ?? null;
          this._wikiSpaceId = wikiInfo.spaceId ?? null;
        } else if (DocMiniApp.getWikiInfo) {
          const wikiInfo = DocMiniApp.getWikiInfo();
          if (wikiInfo) {
            this._wikiNodeToken = wikiInfo.nodeToken ?? null;
            this._wikiSpaceId = wikiInfo.spaceId ?? null;
          }
        }
      } else {
        throw new Error("无法获取 docToken，请提供 config.docTokenProvider");
      }
    }
    if (!this._docToken) {
      throw new Error("docToken 获取失败");
    }
    return this._docToken;
  }

  /**
   * 确保获取到用户 openId（懒加载）
   */
  private async ensureOpenId(): Promise<string> {
    if (!this._openId) {
      let code: string;
      if (this.config.codeProvider) {
        code = await this.config.codeProvider();
      } else if (typeof globalThis !== "undefined" && (globalThis as any).DocMiniApp) {
        const DocMiniApp = (globalThis as any).DocMiniApp;
        code = await DocMiniApp.Service.User.login();
      } else {
        throw new Error("无法获取用户 code，请提供 config.codeProvider");
      }

      // 调用后端认证接口换取 openId
      const payload: AuthRequest = { code };
      const resp = await this.http.postJSON<AuthResponse>("/addon/auth", payload);
      this._openId = resp.open_id;
    }
    if (!this._openId) {
      throw new Error("openId 获取失败");
    }
    return this._openId;
  }

  // ====== 通用处理接口 ======

  /**
   * 通用处理方法：支持任意 mode（灵活调用）
   */
  public async process(opts: ProcessOptions): Promise<GenerateResult> {
    const [docToken, openId] = await Promise.all([
      this.ensureDocToken(),
      this.ensureOpenId(),
    ]);

    const payload: AddonProcessRequest = {
      token: docToken,
      doc_token: docToken,
      user_id: openId,
      mode: opts.mode,
      content: opts.content ?? null,
      wiki_node_token: this._wikiNodeToken,
      wiki_space_id: this._wikiSpaceId,
      trigger_source: "docs_addon",
    };

    const accepted = await this.http.postJSON<AddonProcessAccepted>("/addon/process", payload);
    return this._waitAndExtract(accepted.task_id);
  }

  /**
   * 快捷方法：思路扩展
   */
  public async ideaExpand(opts: IdeaExpandOptions = {}): Promise<GenerateResult> {
    return this.process({ mode: "idea_expand", content: opts.content });
  }

  /**
   * 快捷方法：深度调研
   */
  public async research(opts: ResearchOptions = {}): Promise<GenerateResult> {
    return this.process({ mode: "research", content: opts.content });
  }

  /**
   * 通用保存：不经过处理，直接保存内容为子文档
   */
  public async save(opts: SaveOptions): Promise<SaveResult> {
    const [docToken, openId] = await Promise.all([
      this.ensureDocToken(),
      this.ensureOpenId(),
    ]);

    const payload = {
      content: opts.content,
      title: opts.title ?? null,
      token: docToken,
      user_id: openId,
      wiki_node_token: this._wikiNodeToken,
      wiki_space_id: this._wikiSpaceId,
    };

    const accepted = await this.http.postJSON<AddonProcessAccepted>("/addon/save", payload);
    const task = await this.waitTask(accepted.task_id);

    const result = task.result ?? {};
    return {
      taskId: task.task_id,
      status: task.status === "succeeded" ? "succeeded" : "failed",
      childDocUrl: typeof result["child_doc_url"] === "string" ? result["child_doc_url"] : undefined,
      childDocToken: typeof result["child_doc_token"] === "string" ? result["child_doc_token"] : undefined,
      containerUrl: typeof result["container_url"] === "string" ? result["container_url"] : undefined,
      error: task.error ?? undefined,
    };
  }

  // ====== 手动设置和清除（高级用法）======

  /**
   * 手动设置环境上下文（可选，用于特殊场景）
   */
  public setContext(ctx: {
    docToken?: string;
    wikiNodeToken?: string;
    wikiSpaceId?: string;
  }): this {
    if (ctx.docToken) this._docToken = ctx.docToken;
    if (ctx.wikiNodeToken) this._wikiNodeToken = ctx.wikiNodeToken;
    if (ctx.wikiSpaceId) this._wikiSpaceId = ctx.wikiSpaceId;
    return this;
  }

  /**
   * 清除文档上下文缓存（切换文档时使用）
   * 注意：openId 不会被清除（用户身份不变）
   */
  public clearContext(): this {
    this._docToken = null;
    this._wikiNodeToken = null;
    this._wikiSpaceId = null;
    return this;
  }

  // ====== 内部辅助方法 ======

  /**
   * 等待任务完成并提取结果
   */
  private async _waitAndExtract(taskId: string): Promise<GenerateResult> {
    const task = await this.waitTask(taskId);
    const result = task.result ?? {};
    return {
      task,
      childDocUrl: typeof result["child_doc_url"] === "string" ? result["child_doc_url"] : undefined,
      childDocToken: typeof result["child_doc_token"] === "string" ? result["child_doc_token"] : undefined,
      containerUrl: typeof result["container_url"] === "string" ? result["container_url"] : undefined,
      containerToken: typeof result["container_token"] === "string" ? result["container_token"] : undefined,
      error: task.error ?? undefined,
    };
  }

  // ====== 原有方法（保持向后兼容）======

  /**
   * 触发处理：对应后端 POST /api/addon/process
   * （保持向后兼容，需要手动传入 userId）
   */
  public async trigger(options: TriggerOptions): Promise<AddonProcessAccepted> {
    const payload: AddonProcessRequest = {
      token: options.token ?? null,
      doc_token: options.docToken ?? options.token ?? null,  // 优先使用 docToken，其次 token，避免空字符串
      user_id: options.userId,
      mode: options.mode,
      content: options.content ?? null,  // 支持划词文本
      trigger_source: options.triggerSource ?? "docs_addon",
      wiki_node_token: options.wikiNodeToken ?? null,
      wiki_space_id: options.wikiSpaceId ?? null,
    };
    return await this.http.postJSON<AddonProcessAccepted>("/addon/process", payload);
  }

  /**
   * 查询任务状态：对应后端 GET /api/addon/tasks/{task_id}
   */
  public async getTask(taskId: string): Promise<TaskStatusResponse> {
    return await this.http.getJSON<TaskStatusResponse>(`/addon/tasks/${taskId}`);
  }

  /**
   * 等待任务完成（轮询）
   */
  public async waitTask(
    taskId: string,
    opts?: { pollIntervalMs?: number; timeoutMs?: number }
  ): Promise<TaskStatusResponse> {
    const pollIntervalMs = opts?.pollIntervalMs ?? 2000;
    const timeoutMs = opts?.timeoutMs ?? 180_000;
    const deadline = Date.now() + timeoutMs;

    while (true) {
      const task = await this.getTask(taskId);
      if (task.status === "succeeded" || task.status === "failed") return task;
      if (Date.now() >= deadline) {
        throw new TimeoutError(`waitTask timeout: task_id=${taskId}`);
      }
      await sleep(pollIntervalMs);
    }
  }

  /**
   * 一键：触发 + 等待完成（带进度回调）
   */
  public async generate(options: GenerateOptions): Promise<GenerateResult> {
    const accepted = await this.trigger(options);
    const taskId = accepted.task_id;

    const pollIntervalMs = options.pollIntervalMs ?? 2000;
    const timeoutMs = options.timeoutMs ?? 180_000;
    const deadline = Date.now() + timeoutMs;

    let lastStage: string | undefined;
    let lastPercent: number | undefined;
    let lastStatus: string | undefined;

    while (true) {
      const task = await this.getTask(taskId);
      const stage = task.progress?.stage ?? undefined;
      const percent = task.progress?.percent ?? undefined;
      const message = task.progress?.message ?? undefined;

      const statusChanged = task.status !== lastStatus;
      const stageChanged = stage !== lastStage;
      const percentChanged = percent !== lastPercent;

      if (options.onProgress && (statusChanged || stageChanged || percentChanged)) {
        options.onProgress({
          taskId,
          status: task.status,
          stage,
          percent,
          message,
          raw: task,
        });
      }

      lastStatus = task.status;
      lastStage = stage;
      lastPercent = percent;

      if (task.status === "succeeded" || task.status === "failed") {
        const result = task.result ?? {};
        return {
          task,
          childDocUrl: typeof result["child_doc_url"] === "string" ? result["child_doc_url"] : undefined,
          childDocToken: typeof result["child_doc_token"] === "string" ? result["child_doc_token"] : undefined,
          containerUrl: typeof result["container_url"] === "string" ? result["container_url"] : undefined,
          containerToken: typeof result["container_token"] === "string" ? result["container_token"] : undefined,
          error: task.error ?? undefined,
        };
      }

      if (Date.now() >= deadline) {
        throw new TimeoutError(`generate timeout: task_id=${taskId}`);
      }
      await sleep(pollIntervalMs);
    }
  }
}



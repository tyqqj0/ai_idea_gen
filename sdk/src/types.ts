export type Mode = string;

export interface AddonProcessRequest {
  /**
   * 统一入口：可传 doc_token（doccn/doxc）或 wiki node_token（wikcn...）
   * 若同时传 token 与 doc_token，则后端优先使用 token。
   */
  token?: string | null;
  doc_token?: string | null;  // 修改为可选，与后端对齐
  user_id: string;
  mode?: Mode;
  content?: string | null;  // 用户选中的文本（划词内容）
  trigger_source?: string | null;
  wiki_node_token?: string | null;
  wiki_space_id?: string | null;
}

export interface AuthRequest {
  code: string;
}

export interface AuthResponse {
  open_id: string;
}

export interface AddonProcessAccepted {
  task_id: string;
  status: "accepted";
  message: string;
}

export type TaskStatus = "running" | "succeeded" | "failed";

export interface TaskStatusResponse {
  task_id: string;
  status: TaskStatus;
  result?: Record<string, unknown> | null;
  error?: string | null;
  progress?: {
    stage?: string;
    percent?: number;
    message?: string;
  } | null;
  mode?: string;
  doc_token?: string;
  user_id?: string;
  created_at: number;
  updated_at?: number | null;
}

export interface SDKConfig {
  /**
   * 后端 baseUrl，例如：
   * - 本地开发：http://127.0.0.1:8001
   * - 生产环境：https://your-api-domain.com
   */
  baseUrl: string;

  /**
   * 后端路由前缀（默认 /api，对应 FastAPI include_router(prefix="/api")）
   */
  apiPrefix?: string;

  /**
   * 可选：提供鉴权 token（如果后端未来加了鉴权）
   * SDK 不强依赖该 token；未提供则不发送 Authorization 头。
   */
  authProvider?: () => Promise<string> | string;

  /**
   * fetch 实现注入（便于小程序/Node 环境）
   * 默认使用 globalThis.fetch
   */
  fetch?: typeof fetch;

  /**
   * 可选：自定义获取文档 token 的方式（测试/特殊场景）
   * 默认使用飞书环境的 getCurrentDocToken()
   */
  docTokenProvider?: () => string | Promise<string>;

  /**
   * 可选：自定义获取知识库信息的方式
   * 默认从飞书环境获取
   */
  wikiInfoProvider?: () => { nodeToken?: string; spaceId?: string } | Promise<{ nodeToken?: string; spaceId?: string }>;

  /**
   * 可选：自定义获取用户登录 code 的方式
   * 默认调用 DocMiniApp.Service.User.login()
   */
  codeProvider?: () => Promise<string>;
}

export interface TriggerOptions {
  /**
   * 可选：统一入口 token（doc_token 或 wiki node_token）
   * 若不传则使用 docToken
   */
  token?: string;
  /**
   * 可选：云盘文档 token（doccn/doxc 开头）
   * 如果传了 token 参数，可以不传 docToken
   */
  docToken?: string;
  userId: string;
  mode?: Mode;
  content?: string;  // 用户选中的文本（划词内容）
  triggerSource?: string;
  wikiNodeToken?: string;
  wikiSpaceId?: string;
}

export interface ProcessOptions {
  mode: string;
  content?: string;
  [key: string]: any;  // 允许扩展参数
}

export interface IdeaExpandOptions {
  content?: string;
}

export interface ResearchOptions {
  content?: string;
}

export interface SaveOptions {
  content: string;
  title?: string;
}

export interface GenerateOptions extends TriggerOptions {
  /**
   * 轮询间隔（毫秒）
   */
  pollIntervalMs?: number;
  /**
   * 最大等待时间（毫秒）
   */
  timeoutMs?: number;
  /**
   * 进度回调：每次轮询拿到新状态/进度时触发
   */
  onProgress?: (evt: {
    taskId: string;
    status: TaskStatus;
    stage?: string;
    percent?: number;
    message?: string;
    raw: TaskStatusResponse;
  }) => void;
}

export interface GenerateResult {
  task: TaskStatusResponse;
  /**
   * 兼容后端现有结构：如果输出是子文档，通常在 task.result.child_doc_url 中
   */
  childDocUrl?: string;
  childDocToken?: string;
  containerUrl?: string;
  containerToken?: string;
  error?: string;
}

export interface SaveResult {
  taskId: string;
  status: "succeeded" | "failed";
  childDocUrl?: string;
  childDocToken?: string;
  containerUrl?: string;
  error?: string;
}



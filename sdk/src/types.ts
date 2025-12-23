export type Mode = string;

export interface AddonProcessRequest {
  doc_token: string;
  user_id: string;
  mode?: Mode;
  trigger_source?: string | null;
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
  created_at: number;
  updated_at?: number | null;
}

export interface SDKConfig {
  /**
   * 后端 baseUrl，例如：
   * - 本地：http://127.0.0.1:8001
   * - 生产：https://api.example.com
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
}

export interface TriggerOptions {
  docToken: string;
  userId: string;
  mode?: Mode;
  triggerSource?: string;
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
}

export interface GenerateResult {
  task: TaskStatusResponse;
  /**
   * 兼容后端现有结构：如果输出是子文档，通常在 task.result.child_doc_url 中
   */
  childDocUrl?: string;
  childDocToken?: string;
}



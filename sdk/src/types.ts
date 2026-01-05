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
  trigger_source?: string | null;
  wiki_node_token?: string | null;
  wiki_space_id?: string | null;
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
  triggerSource?: string;
  wikiNodeToken?: string;
  wikiSpaceId?: string;
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
}



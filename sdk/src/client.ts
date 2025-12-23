import { TimeoutError } from "./errors.js";
import { HttpClient } from "./http.js";
import type {
    AddonProcessAccepted,
    AddonProcessRequest,
    GenerateOptions,
    GenerateResult,
    SDKConfig,
    TaskStatusResponse,
    TriggerOptions,
} from "./types.js";

function sleep(ms: number): Promise<void> {
    return new Promise((r) => setTimeout(r, ms));
}

export class FeishuAIDocSDK {
    private readonly http: HttpClient;

    constructor(cfg: SDKConfig) {
        this.http = new HttpClient(cfg);
    }

    /**
     * 触发处理：对应后端 POST /api/addon/process
     */
    public async trigger(options: TriggerOptions): Promise<AddonProcessAccepted> {
        const payload: AddonProcessRequest = {
            doc_token: options.docToken,
            user_id: options.userId,
            mode: options.mode,
            trigger_source: options.triggerSource ?? "docs_addon",
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
     * 一键：触发 + 等待完成
     */
    public async generate(options: GenerateOptions): Promise<GenerateResult> {
        const accepted = await this.trigger(options);
        const task = await this.waitTask(accepted.task_id, {
            pollIntervalMs: options.pollIntervalMs,
            timeoutMs: options.timeoutMs,
        });

        const result = task.result ?? {};
        const childDocUrl = typeof result["child_doc_url"] === "string" ? (result["child_doc_url"] as string) : undefined;
        const childDocToken = typeof result["child_doc_token"] === "string" ? (result["child_doc_token"] as string) : undefined;

        return { task, childDocUrl, childDocToken };
    }
}



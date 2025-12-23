import { HTTPError } from "./errors.js";
import type { SDKConfig } from "./types.js";

function joinUrl(base: string, path: string): string {
  const b = base.replace(/\/+$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${b}${p}`;
}

export class HttpClient {
  private readonly baseUrl: string;
  private readonly apiPrefix: string;
  private readonly authProvider?: SDKConfig["authProvider"];
  private readonly fetchImpl: typeof fetch;

  constructor(cfg: SDKConfig) {
    this.baseUrl = cfg.baseUrl;
    this.apiPrefix = cfg.apiPrefix ?? "/api";
    this.authProvider = cfg.authProvider;
    this.fetchImpl = cfg.fetch ?? globalThis.fetch;
    if (!this.fetchImpl) {
      throw new Error("No fetch implementation found. Please pass config.fetch.");
    }
  }

  public async postJSON<TResp>(
    path: string,
    body: unknown
  ): Promise<TResp> {
    return await this.requestJSON<TResp>(path, {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "Content-Type": "application/json" },
    });
  }

  public async getJSON<TResp>(path: string): Promise<TResp> {
    return await this.requestJSON<TResp>(path, { method: "GET" });
  }

  private async requestJSON<TResp>(
    path: string,
    init: RequestInit
  ): Promise<TResp> {
    const url = joinUrl(this.baseUrl, joinUrl(this.apiPrefix, path));
    const headers = new Headers(init.headers ?? {});

    const token = await this.getAuthToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const resp = await this.fetchImpl(url, { ...init, headers });
    const text = await resp.text();

    if (!resp.ok) {
      throw new HTTPError(`HTTP ${resp.status} for ${url}`, {
        status: resp.status,
        bodyText: text,
      });
    }

    try {
      return JSON.parse(text) as TResp;
    } catch {
      // 后端理论上都返回 JSON；这里保持容错，便于定位问题
      throw new HTTPError(`Invalid JSON response for ${url}`, {
        status: resp.status,
        bodyText: text,
      });
    }
  }

  private async getAuthToken(): Promise<string | undefined> {
    if (!this.authProvider) return undefined;
    const t = await this.authProvider();
    const token = typeof t === "string" ? t : String(t);
    return token.trim() ? token : undefined;
  }
}



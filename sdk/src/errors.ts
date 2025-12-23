export class SDKError extends Error {
  public readonly name = "SDKError";
}

export class HTTPError extends SDKError {
  public readonly name = "HTTPError";
  public readonly status: number;
  public readonly bodyText?: string;

  constructor(message: string, opts: { status: number; bodyText?: string }) {
    super(message);
    this.status = opts.status;
    this.bodyText = opts.bodyText;
  }
}

export class TimeoutError extends SDKError {
  public readonly name = "TimeoutError";
}



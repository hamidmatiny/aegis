export class AegisError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AegisError";
  }
}

export class AegisPolicyBlockedError extends AegisError {
  layer: string;
  policyAction?: string;
  details?: Record<string, unknown>;

  constructor(
    message: string,
    opts: { layer: string; policyAction?: string; details?: Record<string, unknown> },
  ) {
    super(message);
    this.name = "AegisPolicyBlockedError";
    this.layer = opts.layer;
    this.policyAction = opts.policyAction;
    this.details = opts.details;
  }
}

export class AegisProviderError extends AegisError {
  statusCode?: number;
  errorType?: string;
  details?: Record<string, unknown>;

  constructor(
    message: string,
    opts: { statusCode?: number; errorType?: string; details?: Record<string, unknown> } = {},
  ) {
    super(message);
    this.name = "AegisProviderError";
    this.statusCode = opts.statusCode;
    this.errorType = opts.errorType;
    this.details = opts.details;
  }
}

export class AegisApprovalRequiredError extends AegisError {
  approvalId: string;
  toolName?: string;

  constructor(
    message: string,
    opts: { approvalId: string; toolName?: string; details?: Record<string, unknown> },
  ) {
    super(message);
    this.name = "AegisApprovalRequiredError";
    this.approvalId = opts.approvalId;
    this.toolName = opts.toolName;
  }
}

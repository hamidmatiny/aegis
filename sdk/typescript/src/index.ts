import {
  AegisApprovalRequiredError,
  AegisPolicyBlockedError,
  AegisProviderError,
} from "./errors.js";

export type AegisClientOptions = {
  baseUrl?: string;
  apiKey?: string;
  inputDefenseUrl?: string;
  outputDefenseUrl?: string;
  policyEngineUrl?: string;
  modelRouterUrl?: string;
  agentGateUrl?: string;
  tenantId?: string;
  defaultModel?: string;
};

type ChatMessage = { role: string; content: string };
type ChatCreateParams = {
  model?: string;
  messages: ChatMessage[];
  provider?: string;
  stream?: boolean;
  temperature?: number;
  max_tokens?: number;
};

function env(key: string, fallback: string): string {
  return process.env[key] ?? fallback;
}

async function postJson<T>(url: string, body: unknown, apiKey?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (apiKey) headers.Authorization = `Bearer ${apiKey}`;
  const resp = await fetch(url, { method: "POST", headers, body: JSON.stringify(body) });
  const data = (await resp.json()) as Record<string, unknown>;
  if (resp.status === 403) {
    const err = (data.error ?? {}) as Record<string, unknown>;
    if (err.type === "aegis_approval_required") {
      throw new AegisApprovalRequiredError(String(err.message ?? "approval required"), {
        approvalId: String(err.approval_id ?? ""),
        toolName: err.tool_name as string | undefined,
      });
    }
    throw new AegisPolicyBlockedError(String(err.message ?? "blocked"), {
      layer: String(err.layer ?? "policy"),
      policyAction: err.policy_action as string | undefined,
      details: data,
    });
  }
  if (!resp.ok) {
    const err = data.error;
    throw new AegisProviderError(typeof err === "string" ? err : JSON.stringify(err), {
      statusCode: resp.status,
      details: data,
    });
  }
  return data as T;
}

export class OpenAI {
  private opts: Required<Pick<AegisClientOptions, "tenantId" | "defaultModel">> &
    AegisClientOptions;

  chat: { completions: { create: (params: ChatCreateParams) => Promise<unknown> } };
  tools: {
    evaluate: (params: { tool_call: Record<string, unknown> }) => Promise<unknown>;
  };

  constructor(options: AegisClientOptions = {}) {
    this.opts = {
      tenantId: options.tenantId ?? env("AEGIS_DEFAULT_TENANT_ID", "default"),
      defaultModel: options.defaultModel ?? env("AEGIS_DEFAULT_MODEL", "mock-model"),
      ...options,
    };
    this.chat = {
      completions: {
        create: (params) => this.createCompletion(params),
      },
    };
    this.tools = {
      evaluate: (params) => this.evaluateTool(params.tool_call),
    };
  }

  private serviceUrls() {
    return {
      input: this.opts.inputDefenseUrl ?? env("AEGIS_INPUT_DEFENSE_URL", "http://localhost:8090"),
      output: this.opts.outputDefenseUrl ?? env("AEGIS_OUTPUT_DEFENSE_URL", "http://localhost:8091"),
      policy: this.opts.policyEngineUrl ?? env("AEGIS_POLICY_ENGINE_URL", "http://localhost:8081"),
      router: this.opts.modelRouterUrl ?? env("AEGIS_MODEL_ROUTER_URL", "http://localhost:8082"),
      gate: this.opts.agentGateUrl ?? env("AEGIS_AGENT_GATE_URL", "http://localhost:8083"),
    };
  }

  async createCompletion(params: ChatCreateParams): Promise<unknown> {
    if (this.opts.baseUrl) {
      return postJson(
        `${this.opts.baseUrl.replace(/\/$/, "")}/chat/completions`,
        params,
        this.opts.apiKey,
      );
    }
    const urls = this.serviceUrls();
    const model = params.model ?? this.opts.defaultModel;
    const userText = params.messages.filter((m) => m.role === "user").map((m) => m.content).join("\n\n");
    const trace = { trace_id: crypto.randomUUID(), request_id: crypto.randomUUID() };

    const inputResp = await postJson<{ verdict: Record<string, unknown> }>(`${urls.input}/analyze`, {
      tenant_id: this.opts.tenantId,
      trace,
      text: userText,
    });
    if (String(inputResp.verdict.action).toUpperCase() === "BLOCK") {
      throw new AegisPolicyBlockedError("Input blocked by input-defense", {
        layer: "input_defense",
        details: { input_verdict: inputResp.verdict },
      });
    }

    const policyIn = await postJson<{ decision: Record<string, unknown> }>(
      `${urls.policy}/v1/evaluate/input`,
      { tenant_id: this.opts.tenantId, mode: "enforce", trace, input_verdict: inputResp.verdict },
    );
    if (String(policyIn.decision.action).toLowerCase() === "block") {
      throw new AegisPolicyBlockedError("Blocked by input policy", {
        layer: "policy_input",
        policyAction: String(policyIn.decision.action),
        details: { policy_decision: policyIn.decision },
      });
    }

    const llm = await postJson<Record<string, unknown>>(`${urls.router}/v1/chat/completions`, {
      model,
      messages: params.messages,
      provider: params.provider,
      temperature: params.temperature,
      max_tokens: params.max_tokens,
    });

    const choices = llm.choices as Array<{ message: { content: string } }>;
    const content = choices[0]?.message?.content ?? "";

    const outputResp = await postJson<{ verdict: Record<string, unknown> }>(`${urls.output}/analyze`, {
      tenant_id: this.opts.tenantId,
      trace,
      content,
      original_prompt: userText,
    });
    if (String(outputResp.verdict.action).toUpperCase() === "BLOCK") {
      throw new AegisPolicyBlockedError("Output blocked by output-defense", {
        layer: "output_defense",
        details: { output_verdict: outputResp.verdict },
      });
    }

    const policyOut = await postJson<{ decision: Record<string, unknown> }>(
      `${urls.policy}/v1/evaluate/output`,
      { tenant_id: this.opts.tenantId, mode: "enforce", trace, output_verdict: outputResp.verdict },
    );
    if (String(policyOut.decision.action).toLowerCase() === "block") {
      throw new AegisPolicyBlockedError("Blocked by output policy", {
        layer: "policy_output",
        policyAction: String(policyOut.decision.action),
      });
    }

    const redacted = outputResp.verdict.redacted_content as string | undefined;
    if (redacted) choices[0].message.content = redacted;
    llm.aegis = {
      trace_id: trace.trace_id,
      request_id: trace.request_id,
      input_verdict: inputResp.verdict,
      output_verdict: outputResp.verdict,
    };
    return llm;
  }

  async evaluateTool(toolCall: Record<string, unknown>): Promise<unknown> {
    if (this.opts.baseUrl) {
      throw new AegisProviderError("Tool evaluation requires embedded mode (omit baseUrl)", {
        errorType: "unsupported_in_proxy_mode",
      });
    }
    const urls = this.serviceUrls();
    const trace = { trace_id: crypto.randomUUID(), request_id: crypto.randomUUID() };
    const resp = await postJson<{ decision: Record<string, unknown> }>(`${urls.gate}/v1/evaluate`, {
      tenant_id: this.opts.tenantId,
      mode: "enforce",
      trace,
      tool_call: toolCall,
    });
    const status = String(resp.decision.status ?? "");
    if (status === "AWAITING_HUMAN_APPROVAL") {
      throw new AegisApprovalRequiredError("Human approval required", {
        approvalId: String(resp.decision.approval_request_id ?? ""),
        toolName: toolCall.tool_name as string | undefined,
      });
    }
    if (status === "DENIED") {
      throw new AegisPolicyBlockedError(String(resp.decision.denial_reason ?? "denied"), {
        layer: "tool_gate",
      });
    }
    return resp;
  }
}

export { AegisApprovalRequiredError, AegisError, AegisPolicyBlockedError, AegisProviderError } from "./errors.js";
